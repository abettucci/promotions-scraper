"""Respuestas confiables a preguntas en lenguaje natural sobre promociones.

No usa un modelo generativo: interpreta dos consultas frecuentes y responde solo
con la evidencia que existe en la base scrapeada. Esto es importante para no
afirmar que un producto está incluido cuando los T&C no lo mencionan.
"""
from __future__ import annotations

import html
import re
import unicodedata
from collections import defaultdict
from typing import Optional


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
    return exclusion or recommendation or promo_data

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
    details = [f"<b>{_esc(promo.get('discount') or 'Beneficio')}</b> con {_esc(entity)}"]
    if promo.get("tope"):
        details.append(f"tope {_esc(promo['tope'])}")
    if promo.get("valid_days"):
        details.append(_esc(promo["valid_days"]))
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


def _answer_data_question(question: str, promotions: list[dict]) -> str:
    """Lista información scrapeada para preguntas como "¿qué hay en Shell?"."""
    supermarket = _find_supermarket(question, promotions)
    normalized = _norm(question)
    candidates = list(promotions)
    if supermarket:
        candidates = [p for p in candidates if p.get("supermarket_name") == supermarket]
    elif any(word in normalized for word in ("combustible", "nafta", "gasoil", "diesel")):
        candidates = [p for p in candidates if _norm(p.get("category")) == "fuel"]

    # Reconoce el banco/billetera si coincide con alguno de los registros
    # actuales. Así "¿qué hay con Galicia en Shell?" no requiere un comando.
    entities = {
        str(p.get(field) or "").strip()
        for p in candidates for field in ("bank", "wallet", "payment_method")
        if str(p.get(field) or "").strip()
    }
    entity = next((name for name in sorted(entities, key=len, reverse=True)
                   if _norm(name) in normalized), None)
    if entity:
        entity_norm = _norm(entity)
        candidates = [p for p in candidates if entity_norm in _norm(" ".join(
            str(p.get(field) or "") for field in ("bank", "wallet", "payment_method", "title")
        ))]

    if not candidates:
        scope = f" para <b>{_esc(supermarket)}</b>" if supermarket else ""
        return f"No encontré promociones vigentes hoy{scope}."

    scope = supermarket or ("combustibles" if candidates and all(_norm(p.get("category")) == "fuel" for p in candidates)
                            else "supermercados y combustibles")
    if entity:
        scope += f" con {entity}"
    lines = [f"📋 <b>Promos vigentes hoy — {_esc(scope)}</b>"]
    for promo in candidates[:6]:
        name = promo.get("supermarket_name")
        prefix = f"<b>{_esc(name)}</b>: " if not supermarket else "• "
        lines.append(f"{prefix}{_promo_line(promo)}")
    if len(candidates) > 6:
        lines.append(f"\n<i>Mostrando 6 de {len(candidates)} promociones.</i>")
    return "\n".join(lines)


def answer_promo_question(question: str, promotions: list[dict], methods: Optional[list[dict]] = None) -> Optional[str]:
    """Devuelve una respuesta HTML o ``None`` cuando el mensaje no parece consulta."""
    normalized = _norm(question)
    if not normalized:
        return None
    exclusion_intent = bool(re.search(r"\b(exclu|inclu|no aplica|aplica.*producto)\w*", normalized))
    recommendation_intent = bool(re.search(
        r"\b(conviene|mejor(?:es)?|donde comprar|en que super|en cual super|recomenda|recomienda)\b",
        normalized,
    ))
    if exclusion_intent:
        return _answer_exclusion(question, promotions)
    if recommendation_intent:
        return _answer_recommendation(question, promotions, methods or [])
    data_intent = bool(re.search(
        r"\b(promo|promocion|descuento|beneficio|reintegro|cuota|combustible|nafta|gasoil|diesel)\w*",
        normalized,
    ))
    if data_intent:
        return _answer_data_question(question, promotions)
    if "?" in question or "¿" in question:
        return (
            "Puedo responder preguntas sobre promos vigentes y sus T&C.\n\n"
            "• <i>¿El vino Alaris está excluido en Coto hoy?</i>\n"
            "• <i>¿En qué súper me conviene comprar vino hoy?</i>\n\n"
            "También podés usar /ayuda para ver los comandos."
        )
    return None
