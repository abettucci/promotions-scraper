"""Adaptador genérico para tiendas VTEX (Carrefour, Día, Jumbo, Frávega, ...).

Usa la API pública de catálogo que consumen los propios sitios:
``/api/catalog_system/pub/products/search?ft=<texto>&_from=0&_to=N``.
"""
from __future__ import annotations

from typing import Optional
from urllib.parse import quote

import requests

from ..models import Offer
from ..registry import Store

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; PromoAR/1.0)",
    "Accept": "application/json",
}


def search(store: Store, query: str, limit: int = 8, timeout: float = 8.0) -> list[Offer]:
    # El WAF de VTEX rechaza "ft" con espacios como "+" (400 "Scripts are not
    # allowed"); hay que mandarlos como %20.
    url = (f"https://{store.host}/api/catalog_system/pub/products/search"
           f"?ft={quote(query)}&_from=0&_to={max(0, limit - 1)}")
    response = requests.get(url, headers=_HEADERS, timeout=timeout)
    # VTEX responde 206 (Partial Content) en búsquedas paginadas.
    if response.status_code not in (200, 206):
        return []
    try:
        products = response.json()
    except ValueError:
        return []
    return [offer for product in products if (offer := parse_product(store, product))]


def parse_product(store: Store, product: dict) -> Optional[Offer]:
    items = product.get("items") or []
    if not items:
        return None
    item = items[0]
    seller = next((s for s in item.get("sellers") or [] if s.get("sellerDefault")), None) or \
        ((item.get("sellers") or [None])[0])
    offer = (seller or {}).get("commertialOffer") or {}
    # Algunas tiendas (Frávega) publican Price sin IVA y el impuesto en Tax.
    tax = offer.get("Tax") or 0
    price = (offer.get("Price") or 0) + tax
    if not price:
        return None
    installments = [
        i.get("NumberOfInstallments") or 0
        for i in offer.get("Installments") or []
        if not i.get("InterestRate")
    ]
    images = item.get("images") or []
    link = product.get("link") or ""
    if link.startswith("/"):
        link = f"https://{store.host}{link}"
    return Offer(
        store=store.key, store_name=store.name, merchant=store.merchant,
        title=(product.get("productName") or item.get("nameComplete") or "").strip(),
        brand=(product.get("brand") or "").strip(),
        ean=str(item.get("ean") or "").strip(),
        price=float(price),
        list_price=float((offer.get("ListPrice") or 0) + (tax if offer.get("ListPrice") and offer.get("ListPrice") < price else 0)) or None,
        in_stock=bool(offer.get("IsAvailable", (offer.get("AvailableQuantity") or 0) > 0)),
        url=link, image=images[0].get("imageUrl", "") if images else "",
        installments=max(installments, default=0) if max(installments, default=0) > 1 else 0,
    )
