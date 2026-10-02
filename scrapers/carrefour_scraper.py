"""
Carrefour scraper — Descuentos Bancarios

Consume la misma fuente que la UI de https://www.carrefour.com.ar/descuentos-bancarios:
la entidad "BP" de VTEX Master Data expuesta por la app
valtech.carrefourar-bank-promotions vía GraphQL.

Flujo:
  1. GET a la persisted query pública GetPromotions con el mismo filtro de vigencia
     que usa el sitio (active=true y active_from < ahora < active_to).
  2. Si falla, POST a _v/private/graphql con la query explícita y el mismo filtro.
  3. Cada documento se convierte en una promo (una por documento, sin dedup propio:
     el sitio publica variantes distintas por tienda/tramo que antes se colapsaban).

Sin navegador ni IA. Si ambas fuentes fallan se loguea y se devuelve [].
"""
import asyncio
import base64
import json
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from .base_scraper import BaseScraper


# Constantes deliberadas: no se construyen a partir de datos externos ni del usuario.
_SENDER = 'valtech.carrefourar-bank-promotions@0.x'
_PUBLIC_GRAPHQL_URL = 'https://www.carrefour.com.ar/_v/public/graphql/v1'
_PERSISTED_HASH = 'e3aa1d96402d80dbca5c2c9dbcb7ff859970db0ccfdb64e583fb8a9b1bbff49e'
_VTEX_GRAPHQL_URL = (
    'https://www.carrefour.com.ar/_v/private/graphql/v1?workspace=master&locale=es-AR'
)
_FIELDS = [
    'id', 'title', 'sub_title', 'discount_percentage',
    'discounts_amount_installments', 'discounts_text_installments',
    'discount_text_info', 'img_card', 'img_card_2', 'img_card_3', 'hyper', 'market',
    'ecommerce', 'express', 'maxi', 'legal', 'valid', 'validText', 'active',
    'active_from', 'active_to', 'monday', 'tuesday', 'wednesday', 'thursday',
    'friday', 'saturday', 'sunday', 'idBank', 'idCard',
]
_VTEX_GRAPHQL_QUERY = '''
query GetPromotions($account: String, $where: String) @context(sender: "%s") {
  documents(
    acronym: "BP",
    schema: "mdv1",
    fields: %s,
    where: $where,
    sort: "order ASC",
    account: $account,
    pageSize: 999
  ) @context(provider: "vtex.store-graphql") {
    fields { key value }
  }
}
''' % (_SENDER, json.dumps(_FIELDS))
_VTEX_HEADERS = {
    'content-type': 'application/json',
    'x-vtex-tenant': 'carrefourargentina',
}
_HTTP_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36'
    ),
    'Accept': 'application/json',
}
_AR_TZ = timezone(timedelta(hours=-3))

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
_MONTHS = {
    'ENERO': 1, 'FEBRERO': 2, 'MARZO': 3, 'ABRIL': 4, 'MAYO': 5, 'JUNIO': 6,
    'JULIO': 7, 'AGOSTO': 8, 'SEPTIEMBRE': 9, 'OCTUBRE': 10, 'NOVIEMBRE': 11, 'DICIEMBRE': 12,
}


def _norm(text: str) -> str:
    """minúsculas sin tildes ni separadores (para matchear nombres de imagen)."""
    text = (text or '').lower()
    for a, b in (('á', 'a'), ('é', 'e'), ('í', 'i'), ('ó', 'o'), ('ú', 'u'), ('ñ', 'n')):
        text = text.replace(a, b)
    return re.sub(r'[^a-z0-9]', '', text)


def _fmt_amount(raw: str) -> Optional[str]:
    digits = re.sub(r'[^\d]', '', raw.split(',')[0])
    if not digits or int(digits) <= 0:
        return None
    return f"${int(digits):,}".replace(',', '.')


class CarrefourScraper(BaseScraper):
    def __init__(self):
        super().__init__(
            name='Carrefour',
            url='https://www.carrefour.com.ar/descuentos-bancarios'
        )

    async def scrape(self, page=None) -> List[Dict]:
        """page aceptado para compatibilidad pero no se usa."""
        print(f"🔍 Scraping {self.name}...")
        promotions = await self._scrape_vtex_graphql()
        print(f"✅ {self.name}: {len(promotions)} promociones encontradas (VTEX API)")
        return promotions

    # ──────────────────────────────────────────────────────────
    # Fuente VTEX
    # ──────────────────────────────────────────────────────────

    @staticmethod
    def _where_clause(now: Optional[datetime] = None) -> str:
        # Mismo filtro que arma el front (timestamp UTC sin zona).
        now = now or datetime.now(timezone.utc)
        stamp = now.strftime('%Y-%m-%dT%H:%M:%S')
        return f'active=true AND ((active_from < {stamp}) AND (active_to > {stamp}))'

    async def _scrape_vtex_graphql(self) -> List[Dict]:
        """Obtiene y valida los documentos vigentes que usa la UI de Carrefour."""
        try:
            import requests
        except ImportError:
            print("   ⚠️ requests no está instalado")
            return []

        variables = {'where': self._where_clause(), 'account': 'carrefourar'}

        def request_public() -> Any:
            extensions = {
                'persistedQuery': {
                    'version': 1,
                    'sha256Hash': _PERSISTED_HASH,
                    'sender': _SENDER,
                    'provider': 'vtex.store-graphql@2.x',
                },
                'variables': base64.b64encode(json.dumps(variables).encode()).decode(),
            }
            response = requests.get(
                _PUBLIC_GRAPHQL_URL,
                params={
                    'workspace': 'master', 'maxAge': 'short', 'appsEtag': 'remove',
                    'domain': 'store', 'locale': 'es-AR', 'operationName': 'GetPromotions',
                    'variables': '{}', 'extensions': json.dumps(extensions),
                },
                headers=_HTTP_HEADERS,
                timeout=(8, 30),
                allow_redirects=False,
            )
            response.raise_for_status()
            return response.json()

        def request_private() -> Any:
            response = requests.post(
                _VTEX_GRAPHQL_URL,
                json={
                    'operationName': 'GetPromotions',
                    'variables': variables,
                    'query': _VTEX_GRAPHQL_QUERY,
                },
                headers=_VTEX_HEADERS,
                timeout=(8, 30),
                allow_redirects=False,
            )
            response.raise_for_status()
            return response.json()

        documents: Optional[List] = None
        for label, fetch in (('pública', request_public), ('privada', request_private)):
            try:
                payload = await asyncio.to_thread(fetch)
            except Exception:
                # No registrar la respuesta remota: podría contener información operativa.
                print(f"   ⚠️ No se pudo consultar la fuente VTEX {label}")
                continue
            docs = payload.get('data', {}).get('documents') if isinstance(payload, dict) else None
            if isinstance(docs, list) and docs:
                documents = docs
                break
            print(f"   ⚠️ La fuente VTEX {label} devolvió un formato inválido o vacío")

        if not documents:
            return []

        promotions: List[Dict] = []
        for document in documents:
            try:
                promo = self._parse_vtex_document(document)
            except Exception as e:  # un documento raro no tira abajo la corrida
                print(f"   ⚠️ Documento VTEX ignorado: {e}")
                continue
            if promo:
                promotions.append(promo)
        return self._ensure_unique_titles(promotions)

    # ──────────────────────────────────────────────────────────
    # Parsing de documentos
    # ──────────────────────────────────────────────────────────

    def _parse_vtex_document(self, document: Any) -> Optional[Dict]:
        """Convierte un documento VTEX en el contrato interno de promociones."""
        if not isinstance(document, dict) or not isinstance(document.get('fields'), list):
            return None

        fields: Dict[str, str] = {}
        for item in document['fields']:
            if not isinstance(item, dict) or not isinstance(item.get('key'), str):
                continue
            value = item.get('value')
            fields[item['key']] = '' if value is None or str(value).lower() == 'null' else str(value).strip()

        if fields.get('active', '').lower() == 'false':
            return None

        raw_title = self.clean_text(fields.get('title', ''))
        sub_title = self.clean_text(fields.get('sub_title', ''))
        terms_raw = self.clean_text(fields.get('legal', ''))
        if not raw_title or not terms_raw:
            return None

        valid_from, valid_until = self._dates_from_fields(fields)
        if not valid_until:
            legal_from, valid_until = self._extract_validity_dates(terms_raw)
            valid_from = valid_from or legal_from
        if valid_until and valid_until < self._today():
            return None

        discount = self._format_discount(fields, raw_title) or self.extract_discount(raw_title)
        if not discount:
            return None

        source = self._identify_payment_source(fields, raw_title, sub_title, terms_raw)

        day_list = [label for key, label in _DAY_LABELS.items() if fields.get(key, '').lower() == 'true']
        valid_days = 'Todos los días' if len(day_list) == 7 else (', '.join(day_list) or None)
        store_keys = [key for key in _STORE_LABELS if fields.get(key, '').lower() == 'true']
        store_types = ', '.join(_STORE_LABELS[k] for k in store_keys) or None

        # Tope / mínimo: el subtítulo es lo que muestra la card y es más preciso que el
        # legal (los legales de tienda de Patagonia listan tramos de otra promo).
        tope = self._extract_tope(f"{raw_title}. {sub_title}", terms_raw)
        min_purchase = self._extract_min_purchase(sub_title) or self._extract_min_purchase(terms_raw)

        exclusions: List[str] = []
        for text in (sub_title, terms_raw):
            m = re.search(r'(?:NO\s+INCLUYE|QUEDAN\s+EXCLUIDOS\s+DEL\s+DESCUENTO)\s+([^.]{10,800})', text, re.I)
            if m:
                exclusions.append(m.group(1).strip().rstrip('.'))
                break

        requirements = list(source['requirements'])
        tier = self._tier(f"{raw_title} {sub_title}")
        if tier and source['entity'] == 'Banco Patagonia':
            requirements.append(f"Clientes {tier}")

        qualifiers = [q for q in (tier, source.get('qualifier')) if q]
        if store_keys and len(store_keys) < len(_STORE_LABELS):
            qualifiers.append(store_types)
        title = f"{source['entity']} {discount}"
        if qualifiers:
            title += f" ({' · '.join(qualifiers)})"
        if valid_days:
            title += f" - {valid_days}"

        doc_id = fields.get('id', '')
        return {
            'title': title,
            'discount': discount,
            'bank': source['bank'],
            'wallet': source['wallet'],
            'card_type': source['card_type'],
            'payment_method': source['payment_method'],
            'store_types': store_types,
            'valid_days': valid_days,
            'url': self.url,
            'image_url': None,
            # La columna es TEXT: conservar el legal completo permite responder exclusiones reales.
            'terms_raw': terms_raw,
            'tope': tope,
            'acumulable': self._acumulable(f"{raw_title}. {sub_title}. {terms_raw}"),
            'min_purchase': min_purchase,
            'exclusions': exclusions,
            'requirements': requirements,
            'valid_from': valid_from,
            'valid_until': valid_until,
            'source_id': f"carrefour-{doc_id}" if doc_id else None,
        }

    @staticmethod
    def _today() -> str:
        return date.today().isoformat()

    @staticmethod
    def _dates_from_fields(fields: Dict[str, str]) -> Tuple[Optional[str], Optional[str]]:
        """active_from/active_to vienen en UTC con fin exclusivo (00:00 del día siguiente)."""
        valid_from = fields.get('active_from', '')[:10] or None
        valid_until = None
        raw_to = fields.get('active_to', '')
        if raw_to:
            try:
                dt = datetime.fromisoformat(raw_to.replace('Z', '+00:00'))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                valid_until = (dt.astimezone(_AR_TZ) - timedelta(seconds=1)).date().isoformat()
            except ValueError:
                valid_until = None
        if valid_from and not re.match(r'\d{4}-\d{2}-\d{2}$', valid_from):
            valid_from = None
        return valid_from, valid_until

    @staticmethod
    def _format_discount(fields: Dict[str, str], title: str = '') -> str:
        percentage = fields.get('discount_percentage', '').strip()
        if percentage and percentage.replace('.', '', 1).isdigit() and float(percentage) > 0:
            if '.' in percentage:
                percentage = percentage.rstrip('0').rstrip('.')
            return f'{percentage}%'

        installments = fields.get('discounts_amount_installments', '').strip()
        installments_text = fields.get('discounts_text_installments', '').strip() or 'sin interés'
        if installments.isdigit() and int(installments) > 0:
            prefix = 'Hasta ' if re.match(r'\s*hasta\b', title, re.I) else ''
            return f'{prefix}{installments} cuotas {installments_text.lower()}'
        return ''

    def _identify_payment_source(self, fields: Dict[str, str], title: str, sub_title: str,
                                 legal: str) -> Dict[str, Any]:
        """Identifica el medio desde título, subtítulo e imágenes (nunca desde exclusiones del legal)."""
        imgs = _norm(' '.join(fields.get(k, '') for k in ('img_card', 'img_card_2', 'img_card_3')))
        head = f"{title} {sub_title}".lower()
        legal_head = legal[:300].lower()
        src: Dict[str, Any] = {
            'entity': None, 'bank': None, 'wallet': None, 'card_type': None,
            'payment_method': None, 'qualifier': None, 'requirements': [],
        }

        if 'todos los medios' in head or 'cualquier medio de pago' in head:
            src.update(entity='Todos los medios de pago', payment_method='Todos los medios de pago')
        elif 'cuentadni' in imgs or 'cuenta dni' in head:
            src.update(entity='Cuenta DNI', bank='Banco Provincia', wallet='Cuenta DNI',
                       payment_method='Cuenta DNI')
        elif 'mercadopago' in imgs or 'mercado pago' in head:
            src.update(entity='Mercado Pago', wallet='Mercado Pago')
            if 'cuotas sin tarjeta' in head or 'cuotas sin tarjeta' in legal.lower():
                src.update(payment_method='Cuotas sin tarjeta (QR Mercado Pago)', qualifier='Cuotas sin tarjeta')
            elif 'tarjeta de crédito de mercado pago' in head or 'tarjeta de credito de mercado pago' in head:
                src.update(payment_method='Tarjeta de crédito Mercado Pago', card_type='Crédito',
                           qualifier='Tarjeta de crédito MP')
            elif 'dinero en cuenta' in head:
                src.update(payment_method='Dinero en cuenta Mercado Pago', qualifier='Dinero en cuenta')
            else:
                src.update(payment_method='QR Mercado Pago')
        elif 'modo' in imgs or 'modo' in head:
            bank = 'Banco Nación' if ('bna' in imgs or 'banco nación' in legal_head or 'bna' in legal_head) else None
            src.update(entity='MODO' + (' BNA' if bank else ''), bank=bank, wallet='MODO',
                       payment_method='MODO / BNA+' if bank else 'MODO')
            if 'jubilad' in head:
                src['requirements'].append('Jubilados y pensionados que cobren sus haberes en BNA')
                src['qualifier'] = 'Jubilados'
        elif 'patagonia' in imgs or 'patagonia' in head:
            card = 'Crédito, Débito' if re.search(r'd[eé]bit', head) else ('Crédito' if 'crédito' in head else None)
            src.update(entity='Banco Patagonia', bank='Banco Patagonia', card_type=card)
        elif 'naranja' in imgs or 'naranja' in head:
            src.update(entity='Naranja X', bank='Naranja X', card_type='Crédito',
                       payment_method='Tarjeta de crédito Naranja X')
        elif 'clublanacion' in imgs or 'club la nacion' in head or 'club la nación' in head:
            src.update(entity='Club La Nación', bank='Club La Nación', payment_method='Credencial Club La Nación')
        elif 'anses' in imgs or 'anses' in head:
            src.update(entity='Mi Carrefour ANSES/+60', payment_method='Todos los medios de pago')
            src['requirements'].append('Ser parte de Mi Carrefour y beneficiario de ANSES o mayor de 60 años')
        elif 'emplead' in head:
            src.update(entity='Empleados públicos', payment_method='Todos los medios de pago')
            src['requirements'].append('Empleadas/os públicos (presentar credencial/recibo)')
        else:
            credit = 'credito' in imgs or 'crédito' in head or 'credito' in head
            digital = 'cuentadigital' in imgs or 'cuenta digital' in head or 'cuenta digital' in legal_head
            if credit and ('cuenta digital' in head):
                src.update(entity='TC + Cuenta Digital Carrefour Banco', bank='Carrefour Banco',
                           card_type='Crédito',
                           payment_method='Tarjeta de crédito o Cuenta Digital Carrefour Banco')
            elif credit and ('carrefour' in imgs or 'carrefour banco' in head):
                src.update(entity='TC Carrefour Banco', bank='Carrefour Banco', card_type='Crédito',
                           payment_method='Tarjeta de crédito Carrefour Banco')
            elif digital:
                src.update(entity='Cuenta Digital Carrefour Banco', bank='Carrefour Banco',
                           payment_method='Cuenta Digital Carrefour Banco')
            else:
                bank = self.extract_bank(f"{title} {sub_title}")
                wallet = self.extract_wallet(f"{title} {sub_title}")
                if bank or wallet:
                    src.update(entity=bank or wallet, bank=bank, wallet=wallet)
                else:
                    src.update(entity='Todos los medios de pago', payment_method='Todos los medios de pago')

        if 'acumulable con todas' in head and not src['qualifier']:
            src['qualifier'] = 'Acumulable'
        return src

    @staticmethod
    def _acumulable(text: str) -> Optional[bool]:
        if re.search(r'no\s+acumulable', text, re.I):
            return False
        if re.search(r'acumulable', text, re.I):
            return True
        return None

    @staticmethod
    def _tier(text: str) -> Optional[str]:
        low = text.lower()
        if 'plan sueldo singular' in low:
            return 'Plan Sueldo Singular'
        if 'plan sueldo plus' in low:
            return 'Plan Sueldo Plus'
        if 'plan sueldo' in low:
            return 'Plan Sueldo'
        if 'singular' in low:
            return 'Singular'
        if 'clásica' in low or 'clasica' in low:
            return 'Clásica'
        if 'patagonia' in low and 'visa' in low and 'mastercard' not in low:
            return 'Visa'
        return None

    @staticmethod
    def _extract_validity_dates(terms_raw: str) -> Tuple[Optional[str], Optional[str]]:
        """Fallback cuando el documento no trae active_from/active_to."""
        upper = terms_raw.upper()
        # "HASTA EL 31/10/2026" o "HASTA EL 31/10/26"
        m = re.search(r'HASTA\s+EL\s+(\d{1,2})/(\d{1,2})/(\d{2,4})', upper)
        if m:
            day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
            year = year + 2000 if year < 100 else year
            try:
                return None, date(year, month, day).isoformat()
            except ValueError:
                pass

        from terms_parser import TermsParser
        valid_from, valid_until = TermsParser().extract_validity_dates(upper)
        if valid_until:
            return valid_from, valid_until

        # "TODOS LOS JUEVES DE SEPTIEMBRE 2026"
        month_match = re.search(
            r'\bDE\s+(ENERO|FEBRERO|MARZO|ABRIL|MAYO|JUNIO|JULIO|AGOSTO|'
            r'SEPTIEMBRE|OCTUBRE|NOVIEMBRE|DICIEMBRE)(?:\s+DE)?\s+(\d{4})\b',
            upper,
        )
        if not month_match:
            return valid_from, valid_until
        year = int(month_match.group(2))
        month = _MONTHS[month_match.group(1)]
        last_day = 31 if month == 12 else (date(year, month + 1, 1) - timedelta(days=1)).day
        return f'{year}-{month:02d}-01', f'{year}-{month:02d}-{last_day:02d}'

    @staticmethod
    def _ensure_unique_titles(promotions: List[Dict]) -> List[Dict]:
        """El title es parte de la clave UNIQUE en la DB: desambiguar si dos documentos chocan."""
        seen: Dict[str, int] = {}
        for promo in promotions:
            title = promo['title']
            if title in seen:
                seen[title] += 1
                suffix = (promo.get('source_id') or '')[-6:] or str(seen[title])
                promo['title'] = f"{title} [{suffix}]"
            else:
                seen[title] = 1
        return promotions

    # ──────────────────────────────────────────────────────────
    # Tope / compra mínima
    # ──────────────────────────────────────────────────────────

    @staticmethod
    def _tope_in(text: str) -> Tuple[Optional[str], Optional[str]]:
        """Devuelve (monto, período) del primer tope con monto en el texto."""
        for m in re.finditer(r'\btopes?\b', text, re.I):
            window = text[m.start():m.start() + 140]
            amount = re.search(r'\$\s*(\d{1,3}(?:[.,]\d{3})+|\d{3,})', window)
            if not amount:
                continue
            sentence = window[:amount.end() + 45].lower()
            if re.search(r'semana|semanal', sentence):
                period = 'semanal'
            elif re.search(r'\bmes\b|mensual', sentence):
                period = 'mensual'
            elif re.search(r'diari|por d[ií]a', sentence):
                period = 'diario'
            else:
                period = None
            return _fmt_amount(amount.group(1)), period
        return None, None

    def _extract_tope(self, card_text: str, legal: str = '') -> Optional[str]:
        if re.search(r'sin\s+tope', card_text, re.I):
            return 'Sin tope'
        amount, period = self._tope_in(card_text)
        if amount:
            if not period and legal:
                legal_amount, legal_period = self._tope_in(legal)
                if legal_amount == amount:
                    period = legal_period
            return f"{amount} {period}" if period else amount
        if legal:
            if re.search(r'sin\s+tope', legal, re.I):
                return 'Sin tope'
            amount, period = self._tope_in(legal)
            if amount:
                return f"{amount} {period}" if period else amount
        return None

    @staticmethod
    def _extract_min_purchase(text: str) -> Optional[str]:
        m = re.search(
            r'(?:m[ií]nimo\s+de\s+compra(?:\s+de)?|a\s+partir\s+de(?:\s+los)?|superiores?\s+a)\s*\$\s*(\d[\d.,]*)',
            text, re.I,
        )
        return _fmt_amount(m.group(1)) if m else None
