"""Cotizaciones históricas de venta para expresar el índice en dólares."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Optional
from urllib.parse import urlsplit

import requests

from .history import PriceHistory

_HOUSES = {"usd_official": "oficial", "usd_blue": "blue"}
_HOST = "api.argentinadatos.com"
_CACHE_TTL = timedelta(hours=24)
_MAX_BYTES = 4_000_000


def rates(history: PriceHistory, currency: str, *, now: Optional[datetime] = None) -> Optional[dict]:
    house = _HOUSES.get(currency)
    if not house:
        return None
    now = now or datetime.now()
    key = f"exchange_{currency}_v1"
    encoded = history.get_meta(key)
    cached = None
    if encoded:
        try:
            cached = json.loads(encoded)
            if now - datetime.fromisoformat(cached["fetched_at"]) < _CACHE_TTL and cached.get("series"):
                return cached
        except (ValueError, TypeError, KeyError):
            cached = None

    url = f"https://{_HOST}/v1/cotizaciones/dolares/{house}"
    parsed_url = urlsplit(url)
    if parsed_url.scheme != "https" or parsed_url.hostname != _HOST:
        return cached
    try:
        response = requests.get(url, timeout=12, allow_redirects=False)
        if response.status_code != 200 or len(response.content) > _MAX_BYTES:
            return cached
        payload = response.json()
        series = []
        if not isinstance(payload, list):
            return cached
        for row in payload:
            if not isinstance(row, dict):
                continue
            try:
                day = date.fromisoformat(str(row.get("fecha", ""))[:10])
                sale = float(row.get("venta"))
            except (TypeError, ValueError):
                continue
            if row.get("casa") == house and sale > 0:
                series.append({"date": day.isoformat(), "sale": sale})
        series.sort(key=lambda item: item["date"])
        if not series:
            return cached
        result = {"fetched_at": now.isoformat(timespec="seconds"), "series": series,
                  "source": "ArgentinaDatos API · datos de DolarApi"}
        history.set_meta(key, json.dumps(result, separators=(",", ":")))
        return result
    except (requests.RequestException, ValueError):
        return cached
