"""
Cuenta DNI (Banco Provincia) — Beneficios
URL: https://www.bancoprovincia.com.ar/cuentadni/contenidos/cdniBeneficios/

Sitio server-side rendered (ASP.NET MVC), sin JS necesario. Las cards activas
vienen completas en el HTML inicial. El detalle de cada card (tope, legales,
condiciones, vigencia) se obtiene con una request extra por beneficio a:
  GET /cuentadni/Home/GetBeneficioData2?idBeneficio={id}

Es un AGGREGATOR: cada promo se rutea al comercio (merchant_brands) y sólo se
devuelven supermercados y combustible; el resto de los rubros se descarta.
"""
import re
import asyncio
import calendar
from datetime import date, datetime, timedelta, timezone
from typing import List, Dict, Optional
from .base_scraper import BaseScraper


_BASE = 'https://www.bancoprovincia.com.ar'
_LIST_URL = f'{_BASE}/cuentadni/contenidos/cdniBeneficios/'
_DETAIL_URL = f'{_BASE}/cuentadni/Home/GetBeneficioData2'

_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'es-AR,es;q=0.9',
}

_ART = timezone(timedelta(hours=-3))

# slug del beneficio (Beneficio.url / id del card) → (comercio canónico, rubro).
# Lo que no está acá no es supermercado ni combustible y se descarta.
_MERCHANTS = {
    'dia':                            ('Supermercados Día', 'supermarket'),
    'nini':                           ('Mayorista Nini', 'supermarket'),
    # Red de supermercados adheridos sin cadena puntual (la nómina está en
    # el buscador del banco): se agrupa en un comercio genérico.
    'supermercados_martesymiercoles': ('Supermercados de cercanía', 'supermarket'),
    'laanonima':                      ('La Anónima', 'supermarket'),
    'carrefour':                      ('Carrefour', 'supermarket'),
    'josimar':                        ('Josimar', 'supermarket'),
    'changomas':                      ('Más Online (ChangoMás)', 'supermarket'),
    'supercoop':                      ('Supercoop', 'supermarket'),
    # Gastronomía en las tiendas Full de YPF: se publica en la estación.
    'especialypf':                    ('YPF', 'fuel'),
}

# Nombre entre comillas en el legal ("MAYORISTA NINI") → slug, por si el
# banco cambia el slug de la URL.
_LEGAL_NAMES = {
    'mayorista nini': 'nini', 'la anonima': 'laanonima', 'supermercados josimar': 'josimar',
    'supercoop': 'supercoop', 'carrefour': 'carrefour', 'dia': 'dia',
}

_MONTHS = {
    'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6, 'julio': 7,
    'agosto': 8, 'septiembre': 9, 'setiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12,
}
_MES = '(' + '|'.join(_MONTHS) + ')'

_DAYS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
_DAY_KEYS = ['lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado', 'domingo']


def _fold(text: str) -> str:
    """Minúsculas sin tildes (para matchear legales en mayúsculas)."""
    table = str.maketrans('áéíóúüÁÉÍÓÚÜâÂ', 'aeiouuaeiouuaa')
    return (text or '').translate(table).lower()


def normalize_days(text: str) -> str:
    """'Martes y miércoles' → 'Martes, Miércoles'; 'Lunes a viernes' → rango."""
    t = _fold(text)
    if not t.strip():
        return 'Todos los días'
    rng = re.search(r'(' + '|'.join(_DAY_KEYS) + r')\s+a\s+(' + '|'.join(_DAY_KEYS) + r')', t)
    if rng:
        a, b = _DAY_KEYS.index(rng.group(1)), _DAY_KEYS.index(rng.group(2))
        idx = list(range(a, b + 1))
    else:
        idx = [i for i, k in enumerate(_DAY_KEYS) if re.search(rf'\b{k}', t)]
    if len(idx) == 7:
        return 'Todos los días'
    return ', '.join(_DAYS[i] for i in idx) or 'Todos los días'


def _money(value: str) -> str:
    digits = re.sub(r'[^\d]', '', value or '')
    return f"${int(digits):,}".replace(',', '.') if digits else ''


def parse_tope(legal: str, bajada: str = '') -> Optional[str]:
    """Tope del legal (o de la bajada sólo si menciona 'tope')."""
    for text in (legal, bajada if 'tope' in _fold(bajada) else ''):
        t = _fold(text)
        if not t:
            continue
        m = re.search(r'tope de reintegro(?: unificado)?(?: de)?(?: hasta)?\s*\$\s*([\d.]+)(?:[^.$]{0,40}?por\s+(semana|mes|vigencia|\w+))?', t)
        if m:
            amount = _money(m.group(1))
            per = m.group(2) or ''
            suffix = {'semana': ' semanal', 'mes': ' mensual', 'vigencia': ' por vigencia'}.get(
                per, ' por día' if per.rstrip('s') in _DAY_KEYS or per in _DAY_KEYS else '')
            return amount + suffix
        if re.search(r'sin tope', t):
            return 'Sin tope'
    return None


def parse_min_purchase(legal: str) -> Optional[str]:
    t = _fold(legal)
    m = (re.search(r'minimo de compra(?: sea)?(?: de)?\s*\$\s*([\d.]+)', t)
         or re.search(r'(?:iguales o superiores|superiores) a\s*\$\s*([\d.]+)', t))
    return _money(m.group(1)) if m else None


def parse_legal_dates(legal: str):
    """Vigencia escrita en el legal: 'entre el 1 de octubre y el 31 de diciembre
    de 2026', 'desde el 18 de septiembre al 31 de octubre del 2026', 'los martes
    de octubre del 2026', 'de los meses de septiembre y octubre, del 2026'."""
    t = _fold(legal)
    rng = re.search(
        r'(?:entre el|desde el|del)\s+(\d{1,2})(?:\s+de\s+' + _MES + r')?\s+(?:y el|al|hasta el)\s+(\d{1,2})\s+de\s+'
        + _MES + r',?\s+(?:de|del)\s+(\d{4})', t)
    try:
        if rng:
            year = int(rng.group(5))
            m_to = _MONTHS[rng.group(4)]
            m_from = _MONTHS[rng.group(2)] if rng.group(2) else m_to
            start = date(year if m_from <= m_to else year - 1, m_from, int(rng.group(1)))
            return start.isoformat(), date(year, m_to, int(rng.group(3))).isoformat()
        months = re.search(r'\bde(?: los meses de| el mes de| mes de)?\s+' + _MES + r'(?:\s+y\s+' + _MES + r')?,?\s+(?:de|del)\s+(\d{4})', t)
        if months:
            year = int(months.group(3))
            m1 = _MONTHS[months.group(1)]
            m2 = _MONTHS[months.group(2)] if months.group(2) else m1
            last = calendar.monthrange(year, m2)[1]
            return date(year, m1, 1).isoformat(), date(year, m2, last).isoformat()
    except ValueError:
        pass
    return None, None


def parse_dotnet_date(value: Optional[str], shift_days: int = 0) -> Optional[str]:
    """'/Date(ms)/' (UTC) → fecha en hora Argentina, desplazada `shift_days`."""
    m = re.search(r'/Date\((-?\d+)\)/', value or '')
    if not m:
        return None
    try:
        dt = datetime.fromtimestamp(int(m.group(1)) / 1000, tz=_ART) + timedelta(days=shift_days)
        return dt.date().isoformat()
    except (ValueError, OSError, OverflowError):
        return None


class CuentaDniScraper(BaseScraper):
    def __init__(self):
        super().__init__(name='Cuenta DNI', url=_LIST_URL)

    async def scrape(self, page=None) -> List[Dict]:
        import requests
        from bs4 import BeautifulSoup

        print(f"🔍 Scraping {self.name}...")
        print(f"   🌐 URL: {self.url}")

        loop = asyncio.get_event_loop()
        try:
            resp = await loop.run_in_executor(
                None, lambda: requests.get(self.url, headers=_HEADERS, timeout=30)
            )
            resp.raise_for_status()
        except Exception as e:
            print(f"   ❌ Error fetching: {e}")
            return []

        soup = BeautifulSoup(resp.text, 'html.parser')
        cards = soup.select('div.callModalCDNI.BEN_filterDiv')
        print(f"   🔍 {len(cards)} cards encontradas")

        promotions: List[Dict] = []
        seen: set = set()
        for card in cards:
            m = re.match(r'(.+)-(\d+)$', card.get('id', ''))
            if not m or m.group(2) in seen:
                continue
            slug, beneficio_id = m.group(1), m.group(2)
            seen.add(beneficio_id)
            # Sólo pedimos el detalle de los rubros que nos interesan (por
            # slug); si el slug es desconocido igual lo pedimos y decide el legal.
            if slug not in _MERCHANTS and not self._may_be_supermarket(card):
                continue
            detail = await loop.run_in_executor(None, lambda bid=beneficio_id: self._fetch_detail(bid))
            if not detail:
                continue
            card_days = card.find('div', class_='BEN_CON_dias')
            for promo in self.parse_detail(detail, card_days.get_text(' ', strip=True) if card_days else ''):
                promotions.append(promo)
                print(f"   + {promo['title'][:70]} [{promo.get('tope')}]")

        print(f"✅ {self.name}: {len(promotions)} promociones")
        return promotions

    @staticmethod
    def _may_be_supermarket(card) -> bool:
        return 'super' in _fold(card.get_text(' ', strip=True))

    def _fetch_detail(self, beneficio_id: str) -> Optional[Dict]:
        import requests
        try:
            resp = requests.get(
                _DETAIL_URL, params={'idBeneficio': beneficio_id},
                headers=_HEADERS, timeout=20,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"   ⚠️ No se pudo obtener detalle de {beneficio_id}: {e}")
            return None

    def _merchant_for(self, beneficio: Dict):
        slug = (beneficio.get('url') or '').strip().lower()
        if slug in _MERCHANTS:
            return _MERCHANTS[slug]
        legal = _fold(beneficio.get('legal') or '')
        for quoted in re.findall(r'[“"]([^”"]+)[”"]', legal):
            key = _LEGAL_NAMES.get(quoted.strip())
            if key:
                return _MERCHANTS[key]
        return None

    def parse_detail(self, detail: Dict, card_days: str = '') -> List[Dict]:
        """Detalle de GetBeneficioData2 → 0..N promos (DÍA publica dos tramos)."""
        entity = (detail or {}).get('Entity') or {}
        b = entity.get('Beneficio') or {}
        merchant = self._merchant_for(b)
        if not merchant:
            return []
        brand, category = merchant
        slug = (b.get('url') or '').strip().lower()
        legal = self.clean_text(b.get('legal') or '')
        pct = b.get('porcentaje')
        if not pct:
            return []

        valid_days = normalize_days(b.get('titulo_fecha') or card_days)
        legal_from, legal_until = parse_legal_dates(legal)
        # La API guarda medianoche ART en UTC y fecha_hasta es exclusiva.
        api_from = parse_dotnet_date(b.get('fecha_desde'))
        api_until = parse_dotnet_date(b.get('fecha_hasta'), shift_days=-1)
        valid_from = max(filter(None, [legal_from, api_from]), default=None)
        valid_until = min(filter(None, [legal_until, api_until]), default=None)

        exclusions, requirements = [], []
        for cond in entity.get('Condiciones') or []:
            texto = self.clean_text(cond.get('texto', ''))
            if not texto:
                continue
            if re.search(r'no aplica|excluy|salvo|no incluye', texto, re.IGNORECASE):
                exclusions.append(texto)
            else:
                requirements.append(texto)

        merchant_url = None
        for boton in entity.get('Botones') or []:
            if boton.get('link'):
                merchant_url = boton['link']
                break

        base = {
            'discount':        f"{pct}% reintegro",
            'bank':            'Banco Provincia',
            'wallet':          'Cuenta DNI',
            'card_type':       None,
            'payment_method':  'Cuenta DNI (dinero en cuenta)',
            'store_types':     'Tiendas',
            'valid_days':      valid_days,
            'url':             f"{_LIST_URL}#{slug}-{b.get('id')}",
            'image_url':       f"{_BASE}/CDN/Get/{b['logo']}" if b.get('logo') else None,
            'terms_raw':       legal,
            'tope':            parse_tope(legal, b.get('bajada') or ''),
            'min_purchase':    parse_min_purchase(legal),
            'exclusions':      exclusions,
            'requirements':    requirements,
            'valid_from':      valid_from,
            'valid_until':     valid_until,
            'merchant_brands': [brand],
            'merchant_category': category,
            'merchant_url':    merchant_url,
            'source_id':       f"cuentadni:{b.get('id')}",
        }
        days_label = valid_days
        place = 'Tiendas Full YPF' if slug == 'especialypf' else brand

        legal_f = _fold(legal)
        nfc_tier = re.search(r'(\d+)% de reintegro, sin tope, para las compras realizadas de manera presencial a traves de cuenta dni con tecnologia sin contacto \(nfc\)', legal_f)
        account_tier = re.search(r'(\d+)% de reintegro, sin tope, para las compras realizadas de manera presencial con cuenta dni dinero en cuenta', legal_f)
        if nfc_tier and account_tier and nfc_tier.group(1) != account_tier.group(1):
            # Dos tramos distintos (DÍA: 20% NFC Visa crédito / 10% dinero en cuenta).
            nfc = dict(base, discount=f"{nfc_tier.group(1)}% reintegro", card_type='Crédito',
                       payment_method='Cuenta DNI NFC con Visa crédito (Android)', tope='Sin tope',
                       title=f"Cuenta DNI {nfc_tier.group(1)}% en {place} - {days_label} (NFC Visa crédito)",
                       source_id=f"cuentadni:{b.get('id')}:nfc")
            account = dict(base, discount=f"{account_tier.group(1)}% reintegro", tope='Sin tope',
                           title=f"Cuenta DNI {account_tier.group(1)}% en {place} - {days_label} (dinero en cuenta)",
                           source_id=f"cuentadni:{b.get('id')}:cuenta")
            return [nfc, account]
        if nfc_tier and account_tier:
            base['payment_method'] = 'Cuenta DNI (dinero en cuenta o NFC Visa crédito)'
        if 'descuento se realizara en el momento' in legal_f or 'linea de caja' in legal_f:
            base['discount'] = f"{pct}%"
        base['title'] = f"Cuenta DNI {pct}% en {place} - {days_label}"
        return [base]
