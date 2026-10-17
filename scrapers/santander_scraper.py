"""Beneficios públicos de Santander.

La página ``/personas/beneficios`` es una SPA: sus tarjetas se alimentan de la
API pública ``bff-benefits``.  Este scraper consulta esa fuente estructurada,
por lo que no depende de texto renderizado ni de promociones hardcodeadas.

Sólo rutea comercios que el producto ya muestra como supermercados o
movilidad. Los detalles (legal, vigencia, tope y condiciones) provienen de la
respuesta oficial de cada marca.
"""
from __future__ import annotations

import asyncio
import html
import re
from typing import Any, Dict, List, Optional, Tuple

from .base_scraper import BaseScraper


_PAGE_URL = "https://www.santander.com.ar/personas/beneficios"
_API = "https://www.santander.com.ar/bff-benefits"
# Santander protege su SPA contra clientes que se anuncian como Chrome sin la
# misma huella TLS. La BFF pública, en cambio, admite clientes HTTP honestos;
# no requiere sesión, cookies ni ninguna credencial de usuario.
_HTTP_IDENTITIES = (
    # La BFF no necesita headers de navegador. Probamos primero una sesión sin
    # User-Agent (como la llamada pública más simple) y luego dos clientes
    # HTTP honestos. No se usan cookies, tokens ni datos de una persona.
    {},
    {"User-Agent": "GuzzleHttp/7"},
    {"User-Agent": "curl/8.5.0"},
)
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


def _minimum_purchase(text: str) -> Optional[str]:
    """Obtiene el mínimo publicado, conservando el formato monetario AR.

    La BFF de Santander no expone un campo numérico para este dato: suele
    incluirlo dentro de ``additionalText`` (por ejemplo, ``Mínimo de compra
    $100.000``).  No conviene pasar ese importe por ``float`` porque el punto
    es un separador de miles, no decimal.
    """
    match = re.search(
        r"m[ií]nimo\s+(?:de\s+)?compra\s*(?:de\s*)?\$?\s*([\d.]+(?:,[\d]{1,2})?)",
        text or "",
        re.I,
    )
    if not match:
        return None
    digits = re.sub(r"\D", "", match.group(1).split(",", 1)[0])
    if not digits:
        return None
    return f"${int(digits):,}".replace(",", ".")


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
        """Consulta el catálogo público de Santander sin simular un navegador."""
        loop = asyncio.get_event_loop()
        try:
            brands = await loop.run_in_executor(None, self._brands)
        except Exception as exc:
            print(f"   ⚠️ Santander: no se pudo consultar beneficios: {exc}")
            return []

        targets = [brand for brand in brands if _merchant(str(brand.get("name") or ""))]
        promotions: List[Dict] = []
        for brand in targets:
            try:
                detail = await loop.run_in_executor(None, self._get, f"/brands/{brand['id']}")
            except Exception as exc:
                print(f"   ⚠️ Santander: sin detalle para {brand.get('name')}: {exc}")
                continue
            for item in detail.get("items") or []:
                promotions.extend(self.parse_item(item, brand))
        print(f"✅ {self.name}: {len(promotions)} promociones de supermercado/movilidad")
        return promotions

    @staticmethod
    def _get(path: str, params: Optional[Dict[str, Any]] = None) -> Dict:
        import requests

        last_status = None
        for headers in _HTTP_IDENTITIES:
            # requests agrega un UA propio por defecto. Limpiarlo es distinto
            # de enviar uno vacío y permite probar la variante sin identidad.
            session = requests.Session()
            session.headers.clear()
            response = session.get(f"{_API}{path}", params=params or {}, headers=headers, timeout=(10, 35))
            last_status = response.status_code
            if not response.ok:
                continue
            payload = response.json()
            if isinstance(payload, dict):
                return payload
            raise ValueError(f"respuesta inválida para {path}")
        raise RuntimeError(f"Santander rechazó {path} (HTTP {last_status})")

    def _brands(self) -> List[Dict]:
        # El catálogo es paginado; limitar alto evita una dependencia de una
        # cantidad fija de páginas y sólo se piden detalles de marcas conocidas.
        brands: List[Dict] = []
        page = 1
        while page <= 20:
            payload = self._get("/brands", {"page": page, "limit": 100})
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
            "min_purchase": _minimum_purchase(terms),
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
