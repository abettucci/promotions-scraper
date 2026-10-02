"""
Banco Nación — Descuentos YPF (aggregator)
URL: https://www.bna.com.ar/Personas/DescuentosYPromociones/4486/ypf/

HTML server-side estático: cada promo es un div.interna-promo con
  <h2>YPF</h2> <p class="descuento">20% de descuento</p>
  <p class="vigencia">Del 1-3-2026 al 30-9-2026</p>
y el cuerpo con medio de pago y "Tope de reintegro: hasta $10.000 por cliente por mes".
Se parsea con regex, sin navegador ni IA. Si la vigencia ya terminó la devolvemos
igual con su valid_until y el orquestador la descarta.
"""
import asyncio
import html as html_lib
import re
from typing import Dict, List, Optional


_URL = 'https://www.bna.com.ar/Personas/DescuentosYPromociones/4486/ypf/'

_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'es-AR,es;q=0.9',
}

_BRANDS = [('YPF', r'\bypf\b'), ('Shell', r'\bshell\b'), ('Axion', r'\baxion\b'), ('Puma Energy', r'\bpuma\b')]
_DAYS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
_PERIODS = {'mes': 'mensual', 'semana': 'semanal', 'día': 'diario', 'dia': 'diario'}


def _text(raw: str) -> str:
    t = re.sub(r'<br\s*/?>|</br>', ' ', raw or '', flags=re.I)
    t = re.sub(r'<[^>]+>', ' ', t)
    t = html_lib.unescape(t).replace('\xa0', ' ')
    return re.sub(r'\s+', ' ', t).strip()


def _iso(d: str, m: str, y: str) -> str:
    return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"


class BnaScraper:
    def __init__(self, default_brand: str = 'YPF'):
        self.name = 'Banco Nación'
        self.url = _URL
        self.default_brand = default_brand

    async def scrape(self, page=None) -> List[Dict]:
        import requests

        print(f"🔍 Scraping {self.name} (HTML estático)...")
        loop = asyncio.get_event_loop()
        try:
            resp = await loop.run_in_executor(
                None, lambda: requests.get(self.url, headers=_HEADERS, timeout=30)
            )
            resp.raise_for_status()
            resp.encoding = resp.encoding or 'utf-8'
        except Exception as e:
            print(f"   ❌ Error fetching {self.url}: {e}")
            return []

        promotions = self.parse_html(resp.text)
        for p in promotions:
            print(f"   + {p['title']} | {p['valid_from']} → {p['valid_until']} | {p['tope']}")
        print(f"✅ {self.name}: {len(promotions)} promociones")
        return promotions

    def parse_html(self, html: str) -> List[Dict]:
        promotions = []
        # Cada bloque arranca en div.interna-promo y termina en el legal de la página
        blocks = re.split(r'<div class="interna-promo"', html)[1:]
        for i, block in enumerate(blocks):
            block = re.split(r'<div class="legal-descuentos"', block)[0]
            promo = self._parse_block(block, i)
            if promo:
                promotions.append(promo)
        return promotions

    def _parse_block(self, block: str, idx: int) -> Optional[Dict]:
        h2 = re.search(r'<h2[^>]*>(.*?)</h2>', block, re.S | re.I)
        desc = re.search(r'class="descuento"[^>]*>(.*?)</p>', block, re.S | re.I)
        vig = re.search(r'class="vigencia"[^>]*>(.*?)</p>', block, re.S | re.I)
        body = _text('<div ' + block)
        merchant = _text(h2.group(1)) if h2 else ''

        pct = re.search(r'(\d+)\s*%', _text(desc.group(1)) if desc else body)
        if not pct:
            return None
        discount = f"{pct.group(1)}%"

        valid_from = valid_until = None
        dates = re.search(r'(\d{1,2})-(\d{1,2})-(\d{4})\s+al\s+(\d{1,2})-(\d{1,2})-(\d{4})',
                          _text(vig.group(1)) if vig else body)
        if dates:
            g = dates.groups()
            valid_from, valid_until = _iso(*g[:3]), _iso(*g[3:])

        brands = [b for b, pat in _BRANDS if re.search(pat, merchant, re.I)] or [self.default_brand]

        tope = None
        tm = re.search(r'Tope de reintegro:?\s*(?:hasta\s*)?\$\s?([\d.]+)(?:[^.]*?por (mes|semana|d[ií]a))?', body, re.I)
        if tm:
            tope = f"${tm.group(1).rstrip('.')}" + (f" {_PERIODS[tm.group(2).lower()]}" if tm.group(2) else '')

        low = body.lower()
        days = [d for d in _DAYS if re.search(rf'\b{d.lower()}(?:es|s)?\b', low)]
        if 'todos los días' in low or 'todos los dias' in low:
            days = []
            valid_days = 'Todos los días'
        else:
            valid_days = ', '.join(days) or None

        card_types = [t for t, k in (('Crédito', 'crédito'), ('Débito', 'débito')) if k in low]
        via_modo = 'modo' in low
        networks = [n for n in ('Visa', 'Mastercard') if n.lower() in low]
        payment = ('QR MODO BNA+' if via_modo else 'Tarjetas Banco Nación') + \
            (f" con {' y '.join(networks)}" if networks else '')

        title = f"Banco Nación {discount} en {' y '.join(brands)}" + (f" - {valid_days}" if valid_days else '')
        return {
            'title': title,
            'discount': discount,
            'bank': 'Banco Nación',
            'wallet': 'MODO' if via_modo else None,
            'card_type': ', '.join(card_types) or None,
            'payment_method': payment,
            'store_types': 'Tiendas',
            'valid_days': valid_days,
            'valid_from': valid_from,
            'valid_until': valid_until,
            'tope': tope,
            'min_purchase': None,
            'terms_raw': body,
            'source_id': f"bna:4486:{idx}:{valid_from or ''}",
            'url': self.url,
            'merchant_brands': brands,
            'merchant_category': 'fuel',
        }
