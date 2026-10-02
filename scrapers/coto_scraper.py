#!/usr/bin/env python3
"""Promociones de Coto desde el feed público de su página de descuentos.

La página pública ``/descuentos`` se alimenta de ``getPromocionesMulticanal``.
Ese feed incluye tarjetas online (``promocionesDigitales``) y de sucursal
(``promocionesSucursalesFisicas``), con el beneficio y las condiciones
resumidas. Es la fuente de catálogo: no hay listados hardcodeados.

Notas del feed:
  - Requiere un User-Agent de navegador (python-requests recibe 403).
  - El host viejo www.cotodigital.com.ar redirige (301) a www.coto.com.ar.
  - ``vigenciaDesde``/``vigenciaHasta`` suelen venir en null: la vigencia real
    está en ``observacion`` ("Del 01/10 al 31/10/2026").
  - El logo (``icono``) es la entidad que muestra la tarjeta; la descripción a
    veces arrastra texto copiado de otra tarjeta (p. ej. Columbia dice "app de
    Comafi"), por eso el icono manda.
"""
import asyncio
import json
import os
import re
import tempfile
from datetime import date
from typing import Any, Dict, List, Optional

try:
    from playwright.async_api import async_playwright
except ImportError:  # La fuente primaria no requiere browser.
    async_playwright = None


# Endpoints fijos de la página pública de descuentos de Coto (no se arman con
# datos remotos). El primero es el host actual; el segundo, el histórico.
_COTO_MULTICHANNEL_URLS = (
    "https://www.coto.com.ar/rest/model/atg/actors/cProfileActor/getPromocionesMulticanal?enviroment=ag",
    "https://www.cotodigital.com.ar/rest/model/atg/actors/cProfileActor/getPromocionesMulticanal?enviroment=ag",
)
_ALLOWED_HOSTS = ("www.coto.com.ar", "www.cotodigital.com.ar")
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "es-AR,es;q=0.9",
    "Referer": "https://www.coto.com.ar/descuentos",
}

# Fragmento del nombre del icono → (bank, wallet, etiqueta para el título).
# El orden importa: "ciudadania_portena" contiene "ciudad".
_ICON_ENTITIES = (
    ("ciudadania", (None, None, "Ciudadanía Porteña")),
    ("comunidad", (None, None, "Comunidad Coto")),
    ("jubilados", (None, None, "Jubilados y pensionados")),
    ("beneficios_anses", ("ANSES", None, "ANSES")),
    ("debito", (None, None, "Tarjetas de débito")),
    ("mercadopago", (None, "Mercado Pago", "Mercado Pago")),
    ("modo", (None, "MODO", "MODO")),
    ("amex", ("American Express", None, "American Express")),
    ("bbva", ("BBVA", None, "BBVA")),
    ("bancor", ("Bancor", None, "Bancor")),
    ("columbia", ("Banco Columbia", None, "Banco Columbia")),
    ("credicoop", ("Banco Credicoop", None, "Banco Credicoop")),
    ("comafi", ("Banco Comafi", None, "Banco Comafi")),
    ("hipotecario", ("Banco Hipotecario", None, "Banco Hipotecario")),
    ("icbc", ("ICBC", None, "ICBC")),
    ("naranjax", ("Naranja X", None, "Naranja X")),
    ("galicia", ("Banco Galicia", None, "Banco Galicia")),
    ("macro", ("Banco Macro", None, "Banco Macro")),
    ("patagonia", ("Banco Patagonia", None, "Banco Patagonia")),
    ("supervielle", ("Banco Supervielle", None, "Banco Supervielle")),
    ("santander", ("Banco Santander", None, "Banco Santander")),
    ("tci", ("Tarjeta Coto Inteligente", None, "Tarjeta Coto TCI")),
    ("ciudad", ("Banco Ciudad", None, "Banco Ciudad")),
    ("nacion", ("Banco Nación", None, "Banco Nación")),
    ("provincia", ("Banco Provincia", None, "Banco Provincia")),
)

# Fallback cuando el icono no es reconocible: se busca la entidad en el texto.
_TEXT_ENTITIES = (
    (r"ciudadan[ií]a\s+porte[ñn]a", (None, None, "Ciudadanía Porteña")),
    (r"banco\s+macro|\bmacro\b", ("Banco Macro", None, "Banco Macro")),
    (r"banco\s+(?:de\s+la\s+)?naci[oó]n|\bbna\b", ("Banco Nación", None, "Banco Nación")),
    (r"banco\s+ciudad", ("Banco Ciudad", None, "Banco Ciudad")),
    (r"banco\s+(?:de\s+la\s+)?provincia|cuenta\s+dni", ("Banco Provincia", None, "Banco Provincia")),
    (r"galicia", ("Banco Galicia", None, "Banco Galicia")),
    (r"santander", ("Banco Santander", None, "Banco Santander")),
    (r"\bbbva\b", ("BBVA", None, "BBVA")),
    (r"\bicbc\b", ("ICBC", None, "ICBC")),
    (r"patagonia", ("Banco Patagonia", None, "Banco Patagonia")),
    (r"supervielle", ("Banco Supervielle", None, "Banco Supervielle")),
    (r"credicoop", ("Banco Credicoop", None, "Banco Credicoop")),
    (r"comafi", ("Banco Comafi", None, "Banco Comafi")),
    (r"columbia", ("Banco Columbia", None, "Banco Columbia")),
    (r"naranja\s*x", ("Naranja X", None, "Naranja X")),
    (r"american\s+express|\bamex\b", ("American Express", None, "American Express")),
    (r"mercado\s*pago", (None, "Mercado Pago", "Mercado Pago")),
    (r"\bmodo\b", (None, "MODO", "MODO")),
)

_DAY_ORDER = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")
_DAY_ALIASES = {
    "lunes": "Lunes", "martes": "Martes", "miercoles": "Miércoles", "miércoles": "Miércoles",
    "jueves": "Jueves", "viernes": "Viernes", "sabado": "Sábado", "sábado": "Sábado",
    "domingo": "Domingo",
}
_CARD_BRANDS = (
    (r"\bvisa\b", "Visa"),
    (r"master\s*card", "Mastercard"),
    (r"\bcabal\b", "Cabal"),
    (r"american\s+express|\bamex\b", "American Express"),
)


def _debug_dump(name: str, content: str) -> None:
    """Guarda artefactos de debug fuera del repo, sólo con DEBUG_SCRAPER."""
    if os.environ.get("DEBUG_SCRAPER", "").lower() not in ("1", "true", "yes"):
        return
    path = os.path.join(tempfile.gettempdir(), name)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    print(f"   💾 Debug: {path}")


class CotoScraper:
    def __init__(self):
        self.name = 'Coto Digital'
        # Fuente visible para quien abre "Ver promoción". El JSON fijo de
        # arriba es el mismo que consume esta pantalla Angular de Coto.
        self.url = 'https://www.coto.com.ar/descuentos'

    async def scrape(self) -> List[Dict]:
        """Scraping de promociones bancarias de Coto Digital"""
        print(f"\n🔍 Scraping {self.name} - Descuentos multicanal...")
        print(f"   🌐 URL: {self.url}")

        payload = await self._fetch_multichannel_payload()
        if payload is None:
            # Fallback: abrir la página con un navegador y capturar el mismo
            # JSON que pide Angular (por si el WAF bloquea requests directos).
            payload = await self._fetch_payload_with_browser()
        if payload is None:
            print(f"   ⚠️ {self.name}: no se pudo leer la fuente oficial; no se devuelven promos")
            return []

        promotions = self._parse_payload(payload)
        print(f"\n✅ {self.name}: {len(promotions)} promociones encontradas (fuente oficial)")
        return promotions

    # ──────────────────────────────────────────────────────────────────────
    # Descarga
    # ──────────────────────────────────────────────────────────────────────

    async def _fetch_multichannel_payload(self) -> Optional[Dict]:
        """Pide el feed con requests; prueba el host actual y el histórico."""
        try:
            import requests
        except ImportError:
            print("   ⚠️ requests no está instalado; se usará el navegador")
            return None

        def request_payload(url: str) -> Any:
            # Los redirects se siguen a mano y sólo dentro de los hosts de Coto.
            for _ in range(3):
                response = requests.get(
                    url, headers=_HEADERS, timeout=(8, 30), allow_redirects=False,
                )
                location = response.headers.get("Location") if response.is_redirect else None
                if not location:
                    response.raise_for_status()
                    return response.json()
                host = re.sub(r"^https?://([^/]+).*$", r"\1", location)
                if host not in _ALLOWED_HOSTS:
                    raise ValueError(f"redirect inesperado a {host}")
                url = location
            raise ValueError("demasiados redirects")

        for url in _COTO_MULTICHANNEL_URLS:
            try:
                payload = await asyncio.to_thread(request_payload, url)
            except Exception as error:
                print(f"   ⚠️ Fuente estructurada de Coto no disponible ({type(error).__name__}: {error})")
                continue
            if self._result_of(payload) is not None:
                _debug_dump("debug_coto_multicanal.json", json.dumps(payload, ensure_ascii=False))
                return payload
            print("   ⚠️ La fuente estructurada de Coto devolvió un formato inválido")
        return None

    async def _fetch_payload_with_browser(self) -> Optional[Dict]:
        if async_playwright is None:
            return None
        print("   🔄 Reintentando con navegador (captura del JSON de la página)...")
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                try:
                    context = await browser.new_context(user_agent=_HEADERS["User-Agent"])
                    page = await context.new_page()
                    async with page.expect_response(
                        lambda r: "getPromocionesMulticanal" in r.url and r.status == 200,
                        timeout=45000,
                    ) as response_info:
                        await page.goto(self.url, wait_until="domcontentloaded", timeout=60000)
                    payload = await (await response_info.value).json()
                finally:
                    await browser.close()
        except Exception as error:
            print(f"   ⚠️ Navegador sin respuesta del feed ({type(error).__name__})")
            return None
        return payload if self._result_of(payload) is not None else None

    @staticmethod
    def _result_of(payload: Any) -> Optional[Dict]:
        result = payload.get("result") if isinstance(payload, dict) else None
        return result if isinstance(result, dict) else None

    # ──────────────────────────────────────────────────────────────────────
    # Parseo
    # ──────────────────────────────────────────────────────────────────────

    def _parse_payload(self, payload: Dict) -> List[Dict]:
        result = self._result_of(payload) or {}
        promotions: List[Dict] = []
        for field, is_digital in (
            ("promocionesDigitales", True),
            ("promocionesSucursalesFisicas", False),
        ):
            raw_promotions = result.get(field, [])
            if not isinstance(raw_promotions, list):
                continue
            for raw_promo in raw_promotions:
                promo = self._parse_multichannel_promotion(raw_promo, is_digital)
                if promo:
                    promotions.append(promo)
                elif isinstance(raw_promo, dict):
                    print(f"   ⏭️ Coto {raw_promo.get('id')}: sin beneficio publicado, se omite")
        return self._ensure_unique_titles(self._deduplicate_multichannel_promotions(promotions))

    def _parse_multichannel_promotion(self, raw_promo: Any, is_digital: bool) -> Optional[Dict]:
        if not isinstance(raw_promo, dict):
            return None

        description = self._clean_value(raw_promo.get("descripcion"))
        observation = self._clean_value(raw_promo.get("observacion"))
        terms_label = self._clean_value(raw_promo.get("labelTerminos"))
        label = self._clean_value(raw_promo.get("textoDescuento"))
        icon = self._clean_value(raw_promo.get("icono"))
        terms_raw = " ".join(value for value in (label, description, observation, terms_label) if value)
        # No inventamos beneficios: si Coto no publica un porcentaje, cuotas o
        # reintegro en ninguno de sus campos, la tarjeta no es comparable.
        discount = self._benefit_label(label, description, observation)
        if not description or not discount:
            return None

        bank, wallet, entity_label = self._resolve_entity(icon, description, observation)
        # "Pagando con MODO desde la app de <banco>": el banco es la entidad y
        # MODO la billetera (antes el texto pisaba al logo).
        if bank and not wallet and re.search(r"\bmodo\b", description, re.I):
            wallet = "MODO"

        card_type = self._card_type(description, discount)
        payment_method = self._payment_method(description, observation, wallet, card_type)
        if not (bank or wallet or entity_label):
            return None
        # Promos sin entidad (p. ej. "15% Tarjetas de débito") se identifican
        # por el medio de pago para el dedup universal.
        if not bank and not wallet and not payment_method:
            payment_method = card_type or entity_label

        valid_days = self._valid_days(raw_promo)
        valid_from, valid_until = self._validity(raw_promo, f"{observation} {description}")

        requirements: List[str] = []
        if is_digital:
            requirements.append("Exclusivo para compras online en Coto Digital")
        else:
            requirements.append("Válido en sucursales Coto (compras presenciales)")
        if re.search(r"pagando\s+con\s+qr", terms_raw, re.I):
            requirements.append("Pago con QR")
        if re.search(r"miembro\s+de\s+(?:nuestra\s+)?comunidad", terms_raw, re.I):
            requirements.append("Ser miembro de Comunidad Coto")
        if re.search(r"presentando\s+dni", terms_raw, re.I):
            requirements.append("Presentar DNI")
        if re.search(r"prod(?:uctos|\.)\s+seleccionados|aplica\s+en\s+electro|productos\s+de\s+electro", observation, re.I):
            requirements.append(re.split(r"\.\s+(?:Vigencia\s+)?Del\s+\d", observation, maxsplit=1, flags=re.I)[0].strip())
        if re.search(r"no\s+acumula", observation, re.I):
            requirements.append(re.search(r"no\s+acumula[^.]*", observation, re.I).group(0).strip())

        exclusions = ""
        if re.search(r"aplica[n]?\s+exclu", terms_raw, re.I):
            exclusions = "Aplican exclusiones. Consultá los legales de Coto antes de pagar."

        channel_label = "Online" if is_digital else "Sucursal"
        qualifier = self._qualifier(description, observation)
        title_entity = entity_label
        if bank and wallet:
            title_entity = f"{entity_label} + {wallet}"
        title = f"{title_entity} {discount}"
        if qualifier:
            title += f" ({qualifier})"
        if valid_days:
            title += f" - {valid_days}"
        title += f" - {channel_label}"

        return {
            "title": title,
            "discount": discount,
            "bank": bank,
            "wallet": wallet,
            "card_type": card_type,
            "payment_method": payment_method,
            "store_types": "Online" if is_digital else "Tiendas",
            "valid_days": valid_days,
            "valid_from": valid_from,
            "valid_until": valid_until,
            "url": self.url,
            "source_id": f"coto-{self._clean_value(raw_promo.get('id'))}",
            "terms_raw": terms_raw,
            "exclusions": exclusions,
            "requirements": " | ".join(requirements),
            "tope": self._extract_tope(observation or terms_raw),
            "min_purchase": self._extract_min_purchase(terms_raw),
        }

    @staticmethod
    def _clean_value(value: Any) -> str:
        if value is None or str(value).lower() == "null":
            return ""
        return re.sub(r"\s+", " ", str(value)).strip()

    @staticmethod
    def _benefit_label(source_label: str, *text_fields: str) -> str:
        """Normaliza el beneficio publicado, con fallback al texto dinámico.

        Coto normalmente ofrece ``textoDescuento`` ("15% DE DESCUENTO",
        "18 CUOTAS SIN INTERÉS", "15% TARJETAS DE DÉBITO"). Cuando llega vacío,
        el beneficio se extrae de la descripción u observación.
        """
        label = CotoScraper._clean_value(source_label)
        text = " ".join(field for field in text_fields if field)
        cuotas_re = r"(?:hasta\s+)?((?:\d{1,2}\s*-\s*)*)(\d{1,2})\s*cuotas?\s+sin\s+inter[eé]s"
        for source in (label, text):
            if not source:
                continue
            cuotas = re.search(cuotas_re, source, re.I)
            if cuotas:
                top = cuotas.group(2)
                # "3-6-9-12 cuotas" en la descripción = hasta 12 cuotas.
                listed = re.search(rf"(?:\d{{1,2}}\s*-\s*)+{top}\s*cuotas?", text, re.I)
                return f"{'Hasta ' if listed or cuotas.group(1) else ''}{top} cuotas sin interés"
            percent = re.search(
                r"(\d{1,3})\s*%\s*(?:de\s+)?(descuento|reintegro|cashback|devoluci[oó]n)?",
                source, re.I,
            )
            if percent and int(percent.group(1)) > 0:
                kind = (percent.group(2) or "descuento").lower()
                kind = "devolución" if kind.startswith("devoluci") else kind
                return f"{percent.group(1)}% {kind}"
        return ""

    @staticmethod
    def _resolve_entity(icon: str, description: str, observation: str) -> tuple:
        icon_lower = icon.lower()
        for fragment, entity in _ICON_ENTITIES:
            if fragment in icon_lower:
                return entity
        text = f"{description} {observation}"
        for pattern, entity in _TEXT_ENTITIES:
            if re.search(pattern, text, re.I):
                return entity
        if re.search(r"tarjetas?\s+de\s+d[eé]bito", description, re.I):
            return (None, None, "Tarjetas de débito")
        return (None, None, "")

    @staticmethod
    def _card_type(description: str, discount: str) -> Optional[str]:
        types = []
        if re.search(r"cr[eé]dito", description, re.I):
            types.append("Crédito")
        if re.search(r"d[eé]bito", description, re.I):
            types.append("Débito")
        # Las cuotas sin interés sólo existen con tarjeta de crédito.
        if not types and "cuotas" in discount:
            types.append("Crédito")
        return ", ".join(types) or None

    @staticmethod
    def _payment_method(description: str, observation: str, wallet: Optional[str],
                        card_type: Optional[str]) -> Optional[str]:
        text = f"{description} {observation}"
        if re.search(r"ciudadan[ií]a\s+porte[ñn]a", text, re.I):
            return "Tarjeta Ciudadanía Porteña"
        if re.search(r"todos\s+los\s+medios\s+de\s+pago", text, re.I):
            if wallet == "Mercado Pago":
                return "Todos los medios de pago en la app Mercado Pago"
            return "Todos los medios de pago"
        parts: List[str] = []
        if wallet == "MODO" or re.search(r"\bmodo\b", description, re.I):
            parts.append("QR MODO")
        elif re.search(r"\bqr\b", text, re.I):
            parts.append(f"QR {wallet}" if wallet else "QR")
        brands = [name for pattern, name in _CARD_BRANDS if re.search(pattern, description, re.I)]
        if brands:
            parts.append(", ".join(brands))
        if not parts and card_type == "Débito":
            parts.append("Débito")
        return " - ".join(parts) or None

    @staticmethod
    def _valid_days(raw_promo: Dict) -> Optional[str]:
        names = []
        days = raw_promo.get("dias")
        if isinstance(days, list):
            for day in days:
                if isinstance(day, dict):
                    name = _DAY_ALIASES.get(CotoScraper._clean_value(day.get("descripcion")).lower())
                    if name and name not in names:
                        names.append(name)
        if not names:
            text = CotoScraper._clean_value(raw_promo.get("diasVigencia")).lower()
            names = [name for alias, name in _DAY_ALIASES.items() if re.search(rf"\b{alias}\b", text)]
            names = list(dict.fromkeys(names))
        if not names:
            return None
        if len(names) == 7:
            return "Todos los días"
        return ", ".join(sorted(names, key=_DAY_ORDER.index))

    @staticmethod
    def _validity(raw_promo: Dict, text: str) -> tuple:
        from_value = CotoScraper._iso_date(raw_promo.get("vigenciaDesde"))
        until_value = CotoScraper._iso_date(raw_promo.get("vigenciaHasta"))
        if from_value or until_value:
            return from_value, until_value
        # "Del 01/10 al 31/10/2026" (el año inicial suele omitirse).
        match = re.search(
            r"del\s+(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\s+al\s+(\d{1,2})/(\d{1,2})/(\d{2,4})",
            text, re.I,
        )
        if not match:
            return None, None
        d1, m1, y1, d2, m2, y2 = match.groups()
        y2 = int(y2) + (2000 if len(y2) == 2 else 0)
        y1 = int(y1) + (2000 if y1 and len(y1) == 2 else 0) if y1 else (y2 if int(m1) <= int(m2) else y2 - 1)
        try:
            return (date(y1, int(m1), int(d1)).isoformat(), date(y2, int(m2), int(d2)).isoformat())
        except ValueError:
            return None, None

    @staticmethod
    def _iso_date(value: Any) -> Optional[str]:
        text = CotoScraper._clean_value(value)
        if not text:
            return None
        match = re.match(r"^(\d{4})-(\d{2})-(\d{2})", text)
        if match:
            return "-".join(match.groups())
        match = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})", text)
        if match:
            d, m, y = match.groups()
            return f"{y}-{int(m):02d}-{int(d):02d}"
        if text.isdigit() and len(text) >= 12:  # epoch en ms
            from datetime import datetime, timedelta, timezone
            local = datetime.fromtimestamp(int(text) / 1000, tz=timezone(timedelta(hours=-3)))
            return local.date().isoformat()
        return None

    @staticmethod
    def _qualifier(description: str, observation: str) -> str:
        """Segmento o plan que distingue tarjetas con mismo banco y beneficio."""
        segment = re.match(r"(PLAN\s+SUELDO|SGTO\.?\s+[A-ZÁÉÍÓÚ]+)", description)
        if segment:
            value = segment.group(1).upper()
            if value.startswith("PLAN"):
                return "Plan Sueldo"
            name = re.sub(r"^SGTO\.?\s+", "", value).capitalize().replace("Unico", "Único")
            return f"Segmento {name}"
        plan = re.search(r"plan\s+(inicial|turbo|[ée]pico)", observation, re.I)
        if plan:
            return "Plan " + plan.group(1).capitalize().replace("Epico", "Épico")
        return ""

    @staticmethod
    def _deduplicate_multichannel_promotions(promotions: List[Dict]) -> List[Dict]:
        seen: Dict[tuple, Dict] = {}
        for promo in promotions:
            key = (
                promo.get("source_id") or "",
                (promo.get("bank") or "").lower(),
                (promo.get("discount") or "").lower(),
                (promo.get("store_types") or "").lower(),
                (promo.get("valid_days") or "").lower(),
            )
            existing = seen.get(key)
            if existing is None or len(promo.get("terms_raw") or "") > len(existing.get("terms_raw") or ""):
                seen[key] = promo
        return list(seen.values())

    @staticmethod
    def _ensure_unique_titles(promotions: List[Dict]) -> List[Dict]:
        # UNIQUE(supermarket_id, title, bank): dos tarjetas con el mismo texto
        # se distinguen por su id de origen en vez de pisarse.
        counts: Dict[tuple, int] = {}
        for promo in promotions:
            key = (promo["title"], promo.get("bank"))
            counts[key] = counts.get(key, 0) + 1
        for promo in promotions:
            if counts[(promo["title"], promo.get("bank"))] > 1:
                promo["title"] += f" #{promo['source_id'].replace('coto-', '')}"
        return promotions

    @staticmethod
    def _format_amount(raw: str) -> str:
        digits = re.sub(r"[.,]\d{2}$", "", raw.strip())
        digits = re.sub(r"\D", "", digits)
        return f"${int(digits):,}".replace(",", ".") if digits else ""

    @staticmethod
    def _extract_tope(text: str) -> Optional[str]:
        if not text:
            return None
        matches = list(re.finditer(
            r"tope\s*(?:de\s+)?(?:reintegro|descuento|devoluci[oó]n)?\s*(?:unificado\s*)?(?:de\s+)?:?\s*"
            r"\$\s*(\d[\d.,]*\d|\d)((?:(?!tope)[^.$]){0,40})",
            text, re.I,
        ))
        if matches:
            def describe(match) -> str:
                amount = CotoScraper._format_amount(match.group(1))
                tail = match.group(2).lower()
                if re.search(r"semana", tail):
                    return f"{amount} semanal"
                if re.search(r"\bmes\b|mensual", tail):
                    return f"{amount} mensual"
                if re.search(r"transacci[oó]n|compra", tail):
                    return f"{amount} por transacción"
                if re.search(r"\bd[ií]a\b|diario", tail):
                    return f"{amount} diario"
                return amount
            topes = list(dict.fromkeys(describe(m) for m in matches))
            if len(topes) > 1:
                # Comafi: cartera general $15.000 / Segmento Único $25.000.
                return f"{topes[0]} (hasta {topes[-1]} según segmento)"
            return topes[0]
        if re.search(r"sin\s+(?:tope|l[ií]mite)", text, re.I):
            return "Sin tope"
        return None

    @staticmethod
    def _extract_min_purchase(text: str) -> Optional[str]:
        match = re.search(
            r"(?:compras?|pagos?)\s+(?:a\s+partir\s+de|desde|m[ií]nim[ao]s?\s+de)\s*\$\s*(\d[\d.,]*\d|\d)",
            text, re.I,
        )
        return CotoScraper._format_amount(match.group(1)) if match else None


async def main():
    scraper = CotoScraper()
    promotions = await scraper.scrape()
    print(f"\n{'='*100}")
    print(f"📊 RESULTADOS: {len(promotions)} promociones")
    print(f"{'='*100}")
    for i, promo in enumerate(promotions, 1):
        print(f"{i:2d}. {promo['title']}")
        print(f"    💰 {promo['discount']} | 🏦 {promo.get('bank')} / {promo.get('wallet')} | "
              f"💳 {promo.get('card_type')} · {promo.get('payment_method')} | "
              f"📅 {promo.get('valid_days')} {promo.get('valid_from')}→{promo.get('valid_until')} | "
              f"🧢 {promo.get('tope')} | 🛒 {promo.get('min_purchase')}")


if __name__ == "__main__":
    asyncio.run(main())
