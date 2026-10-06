"""Alertas de baja de precio: alta, parseo desde el bot y revisión periódica."""
from __future__ import annotations

import html
import re
from typing import Callable, Optional

from .search import search_prices

_TARGET_RE = re.compile(
    r"(?:\s+(?:a|por|en|menos\s+de|menor\s+a|hasta|<=?)\s*)?\$\s*([\d.]+(?:,\d+)?)\s*$", re.I,
)
_MIN_DROP = 0.01   # sólo avisamos bajas de al menos 1 %
_SEARCH_GROUPS = 8   # igual que la página: el producto elegido tiene que reaparecer
_CHECK_GROUPS = 12   # el ranking varía de un día a otro; margen para no perder el producto


def parse_alert_args(text: str) -> tuple[str, Optional[float]]:
    """'leche 1l a $2000' → ('leche 1l', 2000.0); sin precio → (texto, None)."""
    text = (text or "").strip()
    match = _TARGET_RE.search(text)
    if not match:
        return text, None
    value = float(match.group(1).replace(".", "").replace(",", "."))
    return text[:match.start()].strip(), value if value > 0 else None


def _best(group: dict) -> Optional[dict]:
    offers = [o for o in group.get("offers", []) if o.get("in_stock", True) and o.get("price")]
    return min(offers, key=lambda o: o["price"]) if offers else None


def create_alert(user_db, user_id: int, query: str, *, key: Optional[str] = None,
                 target: Optional[float] = None, search: Callable[..., dict] = search_prices) -> Optional[dict]:
    """Crea la alerta sobre el producto que mejor responde a ``query``.

    Devuelve None si no se encontró el producto, o {"error": "limit"} si el
    usuario ya tiene el máximo de alertas.
    """
    result = search(query, max_groups=_SEARCH_GROUPS)
    groups = [g for g in result.get("groups", []) if g["key"].startswith(("ean:", "model:"))]
    group = next((g for g in groups if g["key"] == key), None) if key else (groups[0] if groups else None)
    best = _best(group) if group else None
    if not group or not best:
        return None
    alert_id = user_db.add_price_alert(user_id, group["key"], group["name"], query, best["price"], target)
    if alert_id is None:
        return {"error": "limit"}
    return {"id": alert_id, "key": group["key"], "name": group["name"], "price": best["price"],
            "store_name": best["store_name"], "target": target}


def _ars(value: float) -> str:
    return "$" + f"{round(value):,}".replace(",", ".")


def _message(alert: dict, best: dict, previous: float, reached_target: bool) -> str:
    head = (f"🎯 <b>Llegó a tu precio</b> (≤ {_ars(alert['target_price'])})"
            if reached_target else "📉 <b>Bajó el precio</b>")
    return (f"{head}\n{html.escape(alert['product_name'])}\n"
            f"<b>{html.escape(best['store_name'])}</b>: {_ars(best['price'])} (antes {_ars(previous)})\n"
            f'<a href="{html.escape(best["url"])}">Ver en la tienda</a>\n'
            "<i>Precio online publicado; confirmá stock y precio final antes de pagar.</i>")


def check_alerts(user_db, send: Callable[[str, str], bool], *,
                 search: Callable[..., dict] = search_prices) -> dict:
    """Revisa todas las alertas con consulta en vivo y avisa por Telegram.

    - Con precio objetivo: avisa cuando el más barato llega a ese precio (y
      vuelve a avisar sólo si baja más; si sube por encima, se rearma).
    - Sin objetivo: avisa ante cualquier baja de al menos 1 % respecto de la
      última revisión.
    """
    stats = {"checked": 0, "notified": 0, "missing": 0}
    by_query: dict[str, dict] = {}
    for alert in user_db.alerts_to_check():
        stats["checked"] += 1
        if alert["query"] not in by_query:
            try:
                by_query[alert["query"]] = search(alert["query"], max_groups=_CHECK_GROUPS)
            except Exception:
                by_query[alert["query"]] = {"groups": []}
        group = next((g for g in by_query[alert["query"]].get("groups", [])
                      if g["key"] == alert["product_key"]), None)
        best = _best(group) if group else None
        if not best:
            stats["missing"] += 1
            continue
        current, baseline = best["price"], alert["baseline_price"]
        target, notified = alert["target_price"], alert["last_notified_price"]
        message = None
        if target is not None:
            if current <= target and (notified is None or current < notified * (1 - _MIN_DROP)):
                message = _message(alert, best, baseline, True)
                notified = current
            elif current > target:
                notified = None          # se rearma para la próxima vez que baje
        elif current < baseline * (1 - _MIN_DROP):
            message = _message(alert, best, baseline, False)
        user_db.update_price_alert_state(alert["id"], current, notified)
        if message and send(alert["telegram_chat_id"], message):
            stats["notified"] += 1
    return stats
