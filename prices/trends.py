"""Variación experimental de un panel comparable, no inflación oficial.

Se compara el mismo producto en la misma tienda. Cada producto pesa igual;
sus tiendas comparables pesan igual dentro del producto. La composición no
se reemplaza silenciosamente: se informa la cobertura respecto del período base.
"""
from collections import defaultdict
from contextlib import closing
from datetime import date, timedelta

from .catalog import CATALOG_FRESH_DAYS
from .history import HEARTBEAT_DAYS, STALE_DAYS, PriceHistory
from .models import category_path

MIN_PRODUCTS = 5
MIN_COVERAGE = 0.8


def trends(history: PriceHistory, days=30, today=None):
    today = today or date.today()
    baseline = today - timedelta(days=days)
    with closing(history._conn()) as conn:
        rows = conn.execute("""
            SELECT h.*, p.category, p.name FROM price_history h
            JOIN price_products p ON p.key=h.product_key
            WHERE h.date BETWEEN ? AND ? AND h.price>0
            ORDER BY h.date
        """, ((baseline-timedelta(days=STALE_DAYS)).isoformat(), baseline.isoformat())).fetchall()
        current = conn.execute("""
            SELECT * FROM price_catalog_offers WHERE in_stock=1 AND price>0
              AND observed_at BETWEEN ? AND ?
        """, ((today-timedelta(days=CATALOG_FRESH_DAYS)).isoformat(), today.isoformat())).fetchall()
    bases = {(r["product_key"], r["store"]): dict(r) for r in rows}
    now = {(r["product_key"], r["store"]): r["price"] for r in current}
    expected, changes = defaultdict(set), defaultdict(lambda: defaultdict(list))
    for pair, row in bases.items():
        path = category_path(row["category"] or "")
        category = path[0] if path else "Otros"
        expected[category].add(row["product_key"])
        if pair in now:
            changes[category][row["product_key"]].append((now[pair]/row["price"] - 1)*100)
    result = []
    for category, keys in sorted(expected.items()):
        products = changes[category]
        coverage = len(products)/len(keys)
        sufficient = len(products) >= MIN_PRODUCTS and coverage >= MIN_COVERAGE
        change = sum(sum(v)/len(v) for v in products.values())/len(products) if products else None
        result.append({"category": category, "baseline_products": len(keys),
                       "compared_products": len(products), "coverage_pct": round(coverage*100, 1),
                       "change_pct": round(change, 2) if sufficient else None,
                       "status": "ready" if sufficient else "insufficient_data"})
    return {"days": days, "baseline": baseline.isoformat(), "as_of": today.isoformat(),
            "categories": result, "experimental": True, "min_products": MIN_PRODUCTS,
            "min_coverage_pct": MIN_COVERAGE*100,
            "baseline_max_age_days": STALE_DAYS, "current_max_age_days": CATALOG_FRESH_DAYS,
            "heartbeat_days": HEARTBEAT_DAYS}
