"""Canasta diaria: busca una lista fija de productos y guarda su historial."""
from __future__ import annotations

import json
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable, Optional

from .history import PriceHistory
from .search import search_ean_prices, search_prices

BASKET_PATH = Path(__file__).with_name("basket.json")
_LAST_RUN_KEY = "basket_last_run"


def load_basket(path: Path = BASKET_PATH) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def due(history: PriceHistory, every_hours: float = 20, now: Optional[datetime] = None) -> bool:
    """¿Pasó el tiempo suficiente desde la última corrida?

    El scheduler se reinicia con cada deploy; sin esto cada reinicio volvería a
    recorrer toda la canasta.
    """
    now = now or datetime.now()
    last = history.get_meta(_LAST_RUN_KEY)
    if not last:
        return True
    return now - datetime.fromisoformat(last) >= timedelta(hours=every_hours)


def run_basket(
    history: PriceHistory, *, basket: Optional[list[dict]] = None, pause: float = 0.6,
    today: Optional[date] = None, log: Callable[[str], None] = print,
    search: Callable[..., dict] = search_prices,
    search_ean: Callable[..., dict] = search_ean_prices,
    groups_per_query: int = 12,
    mark_complete: bool = True,
) -> dict:
    """Consulta cada producto y registra los cambios. Nunca levanta por una tienda caída."""
    basket = basket if basket is not None else load_basket()
    stats = {"queries": 0, "empty": 0, "errors": 0, "rows": 0, "products": 0}
    seen_keys: set[str] = set()
    for entry in basket:
        query = entry["query"]
        stats["queries"] += 1
        try:
            result = search(query, category=entry.get("category"), max_groups=max(1, min(groups_per_query, 30)))
        except Exception as error:
            stats["errors"] += 1
            log(f"   ⚠️ {query}: {type(error).__name__}: {error}")
            continue
        groups = result.get("groups") or []
        if not groups:
            stats["empty"] += 1
        stats["rows"] += history.record_groups(groups, query, today)
        seen_keys.update(g["key"] for g in groups if g["key"].startswith(("ean:", "model:")))
        time.sleep(pause)
    for ean in history.scanned_eans(limit=100):
        key = "ean:" + ean.lstrip("0")
        if key in seen_keys:
            continue
        stats["queries"] += 1
        try:
            result = search_ean(ean)
        except Exception as error:
            stats["errors"] += 1
            log(f"   ⚠️ EAN {ean}: {type(error).__name__}: {error}")
            continue
        group = result.get("group")
        if not group:
            stats["empty"] += 1
            continue
        stats["rows"] += history.record_groups([group], ean, today)
        seen_keys.add(group["key"])
        time.sleep(pause)
    stats["products"] = len(seen_keys)
    if seen_keys and mark_complete:
        history.set_meta(_LAST_RUN_KEY, datetime.now().isoformat(timespec="seconds"))
    log(f"   ✅ Canasta: {stats['queries']} búsquedas, {stats['products']} productos, "
        f"{stats['rows']} cambios de precio, {stats['empty']} sin resultados, {stats['errors']} errores")
    return stats
