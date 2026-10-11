"""Reglas compartidas para cruzar tarjetas declaradas con promociones."""
from __future__ import annotations

import re
import unicodedata
from typing import Iterable


CARD_MODES = {"credit", "debit", "both"}


def _norm(value: object) -> str:
    text = unicodedata.normalize("NFD", str(value or ""))
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    return re.sub(r"\s+", " ", text.lower()).strip()


def card_mode(method: dict) -> str:
    """Normaliza perfiles antiguos que no tenían esta preferencia."""
    value = str(method.get("card_mode") or "both").lower()
    return value if value in CARD_MODES else "both"


def _promotion_card_scope(promotion: dict) -> str:
    """Devuelve crédito, débito, ambos o desconocido según datos publicados."""
    text = _norm(" ".join(str(promotion.get(field) or "") for field in (
        "card_type", "payment_method", "title", "terms_raw", "requirements",
    )))
    has_credit = bool(re.search(r"\bcredito\b", text))
    has_debit = bool(re.search(r"\bdebito\b", text))
    if has_credit and has_debit:
        return "both"
    if has_credit:
        return "credit"
    if has_debit:
        return "debit"
    return "unknown"


def promotion_allows_card_mode(promotion: dict, method: dict) -> bool:
    """No excluye promos cuyo tipo de tarjeta la fuente no publicó.

    Una promo explícitamente exclusiva de crédito no se ofrece a quien sólo
    declaró débito (y viceversa). Cuando el dato no existe, se conserva y se
    muestra como potencialmente aplicable, evitando falsos negativos.
    """
    preferred = card_mode(method)
    if preferred == "both":
        return True
    scope = _promotion_card_scope(promotion)
    return scope in {"both", "unknown", preferred}


def _entity_matches(promotion: dict, method: dict) -> bool:
    name = _norm(method.get("name"))
    if not name:
        return False
    haystack = _norm(" ".join(str(promotion.get(field) or "") for field in (
        "bank", "wallet", "payment_method", "title",
    )))
    if name in haystack:
        return True
    # Las fuentes a veces omiten el prefijo "Banco". Requerimos una palabra
    # significativa para no confundir entidades por artículos o abreviaturas.
    tokens = [token for token in name.split() if len(token) >= 4 and token not in {"banco", "tarjeta"}]
    return bool(tokens) and any(token in haystack for token in tokens)


def promotion_matches_payment_methods(promotion: dict, methods: Iterable[dict]) -> bool:
    return any(
        _entity_matches(promotion, method) and promotion_allows_card_mode(promotion, method)
        for method in methods
        if method.get("name")
    )
