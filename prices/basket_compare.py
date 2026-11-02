"""Canastas comparables: un ticket, una promoción y un único tope por comercio.

No usa IA, no pronostica precios ni presupone acumulación, stock presencial o
saldo restante del tope. Los escenarios son estimaciones sobre precios online.
"""
from __future__ import annotations

import math
import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from payment_preferences import (_entity_matches, _norm as fold, promotion_allows_card_mode, promotion_allows_tier)
from promo_questions import _promo_days
from terms_parser import TermsParser
from .matching import norm
from .registry import STORES
from .watchlist_quotes import positive_price

CENT = Decimal("0.01")
DAYS = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")
_STOP = {"los", "las", "para", "con", "sin", "del", "por", "una", "uno", "toda", "todo", "tipo", "peso"}


def cash(value):
    return float(Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP))


def amount(value):
    """None significa desconocido. No convierte un tope desconocido en ilimitado."""
    if positive_price(value):
        return Decimal(str(value))
    text = str(value or "").strip()
    if not text or len(text) > 512:
        return None
    matches = re.findall(r"\$\s*([0-9][0-9.,]*)(?:\s*(mil|millones|millon|k)\b)?", fold(text))
    if not matches and re.fullmatch(r"\d+(?:\.\d{3})*(?:,\d{1,2})?", text):
        matches = [(text, "")]
    values = []
    for number, suffix in matches:
        if not re.fullmatch(r"\d+(?:\.\d{3})*(?:,\d{1,2})?", number):
            return None
        try:
            result = Decimal(number.replace(".", "").replace(",", "."))
            result *= {"mil": 1000, "k": 1000, "millon": 1_000_000, "millones": 1_000_000}.get(suffix, 1)
            if result.is_finite() and result > 0:
                values.append(result)
        except InvalidOperation:
            return None
    return min(values) if values else None


def words(value):
    return {w[:-1] if w.endswith("s") else w for w in re.findall(r"[a-z]{3,}", norm(value)) if w not in _STOP}


def text(value):
    if isinstance(value, list):
        return " | ".join(str(v) for v in value)
    return str(value or "")


def profile_allows(promo, methods):
    entities = list(dict.fromkeys(str(promo.get(f) or "").strip() for f in ("bank", "wallet") if promo.get(f)))
    if not entities:
        return False
    matched = []
    for entity in entities:
        candidates = [m for m in methods if _entity_matches({"bank": entity}, m)]
        if "la nacion" in norm(entity):
            candidates = [m for m in candidates if "banco nacion" not in norm(m.get("name"))]
        elif norm(entity) in {"nacion", "banco nacion"}:
            candidates = [m for m in candidates if "la nacion" not in norm(m.get("name"))]
        if not candidates:
            return False  # Tener MODO no prueba tener la tarjeta del banco de la promo.
        candidates = [m for m in candidates if promotion_allows_card_mode(dict(promo, terms_raw=""), m)
                      and promotion_allows_tier(promo, m)]
        if not candidates:
            return False
        matched.extend(candidates)
    eligibility = norm(text(promo.get("title"))+" "+text(promo.get("requirements")))
    declarations = " ".join(norm(m.get("name")) + " " + norm(" ".join(m.get("tiers") or [])) for m in matched)
    # Segmentos que el catálogo de perfil todavía no permite verificar no se
    # presuponen disponibles; tampoco las ofertas personales/por invitación.
    if re.search(r"clientes seleccionados|por invitacion|oferta personal|usuarios seleccionados", eligibility):
        return False
    for segment in re.findall(r"\bplan (ultra|plus|epico|turbo|inicial|sueldo)\b", eligibility):
        if segment not in declarations.replace("_", " "):
            return False
    if re.search(r"jubilad|\banses\b|\bpami\b", eligibility):
        if not any(re.search(r"jubilad|anses|pami", norm(m.get("name"))) for m in methods):
            return False
    if re.search(r"\b(socios|suscriptos|adheridos)\b", eligibility):
        if not any(m.get("type") == "club" or m.get("tiers") for m in matched):
            return False
    return True


def prepare(promo, methods, today):
    discount = str(promo.get("discount") or "")
    if re.search(r"\b(cuotas?|tna|cft|tea|interes|recargo)\b", norm(discount)):
        return None
    match = re.match(r"^\s*(\d+(?:[.,]\d+)?)\s*%", discount)
    if not match or len(re.findall(r"\d+(?:[.,]\d+)?\s*%", discount)) != 1:
        return None
    rate = Decimal(match[1].replace(",", "."))/100
    if not 0 < rate <= 1 or not profile_allows(promo, methods):
        return None
    channel = norm(promo.get("store_types"))
    # Precios online: no aplicar promociones sólo presenciales/NFC ni asumir canal.
    payment_text = norm(" ".join(text(promo.get(k)) for k in ("title", "payment_method", "requirements")))
    if "online" not in channel or re.search(r"\bnfc\b|sin contacto|contactless", payment_text):
        return None
    cap_text = norm(promo.get("tope"))
    if not cap_text or re.search(r"no informado|sin tope informado|a confirmar|desconocido", cap_text):
        return None
    cap = Decimal("Infinity") if "sin tope" in cap_text else amount(promo.get("tope"))
    if cap is None:
        return None
    minimum_raw = str(promo.get("min_purchase") or "").strip()
    if not minimum_raw:
        minimum_match = re.search(r"(?:compra minima|monto minimo|minimo de compra|minimo de)[^$]{0,35}(\$\s*[0-9.,]+(?:\s*mil\b)?)",
                                  fold(text(promo.get("requirements"))+" "+text(promo.get("terms_raw"))))
        minimum_raw = minimum_match[1] if minimum_match else ""
    if re.search(r"no informado|sin minimo informado|a confirmar|desconocido", norm(minimum_raw)):
        return None
    minimum = amount(minimum_raw) if minimum_raw and "sin minimo" not in norm(minimum_raw) else Decimal(0)
    if minimum is None:
        return None
    day_text = norm(promo.get("valid_days"))
    named_days = bool(re.search(r"lunes|martes|miercoles|jueves|viernes|sabado|domingo|todos|diario", day_text))
    if not named_days and not (promo.get("valid_from") and promo.get("valid_from") == promo.get("valid_until")):
        return None
    try:
        start = date.fromisoformat(str(promo.get("valid_from") or today.isoformat()))
        end = date.fromisoformat(str(promo.get("valid_until") or today.isoformat()))
    except ValueError:
        return None
    raw = text(promo.get("terms_raw"))[:20000]
    source_exclusions = promo.get("exclusions") or []
    clauses = list(source_exclusions) if isinstance(source_exclusions, list) else str(source_exclusions).split("|")
    parser = TermsParser()
    if raw:
        clauses.extend(parser.extract_exclusions_improved(raw.upper()))
        clauses.append(parser.extract_included_products_restriction(raw.upper()))
    excluded_words, included_scopes = set(), []
    for clause in clauses:
        normalized = fold(clause)
        included = re.search(r"productos incluidos:\s*(.+)", normalized)
        if included:
            parts = re.split(r"\b(?:no incluye|excluye|excluidos|no acumulable)\b", included[1], maxsplit=1)
            included_scopes.append(words(parts[0]))
            if len(parts) > 1:
                excluded_words.update(words(parts[1]))
            prefix = re.split(r"el descuento aplica unicamente|productos incluidos:", normalized)[0]
            excluded_words.update(words(prefix))
        else:
            excluded_words.update(words(normalized))
    return {"promo": promo, "rate": rate, "cap": cap, "minimum": minimum,
            "can_stack_sale": promo.get("acumulable") in (True, 1) and "no acumul" not in fold(raw),
            "start": start, "end": end, "days": _promo_days(promo),
            "excluded_words": excluded_words, "included_scopes": included_scopes,
            "scope_words": words(re.split(r"\ben\b", norm(promo.get("title")), maxsplit=1)[-1])
            if re.search(r"\ben (?:lacteos|vinos|bebidas|electro|perfumeria|almacen)\b", norm(promo.get("title"))) else None}


def covered(rule, item):
    product = item["product"]
    path = product.get("category_path") or []
    narrow = item.get("narrow") or words(product["product_name"]) | words(path[-1] if path else "")
    broad = item.get("broad") or narrow | words(" ".join(path))
    if broad & rule["excluded_words"]:
        return False
    if any(not narrow & scope for scope in rule["included_scopes"]):
        return False
    if rule["scope_words"] and not broad & rule["scope_words"]:
        return False
    if "productos seleccionados" in norm(rule["promo"].get("title")):
        return False
    offer = item["offer"]
    if positive_price(offer.get("list_price")) and offer["list_price"] > offer["price"]:
        if not rule["can_stack_sale"]:
            return False
    return True


def scenario(store, items, rules, today):
    subtotal = sum((Decimal(str(item["offer"]["price"])) for item in items), Decimal(0))
    best_savings, best_rule, best_date, eligible_count = Decimal(0), None, today, 0
    for rule in rules:
        day = next((today+timedelta(days=i) for i in range(7)
                    if rule["start"] <= today+timedelta(days=i) <= rule["end"]
                    and (today+timedelta(days=i)).weekday() in rule["days"]), None)
        if day is None:
            continue
        eligible = [item for item in items if covered(rule, item)]
        base = sum((Decimal(str(item["offer"]["price"])) for item in eligible), Decimal(0))
        if base < rule["minimum"]:
            continue
        savings = min(base*rule["rate"], rule["cap"]).quantize(CENT, rounding=ROUND_HALF_UP)
        if savings > best_savings or (savings == best_savings and savings > 0 and day < best_date):
            best_savings, best_rule, best_date, eligible_count = savings, rule, day, len(eligible)
    promo = best_rule["promo"] if best_rule else None
    method = "Sin descuento calculable con tu perfil"
    if promo:
        method = str(promo.get("bank") or promo.get("wallet"))
        if promo.get("bank") and promo.get("wallet") and norm(promo["bank"]) != norm(promo["wallet"]):
            method += " vía "+str(promo["wallet"])
        if promo.get("card_type"):
            method += " · "+str(promo["card_type"])
        if promo.get("payment_method"):
            method += " · "+str(promo["payment_method"])
    return {"store": store.key, "store_name": store.name, "modality": "online",
            "date": best_date.isoformat(), "day": DAYS[best_date.weekday()], "payment": method,
            "subtotal": cash(subtotal), "savings": cash(best_savings), "total": cash(subtotal-best_savings),
            "priced_count": len(items), "eligible_count": eligible_count,
            "keys": sorted(item["product"]["product_key"] for item in items),
            "promotion": {k: promo.get(k) for k in ("id", "title", "discount", "tope", "min_purchase", "requirements", "exclusions")} if promo else None}


def compare_basket(products, promotions, methods, favorites=(), today=None):
    today = today or datetime.now(ZoneInfo("America/Argentina/Buenos_Aires")).date()
    pool = [s for s in STORES if not favorites or s.name in favorites or s.merchant in favorites]
    rules = {}
    for store in pool:
        rules[store.key] = [r for p in promotions if p.get("supermarket_name") == store.merchant
                            and (r := prepare(p, methods, today))]
    per_store, rows = {}, []
    for store in pool:
        items = []
        for product in products:
            offer = next((o for o in product.get("offers", []) if o["store"] == store.key and positive_price(o["price"])), None)
            if offer:
                path = product.get("category_path") or []
                narrow = words(product["product_name"]) | words(path[-1] if path else "")
                items.append({"product": product, "offer": offer, "narrow": narrow,
                              "broad": narrow | words(" ".join(path))})
        if not items:
            continue
        per_store[store.key] = items
        row = scenario(store, items, rules[store.key], today)
        row["missing"] = [p["product_name"] for p in products if p["product_key"] not in row["keys"]]
        row["coverage_pct"] = round(len(items)/len(products)*100, 1) if products else 0
        rows.append(row)
    rows.sort(key=lambda r: (-r["priced_count"], r["total"], r["store"]))
    complete = [r for r in rows if r["priced_count"] == len(products)]
    reference, kind = None, "insufficient"
    if complete:
        reference, kind = min(complete, key=lambda r: (r["total"], r["date"], r["store"])), "complete"
    elif rows:
        most = [r for r in rows if r["priced_count"] == rows[0]["priced_count"]]
        common = set.intersection(*(set(r["keys"]) for r in most))
        if len(common) >= max(1, math.ceil(len(products)*0.7)):
            candidates = [scenario(next(s for s in pool if s.key == r["store"]),
                                   [i for i in per_store[r["store"]] if i["product"]["product_key"] in common],
                                   rules[r["store"]], today) for r in most]
            reference = min(candidates, key=lambda r: (r["total"], r["date"], r["store"]))
            kind = "partial" if len(most) > 1 else "single_option"
    if reference:
        reference = dict(reference)
        reference["missing"] = [p["product_name"] for p in products if p["product_key"] not in reference["keys"]]
        for row in rows:
            intersection = set(reference["keys"]) & set(row["keys"])
            row["comparison"] = None
            if intersection and row["store"] != reference["store"]:
                comparisons = []
                for name in (reference["store"], row["store"]):
                    store = next(s for s in pool if s.key == name)
                    comparisons.append(scenario(store, [i for i in per_store[name] if i["product"]["product_key"] in intersection], rules[name], today))
                row["comparison"] = {"product_count": len(intersection),
                                     "difference": round(comparisons[1]["total"]-comparisons[0]["total"], 2),
                                     "reference_total": comparisons[0]["total"], "store_total": comparisons[1]["total"],
                                     "store_day": comparisons[1]["day"], "store_payment": comparisons[1]["payment"],
                                     "reference_day": comparisons[0]["day"], "reference_payment": comparisons[0]["payment"]}
    return {"reference": reference, "reference_kind": kind, "options": rows,
            "product_count": len(products), "as_of": today.isoformat(),
            "horizon_days": 7, "quantity_per_product": 1, "shipping_included": False,
            "physical_prices_available": False,
            "unsupported_favorites": [name for name in favorites if name not in {s.name for s in STORES} | {s.merchant for s in STORES}],
            "warnings": ["Falta considerar el costo de envío y posibles cargos de preparación o servicio.",
                         "Se usa una unidad de cada producto. Precios online: no verificamos precios ni stock presencial.",
                         "Para días futuros se mantienen los precios relevados, no se predicen precios.",
                         "Se elige una sola promoción por compra y se aplica el tope una sola vez, suponiendo que no fue consumido.",
                         "Las cuotas no se convierten en ahorro; no se acumulan beneficios de distintos bancos o billeteras.",
                         "No se calcularon beneficios con canal, tope o requisitos de perfil desconocidos; confirmá exclusiones y condiciones."]}
