"""
Buepp — Beneficios
URL: https://www.buepp.com.ar/beneficios

Buepp es la billetera digital de Banco Ciudad. La landing es una SPA Angular,
pero consume una API JSON pública que se puede llamar directo (sin browser):
  POST /buepp_api/beneficios/filter   → listado por rubro (10 = Supermercados)
  POST /buepp_api/beneficios/{id}     → detalle (legales, vigencia, medios)

Es un AGGREGATOR: cada promo se rutea al comercio (merchant_brands). La API no
tiene rubro de combustible (Automotores sólo trae cuotas en talleres/GNC), así
que sólo se devuelven supermercados.
"""
import re
import html as _html
import asyncio
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
from .base_scraper import BaseScraper


_API = 'https://www.buepp.com.ar/buepp_api/beneficios'
_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'es-AR,es;q=0.9',
    'Content-Type': 'application/json',
    'Origin': 'https://www.buepp.com.ar',
    'Referer': 'https://www.buepp.com.ar/beneficios',
}
_RUBRO_SUPERMERCADOS = 10
_ART = timezone(timedelta(hours=-3))

# Nombre del comercio en la API (sin tildes, minúsculas) → (marca canónica, nombre para el título).
# MásGO es el formato de cercanía de ChangoMás: se publica bajo esa cadena,
# aclarando "MásGO" en el título y en store_types (no aplica en los híper).
_MERCHANTS = [
    (r'^coto\b',           'Coto Digital',           'Coto'),
    (r'^mas\s*go\b',       'Más Online (ChangoMás)', 'MásGO'),
    (r'chango\s*mas',      'Más Online (ChangoMás)', 'ChangoMás'),
    (r'^carrefour',        'Carrefour',              'Carrefour'),
    (r'^(supermercados )?dia\b', 'Supermercados Día', 'Día'),
    (r'^jumbo\b',          'Jumbo (Cencosud)',       'Jumbo'),
]

_DAYS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']


def _fold(text: str) -> str:
    table = str.maketrans('áéíóúüÁÉÍÓÚÜ', 'aeiouuaeiouu')
    return (text or '').translate(table).lower()


def _clean(text: str) -> str:
    return re.sub(r'\s+', ' ', text or '').strip()


def html_to_text(value: str) -> str:
    """Legales vienen como documento HTML con entidades."""
    text = re.sub(r'<[^>]+>', ' ', value or '')
    return _clean(_html.unescape(text))


def days_from_mask(mask: str) -> str:
    """'L------' → 'Lunes'; 'LMMJVSD' → 'Todos los días'."""
    mask = (mask or '').ljust(7, '-')[:7]
    days = [_DAYS[i] for i, ch in enumerate(mask) if ch not in '-']
    if not days or len(days) == 7:
        return 'Todos los días'
    return ', '.join(days)


def _money(value: str) -> str:
    digits = re.sub(r'[^\d]', '', re.split(r',\d{1,2}\b', value or '')[0])
    return f"${int(digits):,}".replace(',', '.') if digits else ''


def parse_tope(subtitulo: str, sin_tope: bool, legal: str = '') -> Optional[str]:
    if sin_tope:
        return 'Sin tope'
    for text in (subtitulo, legal):
        t = _fold(text)
        m = re.search(r'tope[^$]{0,60}\$\s*([\d.,]+)', t)
        if m:
            per_m = re.search(r'\b(semana|semanal|mensual|mes|dia|diario)\b', t[m.end():m.end() + 40].split('.')[0])
            per = per_m.group(1) if per_m else ''
            suffix = ' semanal' if per.startswith('seman') else ' mensual' if per in ('mensual', 'mes') else \
                ' diario' if per in ('dia', 'diario') else ''
            return _money(m.group(1)) + suffix
        if 'sin tope' in t:
            return 'Sin tope'
    return None


def parse_min_purchase(text: str) -> Optional[str]:
    m = re.search(r'compras? m[ií]nimas? de \$\s*([\d.,]+)|m[ií]nimo de compra:? \$\s*([\d.,]+)', text or '', re.I)
    return _money(m.group(1) or m.group(2)) if m else None


def parse_legal_dates(legal: str):
    """'desde el 07/09/2026 al 31/12/2026' / 'DESDE EL 27/08/2026 HASTA EL 31/12/2026'."""
    m = re.search(r'desde el (\d{1,2})/(\d{1,2})/(\d{4}) (?:al|hasta el) (\d{1,2})/(\d{1,2})/(\d{4})', legal or '', re.I)
    if not m:
        return None, None
    d1, m1, y1, d2, m2, y2 = m.groups()
    return f"{y1}-{int(m1):02d}-{int(d1):02d}", f"{y2}-{int(m2):02d}-{int(d2):02d}"


def _api_date(value: Optional[str]) -> Optional[str]:
    """'2026-10-31T03:00:00.000+00:00' (medianoche ART en UTC) → '2026-10-31'."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(_ART).date().isoformat()
    except ValueError:
        return None


def merchant_for(name: str):
    """Comercio de la API → (marca canónica, nombre para el título)."""
    t = _fold(_clean(name))
    for pattern, brand, label in _MERCHANTS:
        if re.search(pattern, t):
            return brand, label
    clean = _clean(name)
    return (clean, clean) if clean else (None, None)


class BueppScraper(BaseScraper):
    def __init__(self):
        super().__init__(
            name='Buepp',
            url='https://www.buepp.com.ar/beneficios'
        )

    async def scrape(self, page=None) -> List[Dict]:
        print(f"🔍 Scraping {self.name}...")
        print(f"   🌐 API: {_API}/filter (rubro Supermercados)")

        loop = asyncio.get_event_loop()
        items = await loop.run_in_executor(None, self._fetch_list)
        if items is None:
            return []
        print(f"   🔍 {len(items)} beneficios en Supermercados")

        promotions: List[Dict] = []
        for item in items:
            detail = await loop.run_in_executor(None, lambda i=item['idBeneficio']: self._fetch_detail(i))
            promo = self.parse_benefit(item, detail)
            if promo:
                promotions.append(promo)
                print(f"   + {promo['title'][:70]} [{promo.get('tope')}] →{promo.get('valid_until')}")

        print(f"✅ {self.name}: {len(promotions)} promociones")
        return promotions

    def _fetch_list(self) -> Optional[List[Dict]]:
        import requests
        out: List[Dict] = []
        for page_number in range(1, 6):
            body = {
                'palabra_clave': '', 'rubros': [_RUBRO_SUPERMERCADOS], 'dias': '', 'medios_de_pago': [0],
                'limite_descuento': 0, 'latitud': None, 'longitud': None, 'zona': None,
                'aplica_tienda': False, 'ordenamiento': 'POPULARIDAD',
                'numero_pagina': page_number, 'tamano_pagina': 100,
            }
            try:
                resp = requests.post(f'{_API}/filter', json=body, headers=_HEADERS, timeout=30)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                print(f"   ❌ Error en la API de Buepp: {e}")
                return out or None
            batch = data.get('beneficios') or []
            out.extend(batch)
            if len(batch) < 100 or len(out) >= (data.get('cantidadTotalBeneficios') or 0):
                break
        return out

    def _fetch_detail(self, beneficio_id) -> Optional[Dict]:
        import requests
        try:
            resp = requests.post(f'{_API}/{beneficio_id}', json={'latitud': None, 'longitud': None},
                                 headers=_HEADERS, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"   ⚠️ No se pudo obtener detalle de {beneficio_id}: {e}")
            return None

    def parse_benefit(self, item: Dict, detail: Optional[Dict]) -> Optional[Dict]:
        """Ítem del listado (+ detalle si está) → promo; None si no aplica."""
        b = dict(item)
        if detail and detail.get('beneficio'):
            b.update({k: v for k, v in detail['beneficio'].items() if v not in (None, '')})
        name = (detail or {}).get('comercio', {}).get('nombre') or item.get('comercio_nombre') or ''
        brand, label = merchant_for(name)
        pct = b.get('descuento')
        if not brand or not pct:
            # Sin porcentaje (cuotas) no es un descuento de supermercado útil.
            return None

        legal = html_to_text(b.get('legales') or '')
        resumen = _clean(b.get('resumen') or '')
        legal_f = _fold(legal + ' ' + resumen)
        valid_from, valid_until = parse_legal_dates(legal)
        valid_from = valid_from or _api_date(b.get('fechaDesde'))
        valid_until = valid_until or _api_date(b.get('fechaHasta'))

        medios = [m.get('nombre', '') for m in b.get('medios_pago') or []]
        has_credit = 'credito' in legal_f or any(m.get('credito') == 'S' for m in b.get('medios_pago') or [])
        has_debit = 'debito' in legal_f
        card_type = ', '.join(t for t, ok in (('Crédito', has_credit), ('Débito', has_debit)) if ok) or None
        brands_cards = [m.title() for m in medios if m in ('VISA', 'MASTERCARD', 'CABAL')]
        payment = 'QR MODO (Buepp / App Ciudad)'
        if 'nfc' in legal_f:
            payment += ' o NFC'
        if brands_cards and not has_debit:
            payment += f" con {' / '.join(brands_cards)} crédito Banco Ciudad"

        online = bool(b.get('aplica_tienda_online')) and ('tienda online' in legal_f or 'www.' in legal_f)
        stores = 'Online, Tiendas' if online else 'Tiendas'
        if label == 'MásGO':
            stores = 'Online, Tiendas MásGO' if online else 'Tiendas MásGO'

        days = days_from_mask(b.get('dias') or b.get('diasBeneficio'))
        tope = parse_tope(b.get('subtitulo') or '', bool(b.get('sin_tope')), legal)
        exclusions = []
        excl = re.search(r'(exclusiones:[^.]*\.|no incluye[^.]*\.|excusiones informadas por el comercio:[^.]*\.)', legal, re.I)
        if excl:
            exclusions.append(excl.group(1)[:300])
        title = f"Buepp {pct}% en {label} - {days}"
        if 'credito' in _fold(payment) and 'Débito' not in (card_type or ''):
            title += ' (crédito)'

        return {
            'title':             title,
            'discount':          f"{pct}% reintegro",
            'bank':              'Banco Ciudad',
            'wallet':            'Buepp',
            'card_type':         card_type,
            'payment_method':    payment,
            'store_types':       stores,
            'valid_days':        days,
            'url':               self.url,
            'image_url':         None,
            'terms_raw':         legal or resumen,
            'tope':              tope,
            'min_purchase':      parse_min_purchase(b.get('subtitulo') or '') or parse_min_purchase(legal),
            'exclusions':        exclusions,
            'requirements':      [resumen] if resumen else [],
            'valid_from':        valid_from,
            'valid_until':       valid_until,
            'merchant_brands':   [brand],
            'merchant_category': 'supermarket',
            'source_id':         f"buepp:{b.get('idBeneficio') or b.get('id')}",
        }
