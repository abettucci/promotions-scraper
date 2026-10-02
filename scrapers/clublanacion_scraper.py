"""
Club La Nación — Beneficios
URL: https://club.lanacion.com.ar/beneficios

La web (Next.js) consume una API JSON pública que se llama directo (sin browser):
  GET https://api-clubv2.lanacion.com.ar/v2/accounts?category=supermercados...
      → comercios (crmid, name, slug)
  GET https://api-clubv2.lanacion.com.ar/v2/accounts/{crmid}/benefits
      → beneficios (type "15%", días, vigencia, programas, legal)

Es un AGGREGATOR: sólo supermercados y combustible, con merchant_brands.
La categoría "Mercados" mezcla supermercados con ~25 tiendas gourmet o de marca
(cafés, quesos, Nescafé, Arcor...). Se incluyen las de la subcategoría
"Supermercados" y una lista corta de tiendas que sí son supermercados/almacenes
online (En Combo); el resto ensuciaría el listado de supermercados.
"""
import re
import asyncio
from typing import List, Dict, Optional
from .base_scraper import BaseScraper


_API = 'https://api-clubv2.lanacion.com.ar/v2/accounts'
_SITE = 'https://club.lanacion.com.ar'
_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'es-AR,es;q=0.9',
    'Origin': _SITE,
    'Referer': f'{_SITE}/',
}

# (query del listado, rubro)
_LISTINGS = [
    ('category=supermercados', 'supermarket'),
    ('category=automovil&subcategory=automovil_combustible', 'fuel'),
]

# Nombre del comercio (sin tildes, minúsculas) → marca canónica.
_BRANDS = {
    'carrefour': 'Carrefour', 'coto': 'Coto Digital', 'dia': 'Supermercados Día',
    'jumbo': 'Jumbo (Cencosud)', 'changomas': 'Más Online (ChangoMás)', 'chango mas': 'Más Online (ChangoMás)',
    'ypf': 'YPF', 'shell': 'Shell', 'axion': 'Axion', 'axion energy': 'Axion', 'puma': 'Puma Energy',
    'en combo': 'En Combo',
}
# Tiendas de "Mercados" que se aceptan aunque no estén en la subcategoría Supermercados.
_ALLOWED_SHOPS = {'en combo'}

_DAY_MAP = {
    'monday': 'Lunes', 'tuesday': 'Martes', 'wednesday': 'Miércoles', 'thursday': 'Jueves',
    'friday': 'Viernes', 'saturday': 'Sábado', 'sunday': 'Domingo',
}
_DAY_ORDER = list(_DAY_MAP.values())


def _fold(text: str) -> str:
    table = str.maketrans('áéíóúüÁÉÍÓÚÜ', 'aeiouuaeiouu')
    return (text or '').translate(table).lower()


def _clean(text: str) -> str:
    return re.sub(r'\s+', ' ', text or '').strip()


def days_label(days: List[str]) -> str:
    names = {_DAY_MAP.get((d or '').lower()) for d in days or []} - {None}
    if not names or len(names) == 7:
        return 'Todos los días'
    return ', '.join(d for d in _DAY_ORDER if d in names)


def days_title(label: str) -> str:
    """'Martes, Miércoles, ..., Domingo' → 'Martes a Domingo' para el título."""
    names = [d.strip() for d in label.split(',')]
    idx = [_DAY_ORDER.index(d) for d in names if d in _DAY_ORDER]
    if len(idx) >= 3 and len(idx) == len(names) and idx == list(range(idx[0], idx[0] + len(idx))):
        return f"{names[0]} a {names[-1]}"
    return label


def _money(value: str) -> str:
    digits = re.sub(r'[^\d]', '', re.split(r',\d{1,2}\b', value or '')[0])
    return f"${int(digits):,}".replace(',', '.') if digits else ''


def parse_tope(text: str) -> Optional[str]:
    t = _fold(text)
    m = (re.search(r'tope (semanal|mensual|diario)? ?de (?:descuento |reintegro )?(?:por socio )?(?:de )?\$\s*([\d.,]+)', t)
         or re.search(r'tope[^$]{0,40}\$\s*([\d.,]+)', t))
    if m:
        if m.re.groups == 2:
            per, amount = m.group(1) or '', m.group(2)
        else:
            per, amount = '', m.group(1)
        tail = t[m.end():m.end() + 25]
        if not per:
            per = 'semanal' if re.match(r'\s*(/|por )\s*semana', tail) else \
                'mensual' if re.match(r'\s*(/|por )\s*mes', tail) else ''
        return _money(amount) + (f' {per}' if per else '')
    if 'sin tope' in t:
        return 'Sin tope'
    return None


def _date(value) -> Optional[str]:
    """'2026-10-31T23:59:59.999000-03:00' (o ms epoch) → '2026-10-31' (ART)."""
    if isinstance(value, (int, float)):
        from datetime import datetime, timedelta, timezone
        return datetime.fromtimestamp(value / 1000, tz=timezone(timedelta(hours=-3))).date().isoformat()
    m = re.match(r'(\d{4}-\d{2}-\d{2})', str(value or ''))
    return m.group(1) if m else None


def _qualifier(benefit: Dict, category: str) -> str:
    """Distingue beneficios de un mismo comercio (canal / producto)."""
    t = _fold(f"{benefit.get('title', '')} {benefit.get('description', '')}")
    if category == 'fuel':
        if 'infinia' in t:
            return 'Infinia con App YPF' if 'app ypf' in t else 'Infinia'
        if 'full' in t:
            return 'Tiendas Full'
        if 'boxes' in t or 'lubricante' in t:
            return 'Boxes, lubricante sintético'
    if 'entrega inmediata' in t:
        return 'Entrega Inmediata online'
    if 'tiendas fisicas' in t:
        return 'tiendas físicas'
    if benefit.get('onlinePurchase') and not benefit.get('branchPurchase'):
        return 'online con cupón' if benefit.get('promocode') else 'online'
    return ''


class ClubLaNacionScraper(BaseScraper):
    def __init__(self):
        super().__init__(
            name='Club La Nación',
            url='https://club.lanacion.com.ar/beneficios'
        )

    async def scrape(self, page=None) -> List[Dict]:
        print(f"🔍 Scraping {self.name}...")
        print(f"   🌐 API: {_API}")

        loop = asyncio.get_event_loop()
        promotions: List[Dict] = []
        for query, category in _LISTINGS:
            accounts = await loop.run_in_executor(None, lambda q=query: self._get(f'{_API}?includeFilters=false&{q}&sort=relevance&size=100&page=0'))
            if accounts is None:
                continue
            for account in self.select_accounts(accounts.get('data') or [], category):
                data = await loop.run_in_executor(
                    None, lambda c=account['crmid']: self._get(f'{_API}/{c}/benefits?page=0&size=50'))
                for benefit in (data or {}).get('data') or []:
                    promo = self.parse_benefit(account, benefit, category)
                    if promo:
                        promotions.append(promo)
                        print(f"   + {promo['title'][:75]} [{promo.get('tope')}] →{promo.get('valid_until')}")

        print(f"✅ {self.name}: {len(promotions)} promociones")
        return promotions

    @staticmethod
    def _get(url: str) -> Optional[Dict]:
        import requests
        try:
            resp = requests.get(url, headers=_HEADERS, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"   ⚠️ Error consultando {url}: {e}")
            return None

    @staticmethod
    def select_accounts(accounts: List[Dict], category: str) -> List[Dict]:
        """Filtra los comercios de 'Mercados' que no son supermercados."""
        if category == 'fuel':
            return accounts
        out = []
        for acc in accounts:
            name = _fold(_clean(acc.get('name')))
            slug = acc.get('slug') or ''
            if slug.startswith('/supermercados/supermercados/') or name in _ALLOWED_SHOPS:
                out.append(acc)
        return out

    def parse_benefit(self, account: Dict, b: Dict, category: str) -> Optional[Dict]:
        raw_name = _clean(account.get('name'))
        brand = _BRANDS.get(_fold(raw_name)) or raw_name.title()
        pct = re.search(r'(\d+)\s*%', b.get('type') or '')
        if not brand or not pct:
            return None
        pct = pct.group(1)
        days = days_label(b.get('days') or [])
        qualifier = _qualifier(b, category)
        programs = [p.get('description') for p in b.get('programs') or [] if p.get('description')]
        if programs and len(programs) < 3:
            qualifier = ', '.join(filter(None, [qualifier, 'socios ' + '/'.join(programs)]))
        title = f"Club La Nación {pct}% en {brand} - {days_title(days)}" + (f" ({qualifier})" if qualifier else '')

        description = _clean(b.get('description'))
        legal = _clean(b.get('legal'))
        stores = ', '.join(t for t, ok in (('Online', b.get('onlinePurchase')), ('Tiendas', b.get('branchPurchase'))) if ok) or None
        if category == 'fuel':
            stores = 'Tiendas Full' if 'full' in _fold(qualifier) else 'Estaciones'
        desc_f = _fold(description + ' ' + legal)
        if 'app ypf' in desc_f:
            payment = 'App YPF + credencial Club LA NACION'
        elif b.get('promocode'):
            payment = 'Cupón Club LA NACION'
        elif b.get('onlinePurchase') and not b.get('branchPurchase'):
            payment = 'Número de credencial Club LA NACION'
        else:
            payment = 'Credencial Club LA NACION + DNI'
        exclusions = []
        excl = re.search(r'(no v[aá]lido (?:para|en) [^.]+\.)', description + ' ' + legal, re.I)
        if excl:
            exclusions.append(excl.group(1))

        return {
            'title':             title,
            'discount':          f"{pct}%",
            'bank':              None,
            'wallet':            'Club La Nación',
            'card_type':         None,
            'payment_method':    payment,
            'store_types':       stores,
            'valid_days':        days,
            'url':               f"{_SITE}{account.get('slug') or ''}" if account.get('slug') else self.url,
            'image_url':         ((b.get('images') or [{}])[0] or {}).get('url'),
            'terms_raw':         legal or description,
            'tope':              parse_tope(description) or parse_tope(legal),
            'min_purchase':      None,
            'exclusions':        exclusions,
            'requirements':      [description] + ([f"Socios {', '.join(programs)}"] if programs else []),
            'valid_from':        _date(b.get('fromDate')),
            'valid_until':       _date(b.get('toDate')),
            'merchant_brands':   [brand],
            'merchant_category': category,
            'merchant_url':      (b.get('externalUrl') or '').split('?')[0] or None,
            'source_id':         f"clublanacion:{b.get('id')}",
        }
