"""Precio final con la mejor promo bancaria aplicable a cada oferta."""
from __future__ import annotations

import math
import re
from datetime import date
from typing import Optional

from .models import Offer
from .multibuy import MultiBuy


def money(value: object) -> float:
    """'$10.000 semanal' → 10000; 'Sin tope' / vacío → infinito."""
    text = str(value or "")
    if not text or re.search(r"sin\s+tope", text, re.I):
        return math.inf
    # Exige un dígito: filas viejas traen topes basura como "$." o "$,".
    match = re.search(r"\$\s*(\d[\d.]*(?:,\d+)?)", text)
    if not match:
        return math.inf
    try:
        return float(match.group(1).replace(".", "").replace(",", "."))
    except ValueError:
        return math.inf


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
                     methods: Optional[list[dict]] = None, qty: int = 1) -> Offer:
    """Completa total/final_price/savings con lo que más conviene al llevar ``qty``.

    Compara dos caminos y elige el más barato, sin sumarlos (no se sabe si la
    tienda los acumula):
      - promo por cantidad de la tienda ("2do al 50%"), y
      - la mejor promo bancaria del día (el tope aplica al total de la compra).
    El mínimo de compra se informa pero no descarta la promo: en el súper el
    ticket suele sumar varios productos. Las cuotas sin interés no descuentan.
    """
    day = day or date.today()
    qty = max(1, int(qty))
    base_total = offer.price * qty

    bank_savings, bank_promo = 0.0, None
    for promo in applicable_promos(offer, promotions, day, methods):
        pct = percent(promo.get("discount"))
        if not pct:
            continue
        savings = min(base_total * pct, money(promo.get("tope")))
        if savings > bank_savings:
            bank_savings, bank_promo = savings, promo

    mb = MultiBuy.from_dict(offer.multibuy)
    mb_total = mb.total(offer.price, qty) if mb and mb.exact else base_total
    mb_savings = base_total - mb_total
    if mb:
        # Para mostrar "llevando 2: $X c/u" aunque se esté mirando 1 unidad.
        info = mb.to_dict()
        if mb.exact:
            info["unit_at_min"] = round(mb.total(offer.price, mb.min_qty) / mb.min_qty, 2)
        offer.multibuy = info

    if mb_savings > bank_savings:
        savings, bank_promo, offer.deal = mb_savings, None, "multibuy"
    elif bank_savings > 0:
        savings, offer.deal = bank_savings, "bank"
    else:
        savings, bank_promo, offer.deal = 0.0, None, None

    offer.qty = qty
    offer.total = round(base_total - savings, 2)
    offer.final_price = round(offer.total / qty, 2)
    offer.savings = round(savings, 2)
    if bank_promo:
        entity = bank_promo.get("bank") or bank_promo.get("wallet") or bank_promo.get("payment_method") or ""
        if bank_promo.get("bank") and bank_promo.get("wallet"):
            entity = f"{bank_promo['bank']} vía {bank_promo['wallet']}"
        offer.promo = {
            "id": bank_promo.get("id"), "title": bank_promo.get("title"), "discount": bank_promo.get("discount"),
            "entity": entity, "tope": bank_promo.get("tope"), "min_purchase": bank_promo.get("min_purchase"),
            "valid_days": bank_promo.get("valid_days"), "store_types": bank_promo.get("store_types"),
            "requires_min_purchase": money(bank_promo.get("min_purchase")) not in (math.inf,)
            and money(bank_promo.get("min_purchase")) > offer.price,
        }
    else:
        offer.promo = None
    return offer
