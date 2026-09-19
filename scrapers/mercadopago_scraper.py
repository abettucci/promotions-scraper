"""Promociones públicas de Mercado Pago.

Fuente: https://promociones.mercadopago.com.ar/

Esta fuente contiene campañas públicas de Mercado Pago. No intenta acceder a
la sección Beneficios de la app ni a campañas dirigidas a una cuenta.
"""
from __future__ import annotations

import re
from datetime import date
from html.parser import HTMLParser
from typing import Dict, List, Optional

from .base_scraper import BaseScraper


_MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}


class _PromotionCardsParser(HTMLParser):
    """Parser sin dependencias para las modales de promociones del sitio."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, set[str]]] = []
        self.card: Optional[dict] = None
        self.card_depth = 0
        self.cards: list[dict] = []

    def _inside(self, class_name: str) -> bool:
        return any(class_name in classes for _, classes in self.stack)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]):
        attributes = dict(attrs)
        classes = set((attributes.get("class") or "").split())
        is_void = tag in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
        if not is_void:
            self.stack.append((tag, classes))
        if tag == "div" and "kiyo__data--modal" in classes and self.card is None:
            self.card = {"title": [], "description": [], "legal": [], "badges": [], "url": None, "image_url": None}
            self.card_depth = len(self.stack)
            return
        if not self.card:
            return
        if tag == "img" and self._inside("kiyo__data--details-logo") and attributes.get("src"):
            self.card["image_url"] = attributes["src"]
        elif tag == "a" and self._inside("kiyo__data--details-btn") and attributes.get("href"):
            self.card["url"] = attributes["href"]

    def handle_data(self, data: str):
        if not self.card or not data.strip():
            return
        tag = self.stack[-1][0] if self.stack else ""
        # La plantilla actual deja el h3 de marca dentro de la modal, pero no
        # siempre dentro del mismo contenedor del logo.
        if tag == "h3":
            self.card["title"].append(data)
        elif tag == "p" and self._inside("kiyo__data--details-row1"):
            self.card["description"].append(data)
        elif tag == "small" and self._inside("kiyo__data--details-row2"):
            self.card["legal"].append(data)
        elif self._inside("kiyo__cards--badge"):
            self.card["badges"].append(data)

    def handle_endtag(self, tag: str):
        if self.card and tag == "div" and len(self.stack) == self.card_depth:
            self.cards.append(self.card)
            self.card = None
            self.card_depth = 0
        if self.stack:
            self.stack.pop()


class MercadoPagoScraper(BaseScraper):
    """Extrae promociones publicadas en el sitio oficial de Mercado Pago."""

    def __init__(self):
        super().__init__(
            name="Mercado Pago",
            url="https://promociones.mercadopago.com.ar/",
        )

    async def scrape(self, page=None) -> List[Dict]:
        """Obtiene la página pública sin autenticar ni usar datos de usuarios."""
        try:
            import requests
        except ImportError:
            print("   ⚠️ Mercado Pago: falta la dependencia requests")
            return []
        try:
            response = requests.get(
                self.url,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; promotions-scraper/1.0)",
                    "Accept-Language": "es-AR,es;q=0.9",
                },
                timeout=30,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            print(f"   ⚠️ Mercado Pago: no se pudo descargar la página pública: {exc}")
            return []

        parsed_promotions = self.parse_html(response.text)
        promotions = [promo for promo in parsed_promotions if self._is_current_or_undated(promo)]
        skipped = len(parsed_promotions) - len(promotions)
        if skipped:
            print(f"   ℹ️ Mercado Pago: {skipped} campaña(s) vencida(s) omitida(s)")
        print(f"✅ {self.name}: {len(promotions)} promociones públicas")
        return promotions

    def parse_html(self, html: str) -> List[Dict]:
        """Parsea las modales de detalle, una por tarjeta de promoción."""
        parser = _PromotionCardsParser()
        parser.feed(html)
        promotions: List[Dict] = []
        seen: set[tuple[str, str, str]] = set()

        for card in parser.cards:
            title = self.clean_text(" ".join(card["title"]))
            description = self.clean_text(" ".join(card["description"]))
            legal = self.clean_text(" ".join(card["legal"]))
            badges = [self.clean_text(badge) for badge in card["badges"] if self.clean_text(badge)]
            full_text = self.clean_text(" ".join([*badges, description, legal]))
            if not title or not description:
                continue

            url = card["url"] or self.url
            key = (title.lower(), description.lower(), legal.lower())
            if key in seen:
                continue
            seen.add(key)

            dates = self._extract_spanish_dates(legal)
            promotions.append({
                "title": title,
                "discount": self._discount_from_badges(badges, full_text),
                "bank": None,
                "wallet": "Mercado Pago",
                "card_type": "Tarjeta Mercado Pago" if "tarjeta de mercado pago" in full_text.lower() else None,
                "payment_method": "Mercado Pago",
                "store_types": "Online" if "online" in full_text.lower() else None,
                "valid_days": "Todos los días",
                "valid_from": dates["valid_from"],
                "valid_until": dates["valid_until"],
                "url": url,
                "image_url": card["image_url"],
                "terms_raw": full_text[:3000],
                "tope": self._extract_tope(full_text),
                "min_purchase": self._extract_min_purchase(full_text),
                "exclusions": [],
                "requirements": [],
            })
        return promotions

    @staticmethod
    def _discount_from_badges(badges: List[str], text: str) -> str:
        for badge in badges:
            if re.search(r"\d+\s*(?:%|x\s*\d+|OFF)", badge, re.IGNORECASE):
                return badge
        quota = re.search(r"hasta\s+(\d+)\s+cuotas?|(?<!\d)(\d+)\s+cuotas?", text, re.IGNORECASE)
        if quota:
            return f"{quota.group(1) or quota.group(2)} cuotas"
        return "Beneficio Mercado Pago"

    @staticmethod
    def _extract_tope(text: str) -> Optional[str]:
        match = re.search(r"tope(?:\s+de\s+reintegro)?[^$]{0,35}\$\s*([\d.]+(?:,\d+)?)", text, re.IGNORECASE)
        return f"${match.group(1).rstrip('.,')}" if match else None

    @staticmethod
    def _extract_min_purchase(text: str) -> Optional[str]:
        match = re.search(r"(?:a partir de|compras? desde)\s+\$\s*([\d.]+(?:,\d+)?)", text, re.IGNORECASE)
        return f"${match.group(1).rstrip('.,')}" if match else None

    @staticmethod
    def _is_current_or_undated(promo: Dict) -> bool:
        valid_until = promo.get("valid_until")
        if not valid_until:
            return True
        try:
            return date.fromisoformat(valid_until) >= date.today()
        except ValueError:
            return True

    @staticmethod
    def _extract_spanish_dates(text: str) -> Dict[str, Optional[str]]:
        """Soporta el formato que publica la fuente: ``del 11 al 17 de mayo``."""
        normalized = re.sub(r"\s+", " ", text.lower())
        match = re.search(
            r"(?:valido\s+)?del\s+(\d{1,2})\s+(?:al|a)\s+(\d{1,2})\s+de\s+"
            r"([a-záéíóúñ]+)(?:\s+de\s+(\d{4}))?",
            normalized,
        )
        if not match:
            return {"valid_from": None, "valid_until": None}
        month = _MONTHS.get(match.group(3))
        if not month:
            return {"valid_from": None, "valid_until": None}
        year = int(match.group(4) or date.today().year)
        try:
            return {
                "valid_from": date(year, month, int(match.group(1))).isoformat(),
                "valid_until": date(year, month, int(match.group(2))).isoformat(),
            }
        except ValueError:
            return {"valid_from": None, "valid_until": None}
