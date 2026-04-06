"""
FastAPI REST API for promo-scraper
Exposes the SQLite database with promotions, banks, supermarkets
"""
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
from datetime import date, datetime
import sqlite3
import json
from pathlib import Path
import sys
import os

sys.path.insert(0, str(Path(__file__).parent))
import config

app = FastAPI(
    title="Promo Scraper API",
    description="API de promociones de supermercados argentinos con descuentos bancarios",
    version="1.0.0"
)

# CORS: permitir frontend en desarrollo y producción
# En producción, FRONTEND_URL debe ser la URL de Vercel (ej: https://promo-scraper.vercel.app)
allowed_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

# Agregar URL de producción si está configurada
frontend_url = os.environ.get("FRONTEND_URL")
if frontend_url:
    allowed_origins.append(frontend_url)
    # También permitir sin trailing slash y con www
    if not frontend_url.endswith("/"):
        allowed_origins.append(frontend_url + "/")
    if "www." not in frontend_url:
        allowed_origins.append(frontend_url.replace("https://", "https://www."))

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    """Health check endpoint para Railway"""
    return {"status": "healthy", "service": "promo-scraper-api"}


def get_conn():
    conn = sqlite3.connect(config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    for field in ("exclusions", "requirements"):
        val = d.get(field)
        if val and isinstance(val, str) and val.strip():
            try:
                parsed = json.loads(val)
                d[field] = parsed if isinstance(parsed, list) else []
            except json.JSONDecodeError:
                # Try pipe separator first, then semicolon (Carrefour scraper)
                if "|" in val:
                    items = [s.strip() for s in val.split("|") if s.strip()]
                else:
                    items = [s.strip() for s in val.split(";") if s.strip()]
                d[field] = items if items else []
        else:
            d[field] = []
    return d


# ---------------------------------------------------------------------------
# GET /api/promotions
# ---------------------------------------------------------------------------
@app.get("/api/promotions")
def get_promotions(
    supermarket: Optional[str] = Query(None, description="Nombre del supermercado"),
    bank: Optional[str] = Query(None, description="Nombre del banco o wallet"),
    day: Optional[str] = Query(None, description="Día de la semana (lunes, martes, ...)"),
    search: Optional[str] = Query(None, description="Búsqueda libre en título o términos"),
    discount_type: Optional[str] = Query(None, description="Tipo: percent | cuotas | cashback"),
    active_today: Optional[bool] = Query(None, description="Solo promos vigentes hoy"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    conn = get_conn()
    cursor = conn.cursor()

    conditions = ["p.is_active = 1"]
    params: list = []

    if supermarket:
        conditions.append("LOWER(s.name) = ?")
        params.append(supermarket.lower())

    if bank:
        conditions.append("(LOWER(p.bank) LIKE ? OR LOWER(p.wallet) LIKE ?)")
        params.extend([f"%{bank.lower()}%", f"%{bank.lower()}%"])

    if day:
        conditions.append("LOWER(p.valid_days) LIKE ?")
        params.append(f"%{day.lower()}%")

    if search:
        conditions.append("(LOWER(p.title) LIKE ? OR LOWER(p.terms_raw) LIKE ?)")
        params.extend([f"%{search.lower()}%", f"%{search.lower()}%"])

    if discount_type:
        if discount_type == "percent":
            conditions.append("p.discount LIKE '%\\%%' ESCAPE '\\'")
        elif discount_type == "cuotas":
            conditions.append("LOWER(p.discount) LIKE '%cuota%'")
        elif discount_type == "cashback":
            conditions.append("(LOWER(p.discount) LIKE '%cashback%' OR LOWER(p.discount) LIKE '%reintegro%')")

    if active_today:
        today = date.today().isoformat()
        day_name = date.today().strftime("%A").lower()
        # Map English day name to Spanish
        day_map = {
            "monday": "lunes", "tuesday": "martes", "wednesday": "miércoles",
            "thursday": "jueves", "friday": "viernes", "saturday": "sábado", "sunday": "domingo"
        }
        today_es = day_map.get(day_name, day_name)
        conditions.append(
            "(p.valid_days IS NULL OR p.valid_days = '' OR LOWER(p.valid_days) LIKE ?)"
        )
        params.append(f"%{today_es}%")

    where_clause = " AND ".join(conditions)
    offset = (page - 1) * page_size

    count_query = f"""
        SELECT COUNT(*)
        FROM promotions p
        JOIN supermarkets s ON p.supermarket_id = s.id
        LEFT JOIN terms_conditions t ON p.id = t.promotion_id
        WHERE {where_clause}
    """
    total = cursor.execute(count_query, params).fetchone()[0]

    data_query = f"""
        SELECT
            p.id, p.title, p.discount, p.bank, p.wallet, p.card_type,
            p.payment_method, p.store_types, p.valid_days,
            p.valid_from, p.valid_until, p.image_url, p.tope, p.acumulable,
            p.is_active, p.scraped_at,
            s.name AS supermarket_name,
            p.exclusions, p.requirements,
            t.max_discount, p.min_purchase
        FROM promotions p
        JOIN supermarkets s ON p.supermarket_id = s.id
        LEFT JOIN terms_conditions t ON p.id = t.promotion_id
        WHERE {where_clause}
        ORDER BY p.scraped_at DESC
        LIMIT ? OFFSET ?
    """
    rows = cursor.execute(data_query, params + [page_size, offset]).fetchall()
    conn.close()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
        "data": [row_to_dict(r) for r in rows],
    }


# ---------------------------------------------------------------------------
# GET /api/promotions/today
# ---------------------------------------------------------------------------
@app.get("/api/promotions/today")
def get_promotions_today():
    day_map = {
        "monday": "lunes", "tuesday": "martes", "wednesday": "miércoles",
        "thursday": "jueves", "friday": "viernes", "saturday": "sábado", "sunday": "domingo"
    }
    day_en = datetime.now().strftime("%A").lower()
    day_es = day_map.get(day_en, day_en)

    conn = get_conn()
    cursor = conn.cursor()

    rows = cursor.execute("""
        SELECT
            p.id, p.title, p.discount, p.bank, p.wallet, p.card_type,
            p.payment_method, p.store_types, p.valid_days,
            p.valid_from, p.valid_until, p.image_url, p.tope, p.acumulable,
            s.name AS supermarket_name,
            p.exclusions, p.requirements,
            t.max_discount, p.min_purchase
        FROM promotions p
        JOIN supermarkets s ON p.supermarket_id = s.id
        LEFT JOIN terms_conditions t ON p.id = t.promotion_id
        WHERE p.is_active = 1
          AND (p.valid_days IS NULL OR p.valid_days = '' OR LOWER(p.valid_days) LIKE ?)
        ORDER BY p.scraped_at DESC
    """, (f"%{day_es}%",)).fetchall()
    conn.close()

    return {"day": day_es, "total": len(rows), "data": [row_to_dict(r) for r in rows]}


# ---------------------------------------------------------------------------
# GET /api/promotions/{id}
# ---------------------------------------------------------------------------
@app.get("/api/promotions/{promotion_id}")
def get_promotion(promotion_id: int):
    conn = get_conn()
    cursor = conn.cursor()

    row = cursor.execute("""
        SELECT
            p.*,
            s.name AS supermarket_name,
            t.raw_text, t.exclusions, t.requirements,
            t.max_discount, t.min_purchase, t.valid_days AS tc_valid_days,
            t.payment_methods
        FROM promotions p
        JOIN supermarkets s ON p.supermarket_id = s.id
        LEFT JOIN terms_conditions t ON p.id = t.promotion_id
        WHERE p.id = ?
    """, (promotion_id,)).fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Promoción no encontrada")

    d = row_to_dict(row)
    # Parse remaining JSON arrays
    for field in ("payment_methods", "tc_valid_days"):
        val = d.get(field)
        if val and isinstance(val, str) and val.strip():
            try:
                d[field] = json.loads(val)
            except json.JSONDecodeError:
                d[field] = []
        else:
            d[field] = []
    return d


# ---------------------------------------------------------------------------
# GET /api/banks
# ---------------------------------------------------------------------------
@app.get("/api/banks")
def get_banks():
    conn = get_conn()
    cursor = conn.cursor()

    rows = cursor.execute("""
        SELECT bank AS name, COUNT(*) AS count
        FROM promotions
        WHERE is_active = 1 AND bank IS NOT NULL AND bank != ''
        GROUP BY bank
        UNION
        SELECT wallet AS name, COUNT(*) AS count
        FROM promotions
        WHERE is_active = 1 AND wallet IS NOT NULL AND wallet != ''
        GROUP BY wallet
        ORDER BY count DESC
    """).fetchall()
    conn.close()

    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# GET /api/supermarkets
# ---------------------------------------------------------------------------
@app.get("/api/supermarkets")
def get_supermarkets():
    conn = get_conn()
    cursor = conn.cursor()

    rows = cursor.execute("""
        SELECT
            s.id, s.name, s.url, s.last_scraped, s.scrape_count,
            COUNT(p.id) AS active_promotions
        FROM supermarkets s
        LEFT JOIN promotions p ON s.id = p.supermarket_id AND p.is_active = 1
        GROUP BY s.id
        ORDER BY active_promotions DESC
    """).fetchall()
    conn.close()

    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# GET /api/stats
# ---------------------------------------------------------------------------
@app.get("/api/stats")
def get_stats():
    conn = get_conn()
    cursor = conn.cursor()

    total_promos = cursor.execute(
        "SELECT COUNT(*) FROM promotions WHERE is_active = 1"
    ).fetchone()[0]

    total_banks = cursor.execute(
        "SELECT COUNT(DISTINCT bank) FROM promotions WHERE is_active = 1 AND bank != ''"
    ).fetchone()[0]

    total_supermarkets = cursor.execute(
        "SELECT COUNT(*) FROM supermarkets WHERE enabled = 1"
    ).fetchone()[0]

    last_updated = cursor.execute(
        "SELECT MAX(scraped_at) FROM promotions WHERE is_active = 1"
    ).fetchone()[0]

    top_banks = cursor.execute("""
        SELECT bank AS name, COUNT(*) AS count
        FROM promotions
        WHERE is_active = 1 AND bank IS NOT NULL AND bank != ''
        GROUP BY bank
        ORDER BY count DESC
        LIMIT 5
    """).fetchall()

    by_supermarket = cursor.execute("""
        SELECT s.name, COUNT(p.id) AS count
        FROM supermarkets s
        LEFT JOIN promotions p ON s.id = p.supermarket_id AND p.is_active = 1
        GROUP BY s.id
        ORDER BY count DESC
    """).fetchall()

    conn.close()

    return {
        "total_promotions": total_promos,
        "total_banks": total_banks,
        "total_supermarkets": total_supermarkets,
        "last_updated": last_updated,
        "top_banks": [dict(r) for r in top_banks],
        "by_supermarket": [dict(r) for r in by_supermarket],
    }
