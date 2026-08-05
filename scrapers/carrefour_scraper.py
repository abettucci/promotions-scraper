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
from typing import List, Dict, Optional
from .base_scraper import BaseScraper
from bs4 import BeautifulSoup
import re
import os


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
        try:
            from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, BrowserConfig, CacheMode
        except ImportError:
            print("   ⚠️ crawl4ai no instalado — pip install crawl4ai && crawl4ai-setup")
            return []

        print(f"🔍 Scraping {self.name}...")
        print(f"   🌐 URL base: {self.url}")

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

    # ──────────────────────────────────────────────────────────
    # Parsing VTEX
    # ──────────────────────────────────────────────────────────

    def _extract_vtex_cards(self, html: str) -> List[Dict]:
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
