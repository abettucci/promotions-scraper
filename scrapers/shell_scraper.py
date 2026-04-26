"""Scraper de Shell — descuentos vigentes."""
from typing import List, Dict
from .fuel_base import fetch_html, parse_promo_cards


class ShellScraper:
    def __init__(self):
        self.name = 'Shell'
        self.url = 'https://www.shell.com.ar/conductores/descuentos-vigentes.html'

    async def scrape(self) -> List[Dict]:
        print(f"\n🔍 Scraping {self.name}...")
        print(f"   🌐 {self.url}")
        try:
            html = await fetch_html(self.url, scroll=True)
            promos = parse_promo_cards(html, self.name, self.url)
            print(f"✅ {self.name}: {len(promos)} promociones encontradas")
            return promos
        except Exception as e:
            print(f"❌ Error en {self.name}: {e}")
            import traceback
            traceback.print_exc()
            return []
