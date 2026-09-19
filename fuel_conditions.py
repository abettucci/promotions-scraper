"""Clasificación conservadora de elegibilidad y exclusiones de combustibles.

Solo conserva oraciones publicadas en el texto legal o de la promoción. No
deduce que un programa, app o segmento sea obligatorio si no se lo menciona.
"""
from __future__ import annotations

import re
from typing import Iterable


_REQUIREMENT_SIGNALS = re.compile(
    r"\b(?:exclusiv[oa]s?|unicamente|únicamente|solo|sólo|"
    r"adherid[oa]s?|registrad[oa]s?|miembros?|socios?|beneficiari[oa]s?|"
    r"clientes?\s+(?:de|con)|programa\s+de\s+beneficios|club\s+\w+|"
    r"cuenta\s+sueldo|nivel\s+\w+|paquete\s+\w+|app\s+\w+|"
    r"pagando\s+con|abonando\s+con|mediante\s+(?:qr|la\s+app))\b",
    re.IGNORECASE,
)
_EXCLUSION_SIGNALS = re.compile(
    r"\b(?:no\s+(?:acumulable|combinable|aplica|aplican|válid[oa]s?|valid[oa]s?|"
    r"incluye|incluyen|rige)|exclu(?:ye|yen|ido|ida|idos|idas)|excepto|"
    r"a\s+excepcion|no\s+participan)\b",
    re.IGNORECASE,
)


def _clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip(" \t\n;|.-")


def _items(value: object) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        return [item for raw in value for item in _items(raw)]
    text = _clean(value)
    if not text:
        return []
    return [_clean(item) for item in re.split(r"\s*(?:\||\n)\s*", text) if _clean(item)]


def _sentences(text: str) -> Iterable[str]:
    for sentence in re.split(r"(?<=[.;])\s+|\s+[•·]\s+", _clean(text)):
        cleaned = _clean(sentence)
        if cleaned:
            yield cleaned[:360]


def _dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = _clean(value)
        key = re.sub(r"[^a-z0-9]", "", cleaned.lower())
        if cleaned and key and key not in seen:
            seen.add(key)
            result.append(cleaned)
    return result


def extract_fuel_conditions(
    terms_raw: object,
    requirements: object = None,
    exclusions: object = None,
) -> tuple[list[str], list[str]]:
    """Combina campos existentes con condiciones explícitas halladas en T&C."""
    detected_requirements = []
    detected_exclusions = []
    for sentence in _sentences(str(terms_raw or "")):
        if _REQUIREMENT_SIGNALS.search(sentence):
            detected_requirements.append(sentence)
        if _EXCLUSION_SIGNALS.search(sentence):
            detected_exclusions.append(sentence)
    return (
        _dedupe([*_items(requirements), *detected_requirements]),
        _dedupe([*_items(exclusions), *detected_exclusions]),
    )
