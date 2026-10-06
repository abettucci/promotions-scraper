"""Adaptador genérico para tiendas VTEX (Carrefour, Día, Jumbo, Frávega, ...).

Usa la API pública de catálogo que consumen los propios sitios:
``/api/catalog_system/pub/products/search?ft=<texto>&_from=0&_to=N``.
"""
from __future__ import annotations

from typing import Optional
from urllib.parse import quote

import requests

from ..models import Offer
from ..multibuy import parse_multibuy
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
    categories = product.get("categories") or []
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
        multibuy=_multibuy(product, offer),
        # categories[0] es la ruta más específica ("/Almacén/Aceites/Girasol/")
        category=categories[0] if categories and isinstance(categories[0], str) else "",
    )


def _teaser_name(teaser: dict) -> str:
    """Los teasers de VTEX usan claves como "<Name>k__BackingField"."""
    return str(teaser.get("<Name>k__BackingField") or teaser.get("Name") or teaser.get("name") or "")


def _multibuy(product: dict, offer: dict) -> Optional[dict]:
    """Promo por cantidad del producto, en orden de confianza.

    1. Teaser con la promo y su cantidad mínima (Carrefour: "2do al 50% Max 48
       unidades"). Los teasers de tarjeta (RestrictionsBins) no son por cantidad.
    2. Etiqueta de campaña en los clusters (Jumbo/Vea: "Hasta 2do al 70% en
       Almacén y Bebidas"): sólo orientativa, no se calcula.
    """
    for teaser in offer.get("Teasers") or []:
        if not isinstance(teaser, dict):
            continue
        conditions = teaser.get("<Conditions>k__BackingField") or {}
        minimum = conditions.get("<MinimumQuantity>k__BackingField") or None
        found = parse_multibuy(_teaser_name(teaser), min_qty=minimum)
        if found:
            if minimum and minimum >= 2 and found.kind != "tag":
                found.min_qty = int(minimum)
            return found.to_dict()
    clusters = product.get("clusterHighlights")
    names = list(clusters.values()) if isinstance(clusters, dict) else []
    for name in names:
        found = parse_multibuy(name)
        if found:
            found.exact = False
            return found.to_dict()
    return None
