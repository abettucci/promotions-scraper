"""
Scraper principal - Orquesta el scraping de todos los supermercados
"""
import asyncio
import argparse
import sys
from datetime import datetime
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async
import random

import config
from database import Database
from terms_parser import TermsParser
from scrapers.carrefour_scraper import CarrefourScraper
from scrapers.generic_scraper import GenericScraper

class PromoScraper:
    def __init__(self, verbose: bool = False):
        self.db = Database()
        self.terms_parser = TermsParser()
        self.verbose = verbose
        self.stats = {
            'total_promotions': 0,
            'successful_scrapes': 0,
            'failed_scrapes': 0,
            'start_time': datetime.now()
        }
    
    def log(self, message: str, level: str = 'INFO'):
        """Log con timestamp"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"[{timestamp}] {level}: {message}")
    
    async def setup_browser(self, playwright):
        """Configura el browser con anti-detección"""
        self.log("🚀 Iniciando browser...")
        
        browser = await playwright.chromium.launch(
            headless=config.HEADLESS,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
            ]
        )
        
        # Configurar contexto con datos realistas
        context = await browser.new_context(
            viewport=config.VIEWPORT,
            user_agent=random.choice(config.USER_AGENTS),
            locale='es-AR',
            timezone_id='America/Argentina/Buenos_Aires',
            geolocation=config.GEOLOCATION,
            permissions=['geolocation'],
        )
        
        page = await context.new_page()
        
        # Aplicar técnicas stealth
        await stealth_async(page)
        
        return browser, page
    
    def get_scraper(self, supermarket_key: str, supermarket_data: dict):
        """Retorna el scraper apropiado para cada supermercado"""
        # Scrapers específicos
        if supermarket_key == 'carrefour':
            return CarrefourScraper()
        
        # Para el resto, usar scraper genérico
        return GenericScraper(
            name=supermarket_data['name'],
            url=supermarket_data['url']
        )
    
    async def scrape_supermarket(self, page, supermarket_key: str, supermarket_data: dict):
        """Scrape un supermercado específico"""
        try:
            self.log(f"📍 Iniciando scrape: {supermarket_data['name']}")
            
            # Obtener o crear ID del supermercado en DB
            supermarket_id = self.db.insert_supermarket(
                supermarket_data['name'],
                supermarket_data['url']
            )
            
            # Obtener scraper apropiado
            scraper = self.get_scraper(supermarket_key, supermarket_data)
            
            # Ejecutar scraping
            promotions = await scraper.scrape(page)
            
            if not promotions:
                self.log(f"⚠️  {supermarket_data['name']}: No se encontraron promociones", 'WARNING')
                self.db.insert_scrape_history(
                    supermarket_id, 
                    'success', 
                    0, 
                    'No promotions found'
                )
                return
            
            # Guardar promociones en DB
            current_titles = []
            for promo in promotions:
                # Insertar promoción
                promotion_id = self.db.insert_promotion(supermarket_id, promo)
                
                if promotion_id:
                    current_titles.append(promo['title'])
                    
                    # Parsear y guardar términos y condiciones
                    if promo.get('terms_raw'):
                        terms_data = self.terms_parser.parse(promo['terms_raw'])
                        self.db.insert_terms(promotion_id, terms_data)
            
            # Desactivar promociones que ya no existen
            deactivated = self.db.deactivate_old_promotions(supermarket_id, current_titles)
            
            # Actualizar última fecha de scrape
            self.db.update_supermarket_scraped(supermarket_id)
            
            # Registrar historial
            self.db.insert_scrape_history(
                supermarket_id,
                'success',
                len(promotions)
            )
            
            # Actualizar stats
            self.stats['total_promotions'] += len(promotions)
            self.stats['successful_scrapes'] += 1
            
            self.log(f"✅ {supermarket_data['name']}: {len(promotions)} promociones guardadas" + 
                    (f", {deactivated} desactivadas" if deactivated > 0 else ""))
            
            # Delay entre supermercados
            await asyncio.sleep(random.uniform(3, 6))
            
        except Exception as e:
            self.log(f"❌ Error scraping {supermarket_data['name']}: {str(e)}", 'ERROR')
            
            if self.verbose:
                import traceback
                traceback.print_exc()
            
            # Registrar error en historial
            supermarket_id = self.db.insert_supermarket(
                supermarket_data['name'],
                supermarket_data['url']
            )
            self.db.insert_scrape_history(
                supermarket_id,
                'error',
                0,
                str(e)
            )
            
            self.stats['failed_scrapes'] += 1
    
    async def run(self, supermarket_filter: str = None):
        """Ejecuta el scraping de todos los supermercados"""
        self.log("=" * 60)
        self.log("🛒 SCRAPER DE PROMOCIONES BANCARIAS")
        self.log("=" * 60)
        
        async with async_playwright() as playwright:
            browser, page = await self.setup_browser(playwright)
            
            try:
                # Filtrar supermercados a scrapear
                supermarkets = config.SUPERMARKETS
                if supermarket_filter:
                    if supermarket_filter in supermarkets:
                        supermarkets = {supermarket_filter: supermarkets[supermarket_filter]}
                    else:
                        self.log(f"❌ Supermercado '{supermarket_filter}' no encontrado", 'ERROR')
                        return
                
                # Scrapear solo supermercados habilitados
                enabled_supermarkets = {
                    k: v for k, v in supermarkets.items() 
                    if v.get('enabled', True)
                }
                
                self.log(f"📊 Supermercados a scrapear: {len(enabled_supermarkets)}")
                self.log("")
                
                # Scrapear cada supermercado
                for key, data in enabled_supermarkets.items():
                    await self.scrape_supermarket(page, key, data)
                
            finally:
                await browser.close()
        
        # Mostrar resumen
        self.print_summary()
    
    def print_summary(self):
        """Imprime resumen de la ejecución"""
        elapsed = (datetime.now() - self.stats['start_time']).total_seconds()
        
        self.log("")
        self.log("=" * 60)
        self.log("📊 RESUMEN DE EJECUCIÓN")
        self.log("=" * 60)
        self.log(f"✅ Scrapes exitosos: {self.stats['successful_scrapes']}")
        self.log(f"❌ Scrapes fallidos: {self.stats['failed_scrapes']}")
        self.log(f"🎯 Total promociones: {self.stats['total_promotions']}")
        self.log(f"⏱️  Tiempo total: {elapsed:.1f} segundos")
        self.log("=" * 60)
        
        # Mostrar estadísticas de DB
        stats = self.db.get_supermarket_stats()
        if stats:
            self.log("")
            self.log("📈 ESTADÍSTICAS POR SUPERMERCADO:")
            for stat in stats:
                self.log(f"  • {stat['name']}: {stat['active_promotions']} promociones activas")
        
        self.log("")
        self.log("💾 Base de datos: " + str(config.DATABASE_PATH))
        self.log("")

def main():
    parser = argparse.ArgumentParser(
        description='Scraper de promociones bancarias de supermercados argentinos'
    )
    parser.add_argument(
        '--supermarket', '-s',
        help='Scrapear solo un supermercado específico (carrefour, coto, disco, etc.)',
        type=str
    )
    parser.add_argument(
        '--verbose', '-v',
        help='Modo verbose (más detalles)',
        action='store_true'
    )
    parser.add_argument(
        '--list', '-l',
        help='Listar supermercados disponibles',
        action='store_true'
    )
    
    args = parser.parse_args()
    
    # Listar supermercados
    if args.list:
        print("\n🏪 Supermercados disponibles:")
        print("=" * 50)
        for key, data in config.SUPERMARKETS.items():
            status = "✅" if data.get('enabled', True) else "❌"
            print(f"  {status} {key:15} - {data['name']}")
        print("=" * 50)
        print("\nUso: python scraper.py --supermarket <nombre>")
        print("Ejemplo: python scraper.py --supermarket carrefour\n")
        return
    
    # Ejecutar scraper
    scraper = PromoScraper(verbose=args.verbose)
    
    try:
        asyncio.run(scraper.run(supermarket_filter=args.supermarket))
    except KeyboardInterrupt:
        print("\n\n⚠️  Scraping interrumpido por el usuario")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error fatal: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

