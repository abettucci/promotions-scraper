"""Reglas compartidas para cruzar tarjetas declaradas con promociones."""
from __future__ import annotations

import re
import unicodedata
from typing import Iterable


CARD_MODES = {"credit", "debit", "both"}

# Sólo se filtra si una promoción declara el segmento en título o requisitos.
# Las legales completas suelen enumerar variantes ajenas a la condición puntual.
_TIER_PATTERNS = {
    "brubank": {"plus": (r"\bplan plus\b",), "ultra": (r"\bplan ultra\b",)},
    "banco galicia": {
        "eminent_black": (r"\beminent black\b",),
        "eminent": (r"\beminent\b",),
        "haberes": (r"\bplan sueldo\b", r"\bhaberes\b"),
    },
    "santander": {
        "select_platinum": (r"\bselect platinum\b",),
        "select_black": (r"\bselect black\b",),
        "plan_sueldo": (r"\bplan sueldo\b",),
    },
    "macro": {"selecta": (r"\bmacro selecta\b", r"\bselecta\b")},
    "banco patagonia": {
        "plan_sueldo_plus": (r"\bplan sueldo plus\b",),
        "plan_sueldo_singular": (r"\bplan sueldo singular\b",),
    },
    "comafi": {
        "premium": (r"\bpremium\b", r"\bplatinum\b"),
        "unico_black": (r"\bunico black\b", r"\bsignature\b"),
    },
}


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


def promotion_allows_tier(promotion: dict, method: dict) -> bool:
    patterns = _TIER_PATTERNS.get(_norm(method.get("name")), {})
    if not patterns:
        return True
    requirements = promotion.get("requirements") or ""
    if isinstance(requirements, (list, tuple)):
        requirements = " ".join(str(value) for value in requirements)
    text = _norm(f"{promotion.get('title') or ''} {requirements}")
    required = {
        tier for tier, expressions in patterns.items()
        if any(re.search(expression, text, re.I) for expression in expressions)
    }
    # Éminent Black no queda cubierto por haber elegido únicamente Éminent.
    if "eminent_black" in required:
        required.discard("eminent")
    if not required:
        return True
    selected = {str(value).lower() for value in method.get("tiers") or []}
    return bool(required & selected)


def promotion_matches_payment_methods(promotion: dict, methods: Iterable[dict]) -> bool:
    return any(
        _entity_matches(promotion, method)
        and promotion_allows_card_mode(promotion, method)
        and promotion_allows_tier(promotion, method)
        for method in methods
        if method.get("name")
    )
