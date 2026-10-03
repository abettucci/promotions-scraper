"""Suplementos vía el comparador público SupleRadar (ver supplement_prices.py)."""
from __future__ import annotations

from supplement_prices import find_supplement_price

from ..models import Offer
from ..registry import Store


def search(store: Store, query: str, limit: int = 8, timeout: float = 8.0) -> list[Offer]:
    result = find_supplement_price(query)
    if not result or not result.price:
        return []
    return [Offer(
        store=store.key, store_name=f"{result.store_name} (vía SupleRadar)", merchant=None,
        title=result.product_name, price=float(result.price), url=result.source_url,
    )]
