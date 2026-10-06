from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional


@dataclass
class Offer:
    """Una publicación de un producto en una tienda."""

    store: str                 # clave del registro (p. ej. "carrefour")
    store_name: str            # nombre visible ("Carrefour")
    merchant: Optional[str]    # comercio en la DB de promos, si existe
    title: str
    price: float
    url: str
    brand: str = ""
    ean: str = ""
    list_price: Optional[float] = None
    in_stock: bool = True
    image: str = ""
    installments: int = 0      # máximo de cuotas sin interés publicado
    # Precio final con la mejor promo bancaria aplicable (lo completa effective.py)
    final_price: Optional[float] = None
    savings: float = 0.0
    promo: Optional[dict] = None
    # Promo por cantidad ("2do al 50%") tal como la publica la tienda, y qué
    # conviene al llevar ``qty`` unidades: total a pagar y de dónde sale el ahorro.
    multibuy: Optional[dict] = None
    qty: int = 1
    total: Optional[float] = None
    deal: Optional[str] = None      # "multibuy" | "bank" | None
    category: str = ""              # "/Almacén/Aceites/" tal como lo publica la tienda

    @property
    def percentage_off(self) -> Optional[int]:
        # VTEX a veces publica ListPrice inflados (x80); un "% off" absurdo
        # confunde más de lo que ayuda.
        if not self.list_price or self.list_price <= self.price:
            return None
        pct = round((1 - self.price / self.list_price) * 100)
        return pct if 0 < pct < 80 else None

    def to_dict(self) -> dict:
        data = asdict(self)
        data["percentage_off"] = self.percentage_off
        return data


@dataclass
class ProductGroup:
    """Mismo producto en varias tiendas, ordenado por precio."""

    key: str
    name: str
    brand: str = ""
    ean: str = ""
    image: str = ""
    offers: list[Offer] = field(default_factory=list)

    @property
    def best(self) -> Offer:
        return min(self.offers, key=lambda o: o.final_price if o.final_price is not None else o.price)

    def to_dict(self) -> dict:
        offers = sorted(self.offers, key=lambda o: o.final_price if o.final_price is not None else o.price)
        return {
            "key": self.key, "name": self.name, "brand": self.brand, "ean": self.ean,
            "image": self.image, "store_count": len({o.store for o in offers}),
            "offers": [o.to_dict() for o in offers],
        }
