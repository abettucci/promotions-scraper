"""Autocompletado: sugerencias de productos con miniatura mientras se escribe.

Dos fuentes, de la más rápida a la más lenta:
  1. Índice local: los productos de la canasta diaria (``price_products``).
  2. Consulta en vivo a unas pocas tiendas VTEX, con timeout corto y cache.

Una sugerencia sólo vale si cada palabra escrita es el *comienzo* de una
palabra del nombre o la marca ("heladera sam" → "Heladera Samsung ...").
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional

from .categories import OTHER, category_string, classify
from .matching import group_key, norm
from .models import Offer, category_path
from .registry import STORES, Store
from .search import _store_query

_FAST_STORES = ("carrefour", "jumbo", "masonline", "fravega")
_CACHE_TTL_SECONDS = 10 * 60
_LIVE_TIMEOUT = 2.0
_MIN_CHARS = 2
_cache: dict[str, tuple[float, list[dict]]] = {}


def _tokens(text: str) -> list[str]:
    return [t for t in norm(text).replace("/", " ").split() if t]


def matches(query: str, *texts: str) -> bool:
    """¿Cada palabra de ``query`` es prefijo de alguna palabra de los textos?"""
    wanted = _tokens(query)
    if not wanted:
        return False
    words = [w for text in texts for w in _tokens(text)]
    return all(any(word.startswith(token) for word in words) for token in wanted)


def _score(query: str, name: str, brand: str, stores: int) -> tuple:
    """Menor es mejor: empieza con lo escrito, luego más tiendas, luego nombre corto."""
    name_words = _tokens(name)
    first = _tokens(query)[0] if _tokens(query) else ""
    starts = 0 if name_words and name_words[0].startswith(first) else 1
    brand_hit = 0 if any(w.startswith(first) for w in _tokens(brand)) else 1
    return (starts, brand_hit, -stores, len(name))


def _live_offers(query: str, search_fn: Optional[Callable] = None) -> list[Offer]:
    from .sources import vtex

    search_fn = search_fn or vtex.search
    stores: list[Store] = [s for s in STORES if s.key in _FAST_STORES]
    offers: list[Offer] = []
    pool = ThreadPoolExecutor(max_workers=len(stores) or 1)
    try:
        futures = [pool.submit(search_fn, store, _store_query(query), 6, _LIVE_TIMEOUT) for store in stores]
        for future in as_completed(futures, timeout=_LIVE_TIMEOUT + 0.5):
            try:
                offers.extend(future.result())
            except Exception:
                continue   # una tienda lenta o caída no frena el resto
    except Exception:
        pass               # timeout global: devolvemos lo que haya llegado
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    return offers


def _live_suggestions(query: str, search_fn: Optional[Callable] = None) -> list[dict]:
    cache_key = norm(query)
    cached = _cache.get(cache_key)
    if cached and time.monotonic() - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1]
    groups: dict[str, dict] = {}
    for offer in _live_offers(query, search_fn):
        if not offer.in_stock or not matches(query, offer.title, offer.brand):
            continue
        key = group_key(offer.title, offer.brand, offer.ean)
        group = groups.setdefault(key, {"key": key, "name": offer.title, "brand": offer.brand, "image": "",
                                        "category": "", "stores": set(), "source": "live", "raw_categories": []})
        group["stores"].add(offer.store)
        group["image"] = group["image"] or offer.image
        group["raw_categories"].append(offer.category)
    result = []
    for group in groups.values():
        group["stores"] = len(group["stores"])
        group["category"] = category_string(classify(group["name"], group.pop("raw_categories")))
        result.append(group)
    if result:   # no cacheamos vacíos: pueden ser una falla pasajera de las tiendas
        _cache[cache_key] = (time.monotonic(), result)
    return result


def suggest(query: str, *, products: Optional[list[dict]] = None, live: bool = True,
            limit: int = 8, search_fn: Optional[Callable] = None) -> dict:
    """Sugerencias para lo escrito: ``products`` es el índice local (canasta)."""
    query = (query or "").strip()[:80]
    if len(norm(query)) < _MIN_CHARS:
        return {"query": query, "suggestions": [], "categories": []}

    by_key: dict[str, dict] = {}
    for product in products or []:
        if matches(query, product["name"], product.get("brand") or ""):
            by_key[product["key"]] = {**product, "stores": 0, "source": "local"}
    if live:
        for item in _live_suggestions(query, search_fn):
            current = by_key.get(item["key"])
            # La consulta en vivo trae la cantidad real de tiendas; el índice local, el nombre estable.
            # La imagen en vivo gana: la del índice local puede ser de una tienda que bloquea el hotlink.
            by_key[item["key"]] = {**(current or item), "stores": item["stores"],
                                   "image": item["image"] or (current or {}).get("image") or "",
                                   "category": item["category"] or (current or {}).get("category") or ""}

    ranked = sorted(by_key.values(), key=lambda p: _score(query, p["name"], p.get("brand") or "", p["stores"]))
    suggestions = [{
        "key": p["key"], "name": p["name"], "brand": p.get("brand") or "", "image": p.get("image") or "",
        "category": p.get("category") or "", "category_path": category_path(p.get("category") or ""),
        "stores": p["stores"],
    } for p in ranked[:limit]]

    # Las tiendas escriben igual la categoría con distinta capitalización
    # ("Aceites y vinagres" / "Aceites y Vinagres"): se agrupan sin distinguirla.
    counts: dict[tuple, list] = {}
    for item in ranked:
        path = category_path(item.get("category") or "")[:2]
        if path and norm(path[0]) != norm(OTHER):
            entry = counts.setdefault(tuple(norm(part) for part in path), [path, 0])
            entry[1] += 1
    categories = [{"name": " › ".join(path), "path": path, "count": count}
                  for path, count in sorted(counts.values(), key=lambda entry: -entry[1])[:2] if count >= 2]
    return {"query": query, "suggestions": suggestions, "categories": categories}
