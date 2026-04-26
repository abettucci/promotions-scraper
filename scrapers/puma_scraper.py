"""Scraper de Puma Energy — listing + páginas individuales con Claude Vision."""
import asyncio
import re
from typing import List, Dict
from playwright.async_api import async_playwright
from .fuel_base import scrape_fuel_station_with_ai


class PumaScraper:
    def __init__(self):
        self.name = 'Puma Energy'
        self.url = 'https://pumaenergyarg.com.ar/promociones'
        self.detail_pattern = 'https://pumaenergyarg.com.ar/promocion/{id}'

    async def scrape(self) -> List[Dict]:
        # 1. Sacar IDs de promos del listado
        promo_ids = await self._get_promo_ids()
        if not promo_ids:
            print(f"   ⚠️ No se encontraron IDs en el listado, fallback a scraping del listado completo")
            return await scrape_fuel_station_with_ai(self.name, self.url, debug_name='puma_listing')

        print(f"   🔢 Encontradas {len(promo_ids)} promos individuales: {promo_ids[:10]}...")

        # 2. Scrapear cada página individual con AI
        all_promos = []
        for pid in promo_ids:
            url = self.detail_pattern.format(id=pid)
            try:
                promos = await scrape_fuel_station_with_ai(self.name, url, debug_name=f'puma_{pid}')
                all_promos.extend(promos)
            except Exception as e:
                print(f"   ❌ Error en /promocion/{pid}: {e}")
            await asyncio.sleep(1)

        return all_promos

    async def _get_promo_ids(self) -> List[int]:
        """Extrae los IDs de las URLs /promocion/X del listado."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                context = await browser.new_context(viewport={'width': 1920, 'height': 1080})
                page = await context.new_page()
                try:
                    await page.goto(self.url, wait_until='networkidle', timeout=60000)
                    await asyncio.sleep(2)
                    html = await page.content()
                    ids = set(int(m) for m in re.findall(r'/promocion/(\d+)', html))
                    return sorted(ids)
                except Exception as e:
                    print(f"   ⚠️ Error obteniendo IDs: {e}")
                    return []
            finally:
                await browser.close()
