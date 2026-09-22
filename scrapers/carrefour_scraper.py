"""
Carrefour scraper — Descuentos Bancarios

Itera sobre cada día de la semana usando ?filtro=por-dia&dia=X para garantizar
que se capturan todas las cards de cada día (la URL base tiene lazy-loading que
perdía la mayoría de las promos).

Flujo:
  1. Para cada día (lunes..domingo) navega a la URL filtrada
  2. Espera a que aparezca el primer cardBox VTEX
  3. Ejecuta JS que expande todos los "Ver Legal"
  4. Parsea con BeautifulSoup
  5. Dedup global por (entidad, descuento, valid_days, store_types)
"""
import asyncio
from datetime import date
import re
import os
from typing import Any, Dict, List, Optional

from .base_scraper import BaseScraper

# El endpoint JSON de VTEX no necesita BeautifulSoup. Mantener el import opcional
# permite seguir usando esa fuente aun si el fallback con navegador no está instalado.
try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover - solo afecta al fallback HTML
    BeautifulSoup = None


_DAYS = [
    'lunes', 'martes', 'miercoles', 'jueves',
    'viernes', 'sabado', 'domingo',
]
_SESSION = 'carrefour_session'
_VTEX_CARD = '[class*="valtech-carrefourar-bank-promotions"][class*="cardBox"]'
_JS_EXPAND_LEGAL = (
    'document.querySelectorAll(\'[class*="legalHeader"]\')'
    ".forEach(b => { try { b.click(); } catch(e) {} });"
)

# Carrefour publica estas mismas promociones en el backend VTEX que consume su UI.
# Son constantes deliberadas: no se construyen a partir de datos externos ni del usuario.
_VTEX_GRAPHQL_URL = (
    'https://www.carrefour.com.ar/_v/private/graphql/v1?workspace=master&locale=es-AR'
)
_VTEX_GRAPHQL_QUERY = '''
query GetPromotions($account: String) @context(sender: "valtech.carrefourar-bank-promotions@0.x") {
  documents(
    acronym: "BP",
    schema: "mdv1",
    fields: [
      "id", "title", "sub_title", "discount_percentage",
      "discounts_amount_installments", "discounts_text_installments",
      "discount_text_info", "img_card", "hyper", "market", "ecommerce",
      "express", "maxi", "legal", "valid", "monday", "tuesday",
      "wednesday", "thursday", "friday", "saturday", "sunday",
      "idBank", "idCard"
    ],
    sort: "order ASC",
    account: $account,
    pageSize: 999
  ) @context(provider: "vtex.store-graphql") {
    fields { key value }
  }
}
'''
_VTEX_HEADERS = {
    'content-type': 'application/json',
    'x-vtex-tenant': 'carrefourargentina',
}
_DAY_LABELS = {
    'monday': 'Lunes',
    'tuesday': 'Martes',
    'wednesday': 'Miércoles',
    'thursday': 'Jueves',
    'friday': 'Viernes',
    'saturday': 'Sábado',
    'sunday': 'Domingo',
}
_STORE_LABELS = {
    'hyper': 'Hipermercado',
    'market': 'Market',
    'ecommerce': 'Online',
    'express': 'Express',
    'maxi': 'Maxi',
}

# Image URL fragments → (bank, wallet)
_IMG_PATTERNS: List[tuple] = [
    ('cuenta_dni',     None,             'Cuenta DNI'),
    ('cuentadni',      None,             'Cuenta DNI'),
    ('mercadopago',    None,             'Mercado Pago'),
    ('mercado_pago',   None,             'Mercado Pago'),
    ('mercado-pago',   None,             'Mercado Pago'),
    ('modo',           None,             'MODO'),
    ('bna',            'Banco Nación',   None),
    ('nacion',         'Banco Nación',   None),
    ('galicia',        'Banco Galicia',  None),
    ('santander',      'Santander',      None),
    ('macro',          'Macro',          None),
    ('patagonia',      'Banco Patagonia', None),
    ('provincia',      'Banco Provincia', None),
    ('supervielle',    'Supervielle',    None),
    ('ciudad',         'Banco Ciudad',   None),
    ('hsbc',           'HSBC',           None),
    ('icbc',           'ICBC',           None),
    ('naranja',        None,             None),  # handled below as card_type
    ('club-la-nacion', None,             None),  # handled below
]


class CarrefourScraper(BaseScraper):
    def __init__(self):
        super().__init__(
            name='Carrefour',
            url='https://www.carrefour.com.ar/descuentos-bancarios'
        )

    async def scrape(self, page=None) -> List[Dict]:
        """page aceptado para compatibilidad pero no se usa."""
        print(f"🔍 Scraping {self.name}...")

        # Fuente primaria: no depende de selectores visuales ni de lazy loading.
        graphql_promotions = await self._scrape_vtex_graphql()
        if graphql_promotions:
            print(f"✅ {self.name}: {len(graphql_promotions)} promociones encontradas (VTEX API)")
            return graphql_promotions

        # Fallback para no dejar de intentar si Carrefour cambia temporalmente la API.
        try:
            from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, BrowserConfig, CacheMode
        except ImportError:
            print("   ⚠️ Fuente VTEX sin resultados y crawl4ai no está instalado")
            return []

        if BeautifulSoup is None:
            print("   ⚠️ Fuente VTEX sin resultados y BeautifulSoup no está instalado")
            return []

        print(f"   🌐 Fallback HTML: {self.url}")

        browser_cfg = BrowserConfig(headless=True, verbose=False)
        all_promotions: List[Dict] = []
        seen: set = set()

        try:
            async with AsyncWebCrawler(config=browser_cfg) as crawler:
                for day in _DAYS:
                    day_url = f"{self.url}?filtro=por-dia&dia={day}"
                    print(f"\n   📆 {day.capitalize()}...")

                    run_cfg = CrawlerRunConfig(
                        session_id=_SESSION,
                        wait_for=f"css:{_VTEX_CARD}",
                        js_code=_JS_EXPAND_LEGAL,
                        delay_before_return_html=2.5,
                        page_timeout=30000,
                        cache_mode=CacheMode.BYPASS,
                    )

                    result = await crawler.arun(day_url, config=run_cfg)
                    if not result.success:
                        print(f"      ⚠️  {result.error_message}")
                        continue

                    if os.environ.get('DEBUG_SCRAPER'):
                        with open(f'debug_carrefour_{day}.html', 'w', encoding='utf-8') as f:
                            f.write(result.html)

                    promos = self._extract_vtex_cards(result.html)
                    print(f"      {len(promos)} cards")

                    for p in promos:
                        entity = (p.get('bank') or p.get('wallet') or p.get('card_type') or '').lower()
                        key = (
                            entity,
                            p.get('discount', ''),
                            (p.get('valid_days') or '').lower(),
                            (p.get('store_types') or '').lower(),
                        )
                        if key not in seen:
                            seen.add(key)
                            all_promotions.append(p)
                            label = p.get('bank') or p.get('wallet') or '?'
                            print(f"      + {label:30s} | {p.get('discount') or '—':6s} | {p.get('valid_days') or '—'}")

        except Exception as e:
            print(f"\n   ❌ Error: {e}")
            import traceback
            traceback.print_exc()

        print(f"\n✅ {self.name}: {len(all_promotions)} promociones encontradas")
        return all_promotions

    async def _scrape_vtex_graphql(self) -> List[Dict]:
        """Obtiene y valida los documentos públicos que usa la UI de Carrefour."""
        try:
            import requests
        except ImportError:
            print("   ⚠️ requests no está instalado; se usará el fallback HTML")
            return []

        def request_documents() -> Any:
            response = requests.post(
                _VTEX_GRAPHQL_URL,
                json={
                    'operationName': 'GetPromotions',
                    'variables': {'account': 'carrefourar'},
                    'query': _VTEX_GRAPHQL_QUERY,
                },
                headers=_VTEX_HEADERS,
                timeout=(8, 30),
                allow_redirects=False,
            )
            response.raise_for_status()
            return response.json()

        try:
            payload = await asyncio.to_thread(request_documents)
        except Exception:
            # No registrar la respuesta remota: podría contener información operativa.
            print("   ⚠️ No se pudo consultar la fuente VTEX; se usará el fallback HTML")
            return []

        documents = payload.get('data', {}).get('documents', []) if isinstance(payload, dict) else []
        if not isinstance(documents, list):
            print("   ⚠️ La fuente VTEX devolvió un formato inválido")
            return []

        promotions: List[Dict] = []
        for document in documents:
            promo = self._parse_vtex_document(document)
            if promo:
                promotions.append(promo)

        return self._deduplicate_graphql_promotions(promotions)

    def _parse_vtex_document(self, document: Any) -> Optional[Dict]:
        """Convierte un documento VTEX en el contrato interno de promociones."""
        if not isinstance(document, dict) or not isinstance(document.get('fields'), list):
            return None

        fields: Dict[str, str] = {}
        for item in document['fields']:
            if not isinstance(item, dict):
                continue
            key = item.get('key')
            if not isinstance(key, str):
                continue
            value = item.get('value')
            fields[key] = '' if value is None or str(value).lower() == 'null' else str(value).strip()

        title = self.clean_text(fields.get('title', ''))
        terms_raw = self.clean_text(fields.get('legal', ''))
        if not title or not terms_raw:
            return None

        valid_from, valid_until = self._extract_validity_dates(terms_raw)
        if valid_until and valid_until < date.today().isoformat():
            return None

        identity_text = ' '.join((title, fields.get('sub_title', ''), fields.get('img_card', '')))
        bank, wallet, card_type, payment_method = self._identify_payment_source(identity_text)
        discount = self._format_discount(fields)
        if not discount:
            discount = self.extract_discount(title)
        if not discount:
            return None

        valid_days = [
            label for key, label in _DAY_LABELS.items()
            if fields.get(key, '').lower() == 'true'
        ]
        store_types = [
            label for key, label in _STORE_LABELS.items()
            if fields.get(key, '').lower() == 'true'
        ]

        exclusions: List[str] = []
        exclusion_match = re.search(r'NO\s+INCLUYE\s+([^.]{10,800})', terms_raw, re.I)
        if exclusion_match:
            exclusions.append(exclusion_match.group(1).strip().rstrip('.'))

        return {
            'title': title,
            'discount': discount,
            'bank': bank,
            'wallet': wallet,
            'card_type': card_type,
            'payment_method': payment_method,
            'store_types': ', '.join(store_types) or None,
            'valid_days': ', '.join(valid_days) or None,
            'url': self.url,
            'image_url': None,
            # La columna es TEXT: conservar el legal completo permite responder exclusiones reales.
            'terms_raw': terms_raw,
            'tope': self._extract_tope(terms_raw),
            'min_purchase': self._extract_min_purchase(terms_raw),
            'exclusions': exclusions,
            'requirements': [],
            'valid_from': valid_from,
            'valid_until': valid_until,
        }

    @staticmethod
    def _format_discount(fields: Dict[str, str]) -> str:
        percentage = fields.get('discount_percentage', '').strip()
        if percentage and percentage.replace('.', '', 1).isdigit():
            if '.' in percentage:
                percentage = percentage.rstrip('0').rstrip('.')
            return f'{percentage}%'

        installments = fields.get('discounts_amount_installments', '').strip()
        installments_text = fields.get('discounts_text_installments', '').strip()
        if installments and installments.isdigit() and installments_text:
            return f'{installments} cuotas {installments_text}'
        return ''

    def _identify_payment_source(self, identity_text: str) -> tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
        """Identifica el medio solo desde el encabezado, nunca desde exclusiones del legal."""
        normalized = identity_text.lower()
        bank = self.extract_bank(identity_text)
        wallet = self.extract_wallet(identity_text)
        card_type: Optional[str] = None
        payment_method: Optional[str] = None

        if 'cuenta dni' in normalized:
            bank = 'Banco Provincia'
            wallet = 'Cuenta DNI'
        elif 'cuenta digital' in normalized:
            bank = 'Carrefour Banco'
            card_type = 'Cuenta Digital Carrefour'
        elif 'carrefour banco' in normalized:
            bank = 'Carrefour Banco'
            if 'crédito' in normalized or 'credito' in normalized:
                card_type = 'Tarjeta de crédito Carrefour Banco'
            elif 'prepaga' in normalized:
                card_type = 'Tarjeta prepaga Carrefour Banco'
        elif 'anses' in normalized:
            bank = 'ANSES'
        elif 'todos los medios' in normalized or 'cualquier medio de pago' in normalized:
            payment_method = 'Todos los medios de pago'

        return bank, wallet, card_type, payment_method

    @staticmethod
    def _extract_validity_dates(terms_raw: str) -> tuple[Optional[str], Optional[str]]:
        # Reutiliza el parser compartido para mantener el mismo formato ISO de la base.
        from terms_parser import TermsParser
        valid_from, valid_until = TermsParser().extract_validity_dates(terms_raw.upper())
        if valid_until:
            return valid_from, valid_until

        # Carrefour también publica "TODOS LOS JUEVES DE SEPTIEMBRE 2026".
        # El parser histórico no reconoce esa variante sin "DE" antes del año.
        month_match = re.search(
            r'\bDE\s+(ENERO|FEBRERO|MARZO|ABRIL|MAYO|JUNIO|JULIO|AGOSTO|'
            r'SEPTIEMBRE|OCTUBRE|NOVIEMBRE|DICIEMBRE)(?:\s+DE)?\s+(\d{4})\b',
            terms_raw.upper(),
        )
        if not month_match:
            return valid_from, valid_until

        month_names = {
            'ENERO': 1, 'FEBRERO': 2, 'MARZO': 3, 'ABRIL': 4,
            'MAYO': 5, 'JUNIO': 6, 'JULIO': 7, 'AGOSTO': 8,
            'SEPTIEMBRE': 9, 'OCTUBRE': 10, 'NOVIEMBRE': 11, 'DICIEMBRE': 12,
        }
        year = int(month_match.group(2))
        month = month_names[month_match.group(1)]
        if month == 12:
            last_day = 31
        else:
            last_day = (date(year, month + 1, 1) - date.resolution).day
        return f'{year}-{month:02d}-01', f'{year}-{month:02d}-{last_day:02d}'

    @staticmethod
    def _deduplicate_graphql_promotions(promotions: List[Dict]) -> List[Dict]:
        seen: Dict[tuple, Dict] = {}
        for promo in promotions:
            entity = (
                promo.get('bank') or promo.get('wallet') or promo.get('card_type')
                or promo.get('payment_method') or ''
            ).lower()
            key = (
                entity,
                (promo.get('discount') or '').lower(),
                (promo.get('valid_days') or '').lower(),
                (promo.get('store_types') or '').lower(),
            )
            existing = seen.get(key)
            if existing is None or len(promo.get('terms_raw', '')) > len(existing.get('terms_raw', '')):
                seen[key] = promo
        return list(seen.values())

    # ──────────────────────────────────────────────────────────
    # Parsing VTEX
    # ──────────────────────────────────────────────────────────

    def _extract_vtex_cards(self, html: str) -> List[Dict]:
        if BeautifulSoup is None:
            return []
        soup = BeautifulSoup(html, 'html.parser')
        card_boxes = soup.find_all('div', class_=re.compile(r'valtech-carrefourar-bank-promotions.*cardBox'))
        print(f"      🔍 {len(card_boxes)} cardBox en DOM")

        promotions = []
        seen_inner: set = set()
        for card in card_boxes:
            try:
                promo = self._parse_vtex_card(card)
                if promo and promo.get('discount'):
                    entity = (promo.get('bank') or promo.get('wallet') or promo.get('card_type') or '').lower()
                    key = (entity, promo.get('discount', ''), (promo.get('valid_days') or '').lower(), (promo.get('store_types') or '').lower())
                    if key not in seen_inner:
                        seen_inner.add(key)
                        promotions.append(promo)
            except Exception:
                pass
        return promotions

    def _parse_vtex_card(self, card) -> Optional[Dict]:
        # Días válidos
        date_elem = card.find('span', class_=re.compile(r'dateText'))
        valid_days = date_elem.get_text(strip=True) if date_elem else None

        # Tipos de tienda
        store_types: List[str] = []
        for icon in card.find_all('div', class_=re.compile(r'logoIcon')):
            cls = ' '.join(icon.get('class', []))
            if 'logoMain' in cls:      store_types.append('Hipermercado')
            elif 'logoMarket' in cls:  store_types.append('Market')
            elif 'logoExpress' in cls: store_types.append('Express')
            elif 'logoMaxi' in cls:    store_types.append('Maxi')
            elif 'logoOnline' in cls:  store_types.append('Online')

        # Descuento
        pct = card.find('span', class_=re.compile(r'ColLeftPercentage'))
        sym = card.find('span', class_=re.compile(r'ColLeftPercentageSymbol'))
        discount = ''
        if pct and sym:
            discount = f"{pct.get_text(strip=True)}{sym.get_text(strip=True)}"
        elif pct:
            discount = pct.get_text(strip=True)

        # Todas las imágenes para identificar banco/billetera (multi-logo support)
        img_elems = card.find_all('img', class_=re.compile(r'valtech-carrefourar-bank-promotions.*Image'))
        image_url = ''
        if img_elems:
            src = img_elems[0].get('src', '') or img_elems[0].get('data-src', '') or ''
            image_url = src if src.startswith('http') else f"https://www.carrefour.com.ar{src}"

        # Título
        title_parts: List[str] = []
        t = card.find('span', class_=re.compile(r'ColRightTittle'))
        d = card.find('span', class_=re.compile(r'ColRightText'))
        if t: title_parts.append(t.get_text(strip=True))
        if d:
            dt = d.get_text(strip=True)
            if dt: title_parts.append(dt)
        title = ' '.join(title_parts) or None

        # Texto completo del card para extracciones de texto
        for tag in card.find_all(['style', 'svg', 'script']):
            tag.decompose()
        all_text = card.get_text(' ', strip=True)

        # Términos y condiciones
        footer = card.find('div', class_=re.compile(r'cardFooter'))
        terms_raw = ''
        if footer:
            paras = [p.get_text(' ', strip=True) for p in footer.find_all('p') if len(p.get_text(strip=True)) > 30]
            terms_raw = ' '.join(paras)
        if not terms_raw:
            upper = re.findall(r'[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s\d.,;:/()$%-]{100,}', all_text)
            if upper:
                terms_raw = max(upper, key=len)

        # Banco / billetera desde imágenes (itera todas para multi-logo)
        bank: Optional[str] = None
        wallet: Optional[str] = None
        card_type: Optional[str] = None

        all_srcs = []
        for img in img_elems:
            src = img.get('src', '') or img.get('data-src', '') or ''
            if not src.startswith('http'):
                src = f"https://www.carrefour.com.ar{src}"
            all_srcs.append(src.lower())

        for img_lower in all_srcs:
            if 'cuenta_dni' in img_lower or 'cuentadni' in img_lower:
                if not bank: bank = 'Banco Provincia'
                if not wallet: wallet = 'Cuenta DNI'
            elif 'mercadopago' in img_lower or 'mercado_pago' in img_lower or 'mercado-pago' in img_lower:
                if not wallet: wallet = 'Mercado Pago'
            elif 'modo' in img_lower:
                if not wallet: wallet = 'MODO'
            elif 'carrefour' in img_lower and 'credito' in img_lower:
                if not bank: bank = 'Carrefour Banco'
                if not card_type: card_type = 'Tarjeta Mi Carrefour Crédito'
            elif 'carrefour' in img_lower and 'prepaga' in img_lower:
                if not bank: bank = 'Carrefour Banco'
                if not card_type: card_type = 'Tarjeta Mi Carrefour Prepaga'
            elif 'carrefour' in img_lower and 'digital' in img_lower:
                if not bank: bank = 'Carrefour Banco'
                if not card_type: card_type = 'Cuenta Digital Carrefour'
            elif 'bna' in img_lower or 'banco-nacion' in img_lower or 'banconacion' in img_lower or 'bnaplus' in img_lower or 'bna+' in img_lower:
                if not bank: bank = 'Banco Nación'
            elif 'anses' in img_lower:
                if not bank: bank = 'ANSES'
            elif 'clublanacion' in img_lower or 'club-la-nacion' in img_lower or 'club_la_nacion' in img_lower:
                if not bank: bank = 'Club La Nación'
            elif 'naranja' in img_lower:
                if not card_type: card_type = 'Naranja'
            elif 'galicia' in img_lower:
                if not bank: bank = 'Banco Galicia'
            elif 'santander' in img_lower:
                if not bank: bank = 'Santander'
            elif 'patagonia' in img_lower:
                if not bank: bank = 'Banco Patagonia'
            elif 'provincia' in img_lower:
                if not bank: bank = 'Banco Provincia'
            elif 'supervielle' in img_lower:
                if not bank: bank = 'Supervielle'
            elif 'macro' in img_lower:
                if not bank: bank = 'Macro'
            elif 'hsbc' in img_lower:
                if not bank: bank = 'HSBC'
            elif 'icbc' in img_lower:
                if not bank: bank = 'ICBC'
            elif 'ciudad' in img_lower:
                if not bank: bank = 'Banco Ciudad'
            elif 'carrefour' in img_lower:
                if not bank: bank = 'Carrefour Banco'

        # Fallback a texto si no se detectó nada
        if not bank and not wallet and not card_type:
            bank = self.extract_bank(all_text)
            wallet = self.extract_wallet(all_text)

        if not discount:
            discount = self.extract_discount(all_text)

        if not title:
            entity = bank or wallet or card_type
            title = f"{discount} con {entity}" if (discount and entity) else entity
        if not title:
            return None

        # Tope
        tope = self._extract_tope(all_text)

        # Compra mínima
        min_purchase = self._extract_min_purchase(all_text)

        # Exclusiones desde "NO INCLUYE ..."
        exclusions: List[str] = []
        excl_m = re.search(r'NO\s+INCLUYE\s+([^.]{10,300})', all_text, re.I)
        if excl_m:
            exclusions = [excl_m.group(1).strip().rstrip('.')]

        return {
            'title':          self.clean_text(title),
            'discount':       discount,
            'bank':           bank,
            'wallet':         wallet,
            'card_type':      card_type,
            'payment_method': None,
            'store_types':    ', '.join(store_types) if store_types else None,
            'valid_days':     valid_days,
            'url':            self.url,
            'image_url':      image_url,
            'terms_raw':      self.clean_text(terms_raw)[:1500],
            'tope':           tope,
            'min_purchase':   min_purchase,
            'exclusions':     exclusions,
            'requirements':   [],
            'valid_from':     None,
            'valid_until':    None,
        }

    def _extract_tope(self, text: str) -> Optional[str]:
        if re.search(r'sin\s+tope', text, re.I):
            return 'Sin tope'
        patterns = [
            r'tope\b[^.$\n]{0,40}\$\s*(\d[\d.,]*)',
            r'tope\s+m[aá]ximo[^.$\n]{0,30}\$\s*(\d[\d.,]*)',
            r'm[aá]ximo\s+de\s+descuento[^.$\n]{0,20}\$\s*(\d[\d.,]*)',
        ]
        for pat in patterns:
            m = re.search(pat, text, re.I)
            if m:
                amount = m.group(1).replace('.', '').replace(',', '.')
                try:
                    n = float(amount)
                    if n > 0:
                        return f"${n:,.0f}".replace(',', '.')
                except ValueError:
                    pass
        return None

    def _extract_min_purchase(self, text: str) -> Optional[str]:
        m = re.search(r'm[ií]nimo\s+de\s+compra\s+\$\s*(\d[\d.,]*)', text, re.I)
        if m:
            amount = m.group(1).replace('.', '').replace(',', '.')
            try:
                n = float(amount)
                if n > 0:
                    return f"${n:,.0f}".replace(',', '.')
            except ValueError:
                pass
        return None
