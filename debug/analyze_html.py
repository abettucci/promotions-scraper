"""
Analiza el HTML descargado para entender su estructura
"""
import re
from bs4 import BeautifulSoup

def analyze_html():
    """Analiza el HTML guardado"""
    
    print("=" * 70)
    print("🔍 ANALIZANDO HTML DE CARREFOUR")
    print("=" * 70)
    print()
    
    try:
        # Intentar leer como texto
        try:
            with open('debug_carrefour_simple.html', 'r', encoding='utf-8') as f:
                html = f.read()
            print(f"✅ Archivo leído como texto: {len(html)} caracteres")
        except UnicodeDecodeError:
            # Si falla, es probablemente gzip
            print("⚠️  El archivo parece estar comprimido, intentando descomprimir...")
            import gzip
            with open('debug_carrefour_simple.html', 'rb') as f:
                html = gzip.decompress(f.read()).decode('utf-8')
            print(f"✅ Archivo descomprimido y leído: {len(html)} caracteres")
        
        print()
        
        # 1. Buscar texto literal "descuento" o "%"
        print("📊 1. BUSCANDO TEXTO 'DESCUENTO' Y PORCENTAJES:")
        print("-" * 70)
        
        descuento_count = len(re.findall(r'descuento', html, re.IGNORECASE))
        porcentaje_count = len(re.findall(r'\d+\s*%', html))
        
        print(f"   • Menciones de 'descuento': {descuento_count}")
        print(f"   • Porcentajes (##%): {porcentaje_count}")
        print()
        
        # Mostrar algunos ejemplos
        if porcentaje_count > 0:
            matches = list(re.finditer(r'.{0,50}\d+\s*%.{0,50}', html))[:5]
            print(f"   Ejemplos de porcentajes encontrados:")
            for i, match in enumerate(matches, 1):
                text = match.group(0).replace('\n', ' ').strip()
                print(f"   {i}. ...{text}...")
        print()
        
        # 2. Buscar scripts con datos JSON
        print("🔧 2. BUSCANDO DATOS EN JAVASCRIPT/JSON:")
        print("-" * 70)
        
        soup = BeautifulSoup(html, 'html.parser')
        scripts = soup.find_all('script')
        
        print(f"   • Total de tags <script>: {len(scripts)}")
        
        # Buscar scripts con datos
        json_scripts = []
        for script in scripts:
            script_text = script.string if script.string else ''
            if any(keyword in script_text for keyword in ['window.__', 'var ', 'const ', '{']):
                if len(script_text) > 100:
                    json_scripts.append(script_text)
        
        print(f"   • Scripts con posibles datos: {len(json_scripts)}")
        
        # Buscar específicamente window.__RUNTIME_CONFIG o similar
        runtime_patterns = [
            r'window\.__\w+\s*=\s*(\{.+?\});',
            r'window\.\w+\s*=\s*(\{.+?\});',
            r'var\s+\w+\s*=\s*(\{.+?\});',
        ]
        
        found_data = False
        for pattern in runtime_patterns:
            matches = re.findall(pattern, html, re.DOTALL)
            if matches:
                print(f"   • Encontrado patrón: {pattern[:30]}...")
                print(f"     Matches: {len(matches)}")
                found_data = True
                
                # Buscar si tiene "descuento" o "promo"
                for match in matches[:3]:
                    if 'descuento' in match.lower() or 'promo' in match.lower() or 'banco' in match.lower():
                        preview = match[:200].replace('\n', ' ')
                        print(f"     ✅ Contiene datos relevantes!")
                        print(f"        Preview: {preview}...")
                        break
        
        if not found_data:
            print(f"   ⚠️  No se encontraron objetos JavaScript obvios")
        print()
        
        # 3. Buscar divs/sections específicos
        print("📦 3. BUSCANDO CONTENEDORES HTML:")
        print("-" * 70)
        
        # Buscar por clases comunes
        common_classes = [
            'promo', 'promocion', 'descuento', 'banco', 'tarjeta',
            'card', 'item', 'offer', 'deal', 'discount'
        ]
        
        for cls in common_classes:
            elements = soup.find_all(class_=re.compile(cls, re.IGNORECASE))
            if elements:
                print(f"   • Elementos con clase '*{cls}*': {len(elements)}")
                if len(elements) <= 3:
                    for el in elements:
                        classes = el.get('class', [])
                        print(f"     - {el.name} class=\"{' '.join(classes)}\"")
        print()
        
        # 4. Buscar por data-attributes
        print("🏷️  4. BUSCANDO DATA ATTRIBUTES:")
        print("-" * 70)
        
        data_attrs = soup.find_all(attrs={'data-testid': True})
        print(f"   • Elementos con data-testid: {len(data_attrs)}")
        if data_attrs:
            testids = [el.get('data-testid') for el in data_attrs[:10]]
            for tid in set(testids):
                print(f"     - data-testid=\"{tid}\"")
        print()
        
        # 5. Buscar estructura de la página
        print("🏗️  5. ESTRUCTURA GENERAL:")
        print("-" * 70)
        
        body = soup.find('body')
        if body:
            # Contar elementos principales
            divs = body.find_all('div', recursive=False)
            sections = body.find_all('section')
            articles = body.find_all('article')
            
            print(f"   • DIVs principales: {len(divs)}")
            print(f"   • Sections: {len(sections)}")
            print(f"   • Articles: {len(articles)}")
            
            # Mostrar IDs de elementos principales
            main_ids = []
            for div in divs[:10]:
                div_id = div.get('id')
                if div_id:
                    main_ids.append(div_id)
            
            if main_ids:
                print(f"   • IDs principales: {', '.join(main_ids[:5])}")
        print()
        
        # 6. Buscar por texto específico
        print("🔎 6. BUSCANDO TEXTOS ESPECÍFICOS:")
        print("-" * 70)
        
        keywords = ['cuenta dni', 'banco', 'tarjeta', 'mercado pago', 'miércoles', 'promoción']
        for keyword in keywords:
            count = len(re.findall(keyword, html, re.IGNORECASE))
            if count > 0:
                print(f"   • '{keyword}': {count} menciones")
        print()
        
        # 7. Extraer un fragmento grande de texto visible
        print("📄 7. MUESTRA DE TEXTO VISIBLE:")
        print("-" * 70)
        
        # Obtener todo el texto visible
        all_text = soup.get_text(separator=' ', strip=True)
        all_text = re.sub(r'\s+', ' ', all_text)
        
        # Buscar sección con "descuento"
        if 'descuento' in all_text.lower():
            # Encontrar posición de "descuento" y extraer contexto
            match = re.search(r'.{0,200}descuento.{0,300}', all_text, re.IGNORECASE)
            if match:
                print(f"   Texto cerca de 'descuento':")
                print(f"   {match.group(0)}")
        else:
            # Mostrar primeros 500 caracteres
            print(f"   Primeros 500 caracteres del texto visible:")
            print(f"   {all_text[:500]}")
        print()
        
        # 8. RECOMENDACIONES
        print("=" * 70)
        print("💡 RECOMENDACIONES:")
        print("=" * 70)
        
        if porcentaje_count == 0 and descuento_count == 0:
            print("   ❌ No se encontró texto con 'descuento' o '%'")
            print("   → La página puede estar vacía o el contenido se carga dinámicamente")
            print("   → Necesitas usar Playwright para que JavaScript cargue el contenido")
        elif json_scripts:
            print("   ✅ Hay scripts JavaScript con datos")
            print("   → El contenido puede estar en formato JSON dentro de scripts")
            print("   → Puedo crear un parser para extraer esos datos")
        elif porcentaje_count > 0:
            print("   ✅ Hay porcentajes en el HTML")
            print("   → Los patrones regex necesitan ajuste")
            print("   → Puedo ajustar los selectores según la estructura")
        
        print()
        print("📝 ACCIÓN SUGERIDA:")
        print("   Envíame:")
        print("   1. Este output completo")
        print("   2. Las primeras 100 líneas del archivo debug_carrefour_simple.html")
        print("   3. O una captura del navegador mostrando la página")
        print()
        
    except FileNotFoundError:
        print("❌ Error: No se encuentra el archivo 'debug_carrefour_simple.html'")
        print("   Ejecuta primero: python test_simple_scraper.py")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    analyze_html()

