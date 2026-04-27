"""Scraper de MODO — usa Claude Vision sobre la URL dedicada de combustibles."""
from typing import List, Dict
from .fuel_base import scrape_fuel_station_with_ai


class ModoScraper:
    def __init__(self):
        self.name = 'MODO'
        # MODO expone una URL dedicada por categoría: /promos/<categoria>
        self.url = 'https://www.modo.com.ar/promos/combustibles'

    async def scrape(self) -> List[Dict]:
        return await scrape_fuel_station_with_ai(self.name, self.url, debug_name='modo')
