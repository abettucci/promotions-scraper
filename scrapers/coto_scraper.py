#!/usr/bin/env python3
"""
Scraper de Coto Digital - Promociones Bancarias
- Extrae promociones bancarias de https://www.cotodigital.com.ar/sitios/cdigi/terminos-descuentos
- Esta página tiene toda la información detallada: términos, exclusiones, vigencia, etc.
"""
import asyncio
import re
from typing import List, Dict

from playwright.async_api import async_playwright
from bs4 import BeautifulSoup


class CotoScraper:
    def __init__(self):
        self.name = 'Coto Digital'
        self.url = 'https://www.cotodigital.com.ar/sitios/cdigi/terminos-descuentos'
        
    async def scrape(self) -> List[Dict]:
        """Scraping de promociones bancarias de Coto Digital"""
        print(f"\n🔍 Scraping {self.name} - Términos y Condiciones de Descuentos...")
        print(f"   🌐 URL: {self.url}")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            
            try:
                context = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                )
                
                page = await context.new_page()
                
                # 1. Navegar a la página
                print(f"\n   📡 Navegando...")
                await page.goto(self.url, wait_until='networkidle', timeout=60000)
                
                # 2. Esperar a que cargue el contenido
                print(f"\n   ⏳ Esperando carga de contenido...")
                await asyncio.sleep(3)
                
                # 3. Scroll para cargar todo el contenido
                print(f"\n   📜 Haciendo scroll para cargar contenido...")
                await self._scroll_full_page(page)
                
                # 4. Obtener HTML
                html = await page.content()
                
                # 5. Guardar HTML para debug
                with open('debug_coto_terminos.html', 'w', encoding='utf-8') as f:
                    f.write(html)
                print(f"\n   📸 Debug: debug_coto_terminos.html guardado")
                
                # 6. Tomar screenshot
                await page.screenshot(path='debug_coto_terminos.png', full_page=True)
                print(f"   📸 Debug: debug_coto_terminos.png guardado")
                
                # 7. Extraer promociones bancarias
                print(f"\n   🔍 Extrayendo promociones bancarias...")
                promotions = self._extract_promotions(html)
                
                print(f"\n✅ {self.name}: {len(promotions)} promociones bancarias encontradas")
                
                return promotions
                
            except Exception as e:
                print(f"\n   ❌ Error: {e}")
                import traceback
                traceback.print_exc()
                return []
            finally:
                await browser.close()
    
    async def _scroll_full_page(self, page):
        """Hace scroll completo de la página para cargar todo el contenido"""
        # Scroll progresivo
        for i in range(20):
            await page.evaluate(f'window.scrollBy(0, 500)')
            await asyncio.sleep(0.2)
        
        # Scroll hasta el final
        await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
        await asyncio.sleep(1)
        
        # Volver arriba
        await page.evaluate('window.scrollTo(0, 0)')
        await asyncio.sleep(0.5)
    
    def _extract_promotions(self, html: str) -> List[Dict]:
        """Extrae promociones del HTML de términos y condiciones"""
        soup = BeautifulSoup(html, 'html.parser')
        promotions = []
        
        # Buscar bloques de texto que contengan patrones de promociones bancarias
        all_text_blocks = soup.find_all(['div', 'p', 'section', 'article'])
        
        promo_blocks = []
        for block in all_text_blocks:
            text = block.get_text(' ', strip=True)
            # Un bloque de promoción típicamente tiene: banco + descuento/cuotas + vigencia
            has_bank = bool(re.search(r'banco|macro|nacion|ciudad|galicia|provincia|santander|hsbc|bbva|icbc|naranja|mercado\s*pago|modo\b|patagonia|supervielle|credicoop|hipotecario|comafi|uala|personal\s*pay|cuenta\s*dni', text, re.I))
            has_discount = bool(re.search(r'\d+\s*%|cuotas?\s*sin\s*inter[eé]s|reintegro|descuento', text, re.I))
            
            # Si tiene al menos banco + descuento, es candidato
            if has_bank and has_discount and len(text) > 200 and len(text) < 10000:
                promo_blocks.append(block)
        
        print(f"      Bloques de promociones candidatos: {len(promo_blocks)}")
        
        # Procesar bloques encontrados
        seen_texts = set()
        
        for block in promo_blocks:
            text = block.get_text(' ', strip=True)
            
            # Evitar duplicados (usar primeros 150 chars como key)
            text_key = text[:150]
            if text_key in seen_texts:
                continue
            seen_texts.add(text_key)
            
            # Extraer promoción
            promo = self._parse_promo_text(text)
            
            if promo and promo.get('bank'):
                promotions.append(promo)
                self._print_promo(len(promotions), promo)
        
        # Si no encontramos con la estrategia anterior, intentar parsear todo el texto
        if not promotions:
            print(f"\n      🔄 Intentando extracción alternativa del texto completo...")
            promotions = self._extract_from_full_text(soup)
        
        return promotions
    
    def _parse_promo_text(self, text: str) -> Dict:
        """Parsea un bloque de texto para extraer información de la promoción"""
        promo = {
            'url': self.url,
            'raw_text': text[:2500]
        }
        
        # 1. Identificar banco
        promo['bank'] = self._identify_bank(text)
        
        # 2. Extraer descuento porcentual
        discount_patterns = [
            r'(\d+)\s*%\s*(?:DE\s+)?(?:DESCUENTO|REINTEGRO|DEVOLUCIÓN|DEVOLUCION)',
            r'(?:DESCUENTO|REINTEGRO|DEVOLUCIÓN|DEVOLUCION)\s*(?:DEL?\s+)?(\d+)\s*%',
        ]
        
        for pattern in discount_patterns:
            match = re.search(pattern, text, re.I)
            if match:
                promo['discount'] = f"{match.group(1)}%"
                break
        
        # 3. Extraer cuotas sin interés
        cuotas_patterns = [
            r'(\d+)\s*CUOTAS?\s*SIN\s*INTER[EÉ]S',
            r'HASTA\s+(\d+)\s*CUOTAS?\s*SIN\s*INTER[EÉ]S',
            r'(\d+)\s*(?:A\s+)?(\d+)\s*CUOTAS?\s*SIN\s*INTER[EÉ]S',
        ]
        
        for pattern in cuotas_patterns:
            match = re.search(pattern, text, re.I)
            if match:
                if match.lastindex >= 2 and match.group(2):
                    promo['cuotas'] = f"{match.group(1)}-{match.group(2)} cuotas sin interés"
                else:
                    promo['cuotas'] = f"{match.group(1)} cuotas sin interés"
                if not promo.get('discount'):
                    promo['discount'] = promo['cuotas']
                break
        
        _DAY_NAMES = r'(?:LUNES|MARTES|MI[EÉ]RCOLES|JUEVES|VIERNES|S[AÁ]BADO|DOMINGO)'
        _MONTHS_ES = {
            'enero': '01', 'febrero': '02', 'marzo': '03', 'abril': '04',
            'mayo': '05', 'junio': '06', 'julio': '07', 'agosto': '08',
            'septiembre': '09', 'octubre': '10', 'noviembre': '11', 'diciembre': '12',
        }

        # Patrón especial: "SÁBADO 16, DOMINGO 17 Y LUNES 18 DE MAYO DE 2026"
        # → tomar el último día como valid_until, el primero como valid_from
        specific_dates_match = re.search(
            rf'({_DAY_NAMES})\s+(\d{{1,2}})(?:\s*,\s*{_DAY_NAMES}\s+\d{{1,2}})*\s*(?:,?\s*Y\s+{_DAY_NAMES}\s+(\d{{1,2}}))?\s+DE\s+(\w+)(?:\s+DE\s+(\d{{4}}))?',
            text, re.I
        )
        if specific_dates_match:
            g = specific_dates_match.groups()
            first_day_num, last_day_num, month_name, year = g[1], g[2] or g[1], g[3], g[4]
            mo = _MONTHS_ES.get(month_name.lower())
            yr = year or str(__import__('datetime').date.today().year)
            if mo:
                promo['valid_from'] = f"{yr}-{mo}-{int(first_day_num):02d}"
                promo['valid_until'] = f"{yr}-{mo}-{int(last_day_num):02d}"
            # Extraer días de la semana mencionados
            day_mentions = re.findall(rf'\b({_DAY_NAMES})\b', specific_dates_match.group(0), re.I)
            if day_mentions:
                promo['valid_days'] = ', '.join(d.capitalize() for d in dict.fromkeys(day_mentions))

        # 4. Extraer días válidos y vigencia completa
        # Patrón más completo: "LOS DÍAS LUNES DESDE EL 01 DE ENERO HASTA EL 31 DE ENERO DE 2026"
        vigencia_patterns = [
            # "LOS DÍAS LUNES DESDE EL 01 DE ENERO HASTA EL 31 DE ENERO DE 2026"
            r'(?:LOS\s+)?D[IÍ]AS?\s+(LUNES|MARTES|MI[EÉ]RCOLES|JUEVES|VIERNES|S[AÁ]BADO|DOMINGO)(?:\s+Y\s+(LUNES|MARTES|MI[EÉ]RCOLES|JUEVES|VIERNES|S[AÁ]BADO|DOMINGO))?\s+(?:DESDE\s+)?(?:EL\s+)?(\d{1,2})\s+DE\s+(\w+)(?:\s+DE\s+(\d{4}))?\s+HASTA\s+(?:EL\s+)?(\d{1,2})\s+DE\s+(\w+)(?:\s+DE\s+(\d{4}))?',
            # "DESDE EL 01 DE ENERO HASTA EL 31 DE ENERO DE 2026"
            r'DESDE\s+(?:EL\s+)?(\d{1,2})\s+DE\s+(\w+)(?:\s+DE\s+(\d{4}))?\s+HASTA\s+(?:EL\s+)?(\d{1,2})\s+DE\s+(\w+)(?:\s+DE\s+(\d{4}))?',
            # "VÁLIDO TODOS LOS LUNES DE ENERO 2026"
            r'V[AÁ]LIDO\s+(?:PARA\s+)?(?:TODOS\s+)?(?:LOS\s+)?(LUNES|MARTES|MI[EÉ]RCOLES|JUEVES|VIERNES|S[AÁ]BADO|DOMINGO)\s+DE\s+(\w+)\s+(\d{4})',
            # "LOS DÍAS SÁBADO" solo día
            r'(?:LOS\s+)?D[IÍ]AS?\s+(LUNES|MARTES|MI[EÉ]RCOLES|JUEVES|VIERNES|S[AÁ]BADO|DOMINGO)(?:\s+Y\s+(LUNES|MARTES|MI[EÉ]RCOLES|JUEVES|VIERNES|S[AÁ]BADO|DOMINGO))?',
            # "DE LUNES A JUEVES"
            r'DE\s+(LUNES|MARTES|MI[EÉ]RCOLES|JUEVES|VIERNES|S[AÁ]BADO|DOMINGO)\s+A\s+(LUNES|MARTES|MI[EÉ]RCOLES|JUEVES|VIERNES|S[AÁ]BADO|DOMINGO)',
        ]
        
        for pattern in vigencia_patterns:
            match = re.search(pattern, text, re.I)
            if match:
                groups = match.groups()
                
                # Extraer días
                days = [g for g in groups[:2] if g and g.upper() in ['LUNES', 'MARTES', 'MIÉRCOLES', 'MIERCOLES', 'JUEVES', 'VIERNES', 'SÁBADO', 'SABADO', 'DOMINGO']]
                if days:
                    if len(days) == 2:
                        promo['valid_days'] = f"{days[0].title()} y {days[1].title()}"
                    else:
                        promo['valid_days'] = days[0].title()
                
                # Extraer fechas si están presentes
                # Buscar números y meses en los grupos
                date_parts = [g for g in groups if g and (g.isdigit() or re.match(r'^[A-Za-z]+$', g))]
                if len(date_parts) >= 4:
                    # Tenemos fechas desde-hasta
                    try:
                        # Buscar patrón completo de fechas en el texto original
                        full_date_match = re.search(
                            r'(?:DESDE\s+)?(?:EL\s+)?(\d{1,2})\s+DE\s+(\w+)(?:\s+DE\s+(\d{4}))?\s+HASTA\s+(?:EL\s+)?(\d{1,2})\s+DE\s+(\w+)(?:\s+DE\s+(\d{4}))?',
                            text, re.I
                        )
                        if full_date_match:
                            day1, month1, year1, day2, month2, year2 = full_date_match.groups()
                            promo['valid_from'] = f"{day1} de {month1}" + (f" de {year1}" if year1 else "")
                            promo['valid_until'] = f"{day2} de {month2}" + (f" de {year2}" if year2 else "")
                    except:
                        pass
                break
        
        # Si no encontramos vigencia con el patrón anterior, buscar de forma más simple
        if not promo.get('valid_from'):
            simple_date_match = re.search(
                r'DESDE\s+(?:EL\s+)?(\d{1,2})\s+DE\s+(\w+)(?:\s+DE\s+(\d{4}))?\s+HASTA\s+(?:EL\s+)?(\d{1,2})\s+DE\s+(\w+)(?:\s+DE\s+(\d{4}))?',
                text, re.I
            )
            if simple_date_match:
                day1, month1, year1, day2, month2, year2 = simple_date_match.groups()
                promo['valid_from'] = f"{day1} de {month1}" + (f" de {year1}" if year1 else "")
                promo['valid_until'] = f"{day2} de {month2}" + (f" de {year2}" if year2 else "")

        # Patrón especial: "DESDE EL 18 HASTA EL 19 DE JULIO DE 2026" (mismo mes, sin repetir el mes)
        if not promo.get('valid_from'):
            same_month_match = re.search(
                r'DESDE\s+(?:EL\s+)?(\d{1,2})\s+HASTA\s+(?:EL\s+)?(\d{1,2})\s+DE\s+(\w+)(?:\s+DE\s+(\d{4}))?',
                text, re.I
            )
            if same_month_match:
                day1, day2, month_name, year = same_month_match.groups()
                mo = _MONTHS_ES.get(month_name.lower())
                yr = year or str(__import__('datetime').date.today().year)
                if mo:
                    promo['valid_from'] = f"{yr}-{mo}-{int(day1):02d}"
                    promo['valid_until'] = f"{yr}-{mo}-{int(day2):02d}"
        
        # 5. Extraer tope de reintegro/devolución - MEJORADO
        tope_patterns = [
            r'REEMBOLSO\s+M[AÁ]XIMO[:\s]*\$?\s*([\d.,]+)(?:\s*\([^)]+\))?(?:\s*(SEMANAL|MENSUAL|DIARIO|POR\s+CLIENTE))?',
            r'TOPE\s+(?:DE\s+)?(?:REINTEGRO|DEVOLUCI[OÓ]N|DESCUENTO)?[:\s]*\$?\s*([\d.,]+)(?:\s*(SEMANAL|MENSUAL|DIARIO|POR\s+CLIENTE))?',
            r'M[AÁ]XIMO\s+(?:DE\s+)?(?:REINTEGRO|DEVOLUCI[OÓ]N)?[:\s]*\$?\s*([\d.,]+)(?:\s*(SEMANAL|MENSUAL|DIARIO|POR\s+CLIENTE))?',
            r'REINTEGRO\s+(?:M[AÁ]XIMO|HASTA)?[:\s]*\$?\s*([\d.,]+)(?:\s*(SEMANAL|MENSUAL|DIARIO|POR\s+CLIENTE))?',
            r'\$\s*([\d.,]+)\s*(?:\([^)]+\))?\s*(SEMANAL|MENSUAL|DIARIO)?\s*(?:POR\s+CLIENTE)?\s*(?:TOPE|M[AÁ]XIMO)',
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
                    # Buscar si dice "por cliente"
                    if 'POR CLIENTE' in text.upper() and 'por cliente' not in tope_str:
                        tope_str += " por cliente"
                    promo['tope'] = tope_str
                except:
                    promo['tope'] = f"${match.group(1)}"
                break
        
        # 5b. Extraer compra mínima (tope inferior)
        min_purchase_patterns = [
            r'VALID[OA]\s+EN\s+COMPRAS?\s+A\s+PARTIR\s+DE\s+\$\s*([\d.,]+)',
            r'(?:COMPRAS?\s+)?A\s+PARTIR\s+DE\s+\$\s*([\d.,]+)',
            r'COMPRA\s+M[ÍI]NIMA\s+(?:DE\s+)?\$\s*([\d.,]+)',
            r'PAGANDO\s+CON\s+[A-Z\s]+\s+DESDE\s+\$\s*([\d.,]+)',
        ]
        for pattern in min_purchase_patterns:
            match = re.search(pattern, text, re.I)
            if match:
                amount = match.group(1).replace('.', '').replace(',', '.')
                try:
                    amount_num = float(amount)
                    promo['min_purchase'] = f"${amount_num:,.0f}".replace(',', '.')
                except Exception:
                    promo['min_purchase'] = f"${match.group(1)}"
                break

        # 6. Extraer tarjetas aceptadas - MEJORADO
        tarjetas = []
        # Buscar en contexto de "CON TARJETAS" o "EMITIDAS POR"
        tarjetas_match = re.search(r'(?:CON\s+)?TARJETAS?\s+(?:DE\s+)?(?:CR[EÉ]DITO\s+)?(VISA|MASTERCARD|CABAL|AMEX|AMERICAN\s+EXPRESS|NARANJA)(?:\s*,?\s*Y?\s*(VISA|MASTERCARD|CABAL|AMEX|AMERICAN\s+EXPRESS|NARANJA))*', text, re.I)
        
        if re.search(r'\bVISA\b', text, re.I):
            tarjetas.append('Visa')
        if re.search(r'\bMASTERCARD\b|\bMASTER\s*CARD\b', text, re.I):
            tarjetas.append('Mastercard')
        if re.search(r'\bCABAL\b', text, re.I):
            tarjetas.append('Cabal')
        if re.search(r'\bAMEX\b|\bAMERICAN\s*EXPRESS\b', text, re.I):
            tarjetas.append('American Express')
        if re.search(r'\bNARANJA\b', text, re.I):
            tarjetas.append('Naranja')
        if tarjetas:
            promo['card_types'] = ', '.join(tarjetas)
        
        # 7. Extraer tipo de tarjeta (crédito/débito)
        payment_types = []
        if re.search(r'TARJETAS?\s+DE\s+CR[EÉ]DITO', text, re.I):
            payment_types.append('Crédito')
        if re.search(r'TARJETAS?\s+DE\s+D[EÉ]BITO', text, re.I):
            payment_types.append('Débito')
        if payment_types:
            promo['payment_type'] = ', '.join(payment_types)
        
        # 8. Extraer sucursales/provincias donde aplica - NUEVO
        sucursales_patterns = [
            r'V[AÁ]LIDO\s+PARA\s+SUCURSALES\s+(?:COTO\s+)?(?:DE\s+)?([A-ZÁÉÍÓÚÑ,\s]+?)(?:\s+Y\s+COMPRAS|\s*\.|\s+NO\s+)',
            r'SUCURSALES\s+(?:COTO\s+)?(?:DE\s+)?([A-ZÁÉÍÓÚÑ,\s]+?)(?:\s+Y\s+COMPRAS|\s*\.|\s+NO\s+)',
            r'(?:EN\s+)?(?:PROVINCIA[S]?\s+(?:DE\s+)?)?([A-ZÁÉÍÓÚÑ,\s]+?)(?:\s+Y\s+COTO\s+DIGITAL|\s+Y\s+COMPRAS)',
        ]
        
        for pattern in sucursales_patterns:
            match = re.search(pattern, text, re.I)
            if match:
                sucursales = match.group(1).strip()
                # Limpiar
                sucursales = re.sub(r'\s+', ' ', sucursales)
                sucursales = sucursales.strip(',').strip()
                if len(sucursales) > 3 and len(sucursales) < 200:
                    promo['sucursales'] = sucursales
                break
        
        # Verificar si incluye Coto Digital
        if re.search(r'COTO\s*DIGITAL|WWW\.COTODIGITAL\.COM\.AR', text, re.I):
            if promo.get('sucursales'):
                promo['sucursales'] += ' y Coto Digital'
            else:
                promo['sucursales'] = 'Coto Digital'
        
        # 9. Extraer categorías/productos aplicables
        categories_match = re.search(r'ALCANZA\s+A\s+(?:LA\s+TOTALIDAD\s+DE\s+)?(?:LOS\s+)?([A-Za-záéíóúñÁÉÍÓÚÑ,\s]+?)(?:\s*\(EXCEPTO|\s*\.|\s+REEMBOLSO)', text, re.I)
        if categories_match:
            categories = categories_match.group(1).strip()
            categories = re.sub(r'\s+', ' ', categories)[:200]
            if len(categories) > 3:
                promo['categories'] = categories
        
        # 10. Extraer exclusiones - MEJORADO para capturar todo
        exclusions_parts = []
        
        # Patrón 1: "EXCLUSIONES:" seguido de texto
        excl_match = re.search(r'EXCLUSIONES?[:\s]+(.+?)(?:DESCUENTOS,\s*PRECIOS\s*Y\s*PROMOCIONES|COTO\s+C\.I\.C\.S\.A|$)', text, re.I | re.DOTALL)
        if excl_match:
            exclusions_parts.append(excl_match.group(1).strip())
        
        # Patrón 2: "NO INCLUYE" (puede haber varios)
        no_incluye_matches = re.findall(r'NO\s+INCLUYE\s+([^.]+?)(?:\.\s*(?:NO\s+INCLUYE|DESCUENTOS|ESTA\s+PUBLICACI[OÓ]N)|$)', text, re.I)
        for match in no_incluye_matches:
            exclusions_parts.append(f"No incluye {match.strip()}")
        
        # Patrón 3: "QUEDAN EXCLUIDAS"
        quedan_match = re.search(r'QUEDAN\s+EXCLUIDAS?\s+(?:DE\s+LA\s+PROMOCI[OÓ]N\s+)?([^.]+)', text, re.I)
        if quedan_match:
            exclusions_parts.append(f"Quedan excluidas {quedan_match.group(1).strip()}")
        
        # Patrón 4: "NO VÁLIDO PARA"
        no_valido_match = re.search(r'NO\s+V[AÁ]LIDO\s+PARA\s+([^.]+)', text, re.I)
        if no_valido_match:
            exclusions_parts.append(f"No válido para {no_valido_match.group(1).strip()}")
        
        if exclusions_parts:
            # Unir todas las exclusiones
            full_exclusions = ' | '.join(exclusions_parts)
            # Limpiar espacios múltiples
            full_exclusions = re.sub(r'\s+', ' ', full_exclusions)
            promo['exclusions'] = full_exclusions[:2000]  # Permitir texto más largo
        
        # 11. Extraer requisitos
        requirements_parts = []
        
        # "PARA LA COMPRA EN UN PAGO CON..."
        req_match = re.search(r'PARA\s+LA\s+COMPRA\s+([^.]+?)(?:\.\s*ALCANZA|\.)', text, re.I)
        if req_match:
            requirements_parts.append(req_match.group(1).strip())
        
        # "PROMOCIÓN VÁLIDA PARA..."
        promo_valida_match = re.search(r'PROMOCI[OÓ]N\s+V[AÁ]LIDA\s+PARA\s+([^.]+)', text, re.I)
        if promo_valida_match:
            requirements_parts.append(promo_valida_match.group(1).strip())
        
        if requirements_parts:
            promo['requirements'] = ' | '.join(requirements_parts)[:500]
        
        # 12. Verificar si es acumulable
        if re.search(r'NO\s+ACUMULABLE|NO\s+ACUMULA\s+CON', text, re.I):
            promo['acumulable'] = 'No'
            # Extraer con qué no acumula
            no_acum_match = re.search(r'NO\s+ACUMULABLE\s+CON\s+([^.]+)', text, re.I)
            if no_acum_match:
                promo['no_acumula_con'] = no_acum_match.group(1).strip()[:200]
        elif re.search(r'ACUMULABLE\s+CON', text, re.I):
            promo['acumulable'] = 'Sí'
        
        # 13. Extraer información de reembolso (cómo se hace)
        reembolso_match = re.search(r'(?:EL\s+)?REEMBOLSO\s+SE\s+(?:VER[AÁ]\s+REFLEJADO|REALIZAR[AÁ])\s+([^.]+)', text, re.I)
        if reembolso_match:
            promo['forma_reembolso'] = reembolso_match.group(1).strip()[:300]
        
        # 14. Construir título descriptivo
        title_parts = []
        if promo.get('bank'):
            title_parts.append(promo['bank'])
        if promo.get('discount'):
            title_parts.append(promo['discount'])
        if promo.get('payment_type'):
            title_parts.append(f"({promo['payment_type']})")
        if promo.get('valid_days'):
            title_parts.append(f"- {promo['valid_days']}")
        
        if title_parts:
            promo['title'] = ' '.join(title_parts)
        else:
            promo['title'] = text[:100]
        
        return promo
    
    def _identify_bank(self, text: str) -> str:
        """Identifica el banco de la promoción"""
        text_upper = text.upper()
        
        # Orden de prioridad (más específicos primero)
        banks = [
            (r'BANCO\s+MACRO|MACRO\s+SELECTA?', 'Banco Macro'),
            (r'BANCO\s+(?:DE\s+LA\s+)?NACI[OÓ]N|BNA\b', 'Banco Nación'),
            (r'BANCO\s+CIUDAD', 'Banco Ciudad'),
            (r'BANCO\s+(?:DE\s+LA\s+)?PROVINCIA|BAPRO', 'Banco Provincia'),
            (r'BANCO\s+GALICIA|GALICIA', 'Banco Galicia'),
            (r'BANCO\s+SANTANDER|SANTANDER', 'Banco Santander'),
            (r'\bHSBC\b', 'HSBC'),
            (r'\bBBVA\b|BANCO\s+FRANC[EÉ]S', 'BBVA'),
            (r'\bICBC\b', 'ICBC'),
            (r'BANCO\s+PATAGONIA|PATAGONIA', 'Banco Patagonia'),
            (r'BANCO\s+SUPERVIELLE|SUPERVIELLE', 'Banco Supervielle'),
            (r'BANCO\s+CREDICOOP|CREDICOOP', 'Banco Credicoop'),
            (r'BANCO\s+HIPOTECARIO|HIPOTECARIO', 'Banco Hipotecario'),
            (r'BANCO\s+COMAFI|COMAFI', 'Banco Comafi'),
            (r'BANCO\s+COLUMBIA|COLUMBIA', 'Banco Columbia'),
            (r'BANCO\s+C[OÓ]RDOBA|BANCOR', 'Bancor'),
            (r'\bNARANJA\s*X\b|\bPLAN\s*Z\b|\bTARJETA\s+NARANJA\b', 'Naranja X'),
            (r'MERCADO\s*PAGO', 'Mercado Pago'),
            (r'\bMODO\b', 'MODO'),
            # Beneficios sociales — van como bank para que el filtro los detecte
            (r'\bANSES\b|\bBENEFICIOS?\s+ANSES\b', 'ANSES'),
            (r'\bPAMI\b', 'PAMI'),
            (r'\bJUBILADOS?\b', 'Jubilados'),
        ]
        
        for pattern, bank_name in banks:
            if re.search(pattern, text_upper):
                return bank_name
        
        return ''
    
    def _extract_from_full_text(self, soup) -> List[Dict]:
        """Extrae promociones del texto completo de la página"""
        promotions = []
        
        # Obtener todo el texto
        full_text = soup.get_text('\n', strip=True)
        
        # Dividir por posibles separadores de promociones
        # Buscar patrones que indiquen inicio de nueva promoción (ej: "25% DE DESCUENTO - BANCO...")
        promo_starts = list(re.finditer(r'(\d+%\s+DE\s+DESCUENTO\s*-\s*[A-ZÁÉÍÓÚÑ\s]+)', full_text, re.M))
        
        print(f"      Posibles inicios de promociones: {len(promo_starts)}")
        
        if promo_starts:
            for i, match in enumerate(promo_starts):
                start = match.start()
                # El final es el inicio de la siguiente promoción o el fin del texto
                end = promo_starts[i + 1].start() if i + 1 < len(promo_starts) else min(start + 5000, len(full_text))
                
                promo_text = full_text[start:end]
                
                if len(promo_text) > 100:
                    promo = self._parse_promo_text(promo_text)
                    if promo and promo.get('bank'):
                        promotions.append(promo)
                        self._print_promo(len(promotions), promo)
        
        return promotions
    
    def _print_promo(self, index: int, promo: Dict):
        """Imprime resumen de una promoción"""
        bank = promo.get('bank', 'N/A')
        discount = promo.get('discount', 'N/A')
        days = promo.get('valid_days', 'N/A')
        vigencia = ""
        if promo.get('valid_from') or promo.get('valid_until'):
            vigencia = f"{promo.get('valid_from', '?')} → {promo.get('valid_until', '?')}"
        else:
            vigencia = 'N/A'
        title = promo.get('title', 'Sin título')[:70]
        
        print(f"         {index}. {title}")
        print(f"            🏦 {bank} | 💰 {discount} | 📅 {days} | ⏰ {vigencia}")


async def main():
    scraper = CotoScraper()
    promotions = await scraper.scrape()
    
    print(f"\n{'='*100}")
    print(f"📊 RESULTADOS: {len(promotions)} promociones bancarias")
    print(f"{'='*100}")
    
    if promotions:
        print(f"\n📋 Todas las promociones bancarias encontradas:\n")
        for i, promo in enumerate(promotions, 1):
            print(f"\n{'─'*80}")
            print(f"{i}. {promo.get('title', 'Sin título')}")
            print(f"   💰 Descuento: {promo.get('discount', 'N/A')}")
            print(f"   🏦 Banco: {promo.get('bank', 'N/A')}")
            print(f"   💳 Tarjetas: {promo.get('card_types', 'N/A')}")
            print(f"   💵 Tipo: {promo.get('payment_type', 'N/A')}")
            print(f"   📅 Días válidos: {promo.get('valid_days', 'N/A')}")
            print(f"   📆 Vigencia: {promo.get('valid_from', 'N/A')} → {promo.get('valid_until', 'N/A')}")
            print(f"   🏪 Sucursales: {promo.get('sucursales', 'N/A')}")
            print(f"   📦 Categorías: {promo.get('categories', 'N/A')}")
            print(f"   💵 Tope: {promo.get('tope', 'N/A')}")
            print(f"   🔁 Acumulable: {promo.get('acumulable', 'N/A')}")
            
            if promo.get('no_acumula_con'):
                print(f"   🚫 No acumula con: {promo['no_acumula_con'][:100]}...")
            
            if promo.get('exclusions'):
                excl_preview = promo['exclusions'][:300]
                print(f"   ⛔ Exclusiones: {excl_preview}...")
            
            if promo.get('requirements'):
                print(f"   ✅ Requisitos: {promo['requirements'][:150]}...")
            
            if promo.get('forma_reembolso'):
                print(f"   💳 Forma reembolso: {promo['forma_reembolso'][:150]}...")
            
            raw_text = promo.get('raw_text', '')
            if raw_text:
                print(f"   📝 Texto raw: {raw_text[:300]}...")
    else:
        print("\n⚠️  No se encontraron promociones bancarias.")
        print("   Revisa debug_coto_terminos.html y debug_coto_terminos.png para analizar la estructura.")


if __name__ == "__main__":
    asyncio.run(main())
