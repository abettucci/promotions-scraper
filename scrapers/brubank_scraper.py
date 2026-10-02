"""
Brubank — Beneficios
URL: https://www.brubank.com/beneficios

La página es server-side rendered (Webflow). No requiere browser.
Cards: div.special-card-carousel.card-promo-dark
  - <h4 class="titulo-promo"> = beneficio (<strong>) + nombre del comercio
  - <p class="parrafo-promo-dark"> = tope y días
  - el link "Ir a promo" lleva a un artículo de help.brubank.com con las bases
    (vigencia, tope, plan requerido).

Es un AGGREGATOR: sólo se devuelven supermercados y combustible (con
merchant_brands). Además de las cards, el centro de ayuda publica variantes por
plan (Plan Plus, "Ruedita de Promociones") que no aparecen en la landing: se
buscan en el help center por comercio.
"""
import re
import asyncio
from datetime import date
from typing import List, Dict, Optional
from .base_scraper import BaseScraper


_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'es-AR,es;q=0.9',
}
_HELP_BASE = 'https://help.brubank.com'
_HELP_SEARCH = f'{_HELP_BASE}/es/'

# Patrón (sobre texto sin tildes, minúsculas) → (comercio canónico, rubro, búsqueda en el help).
_MERCHANTS = [
    (r'\bcoto\b',            'Coto Digital',           'supermarket', 'coto'),
    (r'carrefour',           'Carrefour',              'supermarket', 'carrefour'),
    (r'\bjumbo\b',           'Jumbo (Cencosud)',       'supermarket', 'jumbo'),
    (r'chango\s*mas|masonline|mas online', 'Más Online (ChangoMás)', 'supermarket', 'changomas'),
    (r'\bdia\b',             'Supermercados Día',      'supermarket', None),
    (r'\baxion\b',           'Axion',                  'fuel',        'axion'),
    (r'\bypf\b',             'YPF',                    'fuel',        'ypf'),
    (r'\bshell\b',           'Shell',                  'fuel',        'shell'),
    (r'\bpuma\b',            'Puma Energy',            'fuel',        'puma'),
]

_MONTHS = {
    'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6, 'julio': 7,
    'agosto': 8, 'septiembre': 9, 'setiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12,
}
_MES = '(' + '|'.join(_MONTHS) + ')'
_DAYS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
_DAY_KEYS = ['lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado', 'domingo']


def _strip_zw(text: str) -> str:
    """Saca caracteres de ancho cero (Webflow mete U+200D entre palabras)."""
    return re.sub(r'[​-‏⁠﻿]', '', text or '')


def _fold(text: str) -> str:
    table = str.maketrans('áéíóúüÁÉÍÓÚÜ', 'aeiouuaeiouu')
    return _strip_zw(text).translate(table).lower()


def _clean(text: str) -> str:
    return re.sub(r'\s+', ' ', _strip_zw(text)).strip()


def normalize_days(text: str) -> str:
    t = _fold(text)
    idx = [i for i, k in enumerate(_DAY_KEYS) if re.search(rf'\b{k}', t)]
    if not idx or len(idx) == 7:
        return 'Todos los días'
    return ', '.join(_DAYS[i] for i in idx)


def _money(value: str) -> str:
    """'6.000,00' → '$6.000'."""
    integer = re.split(r',\d{1,2}\b', value or '')[0]
    digits = re.sub(r'[^\d]', '', integer)
    return f"${int(digits):,}".replace(',', '.') if digits else ''


def _merchant_for(text: str):
    t = _fold(text)
    for pattern, brand, category, query in _MERCHANTS:
        if re.search(pattern, t):
            return brand, category, query
    return None


def _parse_date(day: str, month: str, year: str) -> Optional[str]:
    try:
        return date(int(year), _MONTHS[month], int(day)).isoformat()
    except (KeyError, ValueError):
        return None


def parse_terms(text: str) -> Dict:
    """Bases del artículo del help center → campos de la promo."""
    raw = _strip_zw(text)
    t = _fold(text)  # mismo largo que `raw`: los spans sirven para ambos
    out: Dict = {}
    # La sección "Vigencia" de las bases (la última mención) es la que manda.
    ranges = list(re.finditer(r'desde (?:el )?(\d{1,2}) de ' + _MES + r' de (\d{4})\s*(?:\d{1,2}:\d{2}\s*)?(?:al|hasta el|-)\s*(?:el )?(\d{1,2}) de ' + _MES + r' de (\d{4})', t))
    rng = ranges[-1] if ranges else None
    if rng:
        out['valid_from'] = _parse_date(rng.group(1), rng.group(2), rng.group(3))
        out['valid_until'] = _parse_date(rng.group(4), rng.group(5), rng.group(6))
    days = re.search(r'valida (?:todos )?(?:los )?dias?\s*([^(“"]{0,60})', t) or re.search(r'todos los dias (lunes|martes|miercoles|jueves|viernes|sabados?|domingos?)', t)
    if days:
        out['valid_days'] = normalize_days(days.group(1)) if days.group(1).strip() else 'Todos los días'
    pct = re.search(r'corresponde al (\d+)\s*%', t) or re.search(r'(\d+)\s*% de (?:descuento|reintegro)', t)
    if pct:
        out['pct'] = pct.group(1)
    tope = re.search(r'tope de \$\s*([\d.,]+)[^.]{0,40}?por compra participante', t)
    if tope:
        out['tope'] = f"{_money(tope.group(1))} por compra"
    elif 'sin tope' in t:
        out['tope'] = 'Sin tope'
    limits = [raw[m.start():m.end()].strip() for m in
              re.finditer(r'limite de \d+ ?\(\w+\) (?:transacci\w+|compras? participantes?)[^,.]*', t)]
    if limits:
        out['requirements'] = [_clean(l[0].upper() + l[1:]) for l in limits]
    if 'plan ultra' in t:
        out['plan'] = 'Plan Ultra'
    elif 'plan plus' in t:
        out['plan'] = 'Plan Plus'
    elif 'ruedita de promociones' in t or 'juga y participa' in t:
        out['plan'] = 'Ruedita'
    if 'descuento se aplicara en linea de caja' in t or 'directamente en caja' in t:
        out['instant'] = True
    if 'visa debito' in t and ('nfc' in t or 'sin contacto' in t):
        out['card_type'] = 'Débito'
        out['payment_method'] = 'Visa Débito Brubank sin contacto (NFC)'
    elif 'debito o credito' in t:
        out['card_type'] = 'Crédito, Débito'
        out['payment_method'] = 'Tarjeta Brubank (débito o crédito)'
    if 'sucursales fisicas' in t or 'tiendas presenciales' in t:
        out['store_types'] = 'Tiendas'
    if 'app ypf' in t:
        out['store_types'] = 'App YPF'
    return out


class BrubankScraper(BaseScraper):
    def __init__(self):
        super().__init__(name='Brubank', url='https://www.brubank.com/beneficios')

    async def scrape(self, page=None) -> List[Dict]:
        import requests
        from bs4 import BeautifulSoup

        print(f"🔍 Scraping {self.name}...")
        print(f"   🌐 URL: {self.url}")

        loop = asyncio.get_event_loop()
        try:
            resp = await loop.run_in_executor(
                None,
                lambda: requests.get(self.url, headers=_HEADERS, timeout=30)
            )
            resp.raise_for_status()
        except Exception as e:
            print(f"   ❌ Error fetching: {e}")
            return []

        cards = self.parse_cards(resp.text)
        print(f"   🔍 {len(cards)} cards de supermercado/combustible")

        # Artículos del help: los de las cards + los que aparecen buscando
        # por comercio (variantes por plan que no están en la landing).
        articles: Dict[str, Dict] = {}
        for card in cards:
            if card.get('href'):
                articles.setdefault(self._article_key(card['href']), {'url': card['href'], 'card': card})
        for query in sorted({c['query'] for c in cards if c.get('query')} | {'axion', 'ypf', 'coto', 'shell'}):
            for href in await loop.run_in_executor(None, lambda q=query: self._search_help(q)):
                articles.setdefault(self._article_key(href), {'url': href, 'card': None, 'query': query})

        promotions: List[Dict] = []
        seen_titles: set = set()
        for key, info in articles.items():
            html = await loop.run_in_executor(None, lambda u=info['url']: self._fetch(u))
            promo = self.build_promo(info.get('card'), self._article_text(html) if html else '', info['url'],
                                     query=info.get('query'))
            if not promo or promo['title'] in seen_titles:
                continue
            seen_titles.add(promo['title'])
            promotions.append(promo)
            print(f"   + {promo['title'][:70]} [{promo.get('tope')}] {promo.get('valid_from')}→{promo.get('valid_until')}")

        print(f"✅ {self.name}: {len(promotions)} promociones")
        return promotions

    @staticmethod
    def _article_key(href: str) -> str:
        m = re.search(r'/articles/(\d+)', href or '')
        return m.group(1) if m else href

    def parse_cards(self, html: str) -> List[Dict]:
        """Cards de la landing que son de supermercado o combustible."""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        out = []
        for card in soup.find_all('div', class_=re.compile(r'card-promo-dark')):
            h4 = card.find('h4', class_=re.compile(r'titulo-promo'))
            if not h4:
                continue
            strong = h4.find('strong')
            benefit = _clean(strong.get_text(' ', strip=True)) if strong else ''
            merchant_name = _clean(h4.get_text(' ', strip=True))
            if benefit and merchant_name.startswith(benefit):
                merchant_name = merchant_name[len(benefit):].strip(' |')
            p = card.find('p', class_=re.compile(r'parrafo-promo'))
            conditions = ''
            if p:
                for a in p.find_all('a'):
                    a.decompose()
                conditions = _clean(p.get_text(' ', strip=True))
            link = card.find_parent('a') or card.find('a', href=True)
            merchant = _merchant_for(merchant_name)
            if not merchant:
                continue
            brand, category, query = merchant
            out.append({
                'benefit': benefit, 'merchant_name': merchant_name, 'conditions': conditions,
                'href': link.get('href') if link else None,
                'brand': brand, 'category': category, 'query': query,
            })
        return out

    def _search_help(self, query: str) -> List[str]:
        """Artículos del help center cuyo slug menciona el comercio."""
        import requests
        from bs4 import BeautifulSoup
        try:
            resp = requests.get(_HELP_SEARCH, params={'q': query}, headers=_HEADERS, timeout=20)
            resp.raise_for_status()
        except Exception as e:
            print(f"   ⚠️ Búsqueda en help '{query}' falló: {e}")
            return []
        soup = BeautifulSoup(resp.text, 'html.parser')
        links = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            if '/articles/' not in href or query not in href.lower():
                continue
            links.append(href if href.startswith('http') else _HELP_BASE + href)
        return links

    @staticmethod
    def _fetch(url: str) -> Optional[str]:
        import requests
        try:
            resp = requests.get(url, headers=_HEADERS, timeout=20)
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            print(f"   ⚠️ No se pudo leer {url}: {e}")
            return None

    @staticmethod
    def _article_text(html: str) -> str:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        art = soup.find('article') or soup
        # El Anexo I (listado de estaciones) no aporta y alarga los legales.
        text = _strip_zw(art.get_text('\n', strip=True))
        return re.split(r'\nANEXO I\n', text)[0]

    def build_promo(self, card: Optional[Dict], terms: str, url: str, query: Optional[str] = None) -> Optional[Dict]:
        """Combina la card (si hay) con las bases del artículo."""
        info = parse_terms(terms) if terms else {}
        if card:
            brand, category = card['brand'], card['category']
        else:
            # Artículo encontrado por búsqueda: el comercio es el buscado
            # (el texto dice "Día de Participación" y confundiría a DÍA).
            merchant = next((m for m in _MERCHANTS if m[3] == query), None)
            if not merchant or not terms:
                return None
            _, brand, category, _ = merchant
            # Sin bases con vigencia y porcentaje no es una promo (FAQ, newsletter...).
            if not (info.get('valid_until') and info.get('pct')):
                return None
            if info['valid_until'] < date.today().isoformat():
                return None

        pct = info.get('pct')
        tope = info.get('tope')
        valid_days = info.get('valid_days')
        if card:
            card_pct = re.search(r'(\d+)\s*%', card['benefit'])
            pct = pct or (card_pct.group(1) if card_pct else None)
            cond = _fold(card['conditions'])
            card_tope = re.search(r'tope de reintegro:?\s*\$\s*([\d.,]+)', cond)
            if not tope:
                tope = f"{_money(card_tope.group(1))} por compra" if card_tope else ('Sin tope' if 'sin tope' in cond else None)
            # Los días se leen después del tope ("Tope de reintegro: $6.000 Todos los lunes").
            days_txt = re.sub(r'tope de reintegro:?\s*\$\s*[\d.,]+', '', cond)
            valid_days = valid_days or normalize_days(days_txt)
        if not pct:
            return None

        plan = info.get('plan')
        instant = info.get('instant') or (card and 'descuento' in _fold(card['benefit']))
        discount = f"{pct}%" if instant else f"{pct}% reintegro"
        days_label = valid_days or 'Todos los días'
        title = f"Brubank {pct}% en {brand} - {days_label}" + (f" ({plan})" if plan else '')
        requirements = list(info.get('requirements') or [])
        if plan == 'Plan Ultra':
            requirements.insert(0, 'Clientes suscriptos a Plan Ultra')
        elif plan == 'Plan Plus':
            requirements.insert(0, 'Clientes con Plan Plus activo')
        elif plan == 'Ruedita':
            requirements.insert(0, 'Girar la "Ruedita de Promociones" en la app después de la compra')

        return {
            'title':             title,
            'discount':          discount,
            'bank':              'Brubank',
            'wallet':            None,
            'card_type':         info.get('card_type'),
            'payment_method':    info.get('payment_method'),
            'store_types':       info.get('store_types') or ('Estaciones' if category == 'fuel' else None),
            'valid_days':        days_label,
            'url':               url or self.url,
            'image_url':         None,
            'terms_raw':         _clean(terms),
            'tope':              tope,
            'min_purchase':      None,
            'exclusions':        [],
            'requirements':      requirements,
            'valid_from':        info.get('valid_from'),
            'valid_until':       info.get('valid_until'),
            'merchant_brands':   [brand],
            'merchant_category': category,
            'source_id':         f"brubank:{self._article_key(url)}",
        }
