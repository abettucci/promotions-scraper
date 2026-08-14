"""
Brubank — Beneficios
URL: https://www.brubank.com/beneficios

La página es server-side rendered (Webflow). No requiere browser.
Cards: div.special-card-carousel.card-promo-dark
  - <strong class="titulo-cuotas"> = tipo de beneficio (ej: "Hasta 6 cuotas sin interés")
  - texto restante en <h4> = nombre del comercio
  - <p class="parrafo-promo-dark"> = días y condiciones
"""
import re
import asyncio
from typing import List, Dict, Optional
from .base_scraper import BaseScraper


_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'es-AR,es;q=0.9',
}


class BrubankScraper(BaseScraper):
    def __init__(self):
        super().__init__(name='Brubank', url='https://www.brubank.com/beneficios')

    async def scrape(self, page=None) -> List[Dict]:
        import requests
        from bs4 import BeautifulSoup

        print(f"🔍 Scraping {self.name}...")
        print(f"   🌐 URL: {self.url}")

        try:
            loop = asyncio.get_event_loop()
            resp = await loop.run_in_executor(
                None,
                lambda: requests.get(self.url, headers=_HEADERS, timeout=30)
            )
            resp.raise_for_status()
        except Exception as e:
            print(f"   ❌ Error fetching: {e}")
            return []

        soup = BeautifulSoup(resp.text, 'html.parser')
        cards = soup.find_all('div', class_=re.compile(r'special-card-carousel.*card-promo-dark|card-promo-dark.*special-card-carousel'))
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
            print(f"   + {promo.get('title', '')[:60]}")

        print(f"✅ {self.name}: {len(promotions)} promociones")
        return promotions

    def _parse_card(self, card) -> Optional[Dict]:
        from bs4 import BeautifulSoup

        h4 = card.find('h4', class_=re.compile(r'titulo-promo'))
        strong = h4.find('strong') if h4 else None

        benefit_type = strong.get_text(strip=True) if strong else ''
        merchant = ''
        if h4:
            full_text = h4.get_text(' ', strip=True)
            merchant = re.sub(re.escape(benefit_type), '', full_text).strip().strip('|').strip()

        # Days / conditions
        p = card.find('p', class_=re.compile(r'parrafo-promo'))
        conditions = ''
        if p:
            # Strip link text
            for a in p.find_all('a'):
                a.decompose()
            conditions = re.sub(r'\s+', ' ', p.get_text(' ', strip=True)).strip()

        if not benefit_type and not merchant:
            return None

        title = f"{benefit_type} en {merchant}" if (benefit_type and merchant) else (benefit_type or merchant)
        discount = self.extract_discount(benefit_type)

        # Map "cuotas sin interés" → discount field
        if not discount and 'cuota' in benefit_type.lower():
            cuota_m = re.search(r'(\d+)\s*cuotas?', benefit_type, re.I)
            if cuota_m:
                discount = f"{cuota_m.group(1)} cuotas"

        tope_m = re.search(r'tope\b[^.$\n]{0,30}\$\s*(\d[\d.,]*)', conditions, re.I)
        tope = None
        if tope_m:
            try:
                n = float(tope_m.group(1).replace('.', '').replace(',', '.'))
                tope = f"${n:,.0f}".replace(',', '.')
            except ValueError:
                pass

        return {
            'title':          self.clean_text(title),
            'discount':       discount,
            'bank':           'Brubank',
            'wallet':         None,
            'card_type':      None,
            'payment_method': None,
            'store_types':    None,
            'valid_days':     conditions or 'Todos los días',
            'url':            self.url,
            'image_url':      None,
            'terms_raw':      '',
            'tope':           tope,
            'min_purchase':   None,
            'exclusions':     [],
            'requirements':   [],
            'valid_from':     None,
            'valid_until':    None,
        }
