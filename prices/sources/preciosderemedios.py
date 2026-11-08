"""Precios públicos de referencia por principio activo, no por farmacia."""
from __future__ import annotations

from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from ..matching import norm
from ..models import Offer
from ..registry import Store

_BASE = "https://preciosderemedios.com.ar/"
_HOST = "preciosderemedios.com.ar"
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PromoAR/1.0)", "Accept": "text/html"}


def _get(url: str, params: dict, timeout: float):
    # El host y las rutas son constantes; la búsqueda viaja en query params.
    response = requests.get(url, params=params, headers=_HEADERS, timeout=timeout,
                            allow_redirects=False)
    parsed = urlsplit(response.url)
    if (response.status_code != 200 or "text/html" not in response.headers.get("Content-Type", "")
            or parsed.hostname != _HOST or parsed.scheme != "https"):
        return None
    return BeautifulSoup(response.content, "html.parser")


def search(store: Store, query: str, limit: int = 8, timeout: float = 8.0) -> list[Offer]:
    try:
        results = _get(_BASE + "result/", {"busqueda": query[:100]}, timeout)
        if not results:
            return []
        combo_links = []
        seen = set()
        for link in results.select("a[href*='combo=']"):
            label = link.get_text(" ", strip=True)
            if label and label not in seen:
                seen.add(label)
                combo_links.append((label, urljoin(_BASE, link.get("href", ""))))
        query_norm = norm(query)
        selected = next((item for item in combo_links if norm(item[0]) == query_norm), None)
        # No se elige al azar entre mezclas de principios activos distintos.
        if selected is None and len(combo_links) == 1:
            selected = combo_links[0]
        if selected is None:
            return []

        target = urlsplit(selected[1])
        if target.scheme != "https" or target.hostname != _HOST:
            return []
        page = _get(selected[1], {}, timeout)
        if not page:
            return []
        offers = []
        for row in page.select("tr[data-price]")[:max(1, limit)]:
            try:
                price = float(row.get("data-price", ""))
            except (TypeError, ValueError):
                continue
            if price <= 0:
                continue
            product_node = row.select_one(".product-text")
            product_name = product_node.get("title", "").strip() if product_node else ""
            if not product_name and product_node:
                product_name = product_node.get_text(" ", strip=True)
            if not product_name:
                continue
            href = row.select_one("a[href]")
            product_url = urljoin(_BASE, href.get("href", "")) if href else selected[1]
            parsed = urlsplit(product_url)
            if parsed.scheme != "https" or parsed.hostname != _HOST:
                product_url = selected[1]
            lab = row.select_one(".laboratorio-text")
            brand = lab.get_text(" ", strip=True) if lab else ""
            offers.append(Offer(
                store=store.key, store_name=store.name, merchant=None,
                title=product_name, brand=brand, price=price, url=product_url,
            ))
        return offers
    except requests.RequestException:
        return []
