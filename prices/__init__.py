"""Comparador de precios entre tiendas (consulta en vivo, sin catálogo completo).

``search_prices`` consulta en paralelo los catálogos públicos de las tiendas,
agrupa las publicaciones del mismo producto (por EAN o modelo) y, si se le
pasan las promos vigentes, calcula el precio final con la mejor promo bancaria.
"""
from .models import Offer, ProductGroup
from .search import search_prices

__all__ = ["Offer", "ProductGroup", "search_prices"]
