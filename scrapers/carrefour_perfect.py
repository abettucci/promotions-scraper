#!/usr/bin/env python3
"""
Scraper perfecto de Carrefour usando las clases VTEX reales
"""
import asyncio
import re
import sys
from pathlib import Path
from typing import List, Dict
import time

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

class CarrefourPerfectScraper:
    def __init__(self):
        self.name = 'Carrefour'
        self.url = 'https://www.carrefour.com.ar/descuentos-bancarios'
        self.db = Database()
        self.terms_parser = TermsParser()
        
    async def scrape(self) -> List[Dict]:
        """Scraping perfecto usando clases VTEX reales"""
        print(f"\n🔍 Scraping {self.name} (versión perfecta)...")
        print(f"\n   🌐 URL: {self.url}")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            
            try:
                context = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                )
                
                page = await context.new_page()
                
                # 1. Navegar
                print(f"\n   📡 Navegando...")
                await page.goto(self.url, wait_until='domcontentloaded', timeout=30000)
                
                # 2. Esperar a que aparezcan las cards
                print(f"\n   ⏳ Esperando promociones...")
                await page.wait_for_selector('.valtech-carrefourar-bank-promotions-0-x-cardBox', timeout=15000)
                await asyncio.sleep(3)
                
                # 3. Scroll para lazy loading
                print(f"\n   📜 Haciendo scroll...")
                await self._scroll_page(page)
                
                # 4. Expandir todos los "Ver legal"
                print(f"\n   📋 Expandiendo términos...")
                expanded = await self._expand_legal_terms(page)
                print(f"   ✅ Expandidos {expanded} términos")
                
                # 5. Esperar que se carguen los términos
                await asyncio.sleep(2)
                
                # 6. Obtener HTML final
                html = await page.content()
                
                # 7. Debug
                await page.screenshot(path='debug_perfect.png', full_page=True)
                with open('debug_perfect.html', 'w', encoding='utf-8') as f:
                    f.write(html)
                print(f"\n   📸 Debug: debug_perfect.png, debug_perfect.html")
                
                # 8. Extraer promociones
                print(f"\n   🔍 Extrayendo promociones...")
                promotions = self._extract_from_html(html)
                
                print(f"\n✅ {self.name}: {len(promotions)} promociones encontradas")
                
                # 9. Guardar en BD
                if promotions:
                    print(f"\n   💾 Guardando en base de datos...")
                    self._save_promotions(promotions)
                
                return promotions
                
            except Exception as e:
                print(f"\n   ❌ Error: {e}")
                import traceback
                traceback.print_exc()
                return []
            finally:
                await browser.close()
    
    async def _scroll_page(self, page):
        """Scroll progresivo"""
        for i in range(3):
            await page.evaluate(f'window.scrollBy(0, {500 * (i + 1)})')
            await asyncio.sleep(0.5)
        await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
        await asyncio.sleep(1)
    
    async def _expand_legal_terms(self, page) -> int:
        """Expande todos los términos legales"""
        try:
            buttons = page.locator('.valtech-carrefourar-bank-promotions-0-x-legalHeader')
            count = await buttons.count()
            
            for i in range(count):
                try:
                    await buttons.nth(i).click(timeout=1000)
                    await asyncio.sleep(0.1)
                except:
                    pass
            
            return count
        except Exception as e:
            print(f"      Error expandiendo: {e}")
            return 0
    
    def _extract_from_html(self, html: str) -> List[Dict]:
        """Extrae promociones del HTML usando las clases VTEX"""
        soup = BeautifulSoup(html, 'html.parser')
        promotions = []
        
        # Buscar todos los cardBox (cada uno es una promoción)
        card_boxes = soup.find_all('div', class_=re.compile(r'valtech-carrefourar-bank-promotions-0-x-cardBox'))
        
        print(f"      Cards encontradas: {len(card_boxes)}")
        
        for i, card in enumerate(card_boxes, 1):
            try:
                promo = self._extract_promotion_from_card(card)
                if promo:
                    promotions.append(promo)
                    print(f"         {i}. {promo.get('title', 'Sin título')[:60]}... [{promo.get('discount', 'N/A')}]")
            except Exception as e:
                print(f"         ⚠️ Error en card {i}: {e}")
                continue
        
        return promotions
    
    def _extract_promotion_from_card(self, card) -> Dict:
        """Extrae datos de una card individual"""
        promo = {
            'url': self.url
        }
        
        # 1. Extraer fecha/días válidos
        date_elem = card.find('span', class_=re.compile(r'dateText'))
        if date_elem:
            promo['valid_days'] = date_elem.get_text(strip=True)
        
        # 2. Extraer tipos de tienda
        store_icons = card.find_all('div', class_=re.compile(r'logoIcon'))
        store_types = []
        for icon in store_icons:
            class_list = icon.get('class', [])
            for cls in class_list:
                if 'logoMain' in cls:
                    store_types.append('Hipermercado')
                elif 'logoMarket' in cls:
                    store_types.append('Market')
                elif 'logoExpress' in cls:
                    store_types.append('Express')
                elif 'logoMaxi' in cls:
                    store_types.append('Maxi')
                elif 'logoOnline' in cls:
                    store_types.append('Online')
        if store_types:
            promo['store_types'] = ', '.join(set(store_types))
        
        # 3. Extraer porcentaje/descuento
        percentage_elem = card.find('span', class_=re.compile(r'ColLeftPercentage'))
        symbol_elem = card.find('span', class_=re.compile(r'ColLeftPercentageSymbol'))
        
        if percentage_elem and symbol_elem:
            percentage = percentage_elem.get_text(strip=True)
            symbol = symbol_elem.get_text(strip=True)
            promo['discount'] = f"{percentage}{symbol}"
        
        # 4. Extraer imagen (para identificar el banco)
        img_elem = card.find('img', class_=re.compile(r'valtech-carrefourar-bank-promotions.*Image'))
        if img_elem:
            img_src = img_elem.get('src', '')
            promo['image_url'] = img_src if img_src.startswith('http') else f"https://www.carrefour.com.ar{img_src}"
            
            # Inferir banco del nombre de imagen
            img_name = img_src.lower()
            if 'cuenta_dni' in img_name or 'cuentadni' in img_name:
                promo['bank'] = 'Banco Provincia'
                promo['payment_method'] = 'Cuenta DNI'
            elif 'mercadopago' in img_name or 'mercado_pago' in img_name:
                promo['bank'] = 'Mercado Pago'
                promo['wallet'] = 'Mercado Pago'
            elif 'carrefour' in img_name and 'credito' in img_name:
                promo['bank'] = 'Banco de Servicios Financieros'
                promo['card_type'] = 'Tarjeta Mi Carrefour Crédito'
            elif 'visa' in img_name:
                promo['card_type'] = 'Visa'
            elif 'mastercard' in img_name or '_mc' in img_name:
                promo['card_type'] = 'Mastercard'
            elif 'bna' in img_name or 'nacion' in img_name:
                promo['bank'] = 'Banco Nación'
            elif 'club' in img_name and 'nacion' in img_name:
                promo['bank'] = 'Club La Nación'
        
        # 5. Extraer título
        title_elem = card.find('span', class_=re.compile(r'ColRightTittle'))
        if title_elem:
            promo['title'] = title_elem.get_text(strip=True)
        
        # 6. Extraer texto descriptivo
        desc_elem = card.find('span', class_=re.compile(r'ColRightText'))
        if desc_elem:
            desc_text = desc_elem.get_text(strip=True)
            # Agregar al título si es corto
            if desc_text and len(desc_text) < 100:
                if promo.get('title'):
                    promo['title'] = f"{promo['title']} {desc_text}"
                else:
                    promo['title'] = desc_text
        
        # 7. Extraer términos y condiciones
        legal_elem = card.find('div', class_=re.compile(r'legalContent'))
        if legal_elem:
            terms_text = legal_elem.get_text(strip=True)
            if terms_text and len(terms_text) > 50:
                promo['terms_raw'] = terms_text
                
                # Parsear términos para extraer info estructurada
                parsed = self.terms_parser.parse(terms_text)
                promo.update(parsed)
        
        # 8. Si no tenemos banco, intentar extraerlo del título o términos
        if not promo.get('bank') and not promo.get('wallet'):
            title_lower = promo.get('title', '').lower()
            terms_lower = promo.get('terms_raw', '').lower()
            combined = f"{title_lower} {terms_lower}"
            
            if 'cuenta dni' in combined or 'cuentadni' in combined:
                promo['bank'] = 'Banco Provincia'
                promo['payment_method'] = 'Cuenta DNI'
            elif 'mercado pago' in combined:
                promo['wallet'] = 'Mercado Pago'
            elif 'mi carrefour' in combined or 'micarrefour' in combined:
                promo['bank'] = 'Banco de Servicios Financieros'
                if 'crédito' in combined or 'credito' in combined:
                    promo['card_type'] = 'Tarjeta Mi Carrefour Crédito'
                elif 'prepaga' in combined:
                    promo['card_type'] = 'Tarjeta Mi Carrefour Prepaga'
            elif 'banco nación' in combined or 'banco nacion' in combined or 'bna' in combined:
                promo['bank'] = 'Banco Nación'
            elif 'club la nación' in combined or 'club la nacion' in combined:
                promo['bank'] = 'Club La Nación'
            elif 'mastercard' in combined:
                promo['card_type'] = 'Mastercard'
            elif 'visa' in combined:
                promo['card_type'] = 'Visa'
            elif 'modo' in combined:
                promo['payment_method'] = 'MODO'
        
        # Validar que tengamos al menos título y descuento
        if not promo.get('title'):
            return None
        
        if not promo.get('discount'):
            return None
        
        return promo
    
    def _save_promotions(self, promotions: List[Dict]):
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
        errors = 0
        for promo in promotions:
            try:
                if self.db.insert_promotion(supermarket_id, promo):
                    saved += 1
            except Exception as e:
                errors += 1
                print(f"         ⚠️ Error guardando: {e}")
        
        print(f"      ✅ Guardadas {saved} promociones")
        if errors:
            print(f"      ⚠️ {errors} errores al guardar")

async def main():
    scraper = CarrefourPerfectScraper()
    promotions = await scraper.scrape()
    
    print(f"\n{'='*100}")
    print(f"\n📊 RESULTADOS: {len(promotions)} promociones")
    print(f"\n{'='*100}")
    
    if promotions:
        print(f"\n📋 Primeras 5 promociones:")
        for i, promo in enumerate(promotions[:5], 1):
            print(f"\n   {i}. {promo.get('title', 'Sin título')[:80]}")
            print(f"      💰 Descuento: {promo.get('discount', 'N/A')}")
            print(f"      🏦 Banco: {promo.get('bank', 'N/A')}")
            print(f"      💳 Tarjeta: {promo.get('card_type', 'N/A')}")
            print(f"      📱 Wallet: {promo.get('wallet', 'N/A')}")
            print(f"      🏪 Tiendas: {promo.get('store_types', 'N/A')}")
            print(f"      📅 Días: {promo.get('valid_days', 'N/A')}")

if __name__ == "__main__":
    asyncio.run(main())

