#!/usr/bin/env python3
"""
Scraper de Carrefour con scroll automático para lazy loading
"""
import asyncio
import re
import sys
from pathlib import Path
from typing import List, Dict
import random

# Ajustar path para imports
parent_dir = str(Path(__file__).parent.parent.absolute())
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

# Imports del proyecto
from database import Database
from terms_parser import TermsParser
from config import SUPERMARKETS

class CarrefourScrollScraper:
    def __init__(self):
        self.name = 'Carrefour'
        self.url = 'https://www.carrefour.com.ar/descuentos-bancarios'
        self.db = Database()
        self.terms_parser = TermsParser()
        
    async def scrape(self) -> List[Dict]:
        """Scraping con scroll progresivo"""
        print(f"\n🔍 Scraping {self.name} (con scroll automático)...")
        print(f"\n   🌐 URL: {self.url}")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=False,  # Visible para debug
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox'
                ]
            )
            
            try:
                context = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                )
                
                page = await context.new_page()
                
                # 1. Navegar a la página
                print(f"\n   📡 Navegando...")
                await page.goto(self.url, wait_until='domcontentloaded', timeout=30000)
                
                # 2. Esperar un poco para que inicie JavaScript
                await asyncio.sleep(3)
                
                # 3. SCROLL PROGRESIVO para activar lazy loading
                print(f"\n   📜 Haciendo scroll para cargar contenido...")
                await self._progressive_scroll(page)
                
                # 4. Verificar cuántos botones "Ver legal" hay ahora
                ver_legal_count = await page.locator('text=/ver\\s+legal/i').count()
                print(f"\n   ✅ Botones 'Ver legal' encontrados: {ver_legal_count}")
                
                if ver_legal_count < 5:
                    print(f"\n   ⚠️  Muy pocos botones encontrados. Esperando más...")
                    await asyncio.sleep(5)
                    ver_legal_count = await page.locator('text=/ver\\s+legal/i').count()
                    print(f"   ✅ Ahora hay: {ver_legal_count} botones")
                
                # 5. Expandir todos los "Ver legal"
                print(f"\n   📋 Expandiendo términos y condiciones...")
                expanded = await self._expand_all_terms(page)
                print(f"   ✅ Expandidos {expanded} términos")
                
                # 6. Esperar a que se carguen los términos
                await asyncio.sleep(2)
                
                # 7. Extraer HTML final
                html = await page.content()
                
                # 8. Guardar debug
                await page.screenshot(path='debug_scroll.png', full_page=True)
                with open('debug_scroll.html', 'w', encoding='utf-8') as f:
                    f.write(html)
                print(f"\n   📸 Debug guardado: debug_scroll.png, debug_scroll.html")
                
                # 9. Extraer promociones
                print(f"\n   🔍 Extrayendo promociones...")
                promotions = await self._extract_promotions(page, html)
                
                print(f"\n✅ {self.name}: {len(promotions)} promociones encontradas")
                
                # 10. Guardar en base de datos
                if promotions:
                    print(f"\n   💾 Guardando en base de datos...")
                    self._save_to_database(promotions)
                
                return promotions
                
            except Exception as e:
                print(f"\n   ❌ Error: {e}")
                import traceback
                traceback.print_exc()
                return []
            finally:
                await browser.close()
    
    async def _progressive_scroll(self, page):
        """Hace scroll progresivo hacia abajo"""
        # Obtener altura total
        scroll_height = await page.evaluate('document.body.scrollHeight')
        viewport_height = 1080
        
        # Scroll en pasos
        current = 0
        step = viewport_height // 2  # Medio viewport cada vez
        
        while current < scroll_height:
            await page.evaluate(f'window.scrollTo(0, {current})')
            await asyncio.sleep(0.5)  # Pausa para que cargue
            current += step
            
            # Recalcular altura (puede aumentar con lazy load)
            scroll_height = await page.evaluate('document.body.scrollHeight')
        
        # Scroll al final
        await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
        await asyncio.sleep(1)
        
        # Volver arriba
        await page.evaluate('window.scrollTo(0, 0)')
        await asyncio.sleep(1)
    
    async def _expand_all_terms(self, page) -> int:
        """Expande todos los botones 'Ver legal'"""
        try:
            # Buscar todos los botones que contienen "Ver legal" (case insensitive)
            buttons = page.locator('text=/ver\\s+legal/i')
            count = await buttons.count()
            
            # Click en cada uno
            for i in range(count):
                try:
                    await buttons.nth(i).click(timeout=1000)
                    await asyncio.sleep(0.2)
                except:
                    pass
            
            return count
        except Exception as e:
            print(f"      Error expandiendo términos: {e}")
            return 0
    
    async def _extract_promotions(self, page, html: str) -> List[Dict]:
        """Extrae las promociones del HTML"""
        soup = BeautifulSoup(html, 'html.parser')
        promotions = []
        
        # Estrategia 1: Buscar por clases VTEX identificadas
        # vtex-flex-layout-0-x-flexRow--rowCucardas tiene 10 elementos
        # Esto podría ser un contenedor de promociones
        
        promo_containers = soup.find_all('div', class_=re.compile(r'flexRow--rowCucardas'))
        print(f"      Contenedores flexRow--rowCucardas: {len(promo_containers)}")
        
        if promo_containers:
            for i, container in enumerate(promo_containers, 1):
                promo = await self._extract_from_container(container, soup)
                if promo:
                    promotions.append(promo)
                    print(f"         Promoción {i}: {promo.get('title', 'Sin título')[:60]}")
        
        # Estrategia 2: Buscar todas las imágenes y buscar promociones alrededor
        if not promotions:
            print(f"      Intentando estrategia alternativa por imágenes...")
            images = soup.find_all('img')
            print(f"      Total imágenes: {len(images)}")
            
            for img in images:
                # Buscar contenedor padre grande
                parent = img.parent
                for _ in range(5):
                    if parent and parent.name == 'div':
                        # Buscar si este contenedor tiene texto de descuento
                        text = parent.get_text()
                        if re.search(r'\d+\s*%', text) and len(text) < 500:
                            promo = self._extract_from_text_block(parent, img)
                            if promo and promo not in promotions:
                                promotions.append(promo)
                                break
                    parent = parent.parent if parent else None
        
        return promotions
    
    async def _extract_from_container(self, container, soup) -> Dict:
        """Extrae datos de un contenedor específico"""
        try:
            promo = {}
            
            # Buscar texto
            text = container.get_text(strip=True)
            
            # Extraer porcentaje
            percent_match = re.search(r'(\d+)\s*%', text)
            if percent_match:
                promo['discount'] = f"{percent_match.group(1)}%"
            
            # Buscar imagen
            img = container.find('img')
            if img:
                promo['image_url'] = img.get('src') or img.get('data-src', '')
            
            # Título: buscar en el texto
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            if lines:
                promo['title'] = lines[0][:200]
            
            # Buscar términos (bloques en mayúsculas cerca)
            terms = self._find_terms_near(container)
            if terms:
                promo['terms_raw'] = terms
                parsed = self.terms_parser.parse(terms)
                promo.update(parsed)
            
            promo['url'] = self.url
            
            return promo if promo.get('title') or promo.get('discount') else None
            
        except Exception as e:
            return None
    
    def _extract_from_text_block(self, block, img) -> Dict:
        """Extrae datos de un bloque de texto"""
        try:
            text = block.get_text(strip=True)
            
            promo = {
                'url': self.url,
                'image_url': img.get('src') or img.get('data-src', '')
            }
            
            # Porcentaje
            percent_match = re.search(r'(\d+)\s*%', text)
            if percent_match:
                promo['discount'] = f"{percent_match.group(1)}%"
            
            # Título
            lines = [line.strip() for line in text.split('\n') if line.strip() and len(line.strip()) > 10]
            if lines:
                promo['title'] = lines[0][:200]
            
            return promo if promo.get('title') or promo.get('discount') else None
            
        except:
            return None
    
    def _find_terms_near(self, element) -> str:
        """Busca términos y condiciones cerca de un elemento"""
        # Buscar hermanos o elementos cercanos con mucho texto en mayúsculas
        parent = element.parent
        if not parent:
            return ''
        
        # Buscar en hermanos
        for sibling in parent.find_next_siblings():
            text = sibling.get_text(strip=True)
            if len(text) > 200 and text.isupper():
                return text[:2000]
        
        # Buscar dentro del mismo elemento
        for child in element.find_all(recursive=True):
            text = child.get_text(strip=True)
            if len(text) > 200 and text.isupper():
                return text[:2000]
        
        return ''
    
    def _save_to_database(self, promotions: List[Dict]):
        """Guarda las promociones en la base de datos"""
        # Obtener/crear ID del supermercado
        supermarket_id = self.db.insert_supermarket(self.name, self.url)
        
        # Limpiar promociones anteriores de Carrefour
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM promotions WHERE supermarket_id = ?", (supermarket_id,))
        conn.commit()
        conn.close()
        
        print(f"      🗑️  Limpiadas promociones anteriores")
        
        # Insertar nuevas
        saved = 0
        for promo in promotions:
            if self.db.insert_promotion(supermarket_id, promo):
                saved += 1
        
        print(f"      ✅ Guardadas {saved} promociones")

async def main():
    scraper = CarrefourScrollScraper()
    promotions = await scraper.scrape()
    
    print(f"\n{'='*100}")
    print(f"\n📊 RESULTADOS: {len(promotions)} promociones")
    print(f"\n{'='*100}")
    
    if promotions:
        print(f"\n📋 Primeras 3 promociones:")
        for i, promo in enumerate(promotions[:3], 1):
            print(f"\n   {i}. {promo.get('title', 'Sin título')[:80]}")
            print(f"      Descuento: {promo.get('discount', 'N/A')}")
            print(f"      Banco: {promo.get('bank', 'N/A')}")

if __name__ == "__main__":
    asyncio.run(main())

