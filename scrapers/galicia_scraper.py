"""
Banco Galicia — Promoción combustible (aggregator)
URL: https://www.galicia.ar/personas/promociones/promocion-combustible

La página es AEM: el contenido completo está en el JSON del modelo
(<url>.model.json), sin JS ni navegador:
  - verticalSecondaryModule.title/description: tramos ("10% de ahorro",
    "Tope de reintegro: $10.000. (1)").
  - responsivegrid/:items/text/text: legales numerados (1)(2)(3).

La promo es los días 10 de cada mes en YPF, Shell, Axion y Puma. El legal suele
quedar con la fecha del mes anterior ("Válida únicamente para el día 10/09/2026"):
si esa fecha ya pasó y la página sigue anunciando "días 10 de cada mes",
emitimos la próxima fecha 10.
"""
import asyncio
import html as html_lib
import re
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Iterator, List, Optional


_URL = 'https://www.galicia.ar/personas/promociones/promocion-combustible'
_MODEL_URL = f'{_URL}.model.json'

_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json',
    'Accept-Language': 'es-AR,es;q=0.9',
}

STATIONS = ['YPF', 'Shell', 'Axion', 'Puma Energy']
_WEEKDAYS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']


def _today_ar() -> date:
    return (datetime.now(timezone.utc) - timedelta(hours=3)).date()


def _text(raw: Optional[str]) -> str:
    if not raw:
        return ''
    t = re.sub(r'<[^>]+>', ' ', raw)
    t = html_lib.unescape(t).replace('\xa0', ' ')
    return re.sub(r'\s+', ' ', t).strip()


def _walk(node) -> Iterator[Dict]:
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


def next_day(day: int, today: date) -> date:
    """Próxima fecha (hoy incluido) con ese número de día."""
    if today.day <= day:
        return today.replace(day=day)
    year, month = (today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1)
    return date(year, month, day)


class GaliciaScraper:
    def __init__(self):
        self.name = 'Banco Galicia'
        self.url = _URL

    async def scrape(self, page=None) -> List[Dict]:
        import requests

        print(f"🔍 Scraping {self.name} (AEM model.json)...")
        loop = asyncio.get_event_loop()
        try:
            resp = await loop.run_in_executor(
                None, lambda: requests.get(_MODEL_URL, headers=_HEADERS, timeout=30)
            )
            resp.raise_for_status()
            model = resp.json()
        except Exception as e:
            print(f"   ❌ Error leyendo {_MODEL_URL}: {e}")
            return []

        promotions = self.parse_model(model)
        for p in promotions:
            print(f"   + {p['title']} | {p['tope']} | {p['valid_from']}")
        print(f"✅ {self.name}: {len(promotions)} promociones")
        return promotions

    def parse_model(self, model: Dict, today: Optional[date] = None) -> List[Dict]:
        today = today or _today_ar()
        tiers, legal_html, page_text = [], '', []
        for node in _walk(model):
            mod = node.get('verticalSecondaryModule')
            if isinstance(mod, dict) and mod.get('title'):
                tiers.append((_text(mod.get('title')), _text(mod.get('description'))))
            for key in ('description', 'text'):
                val = node.get(key)
                if isinstance(val, str):
                    if not legal_html and re.search(r'\(1\)\s*CARTERA', _text(val)):
                        legal_html = val
                    page_text.append(_text(val))
        full_text = ' '.join(page_text)
        legals = self._split_legals(_text(legal_html))
        monthly = re.search(r'd[ií]as?\s+10\s+de\s+cada\s+mes', full_text, re.I)

        promotions = []
        for title, desc in tiers:
            pct = re.search(r'(\d+)\s*%', title)
            ref = re.search(r'\((\d)\)', desc)
            if not pct or not ref:
                continue
            legal = legals.get(ref.group(1), '')
            extra = 'extra' in title.lower() or 'adicional' in title.lower()
            segment = self._segment(legal, desc)
            tope_m = re.search(r'\$\s?([\d.]+)', desc) or re.search(r'\$\s?([\d.]+)\s+en total por mes', legal)
            tope = f"${tope_m.group(1).rstrip('.')} mensual" if tope_m else None

            promo_day = self._promo_date(legal, bool(monthly), today)
            day_label = None
            if promo_day:
                day_label = f"Día {promo_day.day} de cada mes ({_WEEKDAYS[promo_day.weekday()]})" if monthly \
                    else _WEEKDAYS[promo_day.weekday()]

            discount = f"{pct.group(1)}%" + (' extra' if extra else '')
            promotions.append({
                'title': f"Banco Galicia {discount} en YPF, Shell, Axion y Puma - Día 10 ({segment})",
                'discount': discount,
                'bank': 'Banco Galicia',
                'wallet': None,
                'card_type': 'Crédito',
                'payment_method': 'Tarjeta Mastercard Galicia: sin contacto con el celular o QR MODO desde App Galicia',
                'store_types': 'Tiendas',
                'valid_days': day_label,
                'valid_from': promo_day.isoformat() if promo_day else None,
                'valid_until': promo_day.isoformat() if promo_day else None,
                'tope': tope,
                'min_purchase': None,
                'terms_raw': legal or desc,
                'requirements': [f"Clientes {segment}" if not segment.startswith('Clientes') else segment,
                                 'Caja de ahorro en Banco Galicia'],
                'exclusions': ['Pagos con dinero en cuenta o transferencia',
                               'Billeteras virtuales distintas de MODO'],
                'source_id': f"galicia:combustible:{ref.group(1)}",
                'url': _URL,
                'merchant_brands': list(STATIONS),
                'merchant_category': 'fuel',
            })
        return promotions

    @staticmethod
    def _split_legals(text: str) -> Dict[str, str]:
        parts = re.split(r'\((\d)\)\s*(?=CARTERA)', text)
        return {parts[i]: parts[i + 1].strip() for i in range(1, len(parts) - 1, 2)}

    @staticmethod
    def _segment(legal: str, desc: str) -> str:
        low = f"{legal} {desc}".lower()
        if 'éminent' in low or 'eminent' in low:
            return 'Éminent'
        if 'haberes' in low or 'sueldo' in low:
            return 'Plan Sueldo'
        return 'Clientes Galicia'

    @staticmethod
    def _promo_date(legal: str, monthly: bool, today: date) -> Optional[date]:
        m = re.search(r'd[ií]a\s+(\d{1,2})/(\d{1,2})/(\d{4})', legal)
        legal_day = None
        if m:
            try:
                legal_day = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            except ValueError:
                legal_day = None
        if legal_day and legal_day >= today:
            return legal_day
        if monthly:
            # Legal desactualizado: la promo se repite el día 10 de cada mes
            return next_day(10, today)
        return legal_day  # vencida: el orquestador la descarta
