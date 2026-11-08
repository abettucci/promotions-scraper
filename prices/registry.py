"""Tiendas consultadas por el comparador.

``merchant`` es el nombre del comercio en la DB de promos: permite cruzar el
precio con las promos bancarias de ese comercio.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Store:
    key: str
    name: str
    platform: str           # vtex | coto | supleradar | drahorro | preciosderemedios
    host: str = ""
    merchant: Optional[str] = None
    category: str = "supermarket"   # supermarket | electro | supplements | pharmacy


STORES: tuple[Store, ...] = (
    # Supermercados
    Store("carrefour", "Carrefour", "vtex", "www.carrefour.com.ar", "Carrefour"),
    Store("dia", "Día", "vtex", "diaonline.supermercadosdia.com.ar", "Supermercados Día"),
    Store("jumbo", "Jumbo", "vtex", "www.jumbo.com.ar", "Jumbo (Cencosud)"),
    Store("disco", "Disco", "vtex", "www.disco.com.ar", "Disco"),
    Store("vea", "Vea", "vtex", "www.vea.com.ar", "Vea"),
    Store("masonline", "ChangoMás", "vtex", "www.masonline.com.ar", "Más Online (ChangoMás)"),
    Store("coto", "Coto", "coto", "www.coto.com.ar", "Coto Digital"),
    # Electro y hogar
    Store("fravega", "Frávega", "vtex", "www.fravega.com", category="electro"),
    Store("naldo", "Naldo", "vtex", "www.naldo.com.ar", category="electro"),
    Store("easy", "Easy", "vtex", "www.easy.com.ar", category="electro"),
    Store("cetrogar", "Cetrogar", "vtex", "www.cetrogar.com.ar", category="electro"),
    Store("oncity", "On City", "vtex", "www.oncity.com", category="electro"),
    Store("coppel", "Coppel", "vtex", "www.coppel.com.ar", category="electro"),
    # Suplementos (comparador público de terceros)
    Store("supleradar", "SupleRadar", "supleradar", category="supplements"),
    # Farmacias. Farmacity y FarmaPlus exponen el catálogo público VTEX.
    Store("farmacity", "Farmacity", "vtex", "www.farmacity.com", category="pharmacy"),
    Store("farmaplus", "FarmaPlus", "vtex", "www.farmaplus.com.ar", category="pharmacy"),
    Store("drahorro", "Dr. Ahorro", "drahorro", "www.farmaciasdrahorro.com.ar", category="pharmacy"),
    # Referencia de precio por principio activo, no precio de una sucursal.
    Store("preciosderemedios", "Precio de referencia · Precios de Remedios",
          "preciosderemedios", "preciosderemedios.com.ar", category="pharmacy"),
)


def stores_for(category: Optional[str] = None) -> list[Store]:
    if not category:
        return [s for s in STORES if s.category not in {"supplements", "pharmacy"}]
    return [s for s in STORES if s.category == category]
