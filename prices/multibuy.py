"""Promos por cantidad: "2do al 50%", "3x2", "50% 2da", "Max 48 unidades".

Se detectan en los datos que publica cada tienda (teasers VTEX, promos de
Coto) y se calculan sobre el precio unitario. Las que sólo se publican como
etiqueta de campaña ("Hasta 2do al 70%") se muestran pero no se calculan:
el porcentaje real varía por producto.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass
from typing import Optional

_ORDINALS = {2: "2do", 3: "3ro", 4: "4to", 5: "5to", 6: "6to"}

_NTH_PCT = re.compile(r"\b(\d)\s*(?:do|ro|er|to|vo|mo|da|ra|a|°|º)?\s*al\s*(\d{1,3})\s*%")
_PCT_NTH = re.compile(r"\b(\d{1,3})\s*%\s*(?:en\s+(?:la\s+|el\s+)?)?(\d)\s*(?:da|ra|a|do|ro|to|°|º)\b")
_N_FOR_M = re.compile(r"\b(\d{1,2})\s*x\s*(\d{1,2})\b")
_MAX_UNITS = re.compile(r"\bmax(?:imo)?\.?\s*(\d{1,3})\s*(?:unidades|u\b|un\b)")
_UP_TO = re.compile(r"\bhasta\s+(?:el\s+)?\d\s*(?:do|ro|er|to|da|ra|a)?\s*al\b")


def _fold(text: object) -> str:
    value = unicodedata.normalize("NFD", str(text or ""))
    return "".join(c for c in value if unicodedata.category(c) != "Mn").lower()


@dataclass
class MultiBuy:
    label: str                      # "2do al 50%", "3x2", "2x1"
    kind: str                       # nth_pct | n_for_m | tag
    min_qty: int = 2
    pct: Optional[float] = None     # nth_pct: descuento del enésimo producto
    pay: Optional[int] = None       # n_for_m: se pagan `pay` de cada `min_qty`
    max_units: Optional[int] = None  # tope de unidades con promo
    unit_price: Optional[float] = None  # precio por unidad publicado llevando min_qty
    exact: bool = True              # False: etiqueta orientativa, no se calcula

    def total(self, price: float, qty: int) -> float:
        """Costo de ``qty`` unidades con la promo (el resto, a precio normal)."""
        qty = max(1, qty)
        if not self.exact or qty < self.min_qty:
            return price * qty
        promo_units = qty if self.max_units is None else min(qty, self.max_units)
        groups = promo_units // self.min_qty
        covered = groups * self.min_qty
        if self.unit_price is not None:
            group_cost = self.unit_price * self.min_qty
        elif self.kind == "nth_pct" and self.pct is not None:
            group_cost = price * (self.min_qty - 1) + price * (1 - self.pct / 100)
        elif self.kind == "n_for_m" and self.pay is not None:
            group_cost = price * self.pay
        else:
            return price * qty
        return groups * group_cost + (qty - covered) * price

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> Optional["MultiBuy"]:
        if not data:
            return None
        known = {k: data[k] for k in cls.__dataclass_fields__ if k in data}
        return cls(**known)


def parse_multibuy(text: object, min_qty: Optional[int] = None,
                   unit_price: Optional[float] = None) -> Optional[MultiBuy]:
    """Interpreta el texto de una promo por cantidad; None si no lo es."""
    folded = _fold(text)
    if not folded:
        return None
    max_match = _MAX_UNITS.search(folded)
    max_units = int(max_match.group(1)) if max_match else None
    approximate = bool(_UP_TO.search(folded))

    match = _NTH_PCT.search(folded)
    if match:
        n, pct = int(match.group(1)), int(match.group(2))
        if 2 <= n <= 12 and 0 < pct <= 100:
            return MultiBuy(f"{'hasta ' if approximate else ''}{_ORDINALS.get(n, f'{n}°')} al {pct}%", "nth_pct", n,
                            pct=pct, max_units=max_units, unit_price=unit_price, exact=not approximate)
    match = _PCT_NTH.search(folded)
    if match:
        pct, n = int(match.group(1)), int(match.group(2))
        if 2 <= n <= 12 and 0 < pct <= 100:
            return MultiBuy(f"{'hasta ' if approximate else ''}{_ORDINALS.get(n, f'{n}°')} al {pct}%", "nth_pct", n,
                            pct=pct, max_units=max_units, unit_price=unit_price, exact=not approximate)
    match = _N_FOR_M.search(folded)
    if match:
        n, m = int(match.group(1)), int(match.group(2))
        if 2 <= n <= 12 and 1 <= m < n:
            return MultiBuy(f"{n}x{m}", "n_for_m", n, pay=m, max_units=max_units,
                            unit_price=unit_price, exact=not approximate)
    if approximate:
        # "Hasta 2do al 70% en Almacén y Bebidas": campaña, sin precio por producto.
        tag = re.search(r"hasta\s+[^\n]*?\d\s*(?:do|ro|er|to|da|ra|a)?\s*al\s*\d{1,3}\s*%", folded)
        if tag:
            return MultiBuy(re.sub(r"\s+", " ", str(text).strip())[:60], "tag", min_qty or 2, exact=False)
    return None
