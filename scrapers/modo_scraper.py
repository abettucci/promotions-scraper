"""
MODO — Promos en estaciones de servicio (aggregator de combustible)
URL pública: https://www.modo.com.ar/promos

El hub de promos de MODO es una SPA que consume una API JSON pública (sin auth):
  GET /promos/api/rewards/v2/filter?category_ids=5&fcalcstatus=RUNNING&...
      -> cards vigentes de la categoría 5 (Estaciones de Servicios), paginadas.
  GET /promos/api/rewards/v2/benefit/{slug}
      -> detalle con términos y condiciones.

Cada card trae la marca (card.validity_place), el banco (card.participating_bank),
el reintegro, el calendario y el tope. Los bancos suelen publicar la misma promo
partida por segmento (Comafi Ahorro/Premium/Único, Macro Selecta Nivel 1..4) con
distinto tope: las agrupamos en una sola promo con el tope por segmento.
Las promos de Banco Macro (Selecta) salen de acá: la página de Macro está deshabilitada.
"""
import asyncio
import html as html_lib
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional


_BASE = 'https://www.modo.com.ar/promos'
_FILTER_URL = f'{_BASE}/api/rewards/v2/filter'
_DETAIL_URL = f'{_BASE}/api/rewards/v2/benefit/{{slug}}'
_CATEGORY_FUEL = '5'  # Estaciones de Servicios

_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json',
    'Accept-Language': 'es-AR,es;q=0.9',
}

ALL_STATIONS = ['YPF', 'Shell', 'Axion', 'Puma Energy']

# Marcas reconocibles en validity_place / descripciones (orden = orden de salida)
_BRAND_PATTERNS = [
    ('YPF', r'\bypf\b'),
    ('Shell', r'\bshell\b'),
    ('Axion', r'\baxion\b'),
    ('Puma Energy', r'\bpuma\b'),
    ('Gulf', r'\bgulf\b'),
    ('WICO', r'\bwico\b'),
    ('Voy', r'\bvoy\b'),
]
# validity_place que significa "cualquier estación"
_GENERIC_PLACE = re.compile(r'combustible|estaci[oó]n|estaciones|todo el pa[ií]s', re.I)

_DAYS = [
    ('monday', 'Lunes'), ('tuesday', 'Martes'), ('wednesday', 'Miércoles'),
    ('thursday', 'Jueves'), ('friday', 'Viernes'), ('saturday', 'Sábado'),
    ('sunday', 'Domingo'),
]

_ISSUERS = {
    'visa': 'Visa', 'master': 'Mastercard', 'american_express': 'American Express',
    'cabal': 'Cabal', 'maestro': 'Maestro', 'naranja': 'Naranja',
    'dinners_club': 'Diners Club', 'patagonia_365': 'Patagonia 365',
    'tarjeta_sol': 'Tarjeta Sol', 'confiable': 'Confiable',
}

_PERIODS = {'week': 'semanal', 'month': 'mensual', 'day': 'diario', 'promo': 'total'}

# (patrón sobre participating_bank normalizado, banco canónico, nombre para el título)
_BANKS = [
    (r'macro selecta', 'Banco Macro', 'Macro Selecta'),
    (r'macro', 'Banco Macro', 'Banco Macro'),
    (r'comafi', 'Banco Comafi', 'Banco Comafi'),
    (r'icbc', 'ICBC', 'ICBC'),
    (r'hipotecario', 'Banco Hipotecario', 'Banco Hipotecario'),
    (r'supervielle', 'Banco Supervielle', 'Banco Supervielle'),
    (r'\bbna\b|naci[oó]n', 'Banco Nación', 'Banco Nación'),
    (r'columbia', 'Banco Columbia', 'Banco Columbia'),
    (r'credicoop', 'Banco Credicoop', 'Banco Credicoop'),
    (r'ciudad', 'Banco Ciudad', 'Banco Ciudad / Buepp'),
    (r'bica', 'Banco BICA', 'Banco BICA'),
    (r'galicia', 'Banco Galicia', 'Banco Galicia'),
    (r'santander', 'Santander', 'Santander'),
    (r'bbva|franc[eé]s', 'BBVA', 'BBVA'),
    (r'patagonia', 'Banco Patagonia', 'Banco Patagonia'),
    (r'provincia', 'Banco Provincia', 'Banco Provincia'),
    (r'bancor|c[oó]rdoba', 'Bancor', 'Bancor'),
    (r'hsbc', 'HSBC', 'HSBC'),
    (r'brubank', 'Brubank', 'Brubank'),
]
# "Bancos adheridos" / "MODO": promo de MODO para cualquier banco
_NO_BANK = re.compile(r'adherid|^modo$|^$', re.I)

# Beneficios no públicos: corporativos, clientes seleccionados/notificados,
# empleados de empresas puntuales o exclusivos de clientes de seguros de auto.
_PRIVATE = re.compile(
    r'beneficio corporativo|cliente[s]? seleccionad|seleccionad[oa]s previamente'
    r'|notificad[oa] de la presente|exclusivo empleados|son empleados de'
    r'|seguros?[- ]de[- ]auto|seguros?[- ]auto|clientes seguros',
    re.I,
)


def _strip_accents(s: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')


def _html_to_text(raw: Optional[str]) -> str:
    if not raw:
        return ''
    text = re.sub(r'<br\s*/?>|</p>', '\n', raw, flags=re.I)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = html_lib.unescape(text).replace('\xa0', ' ')
    text = re.sub(r'[ \t]+', ' ', text)
    return re.sub(r'\s*\n\s*', '\n', text).strip()


def _money(n) -> str:
    return '$' + f'{int(round(float(n))):,}'.replace(',', '.')


class ModoScraper:
    def __init__(self):
        self.name = 'MODO'
        self.url = _BASE

    async def scrape(self, page=None) -> List[Dict]:
        print(f"🔍 Scraping {self.name} (API rewards, categoría combustible)...")
        loop = asyncio.get_event_loop()
        try:
            cards = await loop.run_in_executor(None, self._fetch_cards)
        except Exception as e:
            print(f"   ❌ Error consultando la API de MODO: {e}")
            return []
        print(f"   🔍 {len(cards)} cards vigentes en la categoría")

        # Detalle (T&C) en paralelo; si falla una, seguimos con los datos de la card
        slugs = [self._slug(c) for c in cards]
        with ThreadPoolExecutor(max_workers=6) as pool:
            details = await asyncio.gather(*[
                loop.run_in_executor(pool, self._fetch_detail, s) for s in slugs
            ])
        promotions = self.parse_cards(cards, dict(zip(slugs, details)))
        for p in promotions:
            print(f"   + {p['title'][:90]} | {p.get('tope')}")
        print(f"✅ {self.name}: {len(promotions)} promociones")
        return promotions

    # ------------------------------------------------------------------ HTTP
    def _fetch_cards(self) -> List[Dict]:
        import requests
        cards: List[Dict] = []
        page = 1
        while True:
            params = {
                'category_ids': _CATEGORY_FUEL, 'fcalcstatus': 'RUNNING', 'limit': 100,
                'page': page, 'source': 'web_modo', 'origin': 'WEB_MODO',
            }
            resp = requests.get(_FILTER_URL, params=params, headers=_HEADERS, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            cards.extend(data.get('cards') or [])
            total_pages = (data.get('pagination') or {}).get('total_pages') or 1
            if page >= total_pages or page >= 20:
                return cards
            page += 1

    def _fetch_detail(self, slug: str) -> Dict:
        import requests
        if not slug:
            return {}
        try:
            resp = requests.get(_DETAIL_URL.format(slug=slug), headers=_HEADERS, timeout=20)
            resp.raise_for_status()
            return resp.json() or {}
        except Exception as e:
            print(f"   ⚠️ Sin detalle para {slug}: {e}")
            return {}

    # --------------------------------------------------------------- parsing
    @staticmethod
    def _slug(card: Dict) -> str:
        return (((card.get('benefit') or {}).get('publication') or {}).get('slug') or '').strip()

    def parse_cards(self, cards: List[Dict], details: Optional[Dict[str, Dict]] = None) -> List[Dict]:
        """Convierte cards (+detalle por slug) en promos agrupadas por segmento."""
        details = details or {}
        entries = []
        for card in cards:
            entry = self._parse_entry(card, details.get(self._slug(card)) or {})
            if entry:
                entries.append(entry)

        # Agrupar segmentos de la misma promo (mismo banco, marca, beneficio, días y fin)
        groups: Dict[tuple, List[Dict]] = {}
        for e in entries:
            key = (tuple(e['brands']), e['bank_key'], e['discount'], e['valid_days'], e['valid_until'])
            groups.setdefault(key, []).append(e)
        return [self._build_promo(g) for g in groups.values()]

    def _parse_entry(self, card: Dict, detail: Dict) -> Optional[Dict]:
        benefit = card.get('benefit') or {}
        offer = card.get('offer') or {}
        info = card.get('card') or {}
        pub = benefit.get('publication') or {}
        slug = self._slug(card)
        if (card.get('calculated_status') or 'RUNNING') != 'RUNNING':
            return None
        if _CATEGORY_FUEL not in [str(c) for c in (offer.get('categories') or [_CATEGORY_FUEL])]:
            return None

        terms = _html_to_text(detail.get('terms_and_conditions'))
        description = detail.get('publication_description') or pub.get('description') or ''
        short = detail.get('short_description') or pub.get('short_description') or ''
        haystack = ' '.join([slug, benefit.get('name') or '', info.get('benefit') or '',
                             short, description, terms])
        if (benefit.get('scope') or '').lower() == 'beneficios' or _PRIVATE.search(haystack):
            print(f"   ⏭️ No pública (corporativa/segmentada): {slug}")
            return None

        brands = self._brands(info.get('validity_place') or '',
                              [(detail.get('details') or {}).get('applicability_description') or '',
                               description])
        if not brands:
            print(f"   ⏭️ Sin marca identificable: {slug} ({info.get('validity_place')})")
            return None

        cashback = (offer.get('outcomes') or {}).get('cashback') or {}
        amount = cashback.get('amount')
        if not amount:
            return None
        amount_txt = f"{amount:g}" if isinstance(amount, (int, float)) else str(amount)
        if (cashback.get('amount_type') or 'percent') == 'percent':
            discount = f"{amount_txt}% reintegro"
        else:
            discount = f"{_money(amount)} de reintegro"

        conditions = benefit.get('conditions') or detail.get('conditions') or {}
        schedule = conditions.get('schedule') or {}
        dow = [d.lower() for d in (schedule.get('days_of_week') or [])]
        days = [es for en, es in _DAYS if en in dow]
        valid_days = 'Todos los días' if len(days) == 7 or not days else ', '.join(days)

        cap = ((offer.get('limits') or {}).get('period_cap') or {})
        cap_amount = cap.get('amount_by_period')
        period = _PERIODS.get((cap.get('reset_by') or '').lower(), '')
        min_amount = ((offer.get('requirements') or {}).get('amount_range') or {}).get('min')

        methods = (conditions.get('payment_methods') or {}).get('methods') or []
        types = {m.get('type') for m in methods}
        card_type = ', '.join(t for t, k in (('Crédito', 'credit_card'), ('Débito', 'debit_card')) if k in types) or None
        issuers = []
        for m in methods:
            name = _ISSUERS.get((m.get('issuer') or '').lower())
            if name and name not in issuers:
                issuers.append(name)

        flows = ((conditions.get('payment_flow') or {}).get('flows') or ['instore'])
        stores = ', '.join(s for s, k in (('Online', 'online'), ('Tiendas', 'instore')) if k in flows) or 'Tiendas'

        bank, bank_title = self._bank(info.get('participating_bank') or '')
        return {
            'slug': slug,
            'brands': brands,
            'bank': bank,
            'bank_title': bank_title,
            'bank_key': bank or bank_title,
            'discount': discount,
            'valid_days': valid_days,
            'valid_from': schedule.get('start_date'),
            'valid_until': schedule.get('stop_date'),
            'cap_amount': cap_amount,
            'period': period,
            'min_purchase': _money(min_amount) if min_amount else None,
            'card_type': card_type,
            'issuers': issuers,
            'store_types': stores,
            'extra': bool(re.search(r'\b(adicional|extra)\b', f"{benefit.get('name') or ''} {info.get('benefit') or ''}", re.I)),
            'segment': self._segment(slug, benefit.get('name') or '', f"{short} {description}", terms, bank),
            'terms': terms,
            'description': description.strip(),
            'image_url': info.get('image'),
        }

    @staticmethod
    def _brands(place: str, extra_texts: List[str]) -> List[str]:
        def find(text: str) -> List[str]:
            return [b for b, pat in _BRAND_PATTERNS if re.search(pat, text, re.I)]

        brands = find(place)
        if brands:
            return brands
        if not _GENERIC_PLACE.search(place):
            return []
        # "Combustible": a veces la descripción acota las marcas (Ciudad: YPF, Shell y Axion)
        for text in extra_texts:
            brands = find(text or '')
            if brands:
                return brands
        return list(ALL_STATIONS)

    @staticmethod
    def _bank(raw: str) -> tuple:
        name = re.sub(r'\s+', ' ', raw).strip()
        norm = _strip_accents(name).lower()
        if _NO_BANK.search(norm):
            return None, 'MODO'
        for pat, bank, title in _BANKS:
            if re.search(pat, norm):
                return bank, title
        return name, name

    @staticmethod
    def _segment(slug: str, name: str, short: str, terms: str, bank: Optional[str]) -> Optional[str]:
        """Segmento de clientes al que apunta la card (para títulos y topes)."""
        m = re.search(r'nivel\s*(\d)', f"{name} {terms}", re.I)
        if m:
            return f"Nivel {m.group(1)}"
        if bank == 'Banco Macro':
            m = re.search(r'[a-z]+(\d)-macroselecta', slug)
            if m:
                return f"Nivel {m.group(1)}"
        m = re.search(r'servicios? de cuenta ([^.]{3,60})\.', terms, re.I)
        if m:
            seg = m.group(1).strip()
            seg = re.sub(r'\bUNICO\b', 'Único', seg, flags=re.I)
            return seg
        low = f"{slug} {short} {name}".lower()
        if 'asalariad' in low or 'payroll' in low or 'haberes' in low:
            return 'Plan Sueldo'
        if 'exclusive' in low:
            return 'Exclusive'
        if 'buho one' in _strip_accents(low):
            return 'Búho One'
        return None

    def _build_promo(self, group: List[Dict]) -> Dict:
        group = sorted(group, key=lambda e: (e['cap_amount'] or 0, e['segment'] or '', e['slug']))
        e0 = group[0]
        brands = e0['brands']
        if brands == ALL_STATIONS:
            place = 'estaciones de servicio'
        elif len(brands) == 1:
            place = brands[0]
        else:
            place = ', '.join(brands[:-1]) + ' y ' + brands[-1]
        pct = e0['discount'].replace(' reintegro', '').replace(' de', '')
        if e0.get('extra'):
            pct += ' extra'

        segments = [e['segment'] for e in group if e['segment']]
        if e0['bank_title'] == 'MODO':  # promo de MODO con bancos adheridos
            title = f"MODO {pct} en {place} - {e0['valid_days']}"
        else:
            title = f"{e0['bank_title']} {pct} en {place} vía MODO - {e0['valid_days']}"
        if len(group) == 1 and e0['segment']:
            title += f" ({e0['segment']})"

        # Tope: único, o por segmento cuando la promo viene partida
        tope = None
        caps = [(e['segment'], e['cap_amount'], e['period']) for e in group if e['cap_amount']]
        if caps:
            periods = {p for _, _, p in caps}
            if len({c for _, c, _ in caps}) == 1:
                tope = f"{_money(caps[0][1])} {caps[0][2]}".strip()
            elif len(periods) == 1:
                parts = []
                for seg, amount, _ in caps:
                    part = f"{seg}: {_money(amount)}" if seg else _money(amount)
                    if part not in parts:
                        parts.append(part)
                tope = ' / '.join(parts) + f" {caps[0][2]}".rstrip()
            else:
                tope = ' / '.join(f"{(seg + ': ') if seg else ''}{_money(a)} {p}".strip() for seg, a, p in caps)

        issuers = []
        for e in group:
            issuers += [i for i in e['issuers'] if i not in issuers]
        card_types = []
        for e in group:
            for t in (e['card_type'] or '').split(', '):
                if t and t not in card_types:
                    card_types.append(t)
        payment = 'QR MODO' + (f" con {', '.join(issuers)}" if issuers else '')

        if len(group) == 1:
            terms = e0['terms'] or e0['description']
        else:
            blocks, seen = [], set()
            for e in group:
                text = e['terms'] or e['description']
                if text and text not in seen:
                    seen.add(text)
                    blocks.append(f"[{e['segment']}] {text}" if e['segment'] else text)
            terms = '\n\n'.join(blocks)

        requirements = [f"Pagar con QR MODO o la app del banco ({e0['bank_title']})"]
        if segments:
            requirements.append('Segmentos: ' + ', '.join(dict.fromkeys(segments)))

        return {
            'title': title,
            'discount': e0['discount'],
            'bank': e0['bank'],
            'wallet': 'MODO',
            'card_type': ', '.join(card_types) or None,
            'payment_method': payment,
            'store_types': e0['store_types'],
            'valid_days': e0['valid_days'],
            'valid_from': min((e['valid_from'] for e in group if e['valid_from']), default=None),
            'valid_until': e0['valid_until'],
            'tope': tope,
            'min_purchase': e0['min_purchase'],
            'terms_raw': terms,
            'requirements': requirements,
            'source_id': 'modo:' + '+'.join(sorted(e['slug'] for e in group)),
            'url': f"{_BASE}/{e0['slug']}" if e0['slug'] else _BASE,
            'image_url': e0['image_url'],
            'merchant_brands': list(brands),
            'merchant_category': 'fuel',
        }
