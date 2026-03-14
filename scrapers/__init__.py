"""
Scrapers específicos para cada supermercado

Modos disponibles para Carrefour:
- CarrefourScraper: Playwright (default) con fallback a simple/scrapling
- CarrefourSimpleScraper: Solo requests, sin browser
- CarrefourScraplingScraper: Adaptive scraping con Scrapling

Configurar via env vars:
- USE_SCRAPLING=true -> Usa Scrapling (recomendado)
- USE_SIMPLE_SCRAPER=true -> Usa requests sin browser
"""
from .carrefour_scraper import CarrefourScraper
from .carrefour_simple_scraper import CarrefourSimpleScraper

try:
    from .carrefour_scrapling import CarrefourScraplingScraper
except ImportError:
    CarrefourScraplingScraper = None

__all__ = [
    'CarrefourScraper',
    'CarrefourSimpleScraper', 
    'CarrefourScraplingScraper',
]
