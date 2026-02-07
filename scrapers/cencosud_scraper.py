#!/usr/bin/env python3
"""
Scraper de Cencosud (Jumbo) - Promociones Bancarias
- Extrae promociones de https://www.jumbo.com.ar/descuentos-del-dia
- Itera solo por días para evitar duplicados
- Expande "Ver más" para obtener texto completo
- Jumbo, Disco y Vea tienen las mismas promociones, solo scrapeamos Jumbo
"""
import asyncio
import re
from typing import List, Dict, Set

from playwright.async_api import async_playwright
from bs4 import BeautifulSoup


class CencosudScraper:
    def __init__(self):
        self.name = 'Jumbo (Cencosud)'
        self.base_url = 'https://www.jumbo.com.ar/descuentos-del-dia'
        
        # Mapeo de días
        self.dias = {
            'Lunes': '1',
            'Martes': '2',
            'Miercoles': '3',
            'Jueves': '4',
            'Viernes': '5',
            'Sabado': '6',
            'Domingo': '0',
        }
        
    async def scrape(self) -> List[Dict]:
        """Scraping de promociones de Jumbo"""
        print(f"\n🔍 Scraping {self.name} - Promociones Bancarias...")
        print(f"   🌐 URL Base: {self.base_url}")
        
        all_promotions = []
        seen_promos: Set[str] = set()
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            
            try:
                context = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                )
                
                page = await context.new_page()
                
                # Scrapear solo por días
                print(f"\n   📅 Scrapeando por DÍAS...")
                for dia_nombre, dia_valor in self.dias.items():
                    url = f"{self.base_url}?type=por-dia&day={dia_valor}"
                    print(f"\n      📆 {dia_nombre}")
                    print(f"         URL: {url}")
                    
                    promos = await self._scrape_day(page, url, dia_nombre)
                    
                    new_count = 0
                    for promo in promos:
                        # Crear key única para evitar duplicados
                        promo_key = f"{promo.get('bank', '')}-{promo.get('discount', '')}-{promo.get('categories', '')}"
                        if promo_key not in seen_promos:
                            seen_promos.add(promo_key)
                            all_promotions.append(promo)
                            new_count += 1
                    
                    print(f"         ✅ {new_count} promociones nuevas encontradas")
                    await asyncio.sleep(1)
                
                print(f"\n✅ {self.name}: {len(all_promotions)} promociones únicas encontradas")
                
                return all_promotions
                
            except Exception as e:
                print(f"\n   ❌ Error: {e}")
                import traceback
                traceback.print_exc()
                return all_promotions
            finally:
                await browser.close()
    
    async def _scrape_day(self, page, url: str, dia_nombre: str) -> List[Dict]:
        """Scrapea las promociones de un día específico"""
        promotions = []
        
        try:
            await page.goto(url, wait_until='networkidle', timeout=30000)
            await asyncio.sleep(2)
            
            # Scroll para cargar todo el contenido
            await self._full_scroll_page(page)
            
            # Expandir todos los "Ver más" para obtener texto completo
            expanded_count = await self._expand_all_ver_mas(page)
            print(f"         📖 Expandidos {expanded_count} 'Ver más'")
            
            # Esperar a que se cargue el contenido expandido
            await asyncio.sleep(1)
            
            # Obtener HTML después de expandir
            html = await page.content()
            
            # Guardar debug para el primer día
            if dia_nombre == 'Lunes':
                with open('debug_jumbo.html', 'w', encoding='utf-8') as f:
                    f.write(html)
                await page.screenshot(path='debug_jumbo.png', full_page=True)
            
            # Extraer promociones
            promotions = self._extract_promotions(html, dia_nombre, url)
            
        except Exception as e:
            print(f"         ⚠️  Error: {e}")
            import traceback
            traceback.print_exc()
        
        return promotions
    
    async def _full_scroll_page(self, page):
        """Hace scroll completo para cargar todo el contenido lazy"""
        # Obtener altura total
        prev_height = 0
        for _ in range(20):  # Máximo 20 intentos
            # Scroll hasta el fondo
            current_height = await page.evaluate('document.body.scrollHeight')
            if current_height == prev_height:
                break
            prev_height = current_height
            
            await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            await asyncio.sleep(0.5)
        
        # Volver arriba
        await page.evaluate('window.scrollTo(0, 0)')
        await asyncio.sleep(0.3)
    
    async def _expand_all_ver_mas(self, page) -> int:
        """Expande todos los botones 'Ver más' de la página"""
        expanded = 0
        
        try:
            # Buscar todos los botones "Ver más" o "+ Ver más"
            ver_mas_buttons = page.locator('text=/[+]?\\s*Ver\\s*m[aá]s/i')
            count = await ver_mas_buttons.count()
            print(f"         🔍 Encontrados {count} botones 'Ver más'")
            
            for i in range(count):
                try:
                    button = ver_mas_buttons.nth(i)
                    if await button.is_visible(timeout=1000):
                        # Scroll al elemento
                        await button.scroll_into_view_if_needed()
                        await asyncio.sleep(0.1)
                        await button.click(timeout=2000)
                        expanded += 1
                        await asyncio.sleep(0.2)
                except Exception:
                    pass
            
            # También buscar con otros selectores
            other_selectors = [
                '[class*="show-more"]',
                '[class*="showMore"]',
                '[class*="ver-mas"]',
                '[class*="verMas"]',
                'button:has-text("Ver")',
                'span:has-text("Ver más")',
                'a:has-text("Ver más")',
            ]
            
            for selector in other_selectors:
                try:
                    buttons = page.locator(selector)
                    count = await buttons.count()
                    for i in range(count):
                        try:
                            btn = buttons.nth(i)
                            if await btn.is_visible(timeout=500):
                                await btn.click(timeout=1000)
                                expanded += 1
                                await asyncio.sleep(0.2)
                        except Exception:
                            pass
                except Exception:
                    pass
                
        except Exception as e:
            print(f"         ⚠️  Error expandiendo: {e}")
        
        return expanded
    
    def _extract_promotions(self, html: str, dia_nombre: str, url: str) -> List[Dict]:
        """Extrae promociones del HTML"""
        soup = BeautifulSoup(html, 'html.parser')
        promotions = []
        
        # Buscar cards de promociones
        # Las cards tienen una estructura con:
        # - Logo del banco (img)
        # - Descuento en texto verde grande (ej: "3 cuotas sin interés", "20% Dto.")
        # - Descripción
        # - Texto legal expandible ("Ver más" / "+ Ver más")
        
        all_cards = []
        
        # Estrategia 1: Buscar divs que contengan img + porcentaje/cuotas
        for div in soup.find_all('div'):
            # Verificar si tiene una imagen (logo del banco)
            img = div.find('img')
            if not img:
                continue
            
            text = div.get_text(' ', strip=True)
            
            # Debe tener descuento o cuotas
            has_discount = bool(re.search(r'\d+\s*%|\d+\s*cuotas?\s*sin\s*inter[eé]s|\d+\s*y\s*\d+\s*cuotas?|\d+\s*CSI', text, re.I))
            
            if not has_discount:
                continue
            
            # Longitud razonable (no muy corto, no muy largo)
            text_len = len(text)
            if text_len < 30 or text_len > 8000:
                continue
            
            # Verificar que no sea un contenedor padre (tiene hijos con la misma estructura)
            child_cards_count = 0
            for child in div.find_all('div', recursive=False):
                child_img = child.find('img')
                child_text = child.get_text(' ', strip=True)
                if child_img and re.search(r'\d+\s*%|\d+\s*cuotas', child_text, re.I):
                    child_cards_count += 1
            
            # Si tiene más de 1 hijo que parece card, es un contenedor
            if child_cards_count > 1:
                continue
            
            all_cards.append(div)
        
        # Estrategia 2: Buscar por clases comunes de cards de promociones
        card_selectors = [
            '[class*="promo"]',
            '[class*="card"]',
            '[class*="oferta"]',
            '[class*="descuento"]',
            '[class*="bank"]',
            '[class*="promotion"]',
        ]
        
        for selector in card_selectors:
            try:
                for element in soup.select(selector):
                    img = element.find('img')
                    if not img:
                        continue
                    
                    text = element.get_text(' ', strip=True)
                    if re.search(r'\d+\s*%|\d+\s*cuotas', text, re.I) and 30 < len(text) < 8000:
                        if element not in all_cards:
                            all_cards.append(element)
            except Exception:
                pass
        
        print(f"         🔍 Cards candidatas: {len(all_cards)}")
        
        # Filtrar duplicados por contenido similar - usar una key más específica
        unique_cards = []
        seen_texts = set()
        
        for card in all_cards:
            text = card.get_text(' ', strip=True)
            # Extraer solo los primeros elementos distintivos
            # Buscar el descuento/cuotas + primeras palabras
            discount_match = re.search(r'(\d+\s*%\s*(?:Dto\.?)?|\d+\s*(?:y\s*\d+\s*)?[Cc]uotas?\s*[Ss]in\s*[Ii]nter[eé]s)', text)
            if discount_match:
                # Usar descuento + primeras 50 chars después del descuento como key
                discount_pos = discount_match.end()
                text_key = f"{discount_match.group(1)}_{text[discount_pos:discount_pos+80]}"
            else:
                text_key = re.sub(r'\s+', ' ', text[:120])
            
            text_key = re.sub(r'\s+', ' ', text_key).strip().lower()
            
            if text_key not in seen_texts:
                seen_texts.add(text_key)
                unique_cards.append(card)
        
        print(f"         🔍 Cards únicas: {len(unique_cards)}")
        
        # Procesar cada card
        for card in unique_cards:
            try:
                promo = self._parse_promo(card, dia_nombre, url)
                if promo and promo.get('discount'):
                    promotions.append(promo)
            except Exception as e:
                print(f"         ⚠️  Error parseando card: {e}")
        
        print(f"         🔍 Cards encontradas: {len(promotions)}")
        
        return promotions
    
    def _parse_promo(self, card, dia_nombre: str, url: str) -> Dict:
        """Parsea una card para extraer información de la promoción"""
        text = card.get_text(' ', strip=True)
        
        promo = {
            'url': url,
            'supermarket': 'Jumbo',
            'valid_days': dia_nombre,
            'raw_text': text[:3000]
        }
        
        # 1. Extraer imagen del banco/tarjeta
        img = card.find('img')
        img_src = ''
        img_alt = ''
        if img:
            img_src = img.get('src', '') or img.get('data-src', '') or ''
            img_alt = img.get('alt', '') or ''
            promo['image_url'] = img_src
            promo['image_alt'] = img_alt
        
        # 2. Identificar banco/tarjeta - MEJORADO
        # Prioridad: 1) Imagen, 2) Texto legal específico, 3) Keywords
        bank = self._identify_bank_from_image(img_src, img_alt)
        
        if not bank:
            bank = self._identify_bank_from_text(text)
        
        promo['bank'] = bank
        
        # 3. Extraer descuento porcentual
        discount_match = re.search(r'(\d+)\s*%\s*(?:Dto\.?|[Dd]escuento)?', text)
        if discount_match:
            promo['discount'] = f"{discount_match.group(1)}%"
        
        # 4. Extraer cuotas sin interés (puede ser "3 y 6 cuotas" o "3, 6 y 12 cuotas")
        cuotas_patterns = [
            r'(\d+)\s*,?\s*(\d+)?\s*y?\s*(\d+)?\s*[Cc]uotas?\s*[Ss]in\s*[Ii]nter[eé]s',
            r'(\d+)\s*[Cc]uotas?\s*[Ss]in\s*[Ii]nter[eé]s',
            r'(\d+)\s*[Cc]SI',  # Cuotas Sin Interés abreviado
        ]
        
        for pattern in cuotas_patterns:
            cuotas_match = re.search(pattern, text, re.I)
            if cuotas_match:
                groups = [g for g in cuotas_match.groups() if g]
                if len(groups) > 1:
                    promo['cuotas'] = f"{', '.join(groups[:-1])} y {groups[-1]} cuotas sin interés"
                else:
                    promo['cuotas'] = f"{groups[0]} cuotas sin interés"
                
                if not promo.get('discount'):
                    promo['discount'] = promo['cuotas']
                break
        
        # 5. Extraer vigencia
        vigencia_patterns = [
            # "entre el 1/12/2025 y el 31/01/2026"
            r'(?:entre\s+(?:el\s+)?|del\s+|desde\s+(?:el\s+)?)(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})\s*(?:y\s+(?:el\s+)?|al\s+|hasta\s+(?:el\s+)?)(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})',
            # Formato con texto "del X de ENERO de 2026"
            r'(?:del|desde)\s+(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})\s+(?:al|hasta)\s+(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})',
        ]
        
        for pattern in vigencia_patterns:
            match = re.search(pattern, text, re.I)
            if match:
                groups = match.groups()
                if len(groups) == 6:
                    # Formato numérico
                    if groups[1].isdigit():
                        promo['valid_from'] = f"{groups[0]}/{groups[1]}/{groups[2]}"
                        promo['valid_until'] = f"{groups[3]}/{groups[4]}/{groups[5]}"
                    else:
                        # Formato con nombre de mes
                        promo['valid_from'] = f"{groups[0]} de {groups[1]} de {groups[2]}"
                        promo['valid_until'] = f"{groups[3]} de {groups[4]} de {groups[5]}"
                break
        
        # 6. Extraer tope
        tope_patterns = [
            r'(?:TOPE|REEMBOLSO\s+M[AÁ]XIMO|M[AÁ]XIMO|Tope\s+(?:m[aá]ximo\s+)?(?:de\s+)?(?:reintegro)?)[:\s]*\$?\s*([\d.,]+)',
            r'\$\s*([\d.,]+)\s*(?:de\s+)?(?:tope|m[aá]ximo)',
        ]
        
        for pattern in tope_patterns:
            tope_match = re.search(pattern, text, re.I)
            if tope_match:
                amount = tope_match.group(1).replace('.', '').replace(',', '.')
                try:
                    amount_num = float(amount)
                    promo['tope'] = f"${amount_num:,.0f}".replace(',', '.')
                except Exception:
                    promo['tope'] = f"${tope_match.group(1)}"
                break
        
        # 7. Extraer tarjetas aceptadas
        tarjetas = []
        if re.search(r'\bVISA\b', text, re.I):
            tarjetas.append('Visa')
        if re.search(r'\bMASTERCARD\b', text, re.I):
            tarjetas.append('Mastercard')
        if re.search(r'\bCABAL\b', text, re.I):
            tarjetas.append('Cabal')
        if re.search(r'\bAMERICAN\s+EXPRESS\b|\bAMEX\b', text, re.I):
            tarjetas.append('American Express')
        if re.search(r'\bNARANJA\b', text, re.I):
            tarjetas.append('Naranja')
        if tarjetas:
            promo['card_types'] = ', '.join(tarjetas)
        
        # 8. Tipo de pago (crédito/débito)
        payment_types = []
        if re.search(r'TARJETAS?\s+DE\s+CR[EÉ]DITO|CR[EÉ]DITO', text, re.I):
            payment_types.append('Crédito')
        if re.search(r'TARJETAS?\s+DE\s+D[EÉ]BITO|D[EÉ]BITO', text, re.I):
            payment_types.append('Débito')
        if payment_types:
            promo['payment_type'] = ', '.join(payment_types)
        
        # 9. Extraer categorías/productos
        categories_patterns = [
            r'(?:cuotas?\s+sin\s+inter[eé]s\s+)?en\s+([A-Za-záéíóúñÁÉÍÓÚÑ\s,]+?)(?:\s+Para\s+compras|\s+Promoci[oó]n|\s+V[aá]lida|\s+Abonando|\s+PROMOCIONES|\.|$)',
            r'Dto\.?\s+(?:en\s+)?([A-Za-záéíóúñÁÉÍÓÚÑ\s,]+?)(?:\s+Para|\s+Promoci[oó]n|\.|$)',
        ]
        
        for pattern in categories_patterns:
            categories_match = re.search(pattern, text, re.I)
            if categories_match:
                categories = categories_match.group(1).strip()
                categories = re.sub(r'\s+', ' ', categories)
                # Limpiar categorías que no son válidas
                if len(categories) > 2 and len(categories) < 100:
                    # Evitar palabras que no son categorías
                    invalid_starts = ['Para', 'Con', 'El', 'La', 'Los', 'Las', 'Desde', 'Del', 'Válido', 'Exclusivo']
                    if not any(categories.startswith(w) for w in invalid_starts):
                        promo['categories'] = categories
                        break
        
        # 10. Extraer exclusiones
        exclusions_parts = []
        
        # "NO VÁLIDO EL 01 DE ENERO DE 2026"
        no_valido_fecha = re.search(r'NO\s+V[AÁ]LIDO\s+(?:EL\s+)?(\d{1,2}\s+DE\s+\w+\s+DE\s+\d{4}|\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})', text, re.I)
        if no_valido_fecha:
            exclusions_parts.append(f"No válido el {no_valido_fecha.group(1)}")
        
        # "No aplica para..."
        no_aplica_matches = re.findall(r'[Nn]o\s+aplica\s+(?:para\s+)?([^.]+?)(?:\.|V[aá]lido|$)', text)
        for match in no_aplica_matches:
            if len(match.strip()) > 5:
                exclusions_parts.append(f"No aplica {match.strip()[:200]}")
        
        if exclusions_parts:
            promo['exclusions'] = ' | '.join(exclusions_parts)[:500]
        
        # 11. Acumulable
        if re.search(r'no\s+(?:es\s+)?acumulable|no\s+acumula', text, re.I):
            promo['acumulable'] = 'No'
        elif re.search(r'\bacumulable\b', text, re.I):
            promo['acumulable'] = 'Sí'
        
        # 12. Validez (presencial/online)
        if re.search(r'EXCLUSIVO\s+ONLINE|COMPRAS?\s+ONLINE|TIENDA\s+ONLINE|JUMBO\.COM', text, re.I):
            promo['validez'] = 'Online'
        elif re.search(r'V[AÁ]LIDO\s+PRESENCIAL|EN\s+(?:LOS\s+)?(?:LOCALES|COMERCIOS)', text, re.I):
            promo['validez'] = 'Presencial'
        
        # 13. Información financiera (TNA, TEA, CFT)
        tna_match = re.search(r'(?:TNA|TASA\s+NOMINAL\s+ANUAL)[:\s]*(\d+[,.]?\d*)\s*%', text, re.I)
        if tna_match:
            promo['tna'] = f"{tna_match.group(1)}%"
        
        tea_match = re.search(r'(?:TEA|TASA\s+EFECTIVA\s+ANUAL)[:\s]*(\d+[,.]?\d*)\s*%', text, re.I)
        if tea_match:
            promo['tea'] = f"{tea_match.group(1)}%"
        
        cft_match = re.search(r'(?:CFTEA?|COSTO\s+FINANCIERO\s+TOTAL)[^:]*[:\s]*(\d+[,.]?\d*)\s*%', text, re.I)
        if cft_match:
            promo['cft'] = f"{cft_match.group(1)}%"
        
        # 14. Extraer bancos participantes (para MODO)
        if promo.get('bank') == 'MODO':
            participan_match = re.search(r'[Pp]articipan\s+(.+?)(?:\.\s*[A-Z]|$)', text)
            if participan_match:
                bancos_text = participan_match.group(1)
                bancos_list = re.findall(r'Banco\s+[\w\s]+|Billetera\s+\w+|\bICBC\b|\bBBVA\b|\bHSBC\b', bancos_text, re.I)
                if bancos_list:
                    bancos_clean = [b.strip().rstrip(',').rstrip('y').strip() for b in bancos_list]
                    bancos_clean = [b for b in bancos_clean if len(b) > 3]
                    if bancos_clean:
                        promo['bancos_participantes'] = ', '.join(bancos_clean[:15])
        
        # 15. Construir título
        title_parts = []
        if promo.get('bank'):
            title_parts.append(promo['bank'])
        
        if promo.get('discount'):
            title_parts.append(promo['discount'])
        
        if promo.get('categories'):
            title_parts.append(f"en {promo['categories']}")
        
        if promo.get('validez') == 'Online':
            title_parts.append('(Online)')
        
        title_parts.append(f"- {dia_nombre}")
        
        promo['title'] = ' '.join(title_parts) if title_parts else text[:80]
        
        return promo
    
    def _identify_bank_from_image(self, img_src: str, img_alt: str) -> str:
        """
        Identifica el banco analizando la URL o alt de la imagen.
        """
        if not img_src and not img_alt:
            return ''
        
        combined = f"{img_src} {img_alt}".lower()
        
        # Mapeo de keywords en imagen -> nombre del banco
        # IMPORTANTE: Orden de prioridad (más específicos primero)
        image_bank_map = [
            # Bancos específicos (tienen prioridad sobre billeteras)
            (r'hipotecario', 'Banco Hipotecario'),
            (r'supervielle', 'Supervielle'),
            (r'galicia', 'Banco Galicia'),
            (r'macro', 'Banco Macro'),
            (r'nacion|bna[^c]|banco.?nacion', 'Banco Nación'),
            (r'ciudad', 'Banco Ciudad'),
            (r'provincia|bapro', 'Banco Provincia'),
            (r'santander', 'Banco Santander'),
            (r'patagonia', 'Banco Patagonia'),
            (r'comafi', 'Banco Comafi'),
            (r'c[oó]rdoba|bancor', 'Bancor'),
            (r'columbia', 'Banco Columbia'),
            (r'hsbc', 'HSBC'),
            (r'bbva|franc[eé]s', 'BBVA'),
            (r'icbc', 'ICBC'),
            (r'credicoop', 'Banco Credicoop'),
            
            # Billeteras virtuales
            (r'modo', 'MODO'),
            (r'mercado[-_]?pago|mp[-_]logo', 'Mercado Pago'),
            (r'prex', 'Prex'),
            (r'personal[-_]?pay', 'Personal Pay'),
            (r'cuenta[-_]?dni', 'Cuenta DNI'),
            (r'ual[aá]', 'Ualá'),
            (r'cencopay|cencosud|cencop', 'CencoPay'),
            
            # Tarjetas
            (r'naranja', 'Naranja X'),
            (r'clarin|365', 'Clarín 365'),
            (r'tarjeta.?sol|sol.?tarjeta', 'Tarjeta Sol'),
            (r'amex|american', 'American Express'),
            
            # Genéricos (último recurso)
            (r'visa[-_]?master|master[-_]?visa', 'Visa/Mastercard'),
            (r'visa', 'Visa'),
            (r'mastercard|master', 'Mastercard'),
        ]
        
        for pattern, bank_name in image_bank_map:
            if re.search(pattern, combined):
                return bank_name
        
        return ''
    
    def _identify_bank_from_text(self, text: str) -> str:
        """
        Identifica el banco desde el texto legal.
        """
        text_upper = text.upper()
        
        # Patrón 1: "a través de MODO" con banco específico en el contexto
        # Ejemplo: "25% Dto. a través de MODO... Vigente... para clientes de Supervielle"
        if 'TRAVÉS DE MODO' in text_upper or 'CON MODO' in text_upper:
            # Buscar si menciona un banco específico como emisor
            banco_emisor = re.search(r'(?:CLIENTES?\s+(?:DE\s+)?|TARJETAS?\s+(?:DE\s+)?|EMITIDAS?\s+POR\s+)(BANCO\s+\w+|SUPERVIELLE|HIPOTECARIO|GALICIA|MACRO|SANTANDER)', text_upper)
            if banco_emisor:
                return self._normalize_bank_name(banco_emisor.group(1))
            
            # Si solo dice "pagando con MODO" sin banco específico
            if re.search(r'PAGANDO\s+CON\s+MODO', text_upper):
                # Verificar si lista múltiples bancos
                if re.search(r'PARTICIPAN\s+BANCO', text_upper):
                    return 'MODO'
        
        # Patrón 2: Buscar banco específico mencionado al inicio
        banco_patterns = [
            (r'BANCO\s+HIPOTECARIO', 'Banco Hipotecario'),
            (r'SUPERVIELLE', 'Supervielle'),
            (r'BANCO\s+(?:DE\s+)?GALICIA', 'Banco Galicia'),
            (r'BANCO\s+MACRO', 'Banco Macro'),
            (r'BANCO\s+(?:DE\s+LA\s+)?NACI[OÓ]N', 'Banco Nación'),
            (r'BANCO\s+CIUDAD', 'Banco Ciudad'),
            (r'BANCO\s+(?:DE\s+LA\s+)?PROVINCIA', 'Banco Provincia'),
            (r'BANCO\s+SANTANDER', 'Banco Santander'),
            (r'BANCO\s+PATAGONIA', 'Banco Patagonia'),
            (r'BANCO\s+COMAFI', 'Banco Comafi'),
            (r'BANCOR|BANCO\s+(?:DE\s+)?C[OÓ]RDOBA', 'Banco Córdoba'),
            (r'\bHSBC\b', 'HSBC'),
            (r'\bBBVA\b', 'BBVA'),
            (r'\bICBC\b', 'ICBC'),
        ]
        
        # Contar menciones de bancos
        bank_mentions = {}
        for pattern, name in banco_patterns:
            count = len(re.findall(pattern, text_upper))
            if count > 0:
                bank_mentions[name] = count
        
        # Si hay un solo banco mencionado, ese es el banco
        if len(bank_mentions) == 1:
            return list(bank_mentions.keys())[0]
        
        # Si hay múltiples bancos, buscar cuál es el emisor
        if len(bank_mentions) > 1:
            # Buscar "clientes de X" o "tarjetas de X"
            for pattern, name in banco_patterns:
                if re.search(rf'(?:CLIENTES?\s+(?:DE\s+)?|TARJETAS?\s+(?:DE\s+)?){pattern}', text_upper):
                    return name
        
        # Billeteras y otros
        billeteras = [
            (r'\bMODO\b', 'MODO'),
            (r'MERCADO\s*PAGO', 'Mercado Pago'),
            (r'\bPREX\b', 'Prex'),
            (r'PERSONAL\s+PAY', 'Personal Pay'),
            (r'CUENTA\s+DNI', 'Cuenta DNI'),
            (r'\bUAL[AÁ]\b', 'Ualá'),
            (r'\bCENCOPAY\b', 'CencoPay'),
            (r'NARANJA\s*X?|TARJETA\s+NARANJA', 'Naranja X'),
            (r'CLAR[IÍ]N\s*365', 'Clarín 365'),
            (r'TARJETA\s+SOL', 'Tarjeta Sol'),
        ]
        
        for pattern, name in billeteras:
            if re.search(pattern, text_upper):
                return name
        
        return ''
    
    def _normalize_bank_name(self, banco_text: str) -> str:
        """Normaliza el nombre del banco extraído"""
        banco_upper = banco_text.upper().strip()
        
        normalization_map = {
            'GALICIA': 'Banco Galicia',
            'BANCO GALICIA': 'Banco Galicia',
            'BANCO DE GALICIA': 'Banco Galicia',
            'MACRO': 'Banco Macro',
            'BANCO MACRO': 'Banco Macro',
            'NACION': 'Banco Nación',
            'BANCO NACION': 'Banco Nación',
            'BANCO DE LA NACION': 'Banco Nación',
            'CIUDAD': 'Banco Ciudad',
            'BANCO CIUDAD': 'Banco Ciudad',
            'PROVINCIA': 'Banco Provincia',
            'BANCO PROVINCIA': 'Banco Provincia',
            'BANCO DE LA PROVINCIA': 'Banco Provincia',
            'SANTANDER': 'Banco Santander',
            'BANCO SANTANDER': 'Banco Santander',
            'PATAGONIA': 'Banco Patagonia',
            'BANCO PATAGONIA': 'Banco Patagonia',
            'SUPERVIELLE': 'Supervielle',
            'BANCO SUPERVIELLE': 'Supervielle',
            'COMAFI': 'Banco Comafi',
            'BANCO COMAFI': 'Banco Comafi',
            'HIPOTECARIO': 'Banco Hipotecario',
            'BANCO HIPOTECARIO': 'Banco Hipotecario',
            'HSBC': 'HSBC',
            'BBVA': 'BBVA',
            'ICBC': 'ICBC',
            'BANCOR': 'Banco Córdoba',
            'BANCO CORDOBA': 'Banco Córdoba',
        }
        
        return normalization_map.get(banco_upper, banco_text.title())


async def main():
    scraper = CencosudScraper()
    promotions = await scraper.scrape()
    
    print(f"\n{'='*100}")
    print(f"📊 RESULTADOS: {len(promotions)} promociones únicas")
    print(f"{'='*100}")
    
    if promotions:
        print(f"\n📋 Todas las promociones encontradas:\n")
        for i, promo in enumerate(promotions, 1):
            print(f"\n{'─'*80}")
            print(f"{i}. {promo.get('title', 'Sin título')}")
            print(f"   💰 Descuento: {promo.get('discount', 'N/A')}")
            print(f"   🏦 Banco: {promo.get('bank', 'N/A')}")
            print(f"   💳 Tarjetas: {promo.get('card_types', 'N/A')}")
            print(f"   💵 Tipo: {promo.get('payment_type', 'N/A')}")
            print(f"   📅 Días válidos: {promo.get('valid_days', 'N/A')}")
            print(f"   📆 Vigencia: {promo.get('valid_from', 'N/A')} → {promo.get('valid_until', 'N/A')}")
            print(f"   🏪 Validez: {promo.get('validez', 'N/A')}")
            print(f"   📦 Categorías: {promo.get('categories', 'N/A')}")
            print(f"   💵 Tope: {promo.get('tope', 'N/A')}")
            print(f"   🔁 Acumulable: {promo.get('acumulable', 'N/A')}")
            
            if promo.get('tna') or promo.get('tea') or promo.get('cft'):
                print(f"   📊 TNA: {promo.get('tna', 'N/A')} | TEA: {promo.get('tea', 'N/A')} | CFT: {promo.get('cft', 'N/A')}")
            
            if promo.get('bancos_participantes'):
                print(f"   🏦 Bancos participantes: {promo['bancos_participantes'][:150]}...")
            
            if promo.get('exclusions'):
                print(f"   ⛔ Exclusiones: {promo['exclusions'][:200]}...")
            
            print(f"   🔗 URL: {promo.get('url', 'N/A')}")
            
            raw_text = promo.get('raw_text', '')
            if raw_text:
                print(f"   📝 Texto: {raw_text[:300]}...")
    else:
        print("\n⚠️  No se encontraron promociones.")
        print("   Revisa debug_jumbo.html y debug_jumbo.png para analizar la estructura.")


if __name__ == "__main__":
    asyncio.run(main())
