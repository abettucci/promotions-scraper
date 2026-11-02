"""Versiones públicas de promociones y última observación por comercio/promo/día.

No reconstruye condiciones ya sobrescritas ni replica una promo en días sin
observación. Los registros recuperados del estado actual se marcan legacy.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ARGENTINA = ZoneInfo("America/Argentina/Buenos_Aires")


def init_history(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS promotion_versions (
            revision TEXT PRIMARY KEY, merchant TEXT NOT NULL, payload TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS promotion_observations (
            merchant TEXT NOT NULL, identity TEXT NOT NULL, observed_on TEXT NOT NULL,
            revision TEXT NOT NULL REFERENCES promotion_versions(revision),
            observed_at TEXT NOT NULL, provenance TEXT NOT NULL,
            PRIMARY KEY (merchant, identity, observed_on)
        );
        CREATE INDEX IF NOT EXISTS idx_promo_observations_day
            ON promotion_observations(merchant, observed_on);
    """)


def _values(value):
    if not value:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            return [value]
    return [str(item) for item in value] if isinstance(value, list) else [str(value)]


def capture_promotion(conn, promotion_id, *, observed_at=None, provenance="scrape", with_terms=True):
    row = conn.execute("""
        SELECT p.*, s.name AS merchant, t.raw_text AS tc_raw, t.exclusions AS tc_exclusions,
               t.requirements AS tc_requirements, t.min_purchase AS tc_minimum,
               t.valid_days AS tc_days, t.max_discount AS tc_tope
        FROM promotions p JOIN supermarkets s ON s.id=p.supermarket_id
        LEFT JOIN terms_conditions t ON t.promotion_id=p.id WHERE p.id=?
    """, (promotion_id,)).fetchone()
    if row is None:
        return
    row = dict(row)
    if not with_terms:
        for key in ("tc_raw", "tc_exclusions", "tc_requirements", "tc_minimum", "tc_days", "tc_tope"):
            row[key] = None
    observed_at = observed_at or datetime.now(timezone.utc)
    if isinstance(observed_at, str):
        try:
            observed_at = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
        except ValueError:
            return
    if not observed_at.tzinfo:
        # SQLite CURRENT_TIMESTAMP y los scraped_at existentes usan UTC.
        observed_at = observed_at.replace(tzinfo=timezone.utc)
    observed = observed_at.astimezone(timezone.utc).isoformat()
    day = observed_at.astimezone(ARGENTINA).date().isoformat()
    payload = {key: row.get(key) for key in (
        "merchant", "title", "discount", "bank", "wallet", "card_type", "payment_method",
        "store_types", "valid_days", "valid_from", "valid_until", "url", "tope", "min_purchase",
        "acumulable", "is_active", "source", "coverage", "mobility_kind",
    )}
    payload["exclusions"] = _values(row.get("tc_exclusions") or row.get("exclusions"))
    payload["requirements"] = _values(row.get("tc_requirements") or row.get("requirements"))
    payload["terms_raw"] = row.get("tc_raw") or row.get("terms_raw") or ""
    payload["min_purchase"] = row.get("tc_minimum") or payload["min_purchase"]
    payload["tope"] = row.get("tc_tope") or payload["tope"]
    if row.get("tc_days") and _values(row["tc_days"]):
        payload["valid_days"] = ", ".join(_values(row["tc_days"]))
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    revision = hashlib.sha256(encoded.encode()).hexdigest()
    identity = hashlib.sha256(json.dumps([row["merchant"], row.get("source"), row["title"],
                                         row.get("bank")], ensure_ascii=False).encode()).hexdigest()
    conn.execute("INSERT OR IGNORE INTO promotion_versions VALUES (?, ?, ?)",
                 (revision, row["merchant"], encoded))
    conn.execute("""
        INSERT INTO promotion_observations VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(merchant, identity, observed_on) DO UPDATE SET
            revision=excluded.revision, observed_at=excluded.observed_at, provenance=excluded.provenance
        WHERE (excluded.provenance='scrape' AND promotion_observations.provenance='legacy')
           OR (excluded.provenance=promotion_observations.provenance
               AND excluded.observed_at>promotion_observations.observed_at)
    """, (row["merchant"], identity, day, revision, observed, provenance))


def bootstrap_history(conn):
    """Sin inventar fechas: sólo el último scraped_at conservado en cada fila."""
    for row in conn.execute("SELECT id, scraped_at FROM promotions").fetchall():
        if row["scraped_at"]:
            capture_promotion(conn, row["id"], observed_at=row["scraped_at"], provenance="legacy")


def merge_history(conn, source_path):
    """Copia a users.db (volumen persistente) sólo historia pública, nunca usuarios."""
    conn.execute("ATTACH DATABASE ? AS promo_source", (str(source_path),))
    try:
        exists = conn.execute("SELECT 1 FROM promo_source.sqlite_master WHERE type='table' AND name='promotion_observations'").fetchone()
        if exists:
            conn.execute("INSERT OR IGNORE INTO promotion_versions SELECT * FROM promo_source.promotion_versions")
            conn.execute("""
                INSERT INTO promotion_observations SELECT * FROM promo_source.promotion_observations WHERE 1
                ON CONFLICT(merchant, identity, observed_on) DO UPDATE SET
                    revision=excluded.revision, observed_at=excluded.observed_at, provenance=excluded.provenance
                WHERE (excluded.provenance='scrape' AND promotion_observations.provenance='legacy')
                   OR (excluded.provenance=promotion_observations.provenance
                       AND excluded.observed_at>promotion_observations.observed_at)
            """)
            conn.commit()
    finally:
        conn.execute("DETACH DATABASE promo_source")
