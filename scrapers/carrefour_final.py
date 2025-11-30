"""
Scraper final de Carrefour - Versión corregida
- Identifica contenedores únicos de promociones
- Extrae términos completos desde "Ver legal"
- Sin duplicaciones
"""
from playwright.async_api import async_playwright
import asyncio
import re
from typing import List, Dict

class CarrefourFinalScraper:
    def __init__(self):
        self.name = 'Carrefour'
        self.url = 'https://www.carrefour.com.ar/descuentos-bancarios'
    
    async def scrape(self) -> List[Dict]:
        """Scrape con identificación correcta de promociones únicas"""
        promotions = []
        
        async with async_playwright() as p:
            print(f"🔍 Scraping {self.name} (versión final)...")
            print(f"   🌐 URL: {self.url}")
            
            browser = await p.chromium.launch(headless=False)
            
            try:
                page = await browser.new_page(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                )
                
                # Navegar
                print(f"   📡 Navegando...")
                await page.goto(self.url, wait_until='domcontentloaded', timeout=30000)
                
                # Esperar y scroll
                print(f"   ⏳ Esperando carga de JavaScript...")
                await asyncio.sleep(8)
                
                for i in range(5):
                    await page.evaluate('window.scrollBy(0, window.innerHeight * 0.7)')
                    await asyncio.sleep(1)
                
                print(f"   ⏳ Esperando más contenido...")
                await asyncio.sleep(5)
                
                # Expandir TODOS los "Ver legal"
                print(f"   📋 Expandiendo términos y condiciones...")
                expanded = await page.evaluate("""() => {
                    let count = 0;
                    // Buscar todos los botones/enlaces con "Ver legal"
                    const buttons = Array.from(document.querySelectorAll('button, a, span, div'));
                    
                    buttons.forEach(btn => {
                        const text = btn.textContent || '';
                        if (text.toLowerCase().includes('ver legal') || 
                            text.toLowerCase().includes('ver términos')) {
                            try {
                                btn.click();
                                count++;
                            } catch (e) {}
                        }
                    });
                    
                    return count;
                }""")
                
                print(f"   ✅ Expandidos {expanded} términos")
                await asyncio.sleep(3)
                
                # Extraer promociones únicas
                print(f"   🔍 Extrayendo promociones únicas...")
                promotions = await self._extract_unique_promotions(page)
                
                # Screenshots
                await page.screenshot(path='debug_final.png', full_page=True)
                html = await page.content()
                with open('debug_final.html', 'w', encoding='utf-8') as f:
                    f.write(html)
                
                print(f"   📸 Screenshots guardados: debug_final.png, debug_final.html")
                print(f"✅ {self.name}: {len(promotions)} promociones encontradas")
                
            finally:
                await asyncio.sleep(3)
                await browser.close()
        
        return promotions
    
    async def _extract_unique_promotions(self, page) -> List[Dict]:
        """Extrae promociones únicas identificando contenedores correctos"""
        
        # Primero, identificar los contenedores principales de promociones
        promo_containers = await page.evaluate("""() => {
            const results = [];
            
            // Estrategia: Buscar divs que tengan:
            // 1. Un porcentaje de descuento grande (en imagen o texto)
            // 2. Un título descriptivo
            // 3. Texto de términos (después de expandir)
            
            // Buscar por estructura visual: divs que contengan imagen con descuento + texto
            const allDivs = document.querySelectorAll('div');
            const seen = new Set();
            
            allDivs.forEach(div => {
                // Verificar si este div tiene una imagen con descuento
                const img = div.querySelector('img[alt*="%"], img[alt*="descuento"]');
                if (!img) return;
                
                const imgAlt = img.alt || '';
                if (!imgAlt.includes('%') && !imgAlt.toLowerCase().includes('descuento')) return;
                
                // Buscar el título (generalmente un h2, h3, p o span cercano)
                const possibleTitles = div.querySelectorAll('h1, h2, h3, h4, h5, h6, p, span');
                let title = '';
                
                for (const el of possibleTitles) {
                    const text = el.textContent?.trim() || '';
                    // El título suele tener "descuento" y algún detalle
                    if (text.length > 15 && text.length < 200 && 
                        text.toLowerCase().includes('descuento')) {
                        title = text;
                        break;
                    }
                }
                
                if (!title) {
                    // Si no hay título descriptivo, usar el alt de la imagen
                    title = imgAlt;
                }
                
                // Evitar duplicados por título
                const titleKey = title.toLowerCase().replace(/\\s+/g, ' ').trim();
                if (seen.has(titleKey)) return;
                seen.add(titleKey);
                
                // Buscar términos y condiciones (texto en MAYÚSCULAS largo)
                let terms = '';
                const allText = div.textContent || '';
                
                // Buscar bloques de texto en mayúsculas
                const upperBlocks = allText.match(/[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\\s\\d.,;:/()$%\\-"']{200,}/g);
                if (upperBlocks && upperBlocks.length > 0) {
                    // Tomar el bloque más largo
                    terms = upperBlocks.reduce((a, b) => a.length > b.length ? a : b, '');
                }
                
                // Extraer descuento del título o imagen
                const discountMatch = (title + ' ' + imgAlt).match(/(\\d+)\\s*%/);
                const discount = discountMatch ? discountMatch[1] + '%' : '';
                
                // Extraer días válidos
                const daysMatch = allText.match(/(?:todos\\s+los|los)\\s+(lunes|martes|miércoles|jueves|viernes|sábado|domingo|miercoles|sabado)/i);
                const validDays = daysMatch ? daysMatch[0] : '';
                
                // Extraer tipos de tienda del título o términos
                const storeTypes = [];
                const fullText = title + ' ' + terms;
                if (/carrefour\\s*market/i.test(fullText)) storeTypes.push('Carrefour Market');
                if (/carrefour\\s*express/i.test(fullText)) storeTypes.push('Carrefour Express');
                if (/carrefour\\s*maxi/i.test(fullText)) storeTypes.push('Carrefour Maxi');
                if (/hipermercado/i.test(fullText)) storeTypes.push('Hipermercado Carrefour');
                if (/carrefour\\.com/i.test(fullText)) storeTypes.push('Carrefour.com.ar');
                
                // Extraer banco/billetera
                let bank = null;
                let wallet = null;
                
                const textLower = fullText.toLowerCase();
                
                // Bancos
                const banks = {
                    'galicia': 'Banco Galicia',
                    'santander': 'Santander',
                    'bbva': 'BBVA',
                    'macro': 'Macro',
                    'icbc': 'ICBC',
                    'provincia': 'Banco Provincia',
                    'nacion': 'Banco Nación',
                    'patagonia': 'Banco Patagonia',
                    'supervielle': 'Supervielle',
                    'frances': 'Banco Francés',
                    'itau': 'Itaú',
                };
                
                for (const [key, value] of Object.entries(banks)) {
                    if (textLower.includes(key)) {
                        bank = value;
                        break;
                    }
                }
                
                // Billeteras
                const wallets = {
                    'cuenta dni': 'Cuenta DNI',
                    'mercado pago': 'Mercado Pago',
                    'ualá': 'Ualá',
                    'uala': 'Ualá',
                    'naranja x': 'Naranja X',
                    'modo': 'MODO',
                    'personal pay': 'Personal Pay',
                };
                
                for (const [key, value] of Object.entries(wallets)) {
                    if (textLower.includes(key)) {
                        wallet = value;
                        break;
                    }
                }
                
                // Detectar tarjetas (Visa, Mastercard, etc)
                let cardType = null;
                if (/mastercard/i.test(fullText)) cardType = 'Mastercard';
                else if (/visa/i.test(fullText)) cardType = 'Visa';
                else if (/american\\s*express|amex/i.test(fullText)) cardType = 'American Express';
                
                // Extraer fechas
                const dateMatch = allText.match(/(?:hasta|válido hasta)\\s+(?:el\\s+)?(\\d{1,2})[/\\-](\\d{1,2})[/\\-](\\d{2,4})/i);
                let validUntil = null;
                if (dateMatch) {
                    const day = dateMatch[1].padStart(2, '0');
                    const month = dateMatch[2].padStart(2, '0');
                    let year = dateMatch[3];
                    if (year.length === 2) year = '20' + year;
                    validUntil = `${year}-${month}-${day}`;
                }
                
                results.push({
                    title: title.trim(),
                    discount: discount,
                    terms: terms.trim(),
                    imageUrl: img.src || '',
                    imageAlt: imgAlt,
                    validDays: validDays,
                    storeTypes: storeTypes,
                    bank: bank,
                    wallet: wallet,
                    cardType: cardType,
                    validUntil: validUntil
                });
            });
            
            return results;
        }""")
        
        print(f"      Contenedores únicos encontrados: {len(promo_containers)}")
        
        # Procesar y estructurar
        promotions = []
        for idx, promo in enumerate(promo_containers, 1):
            print(f"      {idx}. {promo['title'][:60]}...")
            
            # Limpiar título (a veces viene duplicado)
            title = promo['title']
            # Si el título está duplicado, tomar solo la primera parte
            title_parts = title.split(promo['discount'])
            if len(title_parts) > 2:
                # Está duplicado, reconstruir
                title = promo['discount'] + title_parts[-1]
            
            title = re.sub(r'\s+', ' ', title).strip()
            
            promotions.append({
                'title': title,
                'discount': promo['discount'],
                'bank': promo['bank'],
                'wallet': promo['wallet'],
                'card_type': promo['cardType'],
                'payment_method': None,
                'store_types': ', '.join(promo['storeTypes']) if promo['storeTypes'] else None,
                'valid_days': promo['validDays'] or None,
                'url': self.url,
                'image_url': promo['imageUrl'],
                'terms_raw': promo['terms'],
                'exclusions': self._extract_exclusions(promo['terms']),
                'requirements': self._extract_requirements(promo['terms']),
                'valid_from': None,
                'valid_until': promo['validUntil'],
            })
        
        return promotions
    
    def _extract_exclusions(self, terms: str) -> str:
        """Extrae exclusiones de los términos"""
        if not terms:
            return None
        
        exclusions = []
        patterns = [
            r'NO\s+VALID[OA]\s+(?:PARA|EN)\s+([^.]+)',
            r'EXCLU(?:YE|IDOS?)\s+([^.]+)',
            r'NO\s+APLICA\s+(?:PARA|A|EN)\s+([^.]+)',
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, terms, re.IGNORECASE)
            for match in matches:
                exclusion = match.group(1).strip()
                if exclusion and len(exclusion) > 5:
                    exclusions.append(exclusion[:200])
        
        return '; '.join(exclusions[:5]) if exclusions else None
    
    def _extract_requirements(self, terms: str) -> str:
        """Extrae requisitos de los términos"""
        if not terms:
            return None
        
        requirements = []
        patterns = [
            r'(?:SOLO|ÚNICAMENTE|EXCLUSIVAMENTE)\s+(?:PARA|CON)\s+([^.]{10,100})',
            r'VÁLID[OA]\s+(?:SOLO|ÚNICAMENTE)\s+(?:PARA|CON|EN)\s+([^.]{10,100})',
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, terms, re.IGNORECASE)
            for match in matches:
                req = match.group(1).strip()
                if req and len(req) > 10:
                    requirements.append(req[:200])
        
        return '; '.join(requirements[:3]) if requirements else None

async def main():
    """Ejecutar scraper"""
    scraper = CarrefourFinalScraper()
    promotions = await scraper.scrape()
    
    print(f"\n{'='*100}")
    print(f"📊 RESULTADOS: {len(promotions)} promociones únicas")
    print(f"{'='*100}\n")
    
    for idx, promo in enumerate(promotions, 1):
        print(f"📌 Promoción {idx}:")
        print(f"   Título: {promo['title']}")
        print(f"   Descuento: {promo['discount']}")
        print(f"   Pago: {promo['bank'] or promo['wallet'] or promo['card_type'] or 'N/A'}")
        print(f"   Tiendas: {promo['store_types'] or 'N/A'}")
        print(f"   T&C (preview): {promo['terms_raw'][:100] if promo['terms_raw'] else 'N/A'}...")
        print()
    
    if promotions:
        save = input("\n💾 ¿Guardar en la base de datos? (s/n): ").strip().lower()
        if save == 's':
            import sys
            import os
            parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            sys.path.insert(0, parent_dir)
            
            from database import Database
            from terms_parser import TermsParser
            import config
            
            db = Database()
            parser = TermsParser()
            
            # Limpiar promociones anteriores de Carrefour
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM promotions WHERE supermarket_id = (SELECT id FROM supermarkets WHERE name = 'Carrefour')")
            conn.commit()
            conn.close()
            print("   🗑️  Promociones anteriores eliminadas")
            
            supermarket_id = db.insert_supermarket('Carrefour', scraper.url)
            
            for promo in promotions:
                promotion_id = db.insert_promotion(supermarket_id, promo)
                if promotion_id and promo.get('terms_raw'):
                    terms_data = parser.parse(promo['terms_raw'])
                    db.insert_terms(promotion_id, terms_data)
            
            db.update_supermarket_scraped(supermarket_id)
            print(f"   ✅ {len(promotions)} promociones guardadas")
            print(f"\n💡 Verifica con: python view_promotions.py")

if __name__ == "__main__":
    asyncio.run(main())

