"""
Scraper de Shell Argentina — Descuentos bancarios

Estructura real de la página (SPA, descubierta 2026-08):
  - Tab buttons: <a role="tab" aria-controls="tab-X"> con etiqueta ("Lunes", "Jueves", etc.)
  - Tab panels: <div role="tabpanel" id="tab-X"> — se populan al hacer click en cada tab
    Cada panel contiene cards <div data-name="PromoSimple">:
      · <h3> = título promocional
      · <p> = descripción con descuento y tope
      · <sup>(N)</sup> = referencia al footnote con T&C completos
  - Footnotes (siempre en DOM): <ol id="_38"> con 16 <li> numerados
    El footnote N tiene las T&C legales completas del promo de referencia (N)

Approach:
  1. Carga inicial → parsear todos los footnotes de #_38 (1..16) + cards del tab activo
  2. Click cada tab restante (js_only) → esperar 2s → parsear cards del panel
  3. Cruzar card (día, título, discount_rápido) con footnote (fechas, exclusiones, T&C full)
  4. Sin async IIFE → sin timeout de Playwright
"""
import re
from typing import List, Dict, Set, Optional


_TABS = {
    'Todos los días':  'tab-todos-los-días',
    'Lunes a Viernes': 'tab-lunes-a-viernes',
    'Lunes':           'tab-lunes',
    'Miércoles':       'tab-miércoles',
    'Jueves':          'tab-jueves',
    'Viernes':         'tab-viernes',
    'Domingo':         'tab-domingo',
}


def _js_click_tab(tab_id: str) -> str:
    """Hace click en el tab con aria-controls=tab_id (síncrono, sin async IIFE)."""
    safe = tab_id.replace("'", "\\'")
    return f"document.querySelector('[aria-controls=\"{safe}\"]')?.click();"


class ShellScraper:
    def __init__(self):
        self.name = 'Shell'
        self.url = 'https://www.shell.com.ar/conductores/descuentos-vigentes.html'

    async def scrape(self) -> List[Dict]:
        try:
            from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, BrowserConfig, CacheMode
        except ImportError:
            print("   ⚠️ crawl4ai no instalado — instalá con: pip install crawl4ai && crawl4ai-setup")
            return []

        from bs4 import BeautifulSoup
        import os

        print(f"\n🔍 Scraping {self.name}...")
        print(f"   🌐 URL: {self.url}")

        SESSION = 'shell_session'
        browser_cfg = BrowserConfig(headless=True, verbose=False)
        all_promotions: List[Dict] = []
        seen: Set[str] = set()

        try:
            async with AsyncWebCrawler(config=browser_cfg) as crawler:

                # ── 1. Carga inicial — tab "Todos los días" activo por default ────
                print(f"\n   📡 Carga inicial...")
                init_cfg = CrawlerRunConfig(
                    session_id=SESSION,
                    wait_for="js:() => document.querySelector('[role=\"tabpanel\"]') !== null",
                    delay_before_return_html=2.5,
                    page_timeout=60000,
                    cache_mode=CacheMode.BYPASS,
                )
                init_result = await crawler.arun(self.url, config=init_cfg)
                if not init_result.success:
                    print(f"   ❌ Error: {init_result.error_message}")
                    return []

                if os.environ.get('DEBUG_SCRAPER'):
                    with open('debug_shell.html', 'w', encoding='utf-8') as f:
                        f.write(init_result.html)
                    print("   💾 HTML guardado: debug_shell.html")

                init_soup = BeautifulSoup(init_result.html, 'html.parser')

                # Parsear todos los footnotes (#_38) — están en DOM desde la carga
                footnotes = self._parse_footnotes(init_soup)
                print(f"   📋 {len(footnotes)} footnotes cargados")

                # Procesar las cards del primer tab activo
                for day_label, tab_id in _TABS.items():
                    if day_label == 'Todos los días':
                        # Ya lo tenemos en el init_result
                        soup = init_soup
                    else:
                        # Click en el tab y esperar re-render
                        tab_cfg = CrawlerRunConfig(
                            session_id=SESSION,
                            js_only=True,
                            js_code=_js_click_tab(tab_id),
                            wait_for=f"js:() => document.getElementById('{tab_id}') && document.getElementById('{tab_id}').querySelector('[data-name=\"PromoSimple\"]') !== null",
                            delay_before_return_html=2.0,
                            page_timeout=15000,
                            cache_mode=CacheMode.BYPASS,
                        )
                        tab_result = await crawler.arun(self.url, config=tab_cfg)
                        if not tab_result.success:
                            print(f"   ⚠️ {day_label}: {tab_result.error_message}")
                            continue
                        soup = BeautifulSoup(tab_result.html, 'html.parser')

                    panel = soup.find(id=tab_id)
                    if not panel:
                        print(f"   ⚠️ Panel no encontrado: {tab_id}")
                        continue

                    cards = panel.find_all(attrs={'data-name': 'PromoSimple'})
                    print(f"\n   📆 {day_label}: {len(cards)} cards")

                    for card in cards:
                        promo = self._parse_card(card, day_label, footnotes)
                        if not promo:
                            continue
                        k = re.sub(r'\s+', '', f"{promo['bank']}{promo['wallet']}{promo['discount']}{promo['valid_days']}").lower()
                        if k in seen:
                            continue
                        seen.add(k)
                        all_promotions.append(promo)
                        entity = promo['bank'] or promo['wallet'] or '?'
                        print(f"      + {entity:30s} | {promo['discount'] or '—':6s} | tope: {promo['tope'] or '—'}")

        except Exception as e:
            print(f"\n   ❌ Error: {e}")
            import traceback
            traceback.print_exc()

        print(f"\n✅ {self.name}: {len(all_promotions)} promociones")
        return all_promotions

    # ─────────────────────────────────────────────────────────────────────────
    # Parsing
    # ─────────────────────────────────────────────────────────────────────────

    def _parse_footnotes(self, soup) -> Dict[int, str]:
        """Parsea todos los <li> del ol#_38 → {1: text, 2: text, ...}"""
        footnotes = {}
        for ol in soup.find_all(['ol', 'ul']):
            lis = ol.find_all('li', recursive=False)
            if len(lis) < 5:
                continue
            # Verificar que tiene texto sustancial
            sample_text = lis[0].get_text(' ', strip=True) if lis else ''
            if len(sample_text) < 40:
                continue
            for i, li in enumerate(lis, 1):
                # Limpiar style/svg del li
                import copy
                node = copy.copy(li)
                for tag in node.find_all(['style', 'svg', 'script']):
                    tag.decompose()
                text = re.sub(r'\s+', ' ', node.get_text(' ', strip=True)).strip()
                if text:
                    footnotes[i] = text
            if footnotes:
                break
        return footnotes

    def _parse_card(self, card, day_label: str, footnotes: Dict[int, str]) -> Optional[Dict]:
        """Parsea una PromoSimple card y la cruza con su footnote."""
        # Título
        h3 = card.find('h3')
        title = h3.get_text(' ', strip=True) if h3 else ''

        # Imagen
        img = card.find('img')
        img_url = ''
        img_alt = ''
        if img:
            img_url = img.get('src', '') or img.get('data-src', '') or ''
            img_alt = img.get('alt', '')

        # Número de footnote: <sup>(N)</sup>
        sup = card.find('sup')
        footnote_num = 0
        if sup:
            m = re.search(r'\((\d+)\)', sup.get_text())
            if m:
                footnote_num = int(m.group(1))

        # Texto de la card (sin el sup)
        if sup:
            sup.decompose()
        for tag in card.find_all(['style', 'svg', 'script']):
            tag.decompose()
        card_text = re.sub(r'\s+', ' ', card.get_text(' ', strip=True)).strip()

        # Footnote legal (si existe)
        legal_text = footnotes.get(footnote_num, '')

        # Fuente principal para extractores: card_text + legal_text
        full_text = f"{card_text} {legal_text}"

        discount   = self._extract_discount(full_text)
        tope       = self._extract_tope(full_text)
        bank       = self._identify_bank(full_text) or self._identify_bank(img_alt)
        wallet     = self._identify_wallet(full_text) or self._identify_wallet(img_alt)
        card_type  = self._identify_card_type(full_text)
        valid_from, valid_until = self._extract_dates(legal_text)
        excl       = self._extract_exclusion(legal_text)

        if not title and not discount and not bank and not wallet:
            return None

        return {
            'supermarket':  self.name,
            'title':        title or card_text[:80],
            'description':  card_text[:300],
            'discount':     discount,
            'bank':         bank,
            'wallet':       wallet,
            'card_type':    card_type,
            'tope':         tope,
            'valid_days':   day_label,
            'valid_from':   valid_from,
            'valid_until':  valid_until,
            'exclusions':   excl,
            'terms_raw':    legal_text[:1500],
            'image_url':    img_url,
            'footnote_num': footnote_num,
            'url':          self.url,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Extractores de texto
    # ─────────────────────────────────────────────────────────────────────────

    def _extract_discount(self, text: str) -> str:
        m = re.search(r'(\d{1,3})\s*%\s*de\s*(?:descuento|ahorro)', text, re.I)
        if m:
            return f"{m.group(1)}%"
        m = re.search(r'ahorrás?\s+un\s+(\d{1,3})\s*%', text, re.I)
        if m:
            return f"{m.group(1)}%"
        m = re.search(r'(\d{1,3})\s*%\s+(?:sobre\s+precio|en\s+la\s+carga|en\s+combustible|en\s+cargas)', text, re.I)
        if m:
            return f"{m.group(1)}%"
        return ''

    def _extract_tope(self, text: str) -> str:
        if re.search(r'[Ss]in\s+[Tt]ope', text):
            return 'Sin tope'
        # [^.]* stops at sentence boundary; handles "tope de descuento de $4.500"
        m = re.search(r'tope\b[^.]*\$\s*([\d.]+)', text, re.I)
        if m:
            return f"${m.group(1).rstrip('.')}"
        return ''

    def _extract_dates(self, text: str):
        date_pat = r'\d{1,2}[/\-]\d{1,2}(?:[/\-]\d{2,4})?'
        range_m = re.search(r'del?\s+(' + date_pat + r')\s+al\s+(' + date_pat + r')', text, re.I)
        if range_m:
            return range_m.group(1), range_m.group(2)
        mf = re.search(r'(?:desde|del?\s+el?)\s+(' + date_pat + r')', text, re.I)
        mu = re.search(r'(?:hasta|al)\s+(' + date_pat + r')', text, re.I)
        return (mf.group(1) if mf else ''), (mu.group(1) if mu else '')

    def _extract_exclusion(self, text: str) -> str:
        m = re.search(r'(?:no\s+acumulable|no\s+combinable)[^.]{0,120}\.?', text, re.I)
        return m.group(0).strip() if m else ''

    # ─────────────────────────────────────────────────────────────────────────
    # Identificación de entidades
    # ─────────────────────────────────────────────────────────────────────────

    def _identify_bank(self, text: str) -> str:
        t = text.upper()
        for pattern, name in [
            (r'BANCO\s+CIUDAD|CIUDAD\s+DE\s+BUENOS\s+AIRES', 'Banco Ciudad'),
            (r'BANCO\s+GALICIA|GALICIA\b', 'Banco Galicia'),
            (r'BANCO\s+COMAFI|COMAFI\b', 'Banco Comafi'),
            (r'BANCO\s+SUPERVIELLE|SUPERVIELLE\b', 'Banco Supervielle'),
            (r'BANCO\s+PATAGONIA|PATAGONIA\b', 'Banco Patagonia'),
            (r'BANCO\s+MACRO|MACRO\b', 'Banco Macro'),
            (r'SANTANDER', 'Banco Santander'),
            (r'BBVA|FRANC[EÉ]S', 'BBVA'),
            (r'ICBC', 'ICBC'),
            (r'HSBC', 'HSBC'),
            (r'CREDICOOP', 'Banco Credicoop'),
            (r'HIPOTECARIO', 'Banco Hipotecario'),
            (r'COLUMBIA', 'Banco Columbia'),
            (r'PROVINCIA|BAPRO', 'Banco Provincia'),
            (r'NACI[OÓ]N|BNA\b', 'Banco Nación'),
            (r'NARANJA', 'Naranja X'),
            (r'SERVICIOS\s+DE\s+CUOTAS\s*SA|TARSHOP', 'Tarshop/Servicios'),
        ]:
            if re.search(pattern, t):
                return name
        return ''

    def _identify_wallet(self, text: str) -> str:
        t = text.upper()
        found = []
        for pattern, name in [
            (r'SHELL\s*BOX', 'Shell Box'),
            (r'TARJETA\s*365|CLUB\s*CLAR[IÍ]N', 'Club Clarín/365'),
            (r'CLUB\s+EASY', 'Club Easy'),
            (r'JUMBO\+|VEA\s+AHORRO', 'Jumbo+/Vea Ahorro'),
            (r'MERCADO\s*PAGO', 'Mercado Pago'),
            (r'PERSONAL\s*PAY', 'Personal Pay'),
            (r'CUENTA\s*DNI', 'Cuenta DNI'),
            (r'\bUAL[AÁ]\b', 'Ualá'),
            (r'\bMODO\b', 'MODO'),
            (r'\bPREX\b', 'Prex'),
        ]:
            if re.search(pattern, t):
                found.append(name)
        if not found:
            return ''
        non_shell = [n for n in found if n != 'Shell Box']
        if non_shell and 'Shell Box' in found:
            return f"Shell Box + {' + '.join(non_shell)}"
        return found[0]

    def _identify_card_type(self, text: str) -> str:
        t = text.lower()
        parts = []
        if re.search(r'tarjeta[s]?\s+(?:de\s+)?cr[eé]dito|cr[eé]dito\s+(?:visa|master)', t):
            parts.append('Crédito')
        if re.search(r'tarjeta[s]?\s+(?:de\s+)?d[eé]bito|d[eé]bito\s+(?:visa|master)', t):
            parts.append('Débito')
        if re.search(r'tarjeta\s+prepaga|prepag', t):
            parts.append('Prepaga')
        return '/'.join(parts)
