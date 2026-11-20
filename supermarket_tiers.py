"""Clasifica supermercados en cadenas grandes y el resto (comercios chicos).

Las cadenas grandes se reconocen por nombre (sin acentos ni mayúsculas) para
tolerar variantes como "Supermercados Día" o "Más Online (ChangoMás)". El
filtro se aplica después por IDs de la base, así las consultas siguen
paginando en SQL.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Iterable, Optional

TIER_BIG = "grandes"
TIER_SMALL = "chicos"
TIERS = (TIER_BIG, TIER_SMALL)

# Carrefour, Día, Coto, Cencosud (Jumbo, Vea, Disco) y Chango Más / Más Online.
_BIG_CHAIN_PATTERNS = (
    r"\bcarrefour\b",
    r"\bsupermercados dia\b|^dia$",
    r"\bcoto\b",
    r"\bjumbo\b",
    r"\bvea\b",
    r"\bdisco\b",
    r"\bmas online\b|\bchango ?mas\b",
)
_BIG_RE = re.compile("|".join(f"(?:{p})" for p in _BIG_CHAIN_PATTERNS))


def _fold(name: str) -> str:
    decomposed = unicodedata.normalize("NFKD", name or "")
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(stripped.casefold().split())


def is_big_chain(name: str) -> bool:
    return bool(_BIG_RE.search(_fold(name)))


def big_chain_ids(conn) -> list[int]:
    """IDs de supermercados de cadenas grandes presentes en la base."""
    rows = conn.execute("SELECT id, name FROM supermarkets").fetchall()
    return [int(row[0]) for row in rows if is_big_chain(row[1])]


def normalize_tier(value: Optional[str]) -> Optional[str]:
    """'grandes' | 'chicos' → valor normalizado; cualquier otra cosa → None."""
    if not value:
        return None
    key = _fold(value)
    return key if key in TIERS else None


def tier_sql(tier: str, column: str, ids: Iterable[int]) -> tuple[str, list]:
    """Condición SQL sobre la columna de supermarket_id para el tier pedido.

    Si no hay cadenas grandes cargadas, "grandes" no devuelve nada y "chicos"
    devuelve todo, en vez de romper la consulta.
    """
    ids = list(ids)
    if not ids:
        return ("1 = 0", []) if tier == TIER_BIG else ("1 = 1", [])
    marks = ",".join("?" for _ in ids)
    operator = "IN" if tier == TIER_BIG else "NOT IN"
    return f"{column} {operator} ({marks})", ids
