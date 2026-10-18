"""Alertas de baja de precio: alta, parseo desde el bot y revisión periódica."""
from __future__ import annotations

import html
import json
import re
import sqlite3
from datetime import date
from typing import Callable, Optional

from .search import search_prices

_TARGET_RE = re.compile(
    r"(?:\s+(?:a|por|en|menos\s+de|menor\s+a|hasta|<=?)\s*)?\$\s*([\d.]+(?:,\d+)?)\s*$", re.I,
)
_MIN_DROP = 0.01   # sólo avisamos bajas de al menos 1 %
_SEARCH_GROUPS = 24  # igual que la página: el producto elegido tiene que reaparecer
_CHECK_GROUPS = 30   # el ranking varía de un día a otro; margen para no perder el producto


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
    return min(offers, key=_effective_price) if offers else None


def _effective_price(offer: dict) -> float:
    """Precio unitario final: tienda + promo personalizada, si fue calculada."""
    final = offer.get("final_price")
    return float(final if final is not None else offer["price"])


def load_active_promotions() -> list[dict]:
    """Promociones vigentes que permiten estimar el precio final de una alerta."""
    import config

    today = date.today().isoformat()
    conn = sqlite3.connect(str(config.DATABASE_PATH))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT p.id, p.title, p.discount, p.bank, p.wallet, p.card_type, p.payment_method,
                   p.store_types, p.valid_days, p.valid_from, p.valid_until, p.tope,
                   p.min_purchase, p.terms_raw, p.exclusions, p.requirements,
                   s.name AS supermarket_name
            FROM promotions p
            JOIN supermarkets s ON s.id = p.supermarket_id
            WHERE p.is_active = 1
              AND (p.valid_from IS NULL OR p.valid_from = '' OR p.valid_from <= ?)
              AND (p.valid_until IS NULL OR p.valid_until = '' OR p.valid_until >= ?)
            ORDER BY s.name, p.scraped_at DESC
            LIMIT 1000
            """,
            (today, today),
        ).fetchall()
    finally:
        conn.close()
    promos = []
    for row in rows:
        promo = dict(row)
        for field in ("exclusions", "requirements"):
            value = promo.get(field)
            if value:
                try:
                    promo[field] = json.loads(value)
                except (TypeError, json.JSONDecodeError):
                    pass
        promos.append(promo)
    return promos


def create_alert(user_db, user_id: int, query: str, *, key: Optional[str] = None,
                 target: Optional[float] = None, search: Callable[..., dict] = search_prices,
                 promotions: Optional[list[dict]] = None,
                 methods: Optional[list[dict]] = None) -> Optional[dict]:
    """Crea la alerta sobre el producto que mejor responde a ``query``.

    Devuelve None si no se encontró el producto, o {"error": "limit"} si el
    usuario ya tiene el máximo de alertas.
    """
    search_args = {"max_groups": _SEARCH_GROUPS}
    if promotions is not None:
        search_args.update(promotions=promotions if methods else [], methods=methods or [])
    result = search(query, **search_args)
    groups = [g for g in result.get("groups", []) if g["key"].startswith(("ean:", "model:"))]
    group = next((g for g in groups if g["key"] == key), None) if key else (groups[0] if groups else None)
    best = _best(group) if group else None
    if not group or not best:
        return None
    current = _effective_price(best)
    alert_id = user_db.add_price_alert(user_id, group["key"], group["name"], query, current, target)
    if alert_id is None:
        return {"error": "limit"}
    return {"id": alert_id, "key": group["key"], "name": group["name"], "price": current,
            "store_name": best["store_name"], "target": target, "promo": best.get("promo")}


def _ars(value: float) -> str:
    return "$" + f"{round(value):,}".replace(",", ".")


def _message(alert: dict, best: dict, previous: float, reached_target: bool) -> str:
    current = _effective_price(best)
    head = (f"🎯 <b>Llegó a tu precio</b> (≤ {_ars(alert['target_price'])})"
            if reached_target else "📉 <b>Bajó el precio</b>")
    lines = [
        head,
        html.escape(alert["product_name"]),
        f"<b>{html.escape(best['store_name'])}</b>: {_ars(current)} (antes {_ars(previous)})",
    ]
    promo = best.get("promo")
    if promo and current < float(best["price"]):
        entity = html.escape(str(promo.get("entity") or "tu medio de pago"))
        discount = html.escape(str(promo.get("discount") or "beneficio"))
        lines.append(
            f"✨ Precio final estimado con <b>{discount}</b> de {entity}; "
            f"precio publicado {_ars(float(best['price']))}."
        )
    lines.extend([
        f'<a href="{html.escape(best["url"])}">Ver en la tienda</a>',
        "<i>Confirmá stock, condiciones y precio final antes de pagar.</i>",
    ])
    return "\n".join(lines)


def check_alerts(user_db, send: Callable[[str, str], bool], *, send_whatsapp: Optional[Callable[[str, str], bool]] = None,
                 search: Callable[..., dict] = search_prices,
                 promotions: Optional[list[dict]] = None) -> dict:
    """Revisa todas las alertas con consulta en vivo y avisa por Telegram.

    - Con precio objetivo: avisa cuando el más barato llega a ese precio (y
      vuelve a avisar sólo si baja más; si sube por encima, se rearma).
    - Sin objetivo: avisa ante cualquier baja de al menos 1 % respecto de la
      última revisión.
    """
    stats = {"checked": 0, "notified": 0, "missing": 0}
    by_query: dict[tuple, dict] = {}
    for alert in user_db.alerts_to_check():
        stats["checked"] += 1
        methods = user_db.get_user_payment_methods(alert["user_id"]) if promotions is not None else []
        method_key = tuple(
            sorted((method.get("name", ""), method.get("card_mode", "both")) for method in methods)
        )
        cache_key = (alert["query"], method_key)
        if cache_key not in by_query:
            try:
                search_args = {"max_groups": _CHECK_GROUPS}
                if promotions is not None:
                    search_args.update(promotions=promotions if methods else [], methods=methods)
                by_query[cache_key] = search(alert["query"], **search_args)
            except Exception:
                by_query[cache_key] = {"groups": []}
        group = next((g for g in by_query[cache_key].get("groups", [])
                      if g["key"] == alert["product_key"]), None)
        best = _best(group) if group else None
        if not best:
            stats["missing"] += 1
            continue
        current, baseline = _effective_price(best), alert["baseline_price"]
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
        if message:
            delivered = bool(alert.get("telegram_chat_id") and send(alert["telegram_chat_id"], message))
            if send_whatsapp and alert.get("whatsapp_opt_in"):
                from whatsapp_notifier import decrypt_phone
                phone = decrypt_phone(alert.get("whatsapp_phone_ciphertext"))
                delivered = bool(phone and send_whatsapp(phone, message)) or delivered
            if delivered:
                stats["notified"] += 1
    return stats
