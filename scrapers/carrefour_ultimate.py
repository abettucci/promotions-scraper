#!/usr/bin/env python3
"""
Scraper ULTIMATE de Carrefour con todas las mejoras:
- Campo acumulable
- Extracción mejorada de fechas de vigencia
- Extracción mejorada de exclusiones
- Títulos completos
- Tarjeta/banco del título y T&C
"""
import asyncio
import re
import sys
from pathlib import Path
from typing import List, Dict
import json

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

class CarrefourUltimateScraper:
    def __init__(self):
        self.name = 'Carrefour'
        self.url = 'https://www.carrefour.com.ar/descuentos-bancarios'
        self.db = Database()
        self.terms_parser = TermsParser()
        
    async def scrape(self) -> List[Dict]:
        """Scraping ultimate"""
        print(f"\n🔍 Scraping {self.name} (versión ultimate)...")
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
                
                # 2. Esperar cards
                print(f"\n   ⏳ Esperando promociones...")
                await page.wait_for_selector('.valtech-carrefourar-bank-promotions-0-x-cardBox', timeout=15000)
                await asyncio.sleep(3)
                
                # 3. Scroll
                print(f"\n   📜 Haciendo scroll...")
                await self._scroll_page(page)
                
                # 4. Expandir "Ver legal"
                print(f"\n   📋 Expandiendo términos...")
                expanded = await self._expand_legal_terms(page)
                print(f"   ✅ Expandidos {expanded} términos")
                
                # 5. Esperar carga
                await asyncio.sleep(2)
                
                # 6. Obtener HTML
                html = await page.content()
                
                # 7. Debug
                await page.screenshot(path='debug_ultimate.png', full_page=True)
                with open('debug_ultimate.html', 'w', encoding='utf-8') as f:
                    f.write(html)
                print(f"\n   📸 Debug: debug_ultimate.png, debug_ultimate.html")
                
                # 8. Extraer
                print(f"\n   🔍 Extrayendo promociones...")
                promotions = self._extract_from_html(html)
                
                print(f"\n✅ {self.name}: {len(promotions)} promociones encontradas")
                
                # 9. Guardar
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
        """Extrae promociones del HTML"""
        soup = BeautifulSoup(html, 'html.parser')
        promotions = []
        
        # Buscar todos los cardBox
        card_boxes = soup.find_all('div', class_=re.compile(r'valtech-carrefourar-bank-promotions-0-x-cardBox'))
        
        print(f"      Cards encontradas: {len(card_boxes)}")
        
        for i, card in enumerate(card_boxes, 1):
            try:
                promo = self._extract_promotion_from_card(card)
                if promo:
                    promotions.append(promo)
                    bank_info = promo.get('bank') or promo.get('wallet') or promo.get('card_type', 'N/A')
                    vigencia = ''
                    if promo.get('valid_from') or promo.get('valid_until'):
                        vigencia = f" [{promo.get('valid_from', '')} → {promo.get('valid_until', '')}]"
                    print(f"         {i}. {promo.get('title', 'Sin título')[:45]}... - {bank_info}{vigencia}")
            except Exception as e:
                print(f"         ⚠️  Error en card {i}: {e}")
                continue
        
        return promotions
    
    def _extract_promotion_from_card(self, card) -> Dict:
        """Extrae datos de una card"""
        promo = {
            'url': self.url
        }
        
        # 1. Extraer fecha/días válidos del header
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
        
        # 4. Extraer imagen
        img_elem = card.find('img', class_=re.compile(r'valtech-carrefourar-bank-promotions.*Image'))
        if img_elem:
            img_src = img_elem.get('src', '')
            promo['image_url'] = img_src if img_src.startswith('http') else f"https://www.carrefour.com.ar{img_src}"
        
        # 5. Extraer título COMPLETO
        title_elem = card.find('span', class_=re.compile(r'ColRightTittle'))
        desc_elem = card.find('span', class_=re.compile(r'ColRightText'))
        
        title_parts = []
        if title_elem:
            title_parts.append(title_elem.get_text(strip=True))
        if desc_elem:
            desc_text = desc_elem.get_text(strip=True)
            if desc_text:
                title_parts.append(desc_text)
        
        if title_parts:
            promo['title'] = ' '.join(title_parts)
        
        # 6. Extraer términos y condiciones COMPLETOS
        terms_text = ''
        
        # Buscar en el footer (priorizar)
        card_footer = card.find('div', class_=re.compile(r'cardFooter'))
        if card_footer:
            # Opción 1: Buscar todos los párrafos y unirlos
            paragraphs = card_footer.find_all('p')
            terms_parts = []
            for p in paragraphs:
                text = p.get_text(' ', strip=True)  # Usar espacio como separador
                # Solo incluir si parece ser texto de términos (mayúsculas, largo)
                if len(text) > 50:
                    # Limpiar espacios múltiples
                    text = re.sub(r'\s+', ' ', text)
                    terms_parts.append(text)
            
            if terms_parts:
                # Unir todas las partes con espacio
                terms_text = ' '.join(terms_parts)
        
        # Si no encontramos en footer, buscar en todo el card
        if not terms_text or len(terms_text) < 200:
            # Buscar todo el texto del card y extraer bloques en mayúsculas largos
            all_text = card.get_text(' ', strip=True)
            # Patrón: texto largo en mayúsculas (al menos 300 caracteres)
            upper_blocks = re.findall(r'[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s\d.,;:/()$%\-"\']{300,}', all_text)
            if upper_blocks:
                # Tomar el bloque más largo
                terms_text = max(upper_blocks, key=len)
        
        # Limpiar el texto final
        if terms_text:
            # Remover espacios múltiples
            terms_text = re.sub(r'\s+', ' ', terms_text)
            # Remover saltos de línea duplicados
            terms_text = re.sub(r'\n+', ' ', terms_text)
            terms_text = terms_text.strip()
            
            promo['terms_raw'] = terms_text
            
            # Parsear términos con el parser mejorado
            parsed = self.terms_parser.parse(terms_text)
            
            # IMPORTANTE: Convertir listas a strings y agregar todos los campos
            for key, value in parsed.items():
                if key == 'raw_text':
                    continue  # No duplicar raw_text
                
                if isinstance(value, list):
                    promo[key] = ', '.join(str(v) for v in value) if value else ''
                elif isinstance(value, dict):
                    promo[key] = json.dumps(value)
                elif value is not None:
                    promo[key] = value
        
        # 7. Extraer banco/tarjeta del título, términos e imagen
        self._extract_payment_info(promo)
        
        # 8. Extraer tope del título si no está en los términos
        if not promo.get('tope'):
            promo['tope'] = self._extract_tope_from_title(promo.get('title', ''))
        
        # Validar que tengamos al menos título y descuento
        if not promo.get('title'):
            return None
        
        if not promo.get('discount'):
            return None
        
        return promo
    
    def _extract_payment_info(self, promo: Dict):
        """Extrae información de banco/tarjeta de múltiples fuentes"""
        combined_text = f"{promo.get('title', '')} {promo.get('terms_raw', '')}"
        combined_lower = combined_text.lower()
        
        # Inferir del nombre de imagen
        if promo.get('image_url'):
            img_name = promo['image_url'].lower()
            
            if 'cuenta_dni' in img_name or 'cuentadni' in img_name:
                promo['bank'] = 'Banco Provincia'
                promo['payment_method'] = 'Cuenta DNI'
            elif 'mercadopago' in img_name or 'mercado_pago' in img_name or 'mercado-pago' in img_name:
                promo['wallet'] = 'Mercado Pago'
            elif 'carrefour' in img_name and 'credito' in img_name:
                promo['bank'] = 'Banco de Servicios Financieros'
                promo['card_type'] = 'Tarjeta Mi Carrefour Crédito'
            elif 'carrefour' in img_name and 'prepaga' in img_name:
                promo['bank'] = 'Banco de Servicios Financieros'
                promo['card_type'] = 'Tarjeta Mi Carrefour Prepaga'
            elif 'visa' in img_name and 'mc' in img_name:
                promo['card_type'] = 'Visa, Mastercard'
            elif 'visa' in img_name:
                promo['card_type'] = 'Visa'
            elif 'mastercard' in img_name or '_mc' in img_name or 'mc.' in img_name:
                promo['card_type'] = 'Mastercard'
            elif 'bna' in img_name or 'nacion' in img_name:
                promo['bank'] = 'Banco Nación'
            elif 'club' in img_name and 'nacion' in img_name:
                promo['bank'] = 'Club La Nación'
            elif 'naranja' in img_name:
                promo['card_type'] = 'Naranja'
        
        # Extraer del texto si no tenemos info
        if not promo.get('bank') and not promo.get('wallet') and not promo.get('card_type'):
            if 'cuenta dni' in combined_lower or 'cuentadni' in combined_lower:
                promo['bank'] = 'Banco Provincia'
                promo['payment_method'] = 'Cuenta DNI'
            elif 'mercado pago' in combined_lower:
                promo['wallet'] = 'Mercado Pago'
            elif 'mi carrefour' in combined_lower or 'micarrefour' in combined_lower:
                promo['bank'] = 'Banco de Servicios Financieros'
                if 'crédito' in combined_lower or 'credito' in combined_lower:
                    promo['card_type'] = 'Tarjeta Mi Carrefour Crédito'
                elif 'prepaga' in combined_lower:
                    promo['card_type'] = 'Tarjeta Mi Carrefour Prepaga'
                elif 'digital' in combined_lower:
                    promo['card_type'] = 'Cuenta Digital Mi Carrefour'
            elif 'banco nación' in combined_lower or 'banco nacion' in combined_lower or 'bna' in combined_lower:
                promo['bank'] = 'Banco Nación'
            elif 'club la nación' in combined_lower or 'club la nacion' in combined_lower:
                promo['bank'] = 'Club La Nación'
            elif 'visa' in combined_lower and 'mastercard' in combined_lower:
                promo['card_type'] = 'Visa, Mastercard'
            elif 'mastercard' in combined_lower:
                promo['card_type'] = 'Mastercard'
            elif 'visa' in combined_lower:
                promo['card_type'] = 'Visa'
            elif 'naranja' in combined_lower:
                promo['card_type'] = 'Naranja'
            elif 'modo' in combined_lower:
                promo['payment_method'] = 'MODO'
        
        # Extraer tarjeta del título usando regex
        if not promo.get('card_type'):
            title_text = promo.get('title', '')
            
            # "con tarjeta X" o "pagando con X"
            match = re.search(r'(?:con\s+tarjeta[s]?\s+(?:de\s+)?(?:crédito|débito|prepaga)?\s+)([A-Za-záéíóúñÁ-Ú\s]+?)(?:\s|$|crédito|débito)', title_text, re.IGNORECASE)
            if match:
                card_name = match.group(1).strip()
                if card_name and len(card_name) > 2:
                    promo['card_type'] = card_name.title()
            
            if not promo.get('card_type'):
                match = re.search(r'pagando\s+con\s+([A-Za-záéíóúñÁ-Ú\s]+?)(?:\s+(?:en|$|tope|sin))', title_text, re.IGNORECASE)
                if match:
                    card_name = match.group(1).strip()
                    if card_name and len(card_name) > 2:
                        promo['card_type'] = card_name.title()
    
    def _extract_tope_from_title(self, title: str) -> str:
        """Extrae el tope del título"""
        if not title:
            return ''
        
        title_upper = title.upper()
        
        # Buscar "SIN TOPE"
        if re.search(r'SIN\s+TOPE', title_upper):
            return 'SIN TOPE'
        
        # Patrones para tope en el título
        tope_patterns = [
            r'TOPE[:\s]+\$?\s*(\d+[\d.,]*)',
            r'TOPE\s+(?:DE\s+)?(?:DEVOLUCIÓN|DEVOLUCION|REINTEGRO)[:\s]+\$?\s*(\d+[\d.,]*)',
            r'TOPE\s+(?:SEMANAL|MENSUAL|DIARIO)[:\s]+\$?\s*(\d+[\d.,]*)',
            r'\$\s*(\d+[\d.,]*)\s+TOPE',
        ]
        
        for pattern in tope_patterns:
            match = re.search(pattern, title_upper)
            if match:
                amount = match.group(1).replace('.', '').replace(',', '.')
                try:
                    amount_num = float(amount)
                    return f"${amount_num:,.0f}".replace(',', '.')
                except:
                    return f"${amount}"
        
        return ''
    
    def _save_promotions(self, promotions: List[Dict]):
        """Guarda las promociones"""
        # Obtener/crear ID
        supermarket_id = self.db.insert_supermarket(self.name, self.url)
        
        # Limpiar anteriores
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM promotions WHERE supermarket_id = ?", (supermarket_id,))
        conn.commit()
        conn.close()
        
        print(f"      🗑️  Limpiadas promociones anteriores")
        
        # Insertar nuevas
        saved = 0
        errors = 0
        for i, promo in enumerate(promotions, 1):
            try:
                # IMPORTANTE: Asegurarse de que TODOS los campos son strings/primitivos
                cleaned_promo = {}
                for key, value in promo.items():
                    if isinstance(value, list):
                        cleaned_promo[key] = ', '.join(str(v) for v in value) if value else ''
                    elif isinstance(value, dict):
                        cleaned_promo[key] = json.dumps(value)
                    else:
                        cleaned_promo[key] = value
                
                if self.db.insert_promotion(supermarket_id, cleaned_promo):
                    saved += 1
            except Exception as e:
                errors += 1
                print(f"         ⚠️  Error guardando promoción {i}: {e}")
        
        print(f"      ✅ Guardadas {saved} promociones")
        if errors:
            print(f"      ⚠️  {errors} errores al guardar")

async def main():
    scraper = CarrefourUltimateScraper()
    promotions = await scraper.scrape()
    
    print(f"\n{'='*100}")
    print(f"\n📊 RESULTADOS: {len(promotions)} promociones")
    print(f"\n{'='*100}")
    
    if promotions:
        print(f"\n📋 Primeras 3 promociones con detalles completos:")
        for i, promo in enumerate(promotions[:3], 1):
            print(f"\n   {i}. {promo.get('title', 'Sin título')}")
            print(f"      💰 Descuento: {promo.get('discount', 'N/A')}")
            print(f"      🏦 Banco: {promo.get('bank', 'N/A')}")
            print(f"      💳 Tarjeta: {promo.get('card_type', 'N/A')}")
            print(f"      📱 Wallet: {promo.get('wallet', 'N/A')}")
            print(f"      🏪 Tiendas: {promo.get('store_types', 'N/A')}")
            print(f"      📅 Días: {promo.get('valid_days', 'N/A')}")
            print(f"      ⏰ Vigencia: {promo.get('valid_from', 'N/A')} → {promo.get('valid_until', 'N/A')}")
            print(f"      💵 Tope: {promo.get('tope', 'N/A')}")
            print(f"      🔁 Acumulable: {promo.get('acumulable', 'N/A')}")
            
            exclusions = promo.get('exclusions', '')
            if exclusions:
                print(f"      ⛔ Exclusiones: {exclusions[:80]}...")
            
            requirements = promo.get('requirements', '')
            if requirements:
                print(f"      ✅ Requisitos: {requirements[:80]}...")

if __name__ == "__main__":
    asyncio.run(main())

