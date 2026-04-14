"""
Scraper principal - Orquesta el scraping de todos los supermercados
"""
import asyncio
import argparse
import sys
import os
from datetime import datetime

# Asegurar que el directorio del script esté en el path
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

from playwright.async_api import async_playwright
from playwright_stealth import stealth_async
import random

import config
from database import Database
from terms_parser import TermsParser
from notifier import TelegramNotifier

# Scrapers específicos
from scrapers.carrefour_scraper import CarrefourScraper
from scrapers.generic_scraper import GenericScraper
from scrapers.dia_scraper import DiaScraper
from scrapers.coto_scraper import CotoScraper
from scrapers.masonline_scraper import MasOnlineScraper
from scrapers.cencosud_scraper import CencosudScraper

# AI Extractor (opcional)
try:
    from scrapers.ai_extractor import AIExtractor
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False

class PromoScraper:
    def __init__(self, verbose: bool = False, use_ai: bool = False):
        self.db = Database()
        self.terms_parser = TermsParser()
        self.verbose = verbose
        self.use_ai = use_ai
        self.ai_extractor = None
        self.stats = {
            'total_promotions': 0,
            'successful_scrapes': 0,
            'failed_scrapes': 0,
            'start_time': datetime.now()
        }
        
        # Inicializar AI Extractor si se solicita
        if use_ai:
            if not AI_AVAILABLE:
                raise ImportError(
                    "El módulo de IA no está disponible. "
                    "Instala anthropic: pip install anthropic"
                )
            try:
                self.ai_extractor = AIExtractor()
                self.log("🤖 Modo IA activado - usando Claude Vision para extracción")
            except Exception as e:
                raise RuntimeError(f"Error inicializando AI Extractor: {e}")
    
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
        # Scrapers específicos que usan page compartido (heredan de BaseScraper)
        if supermarket_key == 'carrefour':
            return CarrefourScraper()
        
        # Para el resto, usar scraper genérico
        return GenericScraper(
            name=supermarket_data['name'],
            url=supermarket_data['url']
        )
    
    def get_standalone_scraper(self, supermarket_key: str):
        """
        Retorna scrapers que manejan su propio browser (standalone).
        Estos scrapers no reciben page como parámetro.
        """
        standalone_scrapers = {
            'dia': DiaScraper,
            'coto': CotoScraper,
            'masonline': MasOnlineScraper,
            'cencosud': CencosudScraper,
        }
        
        if supermarket_key in standalone_scrapers:
            return standalone_scrapers[supermarket_key]()
        return None
    
    async def scrape_supermarket(self, page, supermarket_key: str, supermarket_data: dict):
        """Scrape un supermercado específico"""
        try:
            mode_indicator = "🤖" if self.use_ai else "📍"
            self.log(f"{mode_indicator} Iniciando scrape: {supermarket_data['name']}")
            
            # Obtener o crear ID del supermercado en DB
            supermarket_id = self.db.insert_supermarket(
                supermarket_data['name'],
                supermarket_data['url']
            )
            
            promotions = []
            
            # Modo IA: usar Claude Vision para extracción
            if self.use_ai and self.ai_extractor:
                # Navegar a la página
                url = supermarket_data['url']
                self.log(f"   🌐 Navegando a {url}")
                
                try:
                    await page.goto(url, wait_until='networkidle', timeout=60000)
                    await asyncio.sleep(3)  # Esperar carga de JS
                    
                    # Extraer con IA
                    promotions = await self.ai_extractor.extract_from_screenshot(
                        page,
                        supermarket_data['name'],
                        url
                    )
                except Exception as e:
                    self.log(f"   ⚠️ Error navegando: {e}", 'WARNING')
                    # Intentar con scraper tradicional como fallback
                    self.log(f"   🔄 Intentando con scraper tradicional...")
                    promotions = await self._scrape_traditional(page, supermarket_key, supermarket_data)
            else:
                # Modo tradicional
                promotions = await self._scrape_traditional(page, supermarket_key, supermarket_data)
            
            if not promotions:
                self.log(f"⚠️  {supermarket_data['name']}: No se encontraron promociones", 'WARNING')
                self.db.insert_scrape_history(
                    supermarket_id, 
                    'success', 
                    0, 
                    'No promotions found'
                )
                return
            
            raw_count = len(promotions)
            promotions = self._deduplicate_promotions(promotions)
            if raw_count != len(promotions):
                self.log(f"   🧹 Dedup: {raw_count} → {len(promotions)} promociones únicas")

            # Deactivate all existing promos before re-inserting so old duplicates are cleared
            self.db.deactivate_all_for_supermarket(supermarket_id)

            # Guardar promociones en DB
            current_titles = []
            for promo in promotions:
                # Insertar promoción
                promotion_id = self.db.insert_promotion(supermarket_id, promo)
                
                if promotion_id:
                    current_titles.append(promo.get('title', ''))
                    
                    # Parsear y guardar términos y condiciones
                    if promo.get('terms_raw'):
                        terms_data = self.terms_parser.parse(promo['terms_raw'])
                        self.db.insert_terms(promotion_id, terms_data)
            
            # Desactivar promociones que ya no existen
            deactivated = self.db.deactivate_old_promotions(supermarket_id, current_titles)
            
            # Actualizar última fecha de scrape
            self.db.update_supermarket_scraped(supermarket_id)
            
            # Registrar historial
            extraction_method = 'ai_vision' if self.use_ai else 'traditional'
            self.db.insert_scrape_history(
                supermarket_id,
                'success',
                len(promotions),
                f'Method: {extraction_method}'
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
    
    @staticmethod
    def _deduplicate_promotions(promotions: list) -> list:
        """
        Universal dedup applied before DB insert, regardless of scraper path.
        Key: (entity, discount, valid_days, has_online).
        Drops promos with no bank AND no wallet (unidentifiable noise).
        Prefers entries with more data (longer terms_raw).
        """
        seen: dict = {}
        for promo in promotions:
            bank = (promo.get('bank') or '').strip().lower()
            wallet = (promo.get('wallet') or '').strip().lower()
            entity = bank or wallet
            if not entity:
                continue
            discount = (promo.get('discount') or '').strip().lower()
            days = (promo.get('valid_days') or '').strip().lower()[:40]
            stores = (promo.get('store_types') or '').lower()
            has_online = 'carrefour.com' in stores or '.com' in stores or 'online' in stores
            key = (entity, discount, days, has_online)
            existing = seen.get(key)
            if existing is None or len(promo.get('terms_raw') or '') > len(existing.get('terms_raw') or ''):
                seen[key] = promo
        return list(seen.values())

    async def _scrape_traditional(self, page, supermarket_key: str, supermarket_data: dict):
        """Ejecuta scraping tradicional (CSS selectors + regex)"""
        # Verificar si hay un scraper standalone para este supermercado
        standalone_scraper = self.get_standalone_scraper(supermarket_key)
        
        if standalone_scraper:
            # Los scrapers standalone manejan su propio browser
            self.log(f"   🔧 Usando scraper standalone para {supermarket_data['name']}")
            return await standalone_scraper.scrape()
        else:
            # Usar scraper que recibe page
            scraper = self.get_scraper(supermarket_key, supermarket_data)
            return await scraper.scrape(page)
    
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

        # Notificación Telegram (si está habilitada o se pidió explícitamente)
        if getattr(self, 'notify', False) or config.TELEGRAM_NOTIFY_ON_SCRAPE:
            self.log("📤 Enviando notificación Telegram...")
            notifier = TelegramNotifier()
            elapsed = (datetime.now() - self.stats['start_time']).total_seconds()
            notifier.send_scrape_summary({**self.stats, 'elapsed_seconds': elapsed})
            notifier.send_promotions(today_only=config.TELEGRAM_TODAY_ONLY)
    
    def print_summary(self):
        """Imprime resumen de la ejecución"""
        elapsed = (datetime.now() - self.stats['start_time']).total_seconds()
        
        self.log("")
        self.log("=" * 60)
        self.log("📊 RESUMEN DE EJECUCIÓN")
        self.log("=" * 60)
        mode = "🤖 IA (Claude Vision)" if self.use_ai else "🔧 Tradicional (CSS + Regex)"
        self.log(f"📋 Modo: {mode}")
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
        help='Scrapear solo un supermercado específico (carrefour, coto, dia, etc.)',
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
    parser.add_argument(
        '--ai',
        help='Usar IA (Claude Vision) para extraer promociones en lugar de selectores CSS',
        action='store_true'
    )
    parser.add_argument(
        '--notify',
        help='Enviar notificación Telegram al finalizar el scraping',
        action='store_true'
    )
    parser.add_argument(
        '--notify-only',
        help='Solo enviar notificación Telegram con las promos actuales en DB (sin scrapear)',
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
        print("\nUso:")
        print("  python scraper.py --supermarket <nombre>     # Scraping tradicional")
        print("  python scraper.py --ai --supermarket <nombre> # Scraping con IA")
        print("\nEjemplos:")
        print("  python scraper.py                            # Todos los habilitados")
        print("  python scraper.py --supermarket carrefour    # Solo Carrefour")
        print("  python scraper.py --ai                       # Todos con IA")
        print("  python scraper.py --ai -s dia                # Solo Día con IA\n")
        return
    
    # Verificar disponibilidad de IA si se solicita
    if args.ai and not AI_AVAILABLE:
        print("\n❌ Error: El modo IA requiere el paquete 'anthropic'")
        print("   Instala con: pip install anthropic")
        print("   Y configura: export ANTHROPIC_API_KEY='tu-api-key'\n")
        sys.exit(1)
    
    # --notify-only: solo enviar digest sin scrapear
    if args.notify_only:
        notifier = TelegramNotifier()
        print(f"📤 Enviando digest Telegram (sin scrapear)...")
        notifier.send_promotions(
            supermarket_filter=args.supermarket,
            today_only=config.TELEGRAM_TODAY_ONLY,
        )
        print("✅ Notificación enviada")
        return

    # Ejecutar scraper
    try:
        scraper = PromoScraper(verbose=args.verbose, use_ai=args.ai)
        scraper.notify = args.notify
    except Exception as e:
        print(f"\n❌ Error inicializando scraper: {e}")
        sys.exit(1)

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

