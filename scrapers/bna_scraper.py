"""Scraper de Banco Nación (descuentos YPF) — usa Claude Vision."""
from typing import List, Dict
from .fuel_base import scrape_fuel_station_with_ai


class BnaScraper:
    def __init__(self):
        self.name = 'Banco Nación'
        self.url = 'https://www.bna.com.ar/Personas/DescuentosYPromociones/4486/ypf/'

    async def scrape(self) -> List[Dict]:
        return await scrape_fuel_station_with_ai(self.name, self.url, debug_name='bna')
