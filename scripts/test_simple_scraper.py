"""
Test del scraper simple de Carrefour (sin navegador)
"""
import sys
sys.path.insert(0, '.')

from scrapers.carrefour_simple_scraper import CarrefourSimpleScraper
from database import Database
from terms_parser import TermsParser
import config

def test_simple_scraper():
    """Prueba el scraper simple"""
    print("=" * 60)
    print("🧪 PROBANDO SCRAPER SIMPLE DE CARREFOUR")
    print("=" * 60)
    print()
    
    # Crear scraper
    scraper = CarrefourSimpleScraper()
    
    # Scrapear
    promotions = scraper.scrape()
    
    print()
    print("=" * 60)
    print(f"📊 RESULTADOS: {len(promotions)} promociones")
    print("=" * 60)
    print()
    
    if not promotions:
        print("❌ No se encontraron promociones")
        print("\n💡 Revisa el archivo debug_carrefour_simple.html")
        return
    
    # Mostrar promociones
    for idx, promo in enumerate(promotions, 1):
        print(f"\n📌 Promoción {idx}:")
        print(f"   Título: {promo['title']}")
        print(f"   Descuento: {promo['discount']}")
        print(f"   Banco: {promo['bank']}")
        print(f"   Billetera: {promo['wallet']}")
        print(f"   Método de pago: {promo['payment_method']}")
        print(f"   Tipos de tienda: {promo['store_types']}")
        print(f"   Días válidos: {promo['valid_days']}")
        print(f"   Válido desde: {promo['valid_from']}")
        print(f"   Válido hasta: {promo['valid_until']}")
        print(f"   Exclusiones: {promo['exclusions'][:100] if promo['exclusions'] else 'N/A'}...")
        print(f"   T&C: {promo['terms_raw'][:100] if promo['terms_raw'] else 'N/A'}...")
    
    # Preguntar si guardar en DB
    print("\n" + "=" * 60)
    save = input("\n💾 ¿Guardar en la base de datos? (s/n): ").strip().lower()
    
    if save == 's':
        print("\n💾 Guardando en base de datos...")
        
        db = Database()
        parser = TermsParser()
        
        # Insertar supermercado
        supermarket_id = db.insert_supermarket('Carrefour', scraper.url)
        
        # Guardar promociones
        for promo in promotions:
            promotion_id = db.insert_promotion(supermarket_id, promo)
            
            if promotion_id and promo.get('terms_raw'):
                terms_data = parser.parse(promo['terms_raw'])
                db.insert_terms(promotion_id, terms_data)
        
        db.update_supermarket_scraped(supermarket_id)
        
        print(f"✅ {len(promotions)} promociones guardadas")
        print(f"📂 Base de datos: {config.DATABASE_PATH}")
    else:
        print("\n⏭️  No se guardó en la base de datos")
    
    print()

if __name__ == "__main__":
    test_simple_scraper()

