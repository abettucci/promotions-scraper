"""Consulta acotada de precios publicados de suplementos.

La fuente se consulta solo para búsquedas de suplementos detectadas por el
asistente. No acepta URLs del usuario ni persiste las consultas: evita que el
bot se convierta en un proxy arbitrario y limita el uso de una fuente externa.
"""
from __future__ import annotations

import json
import re
import time
import unicodedata
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


_BASE_URL = "https://www.supleradar.com.ar"
_SEARCH_URL = f"{_BASE_URL}/buscar"
_CACHE_TTL_SECONDS = 15 * 60
_cache: dict[str, tuple[float, Optional["SupplementPrice"]]] = {}


@dataclass(frozen=True)
class SupplementPrice:
    """El mejor precio publicado para un producto en la fuente consultada."""

    product_name: str
    store_name: str
    price: Optional[int]
    transfer_price: Optional[int]
    offer_count: Optional[int]
    source_url: str


def _norm(value: object) -> str:
    text = unicodedata.normalize("NFD", str(value or ""))
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    return re.sub(r"\s+", " ", text.lower()).strip()


def _fetch_html(url: str, *, params: Optional[dict[str, str]] = None) -> Optional[str]:
    """Obtiene HTML público con límites de tiempo y sin seguir redirecciones."""
    try:
        response = requests.get(
            url,
            params=params,
            headers={"User-Agent": "promotions-scraper/1.0 (+price lookup)"},
            timeout=(3, 10),
            allow_redirects=False,
        )
        if response.status_code != 200:
            return None
        return response.text
    except requests.RequestException:
        return None


def _price(value: object) -> Optional[int]:
    digits = re.sub(r"\D", "", str(value or ""))
    return int(digits) if digits else None


def _candidate_score(query: str, candidate_name: str) -> int:
    aliases = {"protein": "proteina", "proteinas": "proteina"}
    query_tokens = {aliases.get(token, token) for token in re.findall(r"[a-z0-9]+", _norm(query))
                    if len(token) > 1}
    candidate_tokens = {aliases.get(token, token) for token in re.findall(r"[a-z0-9]+", _norm(candidate_name))
                        if len(token) > 1}
    score = len(query_tokens & candidate_tokens)
    # Variantes vegetales, aisladas o de otra línea no son un buen reemplazo
    # cuando el usuario pide la proteína estándar de una marca.
    for variant in ("vegetal", "plant", "isolate", "platinum", "vegana"):
        if variant in candidate_tokens and variant not in query_tokens:
            score -= 2
    return score


def _find_product_page(search_html: str, query: str) -> Optional[str]:
    soup = BeautifulSoup(search_html, "html.parser")
    candidates: list[tuple[int, str]] = []
    for link in soup.find_all("a", href=re.compile(r"^/p/[a-z0-9-]+/?$", re.I)):
        href = str(link.get("href") or "")
        name_element = link.select_one(".card__name, .product-name, h2, h3")
        name = name_element.get_text(" ", strip=True) if name_element else link.get_text(" ", strip=True)
        if name and href:
            candidates.append((_candidate_score(query, name), href))
    if not candidates:
        return None
    score, href = max(candidates, key=lambda item: item[0])
    # Requerimos al menos marca/tipo o una coincidencia fuerte para no devolver
    # un producto diferente por una búsqueda demasiado ambigua.
    return urljoin(_BASE_URL, href) if score >= 2 else None


def _json_ld_product(soup: BeautifulSoup) -> tuple[str, Optional[int], Optional[int]]:
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            payload = json.loads(script.get_text(strip=True))
        except (TypeError, ValueError):
            continue
        entries = payload if isinstance(payload, list) else [payload]
        for entry in entries:
            if not isinstance(entry, dict) or entry.get("@type") != "Product":
                continue
            offers = entry.get("offers") or {}
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            try:
                count = int(offers.get("offerCount")) if offers.get("offerCount") else None
            except (TypeError, ValueError):
                count = None
            return str(entry.get("name") or ""), _price(offers.get("lowPrice")), count
    return "", None, None


def _parse_product_page(page_html: str, source_url: str) -> Optional[SupplementPrice]:
    soup = BeautifulSoup(page_html, "html.parser")
    product_name, structured_price, offer_count = _json_ld_product(soup)

    best = soup.select_one(".offer--best, .best-box, [data-best-offer]")
    if best is None:
        return None
    best_text = best.get_text(" ", strip=True)
    store_element = best.select_one(".offer__store, .best-box__store, .store")
    price_element = best.select_one(".offer__price, .best-box__price, .price")
    transfer_element = best.select_one(".offer__transfer, .best-box__transfer, .transfer")

    store_name = store_element.get_text(" ", strip=True) if store_element else ""
    store_name = re.sub(r"^(?:en|tienda)\s+", "", store_name, flags=re.I).strip()
    if not store_name:
        store_match = re.search(r"\ben\s+([\w .&'-]+?)(?:\s+\$|$)", best_text, re.I)
        store_name = store_match.group(1).strip() if store_match else ""
    price = _price(price_element.get_text(" ", strip=True)) if price_element else structured_price
    if price is None:
        price = structured_price
    transfer_price = _price(transfer_element.get_text(" ", strip=True)) if transfer_element else None
    if not transfer_price:
        transfer_match = re.search(r"\$\s*([\d.]+)\s+con\s+transfer", best_text, re.I)
        transfer_price = _price(transfer_match.group(1)) if transfer_match else None

    if not product_name:
        heading = soup.select_one("h1")
        product_name = heading.get_text(" ", strip=True) if heading else ""
    if not store_name or price is None:
        return None
    return SupplementPrice(
        product_name=product_name or "Suplemento",
        store_name=store_name,
        price=price,
        transfer_price=transfer_price,
        offer_count=offer_count,
        source_url=source_url,
    )


def find_supplement_price(query: str) -> Optional[SupplementPrice]:
    """Busca una comparación pública de precios para un suplemento.

    La consulta tiene una longitud y caracteres limitados; es el único dato que
    se envía a la fuente externa. Los resultados se cachean 15 minutos por
    producto para reducir carga y variaciones entre consultas consecutivas.
    """
    normalized = _norm(query)
    if not normalized or len(normalized) > 120 or not re.fullmatch(r"[a-z0-9 .,+()/-]+", normalized):
        return None
    now = time.monotonic()
    cached = _cache.get(normalized)
    if cached and now - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1]

    search_html = _fetch_html(_SEARCH_URL, params={"q": normalized})
    product_url = _find_product_page(search_html, normalized) if search_html else None
    result = None
    if product_url:
        page_html = _fetch_html(product_url)
        if page_html:
            result = _parse_product_page(page_html, product_url)
    _cache[normalized] = (now, result)
    return result
