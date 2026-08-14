"""
Personal Pay — Beneficios
URL: https://www.personal.com.ar/pay/beneficios

Next.js SPA: el contenido de las cards se carga dinámicamente tras el render.
Usamos Crawl4AI + Playwright para ejecutar el JS y capturar el HTML renderizado.
"""
import re
import os
from typing import List, Dict, Optional
from .base_scraper import BaseScraper


# Selectores candidatos — probamos varios en caso de que cambien los nombres de clase
_WAIT_SELECTORS = [
    'css:[class*="benefit"]',
    'css:[class*="promo"]',
    'css:[class*="offer"]',
    'css:[class*="card"]',
    'css:main',
]


class PersonalPayScraper(BaseScraper):
    def __init__(self):
        super().__init__(
            name='Personal Pay',
            url='https://www.personal.com.ar/pay/beneficios'
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

        # Try each wait selector until one works
        for wait_sel in _WAIT_SELECTORS:
            run_cfg = CrawlerRunConfig(
                wait_for=wait_sel,
                delay_before_return_html=4.0,
                page_timeout=45000,
                cache_mode=CacheMode.BYPASS,
            )
            try:
                async with AsyncWebCrawler(config=browser_cfg) as crawler:
                    result = await crawler.arun(self.url, config=run_cfg)
                if result.success and result.html and len(result.html) > 5000:
                    html = result.html
                    print(f"   ✅ Rendered con selector: {wait_sel}")
                    break
            except Exception:
                continue

        if not html:
            print("   ❌ No se pudo renderizar la página")
            return []

        if os.environ.get('DEBUG_SCRAPER'):
            with open('debug_personalpay.html', 'w', encoding='utf-8') as f:
                f.write(html)

        soup = BeautifulSoup(html, 'html.parser')
        promotions = self._extract_cards(soup)
        print(f"✅ {self.name}: {len(promotions)} promociones")
        return promotions

    def _extract_cards(self, soup) -> List[Dict]:
        """Intenta múltiples estrategias de extracción de cards."""
        promotions = []
        seen: set = set()

        # Estrategia 1: buscar elementos que contengan porcentaje de descuento
        # y tengan texto de comercio/marca
        discount_nodes = soup.find_all(string=re.compile(r'\d+\s*%'))
        for node in discount_nodes:
            card = node.find_parent(['div', 'article', 'li', 'section'])
            if not card:
                continue
            # Subir hasta un contenedor razonable (max 3 niveles)
            for _ in range(3):
                parent = card.find_parent(['div', 'article', 'li', 'section'])
                if parent and len(parent.get_text(strip=True)) < 500:
                    card = parent
                else:
                    break

            text = card.get_text(' ', strip=True)
            if len(text) < 10 or len(text) > 600:
                continue

            discount = self.extract_discount(text)
            if not discount:
                continue

            title = text[:120].strip()
            key = (discount, title[:40])
            if key in seen:
                continue
            seen.add(key)

            promo = self._build_promo(title, discount, text)
            promotions.append(promo)

        # Estrategia 2: buscar patrones de "cuotas sin interés"
        cuotas_nodes = soup.find_all(string=re.compile(r'\d+\s*cuotas?\s+sin\s+inter', re.I))
        for node in cuotas_nodes:
            card = node.find_parent(['div', 'article', 'li'])
            if not card:
                continue
            text = card.get_text(' ', strip=True)[:200]
            m = re.search(r'(\d+)\s*cuotas?', text, re.I)
            if not m:
                continue
            discount = f"{m.group(1)} cuotas"
            key = (discount, text[:40])
            if key in seen:
                continue
            seen.add(key)
            promotions.append(self._build_promo(text[:120], discount, text))

        return promotions

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
            'bank':           None,
            'wallet':         'Personal Pay',
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
