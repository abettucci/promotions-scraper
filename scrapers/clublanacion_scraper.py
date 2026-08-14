"""
Club La Nación — Beneficios
URL: https://club.lanacion.com.ar/beneficios

SSR para las primeras ~12 cards. Las 577 restantes se cargan via scroll infinito.
Usamos Crawl4AI con scroll para capturar cuantas más podamos.

Card selector (SSR): a[data-test-id="account-list-card"]
  - h4.text-16 → nombre del comercio
  - span.text-32.text-secondary-positive → descuento (e.g. "10%")
  - category from URL path (/beneficios/<categoria>/...)
"""
import re
import os
from typing import List, Dict, Optional
from .base_scraper import BaseScraper


_CARD_SEL = 'a[data-test-id="account-list-card"]'

# JS que scrollea hasta el final de la página múltiples veces para cargar más cards
_JS_SCROLL = """
(function() {
  var last = 0;
  var attempts = 0;
  var interval = setInterval(function() {
    window.scrollTo(0, document.body.scrollHeight);
    if (document.body.scrollHeight === last || attempts > 15) {
      clearInterval(interval);
    }
    last = document.body.scrollHeight;
    attempts++;
  }, 600);
})();
"""


class ClubLaNacionScraper(BaseScraper):
    def __init__(self):
        super().__init__(
            name='Club La Nación',
            url='https://club.lanacion.com.ar/beneficios'
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
        run_cfg = CrawlerRunConfig(
            wait_for=f'css:{_CARD_SEL}',
            js_code=_JS_SCROLL,
            delay_before_return_html=12.0,   # tiempo para que el scroll infinite cargue
            page_timeout=60000,
            cache_mode=CacheMode.BYPASS,
        )

        try:
            async with AsyncWebCrawler(config=browser_cfg) as crawler:
                result = await crawler.arun(self.url, config=run_cfg)
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return []

        if not result.success:
            print(f"   ❌ Crawl4AI falló: {result.error_message}")
            return []

        if os.environ.get('DEBUG_SCRAPER'):
            with open('debug_clublanacion.html', 'w', encoding='utf-8') as f:
                f.write(result.html)

        soup = BeautifulSoup(result.html, 'html.parser')
        cards = soup.select(_CARD_SEL)
        print(f"   🔍 {len(cards)} cards encontradas")

        promotions = []
        seen: set = set()

        for card in cards:
            promo = self._parse_card(card)
            if not promo:
                continue
            key = (promo.get('title', '').lower(), promo.get('discount', ''))
            if key in seen:
                continue
            seen.add(key)
            promotions.append(promo)

        print(f"✅ {self.name}: {len(promotions)} promociones")
        return promotions

    def _parse_card(self, card) -> Optional[Dict]:
        # Merchant name
        h4 = card.find('h4', class_=re.compile(r'text-16'))
        merchant = h4.get_text(strip=True) if h4 else ''

        # Discount
        pct_span = card.find('span', class_=re.compile(r'text-32'))
        discount_text = pct_span.get_text(strip=True) if pct_span else ''
        discount = self.extract_discount(discount_text) if discount_text else ''

        # Cuotas pattern in discount_text
        if not discount:
            cuota_m = re.search(r'(\d+)\s*cuotas?', discount_text, re.I)
            if cuota_m:
                discount = f"{cuota_m.group(1)} cuotas"

        # Category from href
        href = card.get('href', '')
        category = ''
        cat_m = re.match(r'/beneficios/([^/]+)', href)
        if cat_m:
            category = cat_m.group(1).replace('-', ' ').title()

        if not merchant and not discount:
            return None

        title = merchant
        if discount:
            title = f"{discount} en {merchant}" if merchant else discount

        return {
            'title':          self.clean_text(title),
            'discount':       discount,
            'bank':           'Club La Nación',
            'wallet':         None,
            'card_type':      None,
            'payment_method': None,
            'store_types':    None,
            'valid_days':     'Todos los días',
            'url':            f"https://club.lanacion.com.ar{href}" if href.startswith('/') else href,
            'image_url':      None,
            'terms_raw':      category,
            'tope':           None,
            'min_purchase':   None,
            'exclusions':     [],
            'requirements':   [],
            'valid_from':     None,
            'valid_until':    None,
        }
