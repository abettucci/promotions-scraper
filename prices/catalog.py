"""Catálogo público persistente: sólo lecturas, sin scraping por navegación."""
from datetime import date, timedelta
from contextlib import closing
from .history import PriceHistory
from .matching import norm
from .models import category_path

CATALOG_FRESH_DAYS = 3


class Catalog:
    def __init__(self, history: PriceHistory):
        self.history = history

    def browse(self, *, q="", rubric="", sort="recent", page=1, page_size=12,
               ean="", today=None):
        today = today or date.today()
        since = (today - timedelta(days=CATALOG_FRESH_DAYS)).isoformat()
        # Literales %, _ y escapes no se convierten en comodines controlados por el usuario.
        term = norm(q).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = "%" + term + "%"
        with closing(self.history._conn()) as conn:
            conn.create_function("fold", 1, norm, deterministic=True)
            # La elección del orden no se interpola en SQL.
            rows = conn.execute("""
                WITH current AS (
                    SELECT p.key, p.name, p.brand, p.ean, p.image, p.category, p.query,
                           MIN(o.price) AS price, COUNT(*) AS store_count,
                           MIN(o.observed_at) AS observed_at
                    FROM price_products p JOIN price_catalog_offers o ON o.product_key=p.key
                    WHERE o.in_stock=1 AND o.observed_at BETWEEN ? AND ? AND o.price>0
                      AND (?='' OR fold(p.name || ' ' || COALESCE(p.brand,'')) LIKE ? ESCAPE '\\')
                      AND (?='' OR p.key=?)
                    GROUP BY p.key
                )
                SELECT *, COUNT(*) OVER() AS total FROM current
                WHERE (?='' OR category LIKE ? ESCAPE '\\' OR (?='Otros' AND COALESCE(category,'')=''))
                ORDER BY CASE WHEN ?='price_asc' THEN price END ASC,
                         CASE WHEN ?='price_desc' THEN price END DESC,
                         CASE WHEN ?='name' THEN name END COLLATE NOCASE ASC,
                         CASE WHEN ?='recent' THEN observed_at END DESC, key ASC
                LIMIT ? OFFSET ?
            """, (since, today.isoformat(), term, pattern, ean, "ean:"+ean.lstrip("0"),
                  rubric, "/"+rubric.replace("%", "\\%").replace("_", "\\_")+"/%",
                  rubric, sort, sort, sort, sort, page_size, (page-1)*page_size)).fetchall()
            facets = conn.execute("""
                SELECT p.category, COUNT(DISTINCT p.key) AS count
                FROM price_products p JOIN price_catalog_offers o ON o.product_key=p.key
                WHERE o.in_stock=1 AND o.observed_at BETWEEN ? AND ? AND o.price>0
                  AND (?='' OR fold(p.name || ' ' || COALESCE(p.brand,'')) LIKE ? ESCAPE '\\')
                  AND (?='' OR p.key=?)
                GROUP BY p.category
            """, (since, today.isoformat(), term, pattern, ean, "ean:"+ean.lstrip("0"))).fetchall()
        counts = {}
        for facet in facets:
            path = category_path(facet["category"] or "")
            name = path[0] if path else "Otros"
            counts[name] = counts.get(name, 0) + facet["count"]
        products = [{k: row[k] for k in row.keys() if k != "total"} for row in rows]
        for product in products:
            product["category_path"] = category_path(product["category"] or "")
        # Count remains accurate even when a caller requests a page beyond the end.
        total = rows[0]["total"] if rows else (counts.get(rubric, 0) if rubric else sum(counts.values()))
        return {"products": products, "total": total, "page": page, "page_size": page_size,
                "facets": [{"name": k, "count": v} for k, v in sorted(counts.items())],
                "fresh_days": CATALOG_FRESH_DAYS, "source": "catalog"}

    def product(self, key, today=None):
        today = today or date.today()
        product = self.history.product(key)
        if not product:
            return None
        with closing(self.history._conn()) as conn:
            rows = conn.execute("""
                SELECT * FROM price_catalog_offers WHERE product_key=? AND in_stock=1
                AND observed_at BETWEEN ? AND ? ORDER BY price, store
            """, (key, (today-timedelta(days=CATALOG_FRESH_DAYS)).isoformat(), today.isoformat())).fetchall()
        if not rows:
            return None
        offers = [dict(row) | {"title": product["name"], "brand": product["brand"],
                  "ean": product["ean"], "image": product["image"], "installments": 0,
                  "final_price": row["price"], "savings": 0, "qty": 1, "promo": None,
                  "multibuy": None, "deal": None, "percentage_off": None} for row in rows]
        return {"key": key, "name": product["name"], "brand": product["brand"],
                "ean": product["ean"], "image": product["image"], "category": product["category"],
                "category_path": category_path(product["category"] or ""),
                "store_count": len(rows), "offers": offers}
