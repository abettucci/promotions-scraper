#!/usr/bin/env python3
"""
Scraper de Supermercados Día - Promociones Bancarias

Estructura VTEX de DIA:
  - Cards: div.diaio-custom-bank-promotions-0-x-card_detail + banco como clase CSS extra
  - Descuento: solo visible en imagen Y en el modal que abre "Ver Legales"
  - Días: los días válidos están en el texto legal del modal

Approach Crawl4AI (sin async IIFE → no timeout de Playwright):
  1. Carga inicial → esperar cards → JS síncrono inyecta metadata de cards visibles
  2. Por cada card: js_only click "Ver Legales" (index puntual) → delay 2s → parsear modal
  3. js_only ESC/close → siguiente card
  4. Extraer discount + días desde el texto del modal
"""
import re
import os
import json
from typing import List, Dict, Set


_CSS_CARD = 'diaio-custom-bank-promotions-0-x-card_detail'

# JS síncrono que inyecta metadata de cards visibles en el DOM
# Sin async/await → nunca hace timeout en page.evaluate()
_JS_INJECT_METADATA = f"""
(() => {{
    const CSS_CARD = '{_CSS_CARD}';
    const cards = Array.from(document.querySelectorAll('.' + CSS_CARD))
        .filter(d => !Array.from(d.classList).some(c => c.includes('__')))
        .filter(d => getComputedStyle(d).display !== 'none'
                  && getComputedStyle(d).visibility !== 'hidden'
                  && d.getBoundingClientRect().width > 0);

    const meta = cards.map((d, i) => {{
        const cls = Array.from(d.classList).filter(c => c !== CSS_CARD);
        const img = d.querySelector('img');
        const channels = Array.from(d.querySelectorAll('span'))
            .map(s => s.textContent.trim())
            .filter(t => t === 'ONLINE' || t === 'TIENDAS');
        return {{
            dom_idx: Array.from(document.querySelectorAll('.' + CSS_CARD))
                .filter(x => !Array.from(x.classList).some(c => c.includes('__')))
                .indexOf(d),
            bank_cls: cls.join(' '),
            channels: [...new Set(channels)],
            img_src: img ? (img.src || img.dataset.src || '') : ''
        }};
    }});

    let el = document.getElementById('__dia_meta');
    if (!el) {{
        el = document.createElement('div');
        el.id = '__dia_meta';
        el.style.display = 'none';
        document.body.appendChild(el);
    }}
    el.textContent = JSON.stringify(meta);
    return meta.length;
}})()
"""

def _js_click_ver_legales(dom_idx: int) -> str:
    """Clickea 'Ver Legales' de la card con posición dom_idx (entre todas las cards top-level)."""
    return f"""
        (() => {{
            const cards = Array.from(document.querySelectorAll('.{_CSS_CARD}'))
                .filter(d => !Array.from(d.classList).some(c => c.includes('__')));
            const btn = cards[{dom_idx}]?.querySelector('[class*="card_detail__terms"]');
            if (btn) {{ btn.click(); return true; }}
            return false;
        }})()
    """

_JS_CLOSE_MODAL = """
    (() => {
        const sels = [
            '[class*="closeButton"]',
            '[aria-label="Close"]',
            '[aria-label="Cerrar"]',
            '[data-testid="modal-close"]',
            '[class*="modal__close"]',
            '[class*="overlayClose"]'
        ];
        for (const sel of sels) {
            const el = document.querySelector(sel);
            if (el) { el.click(); return 'clicked'; }
        }
        document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
        return 'esc';
    })()
"""


class DiaScraper:
    def __init__(self):
        self.name = 'Supermercados Día'
        self.base_url = 'https://diaonline.supermercadosdia.com.ar/medios-de-pago-y-promociones'

    async def scrape(self) -> List[Dict]:
        try:
            from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, BrowserConfig, CacheMode
        except ImportError:
            print("   ⚠️ crawl4ai no instalado — instalá con: pip install crawl4ai && crawl4ai-setup")
            return []

        from bs4 import BeautifulSoup

        print(f"\n🔍 Scraping {self.name}...")
        print(f"   🌐 URL: {self.base_url}")

        SESSION = 'dia_session'
        browser_cfg = BrowserConfig(headless=True, verbose=False)
        all_promotions: List[Dict] = []

        try:
            async with AsyncWebCrawler(config=browser_cfg) as crawler:

                # ── 1. Carga inicial ──────────────────────────────────────────────
                print(f"\n   📡 Carga inicial...")
                init_cfg = CrawlerRunConfig(
                    session_id=SESSION,
                    wait_for=(
                        "js:() => document.querySelectorAll("
                        "'[class*=\"card_detail__terms\"]').length >= 3"
                    ),
                    delay_before_return_html=1.5,
                    page_timeout=60000,
                    cache_mode=CacheMode.BYPASS,
                )
                init_result = await crawler.arun(self.base_url, config=init_cfg)
                if not init_result.success:
                    print(f"   ❌ Error: {init_result.error_message}")
                    return []

                # ── 2. Click "Todos" + inyectar metadata (vista completa) ─────────
                # La página puede defaultear al día de hoy — "Todos" muestra las 23 cards
                print(f"   📋 Seleccionando vista 'Todos' e inyectando metadata...")
                todos_cfg = CrawlerRunConfig(
                    session_id=SESSION,
                    js_only=True,
                    js_code="""
                        (() => {
                            const btns = Array.from(
                                document.querySelectorAll('button[class*="days_fi"]')
                            );
                            const btn = btns.find(b => b.textContent.trim() === 'Todos');
                            if (btn) btn.click();
                        })();
                    """,
                    delay_before_return_html=1.8,
                    cache_mode=CacheMode.BYPASS,
                )
                await crawler.arun(self.base_url, config=todos_cfg)

                # Ahora inyectar metadata de cards visibles
                meta_cfg = CrawlerRunConfig(
                    session_id=SESSION,
                    js_only=True,
                    js_code=_JS_INJECT_METADATA,
                    delay_before_return_html=0.8,
                    cache_mode=CacheMode.BYPASS,
                )
                meta_result = await crawler.arun(self.base_url, config=meta_cfg)
                if not meta_result.success:
                    print(f"   ❌ Error inyectando metadata: {meta_result.error_message}")
                    return []

                # Leer metadata inyectada por JS
                meta_soup = BeautifulSoup(meta_result.html, 'html.parser')
                meta_el = meta_soup.find(id='__dia_meta')
                if not meta_el:
                    print("   ⚠️ Metadata JS no inyectada — usando fallback HTML")
                    cards_meta = self._fallback_cards_meta(meta_soup)
                else:
                    try:
                        cards_meta = json.loads(meta_el.get_text())
                    except json.JSONDecodeError:
                        print("   ⚠️ JSON malformado — usando fallback HTML")
                        cards_meta = self._fallback_cards_meta(meta_soup)

                print(f"   ✅ {len(cards_meta)} cards visibles")

                if os.environ.get('DEBUG_SCRAPER'):
                    with open('debug_dia_meta.html', 'w', encoding='utf-8') as f:
                        f.write(meta_result.html)
                    print(f"   💾 HTML guardado en debug_dia_meta.html")

                # ── 2. Por cada card: abrir modal → extraer → cerrar ─────────────
                print(f"\n   🔎 Extrayendo legales...")
                for card in cards_meta:
                    dom_idx  = card.get('dom_idx', 0)
                    bank_cls = card.get('bank_cls', '')
                    channels = ', '.join(card.get('channels', []))
                    img_url  = card.get('img_src', '')

                    bank = self._normalize_bank(bank_cls)
                    if not bank:
                        bank = self._identify_bank_from_image(img_url, '')
                    if not bank:
                        continue

                    # Abrir modal
                    modal_cfg = CrawlerRunConfig(
                        session_id=SESSION,
                        js_only=True,
                        js_code=_js_click_ver_legales(dom_idx),
                        delay_before_return_html=2.2,
                        cache_mode=CacheMode.BYPASS,
                    )
                    modal_result = await crawler.arun(self.base_url, config=modal_cfg)

                    legal_text = ''
                    if modal_result.success:
                        legal_text = self._extract_modal_text(modal_result.html)

                    discount  = self._extract_discount(legal_text)
                    tope      = self._extract_tope(legal_text)
                    valid_days = self._extract_days(legal_text)

                    print(f"      {bank:25s} | {discount or '—':8s} | {valid_days or 'Todos los días'}")

                    # Cerrar modal
                    close_cfg = CrawlerRunConfig(
                        session_id=SESSION,
                        js_only=True,
                        js_code=_JS_CLOSE_MODAL,
                        delay_before_return_html=0.5,
                        cache_mode=CacheMode.BYPASS,
                    )
                    await crawler.arun(self.base_url, config=close_cfg)

                    title_parts = [p for p in [
                        bank, discount,
                        f"({channels})" if channels else '',
                        f"- {valid_days}" if valid_days else '',
                    ] if p]

                    all_promotions.append({
                        'supermarket': 'Día',
                        'url': self.base_url,
                        'bank': bank,
                        'discount': discount,
                        'valid_days': valid_days,
                        'aplica_en': channels,
                        'tope': tope,
                        'image_url': img_url,
                        'legal_text': legal_text[:2000],
                        'title': ' '.join(title_parts) or bank,
                    })

        except Exception as e:
            print(f"\n   ❌ Error: {e}")
            import traceback
            traceback.print_exc()

        print(f"\n✅ {self.name}: {len(all_promotions)} promociones")
        return all_promotions

    # ──────────────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _fallback_cards_meta(self, soup) -> List[Dict]:
        """Extrae metadata de cards desde HTML puro cuando el JS no inyectó."""
        meta = []
        all_top = [d for d in soup.find_all('div')
                   if d.get('class') and d.get('class')[0] == _CSS_CARD
                   and not any('__' in c for c in d.get('class', [])[1:])]
        for dom_idx, div in enumerate(all_top):
            cls = div.get('class', [])
            bank_cls = ' '.join(c for c in cls if c != _CSS_CARD)
            channels = [s.get_text(strip=True)
                        for s in div.find_all('span')
                        if s.get_text(strip=True) in ('ONLINE', 'TIENDAS')]
            img = div.find('img')
            meta.append({
                'dom_idx': dom_idx,
                'bank_cls': bank_cls,
                'channels': list(dict.fromkeys(channels)),
                'img_src': img.get('src', '') if img else '',
            })
        return meta

    def _extract_modal_text(self, html: str) -> str:
        """Extrae el texto del modal desde el HTML capturado."""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        for sel in [
            '[class*="vtex__modal"]',
            '[role="dialog"]',
            '[class*="Modal__"]',
            '[class*="modal--"]',
            '[class*="overlay--"]',
            '[class*="overlayMask"]',
            '[class*="modalLayout"]',
        ]:
            for el in soup.select(sel):
                text = el.get_text(' ', strip=True)
                if len(text) > 80 and re.search(
                    r'descuento|promo|beneficio|tope|cuota|%|v[aá]lido', text, re.I
                ):
                    return re.sub(r'\s+', ' ', text).strip()
        return ''

    def _extract_discount(self, text: str) -> str:
        if not text:
            return ''
        m = re.search(
            r'(\d{1,3})\s*%\s*(?:de\s+)?(?:descuento|dto\.?|reintegro|bonificaci[oó]n)?',
            text, re.I
        )
        if m:
            return f"{m.group(1)}%"
        m = re.search(r'(\d+)\s*cuotas?\s*sin\s*inter[eé]s', text, re.I)
        if m:
            return f"{m.group(1)} CSI"
        return ''

    def _extract_tope(self, text: str) -> str:
        if not text:
            return ''
        if re.search(r'[Ss]in\s+[Tt]ope', text):
            return 'Sin tope'
        m = re.search(
            r'[Tt]ope\s*(?:m[aá]ximo\s*)?(?:de\s+)?(?:reintegro\s*)?:?\s*\$?\s*([\d.,]+)',
            text, re.I
        )
        if m:
            return f"${m.group(1)}"
        return ''

    def _extract_days(self, text: str) -> str:
        if not text:
            return ''
        day_names = {
            'lunes': 'Lunes', 'martes': 'Martes', 'mi[eé]rcoles': 'Miércoles',
            'jueves': 'Jueves', 'viernes': 'Viernes',
            's[aá]bado': 'Sábado', 'domingo': 'Domingo',
        }
        found = []
        for pattern, name in day_names.items():
            if re.search(pattern, text, re.I):
                found.append(name)
        if not found or len(found) >= 6:
            return ''  # Vacío = todos los días
        return ', '.join(found)

    def _normalize_bank(self, raw: str) -> str:
        if not raw or raw.strip() in (',', ''):
            return ''
        raw = raw.strip()
        for pattern, name in [
            (r'^Modo$', 'MODO'),
            (r'^Prex$', 'Prex'),
            (r'^Personal\s*Pay', 'Personal Pay'),
            (r'^Mercado\s*Pago', 'Mercado Pago'),
            (r'^Banco\s*Columbia', 'Banco Columbia'),
            (r'^Banco\s*del\s*Sol', 'Banco del Sol'),
            (r'Visa.*Master|Master.*Visa', 'Visa/Mastercard'),
            (r'^Naranja', 'Naranja X'),
            (r'^Cuenta\s*DNI', 'Cuenta DNI'),
            (r'^Anses', 'Beneficios ANSES'),
            (r'^Sidecreer', 'Sidecreer'),
            (r'^Tarjeta\s*BA', 'Tarjeta BA'),
            (r'^BNA$|^Banco\s*Naci', 'Banco Nación'),
            (r'^Modo.*BNA|^BNA.*Modo', 'MODO + BNA'),
            (r'^Galicia', 'Banco Galicia'),
        ]:
            if re.search(pattern, raw, re.I):
                return name
        if len(raw) > 1 and raw not in (',', '.'):
            return ' '.join(w.capitalize() for w in raw.split())
        return ''

    def _identify_bank_from_image(self, img_src: str, img_alt: str) -> str:
        combined = f"{img_src} {img_alt}".lower()
        for pattern, name in [
            (r'modo', 'MODO'), (r'prex', 'Prex'),
            (r'personal.?pay', 'Personal Pay'), (r'mercado.?pago', 'Mercado Pago'),
            (r'naranja', 'Naranja X'), (r'cuenta.?dni', 'Cuenta DNI'),
            (r'anses', 'Beneficios ANSES'), (r'galicia', 'Banco Galicia'),
            (r'macro', 'Banco Macro'), (r'nacion|bna', 'Banco Nación'),
            (r'ciudad', 'Banco Ciudad'), (r'santander', 'Banco Santander'),
            (r'patagonia', 'Banco Patagonia'), (r'comafi', 'Banco Comafi'),
            (r'hsbc', 'HSBC'), (r'bbva|franc[eé]s', 'BBVA'),
            (r'icbc', 'ICBC'), (r'credicoop', 'Banco Credicoop'),
            (r'supervielle', 'Supervielle'), (r'columbia', 'Banco Columbia'),
        ]:
            if re.search(pattern, combined):
                return name
        return ''
