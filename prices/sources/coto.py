"""Adaptador para Coto Digital (www.coto.com.ar, backend Oracle ATG/Endeca).

El front Angular consume las páginas Endeca en JSON. La búsqueda es:
``/sitios/cdigi/categoria?Ntt=<texto>&Nrpp=<N>&format=json``; los productos
están en el cartridge ``Category_ResultsList`` -> ``records[].records[0]``.

Precios (lista de precios ``200``, la de la tienda online por defecto):
- ``sku.activePrice``: precio unitario de góndola.
- ``product.dtoDescuentos``: promos de la tienda. Solo se aplica como precio
  "de hoy" un descuento directo por unidad (``"25%Dto"``); las promos por
  cantidad (``2x1``, ``6x4``, ``50% 2da``: traen ``textoLlevando``/``c/u``) y las
  condicionadas (``"1 Pago 20%"`` de Comunidad Coto) se ignoran.
- ``product.dtoDescuentosMediosPago``: cuotas sin interés con todas las tarjetas.

Requiere User-Agent de navegador (con el de python-requests responde 403).
"""
from __future__ import annotations

import json
import re
from typing import Any, Optional
from urllib.parse import quote, urlsplit

import requests

from ..models import Offer
from ..registry import Store

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "es-AR,es;q=0.9",
}
_PRICE_LIST = "200"
_DIRECT_DISCOUNT = re.compile(r"^\s*\d+(?:[.,]\d+)?\s*%\s*dto\s*$", re.IGNORECASE)


def search(store: Store, query: str, limit: int = 8, timeout: float = 8.0) -> list[Offer]:
    try:
        host = store.host or "www.coto.com.ar"
        response = requests.get(
            f"https://{host}/sitios/cdigi/categoria",
            params={"Ntt": query, "Nrpp": max(1, limit), "format": "json"},
            headers=_HEADERS, timeout=timeout,
        )
        if response.status_code != 200:
            return []
        return parse_search(store, response.json())[:limit]
    except Exception:  # noqa: BLE001 - un adaptador caído no debe romper el comparador
        return []


def parse_search(store: Store, payload: Any) -> list[Offer]:
    results = _find_results_list(payload)
    if not results:
        return []
    offers = []
    for record in results.get("records") or []:
        try:
            offer = parse_record(store, record)
        except Exception:  # noqa: BLE001
            offer = None
        if offer:
            offers.append(offer)
    return offers


def parse_record(store: Store, record: dict) -> Optional[Offer]:
    inner = (record.get("records") or [record])[0]
    attrs = inner.get("attributes") or {}

    regular = _num(_first(attrs, "sku.activePrice"))
    if not regular:
        dto_price = _json(_first(attrs, "sku.dtoPrice"), {})
        regular = _num(dto_price.get("precioLista")) if isinstance(dto_price, dict) else None
    if not regular:
        return None

    price, list_price = regular, None
    promo_price = _direct_discount_price(attrs)
    if promo_price and promo_price < regular:
        price, list_price = promo_price, regular

    host = store.host or "www.coto.com.ar"
    stock_flag = _first(attrs, f"product.sDisp_{_PRICE_LIST}")
    title = _first(attrs, "product.displayName") or _first(attrs, "sku.displayName") or ""
    brand = _first(attrs, "product.brand") or _first(attrs, "product.MARCA") or ""
    image = _first(attrs, "product.largeImage.url") or _first(attrs, "product.mediumImage.url") or ""
    return Offer(
        store=store.key, store_name=store.name, merchant=store.merchant,
        title=" ".join(title.split()),
        brand=brand.strip(),
        ean=(_first(attrs, "product.eanPrincipal") or "").strip(),
        price=round(price, 2),
        list_price=round(list_price, 2) if list_price else None,
        in_stock=stock_flag == "1004" if stock_flag else True,
        url=_product_url(host, record, inner, attrs),
        image=image.strip(),
        installments=_installments(attrs),
        multibuy=_multibuy(attrs),
    )


def _multibuy(attrs: dict) -> Optional[dict]:
    """Promo por cantidad: "2x1", "6x4", "50% 2da" (traen "Llevando N" y precio c/u)."""
    from ..multibuy import parse_multibuy

    for promo in _json(_first(attrs, "product.dtoDescuentos"), []) or []:
        if not isinstance(promo, dict):
            continue
        taking = re.search(r"(\d+)", promo.get("textoLlevando") or "")
        per_unit = "c/u" in (promo.get("precioDescTextoAdicional") or "") or "c/u" in (promo.get("precioDescuento") or "")
        if not taking and not per_unit:
            continue
        found = parse_multibuy(
            promo.get("textoDescuento"), min_qty=int(taking.group(1)) if taking else None,
            unit_price=_num(promo.get("precioDesc")) if per_unit else None,
        )
        if found:
            if taking and int(taking.group(1)) >= 2:
                found.min_qty = int(taking.group(1))
            return found.to_dict()
    return None


# --- helpers -----------------------------------------------------------------

def _find_results_list(node: Any) -> Optional[dict]:
    if isinstance(node, dict):
        if node.get("@type") == "Category_ResultsList":
            return node
        children = node.values()
    elif isinstance(node, list):
        children = node
    else:
        return None
    for child in children:
        found = _find_results_list(child)
        if found:
            return found
    return None


def _first(attrs: dict, key: str) -> Optional[str]:
    value = attrs.get(key)
    if isinstance(value, list):
        value = value[0] if value else None
    return value if value is None else str(value)


def _json(raw: Optional[str], default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except ValueError:
        return default


def _num(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        number = float(str(value).replace("$", "").strip())
    except ValueError:
        return None
    return number if number > 0 else None


def _direct_discount_price(attrs: dict) -> Optional[float]:
    best = None
    for promo in _json(_first(attrs, "product.dtoDescuentos"), []) or []:
        if not isinstance(promo, dict):
            continue
        if promo.get("textoLlevando") or (promo.get("precioDescTextoAdicional") or "").strip():
            continue  # promo por cantidad (2x1, 6x4, 50% 2da...)
        if not _DIRECT_DISCOUNT.match(promo.get("textoDescuento") or ""):
            continue  # p. ej. "1 Pago 20%" (Comunidad Coto) o etiquetas sin descuento
        value = _num(promo.get("precioDesc"))
        if value and (best is None or value < best):
            best = value
    return best


def _installments(attrs: dict) -> int:
    best = 0
    for plan in _json(_first(attrs, "product.dtoDescuentosMediosPago"), []) or []:
        try:
            best = max(best, int(str((plan or {}).get("cantidadCuotas") or 0)))
        except (TypeError, ValueError):
            continue
    return best if best > 1 else 0


def _product_url(host: str, record: dict, inner: dict, attrs: dict) -> str:
    state = ((record.get("detailsAction") or {}).get("recordState")
             or (inner.get("detailsAction") or {}).get("recordState") or "")
    path = urlsplit(state).path
    record_id = _first(attrs, "record.id")
    if "/_/" in path:
        slug, _, rid = path.partition("/_/")
        rid = re.sub(r"^[A-Z]-", "R-", rid)
        return f"https://{host}/productos{quote(slug)}/_/{quote(rid)}"
    if record_id:
        return f"https://{host}/productos/p/_/R-{quote(record_id)}"
    return f"https://{host}/"
