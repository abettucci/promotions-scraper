"""Relevamiento paginado y reanudable de los catálogos de supermercados."""
from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from typing import Callable
from urllib.parse import urlsplit

from .categories import category_string, classify
from .history import PriceHistory
from .matching import group_key
from .models import ProductGroup
from .registry import Store, stores_for
from .sources import coto, vtex

# VTEX limita el desplazamiento a aproximadamente 2500 productos por consulta.
# Se dividen intervalos con más resultados hasta que todos sean paginables.
VTEX_PARTITION_LIMIT = 2400
MAX_PRICE_CENTS = 100_000_000_000_000  # un billón de pesos
STATE_PREFIX = "supermarket_catalog_v1:"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp(now: datetime) -> str:
    return now.isoformat(timespec="seconds")


def _new_state(store: Store, now: datetime) -> dict:
    state = {"started_at": _timestamp(now), "completed_at": None, "pages": 0,
             "records": 0, "saved_offers": 0, "unidentified_offers": 0, "last_error_at": None}
    if store.platform == "vtex":
        # VTEX indexa cientos de miles de publicaciones sin precio como cero.
        # Sólo se pueden registrar precios positivos confirmados.
        # Empezar por bandas habituales evita decenas de subdivisiones antes
        # de guardar la primera página; también se recorren las bandas altas.
        bounds = [1, 100_000, 1_000_000, 10_000_000, 100_000_000,
                  1_000_000_000, 100_000_000_000, MAX_PRICE_CENTS]
        state["pending"] = [{"low": low, "high": high, "offset": 0}
                            for low, high in reversed(list(zip(bounds, bounds[1:])))]
        state["blocked"] = []
    else:
        state["offset"] = 0
    return state


def _load(history: PriceHistory, store: Store) -> dict | None:
    raw = history.get_meta(STATE_PREFIX + store.key)
    if not raw:
        return None
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else None
    except (TypeError, ValueError):
        return None


def _save(history: PriceHistory, store: Store, state: dict) -> None:
    history.set_meta(STATE_PREFIX + store.key, json.dumps(state, separators=(",", ":")))


def _record_offers(history: PriceHistory, store: Store, offers: list, today) -> tuple[int, int]:
    groups: dict[str, ProductGroup] = {}
    unidentified = 0
    for offer in offers:
        try:
            parts = urlsplit(offer.url or "")
            if not math.isfinite(offer.price) or offer.price <= 0 or parts.scheme not in {"http", "https"} or not parts.netloc:
                continue
        except (TypeError, ValueError):
            continue
        key = group_key(offer.title, offer.brand, offer.ean, offer.store, offer.source_id)
        if not key.startswith(("ean:", "model:", "store:")):
            unidentified += 1
            continue
        group = groups.setdefault(key, ProductGroup(key=key, name=offer.title, brand=offer.brand,
                                  ean=offer.ean, image=offer.image,
                                  category=category_string(classify(offer.title, [offer.category]))))
        # Cada identidad conserva una sola oferta por comercio y página.
        if not group.offers or offer.price < group.offers[0].price:
            group.offers = [offer]
    history.record_groups([group.to_dict() for group in groups.values()], query=f"catalog:{store.key}", today=today)
    return len(groups), unidentified


def crawl_step(history: PriceHistory, store: Store, *, now: datetime | None = None,
               every_hours: float = 20, page_size: int = 50,
               fetch: Callable | None = None) -> dict:
    """Procesa una página o divide una partición; guarda el cursor después de persistirla.

    Una respuesta incompleta o una partición imposible de dividir es un error,
    nunca una señal de fin de catálogo. Repetir la página tras un reinicio es seguro.
    """
    now = now or _utcnow()
    state = _load(history, store)
    if state and state.get("completed_at"):
        started = datetime.fromisoformat(state["started_at"])
        if now - started < timedelta(hours=every_hours):
            return {"status": "waiting", "state": state}
        state = None
    if state is None:
        state = _new_state(store, now)
        _save(history, store, state)

    size = max(1, min(int(page_size), 50))
    if store.platform == "vtex":
        if not state.get("pending"):
            if state.get("blocked"):
                state["pending"], state["blocked"] = state["blocked"], []
            else:
                raise ValueError("No hay particiones VTEX pendientes en un recorrido incompleto")
        task = state["pending"][-1]
        page = (fetch or vtex.catalog_page)(store, task["offset"], task["low"], task["high"], limit=size)
        count, total = int(page["count"]), int(page["total"])
        if total > VTEX_PARTITION_LIMIT:
            low, high = task["low"], task["high"]
            if low >= high:
                state["blocked"].append(state["pending"].pop())
                state["last_error_at"] = _timestamp(now)
                _save(history, store, state)
                return {"status": "deferred" if state["pending"] else "blocked", "state": state}
            middle = (low + high) // 2
            left = {"low": low, "high": middle, "offset": 0}
            right = {"low": middle if high-low > 1 else high, "high": high, "offset": 0}
            state["pending"].pop()
            state["pending"].extend([right, left])
            if not state.get("blocked"):
                state["last_error_at"] = None
            _save(history, store, state)
            return {"status": "partitioned", "state": state}
        offset = task["offset"]
    elif store.platform == "coto":
        offset = state["offset"]
        page = (fetch or coto.catalog_page)(store, offset, limit=size)
        count, total = int(page["count"]), int(page["total"])
    else:
        raise ValueError(f"Plataforma de catálogo no soportada: {store.platform}")

    if count < 0 or total < 0 or (count == 0 and (offset > 0 or total > 0)):
        raise ValueError("La tienda devolvió una página incompleta")
    saved, unidentified = _record_offers(history, store, page["offers"], now.date())
    next_offset = offset + count
    if store.platform == "vtex":
        if next_offset >= total:
            state["pending"].pop()
        else:
            task["offset"] = next_offset
        finished = not state["pending"] and not state.get("blocked")
    else:
        state["offset"] = next_offset
        finished = next_offset >= total
    state["pages"] += 1
    state["records"] += count
    state["saved_offers"] += saved
    state["unidentified_offers"] += unidentified
    if not state.get("blocked"):
        state["last_error_at"] = None
    if finished:
        state["completed_at"] = _timestamp(now)
    _save(history, store, state)
    blocked = store.platform == "vtex" and not state["pending"] and bool(state.get("blocked"))
    return {"status": "complete" if finished else "blocked" if blocked else "page", "state": state}


def catalog_status(history: PriceHistory) -> list[dict]:
    result = []
    for store in stores_for("supermarket"):
        state = _load(history, store)
        result.append({"store": store.key, "name": store.name,
                       "started_at": state.get("started_at") if state else None,
                       "completed_at": state.get("completed_at") if state else None,
                       "pages": state.get("pages", 0) if state else 0,
                       "records": state.get("records", 0) if state else 0,
                       "saved_offers": state.get("saved_offers", 0) if state else 0,
                       "unidentified_offers": state.get("unidentified_offers", 0) if state else 0,
                       "blocked_partitions": len(state.get("blocked", [])) if state else 0,
                       "last_error_at": state.get("last_error_at") if state else None})
    return result


def mark_error(history: PriceHistory, store: Store, now: datetime | None = None) -> None:
    state = _load(history, store)
    if state:
        state["last_error_at"] = _timestamp(now or _utcnow())
        _save(history, store, state)
