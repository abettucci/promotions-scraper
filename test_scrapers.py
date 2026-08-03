#!/usr/bin/env python3
"""
Test runner local para scrapers de supermercados.
No requiere base de datos ni API keys (solo scrapers de supermercados).

Uso:
    python test_scrapers.py carrefour
    python test_scrapers.py dia
    python test_scrapers.py cencosud
    python test_scrapers.py carrefour,dia
    python test_scrapers.py all
"""
import asyncio
import sys
import os
import time
import json
from datetime import datetime

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault('HEADLESS', 'true')

SCRAPERS_AVAILABLE = {
    'carrefour': 'CarrefourScraper (Crawl4AI — standalone)',
    'dia':       'DiaScraper (Crawl4AI — modal extraction)',
    'cencosud':  'CencosudScraper (Crawl4AI — Jumbo)',
    'coto':      'CotoScraper (standalone)',
    'masonline': 'MasOnlineScraper (Crawl4AI — bulk expand)',
    'shell':     'ShellScraper (Crawl4AI — sin AI)',
    'puma':      'PumaScraper (requests+BS4 — sin AI)',
}


def print_sep(char='─', width=60):
    print(char * width)


def print_result(name: str, promotions: list, elapsed: float):
    print_sep('═')
    status = '✅' if promotions else '❌'
    print(f"{status} {name}: {len(promotions)} promociones  ({elapsed:.1f}s)")
    print_sep()

    if not promotions:
        print("   Sin resultados.")
        return

    for i, p in enumerate(promotions[:5], 1):
        title   = p.get('title', p.get('description', ''))[:80]
        bank    = p.get('bank', p.get('entity', ''))
        discount = p.get('discount_percentage', p.get('discount', ''))
        days    = p.get('valid_days', p.get('days', ''))
        print(f"  [{i}] {title}")
        if bank:     print(f"       Banco: {bank}")
        if discount: print(f"       Descuento: {discount}")
        if days:     print(f"       Días: {days}")
        print()

    if len(promotions) > 5:
        print(f"  ... y {len(promotions) - 5} más")


async def run_standalone(scraper_key: str):
    scraper_map = {
        'carrefour': ('scrapers.carrefour_scraper', 'CarrefourScraper'),
        'dia':       ('scrapers.dia_scraper',       'DiaScraper'),
        'cencosud':  ('scrapers.cencosud_scraper',  'CencosudScraper'),
        'coto':      ('scrapers.coto_scraper',       'CotoScraper'),
        'masonline': ('scrapers.masonline_scraper',  'MasOnlineScraper'),
        'shell':     ('scrapers.shell_scraper',      'ShellScraper'),
        'puma':      ('scrapers.puma_scraper',       'PumaScraper'),
    }
    if scraper_key not in scraper_map:
        print(f"❌ Scraper desconocido: {scraper_key}")
        return [], 0.0

    module_path, class_name = scraper_map[scraper_key]
    import importlib
    mod = importlib.import_module(module_path)
    ScraperClass = getattr(mod, class_name)

    print(f"🔍 {class_name} — iniciando...")
    scraper = ScraperClass()
    t0 = time.monotonic()
    promotions = await scraper.scrape()
    elapsed = time.monotonic() - t0
    return promotions, elapsed


async def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else 'carrefour,dia'

    if arg == 'all':
        targets = list(SCRAPERS_AVAILABLE.keys())
    else:
        targets = [s.strip().lower() for s in arg.split(',')]

    unknown = [t for t in targets if t not in SCRAPERS_AVAILABLE]
    if unknown:
        print(f"❌ Scrapers desconocidos: {unknown}")
        print(f"   Disponibles: {list(SCRAPERS_AVAILABLE.keys())}")
        sys.exit(1)

    print_sep('═')
    print(f"  Promotions Scraper — Test Local")
    print(f"  Scrapers: {', '.join(targets)}")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print_sep('═')
    print()

    results = {}

    for key in targets:
        try:
            promotions, elapsed = await run_standalone(key)

            results[key] = {'count': len(promotions), 'elapsed': elapsed, 'error': None}
            print_result(key.capitalize(), promotions, elapsed)

            # Guardar JSON para inspección
            out_file = f"test_result_{key}.json"
            with open(out_file, 'w', encoding='utf-8') as f:
                json.dump(promotions, f, ensure_ascii=False, indent=2)
            print(f"   💾 Guardado en: {out_file}")
            print()

        except Exception as e:
            results[key] = {'count': 0, 'elapsed': 0, 'error': str(e)}
            print_sep('═')
            print(f"💥 {key.capitalize()}: ERROR")
            print(f"   {e}")
            print()

    # Resumen final
    print_sep('═')
    print("  RESUMEN")
    print_sep()
    total = 0
    for key, r in results.items():
        if r['error']:
            print(f"  ❌ {key:12s} ERROR: {r['error'][:60]}")
        else:
            status = '✅' if r['count'] > 0 else '⚠️ '
            print(f"  {status} {key:12s} {r['count']:3d} promociones  ({r['elapsed']:.1f}s)")
            total += r['count']
    print_sep()
    print(f"  Total: {total} promociones en {len(targets)} scraper(s)")
    print_sep('═')


if __name__ == '__main__':
    asyncio.run(main())
