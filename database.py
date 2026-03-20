"""
Gestión de base de datos SQLite
"""
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional
import json
import config

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
        
        # Tabla de supermercados
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS supermarkets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                url TEXT NOT NULL,
                last_scraped TIMESTAMP,
                scrape_count INTEGER DEFAULT 0,
                enabled BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
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
                promotion_id INTEGER NOT NULL,
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

        conn.commit()
        conn.close()

        print(f"✅ Base de datos inicializada: {self.db_path}")
    
    def insert_supermarket(self, name: str, url: str) -> int:
        """Inserta o actualiza un supermercado"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO supermarkets (name, url)
            VALUES (?, ?)
            ON CONFLICT(name) DO UPDATE SET url=excluded.url
        """, (name, url))
        
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
                promo_data.get('title', ''),
                promo_data.get('discount', ''),
                promo_data.get('bank', ''),
                promo_data.get('wallet', ''),
                promo_data.get('card_type', ''),
                promo_data.get('payment_method', ''),
                store_types,
                promo_data.get('valid_days', ''),
                promo_data.get('valid_from'),
                promo_data.get('valid_until'),
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
                """, (supermarket_id, promo_data.get('title', ''), promo_data.get('bank', ''))).fetchone()
                
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
        """Inserta términos y condiciones"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO terms_conditions
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

# Inicializar base de datos al importar
if __name__ == "__main__":
    db = Database()
    print("Base de datos inicializada correctamente")

