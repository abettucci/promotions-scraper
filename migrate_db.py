"""
Script de migración para agregar nuevas columnas a la base de datos
"""
import sqlite3
import config
from pathlib import Path

def migrate_database():
    """Migra la base de datos agregando las nuevas columnas"""
    db_path = config.DATABASE_PATH
    
    if not db_path.exists():
        print("No hay base de datos existente, no es necesario migrar.")
        return
    
    print(f"🔄 Migrando base de datos: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Obtener columnas existentes
    cursor.execute("PRAGMA table_info(promotions)")
    existing_columns = {row[1] for row in cursor.fetchall()}
    
    # Nuevas columnas a agregar
    new_columns = {
        'payment_method': 'TEXT',
        'store_types': 'TEXT',
        'valid_days': 'TEXT',
        'terms_raw': 'TEXT',
        'exclusions': 'TEXT',
        'requirements': 'TEXT'
    }
    
    # Agregar columnas que no existen
    for column_name, column_type in new_columns.items():
        if column_name not in existing_columns:
            try:
                cursor.execute(f"ALTER TABLE promotions ADD COLUMN {column_name} {column_type}")
                print(f"✅ Columna '{column_name}' agregada")
            except sqlite3.OperationalError as e:
                print(f"⚠️ Error agregando '{column_name}': {e}")
    
    conn.commit()
    conn.close()
    
    print("✅ Migración completada")

if __name__ == "__main__":
    migrate_database()

