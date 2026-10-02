"""
Scraper de Puma Energy — listado + páginas individuales.

El sitio pumaenergyarg.com.ar/promociones sirve HTML estático (sin JavaScript).
No se necesita browser headless ni AI Vision.

Flujo:
  1. GET /promociones  → BeautifulSoup extrae todos los href /promocion/ID
  2. Para cada ID, GET /promocion/ID en paralelo via asyncio.to_thread + requests
  3. Parsear titular (p.heading), detalle (p.details), imagen, link T&C
  4. Extraer banco, billetera, descuento, días, fechas, tramos de tope y tipo
     de tarjeta del detalle; el título se normaliza a "<Entidad> <beneficio>
     [tramo] - <días>" (el titular del sitio es poco legible: "Promo BNA | 20% off").

No usa Gemini/Claude Vision — cero coste de AI.
"""

import asyncio
import re
from typing import List, Dict, Optional

import requests
from bs4 import BeautifulSoup

from .base_scraper import BaseScraper
from fuel_conditions import extract_fuel_conditions
from .shell_scraper import _BANKS, _WEEKDAYS, _money, _period, parse_dates

BASE_URL = 'https://pumaenergyarg.com.ar'
_LISTING_URL = f'{BASE_URL}/promociones'
_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    ),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'es-AR,es;q=0.9',
}
_TIMEOUT = 30
_MAX_WORKERS = 5  # max parallel detail-page fetches


class PumaScraper(BaseScraper):
    def __init__(self):
        super().__init__(name='Puma Energy', url=_LISTING_URL)

    async def scrape(self, page=None) -> List[Dict]:
        """
        page aceptado por compatibilidad con BaseScraper pero no se usa.
        Puma Energy sirve HTML estático — no requiere Playwright ni Crawl4AI.
        """
        print(f"🔍 Scraping {self.name}...")
        print(f"   🌐 URL: {self.url}")

        # 1. Obtener listado de IDs
        listing_html = await asyncio.to_thread(self._fetch, self.url)
        if not listing_html:
            print(f"   ❌ No se pudo obtener el listado de promociones")
            return []

        promo_ids = self._extract_promo_ids(listing_html)
        if not promo_ids:
            print(f"   ⚠️  No se encontraron IDs de promos en el listado")
            return []

        print(f"   🔢 Encontradas {len(promo_ids)} promos: {promo_ids}")

        # 2. Scrapear páginas de detalle en paralelo (limitado a _MAX_WORKERS)
        sem = asyncio.Semaphore(_MAX_WORKERS)

        async def _bounded_fetch(pid: int) -> Optional[Dict]:
            async with sem:
                url = f"{BASE_URL}/promocion/{pid}"
                html = await asyncio.to_thread(self._fetch, url)
                if not html:
                    return None
                return self._parse_promo_page(html, url)

        results = await asyncio.gather(
            *[_bounded_fetch(pid) for pid in promo_ids],
            return_exceptions=True,
        )

        promos: List[Dict] = []
        for r in results:
            if isinstance(r, Exception):
                print(f"   ⚠️  Error al procesar promo: {r}")
            elif r is not None:
                promos.append(r)

        print(f"✅ {self.name}: {len(promos)} promociones encontradas")
        return promos

    # ─────────────────────────────────────────────────────────────────────────
    # HTTP helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _fetch(self, url: str) -> str:
        """Realiza un GET síncrono y retorna el HTML como string (o '' si falla)."""
        try:
            r = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
            r.raise_for_status()
            return r.text
        except requests.RequestException as e:
            print(f"   ❌ Error al obtener {url}: {e}")
            return ''

    def _extract_promo_ids(self, html: str) -> List[int]:
        """Extrae los IDs únicos de /promocion/ID del listado HTML."""
        soup = BeautifulSoup(html, 'html.parser')
        ids: set = set()
        for a in soup.select('div.benefits-container a[href]'):
            m = re.search(r'/promocion/(\d+)', a.get('href', ''))
            if m:
                ids.add(int(m.group(1)))
        return sorted(ids)

    # ─────────────────────────────────────────────────────────────────────────
    # Parsing
    # ─────────────────────────────────────────────────────────────────────────

    def _parse_promo_page(self, html: str, url: str) -> Optional[Dict]:
        """
        Parsea una página /promocion/ID y retorna un dict normalizado.
        Retorna None si no hay título válido en la página.
        """
        soup = BeautifulSoup(html, 'html.parser')

        # Título — buscar dentro de light-bg para evitar el nav
        heading = soup.select_one('div.light-bg p.heading') or soup.find('p', class_='heading')
        if not heading:
            return None
        heading_text = self.clean_text(heading.get_text(' ', strip=True))
        if not heading_text:
            return None

        # Descripción / detalle (puede tener HTML anidado con <span>)
        details_el = soup.select_one('div.light-bg p.details') or soup.find('p', class_='details')
        details = self.clean_text(details_el.get_text(' ', strip=True)) if details_el else ''

        # Imagen de alta resolución
        img_el = soup.select_one('div.light-bg img.img-fluid')
        image_url = ''
        if img_el:
            src = img_el.get('src', '') or ''
            image_url = src if src.startswith('http') else f"{BASE_URL}{src}"

        # Link a Términos y Condiciones (PDF) — puede haber "Ver estaciones" y "Ver T&C"
        terms_url = ''
        for a in soup.select('a.stations[href]'):
            href = a.get('href', '') or ''
            href = href if href.startswith('http') else f"{BASE_URL}{href}"
            if 'rminos' in a.get_text() or not terms_url:
                terms_url = href

        return self.build_promo(heading_text, details, url, image_url, terms_url)

    def build_promo(self, heading: str, details: str, url: str,
                    image_url: str = '', terms_url: str = '') -> Optional[Dict]:
        """Arma la promo normalizada a partir del titular y el detalle."""
        full_text = f"{heading} {details}"
        upper = full_text.upper()

        # ── Entidad ──────────────────────────────────────────────────────────
        bank = None
        for pattern, name in _BANKS:
            if re.search(pattern, upper):
                bank = name
                break
        wallet = None
        payment_method = None
        if re.search(r'PUMA\s+PRIS', upper):
            wallet, payment_method = 'Puma Pris', 'App Puma Pris'
        elif re.search(r'\bMODO\b', upper):
            wallet = 'MODO'
            payment_method = 'MODO BNA+' if re.search(r'BNA\s*\+', upper) else 'QR MODO'
        card_label = None
        m = re.search(r'tarjeta\s+de\s+cr[eé]dito\s+(visa\s+\w+)', details, re.I)
        if m and not bank:
            # Tarjetas co-branded sin banco (p. ej. "VISA AL2")
            card_label = ' '.join(w if w.isupper() or any(c.isdigit() for c in w) else w.capitalize()
                                  for w in m.group(1).split())
            card_label = re.sub(r'(?i)^visa', 'Visa', card_label)
            payment_method = f"Tarjeta de Crédito {card_label}"

        discount = self._discount(details or heading)
        if not discount:
            return None
        valid_days = self._extract_days(full_text) or 'Todos los días'
        dates = parse_dates(details)
        card_type = self._extract_card_type(details)
        tope = self._extract_tope(details)
        qualifier = self._qualifier(heading, bank)

        entity = bank or wallet or card_label or heading
        title = f"{entity} {discount.split(' (')[0]}"
        if qualifier:
            title += f" {qualifier}"
        title += f" - {valid_days}"

        requirements, exclusions = extract_fuel_conditions(full_text)
        if qualifier:
            requirements.append(f"Clientes {qualifier}")
        pid = re.search(r'/promocion/(\d+)', url or '')
        return {
            'title':          title,
            'description':    heading,
            'discount':       discount,
            'bank':           bank,
            'wallet':         wallet,
            'card_type':      card_type,
            'payment_method': payment_method,
            'store_types':    None,
            'valid_days':     valid_days,
            'url':            url,
            'image_url':      image_url,
            'terms_raw':      details or heading,
            'terms_url':      terms_url,
            'tope':           tope,
            'min_purchase':   self._extract_min_purchase(full_text),
            'exclusions':     ' | '.join(exclusions),
            'requirements':   ' | '.join(requirements),
            'valid_from':     dates[0],
            'valid_until':    dates[1],
            'source_id':      f"puma:{pid.group(1)}" if pid else f"puma:{heading.lower()}",
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Text extraction helpers (Puma-specific patterns)
    # ─────────────────────────────────────────────────────────────────────────

    def _discount(self, text: str) -> str:
        """'20%'; si hay % por producto distinto → '5% (10% Ion Diesel)'."""
        if not text:
            return ''
        products = re.findall(r'([A-Z][\w ]*?)\s*\((\d{1,2})\s*%\s*de\s+descuento', text)
        if products:
            pcts = [p for _, p in products]
            base = max(pcts, key=lambda x: (pcts.count(x), -pcts.index(x)))
            extras = [f"{p}% {name.strip()}" for name, p in products if p != base]
            return f"{base}%" + (f" ({', '.join(extras)})" if extras else '')
        m = re.search(r'(\d{1,2})\s*%\s*(?:de\s+)?(?:descuento|reintegro|cashback|off)', text, re.I) \
            or re.search(r'(\d{1,2})\s*%', text)
        return f"{m.group(1)}%" if m else ''

    def _extract_days(self, text: str) -> Optional[str]:
        """'todos los viernes' → 'Viernes'; 'todos los días' → 'Todos los días'."""
        if not text:
            return None
        low = text.lower()
        if re.search(r'todos\s+los\s+d[íi]as', low):
            return 'Todos los días'
        if re.search(r'de\s+lunes\s+a\s+viernes', low):
            return 'Lunes, Martes, Miércoles, Jueves, Viernes'
        found = []
        for wd in _WEEKDAYS:
            stem = wd.lower().replace('é', '[eé]').replace('á', '[aá]')
            if re.search(r'\b' + stem, low):
                found.append(wd)
        return ', '.join(found) or None

    def _extract_card_type(self, text: str) -> Optional[str]:
        """Detecta si la promo aplica a Débito, Crédito o ambas."""
        tl = (text or '').lower()
        has_debito = bool(re.search(r'd[eé]bito', tl))
        has_credito = bool(re.search(r'cr[eé]dito', tl))
        if has_debito and has_credito:
            return 'Crédito, Débito'
        if has_debito:
            return 'Débito'
        if has_credito:
            return 'Crédito'
        return None

    def _extract_tope(self, text: str) -> Optional[str]:
        """Tope de reintegro: monto, tramos por cartera, litros o por producto."""
        if not text:
            return None
        # Tramos: "tope de $5.000 semanal por cliente si sos de Cartera General, ..."
        tiers = re.findall(
            r'tope\s+de\s+\$\s*([\d.]+)\s*(semanal|mensual)?[^,.$]*?si\s+sos\s+(?:de\s+|cliente\s+)?(?:cartera\s+)?([^,.]+)',
            text, re.I)
        if len(tiers) > 1:
            parts = []
            for amount, period, who in tiers:
                who = ' '.join(w.capitalize() if w.isupper() else w for w in who.split())
                parts.append(f"{_money(amount)} {period.lower()}".strip() + f" ({who})")
            return '; '.join(parts)
        # Por producto: "Diesel (5% de descuento o 200lts o 3 transacciones), ..."
        prods = re.findall(r'([A-Z][\w ]*?)\s*\(\d{1,2}\s*%\s*de\s+descuento\s+o\s+(\d+)\s*lts?\s+o\s+(\d+)\s+transacciones\)', text)
        if prods:
            items = ', '.join(f"{name.strip()} {lts} L" for name, lts, _ in prods)
            return f"Por producto: {items} (máx. {prods[0][2]} transacciones)"
        m = re.search(r'tope[^$.]{0,40}?hasta\s+(\d+)\s*litros(?:\s+por\s+(\w+))?', text, re.I)
        if m:
            return f"{m.group(1)} L" + (f" por {m.group(2)}" if m.group(2) else '')
        m = re.search(r'tope[^$]{0,40}?\$\s*([\d.]+)\s*(semanal|mensual|por\s+semana|por\s+mes)?', text, re.I)
        if m:
            period = _period(m.group(2) or '')
            return f"{_money(m.group(1))} {period}".strip()
        return None

    def _qualifier(self, heading: str, bank: Optional[str]) -> str:
        """'PATAGONIA - PLUS PLAN SUELDO' → 'Plus Plan Sueldo' (tramo del banco)."""
        m = re.match(r'^[^-|]+-\s*(.+)$', heading or '')
        if not m or not bank:
            return ''
        return ' '.join(w.capitalize() for w in m.group(1).split())

    def _extract_min_purchase(self, text: str) -> Optional[str]:
        """Extrae el pago/compra mínima requerida."""
        if not text:
            return None
        m = re.search(r'(?:pago|compra)\s+m[íi]nim[ao]\s+de\s+\$\s*([\d.,]+)', text, re.IGNORECASE)
        return _money(m.group(1)) if m else None
