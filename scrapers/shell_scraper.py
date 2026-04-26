"""Scraper de Shell — usa Claude Vision para extraer promociones."""
from typing import List, Dict
from .fuel_base import scrape_fuel_station_with_ai


class ShellScraper:
    def __init__(self):
        self.name = 'Shell'
        self.url = 'https://www.shell.com.ar/conductores/descuentos-vigentes.html'

    async def scrape(self) -> List[Dict]:
        return await scrape_fuel_station_with_ai(self.name, self.url, debug_name='shell')
