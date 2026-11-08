"""Búsqueda pública de productos de Farmacias Dr. Ahorro (WooCommerce)."""
from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from ..models import Offer
from ..registry import Store

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PromoAR/1.0)", "Accept": "text/html"}


def _amount(value: object) -> Optional[float]:
    match = re.search(r"\d[\d.,]*", str(value or ""))
    if not match:
        return None
    raw = match.group(0)
    if "," in raw and "." in raw:
        raw = raw.replace(",", "") if raw.rfind(".") > raw.rfind(",") else raw.replace(".", "").replace(",", ".")
    elif "," in raw:
        tail = raw.rsplit(",", 1)[1]
        raw = raw.replace(",", ".") if len(tail) in (1, 2) else raw.replace(",", "")
    elif "." in raw:
        tail = raw.rsplit(".", 1)[1]
        raw = raw.replace(".", "") if len(tail) == 3 else raw
    try:
        amount = float(raw)
    except ValueError:
        return None
    return amount if amount > 0 else None


def search(store: Store, query: str, limit: int = 8, timeout: float = 8.0) -> list[Offer]:
    host = store.host or "www.farmaciasdrahorro.com.ar"
    try:
        response = requests.get(
            f"https://{host}/", params={"s": query[:120], "post_type": "product"},
            headers=_HEADERS, timeout=timeout, allow_redirects=False,
        )
        if response.status_code != 200 or "text/html" not in response.headers.get("Content-Type", ""):
            return []
        soup = BeautifulSoup(response.content, "html.parser")
    except requests.RequestException:
        return []

    offers = []
    for product in soup.select("li.product, .products .product"):
        link = product.select_one("a[href*='/productos/'], .product-title a[href]")
        price_box = product.select_one(".price")
        if not link or not price_box or "outofstock" in " ".join(product.get("class", [])):
            continue
        target = urljoin(f"https://{host}/", link.get("href", ""))
        parsed = urlsplit(target)
        if parsed.scheme != "https" or parsed.hostname != host:
            continue
        current_node = price_box.select_one("ins .amount") or price_box.select_one(".amount")
        price = _amount(current_node.get_text(" ", strip=True) if current_node else "")
        if not price:
            continue
        old_node = price_box.select_one("del .amount")
        list_price = _amount(old_node.get_text(" ", strip=True) if old_node else "")
        image_node = product.select_one("img")
        image = ""
        if image_node:
            candidate = image_node.get("data-src") or image_node.get("data-lazy-src") or image_node.get("src") or ""
            image_url = urlsplit(urljoin(f"https://{host}/", candidate))
            if image_url.scheme == "https" and image_url.hostname == host:
                image = image_url.geturl()
        title = link.get_text(" ", strip=True)
        if not title:
            continue
        offers.append(Offer(
            store=store.key, store_name=store.name, merchant=None, title=title,
            price=price, list_price=list_price, url=target, image=image,
        ))
        if len(offers) >= max(1, limit):
            break
    return offers
