"""
Analiza el HTML final para encontrar la estructura correcta de las promociones
"""
from bs4 import BeautifulSoup
import re

def analyze():
    print("="*80)
    print("🔍 ANALIZANDO HTML RENDERIZADO")
    print("="*80)
    print()
    
    try:
        with open('debug_final.html', 'r', encoding='utf-8') as f:
            html = f.read()
        
        soup = BeautifulSoup(html, 'html.parser')
        
        print(f"✅ HTML leído: {len(html)} caracteres")
        print()
        
        # 1. Buscar todas las imágenes
        print("📸 1. IMÁGENES ENCONTRADAS:")
        print("-"*80)
        images = soup.find_all('img')
        print(f"   Total de imágenes: {len(images)}")
        
        # Buscar imágenes con descuento en el src o alt
        discount_images = []
        for img in images:
            alt = img.get('alt', '')
            src = img.get('src', '')
            data_src = img.get('data-src', '')
            
            if any(keyword in alt.lower() for keyword in ['descuento', '%', 'promo']) or \
               any(keyword in src.lower() for keyword in ['descuento', 'promo']):
                discount_images.append({
                    'alt': alt,
                    'src': src or data_src,
                    'parent_tag': img.parent.name if img.parent else 'none',
                    'parent_class': img.parent.get('class', []) if img.parent else []
                })
        
        print(f"   Imágenes relacionadas con descuentos: {len(discount_images)}")
        print()
        
        if discount_images:
            print("   Primeras 5 imágenes de descuentos:")
            for i, img in enumerate(discount_images[:5], 1):
                print(f"\n   {i}.")
                print(f"      Alt: {img['alt'][:80]}")
                print(f"      Src: {img['src'][:80]}")
                print(f"      Parent: <{img['parent_tag']}> class={img['parent_class'][:3]}")
        
        print()
        print()
        
        # 2. Buscar divs que contengan texto con porcentaje
        print("📦 2. DIVS CON PORCENTAJES:")
        print("-"*80)
        
        all_divs = soup.find_all('div')
        divs_with_percent = []
        
        for div in all_divs:
            text = div.get_text(strip=True)
            if re.search(r'\d+\s*%', text) and 'descuento' in text.lower():
                if len(text) < 1000:  # No queremos el div completo de la página
                    divs_with_percent.append({
                        'class': div.get('class', []),
                        'id': div.get('id', ''),
                        'text': text[:200]
                    })
        
        print(f"   DIVs con % y 'descuento': {len(divs_with_percent)}")
        
        if divs_with_percent:
            print("\n   Primeros 5 divs:")
            for i, div in enumerate(divs_with_percent[:5], 1):
                print(f"\n   {i}.")
                print(f"      Class: {div['class'][:3]}")
                print(f"      ID: {div['id']}")
                print(f"      Text: {div['text']}")
        
        print()
        print()
        
        # 3. Buscar por clases específicas
        print("🎨 3. CLASES RELEVANTES:")
        print("-"*80)
        
        # Obtener todas las clases únicas
        all_classes = set()
        for tag in soup.find_all(True):
            classes = tag.get('class', [])
            all_classes.update(classes)
        
        # Filtrar clases que parezcan relacionadas con promociones
        promo_classes = [c for c in all_classes if any(
            keyword in c.lower() for keyword in 
            ['promo', 'banco', 'card', 'descuento', 'discount', 'offer', 'deal']
        )]
        
        print(f"   Clases relacionadas con promociones: {len(promo_classes)}")
        for cls in sorted(promo_classes)[:15]:
            # Contar cuántos elementos tienen esta clase
            count = len(soup.find_all(class_=cls))
            print(f"      • {cls} ({count} elementos)")
        
        print()
        print()
        
        # 4. Buscar estructura de bloques
        print("🏗️  4. BUSCANDO BLOQUES DE PROMOCIONES:")
        print("-"*80)
        
        # Buscar el patrón: imagen + título + botón "Ver legal"
        ver_legal_buttons = soup.find_all(text=re.compile(r'ver\s+legal', re.IGNORECASE))
        print(f"   Botones 'Ver legal' encontrados: {len(ver_legal_buttons)}")
        
        if ver_legal_buttons:
            print("\n   Analizando estructura alrededor del primer 'Ver legal':")
            first_button = ver_legal_buttons[0]
            parent = first_button.parent
            
            # Subir hasta encontrar un div contenedor grande
            for i in range(5):
                if parent:
                    print(f"\n   Nivel {i}: <{parent.name}>")
                    print(f"      Class: {parent.get('class', [])[:3]}")
                    print(f"      ID: {parent.get('id', '')}")
                    
                    # Ver hermanos (siblings)
                    siblings = parent.find_all(recursive=False)
                    print(f"      Hijos directos: {len(siblings)}")
                    
                    parent = parent.parent
        
        print()
        print()
        
        # 5. Buscar texto de términos expandidos
        print("📋 5. TÉRMINOS Y CONDICIONES EXPANDIDOS:")
        print("-"*80)
        
        # Buscar bloques de texto en mayúsculas largos
        all_text = soup.get_text()
        upper_blocks = re.findall(r'[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s\d.,;:/()$%\-"\']{300,}', all_text)
        
        print(f"   Bloques de texto en mayúsculas (300+ chars): {len(upper_blocks)}")
        
        if upper_blocks:
            print("\n   Primer bloque de términos:")
            print(f"      {upper_blocks[0][:200]}...")
            
            # Buscar el elemento que contiene este texto
            first_terms = upper_blocks[0][:100]
            elements_with_terms = soup.find_all(text=re.compile(re.escape(first_terms[:50])))
            
            if elements_with_terms:
                elem = elements_with_terms[0]
                print(f"\n   Contenido en: <{elem.parent.name if elem.parent else 'unknown'}>")
                if elem.parent:
                    print(f"      Class: {elem.parent.get('class', [])}")
        
        print()
        print()
        
        # 6. RECOMENDACIÓN
        print("="*80)
        print("💡 RECOMENDACIÓN:")
        print("="*80)
        
        if len(discount_images) > 0:
            print(f"\n✅ Encontradas {len(discount_images)} imágenes de descuentos")
            print("   → Usar las imágenes como punto de partida")
            print(f"   → Parent tags: {set(img['parent_tag'] for img in discount_images)}")
            print(f"   → Parent classes comunes: {[c for img in discount_images for c in img['parent_class']][:10]}")
        
        if len(ver_legal_buttons) > 0:
            print(f"\n✅ Encontrados {len(ver_legal_buttons)} botones 'Ver legal'")
            print("   → Los términos se están expandiendo correctamente")
        
        if len(divs_with_percent) > 0:
            print(f"\n✅ Encontrados {len(divs_with_percent)} divs con porcentajes")
            print("   → Hay contenido visible con descuentos")
        
        print("\n📝 SIGUIENTE PASO:")
        print("   Envíame este output completo para ajustar el scraper")
        print()
        
    except FileNotFoundError:
        print("❌ No se encuentra el archivo 'debug_final.html'")
        print("   Primero ejecuta: python scrapers/carrefour_final.py")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    analyze()

