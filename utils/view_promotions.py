"""
Script para visualizar las promociones de la base de datos de forma amigable
"""
import sqlite3
from datetime import datetime
from pathlib import Path
import config

def print_separator(char="=", length=120):
    """Imprime una línea separadora"""
    print(char * length)

def truncate(text, length=50):
    """Trunca texto si es muy largo"""
    if not text:
        return "N/A"
    text = str(text)
    return text if len(text) <= length else text[:length-3] + "..."

def format_date(date_str):
    """Formatea fecha de forma amigable"""
    if not date_str:
        return "N/A"
    try:
        date = datetime.strptime(date_str, "%Y-%m-%d")
        return date.strftime("%d/%m/%Y")
    except:
        return date_str

def view_promotions(limit=None, supermarket=None, show_full=False):
    """
    Muestra las promociones de la base de datos
    
    Args:
        limit: Número máximo de promociones a mostrar
        supermarket: Filtrar por supermercado
        show_full: Mostrar todos los campos (incluyendo términos completos)
    """
    
    db_path = config.DATABASE_PATH
    
    if not db_path.exists():
        print("❌ No se encontró la base de datos en:", db_path)
        print("   Ejecuta el scraper primero para crear la base de datos")
        return
    
    # Conectar a la base de datos
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Construir query
    query = """
        SELECT 
            p.id,
            s.name as supermarket,
            p.title,
            p.discount,
            p.bank,
            p.wallet,
            p.payment_method,
            p.store_types,
            p.valid_days,
            p.valid_from,
            p.valid_until,
            p.terms_raw,
            p.exclusions,
            p.requirements,
            p.tope,
            p.acumulable,
            p.scraped_at,
            p.is_active
        FROM promotions p
        JOIN supermarkets s ON p.supermarket_id = s.id
        WHERE p.is_active = 1
    """
    
    params = []
    
    if supermarket:
        query += " AND s.name LIKE ?"
        params.append(f"%{supermarket}%")
    
    query += " ORDER BY p.scraped_at DESC"
    
    if limit:
        query += f" LIMIT {limit}"
    
    cursor.execute(query, params)
    promotions = cursor.fetchall()
    
    # Obtener estadísticas
    cursor.execute("SELECT COUNT(*) FROM promotions WHERE is_active = 1")
    total_active = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(DISTINCT supermarket_id) FROM promotions WHERE is_active = 1")
    total_supermarkets = cursor.fetchone()[0]
    
    conn.close()
    
    # Mostrar header
    print()
    print_separator("=")
    print(f"{'🛒 PROMOCIONES BANCARIAS':^120}")
    print_separator("=")
    print(f"📊 Total activas: {total_active} | 🏪 Supermercados: {total_supermarkets} | 📋 Mostrando: {len(promotions)}")
    print_separator("=")
    print()
    
    if not promotions:
        print("❌ No se encontraron promociones")
        if supermarket:
            print(f"   (con filtro: {supermarket})")
        return
    
    # Mostrar cada promoción
    for idx, promo in enumerate(promotions, 1):
        print(f"\n{'='*120}")
        print(f"📌 PROMOCIÓN #{promo['id']} - {promo['supermarket']}")
        print(f"{'='*120}")
        
        print(f"\n  📝 Título:        {promo['title']}")
        print(f"  💰 Descuento:     {promo['discount'] or 'N/A'}")
        
        # Método de pago
        payment_info = []
        if promo['bank']:
            payment_info.append(f"🏦 {promo['bank']}")
        if promo['wallet']:
            payment_info.append(f"💳 {promo['wallet']}")
        if promo['payment_method']:
            payment_info.append(f"💵 {promo['payment_method']}")
        
        if payment_info:
            print(f"  💸 Pago:          {' | '.join(payment_info)}")
        
        # Tiendas y días
        if promo['store_types']:
            print(f"  🏪 Tiendas:       {promo['store_types']}")
        if promo['valid_days']:
            print(f"  📅 Días válidos:  {promo['valid_days']}")
        
        # Fechas
        if promo['valid_from'] or promo['valid_until']:
            date_from = format_date(promo['valid_from'])
            date_until = format_date(promo['valid_until'])
            print(f"  ⏰ Vigencia:      {date_from} → {date_until}")
        
        # Tope
        if promo['tope']:
            print(f"  💵 Tope:          {promo['tope']}")
        
        # Exclusiones (sin truncar, pero con saltos de línea si es muy largo)
        if promo['exclusions']:
            exclusions_text = promo['exclusions']
            if len(exclusions_text) <= 90:
                print(f"  ⛔ Exclusiones:   {exclusions_text}")
            else:
                # Primera línea con los primeros 90 caracteres
                print(f"  ⛔ Exclusiones:   {exclusions_text[:90]}...")
                # Continuar en líneas adicionales si show_full
                if show_full and len(exclusions_text) > 90:
                    remaining = exclusions_text[90:]
                    print(f"                    {remaining}")
        
        # Requisitos (sin truncar completamente)
        if promo['requirements']:
            requirements_text = promo['requirements']
            if len(requirements_text) <= 90:
                print(f"  ✅ Requisitos:    {requirements_text}")
            else:
                print(f"  ✅ Requisitos:    {requirements_text[:90]}...")
                if show_full and len(requirements_text) > 90:
                    remaining = requirements_text[90:]
                    print(f"                    {remaining}")
        
        # Acumulable
        if promo['acumulable'] is not None:
            acumulable_text = "✅ Sí" if promo['acumulable'] else "❌ No"
            print(f"  🔁 Acumulable:    {acumulable_text}")
        
        # Términos y condiciones (sin truncar tanto)
        if promo['terms_raw']:
            if show_full:
                print(f"\n  📋 Términos y Condiciones:")
                print(f"  {'-'*116}")
                # Imprimir con indentación
                for line in promo['terms_raw'].split('\n'):
                    if line.strip():
                        print(f"  {line[:116]}")
            else:
                # Mostrar hasta 150 caracteres en lugar de 80
                terms_text = promo['terms_raw']
                if len(terms_text) <= 90:
                    print(f"  📋 T&C:           {terms_text}")
                else:
                    print(f"  📋 T&C:           {terms_text[:90]}...")
        
        # Metadata
        scraped = datetime.strptime(promo['scraped_at'], "%Y-%m-%d %H:%M:%S")
        print(f"\n  🕐 Scrapeado:     {scraped.strftime('%d/%m/%Y %H:%M')}")
        
        # Separador entre promociones
        if idx < len(promotions):
            print()
    
    print()
    print_separator("=")
    print(f"{'FIN - Mostrando ' + str(len(promotions)) + ' promociones':^120}")
    print_separator("=")
    print()

def view_statistics():
    """Muestra estadísticas generales"""
    db_path = config.DATABASE_PATH
    
    if not db_path.exists():
        print("❌ No se encontró la base de datos")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print()
    print_separator("=")
    print(f"{'📊 ESTADÍSTICAS':^120}")
    print_separator("=")
    print()
    
    # Por supermercado
    cursor.execute("""
        SELECT 
            s.name,
            COUNT(p.id) as total_promos,
            COUNT(CASE WHEN p.is_active = 1 THEN 1 END) as activas,
            MAX(s.last_scraped) as ultimo_scrape
        FROM supermarkets s
        LEFT JOIN promotions p ON s.id = p.supermarket_id
        GROUP BY s.id
        ORDER BY activas DESC
    """)
    
    print("🏪 Por Supermercado:")
    print("-" * 120)
    print(f"{'Supermercado':<30} {'Total':<15} {'Activas':<15} {'Último Scrape':<30}")
    print("-" * 120)
    
    for row in cursor.fetchall():
        name, total, activas, last_scraped = row
        last_scraped_str = last_scraped or "Nunca"
        if last_scraped:
            try:
                dt = datetime.strptime(last_scraped, "%Y-%m-%d %H:%M:%S")
                last_scraped_str = dt.strftime("%d/%m/%Y %H:%M")
            except:
                pass
        
        print(f"{name:<30} {total:<15} {activas:<15} {last_scraped_str:<30}")
    
    print()
    
    # Por banco/billetera
    print("💳 Por Medio de Pago:")
    print("-" * 120)
    
    cursor.execute("""
        SELECT 
            COALESCE(bank, wallet, 'Sin especificar') as payment,
            COUNT(*) as cantidad
        FROM promotions
        WHERE is_active = 1
        GROUP BY payment
        ORDER BY cantidad DESC
        LIMIT 10
    """)
    
    for row in cursor.fetchall():
        payment, cantidad = row
        print(f"  • {payment:<40} {cantidad} promociones")
    
    print()
    
    # Por descuento
    print("💰 Top Descuentos:")
    print("-" * 120)
    
    cursor.execute("""
        SELECT 
            discount,
            COUNT(*) as cantidad
        FROM promotions
        WHERE is_active = 1 AND discount IS NOT NULL AND discount != ''
        GROUP BY discount
        ORDER BY cantidad DESC
        LIMIT 10
    """)
    
    for row in cursor.fetchall():
        discount, cantidad = row
        print(f"  • {discount:<20} {cantidad} promociones")
    
    print()
    print_separator("=")
    print()
    
    conn.close()

def main():
    """Función principal con menú interactivo"""
    while True:
        print()
        print_separator("=")
        print(f"{'🗄️  VISUALIZADOR DE PROMOCIONES':^120}")
        print_separator("=")
        print()
        print("  1. Ver todas las promociones")
        print("  2. Ver últimas N promociones")
        print("  3. Ver promociones de un supermercado")
        print("  4. Ver promociones con detalles completos")
        print("  5. Ver estadísticas")
        print("  6. Salir")
        print()
        
        choice = input("Selecciona una opción (1-6): ").strip()
        
        if choice == "1":
            print()
            view_promotions()
            input("\nPresiona Enter para continuar...")
        
        elif choice == "2":
            try:
                limit = int(input("\n¿Cuántas promociones quieres ver? "))
                print()
                view_promotions(limit=limit)
                input("\nPresiona Enter para continuar...")
            except ValueError:
                print("❌ Número inválido")
        
        elif choice == "3":
            supermarket = input("\n¿Qué supermercado? (ej: Carrefour, Coto, etc.): ").strip()
            print()
            view_promotions(supermarket=supermarket)
            input("\nPresiona Enter para continuar...")
        
        elif choice == "4":
            try:
                limit = int(input("\n¿Cuántas promociones quieres ver? "))
                print()
                view_promotions(limit=limit, show_full=True)
                input("\nPresiona Enter para continuar...")
            except ValueError:
                print("❌ Número inválido")
        
        elif choice == "5":
            print()
            view_statistics()
            input("\nPresiona Enter para continuar...")
        
        elif choice == "6":
            print("\n👋 ¡Hasta luego!\n")
            break
        
        else:
            print("\n❌ Opción inválida")

if __name__ == "__main__":
    import sys
    
    # Si se pasan argumentos, usar modo no interactivo
    if len(sys.argv) > 1:
        if sys.argv[1] == "stats":
            view_statistics()
        elif sys.argv[1] == "all":
            view_promotions()
        elif sys.argv[1].isdigit():
            view_promotions(limit=int(sys.argv[1]))
        else:
            print("Uso:")
            print("  python view_promotions.py           # Menú interactivo")
            print("  python view_promotions.py all       # Ver todas")
            print("  python view_promotions.py 10        # Ver últimas 10")
            print("  python view_promotions.py stats     # Ver estadísticas")
    else:
        # Menú interactivo
        main()

