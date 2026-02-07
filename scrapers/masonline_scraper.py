#!/usr/bin/env python3
"""
Scraper de Más Online (ChangoMás) - Promociones Bancarias
- Extrae promociones de https://www.masonline.com.ar/promociones-bancarias
- Navega por cada día de la semana
- Expande "Ver legal" para obtener términos y condiciones completos
"""
import asyncio
import re
from typing import List, Dict, Set

from playwright.async_api import async_playwright
from bs4 import BeautifulSoup


class MasOnlineScraper:
    def __init__(self):
        self.name = 'Más Online (ChangoMás)'
        self.base_url = 'https://www.masonline.com.ar/promociones-bancarias'
        
        # Días de la semana para iterar
        self.dias = {
            'lunes': 'Lunes',
            'martes': 'Martes',
            'miercoles': 'Miércoles',
            'jueves': 'Jueves',
            'viernes': 'Viernes',
            'sabado': 'Sábado',
            'domingo': 'Domingo',
        }
        
    async def scrape(self) -> List[Dict]:
        """Scraping de promociones de Más Online"""
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
                
                # Iterar por cada día
                print(f"\n   📅 Scrapeando por DÍAS...")
                
                for dia_param, dia_nombre in self.dias.items():
                    url = f"{self.base_url}?dia={dia_param}"
                    print(f"\n      📆 {dia_nombre}")
                    print(f"         URL: {url}")
                    
                    promos = await self._scrape_day(page, url, dia_nombre)
                    
                    new_count = 0
                    for promo in promos:
                        # Key única para evitar duplicados
                        promo_key = f"{promo.get('bank', '')}-{promo.get('discount', '')}-{promo.get('tope', '')}"
                        if promo_key not in seen_promos:
                            seen_promos.add(promo_key)
                            all_promotions.append(promo)
                            new_count += 1
                    
                    print(f"         ✅ {new_count} promociones nuevas encontradas")
                    await asyncio.sleep(1)
                
                # Guardar debug
                html = await page.content()
                with open('debug_masonline.html', 'w', encoding='utf-8') as f:
                    f.write(html)
                await page.screenshot(path='debug_masonline.png', full_page=True)
                print(f"\n   📸 Debug: debug_masonline.html, debug_masonline.png")
                
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
            await page.goto(url, wait_until='networkidle', timeout=60000)
            await asyncio.sleep(2)
            
            # Hacer click en "POR DÍA" si existe
            try:
                por_dia_btn = page.locator('text=POR DÍA, button:has-text("POR DÍA")').first
                if await por_dia_btn.is_visible():
                    await por_dia_btn.click()
                    await asyncio.sleep(1)
            except:
                pass
            
            # Scroll para cargar contenido
            await self._scroll_page(page)
            
            # Expandir todos los "Ver legal"
            expanded = await self._expand_ver_legal(page)
            print(f"         📖 Expandidos {expanded} 'Ver legal'")
            
            # Esperar contenido expandido
            await asyncio.sleep(1)
            
            # Obtener HTML
            html = await page.content()
            
            # Extraer promociones
            promotions = self._extract_promotions(html, dia_nombre, url)
            
        except Exception as e:
            print(f"         ⚠️  Error: {e}")
            import traceback
            traceback.print_exc()
        
        return promotions
    
    async def _scroll_page(self, page):
        """Hace scroll para cargar contenido"""
        for i in range(5):
            await page.evaluate(f'window.scrollBy(0, 400)')
            await asyncio.sleep(0.3)
        await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
        await asyncio.sleep(0.5)
        await page.evaluate('window.scrollTo(0, 0)')
        await asyncio.sleep(0.3)
    
    async def _expand_ver_legal(self, page) -> int:
        """Expande todos los botones 'Ver legal'"""
        expanded = 0
        
        try:
            selectors = [
                'text=Ver legal',
                'text=Ver Legal',
                'text=ver legal',
                'button:has-text("legal")',
                'span:has-text("Ver legal")',
                'div:has-text("Ver legal")',
                '[class*="legal"]',
                '[class*="expand"]',
                '[class*="toggle"]',
            ]
            
            for selector in selectors:
                try:
                    buttons = page.locator(selector)
                    count = await buttons.count()
                    
                    for i in range(count):
                        try:
                            button = buttons.nth(i)
                            if await button.is_visible():
                                await button.click(timeout=2000)
                                expanded += 1
                                await asyncio.sleep(0.3)
                        except:
                            pass
                except:
                    pass
                    
        except Exception as e:
            print(f"         ⚠️  Error expandiendo: {e}")
        
        return expanded
    
    def _extract_promotions(self, html: str, dia_nombre: str, url: str) -> List[Dict]:
        """Extrae promociones del HTML"""
        soup = BeautifulSoup(html, 'html.parser')
        promotions = []
        
        # Buscar cards de promociones
        # Basándonos en la imagen: cada card tiene
        # - Porcentaje de descuento/reintegro (ej: "20% de reintegro")
        # - Logo del banco/billetera (MODO, etc.)
        # - Descripción (ej: "Con crédito y débito de bancos seleccionados")
        # - Tope y mínimo (ej: "Tope: $20.000 por usuario. Mínimo de compra: $50.000")
        # - Botón "Ver legal"
        # - Indicador de dónde aplica (ej: "Pagando: Sucursal y MásOnline")
        
        all_cards = []
        
        # Buscar divs que contengan estructura de promoción
        for div in soup.find_all('div'):
            text = div.get_text(' ', strip=True)
            
            # Debe tener descuento/reintegro o cuotas
            has_discount = bool(re.search(r'\d+\s*%|cuotas?\s*sin\s*inter|reintegro', text, re.I))
            
            # Debe tener información de tope o banco/billetera
            has_promo_info = bool(re.search(r'[Tt]ope|MODO|[Bb]anco|[Cc]r[eé]dito|[Dd][eé]bito|[Mm][ií]nimo', text))
            
            # Longitud razonable
            good_length = 50 < len(text) < 2000
            
            # FILTRO: Excluir contenido institucional/informativo que no es promoción del día
            # Esto detecta secciones como "SERVICIO EXTRA CASH", "CUOTAS SIN INTERÉS" genéricas
            is_institutional_content = self._is_institutional_content(text)
            
            if has_discount and has_promo_info and good_length and not is_institutional_content:
                # Verificar que no sea contenedor padre
                child_divs = div.find_all('div', recursive=False)
                is_parent = False
                for child in child_divs:
                    child_text = child.get_text(' ', strip=True)
                    if re.search(r'\d+\s*%.*[Tt]ope', child_text) and len(child_text) > 40:
                        is_parent = True
                        break
                
                if not is_parent:
                    all_cards.append(div)
        
        print(f"         🔍 Cards encontradas: {len(all_cards)}")
        
        # Procesar cards
        seen_texts = set()
        
        for card in all_cards:
            text = card.get_text(' ', strip=True)
            
            # Evitar duplicados
            text_key = re.sub(r'\s+', ' ', text[:120])
            if text_key in seen_texts:
                continue
            seen_texts.add(text_key)
            
            # FILTRO: Detectar fragmentos parciales de promociones que no son promociones completas
            # Ej: "+5% adicional" es parte de una promoción mayor, no una promoción en sí
            if self._is_partial_fragment(text):
                continue
            
            # Extraer información
            promo = self._parse_promo(card, text, dia_nombre, url)
            
            if promo and promo.get('discount'):
                promotions.append(promo)
        
        return promotions
    
    def _is_partial_fragment(self, text: str) -> bool:
        """Detecta si el texto es un fragmento parcial de una promoción y no una promoción completa.
        
        Ejemplos de fragmentos parciales:
        - "+5% adicional" (es un bonus de otra promoción)
        - Textos muy cortos sin estructura de promoción completa
        - Textos que empiezan con "+" indicando que es adicional a algo
        
        Returns:
            True si es un fragmento parcial que debe ignorarse
        """
        text_stripped = text.strip()
        
        # Fragmento que empieza con "+" (es adicional a otra promoción)
        # Ej: "+ 5% adicional", "+5% adicional"
        if re.match(r'^\+\s*\d+\s*%', text_stripped):
            return True
        
        # Texto que es principalmente "+X% adicional" sin contexto de promoción completa
        # Esto detecta: "Con tarjetas... + 5% adicional y $25.000 de reintegro..."
        # cuando el texto NO tiene el descuento principal (20%) al inicio
        if re.search(r'^\s*[Cc]on\s+tarjetas?', text_stripped):
            # Si empieza con "Con tarjetas" pero NO tiene un porcentaje grande al inicio,
            # probablemente es un fragmento
            first_percent = re.search(r'(\d+)\s*%', text_stripped)
            if first_percent:
                percent_value = int(first_percent.group(1))
                # Si el primer porcentaje es bajo (<=10%) y hay "adicional" cerca,
                # probablemente es un fragmento
                if percent_value <= 10 and re.search(r'adicional', text_stripped, re.I):
                    return True
        
        # Textos muy cortos que no tienen estructura de card completa
        # Una promoción real tiene: descuento + banco/billetera + algún detalle (tope, vigencia, etc.)
        if len(text_stripped) < 100:
            # Verificar si tiene estructura mínima de promoción
            has_main_discount = bool(re.search(r'(\d{2})\s*%\s*(de\s+)?(descuento|ahorro|reintegro|off)', text_stripped, re.I))
            has_bank_or_wallet = bool(re.search(r'MODO|[Bb]anco|Supervielle|Galicia|Macro|HSBC|BBVA|Santander|Patagonia|M[aá]sClub', text_stripped))
            
            # Si es corto y no tiene estructura, es fragmento
            if not has_main_discount and not has_bank_or_wallet:
                return True
        
        return False
    
    def _is_institutional_content(self, text: str) -> bool:
        """Detecta si el texto es contenido institucional/informativo general 
        que no es una promoción específica del día.
        
        Esto incluye:
        - "SERVICIO EXTRA CASH" - información de retiro de efectivo
        - "CUOTAS SIN INTERÉS" genérico sin banco/billetera específico
        - Información legal general que aplica todos los días
        - Textos que excluyen explícitamente billeteras virtuales como promo
        
        Returns:
            True si es contenido institucional que debe filtrarse
        """
        text_upper = text.upper()
        text_lower = text.lower()
        
        # Patrón 1: "SERVICIO EXTRA CASH" - es info de retiro de efectivo, no promoción
        if 'SERVICIO EXTRA CASH' in text_upper or 'EXTRA CASH' in text_upper:
            return True
        
        # Patrón 2: "Con tu compra podrás retirar" - descripción de servicio de cash
        if re.search(r'podr[aá]s\s+retirar|retir[ao]\s+(?:de\s+)?(?:dinero|efectivo|cash)', text_lower):
            return True
        
        # Patrón 3: Texto que SOLO habla de cuotas sin interés genéricas SIN asociarlo a banco/billetera
        # pero que además excluye a las billeteras virtuales en el mismo texto
        # Ej: "Las siguientes promociones aplican... quedan excluidos los pagos mediante MODO, Mercado Pago..."
        if re.search(r'quedan\s+excluidos?\s+los\s+pagos\s+(?:realizados\s+)?mediante\s+(?:MODO|Mercado\s*Pago)', text, re.I):
            # Si excluye MODO/MercadoPago pero NO tiene un banco específico asociado, es info general
            has_specific_bank = bool(re.search(
                r'GALICIA|MACRO|NACI[OÓ]N|BANCO\s+CIUDAD|BANCO\s+PROVINCIA|BAPRO|SANTANDER|BANCO\s+PATAGONIA|SUPERVIELLE|'
                r'HIPOTECARIO|CREDICOOP|HSBC|BBVA|ICBC|BRUBANK|COMAFI|INDUSTRIAL|ITAU',
                text_upper
            ))
            if not has_specific_bank:
                return True
        
        # Patrón 4: Contenido que describe promociones en general sin ser una promoción específica
        # "Las siguientes promociones aplican únicamente para compra online"
        if re.search(r'las\s+siguientes\s+promociones\s+aplican', text_lower):
            return True
        
        # Patrón 5: Texto que es principalmente descripción del servicio de cuotas genérico
        # sin mencionar un banco/billetera específico en el título
        # Detectamos "MERCADO PAGO X CUOTAS SIN INTERÉS" como header genérico
        if re.search(r'^MERCADO\s*PAGO\s+\d+\s+CUOTAS\s+SIN\s+INTER[EÉ]S', text_upper):
            # Verificar si tiene condiciones que lo hacen promoción válida vs info general
            # Si tiene "CFTNA: COSTO FINANCIERO" es probablemente info legal general
            if 'CFTNA' in text_upper or 'COSTO FINANCIERO TOTAL NOMINAL' in text_upper:
                # Pero si tiene fecha de vigencia específica, podría ser promo real
                # Revisar si hay contexto de "aplica solo si se cumplen" que indica info genérica
                if re.search(r'aplica\s+solo\s+si\s+se\s+cumplen\s+todas\s+las\s+condiciones', text_lower):
                    return True
        
        # Patrón 6: Texto muy largo que parece ser términos y condiciones generales
        # más que una card de promoción específica
        if len(text) > 1500 and re.search(r'CFTNA|COSTO\s+FINANCIERO\s+TOTAL', text_upper):
            # Los T&C generales suelen tener toda esta info junta
            return True
        
        return False
    
    def _parse_promo(self, card, text: str, dia_nombre: str, url: str) -> Dict:
        """Parsea una card para extraer información de la promoción"""
        promo = {
            'url': url,
            'supermarket': 'ChangoMás',
            'valid_days': dia_nombre,
            'raw_text': text[:3000]
        }
        
        # 1. Extraer imagen del banco/billetera
        img_alt = ''
        img = card.find('img')
        if img:
            img_src = img.get('src', '') or img.get('data-src', '')
            img_alt = img.get('alt', '')
            promo['image_url'] = img_src
            promo['image_alt'] = img_alt
        
        # 2. Identificar banco y billetera virtual (usando texto + imagen)
        bank, billetera = self._identify_bank_and_wallet(text, img_alt)
        promo['bank'] = bank
        if billetera:
            promo['billetera_virtual'] = billetera
        
        # 3. Extraer días válidos del texto (ej: "todos los lunes y jueves")
        promo['valid_days'] = self._extract_valid_days(text, dia_nombre)
        
        # 4. Extraer descuento/reintegro
        # "20% de reintegro"
        reintegro_match = re.search(r'(\d+)\s*%\s*(?:de\s+)?reintegro', text, re.I)
        if reintegro_match:
            promo['discount'] = f"{reintegro_match.group(1)}% reintegro"
            promo['discount_type'] = 'Reintegro'
        else:
            # Descuento normal
            discount_match = re.search(r'(\d+)\s*%\s*(?:de\s+)?(?:descuento|dto|off)?', text, re.I)
            if discount_match:
                promo['discount'] = f"{discount_match.group(1)}%"
        
        # 5. Extraer cuotas sin interés - mejorado
        cuotas_patterns = [
            # "4 cuotas sin interés"
            r'(\d+)\s*cuotas?\s*sin\s*inter[eé]s',
            # "4 cuotas Sin interés" (con mayúscula)
            r'(\d+)\s*cuotas?\s*[Ss]in\s*[Ii]nter[eé]s',
            # "en 4 cuotas sin interés"
            r'en\s+(\d+)\s*cuotas?\s*sin\s*inter[eé]s',
            # "hasta 12 cuotas sin interés"
            r'hasta\s+(\d+)\s*cuotas?\s*sin\s*inter[eé]s',
            # "4 cuotas fijas"
            r'(\d+)\s*cuotas?\s*fijas?',
            # "cuotas sin interés" genérico (buscar número cerca)
            r'(\d+)\s*c(?:uotas?)?\s*s(?:in)?\s*i(?:nter[eé]s)?',
        ]
        
        for pattern in cuotas_patterns:
            cuotas_match = re.search(pattern, text, re.I)
            if cuotas_match:
                num_cuotas = cuotas_match.group(1)
                promo['cuotas'] = f"{num_cuotas} cuotas sin interés"
                promo['discount_type'] = 'Cuotas'
                if not promo.get('discount'):
                    promo['discount'] = promo['cuotas']
                break
        
        # 6. Extraer tope - mejorado para "Ver legal"
        tope_patterns = [
            # Tope: $20.000 por usuario
            r'[Tt]ope[:\s]*\$?\s*([\d.,]+)(?:\s*(por\s+usuario|mensual|semanal|diario|por\s+transacci[oó]n|por\s+d[ií]a|por\s+semana|por\s+mes))?',
            # Máximo de reintegro/descuento: $20.000
            r'[Mm][aá]ximo\s+(?:de\s+)?(?:reintegro|descuento|beneficio)[:\s]*\$?\s*([\d.,]+)',
            # Reintegro máximo: $20.000
            r'(?:reintegro|descuento|beneficio)\s+m[aá]ximo[:\s]*\$?\s*([\d.,]+)',
            # Hasta $20.000 de reintegro
            r'[Hh]asta\s+\$?\s*([\d.,]+)\s+(?:de\s+)?(?:reintegro|descuento|beneficio)',
            # Máximo $20.000
            r'[Mm][aá]ximo[:\s]*\$?\s*([\d.,]+)',
            # Límite de $20.000
            r'[Ll][ií]mite\s+(?:de\s+)?\$?\s*([\d.,]+)',
        ]
        
        for pattern in tope_patterns:
            match = re.search(pattern, text, re.I)
            if match:
                amount = match.group(1).replace('.', '').replace(',', '.')
                period = match.group(2) if match.lastindex >= 2 and match.group(2) else ''
                try:
                    amount_num = float(amount)
                    tope_str = f"${amount_num:,.0f}".replace(',', '.')
                    if period:
                        tope_str += f" {period.lower()}"
                    promo['tope'] = tope_str
                except:
                    promo['tope'] = f"${match.group(1)}"
                break
        
        # Buscar frecuencia del tope si no se encontró
        if promo.get('tope') and not any(x in promo['tope'].lower() for x in ['usuario', 'mensual', 'semanal', 'diario']):
            freq_match = re.search(r'(?:por|cada)\s+(usuario|mes|semana|d[ií]a|transacci[oó]n)', text, re.I)
            if freq_match:
                freq = freq_match.group(1).lower()
                freq_map = {'mes': 'mensual', 'semana': 'semanal', 'día': 'diario', 'dia': 'diario'}
                freq_str = freq_map.get(freq, f"por {freq}")
                promo['tope'] += f" {freq_str}"
        
        # 7. Extraer mínimo de compra - mejorado para "Ver legal"
        minimo_patterns = [
            r'[Mm][ií]nimo\s+(?:de\s+)?compra[:\s]*\$?\s*([\d.,]+)',
            r'[Cc]ompra\s+m[ií]nima[:\s]*\$?\s*([\d.,]+)',
            r'[Mm]onto\s+m[ií]nimo[:\s]*\$?\s*([\d.,]+)',
            r'[Aa]\s+partir\s+de\s+\$?\s*([\d.,]+)',
            r'[Cc]on\s+compras?\s+(?:mayores?\s+)?(?:a|de)\s+\$?\s*([\d.,]+)',
            r'[Ss]upere[ns]?\s+(?:los\s+)?\$?\s*([\d.,]+)',
        ]
        
        for pattern in minimo_patterns:
            minimo_match = re.search(pattern, text, re.I)
            if minimo_match:
                amount = minimo_match.group(1).replace('.', '').replace(',', '.')
                try:
                    amount_num = float(amount)
                    promo['monto_minimo'] = f"${amount_num:,.0f}".replace(',', '.')
                except:
                    promo['monto_minimo'] = f"${minimo_match.group(1)}"
                break
        
        # Si no hay mínimo explícito, buscar "sin mínimo"
        if not promo.get('monto_minimo'):
            if re.search(r'sin\s+m[ií]nimo|sin\s+compra\s+m[ií]nima', text, re.I):
                promo['monto_minimo'] = 'Sin mínimo'
        
        # 8. Extraer vigencia (fechas) - mejorado para "Ver legal"
        
        # Mapeo de meses en texto a número
        meses_map = {
            'enero': '01', 'febrero': '02', 'marzo': '03', 'abril': '04',
            'mayo': '05', 'junio': '06', 'julio': '07', 'agosto': '08',
            'septiembre': '09', 'setiembre': '09', 'octubre': '10', 
            'noviembre': '11', 'diciembre': '12'
        }
        
        # Patrón para fechas en formato textual: "1 de diciembre de 2025 al 28 de febrero de 2026"
        # o "del 1 de diciembre de 2025 al 28 de febrero de 2026"
        textual_date_pattern = r'(?:del?\s+)?(\d{1,2})\s+de\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)\s+(?:de\s+)?(\d{4})\s+(?:al?|hasta)\s+(?:el\s+)?(\d{1,2})\s+de\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)\s+(?:de\s+)?(\d{4})'
        
        textual_match = re.search(textual_date_pattern, text, re.I)
        if textual_match:
            d1, mes1, y1, d2, mes2, y2 = textual_match.groups()
            m1 = meses_map.get(mes1.lower(), '01')
            m2 = meses_map.get(mes2.lower(), '01')
            promo['valid_from'] = f"{d1}/{m1}/{y1}"
            promo['valid_until'] = f"{d2}/{m2}/{y2}"
        
        # Si no encontramos formato textual, buscar formato numérico
        if not promo.get('valid_from'):
            vigencia_patterns = [
                # Formato: "VIGENCIA DESDE EL 01/10/2025 HASTA EL 31/03/2026"
                r'[Vv][Ii][Gg][Ee][Nn][Cc][Ii][Aa]\s+[Dd][Ee][Ss][Dd][Ee]\s+[Ee][Ll]\s+(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})\s+[Hh][Aa][Ss][Tt][Aa]\s+[Ee][Ll]\s+(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})',
                # Formato: "DESDE EL 01/10/2025 HASTA EL 31/03/2026" (sin "VIGENCIA")
                r'[Dd][Ee][Ss][Dd][Ee]\s+[Ee][Ll]\s+(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})\s+[Hh][Aa][Ss][Tt][Aa]\s+[Ee][Ll]\s+(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})',
                # Formato: 01/01/2024 al 31/01/2024
                r'(?:desde\s+(?:el\s+)?)?(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})\s*(?:al?|hasta|y\s+el)\s*(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})',
                # Formato: válida desde 01/01/2024 hasta 31/01/2024
                r'(?:v[aá]lid[oa]?\s+)?(?:desde\s+(?:el\s+)?)?(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})\s*(?:al?|hasta)\s*(?:el\s+)?(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})',
                # Formato: vigencia: 01/01/2024 - 31/01/2024
                r'[Vv]igencia[:\s]+(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})\s*[-–]\s*(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})',
            ]
            
            for pattern in vigencia_patterns:
                match = re.search(pattern, text, re.I)
                if match:
                    d1, m1, y1, d2, m2, y2 = match.groups()
                    promo['valid_from'] = f"{d1}/{m1}/{y1}"
                    promo['valid_until'] = f"{d2}/{m2}/{y2}"
                    break
        
        # Si no encontramos rango, buscar fecha única o mes
        if not promo.get('valid_from'):
            # Buscar "válido durante enero 2024" o "vigente en enero"
            mes_vigencia = re.search(r'(?:v[aá]lid[oa]?|vigente?)\s+(?:durante|en|para)\s+(?:el\s+mes\s+de\s+)?(\w+)(?:\s+(?:de\s+)?(\d{4}))?', text, re.I)
            if mes_vigencia:
                mes = mes_vigencia.group(1).title()
                # Evitar capturar palabras que no son meses (como "la", "el", etc.)
                if mes.lower() in meses_map:
                    anio = mes_vigencia.group(2) or '2026'
                    promo['valid_from'] = f"{mes} {anio}"
                    promo['valid_until'] = f"{mes} {anio}"
            
            # Buscar "todos los [días] de [mes]"
            todos_dias_mes = re.search(r'todos\s+los\s+(?:lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bados?|domingos?)\s+de\s+(\w+)', text, re.I)
            if todos_dias_mes:
                mes = todos_dias_mes.group(1).title()
                if mes.lower() in meses_map:
                    promo['valid_from'] = f"{mes}"
                    promo['valid_until'] = f"{mes}"
        
        # 9. Extraer tarjetas aceptadas (mejorado para "Ver legal")
        tarjetas = []
        # Patrones más amplios para capturar tarjetas
        if re.search(r'\bVISA\b', text, re.I):
            tarjetas.append('Visa')
        if re.search(r'\bMASTERCARD\b|\bMASTER\s*CARD\b|\bMASTER\b', text, re.I):
            tarjetas.append('Mastercard')
        if re.search(r'\bCABAL\b', text, re.I):
            tarjetas.append('Cabal')
        if re.search(r'\bAMERICAN\s*EXPRESS\b|\bAMEX\b', text, re.I):
            tarjetas.append('American Express')
        if re.search(r'\bNARANJA(?!\s*X)\b', text, re.I):  # Naranja pero no Naranja X (billetera)
            tarjetas.append('Naranja')
        if re.search(r'\bMAESTRO\b', text, re.I):
            tarjetas.append('Maestro')
        if re.search(r'\bDINERS\b', text, re.I):
            tarjetas.append('Diners')
        # Buscar también patrones como "tarjetas de crédito Visa y Mastercard"
        tarjeta_match = re.search(r'tarjetas?\s+(?:de\s+)?(?:cr[eé]dito|d[eé]bito)\s+([^.]+?)(?:\.|$)', text, re.I)
        if tarjeta_match:
            tarjeta_text = tarjeta_match.group(1)
            if 'visa' in tarjeta_text.lower() and 'Visa' not in tarjetas:
                tarjetas.append('Visa')
            if re.search(r'master', tarjeta_text, re.I) and 'Mastercard' not in tarjetas:
                tarjetas.append('Mastercard')
        if tarjetas:
            promo['card_types'] = ', '.join(tarjetas)
        
        # 10. Tipo de pago (crédito/débito)
        payment_types = []
        if re.search(r'cr[eé]dito', text, re.I):
            payment_types.append('Crédito')
        if re.search(r'd[eé]bito', text, re.I):
            payment_types.append('Débito')
        if payment_types:
            promo['payment_type'] = ', '.join(payment_types)
        
        # 11. Extraer dónde aplica (Sucursal, MásOnline) - mejorado
        aplica_en = []
        # Patrones más específicos para "Ver legal"
        if re.search(r'[Ss]ucursal(?:es)?|[Tt]ienda(?:s)?\s+f[ií]sica|local(?:es)?|presencial', text, re.I):
            aplica_en.append('Sucursal')
        if re.search(r'M[aá]s\s*Online|[Oo]nline|[Ww]eb|[Ee]-?commerce|compra(?:s)?\s+(?:por\s+)?internet|www\.', text, re.I):
            aplica_en.append('MásOnline')
        # Buscar "Pagando: Sucursal y MásOnline" en el header
        pagando_match = re.search(r'[Pp]agando[:\s]+([^.]+)', text)
        if pagando_match:
            pagando_text = pagando_match.group(1).lower()
            if 'sucursal' in pagando_text and 'Sucursal' not in aplica_en:
                aplica_en.append('Sucursal')
            if 'online' in pagando_text and 'MásOnline' not in aplica_en:
                aplica_en.append('MásOnline')
        # Si no encontramos nada específico pero hay indicios
        if not aplica_en:
            if re.search(r'v[aá]lid[oa]\s+(?:para\s+)?(?:compras?\s+)?(?:en\s+)?(?:sucursal|tienda|local)', text, re.I):
                aplica_en.append('Sucursal')
            if re.search(r'v[aá]lid[oa]\s+(?:para\s+)?(?:compras?\s+)?(?:en\s+)?(?:online|web|internet)', text, re.I):
                aplica_en.append('MásOnline')
        if aplica_en:
            promo['aplica_en'] = ', '.join(aplica_en)
        
        # 12. Extraer bancos participantes/seleccionados
        if re.search(r'bancos\s+seleccionados', text, re.I):
            promo['bancos_info'] = 'Bancos seleccionados'
            # Buscar lista específica si existe
            bancos_match = re.search(r'(?:[Pp]articipan|[Bb]ancos)[:\s]+(.+?)(?:\.|$)', text)
            if bancos_match:
                bancos_list = re.findall(r'Banco\s+[\w\s]+|\bICBC\b|\bBBVA\b|\bHSBC\b', bancos_match.group(1), re.I)
                if bancos_list:
                    promo['bancos_participantes'] = ', '.join([b.strip() for b in bancos_list[:10]])
        
        # 13. Información financiera (TNA, TEA, CFT)
        tna_match = re.search(r'(?:TNA|[Tt]asa\s+[Nn]ominal\s+[Aa]nual)[:\s]*(\d+[,.]?\d*)\s*%', text)
        if tna_match:
            promo['tna'] = f"{tna_match.group(1)}%"
        
        tea_match = re.search(r'(?:TEA|[Tt]asa\s+[Ee]fectiva\s+[Aa]nual)[:\s]*(\d+[,.]?\d*)\s*%', text)
        if tea_match:
            promo['tea'] = f"{tea_match.group(1)}%"
        
        cft_match = re.search(r'(?:CFT|[Cc]osto\s+[Ff]inanciero\s+[Tt]otal)[^:]*[:\s]*(\d+[,.]?\d*)\s*%', text)
        if cft_match:
            promo['cft'] = f"{cft_match.group(1)}%"
        
        # 14. Acumulable - mejorado para "Ver legal"
        if re.search(r'[Nn]o\s+(?:es\s+)?acumulable|[Nn]o\s+acumula|no\s+se\s+acumula|incompatible\s+con\s+otras', text, re.I):
            promo['acumulable'] = 'No'
        elif re.search(r'[Aa]cumulable|se\s+puede\s+acumular|compatible\s+con\s+otras', text, re.I):
            promo['acumulable'] = 'Sí'
        # Muchas promos por defecto no son acumulables
        elif re.search(r'promoci[oó]n|beneficio|descuento|reintegro', text, re.I):
            # Si hay texto legal pero no menciona acumulable, asumir que no
            if re.search(r'[Vv]er\s+legal|[Tt][eé]rminos|[Cc]ondiciones', text):
                promo['acumulable'] = 'No (por defecto)'
        
        # 15. Extraer exclusiones
        exclusions_parts = []
        
        # "quedan excluidos..."
        excluidos_match = re.search(r'[Qq]uedan\s+excluidos?\s+(.+?)(?:\.|$)', text)
        if excluidos_match:
            exclusions_parts.append(excluidos_match.group(1).strip()[:200])
        
        # "No válido para..."
        no_valido = re.findall(r'[Nn]o\s+v[aá]lido\s+(?:para\s+)?([^.]+?)(?:\.|$)', text)
        for match in no_valido:
            exclusions_parts.append(f"No válido {match.strip()}")
        
        if exclusions_parts:
            promo['exclusions'] = ' | '.join(exclusions_parts)[:1000]
        
        # 15.5 Extraer exclusiones de sucursales específicas
        # Busca patrones como "Excluye sucursal Luján", "No aplica en sucursales X, Y, Z"
        sucursales_excluidas = []
        
        # "Excluye sucursal(es) X"
        excluye_suc = re.findall(r'[Ee]xcluye[ns]?\s+(?:la\s+)?sucursale?s?\s+([^.]+?)(?:\.|$)', text)
        for match in excluye_suc:
            sucursales_excluidas.append(match.strip())
        
        # "Excluye tiendas de X"
        excluye_tiendas = re.findall(r'[Ee]xcluye[ns]?\s+(?:las\s+)?tiendas?\s+(?:de\s+)?([^.]+?)(?:\.|$)', text)
        for match in excluye_tiendas:
            sucursales_excluidas.append(match.strip())
        
        # "No aplica en sucursal(es) X"
        no_aplica_suc = re.findall(r'[Nn]o\s+aplica\s+(?:en\s+)?(?:la\s+)?sucursale?s?\s+([^.]+?)(?:\.|$)', text)
        for match in no_aplica_suc:
            sucursales_excluidas.append(match.strip())
        
        # "No válido en sucursal(es) X"
        no_valido_suc = re.findall(r'[Nn]o\s+v[aá]lido\s+(?:en\s+)?(?:la\s+)?sucursale?s?\s+([^.]+?)(?:\.|$)', text)
        for match in no_valido_suc:
            sucursales_excluidas.append(match.strip())
        
        if sucursales_excluidas:
            promo['sucursales_excluidas'] = ', '.join(sucursales_excluidas)[:500]
        
        # 16. Extraer plazo de acreditación del reintegro/descuento
        # Busca frases como "se verán reflejados en la cuenta... en los 30 días posteriores a la compra"
        # o "el reintegro se acreditará dentro de los 10 días hábiles"
        acreditacion_patterns = [
            # "en los X días posteriores a la compra"
            r'(?:reflejad[oa]s?|acreditad[oa]s?|ver[aá]n?\s+reflejad[oa]s?).*?(?:en\s+)?(?:los\s+)?(\d+)\s*d[ií]as?\s*(?:h[aá]biles?\s*)?(?:posteriores?|siguientes?|despu[eé]s)(?:\s+(?:a|de)\s+la\s+compra)?',
            # "dentro de los X días hábiles"
            r'(?:reintegro|descuento|beneficio).*?(?:dentro\s+de\s+)?(?:los\s+)?(\d+)\s*d[ií]as?\s*h[aá]biles?',
            # "en un plazo de X días"
            r'(?:plazo|t[eé]rmino)\s+(?:de\s+)?(\d+)\s*d[ií]as?',
            # "hasta X días para ver reflejado"
            r'(?:hasta|m[aá]ximo)\s+(\d+)\s*d[ií]as?\s*(?:h[aá]biles?\s*)?(?:para|hasta)\s+(?:ver|que\s+se)',
            # Formato más simple: "X días posteriores"
            r'(\d+)\s*d[ií]as?\s*(?:h[aá]biles?\s*)?posteriores?\s+a\s+la\s+compra',
        ]
        
        for pattern in acreditacion_patterns:
            acred_match = re.search(pattern, text, re.I)
            if acred_match:
                dias = acred_match.group(1)
                # Determinar si son días hábiles o corridos
                is_habiles = bool(re.search(r'h[aá]biles?', acred_match.group(0), re.I))
                tipo_dias = 'días hábiles' if is_habiles else 'días'
                promo['plazo_acreditacion'] = f"{dias} {tipo_dias} posteriores a la compra"
                break
        
        # 17. Mes específico si aplica
        mes_match = re.search(r'(Lunes|Martes|Mi[eé]rcoles|Jueves|Viernes|S[aá]bado|Domingo)\s+de\s+(\w+)', text, re.I)
        if mes_match:
            promo['mes'] = mes_match.group(2).title()
        
        # 17. Construir título
        title_parts = []
        if promo.get('bank'):
            title_parts.append(promo['bank'])
        
        # Agregar billetera virtual si existe
        if promo.get('billetera_virtual'):
            title_parts.append(f"(vía {promo['billetera_virtual']})")
        
        if promo.get('discount'):
            title_parts.append(promo['discount'])
        
        if promo.get('payment_type'):
            title_parts.append(f"({promo['payment_type']})")
        
        title_parts.append(f"- {promo.get('valid_days', dia_nombre)}")
        
        if title_parts:
            promo['title'] = ' '.join(title_parts)
        else:
            promo['title'] = text[:80]
        
        return promo
    
    def _extract_valid_days(self, text: str, default_day: str) -> str:
        """Extrae los días válidos del texto de la promoción.
        
        Busca patrones como:
        - "todos los días"
        - "todos los lunes y jueves"
        - "lunes, martes y miércoles"
        - "válido lunes a viernes"
        - "de lunes a domingo"
        
        Si no encuentra nada, devuelve el día de la solapa (default_day).
        """
        text_lower = text.lower()
        
        # Patrón especial: "Todos los días"
        if re.search(r'todos\s+los\s+d[ií]as', text_lower):
            return 'Todos los días'
        
        # Patrón especial: "Toda la semana"
        if re.search(r'toda\s+la\s+semana', text_lower):
            return 'Todos los días'
        
        # Patrón especial: "Válido cualquier día"
        if re.search(r'v[aá]lid[oa]\s+(?:cualquier|todos?\s+los?)\s+d[ií]as?', text_lower):
            return 'Todos los días'
        
        # Patrón especial: "de lunes a domingo" o "lunes a domingo" (toda la semana)
        if re.search(r'(?:de\s+)?lunes\s+a\s+domingo', text_lower):
            return 'Todos los días'
        
        # Patrón especial: "válida de lunes a domingo"
        if re.search(r'v[aá]lid[oa]\s+(?:de\s+)?lunes\s+a\s+domingo', text_lower):
            return 'Todos los días'
        
        # Mapeo de días normalizados
        dias_map = {
            'lunes': 'Lunes',
            'martes': 'Martes',
            'miercoles': 'Miércoles',
            'miércoles': 'Miércoles',
            'jueves': 'Jueves',
            'viernes': 'Viernes',
            'sabado': 'Sábado',
            'sábado': 'Sábado',
            'sabados': 'Sábado',
            'sábados': 'Sábado',
            'domingo': 'Domingo',
            'domingos': 'Domingo',
        }
        
        found_days = set()
        
        # Patrón 1: "todos los lunes y jueves", "los lunes y jueves"
        pattern_y = r'(?:todos\s+)?(?:los\s+)?(lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bados?|domingos?)\s+y\s+(lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bados?|domingos?)'
        match = re.search(pattern_y, text_lower)
        if match:
            for g in match.groups():
                if g:
                    normalized = dias_map.get(g.lower())
                    if normalized:
                        found_days.add(normalized)
        
        # Patrón 2: "lunes, martes y miércoles" (lista con comas)
        pattern_lista = r'(lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bados?|domingos?)(?:\s*,\s*(lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bados?|domingos?))+(?:\s+y\s+(lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bados?|domingos?))?'
        match = re.search(pattern_lista, text_lower)
        if match:
            # Extraer todos los días mencionados
            all_days = re.findall(r'(lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bados?|domingos?)', match.group(0))
            for d in all_days:
                normalized = dias_map.get(d.lower())
                if normalized:
                    found_days.add(normalized)
        
        # Patrón 3: "de lunes a viernes", "lunes a domingo"
        pattern_rango = r'(?:de\s+)?(lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bados?|domingos?)\s+a\s+(lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bados?|domingos?)'
        match = re.search(pattern_rango, text_lower)
        if match:
            dia_inicio = match.group(1).lower()
            dia_fin = match.group(2).lower()
            
            # Orden de días
            orden_dias = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
            dias_alt = {
                'miercoles': 'miércoles',
                'sabado': 'sábado',
                'sabados': 'sábado',
                'sábados': 'sábado',
                'domingos': 'domingo',
            }
            
            dia_inicio = dias_alt.get(dia_inicio, dia_inicio)
            dia_fin = dias_alt.get(dia_fin, dia_fin)
            
            try:
                idx_inicio = orden_dias.index(dia_inicio)
                idx_fin = orden_dias.index(dia_fin)
                
                # Si es lunes a domingo, es todos los días
                if idx_inicio == 0 and idx_fin == 6:
                    return 'Todos los días'
                
                for i in range(idx_inicio, idx_fin + 1):
                    found_days.add(dias_map.get(orden_dias[i], orden_dias[i].title()))
            except ValueError:
                pass
        
        # Si encontramos todos los 7 días, simplificar
        if len(found_days) == 7:
            return 'Todos los días'
        
        # Si encontramos días, devolverlos ordenados
        if found_days:
            orden = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
            sorted_days = sorted(found_days, key=lambda x: orden.index(x) if x in orden else 99)
            return ', '.join(sorted_days)
        
        # Si no encontramos nada, devolver el día de la solapa
        return default_day
    
    def _identify_bank_and_wallet(self, text: str, img_alt: str = '') -> tuple:
        """Identifica el banco Y la billetera virtual del texto y/o de la imagen.
        
        Args:
            text: Texto de la promoción (incluyendo "Ver legal")
            img_alt: Texto alternativo de la imagen del logo
            
        Returns:
            tuple: (banco, billetera_virtual) - billetera puede ser None
        """
        combined_text = f"{text} {img_alt}"
        text_upper = combined_text.upper()
        
        bank = None
        wallet = None
        
        # Lista de billeteras virtuales
        wallet_patterns = [
            (r'\bMODO\b', 'MODO'),
            (r'MERCADO\s*PAGO', 'Mercado Pago'),
            (r'\bPREX\b', 'Prex'),
            (r'PERSONAL\s*PAY', 'Personal Pay'),
            (r'CUENTA\s*DNI', 'Cuenta DNI'),
            (r'\bUAL[AÁ]\b', 'Ualá'),
            (r'NARANJA\s*X', 'Naranja X'),
            (r'\bYAPE\b', 'Yape'),
            (r'\bBNA\+\b|\bBNA\s*MAS\b', 'BNA+'),
        ]
        
        # Lista de programas de fidelidad/clubes (prioridad alta - detectar primero)
        loyalty_patterns = [
            (r'M[AÂ]S\s*CLUB|MASCLUB', 'MásClub'),
            (r'CLUB\s*DIA|CLUB\s*D[IÍ]A', 'Club Día'),
            (r'CLUB\s*CARREFOUR', 'Club Carrefour'),
            (r'COMUNIDAD\s*COTO', 'Comunidad Coto'),
        ]
        
        # Lista de beneficiarios especiales (empleados, jubilados, etc.)
        beneficiary_patterns = [
            (r'EMPLEADOS?\s+MUNICIPALES?', 'Empleados Municipales'),
            (r'EMPLEADOS?\s+PROVINCIALES?', 'Empleados Provinciales'),
            (r'EMPLEADOS?\s+P[UÚ]BLICOS?', 'Empleados Públicos'),
            (r'JUBILADOS?\s+Y\s+PENSIONADOS?', 'Jubilados y Pensionados'),
            (r'JUBILADOS?', 'Jubilados'),
            (r'PENSIONADOS?', 'Pensionados'),
            (r'ANSES', 'ANSES'),
        ]
        
        # Lista de bancos
        # IMPORTANTE: Los patrones deben ser específicos para evitar falsos positivos
        # Ej: "Patagonia" es también una marca de cerveza, así que buscamos "BANCO PATAGONIA"
        bank_patterns = [
            (r'COMAFI', 'Banco Comafi'),
            (r'GALICIA', 'Banco Galicia'),
            (r'MACRO', 'Banco Macro'),
            (r'NACI[OÓ]N|(?<!\+)BNA(?!\+)', 'Banco Nación'),
            # Ciudad: debe estar precedido por "BANCO" para evitar confusión con "Ciudad de X"
            (r'BANCO\s+CIUDAD|\bCIUDAD\s+BANCO\b', 'Banco Ciudad'),
            # Provincia: debe estar precedido por "BANCO" para evitar confusión con "Provincia de X"
            (r'BANCO\s+PROVINCIA|\bPROVINCIA\s+BANCO\b|BAPRO\b', 'Banco Provincia'),
            (r'SANTANDER', 'Banco Santander'),
            # Patagonia: debe estar precedido por "BANCO" para evitar confusión con cerveza Patagonia
            (r'BANCO\s+PATAGONIA|\bPATAGONIA\s+BANCO\b', 'Banco Patagonia'),
            (r'SUPERVIELLE', 'Supervielle'),
            (r'HIPOTECARIO', 'Banco Hipotecario'),
            (r'CREDICOOP', 'Banco Credicoop'),
            (r'\bHSBC\b', 'HSBC'),
            (r'\bBBVA\b', 'BBVA'),
            (r'\bICBC\b', 'ICBC'),
            (r'BRUBANK', 'Brubank'),
            (r'WILOBANK', 'Wilobank'),
            (r'BIND|INDUSTRIAL', 'Banco Industrial'),
            (r'FRANCES', 'Banco Francés'),
            (r'ITAU|ITA[UÚ]', 'Itaú'),
            # Columbia: evitar falsos positivos con marcas
            (r'BANCO\s+COLUMBIA', 'Banco Columbia'),
            (r'PIANO', 'Banco Piano'),
            (r'BICA', 'Banco BICA'),
            (r'ROELA', 'Banco Roela'),
            (r'SAN JUAN', 'Banco San Juan'),
            (r'SANTA FE', 'Banco Santa Fe'),
            (r'ENTRE R[IÍ]OS', 'Banco Entre Ríos'),
            (r'CHUBUT', 'Banco Chubut'),
            (r'NEUQU[EÉ]N', 'Banco Neuquén'),
            (r'TIERRA DEL FUEGO', 'Banco Tierra del Fuego'),
            (r'CORRIENTES', 'Banco Corrientes'),
            (r'FORMOSA', 'Banco Formosa'),
            # Tarjetas regionales/especiales
            # SOL: buscar "TARJETA SOL", "SOL" como palabra aislada (en contexto de tarjeta), o "(SL)" como código
            (r'TARJETA\s+SOL|(?:TARJETA|CR[EÉ]DITO|D[EÉ]BITO)\s+(?:DE\s+)?SOL|\bSOL\b\s*(?:CR[EÉ]DITO|D[EÉ]BITO)|\(SL\)', 'Tarjeta Sol'),
            (r'TARJETA\s+NEVADA|NEVADA', 'Tarjeta Nevada'),
            (r'TARJETA\s+GRUPAR|GRUPAR', 'Tarjeta Grupar'),
            (r'TARJETA\s+CORDOBESA|CORDOBESA', 'Tarjeta Cordobesa'),
            (r'TARJETA\s+SHOPPING', 'Tarjeta Shopping'),
            (r'TARJETA\s+NATIVA|NATIVA', 'Tarjeta Nativa'),
            (r'CMR\s*FALABELLA|CMR', 'CMR Falabella'),
            (r'CENCOSUD', 'Tarjeta Cencosud'),
        ]
        
        # 0. PRIMERO: Buscar programas de fidelidad (MásClub, Club Día, etc.)
        # Estos tienen prioridad sobre bancos porque son promociones del supermercado
        loyalty_program = None
        for pattern, name in loyalty_patterns:
            if re.search(pattern, text_upper):
                loyalty_program = name
                break
        
        # Si encontramos un programa de fidelidad, usarlo como entidad principal
        if loyalty_program:
            return (loyalty_program, None)
        
        # 0.5. Buscar beneficiarios especiales (Empleados Municipales, Jubilados, etc.)
        # Estos también tienen prioridad sobre bancos
        # Buscar tanto en texto como en img_alt (ANSES suele estar como imagen/logo)
        beneficiary = None
        search_text = text_upper
        if img_alt:
            search_text = f"{text_upper} {img_alt.upper()}"
        
        for pattern, name in beneficiary_patterns:
            if re.search(pattern, search_text):
                beneficiary = name
                break
        
        # Si encontramos un beneficiario especial, usarlo como entidad principal
        if beneficiary:
            return (beneficiary, None)
        
        # 1. Buscar en el alt de la imagen (más confiable para el banco principal)
        if img_alt:
            img_alt_upper = img_alt.upper()
            
            # Buscar programa de fidelidad en imagen primero
            for pattern, name in loyalty_patterns:
                if re.search(pattern, img_alt_upper):
                    return (name, None)
            
            # Buscar banco en imagen
            for pattern, name in bank_patterns:
                if re.search(pattern, img_alt_upper):
                    bank = name
                    break
            
            # Buscar billetera en imagen
            for pattern, name in wallet_patterns:
                if re.search(pattern, img_alt_upper):
                    wallet = name
                    break
        
        # 2. Si no encontramos banco en imagen, buscar en texto
        if not bank:
            for pattern, name in bank_patterns:
                if re.search(pattern, text_upper):
                    bank = name
                    break
        
        # 3. Buscar billetera en texto si no la encontramos en imagen
        if not wallet:
            for pattern, name in wallet_patterns:
                if re.search(pattern, text_upper):
                    wallet = name
                    break
        
        # 4. Si hay MODO mencionado en cualquier lado, registrarlo como billetera
        if not wallet and re.search(r'\bMODO\b', text_upper):
            wallet = 'MODO'
        
        # 5. Si no encontramos banco pero sí billetera, la billetera puede ser el "banco"
        #    Solo si es una billetera que actúa como entidad financiera (ej: Mercado Pago, Ualá)
        if not bank and wallet:
            # Estas billeteras pueden ser la entidad principal
            standalone_wallets = ['Mercado Pago', 'Ualá', 'Naranja X', 'Prex', 'Personal Pay', 'Cuenta DNI']
            if wallet in standalone_wallets:
                bank = wallet
                wallet = None
            # Si es MODO con múltiples bancos, MODO es la billetera y el banco queda genérico
            elif wallet == 'MODO':
                num_bancos = len(re.findall(r'BANCO\s+\w+', text_upper))
                if num_bancos > 2:
                    bank = 'Bancos participantes'
        
        # 6. Si aún no hay banco, buscar Visa/Mastercard genérico
        if not bank:
            if re.search(r'VISA.*MASTERCARD|MASTERCARD.*VISA', text_upper):
                bank = 'Visa/Mastercard'
            elif re.search(r'\bVISA\b', text_upper):
                bank = 'Visa'
            elif re.search(r'\bMASTERCARD\b|\bMASTER\b', text_upper):
                bank = 'Mastercard'
        
        return (bank or '', wallet)


async def main():
    scraper = MasOnlineScraper()
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
            if promo.get('billetera_virtual'):
                print(f"   📱 Billetera Virtual: {promo.get('billetera_virtual')}")
            print(f"   💳 Tarjetas: {promo.get('card_types', 'N/A')}")
            print(f"   💵 Tipo pago: {promo.get('payment_type', 'N/A')}")
            print(f"   📅 Días válidos: {promo.get('valid_days', 'N/A')}")
            print(f"   📆 Vigencia: {promo.get('valid_from', 'N/A')} → {promo.get('valid_until', 'N/A')}")
            print(f"   🏪 Aplica en: {promo.get('aplica_en', 'N/A')}")
            print(f"   💵 Tope: {promo.get('tope', 'N/A')}")
            print(f"   💰 Monto mínimo: {promo.get('monto_minimo', 'N/A')}")
            print(f"   🔁 Acumulable: {promo.get('acumulable', 'N/A')}")
            
            if promo.get('bancos_participantes'):
                print(f"   🏦 Bancos participantes: {promo['bancos_participantes'][:100]}...")
            
            if promo.get('tna') or promo.get('tea') or promo.get('cft'):
                print(f"   📊 TNA: {promo.get('tna', 'N/A')} | TEA: {promo.get('tea', 'N/A')} | CFT: {promo.get('cft', 'N/A')}")
            
            if promo.get('plazo_acreditacion'):
                print(f"   ⏱️  Acreditación: {promo['plazo_acreditacion']}")
            
            if promo.get('exclusions'):
                print(f"   ⛔ Exclusiones: {promo['exclusions'][:150]}...")
            
            if promo.get('sucursales_excluidas'):
                print(f"   🏪 Sucursales excluidas: {promo['sucursales_excluidas']}")
            
            print(f"   🔗 URL: {promo.get('url', 'N/A')}")
            
            raw_text = promo.get('raw_text', '')
            if raw_text:
                print(f"   📝 Texto: {raw_text[:300]}...")
    else:
        print("\n⚠️  No se encontraron promociones.")
        print("   Revisa debug_masonline.html y debug_masonline.png para analizar la estructura.")


if __name__ == "__main__":
    asyncio.run(main())

