"""Importa los resúmenes públicos de promociones de Clash.

Clash publica cada listado como ``window.__clashData`` en un data.js estático.
Se consume ese recurso público directamente; no se automatiza el navegador ni
se accede a datos de la app o de cuentas privadas.
"""
from __future__ import annotations

import calendar
import json
import re
import unicodedata
from datetime import date, datetime
from typing import Dict, List, Optional
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from .base_scraper import BaseScraper


_FEEDS = {
    "supermarket": "https://promos.clash.com.ar/supermercados/data.js",
    "fuel": "https://promos.clash.com.ar/combustibles/data.js",
}
_SECTIONS = {"supermarket": "supermercados", "fuel": "combustibles"}
_MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}
_DAYS = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")
_WALLET_IDS = {"mercadopago", "naranja", "personalpay", "modo", "cuentadni", "prex", "uala", "yoy"}
_WALLET_NAMES = {
    "mercadopago": "Mercado Pago", "naranja": "Naranja X",
    "personalpay": "Personal Pay", "modo": "MODO", "cuentadni": "Cuenta DNI",
    "prex": "Prex", "uala": "Ualá", "yoy": "YOY",
}
_ENTITY_NAMES = {
    "galicia": "Banco Galicia", "nacion": "Banco Nación", "macro": "Banco Macro",
    "santander": "Santander", "bbva": "BBVA", "icbc": "ICBC",
    "hipotecario": "Banco Hipotecario", "credicoop": "Banco Credicoop",
    "patagonia": "Banco Patagonia", "comafi": "Banco Comafi",
    "supervielle": "Banco Supervielle", "santafe": "Banco Santa Fe",
    "provincia": "Banco Provincia", "ciudad": "Banco Ciudad",
    "municipal": "Banco Municipal", "sanjuan": "Banco San Juan",
    "santacruz": "Banco Santa Cruz", "bancor": "Bancor",
    "coinag": "Banco Coinag", "columbia": "Banco Columbia",
    "delsol": "Banco del Sol", "entrerios": "Banco Entre Ríos",
}
_MERCHANT_NAMES = {
    "coto": "Coto Digital", "jumbo": "Jumbo (Cencosud)",
    "changomas": "Más Online (ChangoMás)", "dia": "Supermercados Día",
    "ypf": "YPF", "pumaenergy": "Puma Energy", "wico": "WICO",
}
_PAYMENT_NETWORK_IDS = {"visa", "mastercard"}


def _fold(value: object) -> str:
    text = unicodedata.normalize("NFD", str(value or ""))
    return "".join(char for char in text if unicodedata.category(char) != "Mn").lower().strip()


def _slugify(value: str) -> str:
    return re.sub(r"^-|-$", "", re.sub(r"[^a-z0-9]+", "-", _fold(value)))


class ClashScraper(BaseScraper):
    """Consulta ambos listados públicos y normaliza sus promociones."""

    def __init__(self):
        super().__init__(name="Clash", url="https://promos.clash.com.ar/")

    async def scrape(self, page=None) -> List[Dict]:
        # La página entrega JSON dentro de un JS estático; urllib evita sumar
        # dependencias y no requiere automatizar el navegador.
        today = datetime.now(ZoneInfo("America/Argentina/Buenos_Aires")).date()
        promotions: List[Dict] = []
        for category, url in _FEEDS.items():
            request = Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; promotions-scraper/1.0)",
                    "Accept": "application/javascript,text/javascript,*/*;q=0.8",
                    "Accept-Language": "es-AR,es;q=0.9",
                },
            )
            with urlopen(request, timeout=30) as response:
                source = response.read().decode("utf-8")
            feed_promotions = self.parse_data_js(source, category, today=today)
            updated_at = self._updated_at(source)
            print(
                f"   Clash/{category}: {len(feed_promotions)} promociones; "
                f"actualización declarada {updated_at or 'sin fecha'}"
            )
            promotions.extend(feed_promotions)

        return promotions

    @classmethod
    def parse_data_js(cls, source: str, category: str, today: Optional[date] = None) -> List[Dict]:
        """Parsea un data.js de Clash y limita registros al período publicado.

        El listado de Clash se publica por período mensual. Al guardar esa
        vigencia, las promociones dejan de mostrarse al cambiar de mes si la
        fuente todavía no publicó un snapshot nuevo.
        """
        if category not in _FEEDS:
            raise ValueError(f"Categoría de Clash desconocida: {category}")
        match = re.fullmatch(r"\s*window\.__clashData\s*=\s*(\{.*\})\s*;?\s*", source, re.DOTALL)
        if not match:
            raise ValueError("Clash data.js no contiene window.__clashData")
        data = json.loads(match.group(1))
        if not isinstance(data, dict):
            raise ValueError("Clash devolvió un objeto de datos inválido")

        today = today or datetime.now(ZoneInfo("America/Argentina/Buenos_Aires")).date()
        period = cls._period_bounds(data.get("meta", {}).get("topbar", {}).get("period"), today)
        banks = {str(item.get("id")): item.get("name") for item in data.get("banks", []) if isinstance(item, dict)}
        merchants = {
            str(item.get("id")): item.get("name")
            for item in data.get("merchants", []) if isinstance(item, dict)
        }
        raw_promotions = data.get("P")
        if not isinstance(raw_promotions, list):
            raise ValueError("Clash data.js no contiene el listado P esperado")

        parsed: List[Dict] = []
        section = _SECTIONS[category]
        for item in raw_promotions:
            if not isinstance(item, dict):
                continue
            promo = cls._normalize_promotion(item, category, section, banks, merchants, period, data)
            if promo:
                parsed.append(promo)
        if raw_promotions and not parsed:
            raise ValueError(f"Clash publicó {len(raw_promotions)} registros, pero ninguno pudo normalizarse")
        cls._make_database_titles_unique(parsed)
        return parsed

    @staticmethod
    def _make_database_titles_unique(promotions: List[Dict]) -> None:
        """Desempata los títulos que colisionarían con la clave única local.

        La base usa (comercio, título, banco) como clave de upsert. Clash puede
        publicar dos ofertas del mismo banco con el mismo nombre pero días,
        topes o tarjetas diferentes; añadir el dato que las distingue evita
        que la segunda sobreescriba a la primera al persistirlas.
        """
        groups: Dict[tuple, List[Dict]] = {}
        for promo in promotions:
            for merchant in promo.get("merchant_brands") or []:
                key = (merchant, promo.get("title", ""), promo.get("bank") or "")
                groups.setdefault(key, []).append(promo)

        for (_, original_title, _), rows in groups.items():
            if len(rows) < 2:
                continue
            candidates = (
                ("valid_days", None),
                ("card_type", None),
                ("tope", None),
                ("payment_method", None),
            )
            qualifier_field = next(
                (field for field, _ in candidates
                 if all(str(row.get(field) or "").strip() for row in rows)
                 and len({str(row[field]).strip().lower() for row in rows}) == len(rows)),
                None,
            )
            for row in rows:
                qualifier = str(row.get(qualifier_field) or "").strip() if qualifier_field else ""
                if not qualifier:
                    qualifier = f"Clash {str(row.get('source_id') or '').rsplit(':', 1)[-1]}"
                row["title"] = f"{original_title} · {qualifier}"[:200]

    @staticmethod
    def _period_bounds(period_label: object, today: date) -> tuple[str, str]:
        match = re.search(r"([a-záéíóúñ]+)\s+(\d{4})", str(period_label or ""), re.IGNORECASE)
        month = _MONTHS.get(_fold(match.group(1))) if match else None
        year = int(match.group(2)) if match else 0
        if not month or not year:
            raise ValueError(f"Clash no publicó un período mensual reconocible: {period_label!r}")
        if (year, month) != (today.year, today.month):
            raise ValueError(
                f"Snapshot de Clash fuera del mes vigente ({period_label}); no se importó"
            )
        first = date(year, month, 1)
        last = date(year, month, calendar.monthrange(year, month)[1])
        return first.isoformat(), last.isoformat()

    @staticmethod
    def _updated_at(source: str) -> Optional[str]:
        match = re.search(r'"updatedAt"\s*:\s*"([^"]+)"', source)
        return match.group(1) if match else None

    @classmethod
    def _normalize_promotion(
        cls,
        item: dict,
        category: str,
        section: str,
        banks: dict,
        merchants: dict,
        period: tuple[str, str],
        data: dict,
    ) -> Optional[Dict]:
        promo_id = str(item.get("id") or "").strip()
        bank_id = str(item.get("bk") or "").strip()
        merchant_id = str(item.get("mc") or "").strip()
        source_bank_name = str(banks.get(bank_id) or "").strip()
        source_merchant_name = str(merchants.get(merchant_id) or "").strip()
        if not promo_id or not source_bank_name or not source_merchant_name:
            return None

        merchant = _MERCHANT_NAMES.get(merchant_id, source_merchant_name)
        discount_value = item.get("d")
        installment_value = item.get("inst")
        if discount_value not in (None, "", 0):
            try:
                discount_percent = float(discount_value)
            except (TypeError, ValueError):
                return None
            discount_label = f"{discount_percent:g}%"
            source_benefit = f"{discount_percent:g}% OFF"
        elif installment_value not in (None, "", 0):
            installment_match = re.search(r"\d{1,2}", str(installment_value))
            if not installment_match:
                return None
            installments = int(installment_match.group(0))
            discount_label = f"{installments} cuotas sin interés"
            # El front de Clash compone el título agregando este sufijo a inst.
            source_benefit = f"{installment_value} cuotas sin interés"
        else:
            # No inventar un tipo de beneficio cuando la fuente cambia el esquema.
            return None

        cards = [
            re.sub(r"\.png$", "", str(card), flags=re.IGNORECASE).replace("_", " ").strip()
            for card in item.get("cards", []) if str(card).strip()
        ]
        note = str(item.get("note") or "").strip()
        reference = str(item.get("_ref") or "").strip()
        condition_text = "\n".join(value for value in (note, reference) if value)
        condition_folded = _fold(condition_text)

        wallet = _WALLET_NAMES.get(bank_id, "") if bank_id in _WALLET_IDS else ""
        bank = "" if bank_id in _WALLET_IDS | _PAYMENT_NETWORK_IDS else _ENTITY_NAMES.get(bank_id, source_bank_name)
        card_wallet = next((name for key, name in _WALLET_NAMES.items() if any(_fold(name) in _fold(card) for card in cards)), "")
        if card_wallet:
            wallet = wallet or card_wallet
        if bank_id in _PAYMENT_NETWORK_IDS:
            payment_method = f"Tarjeta {source_bank_name}"
        elif "nfc" in condition_folded or "sin contacto" in condition_folded:
            payment_method = "Tarjeta · NFC"
        elif "qr" in condition_folded and (wallet or "modo" in condition_folded):
            payment_method = "QR MODO" if wallet == "MODO" or "modo" in condition_folded else "QR"
        elif wallet:
            payment_method = wallet
        elif cards:
            payment_method = "Tarjeta"
        else:
            payment_method = ""

        day_values = item.get("days")
        valid_days = None
        if isinstance(day_values, list) and len(day_values) == 7 and all(value in (0, 1, False, True) for value in day_values):
            selected_days = [_DAYS[index] for index, value in enumerate(day_values) if value]
            valid_days = ", ".join(selected_days) if selected_days else None
            if len(selected_days) == 7:
                valid_days = "Todos los días"

        source_title = f"{source_benefit} en {source_merchant_name} con {source_bank_name}"
        source_url = (
            f"https://promos.clash.com.ar/{section}/promocion/"
            f"{_slugify(source_title)}-{promo_id}/"
        )
        entity = wallet or bank or source_bank_name
        title = f"{discount_label} en {merchant} con {entity}"
        if note:
            title += f" · {note}"
        elif cards:
            title += f" · {', '.join(cards)}"

        store_types = None
        if re.search(r"(?:solo|exclusiv\w*)\s+(?:compras\s+)?online|compras\s+online\s+exclusivas", condition_folded):
            store_types = "Online"
        elif re.search(r"(?:solo|exclusiv\w*)\s+(?:en\s+)?(?:sucursal|presencial)", condition_folded):
            store_types = "Presencial"

        min_purchase = None
        min_match = re.search(
            r"(?:min(?:imo)?\.?\s*(?:de\s*)?compra|compra\s+minima|a\s+partir\s+de|compras?\s+desde)"
            r"[^$]{0,30}\$\s*([\d.,]+)",
            condition_folded,
        )
        if min_match:
            min_purchase = f"${min_match.group(1).rstrip('.,')}"

        cap = str(item.get("cap") or "").strip()
        frequency = str(item.get("fr") or "").strip()
        if cap and _fold(cap) not in {"sin tope", "sin limite", "ilimitado"}:
            tope = f"Tope {cap}" + (f" {frequency}" if frequency else "")
        elif cap:
            tope = cap
        else:
            tope = frequency

        updated_at = str(data.get("updatedAt") or "").strip() or None
        period_label = str(data.get("meta", {}).get("topbar", {}).get("period") or "")
        source_note = f"Resumen informativo de Clash para {period_label}"
        if updated_at:
            source_note += f"; actualización declarada {updated_at[:10]}"
        terms_parts = [source_note, *cards, note, reference]
        terms_raw = "\n".join(dict.fromkeys(part for part in terms_parts if part))
        requirements = [note] if note else []

        return {
            "title": title[:200],
            "merchant_brands": [merchant],
            "merchant_category": category,
            "source_id": f"clash:{section}:{promo_id}",
            "discount": discount_label,
            "bank": bank or None,
            "wallet": wallet or None,
            "card_type": ", ".join(cards) or None,
            "payment_method": payment_method,
            "store_types": store_types,
            "valid_days": valid_days,
            "valid_from": period[0],
            "valid_until": period[1],
            "url": source_url,
            "merchant_url": f"https://promos.clash.com.ar/{section}/",
            "terms_raw": terms_raw[:5000],
            "exclusions": [],
            "requirements": requirements,
            "tope": tope,
            "min_purchase": min_purchase,
            "acumulable": None,
        }