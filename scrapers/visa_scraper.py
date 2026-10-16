"""Promociones Visa publicadas en sus términos oficiales."""
from __future__ import annotations

import asyncio
import os
import re
from datetime import date
from io import BytesIO
from typing import Dict, List, Optional

from .base_scraper import BaseScraper


_VISA_COTO_TERMS_URL = os.getenv(
    "VISA_COTO_TERMS_URL",
    "https://www.visa.com.ar/content/dam/VCOM/regional/lac/SPA/argentina/promociones/terminos-y-condiciones-coto-octubre-2026.pdf",
)
_MONTHS = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
           "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _date_es(value: str) -> Optional[str]:
    match = re.search(r"(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})", value, re.I)
    if not match:
        return None
    day, month, year = match.groups()
    number = _MONTHS.get(month.lower())
    return f"{int(year):04d}-{number:02d}-{int(day):02d}" if number else None


class VisaScraper(BaseScraper):
    """Extrae la promoción Coto desde el legal de Visa sin datos fijos."""
    def __init__(self, terms_url: Optional[str] = None):
        self.terms_url = terms_url or _VISA_COTO_TERMS_URL
        super().__init__(name="Visa", url=self.terms_url)

    async def scrape(self, page=None) -> List[Dict]:
        try:
            promo = self.parse_terms(await asyncio.to_thread(self._fetch_text))
        except Exception as exc:
            print(f"   ⚠️ Visa: no se pudo leer el legal de Coto: {type(exc).__name__}: {exc}")
            return []
        return [promo] if promo else []

    def _fetch_text(self) -> str:
        import requests
        from pypdf import PdfReader
        response = requests.get(self.terms_url, timeout=(10, 45), headers={"Accept": "application/pdf,*/*"})
        response.raise_for_status()
        return "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(response.content)).pages)

    def parse_terms(self, raw_text: str) -> Optional[Dict]:
        text, lower = _normalize(raw_text), _normalize(raw_text).lower()
        if "coto" not in lower or "nfc" not in lower:
            return None
        percent = re.search(r"(\d{1,3})\s*(?:%|off)", text, re.I)
        if not percent:
            return None
        dates = re.findall(r"\d{1,2}\s+de\s+[a-záéíóú]+\s+de\s+\d{4}", text, re.I)
        valid_from = _date_es(dates[0]) if dates else None
        valid_until = _date_es(dates[1]) if len(dates) > 1 else None
        if valid_until and valid_until < date.today().isoformat():
            return None
        day = re.search(r"todos\s+los\s+d[ií]as\s+(lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo)", text, re.I)
        exclusion = re.search(r"(?:6\.|7\.)\s*Exclusiones\s*(.*?)(?:7\.|8\.)\s*(?:Suspensi[oó]n|Contacto|Modificaci[oó]n)", text, re.I)
        return {
            "title": f"Visa {percent.group(1)}% de descuento NFC en Coto",
            "discount": f"{percent.group(1)}% descuento", "bank": "Visa", "card_type": "Débito, Prepaga",
            "payment_method": "Pago sin contacto (NFC) con billetera habilitada", "store_types": "Tiendas",
            "valid_days": day.group(1).capitalize() if day else "Todos los días", "valid_from": valid_from,
            "valid_until": valid_until, "url": self.terms_url, "terms_raw": text,
            "requirements": ["Pago sin contacto (NFC) con Visa Débito o Prepaga emitida en Argentina", "Usar una billetera NFC habilitada por Visa", "No válido pagando con QR"],
            "exclusions": [_normalize(exclusion.group(1))] if exclusion else [],
            "merchant_brands": ["Coto Digital"], "merchant_category": "supermarket", "source": "visa",
        }
