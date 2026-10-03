"""Precio final con la mejor promo bancaria aplicable a cada oferta."""
from __future__ import annotations

import math
import re
from datetime import date
from typing import Optional

from .models import Offer


def money(value: object) -> float:
    """'$10.000 semanal' → 10000; 'Sin tope' / vacío → infinito."""
    text = str(value or "")
    if not text or re.search(r"sin\s+tope", text, re.I):
        return math.inf
    match = re.search(r"\$\s*([\d.]+(?:,\d+)?)", text)
    if not match:
        return math.inf
    return float(match.group(1).replace(".", "").replace(",", "."))


def percent(discount: object) -> float:
    match = re.search(r"(\d{1,3})(?:[.,]\d+)?\s*%", str(discount or ""))
    return int(match.group(1)) / 100 if match else 0.0


_SCOPED_RE = re.compile(
    r"\ben\s+(?:productos?\s+seleccionados|electro|tv|muebles|parrillas|galletitas|bebidas|"
    r"perfumer[ií]a|bazar|colchones|hydrum|alaniz|l[ií]nea blanca|ropa)", re.I,
)


def _restricted_to_other_products(promo: dict, product: str) -> bool:
    """Promos acotadas a un rubro que no nombra al producto se descartan."""
    from promo_questions import _norm

    title = str(promo.get("title") or "")
    match = _SCOPED_RE.search(title)
    if not match:
        return False
    scope = _norm(title[match.start():])
    words = [w for w in re.findall(r"[a-z]{4,}", _norm(product))]
    return not any(w in scope for w in words)


def applicable_promos(offer: Offer, promotions: list[dict], day: date,
                      methods: Optional[list[dict]] = None) -> list[dict]:
    """Promos del comercio de la oferta vigentes ese día (y del usuario, si hay)."""
    # Import diferido: promo_questions importa este paquete para el asistente.
    from promo_questions import _matches_payment_method, _promo_days, _scope_may_cover_product

    if not offer.merchant:
        return []
    iso = day.isoformat()
    result = []
    for promo in promotions:
        if promo.get("supermarket_name") != offer.merchant:
            continue
        if day.weekday() not in _promo_days(promo):
            continue
        if (promo.get("valid_from") or "") > iso or (promo.get("valid_until") or "9999") < iso:
            continue
        if methods and not _matches_payment_method(promo, methods):
            continue
        # "25% en galletitas y bebidas" no aplica a una heladera.
        if not _scope_may_cover_product(promo, offer.title) or _restricted_to_other_products(promo, offer.title):
            continue
        result.append(promo)
    return result


def apply_best_promo(offer: Offer, promotions: list[dict], day: Optional[date] = None,
                     methods: Optional[list[dict]] = None) -> Offer:
    """Completa final_price/savings/promo con la promo que más ahorra.

    El mínimo de compra se informa pero no descarta la promo: en el súper el
    ticket suele sumar varios productos. Las cuotas sin interés no descuentan.
    """
    day = day or date.today()
    best: tuple[float, Optional[dict]] = (0.0, None)
    for promo in applicable_promos(offer, promotions, day, methods):
        pct = percent(promo.get("discount"))
        if not pct:
            continue
        savings = min(offer.price * pct, money(promo.get("tope")))
        if savings > best[0]:
            best = (savings, promo)
    savings, promo = best
    offer.final_price = round(offer.price - savings, 2)
    offer.savings = round(savings, 2)
    if promo:
        entity = promo.get("bank") or promo.get("wallet") or promo.get("payment_method") or ""
        if promo.get("bank") and promo.get("wallet"):
            entity = f"{promo['bank']} vía {promo['wallet']}"
        offer.promo = {
            "id": promo.get("id"), "title": promo.get("title"), "discount": promo.get("discount"),
            "entity": entity, "tope": promo.get("tope"), "min_purchase": promo.get("min_purchase"),
            "valid_days": promo.get("valid_days"), "store_types": promo.get("store_types"),
            "requires_min_purchase": money(promo.get("min_purchase")) not in (math.inf,)
            and money(promo.get("min_purchase")) > offer.price,
        }
    return offer
