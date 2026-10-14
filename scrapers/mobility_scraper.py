"""Promociones públicas de movilidad.

Consulta el buscador público de MODO en vez de recorrer su catálogo completo.
Cada resultado se confirma contra su detalle y términos: no se publica nada que
sea privado, invitacional, sin vigencia o sin un comercio/rubro verificable.
"""
from __future__ import annotations

import asyncio
import html
import re
from datetime import date
from typing import Dict, List, Optional

from .base_scraper import BaseScraper


_BASE = "https://www.modo.com.ar/promos"
_SEARCH_URL = f"{_BASE}/api/rewards/v2/search"
_DETAIL_URL = f"{_BASE}/api/rewards/v2/benefit/{{slug}}"
_TERMS = ("uber", "cabify", "didi", "transporte", "sube", "colectivo", "subte", "tren")
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; PromoAR/1.0)",
    "Accept": "application/json",
    "Accept-Language": "es-AR,es;q=0.9",
}
_PRIVATE = re.compile(r"invitad|seleccionad|corporativ|emplead|clientes? seguros", re.I)
_PROVIDERS = (("Uber", r"\buber\b"), ("Cabify", r"\bcabify\b"), ("DiDi", r"\bdidi\b"))


def _clean(value: object) -> str:
    raw = html.unescape(str(value or ""))
    raw = re.sub(r"<br\s*/?>|</p>", "\n", raw, flags=re.I)
    raw = re.sub(r"<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", raw).strip()


def _days(schedule: Dict) -> str:
    names = {
        "monday": "Lunes", "tuesday": "Martes", "wednesday": "Miércoles",
        "thursday": "Jueves", "friday": "Viernes", "saturday": "Sábado", "sunday": "Domingo",
    }
    values = [names.get(str(day).lower()) for day in (schedule.get("days_of_week") or [])]
    values = [day for day in values if day]
    return ", ".join(values) if values and len(values) < 7 else "Todos los días"


def _coverage(text: str) -> Optional[str]:
    """Sólo devuelve alcance literalmente presente en el legal público."""
    compact = re.sub(r"\s+", " ", text or "")
    patterns = (
        r"(?:válid[oa]|aplicable|disponible)\s+(?:en|para)\s+([^.]{4,260}?(?:AMBA|Argentina|Buenos Aires|Córdoba|Rosario|Mendoza|colectivos|subtes?|trenes?)[^.]{0,160})",
        r"(en\s+(?:colectivos|subtes?|trenes?)[^.]{0,220})",
    )
    for pattern in patterns:
        match = re.search(pattern, compact, re.I)
        if match:
            return match.group(1).strip(" .;:")[:300]
    return None


class MobilityScraper(BaseScraper):
    def __init__(self):
        super().__init__(name="Movilidad pública", url=_BASE)

    async def scrape(self, page=None) -> List[Dict]:
        import requests

        loop = asyncio.get_event_loop()
        seen: set[str] = set()
        cards: list[Dict] = []
        for term in _TERMS:
            try:
                response = await loop.run_in_executor(None, lambda q=term: requests.get(
                    _SEARCH_URL,
                    params={"search_text": q, "fcalcstatus": "RUNNING", "limit": 50,
                            "source": "web_modo", "origin": "WEB_MODO"},
                    headers=_HEADERS, timeout=25,
                ))
                response.raise_for_status()
            except Exception as exc:
                print(f"   ⚠️ MODO movilidad ({term}): {exc}")
                continue
            for card in (response.json() or {}).get("cards") or []:
                slug = self._slug(card)
                if slug and slug not in seen:
                    seen.add(slug)
                    cards.append(card)

        promotions: list[Dict] = []
        for card in cards:
            slug = self._slug(card)
            detail = await loop.run_in_executor(None, self._detail, slug)
            promo = self.parse_card(card, detail)
            if promo:
                promotions.append(promo)
        print(f"✅ {self.name}: {len(promotions)} promociones públicas vigentes")
        return promotions

    @staticmethod
    def _slug(card: Dict) -> str:
        return str((((card.get("benefit") or {}).get("publication") or {}).get("slug") or "")).strip()

    @staticmethod
    def _detail(slug: str) -> Dict:
        import requests
        if not slug:
            return {}
        try:
            response = requests.get(_DETAIL_URL.format(slug=slug), headers=_HEADERS, timeout=25)
            response.raise_for_status()
            return response.json() or {}
        except Exception:
            return {}

    def parse_card(self, card: Dict, detail: Optional[Dict] = None) -> Optional[Dict]:
        detail = detail or {}
        benefit = card.get("benefit") or {}
        publication = benefit.get("publication") or {}
        info = card.get("card") or {}
        offer = card.get("offer") or {}
        terms = _clean(detail.get("terms_and_conditions"))
        description = _clean(detail.get("publication_description") or publication.get("description"))
        name = _clean(benefit.get("name") or info.get("benefit"))
        haystack = " ".join((name, description, terms, self._slug(card)))
        if not haystack or _PRIVATE.search(haystack):
            return None

        provider = next((label for label, pattern in _PROVIDERS if re.search(pattern, haystack, re.I)), None)
        transit = bool(re.search(r"\b(transporte|sube|colectivo|subte|tren|viaje con qr)\b", haystack, re.I))
        if not provider and not transit:
            return None

        cashback = (offer.get("outcomes") or {}).get("cashback") or {}
        amount = cashback.get("amount")
        if amount is not None:
            discount = f"{amount:g}% reintegro" if cashback.get("amount_type", "percent") == "percent" else f"${int(amount):,}".replace(",", ".") + " de reintegro"
        else:
            match = re.search(r"(\d+(?:[,.]\d+)?)\s*%", haystack)
            if not match:
                return None
            discount = f"{match.group(1)}%"

        conditions = benefit.get("conditions") or detail.get("conditions") or {}
        schedule = conditions.get("schedule") or {}
        methods = ((conditions.get("payment_methods") or {}).get("methods") or [])
        method_types = {str(item.get("type") or "") for item in methods}
        card_type = ", ".join(label for label, key in (("Crédito", "credit_card"), ("Débito", "debit_card")) if key in method_types) or None
        flows = ((conditions.get("payment_flow") or {}).get("flows") or [])
        payment = "MODO"
        if "trip" in flows or re.search(r"qr transporte", haystack, re.I):
            payment = "QR Transporte con MODO"
        elif "instore_nfc" in flows or re.search(r"nfc|sin contacto|contactless", haystack, re.I):
            payment = "MODO sin contacto (NFC)"

        cap = ((offer.get("limits") or {}).get("period_cap") or {}).get("amount_by_period")
        tope = f"${int(cap):,}".replace(",", ".") if isinstance(cap, (int, float)) else None
        exclusions = [terms] if re.search(r"no aplica|excluye|no incluye", terms, re.I) else []
        requirements = [piece.strip() for piece in re.findall(
            r"(?:requisito|deber[aá]|exclusivo para|solo para)[^.]{0,260}", terms, re.I
        )[:3]]
        merchant = provider or "Transporte público"
        kind = "ride_hailing" if provider else "public_transit"
        coverage = _coverage(terms + " " + description)
        return {
            "title": f"MODO {discount.replace(' reintegro', '')} en {merchant} - {_days(schedule)}",
            "discount": discount,
            "bank": info.get("participating_bank") or None,
            "wallet": "MODO",
            "card_type": card_type,
            "payment_method": payment,
            "store_types": "App" if provider else "Presencial",
            "valid_days": _days(schedule),
            "valid_from": schedule.get("start_date"),
            "valid_until": schedule.get("stop_date"),
            "url": f"{_BASE}/{self._slug(card)}",
            "image_url": info.get("image"),
            "terms_raw": terms or description,
            "tope": tope,
            "exclusions": exclusions,
            "requirements": requirements,
            "merchant_brands": [merchant],
            "merchant_category": "mobility",
            "mobility_kind": kind,
            "coverage": coverage,
            "source_id": f"modo-mobility:{self._slug(card)}",
        }
