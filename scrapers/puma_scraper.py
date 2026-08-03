"""
Scraper de Puma Energy — listado + páginas individuales.

El sitio pumaenergyarg.com.ar/promociones sirve HTML estático (sin JavaScript).
No se necesita browser headless ni AI Vision.

Flujo:
  1. GET /promociones  → BeautifulSoup extrae todos los href /promocion/ID
  2. Para cada ID, GET /promocion/ID en paralelo via asyncio.to_thread + requests
  3. Parsear title (p.heading), descripción (p.details), imagen, link T&C
  4. Extraer banco, billetera, descuento, días y fechas del texto libre

No usa Gemini/Claude Vision — cero coste de AI.
"""

import asyncio
import re
from typing import List, Dict, Optional

import requests
from bs4 import BeautifulSoup

from .base_scraper import BaseScraper

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
        heading = soup.select_one('div.light-bg p.heading')
        if not heading:
            heading = soup.find('p', class_='heading')
        if not heading:
            return None
        title = self.clean_text(heading.get_text())
        if not title:
            return None

        # Descripción / detalle (puede tener HTML anidado con <span>)
        details_el = soup.select_one('div.light-bg p.details')
        if not details_el:
            details_el = soup.find('p', class_='details')
        details_text = ''
        if details_el:
            details_text = self.clean_text(details_el.get_text(' ', strip=True))

        # Imagen de alta resolución
        img_el = soup.select_one('div.light-bg img.img-fluid')
        image_url = ''
        if img_el:
            src = img_el.get('src', '') or ''
            image_url = src if src.startswith('http') else f"{BASE_URL}{src}"

        # Link a Términos y Condiciones (a.stations → PDF)
        terms_link = soup.find('a', class_='stations')
        terms_url = ''
        if terms_link:
            href = terms_link.get('href', '') or ''
            terms_url = href if href.startswith('http') else f"{BASE_URL}{href}"

        # Extracción de entidades del texto completo
        full_text = f"{title} {details_text}"

        bank         = self.extract_bank(full_text)
        wallet       = self.extract_wallet(full_text)
        discount     = self._extract_discount_puma(full_text)
        valid_days   = self._extract_days(full_text)
        card_type    = self._extract_card_type(full_text)
        tope         = self._extract_tope(full_text)
        min_purchase = self._extract_min_purchase(full_text)
        exclusions   = self._extract_exclusions(full_text)
        dates        = self.extract_dates(details_text)

        return {
            'title':          title,
            'discount':       discount,
            'bank':           bank,
            'wallet':         wallet,
            'card_type':      card_type,
            'payment_method': None,
            'store_types':    None,
            'valid_days':     valid_days,
            'url':            url,
            'image_url':      image_url,
            'terms_raw':      details_text,
            'terms_url':      terms_url,
            'tope':           tope,
            'min_purchase':   min_purchase,
            'exclusions':     exclusions,
            'requirements':   None,
            'valid_from':     dates.get('valid_from'),
            'valid_until':    dates.get('valid_until'),
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Text extraction helpers (Puma-specific patterns)
    # ─────────────────────────────────────────────────────────────────────────

    def _extract_discount_puma(self, text: str) -> str:
        """Extrae porcentaje de descuento/reintegro del texto."""
        if not text:
            return ''
        # "20% de descuento", "10% de reintegro", "10% cashback", "5% off"
        m = re.search(
            r'(\d+)\s*%\s*(?:de\s+)?(?:descuento|reintegro|cashback|off)',
            text, re.IGNORECASE
        )
        if m:
            return f"{m.group(1)}%"
        # porcentaje genérico
        m = re.search(r'(\d+)\s*%', text)
        if m:
            return f"{m.group(1)}%"
        return self.extract_discount(text)

    def _extract_days(self, text: str) -> Optional[str]:
        """Extrae los días de validez del texto de la promo."""
        if not text:
            return None
        patterns = [
            r'todos\s+los\s+d[íi]as',
            r'de\s+lunes\s+a\s+viernes',
            r'todos\s+los\s+(?:lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bados?|domingos?)',
            r'los\s+(?:lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bados?\s+y\s+domingos?)',
            (r'(?:lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bados?)'
             r'\s+y\s+'
             r'(?:lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bados?|domingos?)'),
        ]
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                return self.clean_text(m.group(0))
        return None

    def _extract_card_type(self, text: str) -> Optional[str]:
        """Detecta si la promo aplica a Débito, Crédito o ambas."""
        tl = text.lower()
        has_debito  = 'débito' in tl or 'debito' in tl
        has_credito = 'crédito' in tl or 'credito' in tl
        if has_debito and has_credito:
            return 'Crédito y Débito'
        if has_debito:
            return 'Débito'
        if has_credito:
            return 'Crédito'
        return None

    def _extract_tope(self, text: str) -> Optional[str]:
        """Extrae el tope máximo de reintegro/descuento."""
        if not text:
            return None
        m = re.search(r'tope\s+de\s+\$\s*([\d.,]+)', text, re.IGNORECASE)
        if m:
            return f"${m.group(1)}"
        return None

    def _extract_min_purchase(self, text: str) -> Optional[str]:
        """Extrae el pago/compra mínima requerida."""
        if not text:
            return None
        m = re.search(r'pago\s+m[íi]nimo\s+de\s+\$\s*([\d.,]+)', text, re.IGNORECASE)
        if m:
            return f"${m.group(1)}"
        m = re.search(r'compra\s+m[íi]nima\s+de\s+\$\s*([\d.,]+)', text, re.IGNORECASE)
        if m:
            return f"${m.group(1)}"
        return None

    def _extract_exclusions(self, text: str) -> Optional[str]:
        """Extrae texto de no-acumulabilidad o exclusiones."""
        if not text:
            return None
        m = re.search(r'(no\s+acumulable\s+con\s+[^.]+)', text, re.IGNORECASE)
        if m:
            return self.clean_text(m.group(0))
        return None
