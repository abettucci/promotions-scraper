"""
FastAPI REST API for promo-scraper
Exposes the SQLite database with promotions, banks, supermarkets
Includes user auth (JWT) and personalized promotion endpoints
"""
from fastapi import FastAPI, Query, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, List
from datetime import date, datetime, timedelta, timezone
from pydantic import BaseModel
import sqlite3
import json
from pathlib import Path
import sys
import os

sys.path.insert(0, str(Path(__file__).parent))
import config
from database import UserDatabase

# ── Auth deps ─────────────────────────────────────────────────────────────────
try:
    import bcrypt as _bcrypt
    from jose import JWTError, jwt
    AUTH_AVAILABLE = True
except ImportError:
    AUTH_AVAILABLE = False

def _hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()

def _verify_password(password: str, hashed: str) -> bool:
    return _bcrypt.checkpw(password.encode(), hashed.encode())

# ── Background scraper scheduler ─────────────────────────────────────────────
if os.getenv("ENABLE_SCRAPER", "").lower() in ("1", "true", "yes"):
    import scheduler
    scheduler.start()

app = FastAPI(
    title="Promo Scraper API",
    description="API de promociones de supermercados argentinos con descuentos bancarios",
    version="2.0.0"
)

# ── CORS ──────────────────────────────────────────────────────────────────────
allowed_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
frontend_url = os.environ.get("FRONTEND_URL")
if frontend_url:
    allowed_origins.append(frontend_url)
    if not frontend_url.endswith("/"):
        allowed_origins.append(frontend_url + "/")
    if "www." not in frontend_url:
        allowed_origins.append(frontend_url.replace("https://", "https://www."))

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# ── DB helpers ────────────────────────────────────────────────────────────────
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
                if isinstance(parsed, list):
                    d[field] = parsed
                elif isinstance(parsed, str) and parsed.strip():
                    d[field] = [parsed.strip()]
                else:
                    d[field] = []
            except json.JSONDecodeError:
                d[field] = [val.strip()]
        else:
            d[field] = []
    return d

_db = UserDatabase()

# ── JWT helpers ───────────────────────────────────────────────────────────────
security = HTTPBearer(auto_error=False)

def _create_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(days=config.JWT_EXPIRE_DAYS),
    }
    return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)

def _decode_token(token: str) -> Optional[int]:
    try:
        payload = jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
        return int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        return None

def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    if not AUTH_AVAILABLE:
        raise HTTPException(503, "Auth no disponible: instalá bcrypt y python-jose")
    if not credentials:
        raise HTTPException(401, "Token requerido")
    user_id = _decode_token(credentials.credentials)
    if not user_id:
        raise HTTPException(401, "Token inválido o expirado")
    user = _db.get_user_by_id(user_id)
    if not user:
        raise HTTPException(401, "Usuario no encontrado")
    return user

def _user_response(user: dict) -> dict:
    methods = _db.get_user_payment_methods(user["id"])
    return {
        "id": user["id"],
        "email": user["email"],
        "telegram_chat_id": user.get("telegram_chat_id"),
        "notify_daily": bool(user.get("notify_daily", True)),
        "notify_hour": user.get("notify_hour", 9),
        "payment_methods": methods,
        "created_at": user.get("created_at"),
    }

# ── Pydantic models ───────────────────────────────────────────────────────────
class RegisterBody(BaseModel):
    email: str
    password: str

class LoginBody(BaseModel):
    email: str
    password: str

class PaymentMethod(BaseModel):
    name: str
    type: str  # bank | wallet | club

class UpdatePaymentMethodsBody(BaseModel):
    methods: List[PaymentMethod]

class UpdateProfileBody(BaseModel):
    telegram_chat_id: Optional[str] = None
    notify_daily: Optional[bool] = None
    notify_hour: Optional[int] = None

# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "promo-scraper-api"}

# ── Admin: trigger manual scrape ──────────────────────────────────────────────
@app.post("/api/admin/scrape")
def trigger_scrape(token: str = Query(...)):
    """Lanza el scraper en background. Requiere ?token=<ADMIN_TOKEN>."""
    expected = os.getenv("ADMIN_TOKEN", "")
    if not expected or token != expected:
        raise HTTPException(403, "Token inválido")
    try:
        import scheduler
        import threading
        threading.Thread(target=scheduler._run_scraper, daemon=True).start()
        return {"status": "started", "message": "Scraper lanzado en background. Ver logs para progreso."}
    except Exception as e:
        raise HTTPException(500, f"Error lanzando scraper: {e}")

@app.get("/api/admin/last-scrape")
def get_last_scrape():
    """Devuelve timestamp del último scraping."""
    conn = get_conn()
    row = conn.execute(
        "SELECT MAX(scraped_at) as last FROM scrape_history WHERE status = 'success'"
    ).fetchone()
    conn.close()
    return {"last_successful_scrape": row["last"] if row else None}

# ── Auth endpoints ────────────────────────────────────────────────────────────
@app.post("/api/auth/register")
def register(body: RegisterBody):
    if not AUTH_AVAILABLE:
        raise HTTPException(503, "Auth no disponible")
    email = body.email.lower().strip()
    if not email or "@" not in email:
        raise HTTPException(400, "Email inválido")
    if len(body.password) < 6:
        raise HTTPException(400, "La contraseña debe tener al menos 6 caracteres")

    pw_hash = _hash_password(body.password)
    user_id = _db.create_user(email, pw_hash)
    if not user_id:
        raise HTTPException(409, "Ya existe una cuenta con ese email")

    user = _db.get_user_by_id(user_id)
    token = _create_token(user_id)
    return {"token": token, "user": _user_response(user)}


@app.post("/api/auth/login")
def login(body: LoginBody):
    if not AUTH_AVAILABLE:
        raise HTTPException(503, "Auth no disponible")
    user = _db.get_user_by_email(body.email)
    if not user or not _verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "Email o contraseña incorrectos")

    token = _create_token(user["id"])
    return {"token": token, "user": _user_response(user)}


@app.get("/api/auth/me")
def get_me(current_user=Depends(get_current_user)):
    return _user_response(current_user)


@app.put("/api/auth/me")
def update_me(body: UpdateProfileBody, current_user=Depends(get_current_user)):
    user = current_user
    _db.update_user_telegram(
        user["id"],
        telegram_chat_id=body.telegram_chat_id if body.telegram_chat_id is not None else user.get("telegram_chat_id"),
        notify_daily=body.notify_daily if body.notify_daily is not None else bool(user.get("notify_daily", True)),
        notify_hour=body.notify_hour if body.notify_hour is not None else user.get("notify_hour", 9),
    )
    updated = _db.get_user_by_id(user["id"])
    return _user_response(updated)


@app.put("/api/auth/me/payment-methods")
def update_payment_methods(body: UpdatePaymentMethodsBody, current_user=Depends(get_current_user)):
    methods = [{"name": m.name, "type": m.type} for m in body.methods]
    _db.set_user_payment_methods(current_user["id"], methods)
    updated = _db.get_user_by_id(current_user["id"])
    return _user_response(updated)


@app.get("/api/auth/me/promotions")
def get_my_promotions(
    today_only: bool = Query(True),
    current_user=Depends(get_current_user),
):
    promos = _db.get_promotions_for_user(current_user["id"], today_only=today_only)

    # Group by supermarket
    by_super: dict = {}
    for p in promos:
        name = p["supermarket_name"]
        by_super.setdefault(name, []).append(p)

    return {
        "total": len(promos),
        "today_only": today_only,
        "by_supermarket": [
            {"supermarket": name, "promotions": items}
            for name, items in by_super.items()
        ],
    }

# ── Catálogo de medios de pago ────────────────────────────────────────────────
@app.get("/api/catalog/payment-methods")
def get_payment_methods_catalog():
    return config.PAYMENT_METHODS_CATALOG

# ---------------------------------------------------------------------------
# GET /api/promotions
# ---------------------------------------------------------------------------
@app.get("/api/promotions")
def get_promotions(
    supermarket: Optional[str] = Query(None),
    bank: Optional[str] = Query(None),
    day: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    discount_type: Optional[str] = Query(None),
    active_today: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    conn = get_conn()
    cursor = conn.cursor()

    today_iso = date.today().isoformat()
    conditions = [
        "p.is_active = 1",
        # Excluir promos vencidas (valid_until < hoy)
        "(p.valid_until IS NULL OR p.valid_until = '' OR p.valid_until >= ?)",
        # Excluir promos que aún no empezaron (valid_from > hoy)
        "(p.valid_from IS NULL OR p.valid_from = '' OR p.valid_from <= ?)",
    ]
    params: list = [today_iso, today_iso]

    if supermarket:
        conditions.append("LOWER(s.name) = ?")
        params.append(supermarket.lower())

    if bank:
        conditions.append("(LOWER(p.bank) LIKE ? OR LOWER(p.wallet) LIKE ?)")
        params.extend([f"%{bank.lower()}%", f"%{bank.lower()}%"])

    if day:
        # Incluye promos del día específico + las que aplican todos los días (o sin día definido)
        conditions.append(
            "(LOWER(p.valid_days) LIKE ? OR LOWER(p.valid_days) LIKE ? "
            "OR p.valid_days IS NULL OR p.valid_days = '')"
        )
        params.extend([f"%{day.lower()}%", "%todos los d%"])

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
        day_map = {
            "monday": "lunes", "tuesday": "martes", "wednesday": "miércoles",
            "thursday": "jueves", "friday": "viernes", "saturday": "sábado", "sunday": "domingo"
        }
        today_es = day_map.get(date.today().strftime("%A").lower(), "")
        conditions.append(
            "(p.valid_days IS NULL OR p.valid_days = '' OR LOWER(p.valid_days) LIKE ?)"
        )
        params.append(f"%{today_es}%")

    where_clause = " AND ".join(conditions)
    offset = (page - 1) * page_size

    total = cursor.execute(
        f"SELECT COUNT(*) FROM promotions p JOIN supermarkets s ON p.supermarket_id = s.id WHERE {where_clause}",
        params
    ).fetchone()[0]

    rows = cursor.execute(f"""
        SELECT
            p.id, p.title, p.discount, p.bank, p.wallet, p.card_type,
            p.payment_method, p.store_types, p.valid_days,
            p.valid_from, p.valid_until, p.image_url, p.tope, p.acumulable,
            p.is_active, p.scraped_at,
            s.name AS supermarket_name,
            COALESCE((SELECT t.exclusions FROM terms_conditions t WHERE t.promotion_id = p.id LIMIT 1), p.exclusions) AS exclusions,
            COALESCE((SELECT t.requirements FROM terms_conditions t WHERE t.promotion_id = p.id LIMIT 1), p.requirements) AS requirements,
            (SELECT t.max_discount FROM terms_conditions t WHERE t.promotion_id = p.id LIMIT 1) AS max_discount,
            p.min_purchase
        FROM promotions p
        JOIN supermarkets s ON p.supermarket_id = s.id
        WHERE {where_clause}
        ORDER BY p.scraped_at DESC
        LIMIT ? OFFSET ?
    """, params + [page_size, offset]).fetchall()
    conn.close()

    return {"total": total, "page": page, "page_size": page_size,
            "pages": (total + page_size - 1) // page_size,
            "data": [row_to_dict(r) for r in rows]}


# ---------------------------------------------------------------------------
# GET /api/promotions/today
# ---------------------------------------------------------------------------
@app.get("/api/promotions/today")
def get_promotions_today():
    day_map = {
        "monday": "lunes", "tuesday": "martes", "wednesday": "miércoles",
        "thursday": "jueves", "friday": "viernes", "saturday": "sábado", "sunday": "domingo"
    }
    day_es = day_map.get(datetime.now().strftime("%A").lower(), "")

    today_iso = date.today().isoformat()
    conn = get_conn()
    rows = conn.execute("""
        SELECT
            p.id, p.title, p.discount, p.bank, p.wallet, p.card_type,
            p.payment_method, p.store_types, p.valid_days,
            p.valid_from, p.valid_until, p.image_url, p.tope, p.acumulable,
            s.name AS supermarket_name,
            COALESCE((SELECT t.exclusions FROM terms_conditions t WHERE t.promotion_id = p.id LIMIT 1), p.exclusions) AS exclusions,
            COALESCE((SELECT t.requirements FROM terms_conditions t WHERE t.promotion_id = p.id LIMIT 1), p.requirements) AS requirements,
            (SELECT t.max_discount FROM terms_conditions t WHERE t.promotion_id = p.id LIMIT 1) AS max_discount,
            p.min_purchase
        FROM promotions p
        JOIN supermarkets s ON p.supermarket_id = s.id
        WHERE p.is_active = 1
          AND (p.valid_days IS NULL OR p.valid_days = '' OR LOWER(p.valid_days) LIKE ? OR LOWER(p.valid_days) LIKE '%todos los d%')
          AND (p.valid_until IS NULL OR p.valid_until = '' OR p.valid_until >= ?)
          AND (p.valid_from IS NULL OR p.valid_from = '' OR p.valid_from <= ?)
        ORDER BY p.scraped_at DESC
    """, (f"%{day_es}%", today_iso, today_iso)).fetchall()
    conn.close()

    return {"day": day_es, "total": len(rows), "data": [row_to_dict(r) for r in rows]}


# ---------------------------------------------------------------------------
# GET /api/promotions/{id}
# ---------------------------------------------------------------------------
@app.get("/api/promotions/{promotion_id}")
def get_promotion(promotion_id: int):
    conn = get_conn()
    row = conn.execute("""
        SELECT
            p.id, p.supermarket_id, p.title, p.discount, p.bank, p.wallet,
            p.card_type, p.payment_method, p.store_types, p.valid_days,
            p.valid_from, p.valid_until, p.url, p.image_url, p.terms_raw,
            p.tope, p.acumulable, p.is_active, p.scraped_at, p.min_purchase,
            s.name AS supermarket_name,
            (SELECT t.raw_text FROM terms_conditions t WHERE t.promotion_id = p.id LIMIT 1) AS raw_text,
            (SELECT t.exclusions FROM terms_conditions t WHERE t.promotion_id = p.id LIMIT 1) AS exclusions,
            (SELECT t.requirements FROM terms_conditions t WHERE t.promotion_id = p.id LIMIT 1) AS requirements,
            (SELECT t.max_discount FROM terms_conditions t WHERE t.promotion_id = p.id LIMIT 1) AS max_discount,
            (SELECT t.min_purchase FROM terms_conditions t WHERE t.promotion_id = p.id LIMIT 1) AS tc_min_purchase,
            (SELECT t.valid_days FROM terms_conditions t WHERE t.promotion_id = p.id LIMIT 1) AS tc_valid_days,
            (SELECT t.payment_methods FROM terms_conditions t WHERE t.promotion_id = p.id LIMIT 1) AS payment_methods
        FROM promotions p
        JOIN supermarkets s ON p.supermarket_id = s.id
        WHERE p.id = ?
    """, (promotion_id,)).fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Promoción no encontrada")

    d = row_to_dict(row)
    for field in ("payment_methods", "tc_valid_days"):
        val = d.get(field)
        if val and isinstance(val, str):
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
    rows = conn.execute("""
        SELECT bank AS name, COUNT(*) AS count FROM promotions
        WHERE is_active = 1 AND bank IS NOT NULL AND bank != ''
        GROUP BY bank
        UNION
        SELECT wallet AS name, COUNT(*) AS count FROM promotions
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
    rows = conn.execute("""
        SELECT s.id, s.name, s.url, s.last_scraped, s.scrape_count,
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
    total_promos = conn.execute("SELECT COUNT(*) FROM promotions WHERE is_active = 1").fetchone()[0]
    total_banks = conn.execute("SELECT COUNT(DISTINCT bank) FROM promotions WHERE is_active = 1 AND bank != ''").fetchone()[0]
    total_supermarkets = conn.execute("SELECT COUNT(*) FROM supermarkets WHERE enabled = 1").fetchone()[0]
    last_updated = conn.execute("SELECT MAX(scraped_at) FROM promotions WHERE is_active = 1").fetchone()[0]
    top_banks = conn.execute("""
        SELECT bank AS name, COUNT(*) AS count FROM promotions
        WHERE is_active = 1 AND bank IS NOT NULL AND bank != ''
        GROUP BY bank ORDER BY count DESC LIMIT 5
    """).fetchall()
    by_supermarket = conn.execute("""
        SELECT s.name, COUNT(p.id) AS count FROM supermarkets s
        LEFT JOIN promotions p ON s.id = p.supermarket_id AND p.is_active = 1
        GROUP BY s.id ORDER BY count DESC
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
