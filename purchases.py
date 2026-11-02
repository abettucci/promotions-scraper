"""Compras privadas declaradas y métricas basadas en evidencia histórica diaria."""
from __future__ import annotations

import json
import re
from collections import Counter
from contextlib import closing
from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from payment_preferences import _norm
from promotion_history import ARGENTINA, init_history, merge_history
from promo_questions import _promo_days


def today():
    return datetime.now(ARGENTINA).date()


class PurchaseBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    request_id: UUID
    purchased_on: date
    merchant: str = Field(min_length=1, max_length=120)
    amount: Decimal = Field(gt=0, le=1_000_000_000, decimal_places=2, allow_inf_nan=False)
    received_discount: Decimal | None = Field(default=None, ge=0, le=1_000_000_000, decimal_places=2, allow_inf_nan=False)
    bank: str = Field(default="", max_length=80)
    wallet: str = Field(default="", max_length=80)
    card_type: Literal["credit", "debit", "account", "cash", "unknown"] = "unknown"
    modality: Literal["online", "in_store", "unknown"] = "unknown"

    @field_validator("purchased_on", mode="before")
    @classmethod
    def calendar_date(cls, value):
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("Usá una fecha YYYY-MM-DD.")
        return value

    @field_validator("amount", "received_discount", mode="before")
    @classmethod
    def not_boolean(cls, value):
        if isinstance(value, bool):
            raise ValueError("Monto inválido.")
        return value

    @field_validator("merchant", "bank", "wallet")
    @classmethod
    def plain_text(cls, value):
        if any(ord(char) < 32 for char in value):
            raise ValueError("Texto inválido.")
        return value

    @model_validator(mode="after")
    def valid_purchase(self):
        if not date(2000, 1, 1) <= self.purchased_on <= today():
            raise ValueError("La compra debe tener una fecha pasada o de hoy.")
        if self.received_discount is not None and self.received_discount > self.amount:
            raise ValueError("El descuento recibido no puede superar el monto original.")
        return self


def init_purchases(conn):
    init_history(conn)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS purchases (
            id TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            request_id TEXT NOT NULL, purchased_on TEXT NOT NULL, merchant TEXT NOT NULL,
            amount_cents INTEGER NOT NULL CHECK(amount_cents>0), received_discount_cents INTEGER,
            bank TEXT NOT NULL, wallet TEXT NOT NULL, card_type TEXT NOT NULL, modality TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(user_id,request_id)
        );
        CREATE INDEX IF NOT EXISTS idx_purchases_user_day ON purchases(user_id,purchased_on);
    """)


class PurchaseStore:
    def __init__(self, users_db):
        self.users_db = users_db

    def sync(self, promotions_path):
        with closing(self.users_db._conn()) as conn:
            merge_history(conn, promotions_path)

    def create(self, user_id, body):
        with closing(self.users_db._conn()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute("SELECT * FROM purchases WHERE user_id=? AND request_id=?",
                                    (user_id, str(body.request_id))).fetchone()
            if existing:
                # Misma clave con otro contenido no puede ocultar una compra distinta.
                if self._payload(existing) != self._body_payload(body):
                    raise ValueError("idempotency")
                return dict(existing)
            if conn.execute("SELECT COUNT(*) FROM purchases WHERE user_id=?", (user_id,)).fetchone()[0] >= 5000:
                raise ValueError("limit")
            identifier = str(uuid4())
            conn.execute("""INSERT INTO purchases
                (id,user_id,request_id,purchased_on,merchant,amount_cents,received_discount_cents,bank,wallet,card_type,modality)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""", (identifier, user_id, str(body.request_id), *self._body_payload(body)))
            conn.commit()
            return dict(conn.execute("SELECT * FROM purchases WHERE id=? AND user_id=?", (identifier, user_id)).fetchone())

    @staticmethod
    def _body_payload(body):
        return (body.purchased_on.isoformat(), body.merchant, int(body.amount*100),
                int(body.received_discount*100) if body.received_discount is not None else None,
                body.bank, body.wallet, body.card_type, body.modality)

    @staticmethod
    def _payload(row):
        return tuple(row[key] for key in ("purchased_on", "merchant", "amount_cents", "received_discount_cents",
                                         "bank", "wallet", "card_type", "modality"))

    def delete(self, user_id, identifier):
        with closing(self.users_db._conn()) as conn:
            deleted = conn.execute("DELETE FROM purchases WHERE id=? AND user_id=?", (identifier, user_id)).rowcount
            conn.commit()
            return bool(deleted)

    def report(self, user_id, start, end, page=1, page_size=20):
        with closing(self.users_db._conn()) as conn:
            records = conn.execute("SELECT * FROM purchases WHERE user_id=? AND purchased_on BETWEEN ? AND ? ORDER BY purchased_on DESC, created_at DESC, id",
                                   (user_id, start.isoformat(), end.isoformat())).fetchall()
            cache = {}
            analyzed = []
            for row in records:
                key = row["merchant"], row["purchased_on"]
                if key not in cache:
                    cache[key] = conn.execute("""SELECT o.*, v.payload FROM promotion_observations o
                        JOIN promotion_versions v ON v.revision=o.revision
                        WHERE o.merchant=? AND o.observed_on=?""", key).fetchall()
                analyzed.append(analyze(dict(row), cache[key]))
            history = conn.execute("SELECT MIN(observed_on) AS first_day, MAX(observed_on) AS last_day FROM promotion_observations WHERE provenance='scrape'").fetchone()
        known = [p for p in analyzed if p["history_status"] == "observed"]
        promo = [p for p in analyzed if p["has_percentage_promo"]]
        discounts = Counter()
        for p in promo:
            rates = sorted({("Hasta " if _norm(c["discount"]).startswith("hasta ") else "") + f"{c['percentage']:g}%"
                            for c in p["promotions"] if c["evidence"] == "scrape" and c["percentage"] is not None})
            discounts[rates[0] if len(rates) == 1 else "Varios porcentajes"] += 1
        declared = [p for p in analyzed if p["received_discount"] is not None]
        return {"purchases": analyzed[(page-1)*page_size:page*page_size], "page": page, "page_size": page_size,
                "total": len(analyzed), "from": start.isoformat(), "to": end.isoformat(),
                "summary": {"purchase_count": len(analyzed), "with_history_count": len(known),
                    "without_history_count": len(analyzed)-len(known), "promo_day_count": len(promo),
                    "promo_day_share_pct": round(len(promo)/len(known)*100, 1) if known else None,
                    "possible_payment_count": sum(any(c["payment_match"] == "possible" and c["evidence"] == "scrape" for c in p["promotions"]) for p in analyzed),
                    "total_amount": sum(r["amount_cents"] for r in records)/100,
                    "declared_savings": sum(r["received_discount_cents"] or 0 for r in records)/100,
                    "declared_savings_count": len(declared),
                    "declared_effective_pct": round(sum(p["received_discount"] for p in declared)/sum(p["amount"] for p in declared)*100, 2) if declared else None,
                    "by_published_percentage": [{"label": label, "purchases": count} for label, count in sorted(discounts.items())]},
                "history": dict(history),
                "notes": ["El porcentaje publicado no prueba que hayas recibido el beneficio.",
                    "Sólo se cruzan observaciones del mismo comercio y día, con vigencia y día de aplicación verificables.",
                    "Los días sin evidencia y los snapshots legacy no cuentan como compras sin promoción ni entran en el denominador.",
                    "Medio compatible significa coincidencia parcial; faltan validar productos, tiers, topes consumidos, sucursal y otros requisitos.",
                    "El ahorro recibido es declarado por vos; no se estima a partir del porcentaje de la promoción.",
                    "La observación es diaria, no prueba las condiciones exactas a la hora del pago."]}


def _day_matches(promo, day):
    try:
        start, end = date.fromisoformat(promo.get("valid_from") or ""), date.fromisoformat(promo.get("valid_until") or "")
    except ValueError:
        return None
    if not start <= day <= end:
        return False
    days = _norm(promo.get("valid_days"))
    if start == end == day:
        return True
    if not re.search(r"lunes|martes|miercoles|jueves|viernes|sabado|domingo|todos", days):
        return None
    return day.weekday() in _promo_days(promo)


def _percentage(value):
    value = _norm(value)
    matches = re.findall(r"(\d+(?:[.,]\d+)?)\s*%", value)
    if len(matches) != 1 or re.search(r"cuota|\btna\b|\bcft\b|interes", value):
        return None
    number = Decimal(matches[0].replace(",", "."))
    return float(number) if 0 < number <= 100 else None


def _payment_match(purchase, promo):
    for key in ("bank", "wallet"):
        if promo.get(key):
            if not purchase.get(key):
                return "unknown"
            if re.sub(r"^banco\s+", "", _norm(purchase[key])) != re.sub(r"^banco\s+", "", _norm(promo[key])):
                return "different"
    scope = _norm(promo.get("store_types"))
    if purchase["modality"] == "unknown" or not scope:
        return "unknown"
    online = "online" in scope
    physical = any(w in scope for w in ("tienda", "presencial", "sucursal"))
    if not online and not physical:
        return "unknown"
    if purchase["modality"] == "online" and not online:
        return "different"
    if purchase["modality"] == "in_store" and not physical:
        return "different"
    cards = _norm(promo.get("card_type"))
    if any(word in cards for word in ("credito", "debito")) and purchase["card_type"] not in {"credit", "debit"}:
        return "unknown" if purchase["card_type"] == "unknown" else "different"
    if "credito" in cards and "debito" not in cards and purchase["card_type"] != "credit":
        return "unknown" if purchase["card_type"] == "unknown" else "different"
    if "debito" in cards and "credito" not in cards and purchase["card_type"] != "debit":
        return "unknown" if purchase["card_type"] == "unknown" else "different"
    return "possible" if promo.get("bank") or promo.get("wallet") else "unknown"


def analyze(purchase, observations):
    day = date.fromisoformat(purchase["purchased_on"])
    candidates, has_observation, uncertain = [], False, False
    for observation in observations:
        promo = json.loads(observation["payload"])
        evidence = observation["provenance"]
        if evidence == "scrape":
            has_observation = True
        if not promo.get("is_active"):
            continue
        match = _day_matches(promo, day)
        if match is None and evidence == "scrape":
            uncertain = True
        if match is not True:
            continue
        candidates.append({"revision": observation["revision"], "title": promo.get("title"),
            "discount": promo.get("discount"), "percentage": _percentage(promo.get("discount")),
            "bank": promo.get("bank"), "wallet": promo.get("wallet"), "card_type": promo.get("card_type"),
            "store_types": promo.get("store_types"), "tope": promo.get("tope"), "min_purchase": promo.get("min_purchase"),
            "exclusions": promo.get("exclusions") or [], "requirements": promo.get("requirements") or [],
            "evidence": evidence, "payment_match": _payment_match(purchase, promo), "observed_at": observation["observed_at"]})
    verified = [p for p in candidates if p["evidence"] == "scrape" and p["percentage"] is not None]
    # Un faltante/ambigüedad de calendario nunca se convierte en un cero verificable.
    status = "observed" if has_observation and (not uncertain or verified) else "insufficient"
    return {"id": purchase["id"], "purchased_on": purchase["purchased_on"], "merchant": purchase["merchant"],
            "amount": purchase["amount_cents"]/100,
            "received_discount": purchase["received_discount_cents"]/100 if purchase["received_discount_cents"] is not None else None,
            "bank": purchase["bank"], "wallet": purchase["wallet"], "card_type": purchase["card_type"], "modality": purchase["modality"],
            "history_status": status, "has_percentage_promo": bool(verified), "promotions": candidates[:30],
            "promotion_count": len(candidates)}
