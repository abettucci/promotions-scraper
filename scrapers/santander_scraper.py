"""Beneficios públicos de Santander.

La página ``/personas/beneficios`` es una SPA: sus tarjetas se alimentan de la
API pública ``bff-benefits``.  Este scraper consulta esa fuente estructurada,
por lo que no depende de texto renderizado ni de promociones hardcodeadas.

Sólo rutea comercios que el producto ya muestra como supermercados o
movilidad. Los detalles (legal, vigencia, tope y condiciones) provienen de la
respuesta oficial de cada marca.
"""
from __future__ import annotations

import html
import re
from typing import Any, Dict, List, Optional, Tuple

from .base_scraper import BaseScraper


_PAGE_URL = "https://www.santander.com.ar/personas/beneficios"
_RESULTS_URL = (
    "https://www.santander.com.ar/personas/beneficios"
    "#/results?category-code=SUP%2CTRA"
)
_API = "https://www.santander.com.ar/bff-benefits"
# Nombre publicado por Santander -> comercio y categoría internos. No son
# promociones: la lista de beneficios y sus condiciones siempre viene de API.
_MERCHANTS: Tuple[Tuple[str, str, str], ...] = (
    (r"\bcarrefour\b", "Carrefour", "supermarket"),
    (r"\bcoto\b", "Coto Digital", "supermarket"),
    (r"\bjumbo\b", "Jumbo (Cencosud)", "supermarket"),
    (r"\bdisco\b", "Disco", "supermarket"),
    (r"\bvea\b", "Vea", "supermarket"),
    (r"chango\s*m[aá]s|m[aá]s\s*online", "Más Online (ChangoMás)", "supermarket"),
    (r"\bd[ií]a\b", "Supermercados Día", "supermarket"),
    (r"\buber\b", "Uber", "mobility"),
    (r"\bcabify\b", "Cabify", "mobility"),
    (r"\bdidi\b", "DiDi", "mobility"),
    (r"\bsube\b|transporte\s+p[uú]blico", "Transporte público", "mobility"),
)
_DAY_NAMES = (
    ("monday", "Lunes"), ("tuesday", "Martes"), ("wednesday", "Miércoles"),
    ("thursday", "Jueves"), ("friday", "Viernes"), ("saturday", "Sábado"),
    ("sunday", "Domingo"),
)


def _text(value: Any) -> str:
    value = html.unescape(str(value or ""))
    value = re.sub(r"<br\s*/?>|</p>|</li>", "\n", value, flags=re.I)
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _money(value: Any) -> Optional[str]:
    try:
        return f"${int(float(value)):,}".replace(",", ".")
    except (TypeError, ValueError):
        return None


def _days(item: Dict[str, Any]) -> str:
    if item.get("fullWeek"):
        return "Todos los días"
    selected = [label for key, label in _DAY_NAMES if item.get(key)]
    return ", ".join(selected) if selected else "Todos los días"


def _merchant(name: str) -> Optional[Tuple[str, str]]:
    for pattern, canonical, category in _MERCHANTS:
        if re.search(pattern, name or "", re.I):
            return canonical, category
    return None


class SantanderScraper(BaseScraper):
    def __init__(self):
        super().__init__(name="Santander", url=_PAGE_URL)

    async def scrape(self, page=None) -> List[Dict]:
        """Consulta la API con la misma sesión que crea la SPA oficial.

        La BFF rechaza HTTP directo (403). El sitio primero crea cookies y
        encabezados de navegador; interceptamos ese request real y reutilizamos
        el ``APIRequestContext`` de Playwright, sin emular ni inventar tokens.
        """
        from playwright.async_api import async_playwright

        bff_headers: Dict[str, str] = {}
        browser = None
        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(
                    headless=True,
                    # Santander's edge has intermittently closed the HTTP/2
                    # stream from GitHub-hosted Chromium. Its SPA and BFF both
                    # support HTTP/1.1, which avoids that transport failure.
                    args=[
                        "--disable-blink-features=AutomationControlled", "--disable-http2",
                        "--no-sandbox",
                    ],
                )
                context = await browser.new_context(
                    locale="es-AR",
                    user_agent=(
                        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
                    ),
                )
                page = await context.new_page()

                def capture_request(request) -> None:
                    if "/bff-benefits/brands" not in request.url or request.method != "GET":
                        return
                    # No copiar headers de transporte ni cookies: Playwright los
                    # administra en la sesión. Estos son los headers de aplicación
                    # que Santander validó para la consulta de su propia SPA.
                    allowed = {
                        "accept", "accept-language", "origin", "referer", "user-agent",
                        "sec-ch-ua", "sec-ch-ua-mobile", "sec-ch-ua-platform",
                    }
                    bff_headers.update({
                        key: value for key, value in request.headers.items()
                        if key.lower() in allowed
                    })

                page.on("request", capture_request)
                try:
                    await page.goto(_RESULTS_URL, wait_until="domcontentloaded", timeout=45_000)
                except Exception as exc:
                    # La SPA puede mantener una conexión analítica abierta; si la
                    # navegación parcial ya originó la BFF, todavía sirve.
                    print(f"   ⚠️ Santander: navegación parcial: {exc}")
                await page.wait_for_timeout(4_000)
                if not bff_headers:
                    print("   ⚠️ Santander: la SPA no inició la BFF; no se publica un resultado vacío")
                    return []

                async def api_get(path: str, params: Optional[Dict[str, Any]] = None) -> Dict:
                    response = await context.request.get(
                        f"{_API}{path}", params=params or {}, headers=bff_headers, timeout=35_000,
                    )
                    if not response.ok:
                        raise RuntimeError(f"HTTP {response.status} para {path}")
                    payload = await response.json()
                    if not isinstance(payload, dict):
                        raise ValueError(f"respuesta inválida para {path}")
                    return payload

                brands = await self._brands(api_get)
                targets = [brand for brand in brands if _merchant(str(brand.get("name") or ""))]
                promotions: List[Dict] = []
                for brand in targets:
                    try:
                        detail = await api_get(f"/brands/{brand['id']}")
                    except Exception as exc:
                        print(f"   ⚠️ Santander: sin detalle para {brand.get('name')}: {exc}")
                        continue
                    for item in detail.get("items") or []:
                        promotions.extend(self.parse_item(item, brand))
                print(f"✅ {self.name}: {len(promotions)} promociones de supermercado/movilidad")
                await context.close()
                return promotions
        except Exception as exc:
            print(f"   ⚠️ Santander: no se pudo consultar beneficios: {exc}")
            return []

    async def _brands(self, api_get) -> List[Dict]:
        # El catálogo es paginado; limitar alto evita una dependencia de una
        # cantidad fija de páginas y sólo se piden detalles de marcas conocidas.
        brands: List[Dict] = []
        page = 1
        while page <= 20:
            payload = await api_get("/brands", {"page": page, "limit": 100})
            items = payload.get("items") or []
            if not isinstance(items, list):
                break
            brands.extend(item for item in items if isinstance(item, dict) and item.get("id"))
            total = payload.get("totalItems")
            if not items or len(brands) >= int(total or 0) or len(items) < 100:
                break
            page += 1
        return brands

    def parse_item(self, item: Dict[str, Any], brand: Dict[str, Any]) -> List[Dict]:
        """Convierte ahorro y cuotas de una publicación oficial en promos."""
        merchant_info = _merchant(str(brand.get("name") or ""))
        if not merchant_info or not isinstance(item, dict):
            return []
        merchant, category = merchant_info
        texts = item.get("texts") or {}
        legal = _text(item.get("legal"))
        additional = _text(item.get("additionalText"))
        terms = "\n\n".join(part for part in (additional, legal) if part)
        if not terms:
            return []

        valid_from = str(item.get("startDatePublication") or "")[:10] or None
        valid_until = str(item.get("endDatePublication") or "")[:10] or None
        days = _days(item)
        payment_type = (item.get("paymentType") or {}).get("code")
        tag = item.get("tag") or {}
        tag_label = _text(tag.get("description")) if tag else ""
        categories = {str(value.get("code") or "") for value in item.get("categories") or [] if isinstance(value, dict)}
        requirements = [part for part in (tag_label, additional) if part]
        if "SOR" in categories and not any("sorpresa" in part.lower() for part in requirements):
            requirements.insert(0, "Suscripción al programa Sorpresa Santander")

        card_type = "Crédito, Débito" if re.search(r"cr[eé]dito\s+y/o\s+d[eé]bito|d[eé]bito\s+y/o\s+cr[eé]dito", terms, re.I) else None
        if not card_type and re.search(r"tarjeta.*d[eé]bito|d[eé]bito", terms, re.I):
            card_type = "Débito"
        elif not card_type and re.search(r"tarjeta.*cr[eé]dito|cr[eé]dito", terms, re.I):
            card_type = "Crédito"
        wallet = "MODO" if payment_type == "M" or "EPM" in categories else None
        payment_method = "QR con App Santander o MODO" if wallet else "Tarjetas Santander"
        if re.search(r"nfc|sin contacto|contactless", terms, re.I):
            payment_method = "Pago sin contacto (NFC) con tarjeta Santander"

        if category == "mobility":
            store_types = "Presencial" if merchant == "Transporte público" else "App"
        else:
            store_types = "Online" if re.search(r"online|app|web", terms, re.I) and not re.search(r"sucursal|local(?:es)? f[ií]sic", terms, re.I) else "Tiendas"
        base = {
            "bank": "Santander",
            "wallet": wallet,
            "card_type": card_type,
            "payment_method": payment_method,
            "store_types": store_types,
            "valid_days": days,
            "valid_from": valid_from,
            "valid_until": valid_until,
            "url": f"{_PAGE_URL}#/?brandId={brand.get('id')}",
            "image_url": brand.get("desktopMinImage") or brand.get("desktopImage"),
            "terms_raw": terms,
            "tope": _money(item.get("topAmount")),
            "exclusions": [legal] if re.search(r"no aplica|no v[aá]lido|no incluye|exclu", legal, re.I) else [],
            "requirements": requirements,
            "merchant_brands": [merchant],
            "merchant_category": category,
            "mobility_kind": "public_transit" if merchant == "Transporte público" else ("ride_hailing" if category == "mobility" else None),
        }

        qualifier = f" ({tag_label})" if tag_label else ""
        suffix = f" - {days}" if days != "Todos los días" else ""
        promotion_id = item.get("idPromotion") or item.get("id")
        out: List[Dict] = []
        discount = texts.get("discount", item.get("customerDiscount"))
        try:
            if float(discount) > 0:
                kind = "reintegro" if (item.get("benefitType") or {}).get("code") == "A" else "descuento"
                out.append({
                    **base,
                    "title": f"Santander {float(discount):g}% de {kind} en {merchant}{qualifier}{suffix}",
                    "discount": f"{float(discount):g}% {kind}",
                    "source_id": f"santander:{promotion_id}:discount",
                })
        except (TypeError, ValueError):
            pass

        installments = item.get("finalQuote") or texts.get("fees")
        if item.get("interestFreeFees") and installments:
            out.append({
                **base,
                "title": f"Santander {installments} cuotas sin interés en {merchant}{qualifier}{suffix}",
                "discount": f"{installments} cuotas sin interés",
                "source_id": f"santander:{promotion_id}:installments",
            })
        return out
