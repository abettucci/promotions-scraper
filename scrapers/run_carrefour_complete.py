#!/usr/bin/env python3
"""
Script completo: Migra la base de datos y ejecuta el scraper
"""
import os
import subprocess
import sys
import asyncio

def migrate_database():
    """Ejecuta las migraciones necesarias"""
    print("="*100)
    print("PASO 1: MIGRANDO BASE DE DATOS")
    print("="*100)
    
    # Ejecutar migración
    result = subprocess.run([sys.executable, 'migrate_add_tope.py'], 
                          capture_output=False, 
                          text=True)
    
    if result.returncode != 0:
        print("⚠️  Advertencia: La migración tuvo problemas, pero continuaremos...")
    
    print()

async def run_scraper():
    """Ejecuta el scraper"""
    print("="*100)
    print("PASO 2: EJECUTANDO SCRAPER")
    print("="*100)
    print()
    
    # Importar y ejecutar el scraper
    from scrapers.carrefour_ultimate import CarrefourUltimateScraper
    
    scraper = CarrefourUltimateScraper()
    promotions = await scraper.scrape()
    
    print(f"\n{'='*100}")
    print(f"\n📊 RESUMEN FINAL: {len(promotions)} promociones extraídas y guardadas")
    print(f"\n{'='*100}")
    
    return promotions

def view_promotions():
    """Muestra las promociones"""
    print("\n" + "="*100)
    print("PASO 3: ¿DESEAS VER LAS PROMOCIONES?")
    print("="*100)
    
    try:
        response = input("\n¿Ver promociones ahora? (s/n): ").strip().lower()
        if response == 's':
            subprocess.run([sys.executable, 'view_promotions.py'])
    except KeyboardInterrupt:
        print("\n\n✅ Proceso completado. Usa 'python view_promotions.py' para ver las promociones.")

async def main():
    print("\n")
    print("="*100)
    print("🚀 SCRAPER COMPLETO DE CARREFOUR - BANCO DESCUENTOS")
    print("="*100)
    print()
    
    # Paso 1: Migrar
    migrate_database()
    
    # Paso 2: Scrapear
    promotions = await run_scraper()
    
    # Paso 3: Ver (opcional)
    if promotions:
        view_promotions()
    
    print("\n✅ Proceso completo finalizado\n")

if __name__ == "__main__":
    asyncio.run(main())

