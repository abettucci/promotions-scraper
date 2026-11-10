"""IPC oficial del INDEC, cacheado en la base del historial de precios."""
from __future__ import annotations

import csv
import io
import json
from datetime import date, datetime, timedelta
from typing import Optional
from urllib.parse import urlsplit

import requests

from .history import PriceHistory

_SOURCE_URL = "https://www.indec.gob.ar/ftp/cuadros/economia/serie_ipc_divisiones.csv"
_CACHE_KEY = "indec_ipc_nacional_v1"
_CACHE_TTL = timedelta(hours=24)
_MAX_BYTES = 4_000_000


def _number(value: str) -> Optional[float]:
    try:
        result = float(value.strip().replace(".", "").replace(",", "."))
    except (AttributeError, ValueError):
        return None
    return result if result > 0 else None


def _parse_csv(content: bytes) -> list[dict]:
    text = content.decode("latin-1")
    rows = csv.DictReader(io.StringIO(text), delimiter=";")
    series = []
    for row in rows:
        if row.get("Codigo") != "0" or row.get("Region") != "Nacional":
            continue
        period = row.get("Periodo", "")
        index = _number(row.get("Indice_IPC", ""))
        if len(period) != 6 or not period.isdigit() or not index:
            continue
        year, month = int(period[:4]), int(period[4:])
        if not 2016 <= year <= 2100 or not 1 <= month <= 12:
            continue
        series.append({"month": f"{year:04d}-{month:02d}", "index": index})
    series.sort(key=lambda item: item["month"])
    if len(series) < 2:
        raise ValueError("La serie IPC del INDEC no contiene suficientes períodos")
    return series


def monthly_series(history: PriceHistory, *, now: Optional[datetime] = None) -> Optional[dict]:
    now = now or datetime.utcnow()
    encoded = history.get_meta(_CACHE_KEY)
    cached = None
    if encoded:
        try:
            cached = json.loads(encoded)
            fetched = datetime.fromisoformat(cached["fetched_at"])
            if now - fetched < _CACHE_TTL and cached.get("series"):
                return cached
        except (ValueError, TypeError, KeyError):
            cached = None

    parsed_url = urlsplit(_SOURCE_URL)
    if parsed_url.scheme != "https" or parsed_url.hostname != "www.indec.gob.ar":
        return cached
    try:
        response = requests.get(_SOURCE_URL, timeout=12, allow_redirects=False)
        if response.status_code != 200 or len(response.content) > _MAX_BYTES:
            return cached
        series = _parse_csv(response.content)
        result = {"fetched_at": now.isoformat(timespec="seconds"), "series": series}
        history.set_meta(_CACHE_KEY, json.dumps(result, separators=(",", ":")))
        return result
    except (requests.RequestException, UnicodeError, ValueError, csv.Error):
        return cached


def latest_comparison(history: PriceHistory, days: int, *, today: Optional[date] = None) -> Optional[dict]:
    """Compara contra el último IPC publicado; semanal es una equivalencia estimada."""
    cached = monthly_series(history)
    if not cached:
        return None
    series = cached["series"]
    latest = series[-1]
    previous = next((item for item in reversed(series[:-1]) if item["month"] < latest["month"]), None)
    if not previous:
        return None
    monthly_pct = (latest["index"] / previous["index"] - 1) * 100
    period_pct = monthly_pct if days >= 30 else ((1 + monthly_pct / 100) ** (days / 30) - 1) * 100
    return {
        "period": latest["month"],
        "monthly_pct": round(monthly_pct, 2),
        "comparison_pct": round(period_pct, 2),
        "estimated": days < 30,
        "source": "INDEC · IPC Nacional, nivel general",
        "fetched_at": cached["fetched_at"],
    }
