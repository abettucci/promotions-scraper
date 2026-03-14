"""
Script para resetear y recrear la base de datos desde cero
"""
import os
import config
from database import Database

def reset_database():
    """Elimina y recrea la base de datos"""
    db_path = config.DATABASE_PATH
    
    # Eliminar base de datos existente
    if db_path.exists():
        print(f"🗑️  Eliminando base de datos existente: {db_path}")
        os.remove(db_path)
        print("   ✅ Base de datos eliminada")
    else:
        print("ℹ️  No existe base de datos previa")
    
    # Crear nueva base de datos
    print("\n🔧 Creando nueva base de datos...")
    db = Database()
    
    # Verificar que se creó correctamente
    print("\n✅ Base de datos creada exitosamente")
    print(f"📂 Ubicación: {db_path}")
    
    # Mostrar esquema
    print("\n📋 Verificando esquema de la tabla 'promotions'...")
    conn = db.get_connection()
    cursor = conn.cursor()
    
    cursor.execute("PRAGMA table_info(promotions)")
    columns = cursor.fetchall()
    
    print("\n   Columnas:")
    for col in columns:
        print(f"   • {col[1]:20} {col[2]}")
    
    conn.close()
    
    print("\n✅ Proceso completado. La base de datos está lista para usar.")

if __name__ == "__main__":
    reset_database()

