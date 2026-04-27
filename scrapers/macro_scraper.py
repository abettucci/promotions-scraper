"""Scraper de Banco Macro Selecta (combustibles) — usa Claude Vision."""
from typing import List, Dict
from .fuel_base import scrape_fuel_station_with_ai


class MacroScraper:
    def __init__(self):
        self.name = 'Banco Macro'
        self.url = 'https://www.macro.com.ar/selecta/combustible'

    async def scrape(self) -> List[Dict]:
        return await scrape_fuel_station_with_ai(self.name, self.url, debug_name='macro')
