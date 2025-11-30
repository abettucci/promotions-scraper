"""
Extrae datos JSON de templates VTEX
"""
import re
import json
from bs4 import BeautifulSoup

def extract_vtex_data():
    """Extrae datos de templates VTEX"""
    
    print("=" * 70)
    print("🔍 EXTRAYENDO DATOS JSON DE TEMPLATES VTEX")
    print("=" * 70)
    print()
    
    try:
        with open('debug_carrefour_simple.html', 'r', encoding='utf-8') as f:
            html = f.read()
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # Buscar todos los templates con data-varname
        templates = soup.find_all('template', {'data-varname': True})
        
        print(f"✅ Encontrados {len(templates)} templates")
        print()
        
        runtime_data = {}
        
        for idx, template in enumerate(templates, 1):
            varname = template.get('data-varname')
            field = template.get('data-field', 'main')
            
            print(f"📦 Template {idx}: {varname}" + (f" (field: {field})" if field != 'main' else ''))
            
            # Obtener el contenido del script dentro del template
            script = template.find('script')
            if script and script.string:
                try:
                    data = json.loads(script.string)
                    
                    if varname == '__RUNTIME__':
                        if field not in runtime_data:
                            runtime_data[field] = data
                        else:
                            runtime_data[field].update(data)
                    
                    # Mostrar información sobre el contenido
                    if isinstance(data, dict):
                        print(f"   Tipo: dict con {len(data)} claves")
                        keys = list(data.keys())[:10]
                        print(f"   Claves: {', '.join(keys)}")
                        
                        # Buscar claves relacionadas con promociones/descuentos
                        promo_keys = [k for k in data.keys() if any(word in k.lower() for word in ['promo', 'descuento', 'banco', 'card', 'discount'])]
                        if promo_keys:
                            print(f"   🎯 Claves de interés: {', '.join(promo_keys)}")
                    elif isinstance(data, list):
                        print(f"   Tipo: list con {len(data)} elementos")
                    else:
                        print(f"   Tipo: {type(data).__name__}")
                    
                    print()
                    
                except json.JSONDecodeError as e:
                    print(f"   ⚠️ Error parseando JSON: {e}")
                    print(f"   Primeros 200 caracteres: {script.string[:200]}")
                    print()
        
        # Guardar runtime data completo
        if runtime_data:
            with open('debug_runtime_data.json', 'w', encoding='utf-8') as f:
                json.dump(runtime_data, f, indent=2, ensure_ascii=False)
            print(f"💾 Runtime data guardado en: debug_runtime_data.json")
            print()
        
        # Buscar específicamente tabs-banks-descuentos
        print("🔍 BUSCANDO ESPECÍFICAMENTE 'tabs-banks-descuentos'...")
        print("-" * 70)
        
        runtime_str = json.dumps(runtime_data, ensure_ascii=False)
        if 'tabs-banks-descuentos' in runtime_str:
            print("✅ Encontrado en runtime data!")
            
            # Extraer ese fragmento
            # Buscar en extensions
            if 'extensions' in runtime_data:
                extensions = runtime_data['extensions']
                if 'store.custom#tabs-banks-descuentos' in extensions:
                    tabs_data = extensions['store.custom#tabs-banks-descuentos']
                    print(f"   📊 Estructura encontrada:")
                    print(f"      Claves: {list(tabs_data.keys())}")
                    
                    with open('debug_tabs_banks.json', 'w', encoding='utf-8') as f:
                        json.dump(tabs_data, f, indent=2, ensure_ascii=False)
                    print(f"   💾 Guardado en: debug_tabs_banks.json")
        else:
            print("❌ No encontrado 'tabs-banks-descuentos' en runtime data")
        
        print()
        
        # Buscar cualquier mención de descuento en el JSON
        print("🔍 BUSCANDO MENCIONES DE 'DESCUENTO' EN EL JSON...")
        print("-" * 70)
        
        descuento_count = runtime_str.lower().count('descuento')
        print(f"   Menciones de 'descuento': {descuento_count}")
        
        if descuento_count > 0:
            # Encontrar fragmentos con descuento
            pattern = r'.{0,100}descuento.{0,100}'
            matches = re.findall(pattern, runtime_str, re.IGNORECASE)
            
            print(f"   Fragmentos encontrados: {len(matches)}")
            for i, match in enumerate(matches[:5], 1):
                clean = match.replace('\\n', ' ').replace('\\', '')
                print(f"   {i}. ...{clean}...")
        
        print()
        print("=" * 70)
        print("💡 CONCLUSIÓN:")
        print("=" * 70)
        
        if descuento_count == 0:
            print("❌ No hay datos de promociones en el HTML inicial")
            print("→ Las promociones se cargan dinámicamente con JavaScript")
            print("→ Necesitas usar Playwright para ejecutar JavaScript")
            print()
            print("🔧 ALTERNATIVA: Buscar si hay un endpoint API")
            print("→ Voy a buscar URLs de API en el HTML...")
            
            # Buscar URLs de API
            api_patterns = [
                r'https?://[^"\']+/api/[^"\']+',
                r'https?://[^"\']+graphql[^"\']+',
                r'/api/[^"\']+',
            ]
            
            for pattern in api_patterns:
                matches = re.findall(pattern, html)
                if matches:
                    print(f"\n   URLs encontradas ({pattern}):")
                    for url in set(matches)[:5]:
                        print(f"      • {url}")
        else:
            print("✅ Hay datos de promociones en el runtime data")
            print("→ Revisa los archivos JSON guardados para ver la estructura")
            print("→ Puedo crear un parser específico para esa estructura")
        
        print()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    extract_vtex_data()

