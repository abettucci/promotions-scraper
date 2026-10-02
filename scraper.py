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
from playwright_stealth import Stealth as _Stealth
_stealth_instance = _Stealth()
async def stealth_async(page): await _stealth_instance.apply_stealth_async(page)
import random

import config
from database import Database
from scrape_result_cache import ScrapeResultCache
from terms_parser import TermsParser
from notifier import TelegramNotifier

# Scrapers específicos
from scrapers.carrefour_scraper import CarrefourScraper
from scrapers.generic_scraper import GenericScraper
from scrapers.dia_scraper import DiaScraper
from scrapers.coto_scraper import CotoScraper
from scrapers.masonline_scraper import MasOnlineScraper
from scrapers.cencosud_scraper import CencosudScraper
from scrapers.shell_scraper import ShellScraper
from scrapers.axion_scraper import AxionScraper
from scrapers.puma_scraper import PumaScraper
from scrapers.modo_scraper import ModoScraper
from scrapers.macro_scraper import MacroScraper
from scrapers.galicia_scraper import GaliciaScraper
from scrapers.bna_scraper import BnaScraper
from scrapers.brubank_scraper import BrubankScraper
from scrapers.personalpay_scraper import PersonalPayScraper
from scrapers.mercadopago_scraper import MercadoPagoScraper
from scrapers.clublanacion_scraper import ClubLaNacionScraper
from scrapers.buepp_scraper import BueppScraper
from scrapers.cuentadni_scraper import CuentaDniScraper

# AI Extractor (opcional)
try:
    from scrapers.ai_extractor import AIExtractor
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False

class PromoScraper:
    def __init__(self, verbose: bool = False, use_ai: bool = False):
        self.db = Database()
        self.result_cache = ScrapeResultCache(config.SCRAPER_RESULT_CACHE_PATH)
        # Fuentes que fueron verificadas en esta ejecución pero cuyo resultado
        # no cambió. Se protege su contenido del TTL sin tocar scraped_at.
        self.verified_supermarket_ids: set[int] = set()
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
            'carrefour': CarrefourScraper,  # usa Crawl4AI, standalone
            'dia': DiaScraper,
            'coto': CotoScraper,
            'masonline': MasOnlineScraper,
            'cencosud': CencosudScraper,
            'shell': ShellScraper,
            'axion': AxionScraper,
            'puma': PumaScraper,
            'modo': ModoScraper,
            'macro': MacroScraper,
            'galicia': GaliciaScraper,
            'bna': BnaScraper,
            'brubank': BrubankScraper,
            'personalpay': PersonalPayScraper,
            'mercadopago': MercadoPagoScraper,
            'clublanacion': ClubLaNacionScraper,
            'buepp': BueppScraper,
            'cuentadni': CuentaDniScraper,
        }
        
        if supermarket_key in standalone_scrapers:
            return standalone_scrapers[supermarket_key]()
        return None
    
    async def scrape_supermarket(self, page, supermarket_key: str, supermarket_data: dict):
        """Scrape un supermercado específico"""
        try:
            mode_indicator = "🤖" if self.use_ai else "📍"
            is_aggregator = bool(supermarket_data.get('aggregator'))
            label = supermarket_data['name'] + (" [aggregator]" if is_aggregator else "")
            self.log(f"{mode_indicator} Iniciando scrape: {label}")

            # Para aggregators (bancos/MODO), no creamos un supermarket entry propio.
            # Cada promo se rutea a la marca de gasolinera extraída por la IA.
            # Igual obtenemos el id si existe (de scrapes anteriores) para limpiar promos viejas.
            supermarket_id = self.db.insert_supermarket(
                supermarket_data['name'],
                supermarket_data['url'],
                supermarket_data.get('category', 'supermarket'),
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
            promotions, expired = self._drop_expired_promotions(promotions)
            if expired:
                self.log(f"   ⌛ {expired} promociones vencidas descartadas")
            if not promotions:
                self.log(f"⚠️  {supermarket_data['name']}: todas las promociones están vencidas", 'WARNING')
                self.db.deactivate_for_source(supermarket_id, supermarket_key, include_legacy=not is_aggregator)
                self.db.insert_scrape_history(supermarket_id, 'success', 0, 'All promotions expired')
                return
            promotions = self._deduplicate_promotions(promotions)
            if raw_count != len(promotions):
                self.log(f"   🧹 Dedup: {raw_count} → {len(promotions)} promociones únicas")

            if self.result_cache.unchanged(supermarket_key, promotions):
                self._mark_verified_cache_targets(
                    supermarket_id, promotions, is_aggregator, supermarket_data.get('default_brand'),
                )
                self.stats['total_promotions'] += len(promotions)
                self.stats['successful_scrapes'] += 1
                self.log(
                    f"🗃️  {supermarket_data['name']}: sin cambios — se conserva la base y se omite escritura"
                )
                return

            # Desactivar sólo lo que publicó esta fuente antes de re-insertar:
            # las promos que otros aggregators rutearon a este comercio
            # (p. ej. MODO → Shell) no se tocan.
            self.db.deactivate_for_source(supermarket_id, supermarket_key, include_legacy=not is_aggregator)

            inserted = 0
            extraction_method = 'ai_vision' if self.use_ai else 'traditional'

            if is_aggregator:
                # Splitear cada promo por marca de gasolinera y rutear a su supermarket entry
                default_brand = supermarket_data.get('default_brand')
                # Trackear ids únicos tocados para dedup-deactivate al final
                touched: dict[int, list[str]] = {}

                for promo in promotions:
                    brands = promo.get('merchant_brands') or []
                    if not brands and default_brand:
                        brands = [default_brand]
                    if not brands:
                        # Sin marca identificable no sabemos dónde aplica: antes
                        # se creaba "Combustible (genérico)" con datos basura.
                        self.log(f"   ⏭️ Sin marca identificable, se omite: {promo.get('title')}", 'WARNING')
                        continue

                    # Los aggregators de combustible rutean a estaciones; los de
                    # beneficios (Cuenta DNI, Buepp...) indican el rubro por promo.
                    category = promo.get('merchant_category') or supermarket_data.get('category', 'fuel')
                    if category not in ('supermarket', 'fuel'):
                        continue
                    for brand in brands:
                        brand_id = self.db.insert_supermarket(
                            brand,
                            promo.get('merchant_url') or supermarket_data['url'],
                            category,
                            update_existing=False,
                        )
                        # Limpiar lo que esta fuente publicó antes en la marca
                        # (sólo la primera vez que la tocamos en la corrida).
                        if brand_id not in touched:
                            self.db.deactivate_for_source(brand_id, supermarket_key)
                            touched[brand_id] = []

                        if self.db.has_equivalent_promotion(brand_id, supermarket_key, promo):
                            self.log(f"   ↔️ {brand} ya publica: {promo.get('title')}")
                            continue
                        promo_for_brand = dict(promo)
                        promo_for_brand['merchant_brand'] = brand
                        promo_for_brand['source'] = supermarket_key
                        promotion_id = self.db.insert_promotion(brand_id, promo_for_brand)
                        if promotion_id:
                            touched[brand_id].append(promo.get('title', ''))
                            inserted += 1
                            if promo.get('terms_raw'):
                                terms_data = self._terms_for_promo(promo)
                                self.db.insert_terms(promotion_id, terms_data)

                # Update scrape metadata para cada marca tocada
                for bid in touched:
                    self.db.update_supermarket_scraped(bid)
                    self.db.insert_scrape_history(bid, 'success', len(touched[bid]),
                                                   f'Method: {extraction_method} (via {supermarket_data["name"]})')

                # El aggregator entry queda con 0 promos activas (ya las deactivamos arriba)
                # Eso lo saca del dropdown (HAVING active_promotions > 0 en /api/supermarkets)
                self.db.insert_scrape_history(supermarket_id, 'success', inserted,
                                               f'Aggregator: routed to {len(touched)} brand(s)')
                self.log(f"✅ {supermarket_data['name']}: {inserted} promos ruteadas a {len(touched)} marca(s)")
            else:
                # Flujo standard: todas las promos van bajo este supermarket
                current_titles = []
                for promo in promotions:
                    promotion_id = self.db.insert_promotion(supermarket_id, {**promo, 'source': supermarket_key})
                    if promotion_id:
                        current_titles.append(promo.get('title', ''))
                        inserted += 1
                        if promo.get('terms_raw'):
                            terms_data = self._terms_for_promo(promo)
                            self.db.insert_terms(promotion_id, terms_data)

                # Las que no volvieron a aparecer ya quedaron desactivadas por
                # deactivate_for_source; el upsert reactiva las vigentes.
                deactivated = 0
                self.db.update_supermarket_scraped(supermarket_id)
                self.db.insert_scrape_history(supermarket_id, 'success', inserted,
                                               f'Method: {extraction_method}')
                self.log(f"✅ {supermarket_data['name']}: {inserted} promociones guardadas" +
                         (f", {deactivated} desactivadas" if deactivated > 0 else ""))

            # Solo se actualiza si se persistió todo lo extraído. Si algún
            # INSERT falló, el cache ocultaría el reintento en la próxima
            # corrida (así quedaron fuentes con 0 promos durante semanas).
            # (Los aggregators abren cada promo en N marcas y omiten las que no
            # tienen marca, así que el conteo no es comparable.)
            if not is_aggregator and inserted < len(promotions):
                self.log(
                    f"⚠️ {supermarket_data['name']}: solo {inserted}/{len(promotions)} promociones "
                    "se guardaron; no se actualiza el cache", 'WARNING',
                )
                self.db.insert_scrape_history(
                    supermarket_id, 'error', inserted,
                    f'Partial insert: {inserted}/{len(promotions)}',
                )
                self.stats['total_promotions'] += inserted
                self.stats['failed_scrapes'] += 1
                return
            try:
                self.result_cache.remember(supermarket_key, promotions)
            except Exception as cache_error:
                # El cache es una optimización: una falla al guardarlo no puede
                # invalidar una extracción que ya quedó correctamente guardada.
                self.log(f"⚠️ No se pudo actualizar cache de {supermarket_key}: {cache_error}", 'WARNING')

            # Actualizar stats
            self.stats['total_promotions'] += inserted
            self.stats['successful_scrapes'] += 1
            
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

    def _mark_verified_cache_targets(
        self, supermarket_id: int, promotions: list[dict], is_aggregator: bool,
        default_brand: str | None,
    ) -> None:
        """Marca como frescas las promos comprobadas sin reescribir la DB."""
        if not is_aggregator:
            self.verified_supermarket_ids.add(supermarket_id)
            return
        brands: set[str] = set()
        for promo in promotions:
            raw_brands = promo.get('merchant_brands') or []
            if isinstance(raw_brands, str):
                raw_brands = [raw_brands]
            brands.update(str(brand) for brand in raw_brands if brand)
        if not brands and default_brand:
            brands.add(default_brand)
        for brand in brands:
            brand_id = self.db.get_supermarket_id(str(brand))
            if brand_id is not None:
                self.verified_supermarket_ids.add(brand_id)
    
    @staticmethod
    def _deduplicate_promotions(promotions: list) -> list:
        """
        Universal dedup applied before DB insert, regardless of scraper path.
        Key: (entity, discount, valid_days, has_online).
        Keeps promotions that identify either an entity, a card type or a general
        payment method. Carrefour publishes valid "todos los medios" promotions
        without a bank/wallet, and dropping them turned a successful scrape into 0.
        Prefers entries with more data (longer terms_raw).
        """
        seen: dict = {}
        for promo in promotions:
            # Algunas fuentes oficiales (como Coto) publican varias tarjetas
            # con la misma entidad y beneficio, pero distinto canal, día o
            # condición. El id de origen evita que el deduplicador universal
            # borre una promo publicada legítimamente.
            source_id = (promo.get('source_id') or '').strip()
            if source_id:
                key = ('source', source_id)
                existing = seen.get(key)
                if existing is None or len(promo.get('terms_raw') or '') > len(existing.get('terms_raw') or ''):
                    seen[key] = promo
                continue

            bank = (promo.get('bank') or '').strip().lower()
            wallet = (promo.get('wallet') or '').strip().lower()
            card_type = (promo.get('card_type') or '').strip().lower()
            payment_method = (promo.get('payment_method') or '').strip().lower()
            entity = bank or wallet or card_type or payment_method
            if not entity:
                # Promos de "todos los medios de pago" o programas propios
                # (p. ej. Puma Pris) no tienen entidad; se distinguen por título.
                entity = 'title:' + (promo.get('title') or '').strip().lower()
                if entity == 'title:':
                    continue
            discount = (promo.get('discount') or '').strip().lower()
            days = (promo.get('valid_days') or '').strip().lower()[:40]
            stores = (promo.get('store_types') or promo.get('aplica_en') or '').strip().lower()
            # El tope distingue tramos de la misma promo (Plan Sueldo vs Singular,
            # tarjeta clásica vs Visa) que antes se pisaban entre sí.
            tope = (promo.get('tope') or '').strip().lower()
            key = (entity, discount, days, stores, tope)
            existing = seen.get(key)
            if existing is None or len(promo.get('terms_raw') or '') > len(existing.get('terms_raw') or ''):
                seen[key] = promo
        return list(seen.values())

    @staticmethod
    def _drop_expired_promotions(promotions: list) -> tuple[list, int]:
        """Descarta promos con valid_until pasado antes de tocar la DB.

        Si valid_until < valid_from (typo frecuente en legales, p. ej. "DEL
        1/10/2026 AL 31/12/2025") se descarta sólo la fecha de fin para no
        ocultar una promo que sigue publicada.
        """
        from database import normalize_date_iso

        today = datetime.now().date().isoformat()
        kept = []
        expired = 0
        for promo in promotions:
            valid_from = normalize_date_iso(promo.get('valid_from'))
            valid_until = normalize_date_iso(promo.get('valid_until'))
            if valid_from and valid_until and valid_until < valid_from:
                promo = {**promo, 'valid_until': None}
                valid_until = None
            if valid_until and valid_until < today:
                expired += 1
                continue
            kept.append(promo)
        return kept, expired

    def _terms_for_promo(self, promo: dict) -> dict:
        """Las condiciones explícitas del scraper mandan sobre el parser genérico.

        Los scrapers leen exclusiones/requisitos de la estructura del legal
        (p. ej. la lista de marcas excluidas de Coto); el parser por regex
        sacaba frases sueltas y la API mostraba ésas en lugar de las reales.
        """
        terms_data = self.terms_parser.parse(promo['terms_raw'])
        for field in ('exclusions', 'requirements'):
            source_value = promo.get(field)
            if source_value:
                terms_data[field] = source_value
        return terms_data

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

        # Limpiar promos que quedaron activas por scrapes fallidos (TTL = 2 días)
        # Cubre: scrape retorna 0 resultados, excepción en el scrape, anti-bot, etc.
        self.db.deactivate_stale_promotions(
            max_age_days=2, verified_supermarket_ids=self.verified_supermarket_ids,
        )

        # Notificación Telegram (si está habilitada o se pidió explícitamente)
        if getattr(self, 'notify', False) or config.TELEGRAM_NOTIFY_ON_SCRAPE:
            self.log("📤 Enviando notificación Telegram...")
            notifier = TelegramNotifier()
            elapsed = (datetime.now() - self.stats['start_time']).total_seconds()
            # Resumen al chat de admin (TELEGRAM_CHAT_ID)
            notifier.send_scrape_summary({**self.stats, 'elapsed_seconds': elapsed})
            # Digest personalizado a cada usuario registrado, filtrado por sus métodos de pago
            try:
                notifier.send_user_digests()
            except Exception as e:
                self.log(f"⚠️  Error enviando digests personalizados: {e}", 'WARNING')
    
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
        print(f"📤 Enviando digests personalizados Telegram (sin scrapear)...")
        notifier.send_user_digests()
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
