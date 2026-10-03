"""Normalización y agrupación de publicaciones del mismo producto.

1. EAN (código de barras): súper, farmacia y casi todo el electro VTEX.
2. Sin EAN: marca + código de modelo (p. ej. RT29K507JS8) + tamaño.
"""
from __future__ import annotations

import re
import unicodedata

_STOP = {"de", "del", "la", "el", "los", "las", "con", "sin", "para", "en", "y", "x", "a", "por"}
_UNITS = {
    "l": "l", "lt": "l", "lts": "l", "litro": "l", "litros": "l",
    "ml": "ml", "cc": "ml", "kg": "kg", "kgs": "kg", "kilo": "kg", "kilos": "kg",
    "g": "g", "gr": "g", "grs": "g", "gramos": "g", "gramo": "g",
    "lb": "lb", "lbs": "lb", "libras": "lb", "pulgadas": "in", "pulg": "in",
    "gb": "gb", "tb": "tb", "w": "w",
}
_SIZE_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(" + "|".join(sorted(_UNITS, key=len, reverse=True)) + r")\b")


def norm(text: object) -> str:
    value = unicodedata.normalize("NFD", str(text or ""))
    value = "".join(c for c in value if unicodedata.category(c) != "Mn").lower()
    # "1 L", "1lt", "1 litro" → "1l"; "1,5 L" → "1.5l"
    value = _SIZE_RE.sub(lambda m: f"{m.group(1).replace(',', '.')}{_UNITS[m.group(2)]}", value)
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9.%/ ]", " ", value)).strip()


def tokens(text: object) -> list[str]:
    return [t for t in norm(text).split() if t not in _STOP and len(t) > 1]


def relevance(query: str, title: str, brand: str = "") -> float:
    """Fracción de términos de la búsqueda presentes en la publicación."""
    wanted = tokens(query)
    if not wanted:
        return 0.0
    have = set(tokens(f"{title} {brand}"))
    hits = sum(1 for t in wanted if t in have or any(h.startswith(t) for h in have if len(t) >= 4))
    return hits / len(wanted)


def model_code(text: str) -> str:
    """Código de modelo: token alfanumérico con letras y dígitos (no un tamaño)."""
    for token in re.findall(r"[a-z0-9/-]{5,}", norm(text)):
        clean = token.replace("/", "").replace("-", "")
        if re.search(r"[a-z]", clean) and re.search(r"\d", clean) and not _SIZE_RE.fullmatch(token):
            return clean
    return ""


def group_key(title: str, brand: str, ean: str) -> str:
    digits = re.sub(r"\D", "", ean or "")
    if len(digits) >= 8:
        return f"ean:{digits.lstrip('0')}"
    code = model_code(title)
    sizes = "".join(m.group(0) for m in _SIZE_RE.finditer(norm(title)))
    if code:
        return f"model:{norm(brand)}:{code}"
    return "title:" + " ".join(sorted(set(tokens(f"{brand} {title}")))) + f":{sizes}"
