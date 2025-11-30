"""
Script de debug para Carrefour scraper
"""
import asyncio
from playwright.async_api import async_playwright
import re

async def debug_carrefour():
    """Debug del scraper de Carrefour"""
    url = 'https://www.carrefour.com.ar/descuentos-bancarios'
    
    print(f"🔍 Analizando: {url}")
    print("=" * 60)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        try:
            # Navegar
            print("📡 Navegando...")
            response = await page.goto(url, wait_until='networkidle', timeout=60000)
            print(f"✅ Status: {response.status}")
            print(f"✅ URL final: {page.url}")
            
            # Esperar
            await asyncio.sleep(3)
            
            # Obtener título de la página
            title = await page.title()
            print(f"📄 Título: {title}")
            
            # Scroll
            print("\n🔄 Scrolling...")
            for i in range(5):
                await page.evaluate("window.scrollBy(0, window.innerHeight * 0.5)")
                await asyncio.sleep(0.5)
            
            await asyncio.sleep(2)
            
            # Buscar elementos con "Ver legal"
            print("\n🔍 Buscando botones 'Ver legal'...")
            legal_buttons = await page.query_selector_all('button, a, div[role="button"]')
            print(f"   Total de botones/enlaces: {len(legal_buttons)}")
            
            ver_legal_count = 0
            for button in legal_buttons[:30]:
                try:
                    text = await button.text_content()
                    if text and 'ver legal' in text.lower():
                        ver_legal_count += 1
                        print(f"   ✓ Encontrado: '{text.strip()}'")
                except:
                    pass
            
            print(f"\n📊 Total 'Ver legal' encontrados: {ver_legal_count}")
            
            # Intentar extraer contenido
            print("\n🔍 Extrayendo contenido de la página...")
            content = await page.content()
            
            # Buscar promociones en el contenido
            discount_matches = re.findall(r'(\d+)\s*%\s*(?:de\s*)?descuento', content, re.IGNORECASE)
            print(f"📊 Descuentos encontrados: {len(set(discount_matches))}")
            for discount in set(discount_matches)[:5]:
                print(f"   • {discount}%")
            
            # Buscar menciones de bancos/billeteras
            banks_wallets = ['banco', 'tarjeta', 'cuenta dni', 'mercado pago', 'ualá']
            print(f"\n🏦 Buscando métodos de pago...")
            for item in banks_wallets:
                count = len(re.findall(item, content, re.IGNORECASE))
                if count > 0:
                    print(f"   • '{item}': {count} menciones")
            
            # Buscar T&C
            print(f"\n📋 Buscando términos y condiciones...")
            tc_matches = re.findall(r'PROMOCIÓN[A-ZÁÉÍÓÚÑ\s]{50,}', content, re.IGNORECASE)
            print(f"   T&C encontrados: {len(tc_matches)}")
            
            # Screenshot
            print(f"\n📸 Guardando screenshot...")
            await page.screenshot(path='debug_carrefour_screenshot.png', full_page=True)
            print(f"   ✅ Screenshot guardado: debug_carrefour_screenshot.png")
            
            # Guardar HTML
            print(f"\n💾 Guardando HTML...")
            with open('debug_carrefour_page.html', 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"   ✅ HTML guardado: debug_carrefour_page.html")
            
            # Intentar evaluar JavaScript
            print(f"\n🧪 Probando evaluación JavaScript...")
            try:
                result = await page.evaluate("""() => {
                    const divs = document.querySelectorAll('div');
                    const promoElements = [];
                    
                    divs.forEach(el => {
                        const text = el.textContent || '';
                        if (/\\d+%/.test(text) && /descuento/i.test(text)) {
                            promoElements.push({
                                text: text.substring(0, 200),
                                hasDiscount: true
                            });
                        }
                    });
                    
                    return {
                        totalDivs: divs.length,
                        promoElements: promoElements.length,
                        samples: promoElements.slice(0, 3)
                    };
                }""")
                print(f"   ✅ Evaluación exitosa")
                print(f"   Total DIVs: {result.get('totalDivs', 0)}")
                print(f"   Elementos con promoción: {result.get('promoElements', 0)}")
            except Exception as e:
                print(f"   ❌ Error en evaluación: {e}")
            
            print("\n" + "=" * 60)
            print("✅ Debug completado. Presiona Enter para cerrar...")
            input()
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(debug_carrefour())

