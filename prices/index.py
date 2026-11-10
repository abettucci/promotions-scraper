"""Índice semanal encadenado de productos comparables del catálogo observado."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from bisect import bisect_right
from contextlib import closing

from .exchange import rates as exchange_rates
from .history import STALE_DAYS, PriceHistory
from .models import category_path

_RANGES = {"year": "year", "3m": 90, "6m": 180, "1y": 365, "all": None}
_MIN_PRODUCTS = 5
_MIN_COVERAGE = 0.6


def price_index(history: PriceHistory, *, period: str = "1y", currency: str = "ars",
                today: date | None = None) -> dict:
    today = today or date.today()
    if period not in _RANGES:
        raise ValueError("Período inválido")
    if currency not in {"ars", "usd_official", "usd_blue"}:
        raise ValueError("Moneda inválida")
    fx = exchange_rates(history, currency) if currency != "ars" else None
    fx_dates = [date.fromisoformat(item["date"]) for item in fx["series"]] if fx else []

    def rate_at(day: date):
        if currency == "ars":
            return 1.0
        position = bisect_right(fx_dates, day) - 1
        if position < 0 or (day - fx_dates[position]).days > 4:
            return None
        return float(fx["series"][position]["sale"])

    with closing(history._conn()) as conn:
        rows = conn.execute("""
            SELECT h.product_key, h.store, h.date, h.price, p.category
            FROM price_history h JOIN price_products p ON p.key = h.product_key
            WHERE h.price > 0 ORDER BY h.date
        """).fetchall()
        current = conn.execute("""
            SELECT c.product_key, c.store, c.observed_at, c.price, p.category
            FROM price_catalog_offers c JOIN price_products p ON p.key = c.product_key
            WHERE c.in_stock = 1 AND c.price > 0
        """).fetchall()

    if period == "year":
        range_start = date(today.year, 1, 1)
    elif _RANGES[period] is None:
        range_start = min((date.fromisoformat(row["date"]) for row in rows), default=today)
    else:
        range_start = today - timedelta(days=int(_RANGES[period]))
    # Cerrar cada punto al domingo para que los porcentajes no mezclen semanas
    # completas con una fracción variable de la semana actual.
    last_anchor = today - timedelta(days=(today.weekday() + 1) % 7)
    first_anchor = range_start + timedelta(days=(6 - range_start.weekday()) % 7)
    anchors = []
    anchor = first_anchor
    while anchor <= last_anchor:
        anchors.append(anchor)
        anchor += timedelta(days=7)
    if not anchors:
        anchors = [last_anchor]
    base_anchor = anchors[0] - timedelta(days=7)
    anchors.insert(0, base_anchor)
    oldest_needed = base_anchor - timedelta(days=STALE_DAYS)

    observations: dict[tuple[str, str], list[tuple[date, float]]] = defaultdict(list)
    categories: dict[str, str] = {}
    for row in rows:
        observed = date.fromisoformat(row["date"])
        if observed < oldest_needed:
            continue
        key = (row["product_key"], row["store"])
        observations[key].append((observed, float(row["price"])))
        path = category_path(row["category"] or "")
        categories[row["product_key"]] = path[0] if path else "Otros"
    for values in observations.values():
        values.sort(key=lambda item: item[0])

    latest = {}
    for row in current:
        try:
            observed = date.fromisoformat(str(row["observed_at"])[:10])
        except ValueError:
            continue
        if observed <= today and (today - observed).days <= 3:
            key = (row["product_key"], row["store"])
            existing = latest.get(key)
            if existing is None or observed >= existing[0]:
                latest[key] = (observed, float(row["price"]))

    snapshots = []
    for anchor in anchors:
        snapshot = {}
        for pair, values in observations.items():
            dates = [item[0] for item in values]
            pos = bisect_right(dates, anchor) - 1
            if pos >= 0:
                observed, amount = values[pos]
                if (anchor - observed).days <= STALE_DAYS:
                    snapshot[pair] = amount
        if anchor == last_anchor:
            snapshot.update({pair: item[1] for pair, item in latest.items() if item[0] <= anchor})
        snapshots.append(snapshot)

    all_categories = sorted(set(categories.values()))
    series = []
    for category in all_categories:
        value = 100.0
        points = [{"date": anchors[0].isoformat(), "index": 0.0, "weekly_change_pct": None,
                   "products": 0, "coverage_pct": 0.0}]
        for index in range(1, len(anchors)):
            previous, current_snapshot = snapshots[index-1], snapshots[index]
            previous_rate, current_rate = rate_at(anchors[index-1]), rate_at(anchors[index])
            base_products = {product for product, store in previous if categories.get(product) == category}
            per_product: dict[str, list[float]] = defaultdict(list)
            if previous_rate is None or current_rate is None:
                points.append({"date": anchors[index].isoformat(), "index": None,
                               "weekly_change_pct": None, "products": 0, "coverage_pct": 0.0})
                continue
            for pair, amount in current_snapshot.items():
                product, _store = pair
                if categories.get(product) != category or pair not in previous:
                    continue
                prior = previous[pair]
                if prior > 0:
                    per_product[product].append(((amount/current_rate)/(prior/previous_rate) - 1)*100)
            coverage = len(per_product) / len(base_products) if base_products else 0.0
            enough = len(per_product) >= _MIN_PRODUCTS and coverage >= _MIN_COVERAGE
            weekly = (sum(sum(changes)/len(changes) for changes in per_product.values()) / len(per_product)
                      if enough else None)
            if weekly is not None:
                value *= 1 + weekly/100
            points.append({"date": anchors[index].isoformat(),
                           "index": round(value - 100, 2) if weekly is not None else None,
                           "weekly_change_pct": round(weekly, 2) if weekly is not None else None,
                           "products": len(per_product), "coverage_pct": round(coverage*100, 1)})
        series.append({"category": category, "points": points,
                       "last_change_pct": next((p["weekly_change_pct"] for p in reversed(points)
                                                 if p["weekly_change_pct"] is not None), None),
                       "products": max((p["products"] for p in points), default=0)})

    return {"period": period, "currency": currency, "from": anchors[0].isoformat(), "to": anchors[-1].isoformat(),
            "series": series, "min_products": _MIN_PRODUCTS,
            "min_coverage_pct": _MIN_COVERAGE*100,
            "exchange_source": fx["source"] if fx else None,
            "exchange_updated_at": fx["fetched_at"] if fx else None,
            "method": "Variación semanal del mismo producto en el mismo comercio, promedio por producto y encadenado desde el inicio del período.",
            "experimental": True}
