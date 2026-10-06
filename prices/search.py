"""Búsqueda en vivo en todas las tiendas, agrupada por producto."""
from __future__ import annotations

import importlib
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from typing import Optional

from .effective import apply_best_promo
from .matching import _SIZE_RE, group_key, model_code, norm, relevance
from .models import Offer, ProductGroup
from .registry import Store, stores_for

_CACHE_TTL_SECONDS = 2 * 60 * 60
_cache: dict[tuple, tuple[float, list[Offer], list[str]]] = {}
_MIN_RELEVANCE = 0.6


def _source(store: Store):
    return importlib.import_module(f"prices.sources.{store.platform}")


def _store_query(query: str) -> str:
    """Búsqueda que se manda a las tiendas: sin tamaño ("1,5 L", "900 ml").

    Varios buscadores VTEX (Jumbo/Disco/Vea) y Coto no devuelven nada si el
    texto trae el tamaño; el tamaño se usa después para ordenar por relevancia.
    """
    stripped = _SIZE_RE.sub(" ", norm(query))
    stripped = " ".join(stripped.split())
    return stripped if len(stripped.split()) >= 2 else norm(query)


def _fetch_offers(query: str, category: Optional[str]) -> tuple[list[Offer], list[str]]:
    query = _store_query(query)
    key = (query, category)
    cached = _cache.get(key)
    if cached and time.monotonic() - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1], cached[2]

    offers: list[Offer] = []
    failed: list[str] = []
    stores = stores_for(category)
    with ThreadPoolExecutor(max_workers=len(stores) or 1) as pool:
        futures = {}
        for store in stores:
            try:
                futures[pool.submit(_source(store).search, store, query)] = store
            except ModuleNotFoundError:
                failed.append(store.name)
        for future in as_completed(futures, timeout=20):
            store = futures[future]
            try:
                offers.extend(future.result())
            except Exception:
                # Una tienda caída o lenta no puede tirar la comparación.
                failed.append(store.name)
    _cache[key] = (time.monotonic(), offers, failed)
    return offers, failed


def _merge_by_model(groups: dict[str, ProductGroup], scores: dict[str, float]) -> dict[str, ProductGroup]:
    """Une grupos del mismo modelo publicados con EAN distinto o sin EAN.

    Frávega usa EAN internos y Coppel no publica EAN: el código de modelo
    (UN50U8000FGCZB) es lo que los identifica como el mismo producto.
    """
    by_code: dict[str, str] = {}
    merged: dict[str, ProductGroup] = {}
    for key, group in groups.items():
        codes = {model_code(o.title) for o in group.offers} - {""}
        # Los primeros 10 caracteres alcanzan para identificar el modelo y
        # toleran sufijos de región/color (UN50U8000FG vs UN50U8000FGCZB).
        codes = {c[:10] for c in codes if len(c) >= 7}
        target = next((by_code[c] for c in codes if c in by_code), None)
        if target is None:
            merged[key] = group
            target = key
        else:
            dest = merged[target]
            for offer in group.offers:
                same = [o for o in dest.offers if o.store == offer.store]
                if same and same[0].price <= offer.price:
                    continue
                dest.offers = [o for o in dest.offers if o.store != offer.store] + [offer]
            scores[target] = max(scores[target], scores[key])
        for code in codes:
            by_code.setdefault(code, target)
    return merged


def search_prices(query: str, *, category: Optional[str] = None, promotions: Optional[list[dict]] = None,
                  day: Optional[date] = None, methods: Optional[list[dict]] = None,
                  max_groups: int = 8, qty: int = 1) -> dict:
    """Busca ``query`` y devuelve grupos de producto con sus ofertas.

    ``promotions`` son las promos vigentes (mismo formato que el asistente);
    si se pasan, cada oferta trae su precio final con la mejor promo del día.
    """
    query = (query or "").strip()[:120]
    if len(norm(query)) < 2:
        return {"query": query, "groups": [], "failed_stores": []}
    offers, failed = _fetch_offers(query, category)

    scored = [(relevance(query, o.title, o.brand), o) for o in offers if o.in_stock]
    top = max((score for score, _ in scored), default=0)
    threshold = min(_MIN_RELEVANCE, top)
    relevant = [o for score, o in scored if score >= threshold and score > 0]

    groups: dict[str, ProductGroup] = {}
    scores: dict[str, float] = {}
    for offer in relevant:
        key = group_key(offer.title, offer.brand, offer.ean)
        group = groups.setdefault(key, ProductGroup(key=key, name=offer.title, brand=offer.brand,
                                                    ean=offer.ean, image=offer.image))
        # Una sola oferta por tienda en cada grupo (la más barata).
        same_store = [o for o in group.offers if o.store == offer.store]
        if same_store and same_store[0].price <= offer.price:
            continue
        group.offers = [o for o in group.offers if o.store != offer.store] + [Offer(**{
            k: v for k, v in offer.__dict__.items()
        })]
        scores[key] = max(scores.get(key, 0), relevance(query, offer.title, offer.brand))

    groups = _merge_by_model(groups, scores)
    for group in groups.values():
        for offer in group.offers:
            apply_best_promo(offer, promotions or [], day, methods, qty)

    ranked = sorted(
        groups.values(),
        key=lambda g: (-scores[g.key], -len({o.store for o in g.offers}),
                       g.best.final_price if g.best.final_price is not None else g.best.price),
    )
    return {
        "query": query,
        "day": (day or date.today()).isoformat(),
        "qty": max(1, int(qty)),
        "groups": [g.to_dict() for g in ranked[:max_groups]],
        "failed_stores": sorted(set(failed)),
    }
