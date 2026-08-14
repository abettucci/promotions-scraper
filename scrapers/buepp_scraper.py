"""
Buepp — Beneficios
URL: https://www.buepp.com.ar/beneficios

Angular SPA puro (app-root vacío en HTML inicial). Requiere ejecución completa del browser.
Buepp es la billetera digital de Banco Ciudad (BUEPP = Buenos Aires + app).

Estrategia:
  1. Crawl4AI navega y espera que Angular renderice
  2. Buscamos selectores de Angular Material (mat-card) o los más genéricos
  3. Fallback: buscar cualquier elemento con % de descuento
"""
import re
import os
from typing import List, Dict, Optional
from .base_scraper import BaseScraper


_WAIT_OPTIONS = [
    'css:mat-card',
    'css:[class*="benefit"]',
    'css:[class*="promo"]',
    'css:[class*="offer"]',
    'css:[class*="card"]:not(meta):not(link)',
    'css:app-root > *',
]


class BueppScraper(BaseScraper):
    def __init__(self):
        super().__init__(
            name='Buepp',
            url='https://www.buepp.com.ar/beneficios'
        )

    async def scrape(self, page=None) -> List[Dict]:
        try:
            from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, BrowserConfig, CacheMode
        except ImportError:
            print("   ⚠️ crawl4ai no instalado")
            return []
        from bs4 import BeautifulSoup

        print(f"🔍 Scraping {self.name}...")
        print(f"   🌐 URL: {self.url}")

        browser_cfg = BrowserConfig(headless=True, verbose=False)
        html = None

        for wait_sel in _WAIT_OPTIONS:
            run_cfg = CrawlerRunConfig(
                wait_for=wait_sel,
                delay_before_return_html=5.0,
                page_timeout=45000,
                cache_mode=CacheMode.BYPASS,
            )
            try:
                async with AsyncWebCrawler(config=browser_cfg) as crawler:
                    result = await crawler.arun(self.url, config=run_cfg)
                if result.success and result.html:
                    body_text = BeautifulSoup(result.html, 'html.parser').get_text()
                    # Verify Angular rendered something meaningful (not just empty app-root)
                    if len(body_text.strip()) > 500:
                        html = result.html
                        print(f"   ✅ Renderizado con selector: {wait_sel}")
                        break
            except Exception:
                continue

        if not html:
            print("   ❌ No se pudo renderizar la página Angular")
            return []

        if os.environ.get('DEBUG_SCRAPER'):
            with open('debug_buepp.html', 'w', encoding='utf-8') as f:
                f.write(html)

        soup = BeautifulSoup(html, 'html.parser')
        promotions = self._extract_cards(soup)
        print(f"✅ {self.name}: {len(promotions)} promociones")
        return promotions

    def _extract_cards(self, soup) -> List[Dict]:
        promotions = []
        seen: set = set()

        # Estrategia 1: Angular Material mat-card
        mat_cards = soup.find_all('mat-card')
        if mat_cards:
            for card in mat_cards:
                promo = self._parse_generic_card(card)
                if promo:
                    key = (promo['title'][:40], promo['discount'])
                    if key not in seen:
                        seen.add(key)
                        promotions.append(promo)
            if promotions:
                return promotions

        # Estrategia 2: cualquier div/article con porcentaje de descuento
        discount_nodes = soup.find_all(string=re.compile(r'\d+\s*%'))
        for node in discount_nodes:
            card = node.find_parent(['div', 'article', 'section', 'li'])
            if not card:
                continue
            text = card.get_text(' ', strip=True)
            if len(text) < 10 or len(text) > 600:
                continue
            discount = self.extract_discount(text)
            if not discount:
                continue
            key = (discount, text[:40])
            if key in seen:
                continue
            seen.add(key)
            promotions.append(self._build_promo(text[:120], discount, text))

        return promotions

    def _parse_generic_card(self, card) -> Optional[Dict]:
        text = card.get_text(' ', strip=True)
        if not text or len(text) < 10:
            return None

        discount = self.extract_discount(text)
        if not discount:
            cuota_m = re.search(r'(\d+)\s*cuotas?', text, re.I)
            if cuota_m:
                discount = f"{cuota_m.group(1)} cuotas"

        if not discount:
            return None

        title_el = card.find(['h1', 'h2', 'h3', 'h4', 'h5', 'mat-card-title'])
        title = title_el.get_text(strip=True) if title_el else text[:80]

        return self._build_promo(title, discount, text)

    def _build_promo(self, title: str, discount: str, text: str) -> Dict:
        tope = None
        tope_m = re.search(r'tope\b[^.$\n]{0,30}\$\s*(\d[\d.,]*)', text, re.I)
        if tope_m:
            try:
                n = float(tope_m.group(1).replace('.', '').replace(',', '.'))
                tope = f"${n:,.0f}".replace(',', '.')
            except ValueError:
                pass

        days_m = re.search(
            r'(todos\s+los\s+d[ií]as|lunes\s+a\s+viernes|lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo)',
            text, re.I
        )
        valid_days = days_m.group(0).strip().capitalize() if days_m else 'Todos los días'

        return {
            'title':          self.clean_text(title),
            'discount':       discount,
            'bank':           'Banco Ciudad',
            'wallet':         'Buepp',
            'card_type':      None,
            'payment_method': None,
            'store_types':    None,
            'valid_days':     valid_days,
            'url':            self.url,
            'image_url':      None,
            'terms_raw':      self.clean_text(text[:800]),
            'tope':           tope,
            'min_purchase':   None,
            'exclusions':     [],
            'requirements':   [],
            'valid_from':     None,
            'valid_until':    None,
        }
