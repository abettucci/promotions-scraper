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
__all__ = [
    'CarrefourScraper',
    'CarrefourSimpleScraper', 
    'CarrefourScraplingScraper',
]


def __getattr__(name):
    """Evita importar dependencias opcionales al pedir otro scraper del paquete."""
    if name == 'CarrefourScraper':
        from .carrefour_scraper import CarrefourScraper
        return CarrefourScraper
    if name == 'CarrefourSimpleScraper':
        from .carrefour_simple_scraper import CarrefourSimpleScraper
        return CarrefourSimpleScraper
    if name == 'CarrefourScraplingScraper':
        try:
            from .carrefour_scrapling import CarrefourScraplingScraper
            return CarrefourScraplingScraper
        except ImportError:
            return None
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
