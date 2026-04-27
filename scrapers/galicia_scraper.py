"""Scraper de Banco Galicia (promoción combustible) — usa Claude Vision."""
from typing import List, Dict
from .fuel_base import scrape_fuel_station_with_ai


class GaliciaScraper:
    def __init__(self):
        self.name = 'Banco Galicia'
        self.url = 'https://www.galicia.ar/personas/promociones/promocion-combustible'

    async def scrape(self) -> List[Dict]:
        return await scrape_fuel_station_with_ai(self.name, self.url, debug_name='galicia')
