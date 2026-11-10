"""Cotizaciones privadas de la lista. Nunca usa $0 como precio ni mezcla usuarios."""
from __future__ import annotations

import json
import math
from contextlib import closing
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from .categories import classify
from .catalog import Catalog
from .history import PriceHistory
from .models import category_path
from .registry import STORES

QUOTE_MAX_AGE = timedelta(days=3)
REFRESH_TTL = timedelta(hours=1)


def positive_price(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and 0 < value <= 1e12


def category_for(product):
    path = category_path(str(product.get("category") or ""))
    if not path or path == ["Otros"]:
        path = classify(str(product.get("product_name") or product.get("name") or ""))
    return path or ["Otros"]


def safe_url(value):
    try:
        parts = urlsplit(str(value or ""))
        return str(value) if parts.scheme in {"https", "http"} and parts.netloc else ""
    except ValueError:
        return ""


class WatchlistQuotes:
    def __init__(self, history: PriceHistory):
        self.history = history

    def load(self, user_id, key):
        with closing(self.history._conn()) as conn:
            row = conn.execute("SELECT group_json, checked_at FROM watchlist_quotes WHERE user_id=? AND product_key=?",
                               (user_id, key)).fetchone()
        if not row:
            return None
        try:
            checked = datetime.fromisoformat(row["checked_at"])
            return {"group": json.loads(row["group_json"]), "checked_at": checked} if checked.tzinfo else None
        except (ValueError, TypeError):
            return None

    def save(self, user_id, key, group, now=None):
        now = now or datetime.now(timezone.utc)
        stores = {store.key: store for store in STORES}
        offers = {}
        for item in (group or {}).get("offers", []):
            store = stores.get(item.get("store"))
            price, url = item.get("price"), safe_url(item.get("url"))
            if not store or not positive_price(price) or not item.get("in_stock", True) or not url:
                continue
            if store.key in offers and offers[store.key]["price"] <= price:
                continue
            # Sólo campos públicos de la oferta: nada de precios finales del usuario,
            # medios de pago, preguntas, títulos de promos o referencias personales.
            offers[store.key] = {"store": store.key, "store_name": store.name, "merchant": store.merchant,
                                 "price": float(price), "url": url, "modality": "online",
                                 "list_price": item.get("list_price") if positive_price(item.get("list_price")) else None,
                                 "observed_at": now.isoformat()}
        payload = {"key": key, "offers": list(offers.values()),
                   "failed_stores": [str(s)[:80] for s in ((group or {}).get("failed_stores") or [])][:20]}
        with closing(self.history._conn()) as conn:
            conn.execute("INSERT INTO watchlist_quotes VALUES (?, ?, ?, ?) "
                         "ON CONFLICT(user_id,product_key) DO UPDATE SET "
                         "group_json=excluded.group_json, checked_at=excluded.checked_at",
                         (user_id, key, json.dumps(payload, allow_nan=False), now.isoformat()))
            conn.execute("DELETE FROM watchlist_quotes WHERE checked_at<?", ((now-timedelta(days=7)).isoformat(),))
            conn.commit()
        return payload

    def offers(self, user_id, product, now=None):
        now = now or datetime.now(timezone.utc)
        key = product["product_key"]
        cached = self.load(user_id, key)
        if cached and timedelta(0) <= now-cached["checked_at"] <= QUOTE_MAX_AGE:
            return cached["group"].get("offers", [])
        # El catálogo público es un respaldo para identidades estables, no para
        # coincidencias difusas por título. Ninguna lectura dispara scraping.
        if key.startswith(("ean:", "model:", "store:")):
            group = Catalog(self.history).product(key, today=now.date())
            if group:
                stores = {store.key: store for store in STORES}
                return [{"store": o["store"], "store_name": o["store_name"], "price": o["price"],
                         "list_price": o.get("list_price"), "url": safe_url(o.get("url")),
                         "merchant": stores[o["store"]].merchant, "modality": "online",
                         "observed_at": o["observed_at"]}
                        for o in group["offers"] if o["store"] in stores and positive_price(o["price"])]
        return []

    def enrich(self, user_id, products, now=None):
        enriched = []
        for product in products:
            offers = self.offers(user_id, product, now)
            best = min(offers, key=lambda o: o["price"]) if offers else None
            path = category_for(product)
            enriched.append(dict(product, category="/"+"/".join(path)+"/", category_path=path,
                                 best_offer=best, offers=offers))
        return enriched

    def refresh(self, user_id, products, *, now=None, search=None):
        from .search import search_prices
        search = search or search_prices
        now = now or datetime.now(timezone.utc)
        results = []
        queries = {}
        for product in products:
            key = product["product_key"]
            cached = self.load(user_id, key)
            if cached and timedelta(0) <= now-cached["checked_at"] < REFRESH_TTL:
                results.append({"id": product["id"], "status": "cached" if cached["group"].get("offers") else "missing"})
                continue
            try:
                query = product["query"]
                if query not in queries:
                    queries[query] = search(query, max_groups=30)
                result = queries[query]
                group = next((g for g in result.get("groups", []) if g.get("key") == key), None)
                if not group and result.get("failed_stores"):
                    # Una falla de transporte no invalida datos anteriores ni renueva su fecha.
                    results.append({"id": product["id"], "status": "error"})
                    continue
                saved = self.save(user_id, key, dict(group or {}, failed_stores=result.get("failed_stores", [])), now)
                results.append({"id": product["id"], "status": "updated" if saved["offers"] else "missing"})
            except Exception:
                results.append({"id": product["id"], "status": "error"})
        return results
