"""
Gestión de base de datos SQLite
"""
import sqlite3
import re
import unicodedata
from datetime import datetime
from typing import List, Dict, Optional
import json
import config


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn")


def normalize_date_iso(value) -> Optional[str]:
    """Normaliza una fecha a formato ISO (YYYY-MM-DD) para que las comparaciones de strings funcionen.

    Acepta:
    - 'YYYY-MM-DD' o 'YYYY/MM/DD' → ya está OK
    - 'DD/MM/YYYY' o 'DD-MM-YYYY' → convierte
    - 'DD/MM/YY' → asume 20YY
    - Otros formatos → devuelve '' (sin filtro)
    """
    if not value:
        return ''
    s = str(value).strip()
    if not s:
        return ''
    # ISO ya correcto
    m = re.match(r'^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$', s)
    if m:
        y, mo, d = m.groups()
        return f"{y}-{int(mo):02d}-{int(d):02d}"
    # DD/MM/YYYY o DD-MM-YYYY
    m = re.match(r'^(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})$', s)
    if m:
        d, mo, y = m.groups()
        if len(y) == 2:
            y = f"20{y}"
        return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
    # No reconocemos el formato — devolver vacío para que no se filtre
    return ''

class Database:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or config.DATABASE_PATH
        self.init_database()
    
    def get_connection(self):
        """Obtiene una conexión a la base de datos"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Para acceder por nombre de columna
        return conn
    
    def init_database(self):
        """Inicializa las tablas de la base de datos"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Tabla de supermercados / merchants
        # category: 'supermarket' | 'fuel'
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS supermarkets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                url TEXT NOT NULL,
                category TEXT DEFAULT 'supermarket',
                last_scraped TIMESTAMP,
                scrape_count INTEGER DEFAULT 0,
                enabled BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Migración: agregar columna category si no existe
        try:
            cursor.execute("ALTER TABLE supermarkets ADD COLUMN category TEXT DEFAULT 'supermarket'")
            conn.commit()
        except Exception:
            pass
        
        # Tabla de promociones
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS promotions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                supermarket_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                discount TEXT,
                bank TEXT,
                wallet TEXT,
                card_type TEXT,
                payment_method TEXT,
                store_types TEXT,
                valid_days TEXT,
                valid_from DATE,
                valid_until DATE,
                url TEXT,
                image_url TEXT,
                terms_raw TEXT,
                exclusions TEXT,
                requirements TEXT,
                tope TEXT,
                acumulable BOOLEAN,
                is_active BOOLEAN DEFAULT 1,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (supermarket_id) REFERENCES supermarkets(id),
                UNIQUE(supermarket_id, title, bank)
            )
        """)
        
        # Tabla de términos y condiciones
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS terms_conditions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                promotion_id INTEGER NOT NULL UNIQUE,
                raw_text TEXT,
                exclusions TEXT,  -- JSON array
                requirements TEXT,  -- JSON array
                max_discount TEXT,
                min_purchase TEXT,
                valid_days TEXT,  -- JSON array
                payment_methods TEXT,  -- JSON array
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (promotion_id) REFERENCES promotions(id)
            )
        """)

        # Clean up duplicate terms_conditions rows from previous runs
        cursor.execute("""
            DELETE FROM terms_conditions
            WHERE id NOT IN (
                SELECT MIN(id) FROM terms_conditions GROUP BY promotion_id
            )
        """)
        conn.commit()
        
        # Tabla de historial de scraping
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scrape_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                supermarket_id INTEGER NOT NULL,
                status TEXT NOT NULL,  -- success, error
                promotions_found INTEGER DEFAULT 0,
                error_message TEXT,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (supermarket_id) REFERENCES supermarkets(id)
            )
        """)
        
        # Add min_purchase column if it doesn't exist (safe migration)
        try:
            cursor.execute("ALTER TABLE promotions ADD COLUMN min_purchase TEXT")
            conn.commit()
        except Exception:
            pass  # Column already exists

        # Ensure one terms_conditions row per promotion (for existing DBs)
        try:
            cursor.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_tc_promotion_id "
                "ON terms_conditions(promotion_id)"
            )
            conn.commit()
        except Exception:
            pass

        # Migración: normalizar valid_from/valid_until existentes a ISO (YYYY-MM-DD)
        try:
            rows = cursor.execute(
                "SELECT id, valid_from, valid_until FROM promotions "
                "WHERE valid_from IS NOT NULL OR valid_until IS NOT NULL"
            ).fetchall()
            updated = 0
            for r in rows:
                new_from = normalize_date_iso(r['valid_from'])
                new_until = normalize_date_iso(r['valid_until'])
                if new_from != (r['valid_from'] or '') or new_until != (r['valid_until'] or ''):
                    cursor.execute(
                        "UPDATE promotions SET valid_from = ?, valid_until = ? WHERE id = ?",
                        (new_from, new_until, r['id']),
                    )
                    updated += 1
            if updated:
                conn.commit()
                print(f"📅 Migración fechas: {updated} promos normalizadas a ISO")
        except Exception as e:
            print(f"⚠️ Migración fechas falló: {e}")

        # Desactivar promos vencidas (valid_until < hoy) sin esperar al próximo scrape
        try:
            today_iso = datetime.now().date().isoformat()
            res = cursor.execute(
                "UPDATE promotions SET is_active = 0 "
                "WHERE is_active = 1 AND valid_until IS NOT NULL "
                "AND valid_until != '' AND valid_until < ?",
                (today_iso,),
            )
            if res.rowcount:
                conn.commit()
                print(f"🗓️  {res.rowcount} promos vencidas desactivadas")
        except Exception as e:
            print(f"⚠️ Desactivación de vencidas falló: {e}")

        # ── Tabla de usuarios ────────────────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                telegram_chat_id TEXT,
                notify_daily BOOLEAN DEFAULT 1,
                notify_hour INTEGER DEFAULT 9,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # ── Métodos de pago por usuario ───────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_payment_methods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                entity_name TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                UNIQUE(user_id, entity_name)
            )
        """)

        conn.commit()
        conn.close()

        print(f"✅ Base de datos inicializada: {self.db_path}")

    # ── User CRUD ─────────────────────────────────────────────────────────────

    def create_user(self, email: str, password_hash: str) -> Optional[int]:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (email, password_hash) VALUES (?, ?)",
                (email.lower().strip(), password_hash),
            )
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            return None
        finally:
            conn.close()

    def get_user_by_email(self, email: str) -> Optional[Dict]:
        conn = self.get_connection()
        row = conn.execute(
            "SELECT * FROM users WHERE email = ?", (email.lower().strip(),)
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        conn = self.get_connection()
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def update_user_telegram(self, user_id: int, telegram_chat_id: str,
                             notify_daily: bool, notify_hour: int):
        conn = self.get_connection()
        conn.execute(
            """UPDATE users
               SET telegram_chat_id = ?, notify_daily = ?, notify_hour = ?,
                   updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (telegram_chat_id or None, int(notify_daily), int(notify_hour), user_id),
        )
        conn.commit()
        conn.close()

    def set_user_payment_methods(self, user_id: int, methods: List[Dict]):
        """Reemplaza todos los métodos de pago del usuario."""
        conn = self.get_connection()
        conn.execute("DELETE FROM user_payment_methods WHERE user_id = ?", (user_id,))
        conn.executemany(
            "INSERT OR IGNORE INTO user_payment_methods (user_id, entity_name, entity_type) VALUES (?, ?, ?)",
            [(user_id, m["name"], m["type"]) for m in methods if m.get("name") and m.get("type")],
        )
        conn.commit()
        conn.close()

    def get_user_payment_methods(self, user_id: int) -> List[Dict]:
        conn = self.get_connection()
        rows = conn.execute(
            "SELECT entity_name AS name, entity_type AS type FROM user_payment_methods WHERE user_id = ?",
            (user_id,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_users_for_notification(self) -> List[Dict]:
        """Usuarios con Telegram configurado y notify_daily activo."""
        conn = self.get_connection()
        rows = conn.execute(
            "SELECT * FROM users WHERE telegram_chat_id IS NOT NULL AND notify_daily = 1"
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_promotions_for_user(self, user_id: int, today_only: bool = True) -> List[Dict]:
        """Promociones activas que coinciden con los métodos de pago del usuario."""
        methods = self.get_user_payment_methods(user_id)
        if not methods:
            return []

        day_map = {
            "monday": "lunes", "tuesday": "martes", "wednesday": "miércoles",
            "thursday": "jueves", "friday": "viernes", "saturday": "sábado", "sunday": "domingo"
        }
        today_es = day_map.get(datetime.now().strftime("%A").lower(), "")

        entity_conditions = " OR ".join(
            ["(LOWER(p.bank) LIKE ? OR LOWER(p.wallet) LIKE ?)"] * len(methods)
        )
        entity_params: list = []
        for m in methods:
            entity_params.extend([f"%{m['name'].lower()}%", f"%{m['name'].lower()}%"])

        day_clause = ""
        day_params: list = []
        if today_only and today_es:
            today_es_norm = _strip_accents(today_es).lower()
            if today_es_norm != today_es:
                day_clause = ("AND (p.valid_days IS NULL OR p.valid_days = '' "
                              "OR LOWER(p.valid_days) LIKE ? OR LOWER(p.valid_days) LIKE ? "
                              "OR LOWER(p.valid_days) LIKE ?)")
                day_params = [f"%{today_es}%", f"%{today_es_norm}%", "%todos los d%"]
            else:
                day_clause = ("AND (p.valid_days IS NULL OR p.valid_days = '' "
                              "OR LOWER(p.valid_days) LIKE ? OR LOWER(p.valid_days) LIKE ?)")
                day_params = [f"%{today_es}%", "%todos los d%"]

        query = f"""
            SELECT p.id, p.title, p.discount, p.bank, p.wallet,
                   p.valid_days, p.store_types, p.tope, p.min_purchase,
                   p.acumulable, s.name AS supermarket_name
            FROM promotions p
            JOIN supermarkets s ON p.supermarket_id = s.id
            WHERE p.is_active = 1 AND ({entity_conditions}) {day_clause}
            ORDER BY s.name, p.discount DESC
        """
        conn = self.get_connection()
        rows = conn.execute(query, entity_params + day_params).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    
    def insert_supermarket(self, name: str, url: str, category: str = 'supermarket') -> int:
        """Inserta o actualiza un supermercado / merchant. category: 'supermarket' | 'fuel'."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO supermarkets (name, url, category)
            VALUES (?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET url=excluded.url, category=excluded.category
        """, (name, url, category))

        supermarket_id = cursor.lastrowid or cursor.execute(
            "SELECT id FROM supermarkets WHERE name = ?", (name,)
        ).fetchone()[0]

        conn.commit()
        conn.close()

        return supermarket_id
    
    def update_supermarket_scraped(self, supermarket_id: int):
        """Actualiza última fecha de scraping"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE supermarkets
            SET last_scraped = ?,
                scrape_count = scrape_count + 1
            WHERE id = ?
        """, (datetime.now(), supermarket_id))
        
        conn.commit()
        conn.close()
    
    def insert_promotion(self, supermarket_id: int, promo_data: Dict) -> Optional[int]:
        """Inserta una promoción"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Normalize field aliases across scrapers
            store_types = promo_data.get('store_types') or promo_data.get('aplica_en', '')
            min_purchase = promo_data.get('min_purchase') or promo_data.get('monto_minimo', '')

            # Truncate title so near-identical long titles hit the UNIQUE constraint
            title = (promo_data.get('title', '') or '')[:200]

            # Normalizar fechas a ISO (YYYY-MM-DD) para que el filtro de vigencia funcione
            valid_from = normalize_date_iso(promo_data.get('valid_from'))
            valid_until = normalize_date_iso(promo_data.get('valid_until'))

            cursor.execute("""
                INSERT INTO promotions
                (supermarket_id, title, discount, bank, wallet, card_type,
                 payment_method, store_types, valid_days, valid_from, valid_until,
                 url, image_url, terms_raw, exclusions, requirements, tope, acumulable, min_purchase)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(supermarket_id, title, bank) DO UPDATE SET
                    discount = excluded.discount,
                    payment_method = excluded.payment_method,
                    store_types = excluded.store_types,
                    valid_days = excluded.valid_days,
                    valid_from = excluded.valid_from,
                    valid_until = excluded.valid_until,
                    terms_raw = excluded.terms_raw,
                    exclusions = excluded.exclusions,
                    requirements = excluded.requirements,
                    tope = excluded.tope,
                    acumulable = excluded.acumulable,
                    min_purchase = excluded.min_purchase,
                    is_active = 1,
                    scraped_at = CURRENT_TIMESTAMP
            """, (
                supermarket_id,
                title,
                promo_data.get('discount', '') or '',
                # Coerce None → '' so UNIQUE(supermarket_id, title, bank) works (SQLite NULL != NULL)
                promo_data.get('bank') or '',
                promo_data.get('wallet') or '',
                promo_data.get('card_type') or '',
                promo_data.get('payment_method', ''),
                store_types,
                promo_data.get('valid_days', ''),
                valid_from,
                valid_until,
                promo_data.get('url', ''),
                promo_data.get('image_url', ''),
                promo_data.get('terms_raw', ''),
                promo_data.get('exclusions', ''),
                promo_data.get('requirements', ''),
                promo_data.get('tope', ''),
                promo_data.get('acumulable'),
                min_purchase,
            ))
            
            promotion_id = cursor.lastrowid
            
            # Si lastrowid es 0, significa que fue un UPDATE (ON CONFLICT)
            if not promotion_id:
                result = cursor.execute("""
                    SELECT id FROM promotions
                    WHERE supermarket_id = ? AND title = ? AND bank = ?
                """, (supermarket_id, title, promo_data.get('bank', ''))).fetchone()
                
                if result:
                    promotion_id = result[0]
            
            conn.commit()
            return promotion_id
            
        except Exception as e:
            print(f"Error insertando promoción: {e}")
            import traceback
            traceback.print_exc()
            return None
        finally:
            conn.close()
    
    def insert_terms(self, promotion_id: int, terms_data: Dict):
        """Inserta términos y condiciones (one row per promotion)"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "DELETE FROM terms_conditions WHERE promotion_id = ?",
            (promotion_id,),
        )
        cursor.execute("""
            INSERT INTO terms_conditions
            (promotion_id, raw_text, exclusions, requirements, 
             max_discount, min_purchase, valid_days, payment_methods)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            promotion_id,
            terms_data.get('raw_text', ''),
            json.dumps(terms_data.get('exclusions', [])),
            json.dumps(terms_data.get('requirements', [])),
            terms_data.get('max_discount', ''),
            terms_data.get('min_purchase', ''),
            json.dumps(terms_data.get('valid_days', [])),
            json.dumps(terms_data.get('payment_methods', []))
        ))

        conn.commit()
        conn.close()
    
    def insert_scrape_history(self, supermarket_id: int, status: str, 
                            promotions_found: int = 0, error_message: str = None):
        """Registra historial de scraping"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO scrape_history
            (supermarket_id, status, promotions_found, error_message)
            VALUES (?, ?, ?, ?)
        """, (supermarket_id, status, promotions_found, error_message))
        
        conn.commit()
        conn.close()
    
    def get_active_promotions(self, supermarket_name: str = None) -> List[Dict]:
        """Obtiene promociones activas"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT 
                p.*,
                s.name as supermarket_name,
                t.raw_text as terms_raw,
                t.exclusions,
                t.requirements,
                t.max_discount,
                t.min_purchase
            FROM promotions p
            JOIN supermarkets s ON p.supermarket_id = s.id
            LEFT JOIN terms_conditions t ON p.id = t.promotion_id
            WHERE p.is_active = 1
        """
        
        params = []
        if supermarket_name:
            query += " AND s.name = ?"
            params.append(supermarket_name)
        
        query += " ORDER BY p.scraped_at DESC"
        
        cursor.execute(query, params)
        
        promotions = []
        for row in cursor.fetchall():
            promo = dict(row)
            # Parse JSON fields - manejar None y strings vacíos
            exclusions = promo.get('exclusions')
            requirements = promo.get('requirements')
            
            # Parsear exclusions
            if exclusions and isinstance(exclusions, str) and exclusions.strip():
                try:
                    promo['exclusions'] = json.loads(exclusions)
                except json.JSONDecodeError:
                    promo['exclusions'] = []
            else:
                promo['exclusions'] = []
            
            # Parsear requirements
            if requirements and isinstance(requirements, str) and requirements.strip():
                try:
                    promo['requirements'] = json.loads(requirements)
                except json.JSONDecodeError:
                    promo['requirements'] = []
            else:
                promo['requirements'] = []
            
            promotions.append(promo)
        
        conn.close()
        return promotions
    
    def get_supermarket_stats(self) -> List[Dict]:
        """Obtiene estadísticas por supermercado"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                s.name,
                s.last_scraped,
                s.scrape_count,
                COUNT(p.id) as active_promotions
            FROM supermarkets s
            LEFT JOIN promotions p ON s.id = p.supermarket_id AND p.is_active = 1
            GROUP BY s.id
            ORDER BY active_promotions DESC
        """)
        
        stats = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return stats
    
    def deactivate_all_for_supermarket(self, supermarket_id: int):
        """Desactiva todas las promociones de un supermercado antes de re-insertar"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE promotions SET is_active = 0 WHERE supermarket_id = ?", (supermarket_id,))
        conn.commit()
        conn.close()

    def deactivate_old_promotions(self, supermarket_id: int, current_titles: List[str]):
        """Desactiva promociones que ya no están en el sitio"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        placeholders = ','.join('?' * len(current_titles))
        cursor.execute(f"""
            UPDATE promotions
            SET is_active = 0
            WHERE supermarket_id = ?
            AND title NOT IN ({placeholders})
            AND is_active = 1
        """, [supermarket_id] + current_titles)
        
        deactivated = cursor.rowcount
        conn.commit()
        conn.close()
        
        return deactivated

# ── UserDatabase — DB separada para usuarios (Railway Volume) ─────────────────
class UserDatabase:
    """
    Base de datos exclusiva para usuarios y métodos de pago.
    Se persiste en Railway Volume (/app/userdata/users.db) y NO se sobreescribe
    en cada deploy, a diferencia de promotions.db que viene del repo.
    """

    def __init__(self, db_path: str = None):
        self.db_path = str(db_path or config.USERS_DB_PATH)
        self._init()

    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init(self):
        conn = self._conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                telegram_chat_id TEXT,
                notify_daily BOOLEAN DEFAULT 1,
                notify_hour INTEGER DEFAULT 9,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS user_payment_methods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                entity_name TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                UNIQUE(user_id, entity_name)
            );
            CREATE TABLE IF NOT EXISTS password_resets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                token_hash TEXT NOT NULL UNIQUE,
                expires_at TIMESTAMP NOT NULL,
                used_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_password_resets_token ON password_resets(token_hash);
            CREATE INDEX IF NOT EXISTS idx_password_resets_user ON password_resets(user_id);
        """)
        conn.commit()
        conn.close()
        print(f"✅ Users DB inicializada: {self.db_path}")

    def create_user(self, email: str, password_hash: str) -> Optional[int]:
        conn = self._conn()
        try:
            cursor = conn.execute(
                "INSERT INTO users (email, password_hash) VALUES (?, ?)",
                (email.lower().strip(), password_hash),
            )
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            return None
        finally:
            conn.close()

    def get_user_by_email(self, email: str) -> Optional[Dict]:
        conn = self._conn()
        row = conn.execute(
            "SELECT * FROM users WHERE email = ?", (email.lower().strip(),)
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        conn = self._conn()
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def get_user_by_telegram_chat_id(self, chat_id: str) -> Optional[Dict]:
        conn = self._conn()
        row = conn.execute(
            "SELECT * FROM users WHERE telegram_chat_id = ?", (str(chat_id),)
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def link_telegram_chat_id(self, user_id: int, chat_id: str):
        """Vincula un chat_id a un user (sin tocar notify settings)."""
        conn = self._conn()
        conn.execute(
            "UPDATE users SET telegram_chat_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (str(chat_id), user_id),
        )
        conn.commit()
        conn.close()

    def update_user_telegram(self, user_id: int, telegram_chat_id: str,
                             notify_daily: bool, notify_hour: int):
        conn = self._conn()
        conn.execute(
            """UPDATE users
               SET telegram_chat_id = ?, notify_daily = ?, notify_hour = ?,
                   updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (telegram_chat_id or None, int(notify_daily), int(notify_hour), user_id),
        )
        conn.commit()
        conn.close()

    def set_user_payment_methods(self, user_id: int, methods: List[Dict]):
        conn = self._conn()
        conn.execute("DELETE FROM user_payment_methods WHERE user_id = ?", (user_id,))
        conn.executemany(
            "INSERT OR IGNORE INTO user_payment_methods (user_id, entity_name, entity_type) VALUES (?, ?, ?)",
            [(user_id, m["name"], m["type"]) for m in methods if m.get("name") and m.get("type")],
        )
        conn.commit()
        conn.close()

    def get_user_payment_methods(self, user_id: int) -> List[Dict]:
        conn = self._conn()
        rows = conn.execute(
            "SELECT entity_name AS name, entity_type AS type FROM user_payment_methods WHERE user_id = ?",
            (user_id,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_users_for_notification(self) -> List[Dict]:
        conn = self._conn()
        rows = conn.execute(
            "SELECT * FROM users WHERE telegram_chat_id IS NOT NULL AND notify_daily = 1"
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ── Password reset ────────────────────────────────────────────────────────
    def create_password_reset(self, user_id: int, token_hash: str, expires_at: str):
        """Inserta un nuevo password reset. expires_at es ISO timestamp."""
        conn = self._conn()
        conn.execute(
            "INSERT INTO password_resets (user_id, token_hash, expires_at) VALUES (?, ?, ?)",
            (user_id, token_hash, expires_at),
        )
        conn.commit()
        conn.close()

    def get_password_reset_by_token_hash(self, token_hash: str) -> Optional[Dict]:
        """Devuelve el reset si existe y NO está usado/vencido."""
        conn = self._conn()
        row = conn.execute(
            """SELECT * FROM password_resets
               WHERE token_hash = ?
                 AND used_at IS NULL
                 AND expires_at > CURRENT_TIMESTAMP""",
            (token_hash,),
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def mark_password_reset_used(self, reset_id: int):
        conn = self._conn()
        conn.execute(
            "UPDATE password_resets SET used_at = CURRENT_TIMESTAMP WHERE id = ?",
            (reset_id,),
        )
        conn.commit()
        conn.close()

    def update_user_password(self, user_id: int, new_password_hash: str):
        conn = self._conn()
        conn.execute(
            """UPDATE users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (new_password_hash, user_id),
        )
        conn.commit()
        conn.close()

    def count_recent_password_resets(self, user_id: int, within_seconds: int = 3600) -> int:
        """Cuenta resets pedidos por este user en las últimas N segundos (rate limit)."""
        conn = self._conn()
        row = conn.execute(
            """SELECT COUNT(*) AS c FROM password_resets
               WHERE user_id = ?
                 AND created_at > datetime('now', ?)""",
            (user_id, f'-{within_seconds} seconds'),
        ).fetchone()
        conn.close()
        return row["c"] if row else 0

    def get_promotions_for_user(self, user_id: int, today_only: bool = True) -> List[Dict]:
        """Promociones activas que coinciden con los métodos de pago del usuario.
        Lee desde promotions.db (separada)."""
        methods = self.get_user_payment_methods(user_id)
        if not methods:
            return []

        day_map = {
            "monday": "lunes", "tuesday": "martes", "wednesday": "miércoles",
            "thursday": "jueves", "friday": "viernes", "saturday": "sábado", "sunday": "domingo"
        }
        today_es = day_map.get(datetime.now().strftime("%A").lower(), "")

        entity_conditions = " OR ".join(
            ["(LOWER(p.bank) LIKE ? OR LOWER(p.wallet) LIKE ?)"] * len(methods)
        )
        entity_params: list = []
        for m in methods:
            entity_params.extend([f"%{m['name'].lower()}%", f"%{m['name'].lower()}%"])

        day_clause = ""
        day_params: list = []
        if today_only and today_es:
            today_es_norm = _strip_accents(today_es).lower()
            if today_es_norm != today_es:
                day_clause = ("AND (p.valid_days IS NULL OR p.valid_days = '' "
                              "OR LOWER(p.valid_days) LIKE ? OR LOWER(p.valid_days) LIKE ? "
                              "OR LOWER(p.valid_days) LIKE ?)")
                day_params = [f"%{today_es}%", f"%{today_es_norm}%", "%todos los d%"]
            else:
                day_clause = ("AND (p.valid_days IS NULL OR p.valid_days = '' "
                              "OR LOWER(p.valid_days) LIKE ? OR LOWER(p.valid_days) LIKE ?)")
                day_params = [f"%{today_es}%", "%todos los d%"]

        today_iso = datetime.now().date().isoformat()
        query = f"""
            SELECT p.id, p.title, p.discount, p.bank, p.wallet,
                   p.valid_days, p.store_types, p.tope, p.min_purchase,
                   p.acumulable, s.name AS supermarket_name
            FROM promotions p
            JOIN supermarkets s ON p.supermarket_id = s.id
            WHERE p.is_active = 1 AND ({entity_conditions}) {day_clause}
              AND (p.valid_until IS NULL OR p.valid_until = '' OR p.valid_until >= ?)
              AND (p.valid_from IS NULL OR p.valid_from = '' OR p.valid_from <= ?)
            ORDER BY s.name, p.discount DESC
        """
        # Lee desde promotions.db (distinta a esta DB de usuarios)
        promo_conn = sqlite3.connect(str(config.DATABASE_PATH))
        promo_conn.row_factory = sqlite3.Row
        rows = promo_conn.execute(
            query, entity_params + day_params + [today_iso, today_iso]
        ).fetchall()
        promo_conn.close()
        return [dict(r) for r in rows]


# Inicializar base de datos al importar
if __name__ == "__main__":
    db = Database()
    print("Base de datos inicializada correctamente")

