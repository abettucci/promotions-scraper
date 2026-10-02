"""Respuestas confiables a preguntas en lenguaje natural sobre promociones.

No usa un modelo generativo: interpreta la pregunta en filtros (comercio,
banco/billetera, día, rubro, método de pago, canal) y responde solo con la
evidencia que existe en la base scrapeada. Esto es importante para no afirmar
que un producto está incluido cuando los T&C no lo mencionan.
"""
from __future__ import annotations

import html
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

from supplement_prices import find_supplement_price


_STOP_WORDS = {
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del",
    "para", "con", "sin", "en", "y", "por", "a", "mi", "me", "que",
    "super", "supermercado", "producto", "cosa",
}

_PRODUCT_CATEGORIES = {
    "vino": ("vino", "vinos", "bebida", "bebidas", "bodega"),
    "cerveza": ("cerveza", "cervezas", "bebida", "bebidas"),
    "gaseosa": ("gaseosa", "gaseosas", "bebida", "bebidas"),
    "carne": ("carne", "carnes", "carniceria"),
    "pollo": ("pollo", "aves", "carnes"),
    "lacteo": ("lacteo", "lacteos", "leche", "queso", "yogur"),
    "nafta": ("nafta", "combustible", "combustibles", "infinia"),
    "combustible": ("nafta", "combustible", "combustibles", "diesel", "gasoil"),
}

_PRICE_INTENT_RE = re.compile(
    r"\b(?:mas barat[oa]s?|precio(?:s)?|cuanto cuesta|cuanto sale|comparar precio)\b",
)
_SUPPLEMENT_TERMS = (
    "proteina", "protein", "whey", "creatina", "aminoacido", "bcaa",
    "pre entreno", "preentreno", "suplemento", "star nutrition",
)


_WEEKDAYS = ("lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo")
_WEEKDAY_LABELS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")

# Formas coloquiales → texto que aparece en bank/wallet/payment_method/título.
_ENTITY_ALIASES = {
    "bna": "nacion", "banco nacion": "nacion", "nacion": "nacion",
    "provincia": "provincia", "bapro": "provincia", "cuenta dni": "cuenta dni",
    "mp": "mercado pago", "mercadopago": "mercado pago", "mercado pago": "mercado pago",
    "naranja": "naranja", "galicia": "galicia", "santander": "santander", "bbva": "bbva",
    "frances": "bbva", "macro": "macro", "ciudad": "ciudad", "buepp": "buepp",
    "icbc": "icbc", "supervielle": "supervielle", "patagonia": "patagonia",
    "comafi": "comafi", "credicoop": "credicoop", "columbia": "columbia",
    "hipotecario": "hipotecario", "brubank": "brubank", "uala": "uala",
    "personal pay": "personal pay", "modo": "modo", "prex": "prex",
    "cencopay": "cencopay", "jubilad": "jubilad", "anses": "anses",
    "club la nacion": "club la nacion", "la nacion": "club la nacion",
    "amex": "american express", "american express": "american express",
    "visa": "visa", "mastercard": "mastercard", "cabal": "cabal",
}
# Alias de comercio → nombre en la base.
_MERCHANT_ALIASES = {
    "dia": "Supermercados Día", "chango": "Más Online (ChangoMás)",
    "changomas": "Más Online (ChangoMás)", "masonline": "Más Online (ChangoMás)",
    "mas online": "Más Online (ChangoMás)", "masgo": "Más Online (ChangoMás)",
    "jumbo": "Jumbo (Cencosud)", "cencosud": "Jumbo (Cencosud)",
    "coto": "Coto Digital", "carrefour": "Carrefour", "ypf": "YPF",
    "shell": "Shell", "axion": "Axion", "puma": "Puma Energy",
}
_FUEL_WORDS = r"\b(nafta|naftas|combustible|combustibles|estacion(?:es)?(?: de servicio)?|cargar|gasoil|diesel|infinia|v-?power|surtidor)\b"
_SUPER_WORDS = r"\b(super|supers|supermercado|supermercados|mercado|almacen)\b"
_BEST_WORDS = r"\b(mejor(?:es)?|mas descuento|mayor descuento|maximo|conviene|mas me conviene|cual rinde|el mas alto)\b"


@dataclass
class PromoQuery:
    """Filtros que se entendieron de una pregunta."""
    merchant: Optional[str] = None
    entity: Optional[str] = None
    days: Optional[set] = None          # índices 0=lunes … 6=domingo
    day_label: str = ""
    target_date: Optional[date] = None  # sólo para "hoy" / "mañana"
    category: Optional[str] = None      # supermarket | fuel
    method: Optional[str] = None        # qr | nfc | debito | credito | cuotas
    channel: Optional[str] = None       # online | tiendas
    best: bool = False
    understood: list = field(default_factory=list)

    @property
    def has_filters(self) -> bool:
        return any((self.merchant, self.entity, self.days is not None, self.category, self.method, self.channel))


def _parse_days(normalized: str, today: date) -> tuple[Optional[set], str, Optional[date]]:
    if re.search(r"\bpasado manana\b", normalized):
        target = today + timedelta(days=2)
        return {target.weekday()}, f"pasado mañana ({_WEEKDAY_LABELS[target.weekday()]})", target
    if re.search(r"\bmanana\b", normalized):
        target = today + timedelta(days=1)
        return {target.weekday()}, f"mañana ({_WEEKDAY_LABELS[target.weekday()]})", target
    if re.search(r"\b(hoy|ahora|esta noche)\b", normalized):
        return {today.weekday()}, f"hoy ({_WEEKDAY_LABELS[today.weekday()]})", today
    if re.search(r"\bfin(?:de)? de semana\b|\bfinde\b", normalized):
        return {5, 6}, "el fin de semana", None
    named = {i for i, day in enumerate(_WEEKDAYS) if re.search(rf"\b{day}s?\b", normalized)}
    if named:
        return named, ", ".join(_WEEKDAY_LABELS[i] for i in sorted(named)), None
    return None, "", None


def _promo_days(promo: dict) -> set:
    """Días en que aplica la promo según valid_days ('' = todos)."""
    text = _norm(promo.get("valid_days"))
    if not text or "todos los dias" in text or "todos" == text:
        return set(range(7))
    days = {i for i, day in enumerate(_WEEKDAYS) if re.search(rf"\b{day}s?\b", text)}
    for start, end in re.findall(rf"\b({'|'.join(_WEEKDAYS)})s? a ({'|'.join(_WEEKDAYS)})s?\b", text):
        a, b = _WEEKDAYS.index(start), _WEEKDAYS.index(end)
        days.update(range(a, b + 1) if a <= b else list(range(a, 7)) + list(range(0, b + 1)))
    # "Día 10 de cada mes (Sábado)" y similares: si no hay día reconocible,
    # no se puede descartar por día.
    return days or set(range(7))


def parse_promo_query(question: str, promotions: list[dict], today: Optional[date] = None) -> PromoQuery:
    normalized = _norm(question)
    today = today or date.today()
    query = PromoQuery()
    query.merchant = _find_supermarket(question, promotions)
    if not query.merchant:
        for alias, name in sorted(_MERCHANT_ALIASES.items(), key=lambda kv: -len(kv[0])):
            if re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", normalized):
                query.merchant = name
                break
    for alias, needle in sorted(_ENTITY_ALIASES.items(), key=lambda kv: -len(kv[0])):
        # "La Nación" (club) no debe confundirse con Banco Nación.
        if needle == "nacion" and "la nacion" in normalized:
            continue
        if re.search(rf"(?<!\w){re.escape(alias)}\w*", normalized):
            query.entity = needle
            break
    query.days, query.day_label, query.target_date = _parse_days(normalized, today)
    if re.search(_FUEL_WORDS, normalized):
        query.category = "fuel"
    elif re.search(_SUPER_WORDS, normalized):
        query.category = "supermarket"
    if re.search(r"\bqr\b", normalized):
        query.method = "qr"
    elif re.search(r"\bnfc\b|sin contacto|contactless|apple pay|google pay", normalized):
        query.method = "nfc"
    elif re.search(r"\bdebito\b", normalized):
        query.method = "debito"
    elif re.search(r"\bcuotas?\b", normalized):
        query.method = "cuotas"
    elif re.search(r"\bcredito\b", normalized):
        query.method = "credito"
    if re.search(r"\b(online|web|por internet|envio|delivery|app del super)\b", normalized):
        query.channel = "online"
    elif re.search(r"\b(presencial|en tienda|en el local|sucursal|en la caja)\b", normalized):
        query.channel = "tiendas"
    query.best = bool(re.search(_BEST_WORDS, normalized))
    return query


def _matches_query(promo: dict, query: PromoQuery) -> bool:
    if query.merchant and promo.get("supermarket_name") != query.merchant:
        return False
    if query.category and _norm(promo.get("category") or "supermarket") != query.category:
        return False
    if query.entity:
        haystack = _norm(" ".join(str(promo.get(f) or "") for f in ("bank", "wallet", "payment_method", "title")))
        if query.entity not in haystack:
            return False
        # "nacion" está dentro de "Club La Nación": no es Banco Nación.
        if query.entity == "nacion" and "la nacion" in haystack and not re.search(r"banco nacion|\bbna\b", haystack):
            return False
    if query.days is not None and not (_promo_days(promo) & query.days):
        return False
    if query.target_date:
        iso = query.target_date.isoformat()
        if (promo.get("valid_from") or "") > iso or (promo.get("valid_until") or "9999") < iso:
            return False
    method_text = _norm(" ".join(str(promo.get(f) or "") for f in ("payment_method", "card_type", "discount", "title")))
    if query.method == "qr" and "qr" not in method_text:
        return False
    if query.method == "nfc" and not re.search(r"nfc|sin contacto|contactless", method_text):
        return False
    if query.method == "debito" and "debito" not in method_text:
        return False
    if query.method == "credito" and "credito" not in method_text:
        return False
    if query.method == "cuotas" and "cuota" not in method_text:
        return False
    stores = _norm(promo.get("store_types"))
    if query.channel == "online" and stores and "online" not in stores:
        return False
    if query.channel == "tiendas" and stores and not re.search(r"tienda|sucursal|presencial", stores):
        return False
    return True


def _benefit_rank(promo: dict) -> tuple:
    discount = str(promo.get("discount") or "")
    cuotas = re.search(r"(\d{1,2})\s*cuotas", discount, re.I)
    return (_discount_value(discount), int(cuotas.group(1)) if cuotas else 0, not promo.get("tope"))


def is_allowed_promo_question(question: object) -> bool:
    """Allowlist de preguntas que el asistente puede contestar.

    El asistente no es un chat general ni ejecuta acciones: solo consulta la
    información de promociones vigente. Este control también evita enviar
    texto arbitrario a futuros proveedores de IA.
    """
    raw = str(question or "")
    if not raw or len(raw) > 280 or any(ord(char) < 32 and char not in "\n\t" for char in raw):
        return False
    normalized = _norm(raw)
    exclusion = bool(re.search(r"\b(exclu|inclu|no aplica|aplica.*producto)\w*", normalized))
    recommendation = bool(re.search(
        r"\b(conviene|mejor(?:es)?|donde comprar|en que super|en cual super|recomenda|recomienda)\b",
        normalized,
    ))
    promo_data = bool(re.search(
        r"\b(promo|promocion|descuento|beneficio|reintegro|cuota|combustible|nafta|gasoil|diesel)\w*",
        normalized,
    ))
    price_comparison = bool(_PRICE_INTENT_RE.search(normalized))
    # "¿Qué hay hoy en Coto con Galicia?" no dice "promo" pero es una consulta
    # de promos: alcanza con nombrar un comercio, banco/billetera o rubro.
    query = parse_promo_query(raw, [])
    scoped = bool(query.merchant or query.entity or query.category)
    help_request = bool(re.search(r"\b(ayuda|que podes|que puedes|que sabes|como funciona|como te uso|hola)\b", normalized))
    return exclusion or recommendation or promo_data or price_comparison or scoped or help_request

# Términos que pueden justificar una exclusión por categoría. Son más
# estrechos que los usados para recomendar: "bodega" por sí solo no permite
# concluir nada sobre un vino concreto.
_EXCLUSION_CATEGORY_TERMS = {
    "vino": ("vino", "vinos"),
    "cerveza": ("cerveza", "cervezas"),
    "gaseosa": ("gaseosa", "gaseosas"),
    "carne": ("carne", "carnes"),
    "pollo": ("pollo", "aves"),
    "lacteo": ("lacteo", "lacteos", "leche", "queso", "yogur"),
    "nafta": ("nafta", "combustible", "combustibles", "infinia"),
    "combustible": ("nafta", "combustible", "combustibles", "diesel", "gasoil"),
}


def _norm(value: object) -> str:
    text = unicodedata.normalize("NFD", str(value or ""))
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", text.lower()).strip()


def _esc(value: object) -> str:
    return html.escape(str(value or ""), quote=False)


def _tokens(value: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9]+", _norm(value))
            if len(token) > 2 and token not in _STOP_WORDS]


def _contains_product(text: str, product: str) -> bool:
    """Busca frase o tokens significativos; evita que 'vino' por sí solo baste."""
    normalized = _norm(text)
    phrase = _norm(product)
    if phrase and phrase in normalized:
        return True
    meaningful = _tokens(product)
    # Si hay una marca/palabra específica, una coincidencia alcanza. Para una
    # consulta genérica (p.ej. "vino"), exigimos la coincidencia exacta.
    return len(meaningful) > 1 and any(token in normalized for token in meaningful)


def _product_parts(product: str) -> tuple[list[str], list[str]]:
    """Separa la categoría de los datos que identifican una marca/bodega.

    ``vino Alaris`` no puede considerarse excluido solo porque un T&C diga
    "vinos en tetrabrik". En cambio, la consulta genérica ``vino`` sí puede
    responderse con una exclusión que nombre a los vinos.
    """
    tokens = _tokens(product)
    category_tokens: set[str] = set()
    for trigger, words in _EXCLUSION_CATEGORY_TERMS.items():
        if trigger in tokens or trigger in _norm(product):
            category_tokens.add(trigger)
            category_tokens.update(words)
    specific_tokens = [token for token in tokens if token not in category_tokens]
    return list(category_tokens), specific_tokens


def _excerpt_for_match(
    text: object, anchors: list[str], limit: int = 220, position: Optional[int] = None,
) -> str:
    """Devuelve el fragmento legal relevante, no el T&C completo."""
    raw = re.sub(r"\s+", " ", str(text or "")).strip()
    normalized = _norm(raw)
    positions = [normalized.find(_norm(anchor)) for anchor in anchors if _norm(anchor)]
    positions = [found for found in positions if found >= 0]
    if not positions:
        return raw[:limit].rstrip() + ("…" if len(raw) > limit else "")

    # Busca el inicio de la cláusula de exclusión anterior a la coincidencia.
    position = position if position is not None else min(positions)
    starts = [match.start() for match in re.finditer(
        r"\b(?:no incluye|no aplica|no valido|no válido|excluye|excluidos?|excepto|quedan excluidos?)\b",
        normalized,
    ) if match.start() <= position]
    start = starts[-1] if starts else max(0, position - 70)
    # En T&C extensos sin puntos, la cláusula puede ser mucho más larga que
    # el extracto. Conservamos contexto, pero sin cortar antes del término.
    if position - start > limit - 70:
        start = max(0, position - 70)
    end = normalized.find(".", position)
    if end < 0:
        end = min(len(raw), start + limit)
    else:
        end += 1
    excerpt = raw[start:end].strip()
    return excerpt[:limit].rstrip() + ("…" if len(excerpt) > limit else "")


def _direct_category_term(text: str, categories: list[str]) -> Optional[tuple[str, int]]:
    """Devuelve una categoría solo si está en una cláusula de exclusión directa."""
    normalized = _norm(text)
    for category in categories:
        for match in re.finditer(rf"(?<!\w){re.escape(category)}(?:s)?(?!\w)", normalized):
            before = normalized[max(0, match.start() - 90):match.start()]
            # Ej.: "NO INCLUYE VINOS" o ", NI VINOS EN TETRABRIK".
            if re.search(
                r"(?:no incluye|no aplica|no valido|no válido|excluye|excluidos?|excepto)\b[^.]{0,55}$|"
                r"(?:^|[,;])\s*ni\s+$",
                before,
            ):
                return category, match.start()
    return None


def _exclusion_match(exclusions: object, product: str) -> tuple[str, str]:
    """Clasifica la evidencia como exacta, de categoría o relacionada.

    Una coincidencia relacionada se informa como advertencia, nunca como una
    confirmación de exclusión del producto específico.
    """
    text = str(exclusions or "")
    normalized = _norm(text)
    categories, specific = _product_parts(product)
    if not normalized:
        return "", ""

    # Para marcas y bodegas exigimos que todos sus términos aparezcan en el
    # texto de exclusiones. Evita falsos positivos por el término "vino".
    if specific and all(re.search(rf"(?<!\w){re.escape(token)}(?!\w)", normalized) for token in specific):
        return "exact", _excerpt_for_match(text, specific)

    direct_category_match = _direct_category_term(text, categories)
    if not direct_category_match:
        return "", ""
    direct_category, position = direct_category_match
    excerpt = _excerpt_for_match(text, [direct_category], position=position)
    # Solo una pregunta genérica ("vino") se puede confirmar por categoría.
    # Para una marca concreta la categoría es una pista, no una respuesta.
    return ("related" if specific else "category"), excerpt


def _promo_text(promo: dict) -> str:
    return " ".join(str(promo.get(field) or "") for field in (
        "title", "terms_raw", "exclusions", "requirements", "store_types",
    ))


def _find_supermarket(question: str, promotions: list[dict]) -> Optional[str]:
    """Resuelve el comercio por la coincidencia más larga de su nombre/alias."""
    normalized_question = _norm(question)
    names = {str(p.get("supermarket_name") or "").strip() for p in promotions}
    best: tuple[int, str] | None = None
    for name in names:
        normalized_name = _norm(name)
        aliases = [normalized_name]
        # "Jumbo (Cencosud)" puede llegar como "Jumbo" o "Cencosud".
        aliases.extend(part.strip() for part in re.split(r"[()/-]", normalized_name) if len(part.strip()) >= 3)
        # En la conversación normalmente se usa la marca corta: "Coto" en
        # vez de "Coto Digital", o "Más Online" en vez del nombre completo.
        name_words = _tokens(normalized_name)
        if name_words:
            aliases.append(name_words[0])
        for alias in aliases:
            if alias and re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", normalized_question):
                candidate = (len(alias), name)
                if best is None or candidate[0] > best[0]:
                    best = candidate
    return best[1] if best else None


def _extract_exclusion_product(question: str) -> Optional[str]:
    patterns = (
        r"(?:^|\b)(.+?)\s+(?:esta|esta\s+o\s+no|queda|quedan|viene|vienen|aplica|aplican)\s+excluid[oa]s?\b",
        r"(?:exclu(?:ye|ido|ida|idos|idas)|no\s+incluye)\s+(?:el|la|los|las)?\s*(.+?)(?:\s+de\s+(?:la\s+)?promo|\?|$)",
    )
    for pattern in patterns:
        match = re.search(pattern, _norm(question))
        if match:
            product = re.sub(r"^(?:el|la|los|las)\s+", "", match.group(1)).strip(" ?!.,¿")
            # Quitar el preámbulo habitual de la segunda forma de pregunta.
            product = re.sub(r"^(?:el|la|los|las)\s+", "", product)
            if product and len(product) <= 80:
                return product
    return None


def _extract_recommendation_product(question: str) -> Optional[str]:
    normalized = _norm(question)
    match = re.search(r"\b(?:comprar|compra|conseguir|llevar)\s+(.+?)(?:\?|$)", normalized)
    if not match:
        return None
    product = re.sub(r"\b(?:hoy|ahora|en oferta)\b.*$", "", match.group(1)).strip(" ?!.,")
    return product if product and len(product) <= 80 else None


def _is_price_comparison_question(question: str) -> bool:
    return bool(_PRICE_INTENT_RE.search(_norm(question)))


def _extract_price_product(question: str) -> Optional[str]:
    normalized = _norm(question)
    patterns = (
        r"\b(?:en que|en cual|donde)\s+(?:lugar|tienda|comercio)?\s*(?:esta|sale)?\s*(?:mas|menos)\s+(?:barat[oa]|car[oa])\s+(?:el|la|los|las)?\s*(.+?)(?:\?|$)",
        r"\b(?:precio|cuanto cuesta|cuanto sale)\s+(?:de|del|de la)?\s*(.+?)(?:\?|$)",
    )
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if not match:
            continue
        product = re.sub(r"^(?:el|la|los|las)\s+", "", match.group(1)).strip(" ?!.,")
        if product and len(product) <= 120:
            return product
    return None


def _format_ars(value: int) -> str:
    return f"${value:,}".replace(",", ".")


def _answer_price_comparison(question: str) -> str:
    product = _extract_price_product(question)
    if not product:
        return "¿Qué suplemento querés comparar? Ej.: <i>¿En qué lugar está más barata la proteína Star Nutrition 2 lb?</i>"
    normalized = _norm(product)
    if not any(term in normalized for term in _SUPPLEMENT_TERMS):
        return (
            "Por ahora puedo comparar precios publicados de <b>suplementos</b>. "
            "Para supermercados y combustibles comparo promociones y sus condiciones, no precios ni stock de productos."
        )
    result = find_supplement_price(product)
    if not result:
        return (
            f"No encontré un precio publicado para <b>{_esc(product)}</b> en este momento. "
            "Probá con marca, presentación y peso; verificá siempre el precio final en la tienda."
        )
    lines = [
        f"💸 <b>Precio más bajo publicado para {_esc(result.product_name)}</b>",
        f"<b>{_esc(result.store_name)}</b> — {_format_ars(result.price or 0)}",
    ]
    if result.transfer_price and result.transfer_price != result.price:
        lines.append(f"Con transferencia: {_format_ars(result.transfer_price)}")
    if result.offer_count:
        lines.append(f"{result.offer_count} tiendas publicadas en la comparación.")
    lines.append(f'<a href="{_esc(result.source_url)}">Ver comparación y precio actualizado</a>')
    lines.append("<i>Es un precio publicado: confirmá stock, sabor/presentación, envío y precio final antes de pagar.</i>")
    return "\n".join(lines)


def _discount_value(value: object) -> float:
    match = re.search(r"(\d+(?:[,.]\d+)?)\s*%", str(value or ""))
    return float(match.group(1).replace(",", ".")) if match else 0.0


def _matches_payment_method(promo: dict, methods: list[dict]) -> bool:
    haystack = _norm(" ".join(str(promo.get(field) or "") for field in (
        "bank", "wallet", "payment_method", "title",
    )))
    return any(_norm(method.get("name")) in haystack for method in methods if method.get("name"))


def _scope_may_cover_product(promo: dict, product: str) -> bool:
    """Evalúa alcance conocido. Una promo genérica queda como potencialmente válida."""
    combined = _norm(_promo_text(promo))
    if _contains_product(combined, product):
        return True
    product_tokens = set(_tokens(product))
    category_words: set[str] = set()
    for trigger, words in _PRODUCT_CATEGORIES.items():
        if trigger in product_tokens or trigger in _norm(product):
            category_words.update(words)
    if category_words:
        # Si la promo declara una categoría compatible, podemos recomendarla.
        if any(word in combined for word in category_words):
            return True
        # Si declara que es para otra categoría concreta, no la presentamos.
        scoped_words = {word for words in _PRODUCT_CATEGORIES.values() for word in words}
        if any(word in combined for word in scoped_words):
            return False
    return True


def _promo_line(promo: dict) -> str:
    entity = promo.get("bank") or promo.get("wallet") or promo.get("payment_method") or "medio de pago informado"
    if promo.get("bank") and promo.get("wallet") and _norm(promo["wallet"]) not in _norm(promo["bank"]):
        entity = f"{promo['bank']} vía {promo['wallet']}"
    details = [f"<b>{_esc(promo.get('discount') or 'Beneficio')}</b> con {_esc(entity)}"]
    if promo.get("valid_days"):
        details.append(_esc(promo["valid_days"]))
    if promo.get("tope"):
        tope = str(promo["tope"])
        details.append("sin tope" if _norm(tope) == "sin tope" else f"tope {_esc(tope)}")
    if promo.get("min_purchase"):
        details.append(f"mín. {_esc(promo['min_purchase'])}")
    stores = _norm(promo.get("store_types"))
    if stores == "online":
        details.append("solo online")
    elif stores and "online" not in stores:
        details.append("solo tiendas")
    valid_from, valid_until = promo.get("valid_from") or "", promo.get("valid_until") or ""
    if valid_from and valid_from == valid_until:
        details.append(f"solo el {_esc(valid_from)}")
    else:
        if valid_from > date.today().isoformat():
            # Promos próximas: el asistente las muestra para planificar la compra.
            details.append(f"desde {_esc(valid_from)}")
        if valid_until:
            details.append(f"hasta {_esc(valid_until)}")
    return " · ".join(details)


def _answer_exclusion(question: str, promotions: list[dict]) -> str:
    product = _extract_exclusion_product(question)
    supermarket = _find_supermarket(question, promotions)
    if not product:
        return "¿Qué producto querés verificar? Ej.: <i>¿El vino Alaris está excluido en Coto hoy?</i>"
    if not supermarket:
        return (f"Puedo revisar si <b>{_esc(product)}</b> figura excluido, pero necesito el supermercado. "
                "Ej.: <i>¿Está excluido en Carrefour hoy?</i>")

    candidates = [p for p in promotions if p.get("supermarket_name") == supermarket]
    if not candidates:
        return f"No encontré promociones vigentes hoy para <b>{_esc(supermarket)}</b>."

    matches = [
        (promo, *_exclusion_match(promo.get("exclusions"), product))
        for promo in candidates
    ]
    exact = [(promo, excerpt) for promo, kind, excerpt in matches if kind in {"exact", "category"}]
    related = [(promo, excerpt) for promo, kind, excerpt in matches if kind == "related"]
    if exact:
        lines = [f"⛔ <b>Sí: {_esc(product)}</b> figura excluido en { _esc(supermarket) } hoy."]
        for promo, evidence in exact[:2]:
            lines.append(f"• {_promo_line(promo)}")
            lines.append(f"  <i>Fragmento: {_esc(evidence)}</i>")
        return "\n".join(lines)

    if related:
        lines = [
            f"⚠️ <b>{_esc(product)}</b> no figura mencionado en las exclusiones de { _esc(supermarket) }. "
            "Sí hay una restricción para una categoría relacionada, pero no alcanza para confirmar esa marca o bodega.",
        ]
        for promo, evidence in related[:1]:
            lines.append(f"• {_promo_line(promo)}")
            lines.append(f"  <i>Fragmento: {_esc(evidence)}</i>")
        return "\n".join(lines)

    mentioned = [p for p in candidates if _contains_product(_promo_text(p), product)]
    if mentioned:
        lines = [f"✅ No encontré a <b>{_esc(product)}</b> en las exclusiones de { _esc(supermarket) } hoy.",
                 "Aparece mencionado en estas promos:"]
        lines.extend(f"• {_promo_line(p)}" for p in mentioned[:3])
        return "\n".join(lines)

    return (
        f"🔎 No encontré una mención explícita a <b>{_esc(product)}</b> en los T&C scrapeados de "
        f"<b>{_esc(supermarket)}</b> para hoy. Eso no confirma que esté incluido: revisá el cartel o los T&C finales antes de pagar."
    )


def _answer_recommendation(question: str, promotions: list[dict], methods: list[dict]) -> str:
    product = _extract_recommendation_product(question)
    if not product:
        return "¿Qué querés comprar? Ej.: <i>¿En qué súper me conviene comprar vino hoy?</i>"

    usable = [p for p in promotions if not _contains_product(str(p.get("exclusions") or ""), product)
              and _scope_may_cover_product(p, product)]
    personalized = bool(methods)
    if personalized:
        usable = [p for p in usable if _matches_payment_method(p, methods)]
    if not usable:
        suffix = " con tus medios de pago" if personalized else ""
        return f"No encontré una promo aplicable a <b>{_esc(product)}</b> hoy{suffix}."

    by_super: dict[str, list[dict]] = defaultdict(list)
    for promo in usable:
        by_super[str(promo.get("supermarket_name") or "Sin comercio")].append(promo)
    best = []
    for name, promos in by_super.items():
        promo = max(promos, key=lambda p: (_discount_value(p.get("discount")), bool(p.get("tope"))))
        best.append((name, promo))
    best.sort(key=lambda item: _discount_value(item[1].get("discount")), reverse=True)

    intro = ("usando tus medios de pago vinculados" if personalized
             else "por porcentaje de descuento (sin conocer tus tarjetas)")
    lines = [f"🛒 <b>Para comprar {_esc(product)} hoy</b>, estas son las mejores opciones {intro}:"]
    for index, (name, promo) in enumerate(best[:3], 1):
        lines.append(f"{index}. <b>{_esc(name)}</b> — {_promo_line(promo)}")
    lines.append("\n<i>Comparo el beneficio publicado, no el precio del producto ni su stock. Si el T&C no nombra el producto, confirmalo antes de pagar.</i>")
    if not personalized:
        lines.append("\nTip: vinculá tus medios de pago en la web y la recomendación será personalizada.")
    return "\n".join(lines)


_CATEGORY_LABELS = {"fuel": "combustible", "supermarket": "supermercados"}
_ENTITY_LABELS = {
    "nacion": "Banco Nación", "provincia": "Banco Provincia", "cuenta dni": "Cuenta DNI",
    "mercado pago": "Mercado Pago", "naranja": "Naranja X", "galicia": "Banco Galicia",
    "bbva": "BBVA", "macro": "Banco Macro", "ciudad": "Banco Ciudad", "icbc": "ICBC",
    "modo": "MODO", "jubilad": "jubilados", "anses": "ANSES", "uala": "Ualá",
    "club la nacion": "Club La Nación", "personal pay": "Personal Pay",
}
_METHOD_LABELS = {"qr": "con QR", "nfc": "con NFC", "debito": "con débito", "credito": "con crédito", "cuotas": "en cuotas"}


def _describe_query(query: PromoQuery) -> str:
    parts = []
    if query.merchant:
        parts.append(query.merchant)
    elif query.category:
        parts.append(_CATEGORY_LABELS[query.category])
    if query.entity:
        parts.append(f"con {_ENTITY_LABELS.get(query.entity, query.entity.title())}")
    if query.method:
        parts.append(_METHOD_LABELS[query.method])
    if query.channel:
        parts.append("online" if query.channel == "online" else "en tiendas")
    if query.day_label:
        parts.append(query.day_label)
    return " · ".join(parts) or "supermercados y combustibles"


def _answer_search(query: PromoQuery, promotions: list[dict], methods: list[dict]) -> str:
    """Busca con todos los filtros entendidos y explica qué se buscó."""
    candidates = [p for p in promotions if _matches_query(p, query)]
    personalized = bool(methods) and not query.entity
    if personalized:
        mine = [p for p in candidates if _matches_payment_method(p, methods)]
        if mine:
            candidates = mine
        else:
            personalized = False
    scope = _describe_query(query)
    if not candidates:
        # Explicar qué filtro dejó la búsqueda vacía ayuda a reformular.
        hint = ""
        if query.days is not None:
            relaxed = PromoQuery(**{**query.__dict__, "days": None, "day_label": "", "target_date": None})
            other_days = [p for p in promotions if _matches_query(p, relaxed)]
            if other_days:
                found = sorted({d for p in other_days for d in _promo_days(p)})
                hint = ("\nSí hay otros días: " + ", ".join(_WEEKDAY_LABELS[d] for d in found) + ".")
        return f"No encontré promos vigentes para <b>{_esc(scope)}</b>.{hint}"

    candidates.sort(key=_benefit_rank, reverse=True)
    limit = 3 if query.best else 8
    title = "🏆 <b>Mejores promos" if query.best else "📋 <b>Promos vigentes"
    lines = [f"{title} — {_esc(scope)}</b>" + (" (con tus medios de pago)" if personalized else "")]
    for promo in candidates[:limit]:
        prefix = "• " if query.merchant else f"<b>{_esc(promo.get('supermarket_name'))}</b>: "
        lines.append(f"{prefix}{_promo_line(promo)}")
    if len(candidates) > limit:
        lines.append(f"\n<i>Mostrando {limit} de {len(candidates)}. Sumá un banco, día o comercio para afinar.</i>")
    lines.append("<i>Ordenado por beneficio publicado; revisá topes y condiciones antes de pagar.</i>")
    return "\n".join(lines)


_HELP = (
    "Puedo buscar promos vigentes de supermercados y combustible, y precios de suplementos. Probá:\n\n"
    "• <i>¿Qué promos hay hoy en Coto?</i>\n"
    "• <i>¿Cuál es el mejor descuento en nafta el sábado?</i>\n"
    "• <i>Promos con Galicia en Shell</i>\n"
    "• <i>¿Qué hay con Cuenta DNI esta semana?</i>\n"
    "• <i>Descuentos con QR de Mercado Pago en Día</i>\n"
    "• <i>¿En qué súper me conviene comprar carne hoy?</i>\n"
    "• <i>¿El vino Alaris está excluido en Coto?</i>\n"
    "• <i>¿Dónde está más barata la proteína Star Nutrition 2 lb?</i>\n\n"
    "También podés usar /ayuda para ver los comandos."
)


def answer_promo_question(
    question: str, promotions: list[dict], methods: Optional[list[dict]] = None,
    today: Optional[date] = None,
) -> Optional[str]:
    """Devuelve una respuesta HTML o ``None`` cuando el mensaje no parece consulta.

    ``promotions`` debe traer todas las promos vigentes (no sólo las de hoy):
    el día lo filtra esta función según lo que pida la pregunta.
    """
    normalized = _norm(question)
    if not normalized:
        return None
    exclusion_intent = bool(re.search(r"\b(exclu|inclu|no aplica|aplica.*producto)\w*", normalized))
    recommendation_intent = bool(re.search(
        r"\b(conviene|mejor(?:es)?|donde comprar|en que super|en cual super|recomenda|recomienda)\b",
        normalized,
    ))
    if _is_price_comparison_question(question):
        return _answer_price_comparison(question)
    query = parse_promo_query(question, promotions, today)
    if exclusion_intent:
        return _answer_exclusion(question, promotions)
    product = _extract_recommendation_product(question)
    if recommendation_intent and product and not _is_only_filters(product, query):
        # El producto lo evalúa _answer_recommendation; el resto de lo que se
        # entendió (súper vs nafta, comercio, banco, día) filtra antes.
        scoped = [p for p in promotions if _matches_query(p, query)]
        return _answer_recommendation(question, scoped, methods or [])
    data_intent = bool(re.search(
        r"\b(promo|promocion|descuento|beneficio|reintegro|cuota|ofert|tope|minimo|ahorr|hay)\w*",
        normalized,
    ))
    if query.has_filters or query.best or data_intent:
        return _answer_search(query, promotions, methods or [])
    if "?" in question or "¿" in question or re.search(r"\b(ayuda|que podes|que puedes|hola)\b", normalized):
        return _HELP
    return None


def _is_only_filters(product: str, query: PromoQuery) -> bool:
    """'comprar nafta' o 'comprar en Coto' no nombran un producto: es una búsqueda."""
    leftover = _norm(product)
    leftover = re.sub(_FUEL_WORDS + "|" + _SUPER_WORDS, " ", leftover)
    for alias in list(_MERCHANT_ALIASES) + list(_ENTITY_ALIASES):
        leftover = re.sub(rf"(?<!\w){re.escape(alias)}\w*", " ", leftover)
    leftover = re.sub(rf"\b(en|con|el|la|los|las|de|hoy|manana|{'|'.join(_WEEKDAYS)})s?\b", " ", leftover)
    return not leftover.strip()
