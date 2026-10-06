"""Historial de precios de la canasta diaria (SQLite, sólo guarda cambios).

Se registra un punto por (producto, tienda) cuando el precio cambia o, como
latido, cada ``HEARTBEAT_DAYS`` días: así se sabe que la tienda sigue
publicándolo. Una tienda que no confirma el precio en ``STALE_DAYS`` días deja
de contar en la serie (un precio viejo es peor que ninguno).
"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable, Optional

HEARTBEAT_DAYS = 7
STALE_DAYS = 8
_TRACKED_PREFIXES = ("ean:", "model:")


class PriceHistory:
    def __init__(self, db_path: Optional[str | Path] = None):
        if db_path is None:
            import config
            db_path = config.PRICES_DB_PATH
        self.db_path = str(db_path)
        self._init()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        conn = self._conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS price_products (
                key TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                brand TEXT,
                ean TEXT,
                query TEXT,
                image TEXT,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS price_history (
                product_key TEXT NOT NULL,
                store TEXT NOT NULL,
                store_name TEXT NOT NULL,
                date TEXT NOT NULL,
                price REAL NOT NULL,
                list_price REAL,
                url TEXT,
                PRIMARY KEY (product_key, store, date)
            );
            CREATE INDEX IF NOT EXISTS idx_price_history_key ON price_history(product_key, date);
            CREATE TABLE IF NOT EXISTS price_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)
        conn.commit()
        conn.close()

    # ── escritura ────────────────────────────────────────────────────────────
    def record_groups(self, groups: Iterable[dict], query: str, today: Optional[date] = None) -> int:
        """Guarda los grupos devueltos por ``search_prices``. Devuelve filas nuevas."""
        today = today or date.today()
        iso = today.isoformat()
        written = 0
        conn = self._conn()
        try:
            for group in groups:
                key = group.get("key") or ""
                # Las claves por título cambian con el texto de la tienda: no
                # sirven para seguir un producto en el tiempo.
                if not key.startswith(_TRACKED_PREFIXES):
                    continue
                conn.execute(
                    "INSERT INTO price_products (key, name, brand, ean, query, image, first_seen, last_seen) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET name = excluded.name, image = excluded.image, "
                    "query = excluded.query, last_seen = excluded.last_seen",
                    (key, group.get("name", ""), group.get("brand", ""), group.get("ean", ""),
                     query, group.get("image", ""), iso, iso),
                )
                for offer in group.get("offers", []):
                    if not offer.get("in_stock", True) or not offer.get("price"):
                        continue
                    last = conn.execute(
                        "SELECT date, price FROM price_history WHERE product_key = ? AND store = ? "
                        "ORDER BY date DESC LIMIT 1", (key, offer["store"]),
                    ).fetchone()
                    if last:
                        age = (today - date.fromisoformat(last["date"])).days
                        if abs(last["price"] - offer["price"]) < 0.5 and age < HEARTBEAT_DAYS:
                            continue
                    conn.execute(
                        "INSERT OR REPLACE INTO price_history "
                        "(product_key, store, store_name, date, price, list_price, url) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (key, offer["store"], offer["store_name"], iso, offer["price"],
                         offer.get("list_price"), offer.get("url")),
                    )
                    written += 1
            conn.commit()
        finally:
            conn.close()
        return written

    def set_meta(self, key: str, value: str) -> None:
        conn = self._conn()
        conn.execute("INSERT OR REPLACE INTO price_meta (key, value) VALUES (?, ?)", (key, value))
        conn.commit()
        conn.close()

    def get_meta(self, key: str) -> Optional[str]:
        conn = self._conn()
        row = conn.execute("SELECT value FROM price_meta WHERE key = ?", (key,)).fetchone()
        conn.close()
        return row["value"] if row else None

    # ── lectura ──────────────────────────────────────────────────────────────
    def product(self, key: str) -> Optional[dict]:
        conn = self._conn()
        row = conn.execute("SELECT * FROM price_products WHERE key = ?", (key,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def series(self, key: str, days: int = 90, today: Optional[date] = None) -> dict:
        """Serie diaria (mínimo/promedio/máximo entre tiendas) con carry-forward."""
        today = today or date.today()
        start = today - timedelta(days=days)
        conn = self._conn()
        rows = conn.execute(
            "SELECT store, store_name, date, price FROM price_history "
            "WHERE product_key = ? AND date >= ? ORDER BY date",
            (key, (start - timedelta(days=STALE_DAYS)).isoformat()),
        ).fetchall()
        conn.close()
        by_store: dict[str, list[tuple[date, float]]] = {}
        names: dict[str, str] = {}
        for row in rows:
            by_store.setdefault(row["store"], []).append((date.fromisoformat(row["date"]), row["price"]))
            names[row["store"]] = row["store_name"]

        points = []
        day = start
        while day <= today:
            values = []
            for store, history in by_store.items():
                known = [(d, p) for d, p in history if d <= day]
                if known and (day - known[-1][0]).days <= STALE_DAYS:
                    values.append(known[-1][1])
            if values:
                points.append({"date": day.isoformat(), "min": min(values),
                               "avg": round(sum(values) / len(values), 2), "max": max(values),
                               "stores": len(values)})
            day += timedelta(days=1)

        current = []
        for store, history in by_store.items():
            last_date, last_price = history[-1]
            if (today - last_date).days <= STALE_DAYS:
                current.append({"store": store, "store_name": names[store], "price": last_price,
                                "date": last_date.isoformat()})
        current.sort(key=lambda item: item["price"])
        return {"key": key, "days": days, "points": points, "current": current,
                "summary": _summary(points)}


def _summary(points: list[dict]) -> Optional[dict]:
    if not points:
        return None
    lows = [p["min"] for p in points]
    low_point = min(points, key=lambda p: p["min"])
    return {"today": points[-1]["min"], "lowest": min(lows), "lowest_date": low_point["date"],
            "highest": max(p["max"] for p in points),
            "change_pct": round((points[-1]["min"] / points[0]["min"] - 1) * 100) if points[0]["min"] else 0}
