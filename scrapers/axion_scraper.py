"""Scraper de Axion — usa Claude Vision."""
from typing import List, Dict
from .fuel_base import scrape_fuel_station_with_ai


class AxionScraper:
    def __init__(self):
        self.name = 'Axion'
        self.url = 'https://www.axionenergy.com/Paginas/beneficios/beneficiosypromociones.aspx'

    async def scrape(self) -> List[Dict]:
        return await scrape_fuel_station_with_ai(self.name, self.url, debug_name='axion')
