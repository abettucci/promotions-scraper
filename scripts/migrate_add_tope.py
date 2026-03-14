#!/usr/bin/env python3
"""
Script para agregar el campo 'tope' a la tabla promotions
"""
import sqlite3
import os

def migrate():
    db_path = 'promotions.db'
    
    if not os.path.exists(db_path):
        print(f"❌ No se encontró la base de datos: {db_path}")
        print("   Ejecuta primero el scraper para crear la base de datos.")
        return
    
    print("🔧 Migrando base de datos...")
    print(f"   Base de datos: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Verificar si la columna ya existe
        cursor.execute("PRAGMA table_info(promotions)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'tope' in columns:
            print("   ℹ️  El campo 'tope' ya existe")
        else:
            # Agregar la columna
            print("   ➕ Agregando campo 'tope'...")
            cursor.execute("ALTER TABLE promotions ADD COLUMN tope TEXT")
            conn.commit()
            print("   ✅ Campo 'tope' agregado exitosamente")
        
        # Verificar acumulable también
        if 'acumulable' not in columns:
            print("   ➕ Agregando campo 'acumulable'...")
            cursor.execute("ALTER TABLE promotions ADD COLUMN acumulable BOOLEAN")
            conn.commit()
            print("   ✅ Campo 'acumulable' agregado exitosamente")
        
        # Mostrar estructura final
        cursor.execute("PRAGMA table_info(promotions)")
        print("\n📋 Estructura de la tabla 'promotions':")
        for row in cursor.fetchall():
            col_id, name, col_type, notnull, default, pk = row
            print(f"   {col_id}. {name} ({col_type})")
        
        print("\n✅ Migración completada exitosamente")
        
    except Exception as e:
        print(f"❌ Error durante la migración: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()

