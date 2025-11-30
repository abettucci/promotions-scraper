"""
Scraper de Carrefour usando Playwright con espera inteligente
En lugar de esperar networkidle, esperamos elementos específicos
"""
from typing import List, Dict
from playwright.async_api import async_playwright, Page
import asyncio
import re

class CarrefourPlaywrightV2:
    def __init__(self):
        self.name = 'Carrefour'
        self.url = 'https://www.carrefour.com.ar/descuentos-bancarios'
    
    async def scrape(self) -> List[Dict]:
        """Scrape con Playwright esperando elementos específicos"""
        promotions = []
        
        async with async_playwright() as p:
            print(f"🔍 Scraping {self.name} con Playwright v2...")
            print(f"   🌐 URL: {self.url}")
            
            # Lanzar navegador
            browser = await p.chromium.launch(
                headless=False,  # Visual para debug
                args=['--disable-blink-features=AutomationControlled']
            )
            
            try:
                page = await browser.new_page(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                )
                
                # Navegar SIN esperar networkidle (solo básico)
                print(f"   📡 Navegando (sin esperar networkidle)...")
                try:
                    await page.goto(self.url, wait_until='domcontentloaded', timeout=30000)
                    print(f"   ✅ DOM cargado")
                except Exception as e:
                    print(f"   ⚠️  Error en goto: {e}")
                    return []
                
                # Esperar un poco para que JavaScript inicie
                print(f"   ⏳ Esperando 5 segundos para JavaScript...")
                await asyncio.sleep(5)
                
                # Hacer scroll para activar lazy loading
                print(f"   📜 Scrolling...")
                for i in range(5):
                    await page.evaluate('window.scrollBy(0, window.innerHeight * 0.5)')
                    await asyncio.sleep(0.5)
                
                # Esperar más tiempo para que carguen las promociones
                print(f"   ⏳ Esperando 10 segundos más para que carguen promociones...")
                await asyncio.sleep(10)
                
                # Buscar elementos de promociones - intentar varios selectores
                print(f"   🔍 Buscando elementos de promociones...")
                
                selectors_to_try = [
                    'div[class*="promo"]',
                    'div[class*="banco"]',
                    'div[class*="descuento"]',
                    '[class*="BanksPromotions"]',
                    '[class*="dynamicTabs"]',
                    'img[alt*="descuento"]',
                    'img[alt*="%"]',
                ]
                
                found_elements = False
                for selector in selectors_to_try:
                    try:
                        elements = await page.query_selector_all(selector)
                        if elements:
                            print(f"   ✅ Encontrados {len(elements)} elementos con selector: {selector}")
                            found_elements = True
                            break
                    except:
                        pass
                
                if not found_elements:
                    print(f"   ⚠️  No se encontraron elementos específicos de promociones")
                
                # Guardar screenshot
                print(f"   📸 Guardando screenshot...")
                await page.screenshot(path='debug_playwright_v2.png', full_page=True)
                
                # Obtener todo el HTML después de que JavaScript ejecutó
                html_content = await page.content()
                print(f"   📄 HTML después de JS: {len(html_content)} caracteres")
                
                # Guardar HTML
                with open('debug_playwright_v2.html', 'w', encoding='utf-8') as f:
                    f.write(html_content)
                print(f"   💾 HTML guardado en: debug_playwright_v2.html")
                
                # Extraer promociones del HTML renderizado
                promotions = await self._extract_from_rendered_html(page, html_content)
                
                print(f"✅ {self.name}: {len(promotions)} promociones encontradas")
                
            except Exception as e:
                print(f"❌ Error: {e}")
                import traceback
                traceback.print_exc()
            finally:
                # Esperar antes de cerrar para poder ver
                print(f"\n⏸️  Esperando 5 segundos antes de cerrar (para debug)...")
                await asyncio.sleep(5)
                await browser.close()
        
        return promotions
    
    async def _extract_from_rendered_html(self, page: Page, html: str) -> List[Dict]:
        """Extrae promociones del HTML renderizado"""
        promotions = []
        
        try:
            # Método 1: Buscar en el HTML renderizado con regex
            print(f"\n   🔍 Método 1: Buscando con regex en HTML renderizado...")
            
            # Buscar imágenes con alt que contenga descuento o %
            img_pattern = r'<img[^>]+alt="([^"]*(?:descuento|%)[^"]*)"[^>]+src="([^"]+)"'
            img_matches = re.findall(img_pattern, html, re.IGNORECASE)
            
            print(f"      Imágenes con descuento: {len(img_matches)}")
            
            for alt, src in img_matches[:10]:
                print(f"         • {alt[:50]}...")
                
                # Extraer descuento del alt
                discount_match = re.search(r'(\d+)\s*%', alt)
                discount = discount_match.group(0) if discount_match else ''
                
                promotions.append({
                    'title': alt,
                    'discount': discount,
                    'image_url': src,
                    'url': self.url,
                    'bank': None,
                    'wallet': None,
                    'card_type': None,
                    'payment_method': None,
                    'store_types': None,
                    'valid_days': None,
                    'terms_raw': '',
                    'exclusions': None,
                    'requirements': None,
                    'valid_from': None,
                    'valid_until': None,
                })
            
            # Método 2: Usar JavaScript en el navegador para extraer
            print(f"\n   🔍 Método 2: Extrayendo con JavaScript en el navegador...")
            
            js_promos = await page.evaluate("""() => {
                const results = [];
                
                // Buscar todos los elementos que puedan ser promociones
                const allElements = document.querySelectorAll('*');
                
                allElements.forEach(el => {
                    const text = el.textContent || '';
                    
                    // Si el elemento tiene texto con % y descuento
                    if (text.length > 10 && text.length < 500 &&
                        /\\d+\\s*%/.test(text) &&
                        /descuento|promo|banco|tarjeta/i.test(text)) {
                        
                        // Buscar imagen dentro del elemento
                        const img = el.querySelector('img');
                        const imgSrc = img ? (img.src || img.getAttribute('data-src')) : '';
                        const imgAlt = img ? img.alt : '';
                        
                        results.push({
                            text: text.substring(0, 200),
                            imageUrl: imgSrc,
                            imageAlt: imgAlt,
                            classes: el.className
                        });
                    }
                });
                
                return results;
            }""")
            
            print(f"      Elementos con JS: {len(js_promos)}")
            
            for idx, promo in enumerate(js_promos[:10], 1):
                print(f"         {idx}. {promo['text'][:50]}...")
            
            # Si JavaScript encontró más, usarlos
            if len(js_promos) > len(promotions):
                promotions = []
                for promo in js_promos:
                    text = promo['text']
                    
                    # Extraer descuento
                    discount_match = re.search(r'(\d+)\s*%', text)
                    discount = discount_match.group(0) if discount_match else ''
                    
                    # Título
                    lines = [l.strip() for l in text.split('\n') if l.strip()]
                    title = lines[0] if lines else text[:100]
                    
                    promotions.append({
                        'title': title,
                        'discount': discount,
                        'image_url': promo['imageUrl'],
                        'url': self.url,
                        'bank': None,
                        'wallet': None,
                        'card_type': None,
                        'payment_method': None,
                        'store_types': None,
                        'valid_days': None,
                        'terms_raw': text,
                        'exclusions': None,
                        'requirements': None,
                        'valid_from': None,
                        'valid_until': None,
                    })
            
        except Exception as e:
            print(f"   ⚠️  Error extrayendo: {e}")
            import traceback
            traceback.print_exc()
        
        return promotions

async def main():
    scraper = CarrefourPlaywrightV2()
    promotions = await scraper.scrape()
    
    print(f"\n{'='*70}")
    print(f"📊 RESULTADOS: {len(promotions)} promociones")
    print(f"{'='*70}\n")
    
    for idx, promo in enumerate(promotions, 1):
        print(f"📌 Promoción {idx}:")
        print(f"   Título: {promo['title'][:80]}")
        print(f"   Descuento: {promo['discount']}")
        print(f"   Imagen: {promo['image_url'][:80] if promo['image_url'] else 'N/A'}...")
        print()
    
    if promotions:
        save = input("\n💾 ¿Guardar en la base de datos? (s/n): ").strip().lower()
        if save == 's':
            import sys
            import os
            # Agregar el directorio padre al path
            parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            sys.path.insert(0, parent_dir)
            
            from database import Database
            from terms_parser import TermsParser
            import config
            
            db = Database()
            parser = TermsParser()
            
            supermarket_id = db.insert_supermarket('Carrefour', scraper.url)
            
            for promo in promotions:
                promotion_id = db.insert_promotion(supermarket_id, promo)
                if promotion_id and promo.get('terms_raw'):
                    terms_data = parser.parse(promo['terms_raw'])
                    db.insert_terms(promotion_id, terms_data)
            
            db.update_supermarket_scraped(supermarket_id)
            print(f"✅ {len(promotions)} promociones guardadas")

if __name__ == "__main__":
    asyncio.run(main())

