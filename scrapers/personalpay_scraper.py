"""
Personal Pay — Beneficios
URL: https://www.personal.com.ar/pay/beneficios

La web (Next.js) consume una API JSON propia que se llama directo (sin browser):
  GET /pay/api/benefits?sourceSection=web&category=Supermercados[&offset=N]
      → data.benefits[] (id, title, name, discounts, days, dueDate, levels...)
  GET /pay/api/benefits/{id}
      → detalle (description, legal, startDate, locations)

Es un AGGREGATOR: sólo se consultan las categorías Supermercados y
Combustible, y cada promo lleva merchant_brands / merchant_category.
"""
import re
import asyncio
from typing import List, Dict, Optional
from .base_scraper import BaseScraper


_API = 'https://www.personal.com.ar/pay/api/benefits'
_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'es-AR,es;q=0.9',
    'Referer': 'https://www.personal.com.ar/pay/beneficios',
}
_CATEGORIES = [('Supermercados', 'supermarket'), ('Combustible', 'fuel')]

# Patrón sobre "title name" (sin tildes, minúsculas) → (marca canónica, nombre para el título).
_MERCHANTS = [
    (r'\bdia\b',              'Supermercados Día',      'Supermercados Día'),
    (r'\bcoto\b',             'Coto Digital',           'Coto'),
    (r'chango\s*mas',         'Más Online (ChangoMás)', 'ChangoMás'),
    (r'carrefour',            'Carrefour',              'Carrefour'),
    (r'\bjumbo\b',            'Jumbo (Cencosud)',       'Jumbo'),
    (r'diarco barrio',        'Diarco',                 'Diarco Barrio'),
    (r'diarco mayorista',     'Diarco',                 'Diarco Mayorista'),
    (r'\bdiarco\b',           'Diarco',                 'Diarco'),
    (r'\bypf\b',              'YPF',                    'YPF'),
    (r'\bshell\b',            'Shell',                  'Shell'),
    (r'\baxion\b',            'Axion',                  'Axion'),
    (r'\bpuma\b',             'Puma Energy',            'Puma Energy'),
    (r'\bwico\b',             'WICO',                   'WICO'),  # mismo nombre que usa MODO
]

_DAYS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
_DAY_PREFIX = ['lu', 'ma', 'mi', 'ju', 'vi', 'sa', 'do']
_MONTHS = {
    'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6, 'julio': 7,
    'agosto': 8, 'septiembre': 9, 'setiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12,
}


def _fold(text: str) -> str:
    table = str.maketrans('áéíóúüÁÉÍÓÚÜ', 'aeiouuaeiouu')
    return (text or '').translate(table).lower()


def _clean(text: str) -> str:
    return re.sub(r'\s+', ' ', text or '').strip()


def days_label(days: List[str]) -> str:
    """['Do', 'Vi', 'Sá'] / ['Jueves'] / ['Todos los días'] → 'Viernes, Sábado, Domingo'."""
    idx = set()
    for d in days or []:
        f = _fold(d).strip()
        if 'todos' in f:
            return 'Todos los días'
        if f[:2] in _DAY_PREFIX:
            idx.add(_DAY_PREFIX.index(f[:2]))
    if not idx or len(idx) == 7:
        return 'Todos los días'
    return ', '.join(_DAYS[i] for i in sorted(idx))


def _money(value: str) -> str:
    digits = re.sub(r'[^\d]', '', re.split(r',\d{1,2}\b', str(value or ''))[0])
    return f"${int(digits):,}".replace(',', '.') if digits else ''


def parse_tope(text: str, subtitle: Optional[str] = None) -> Optional[str]:
    t = _fold(text)
    if 'sin tope' in t:
        return 'Sin tope'
    # Sin cruzar un punto: "El tope se aplica... semana. Mínima de compra $30.000".
    m = re.search(r'tope[^$.]{0,80}\$\s*([\d.,]+)', t)
    if not m and subtitle and '$' in subtitle:
        m = re.search(r'\$\s*([\d.,]+)', _fold(subtitle))
        tail = ''
    else:
        tail = t[m.end():m.end() + 80] if m else ''
    if not m:
        return 'Sin tope' if subtitle and 'sin tope' in _fold(subtitle) else None
    amount = _money(m.group(1))
    if 'semana' in tail:
        return f'{amount} semanal'
    if re.search(r'\bmes\b|mensual', tail):
        return f'{amount} mensual'
    if re.search(r'transaccion|\buso\b|compra', tail):
        return f'{amount} por compra'
    return amount


def parse_min_purchase(text: str, levels: List[Dict]) -> Optional[str]:
    for level in levels or []:
        if level.get('paymentMin'):
            return _money(level['paymentMin'])
    m = re.search(r'(?:minimo de compra|compra minima|minima de compra|compras mayores a)(?: de)?:?\s*\$\s*([\d.,]+)', _fold(text))
    return _money(m.group(1)) if m else None


def parse_legal_dates(legal: str):
    """Vigencia del legal: 'del 11/09/2025 hasta el 31/10/2026', 'del 01/05/26 al
    31/10/26', 'desde el 26 de Febrero de 2026 hasta el 01 de Octubre de 2026'."""
    t = _fold(legal)
    m = re.search(r'(?:desde|del)(?: el)? (\d{1,2})/(\d{1,2})/(\d{2,4}) (?:hasta|al)(?: el)? (\d{1,2})/(\d{1,2})/(\d{2,4})', t)
    if m:
        d1, m1, y1, d2, m2, y2 = m.groups()
        y1, y2 = (y if len(y) == 4 else f'20{y}' for y in (y1, y2))
        return f'{y1}-{int(m1):02d}-{int(d1):02d}', f'{y2}-{int(m2):02d}-{int(d2):02d}'
    mes = '(' + '|'.join(_MONTHS) + ')'
    m = re.search(rf'desde el (\d{{1,2}}) de {mes} de (\d{{4}}) hasta el (\d{{1,2}}) de {mes} de (\d{{4}})', t)
    if m:
        d1, m1, y1, d2, m2, y2 = m.groups()
        return f'{y1}-{_MONTHS[m1]:02d}-{int(d1):02d}', f'{y2}-{_MONTHS[m2]:02d}-{int(d2):02d}'
    return None, None


def _iso(value: Optional[str]) -> Optional[str]:
    """'2026-10-31T00:00:00.000Z' → '2026-10-31' (la API guarda la fecha calendario)."""
    m = re.match(r'(\d{4}-\d{2}-\d{2})', value or '')
    return m.group(1) if m else None


def merchant_for(title: str, name: str, category: str):
    t = _fold(f'{title} {name}')
    for pattern, brand, label in _MERCHANTS:
        if re.search(pattern, t):
            return brand, label
    clean = re.sub(r'^supermercados?\s+', '', _clean(title), flags=re.I)
    return (clean, clean) if clean else (None, None)


class PersonalPayScraper(BaseScraper):
    def __init__(self):
        super().__init__(
            name='Personal Pay',
            url='https://www.personal.com.ar/pay/beneficios'
        )

    async def scrape(self, page=None) -> List[Dict]:
        print(f"🔍 Scraping {self.name}...")
        print(f"   🌐 API: {_API}")

        loop = asyncio.get_event_loop()
        promotions: List[Dict] = []
        any_ok = False
        for api_category, category in _CATEGORIES:
            items = await loop.run_in_executor(None, lambda c=api_category: self._fetch_list(c))
            if items is None:
                continue
            any_ok = True
            print(f"   🔍 {api_category}: {len(items)} beneficios")
            for item in items:
                detail = await loop.run_in_executor(None, lambda i=item.get('id'): self._fetch_detail(i))
                promo = self.parse_benefit(item, detail, category)
                if promo:
                    promotions.append(promo)
                    print(f"   + {promo['title'][:70]} [{promo.get('tope')}] →{promo.get('valid_until')}")

        if not any_ok:
            return []
        print(f"✅ {self.name}: {len(promotions)} promociones")
        return promotions

    def _fetch_list(self, api_category: str) -> Optional[List[Dict]]:
        import requests
        out: List[Dict] = []
        offset = 0
        for _ in range(10):
            params = {'sourceSection': 'web', 'category': api_category}
            if offset:
                params['offset'] = offset
            try:
                resp = requests.get(_API, params=params, headers=_HEADERS, timeout=30)
                resp.raise_for_status()
                data = (resp.json() or {}).get('data') or {}
            except Exception as e:
                print(f"   ❌ Error en la API de Personal Pay ({api_category}): {e}")
                return out or None
            batch = data.get('benefits') or []
            new = [b for b in batch if b.get('id') not in {o.get('id') for o in out}]
            out.extend(new)
            try:
                next_offset = int((data.get('meta') or {}).get('offset') or 0)
            except (TypeError, ValueError):
                break
            if not new or next_offset <= offset:
                break
            offset = next_offset
        return out

    def _fetch_detail(self, benefit_id) -> Optional[Dict]:
        import requests
        try:
            resp = requests.get(f'{_API}/{benefit_id}', headers=_HEADERS, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            return data.get('data', data) if isinstance(data, dict) else None
        except Exception as e:
            print(f"   ⚠️ No se pudo obtener detalle de {benefit_id}: {e}")
            return None

    def parse_benefit(self, item: Dict, detail: Optional[Dict], category: str) -> Optional[Dict]:
        b = dict(item)
        if isinstance(detail, dict):
            b.update({k: v for k, v in detail.items() if v not in (None, '', [])})
        pct = re.search(r'(\d+)\s*%', str(item.get('discounts') or b.get('discounts') or ''))
        if not pct:
            return None
        pct = pct.group(1)
        brand, label = merchant_for(item.get('title') or '', item.get('name') or '', category)
        if not brand:
            return None

        description = _clean(b.get('description'))
        legal = _clean(b.get('legal') or b.get('documentTyc'))
        text = f'{description} {legal}'
        text_f = _fold(text)
        days = days_label(b.get('days') or [])

        legal_from, legal_until = parse_legal_dates(legal)
        api_until = _iso(b.get('dueDate'))
        valid_until = min(filter(None, [legal_until, api_until]), default=None)
        valid_from = legal_from or _iso(b.get('startDate'))

        positive = re.sub(r'no valido para (?:venta |compras )?online', '', text_f)
        online = bool(re.search(r'\bonline\b|sitio web|del sitio|en la app de', positive))
        stores = bool(re.search(r'fisica|presencial|sucursales', text_f))
        store_types = ', '.join(s for s, ok in (('Online', online), ('Tiendas', stores)) if ok) or None
        if category == 'fuel':
            store_types = 'Estaciones'
        payment = ', '.join(_clean(m.get('name')) for m in b.get('paymentMethods') or item.get('paymentMethods') or [] if m.get('name'))

        cashback = (item.get('typeCode') or b.get('typeCode')) == 'Cashback' or 'reintegro' in _fold(item.get('benefitValue') or '')
        title = f"Personal Pay {pct}% en {label} - {days}"
        exclusions = []
        excl = re.search(r'(exclu(?:ye|siones)[^.]*\.)', legal, re.I)
        if excl:
            exclusions.append(excl.group(1)[:300])

        return {
            'title':             title,
            'discount':          f"{pct}% reintegro" if cashback else f"{pct}%",
            'bank':              None,
            'wallet':            'Personal Pay',
            'card_type':         None,
            'payment_method':    payment or 'Personal Pay',
            'store_types':       store_types,
            'valid_days':        days,
            'url':               f"{self.url}",
            'image_url':         item.get('partnerImage'),
            'terms_raw':         legal or description,
            'tope':              parse_tope(f'{legal} {description}', item.get('limitAmountSubtitle')),
            'min_purchase':      parse_min_purchase(text, item.get('levels') or []),
            'exclusions':        exclusions,
            'requirements':      [description] if description else [],
            'valid_from':        valid_from,
            'valid_until':       valid_until,
            'merchant_brands':   [brand],
            'merchant_category': category,
            'source_id':         f"personalpay:{item.get('id')}",
        }
