#!/usr/bin/env python3
"""
Scraper de Supermercados Día - Promociones Bancarias
- Extrae promociones de https://diaonline.supermercadosdia.com.ar/medios-de-pago-y-promociones
- Navega por cada día de la semana
- Expande "Ver Legales" para obtener términos y condiciones completos
"""
import asyncio
import re
from typing import List, Dict, Set

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup


class DiaScraper:
    def __init__(self):
        self.name = 'Supermercados Día'
        self.base_url = 'https://diaonline.supermercadosdia.com.ar/medios-de-pago-y-promociones'
        
        # Días de la semana
        self.dias = ['Todos', 'Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
        
    async def scrape(self) -> List[Dict]:
        """Scraping de promociones de Día"""
        print(f"\n🔍 Scraping {self.name} - Promociones Bancarias...")
        print(f"   🌐 URL: {self.base_url}")
        
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
                
                # Navegar a la página
                print(f"\n   📡 Navegando a la página...")
                await page.goto(self.base_url, wait_until='networkidle', timeout=60000)
                await asyncio.sleep(3)
                
                # Hacer click en "Promociones Bancarias" si existe
                try:
                    promo_bancarias = page.locator('text=Promociones Bancarias')
                    if await promo_bancarias.count() > 0:
                        await promo_bancarias.first.click()
                        await asyncio.sleep(2)
                        print(f"   ✅ Click en 'Promociones Bancarias'")
                except Exception:
                    pass
                
                # Hacer click en "Por Día" para asegurarnos de estar en esa vista
                try:
                    por_dia = page.locator('text=Por Día')
                    if await por_dia.count() > 0:
                        await por_dia.first.click()
                        await asyncio.sleep(2)
                        print(f"   ✅ Click en 'Por Día'")
                except Exception:
                    pass
                
                # Iterar por cada día
                print(f"\n   📅 Scrapeando por DÍAS...")
                
                for dia in self.dias:
                    print(f"\n      📆 {dia}")
                    
                    # IMPORTANTE: Cerrar modales ANTES de intentar hacer click
                    await self._close_all_modals(page)
                    
                    # Scroll al inicio para asegurarnos de ver los tabs
                    await page.evaluate('window.scrollTo(0, 0)')
                    await asyncio.sleep(0.5)
                    
                    # Hacer click en el día
                    try:
                        clicked = await self._click_day_button(page, dia)
                        if not clicked:
                            print(f"         ⚠️  No se encontró botón para '{dia}'")
                            continue
                        print(f"         ✅ Click en '{dia}'")
                    except Exception as e:
                        print(f"         ⚠️  Error haciendo click en '{dia}': {e}")
                        # Intentar recuperar cerrando modales y reintentando
                        await self._close_all_modals(page)
                        await asyncio.sleep(1)
                        continue
                    
                    # Esperar a que se carguen las promociones
                    await asyncio.sleep(2)
                    
                    # Scroll para cargar contenido
                    await self._scroll_page(page)
                    
                    # NO expandir "Ver Legales" para evitar modales que bloquean
                    # Si necesitas los legales, hacerlo de forma individual y cerrar después
                    
                    # Obtener HTML
                    html = await page.content()
                    
                    # Extraer promociones
                    promos = self._extract_promotions(html, dia)
                    
                    new_count = 0
                    for promo in promos:
                        # Key única para evitar duplicados
                        promo_key = f"{promo.get('bank', '')}-{promo.get('discount', '')}-{promo.get('tope', '')}"
                        if promo_key not in seen_promos:
                            seen_promos.add(promo_key)
                            all_promotions.append(promo)
                            new_count += 1
                    
                    print(f"         ✅ {new_count} promociones nuevas encontradas")
                    
                    # Cerrar cualquier modal que se haya abierto
                    await self._close_all_modals(page)
                    
                    await asyncio.sleep(0.5)
                
                # Guardar debug
                html = await page.content()
                with open('debug_dia.html', 'w', encoding='utf-8') as f:
                    f.write(html)
                await page.screenshot(path='debug_dia.png', full_page=True)
                print(f"\n   📸 Debug: debug_dia.html, debug_dia.png")
                
                print(f"\n✅ {self.name}: {len(all_promotions)} promociones únicas encontradas")
                
                return all_promotions
                
            except Exception as e:
                print(f"\n   ❌ Error: {e}")
                import traceback
                traceback.print_exc()
                return all_promotions
            finally:
                await browser.close()
    
    async def _click_day_button(self, page, dia: str) -> bool:
        """Hace click en el botón del día especificado"""
        
        # Primero cerrar cualquier modal/overlay que pueda estar bloqueando
        await self._close_all_modals(page)
        await asyncio.sleep(0.3)
        
        # Scroll al inicio de la página
        await page.evaluate('window.scrollTo(0, 0)')
        await asyncio.sleep(0.3)
        
        # Variantes del nombre del día (con/sin acento)
        dia_variants = [dia]
        if dia == 'Miércoles':
            dia_variants.extend(['Miercoles', 'miércoles', 'miercoles'])
        elif dia == 'Sábado':
            dia_variants.extend(['Sabado', 'sábado', 'sabado'])
        
        # Lista de selectores para encontrar los botones de día
        for dia_var in dia_variants:
            selectors = [
                # Buscar en el contenedor de tabs de días
                f'[role="tablist"] >> text="{dia_var}"',
                f'[class*="tab"] >> text="{dia_var}"',
                f'[class*="filter"] >> text="{dia_var}"',
                f'[class*="day"] >> text="{dia_var}"',
                # Botones con texto exacto
                f'button:text-is("{dia_var}")',
                f'span:text-is("{dia_var}")',
                # Texto contenido (menos estricto)
                f'button:has-text("{dia_var}")',
                f'[class*="btn"]:has-text("{dia_var}")',
                # Texto exacto
                f'text="{dia_var}"',
            ]
            
            for selector in selectors:
                try:
                    locator = page.locator(selector)
                    count = await locator.count()
                    
                    if count > 0:
                        # Buscar el primer elemento visible
                        for i in range(min(count, 5)):  # Máximo 5 intentos
                            element = locator.nth(i)
                            
                            try:
                                # Verificar si es visible
                                if await element.is_visible(timeout=2000):
                                    # Scroll al elemento
                                    await element.scroll_into_view_if_needed()
                                    await asyncio.sleep(0.3)
                                    
                                    # Intentar click con force para ignorar overlays
                                    try:
                                        await element.click(timeout=5000, force=True)
                                        await asyncio.sleep(1)
                                        return True
                                    except Exception:
                                        # Si falla con force, intentar sin force
                                        await element.click(timeout=5000)
                                        await asyncio.sleep(1)
                                        return True
                            except Exception:
                                continue
                except Exception:
                    continue
        
        # Fallback: buscar por JavaScript
        for dia_var in dia_variants:
            try:
                clicked = await page.evaluate(f'''() => {{
                    const texts = Array.from(document.querySelectorAll('button, span, div, a, li'));
                    for (const el of texts) {{
                        const text = el.textContent.trim().toLowerCase();
                        if (text === "{dia_var.lower()}" && el.offsetParent !== null) {{
                            el.click();
                            return true;
                        }}
                    }}
                    return false;
                }}''')
                if clicked:
                    await asyncio.sleep(1)
                    return True
            except Exception:
                pass
        
        return False
    
    async def _scroll_page(self, page):
        """Hace scroll para cargar contenido"""
        for _ in range(5):
            await page.evaluate('window.scrollBy(0, 400)')
            await asyncio.sleep(0.3)
        await page.evaluate('window.scrollTo(0, 0)')
        await asyncio.sleep(0.3)
    
    async def _close_all_modals(self, page):
        """Cierra todos los modales abiertos de forma agresiva"""
        
        # Primero intentar con Escape
        try:
            await page.keyboard.press('Escape')
            await asyncio.sleep(0.3)
        except Exception:
            pass
        
        # Intentar click fuera de cualquier modal
        try:
            await page.evaluate('''() => {
                // Cerrar modales haciendo click en overlay/backdrop
                const overlays = document.querySelectorAll('[class*="overlay"], [class*="backdrop"], [class*="modal-bg"]');
                overlays.forEach(el => el.click());
                
                // Remover clases que bloquean scroll
                document.body.classList.remove('modal-open', 'overflow-hidden');
                document.body.style.overflow = '';
            }''')
        except Exception:
            pass
        
        # Intentar cerrar con botones de cerrar
        close_selectors = [
            'button[class*="close"]',
            'button[class*="Close"]',
            '[class*="modal"] button[aria-label="close"]',
            '[class*="modal"] button[aria-label="cerrar"]',
            '[class*="modal-close"]',
            '[class*="modalClose"]',
            '[aria-label="close"]',
            '[aria-label="cerrar"]',
            'button:has(svg[class*="close"])',
            '[class*="modal"] button:first-child',
            'text=×',
            'text=X',
        ]
        
        for selector in close_selectors:
            try:
                close_buttons = page.locator(selector)
                count = await close_buttons.count()
                for i in range(count):
                    try:
                        btn = close_buttons.nth(i)
                        if await btn.is_visible(timeout=500):
                            await btn.click(timeout=1000, force=True)
                            await asyncio.sleep(0.2)
                    except Exception:
                        pass
            except Exception:
                pass
        
        # Intentar cerrar modales por JavaScript
        try:
            await page.evaluate('''() => {
                // Buscar y ocultar cualquier modal visible
                const modals = document.querySelectorAll('[class*="modal"], [class*="Modal"], [role="dialog"]');
                modals.forEach(modal => {
                    if (modal.style.display !== 'none') {
                        modal.style.display = 'none';
                    }
                });
                
                // Remover cualquier overlay
                const overlays = document.querySelectorAll('[class*="overlay"], [class*="Overlay"]');
                overlays.forEach(overlay => {
                    overlay.style.display = 'none';
                });
            }''')
        except Exception:
            pass
        
        await asyncio.sleep(0.3)
    
    async def _expand_ver_legales(self, page) -> int:
        """Expande todos los botones 'Ver Legales'"""
        expanded = 0
        
        try:
            # Buscar botones "Ver Legales"
            selectors = [
                'text=Ver Legales',
                'text=Ver legales',
                'text=ver legales',
                'button:has-text("Legales")',
                'a:has-text("Legales")',
            ]
            
            for selector in selectors:
                try:
                    buttons = page.locator(selector)
                    count = await buttons.count()
                    
                    for i in range(count):
                        try:
                            button = buttons.nth(i)
                            if await button.is_visible(timeout=1000):
                                await button.click(timeout=2000)
                                expanded += 1
                                await asyncio.sleep(0.5)
                                
                                # Cerrar modal inmediatamente después de obtener info
                                await self._close_all_modals(page)
                        except Exception:
                            pass
                except Exception:
                    pass
                    
        except Exception as e:
            print(f"         ⚠️  Error expandiendo legales: {e}")
        
        return expanded
    
    def _extract_promotions(self, html: str, dia: str) -> List[Dict]:
        """Extrae promociones del HTML"""
        soup = BeautifulSoup(html, 'html.parser')
        promotions = []
        
        # Buscar cards de promociones
        # Basándonos en la imagen: cada card tiene
        # - Tags: "APLICA ONLINE", "APLICA TIENDA"
        # - Logo del banco/tarjeta
        # - Descuento (ej: "25% Dto")
        # - Tope (ej: "Tope: $10.000")
        # - Fechas
        # - Botón "Ver Legales"
        
        # Buscar contenedores de cards
        all_cards = []
        
        # Buscar divs que contengan estructura de promoción
        for div in soup.find_all('div'):
            text = div.get_text(' ', strip=True)
            
            # Debe tener descuento
            has_discount = bool(re.search(r'\d+\s*%\s*[Dd]to|\d+\s*%\s*[Dd]escuento|\d+\s*cuotas', text, re.I))
            
            # Debe tener tope o "Sin tope" o info de pago
            has_tope = bool(re.search(r'[Tt]ope|[Ss]in\s+tope|inter[eé]s', text, re.I))
            
            # Longitud razonable
            good_length = 50 < len(text) < 1500
            
            if has_discount and has_tope and good_length:
                # Verificar que no sea contenedor padre
                child_divs = div.find_all('div', recursive=False)
                is_parent = False
                for child in child_divs:
                    child_text = child.get_text(' ', strip=True)
                    if re.search(r'\d+\s*%', child_text) and 'Tope' in child_text:
                        is_parent = True
                        break
                
                if not is_parent:
                    all_cards.append(div)
        
        print(f"         🔍 Cards encontradas: {len(all_cards)}")
        
        # También buscar modales con legales abiertos
        modals = soup.find_all(['div', 'section'], class_=re.compile(r'modal|legal|popup', re.I))
        modal_texts = {}
        for modal in modals:
            modal_text = modal.get_text(' ', strip=True)
            if len(modal_text) > 200 and 'BENEFICIO' in modal_text.upper():
                # Asociar con banco si es posible
                bank = self._identify_bank(modal_text)
                if bank:
                    modal_texts[bank] = modal_text
        
        # Procesar cards
        seen_texts = set()
        
        for card in all_cards:
            text = card.get_text(' ', strip=True)
            
            # Evitar duplicados
            text_key = re.sub(r'\s+', ' ', text[:100])
            if text_key in seen_texts:
                continue
            seen_texts.add(text_key)
            
            # Extraer promoción
            promo = self._parse_promo(card, text, dia, modal_texts)
            
            if promo and promo.get('discount'):
                promotions.append(promo)
        
        return promotions
    
    def _parse_promo(self, card, text: str, dia: str, modal_texts: dict) -> Dict:
        """Parsea una card para extraer información de la promoción"""
        promo = {
            'url': self.base_url,
            'supermarket': 'Día',
            'raw_text': text[:2000]
        }
        
        # 1. Identificar banco/tarjeta - primero desde imagen, luego desde texto
        img = card.find('img')
        img_src = ''
        img_alt = ''
        if img:
            img_src = img.get('src', '') or img.get('data-src', '') or ''
            img_alt = img.get('alt', '') or ''
            promo['image_url'] = img_src
            promo['image_alt'] = img_alt
        
        # Intentar identificar desde imagen primero
        bank = self._identify_bank_from_image(img_src, img_alt)
        if not bank:
            bank = self._identify_bank(text)
        promo['bank'] = bank
        
        # 2. Extraer si aplica online/tienda
        aplica = []
        if re.search(r'APLICA\s+ONLINE|ONLINE', text, re.I):
            aplica.append('Online')
        if re.search(r'APLICA\s+TIENDA|TIENDA', text, re.I):
            aplica.append('Tienda')
        if aplica:
            promo['aplica_en'] = ', '.join(aplica)
        
        # 3. Extraer descuento o cuotas sin interés
        discount_match = re.search(r'(\d+)\s*%\s*(?:[Dd]to|[Dd]escuento)?', text)
        cuotas_match = re.search(r'(\d+)\s*cuotas?\s*(?:sin\s*inter[eé]s)?', text, re.I)
        
        if discount_match:
            promo['discount'] = f"{discount_match.group(1)}%"
        elif cuotas_match:
            promo['discount'] = f"{cuotas_match.group(1)} cuotas sin interés"
        
        # 4. Extraer tope
        if re.search(r'[Ss]in\s+[Tt]ope', text):
            promo['tope'] = 'Sin tope'
        else:
            tope_patterns = [
                r'[Tt]ope\s*:\s*\$?\s*([\d.,]+)(?:\s*(mensual|semanal|por\s+transacci[oó]n|por\s+semana|por\s+usuario|por\s+mes))?',
                r'\$\s*([\d.,]+)\s*(mensual|semanal|por\s+transacci[oó]n|por\s+semana|por\s+mes)',
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
                    except Exception:
                        promo['tope'] = f"${match.group(1)}"
                    break
        
        # 5. Extraer monto mínimo
        monto_min_match = re.search(r'[Mm]onto\s+[Mm][ií]nimo\s*:?\s*\$?\s*([\d.,]+)', text)
        if not monto_min_match:
            monto_min_match = re.search(r'[Mm][ií]n\.?\s*[Cc]ompra\s*:?\s*\$?\s*([\d.,]+)', text)
        if monto_min_match:
            promo['monto_minimo'] = f"${monto_min_match.group(1)}"
        
        # 6. Extraer fechas de vigencia
        # Formato: "06/01/2026 y 20/01/2026" o "Del 01/01/2026 al 28/02/2026"
        fecha_patterns = [
            r'(\d{1,2}/\d{1,2}/\d{4})\s*(?:y|al)\s*(\d{1,2}/\d{1,2}/\d{4})',
            r'[Dd]el\s+(\d{1,2}/\d{1,2}/\d{4})\s+al\s+(\d{1,2}/\d{1,2}/\d{4})',
            r'(\d{1,2}/\d{1,2}/\d{4})',
        ]
        
        for pattern in fecha_patterns:
            match = re.search(pattern, text)
            if match:
                if match.lastindex and match.lastindex >= 2:
                    promo['valid_from'] = match.group(1)
                    promo['valid_until'] = match.group(2)
                else:
                    # Fecha única: usarla como valid_until (la promo termina ese día)
                    promo['valid_until'] = match.group(1)
                break
        
        # 7. Extraer días específicos de la promoción
        if dia != 'Todos':
            promo['valid_days'] = dia
        else:
            # Buscar días en el texto
            dias_match = re.search(r'(?:los\s+)?(?:d[ií]as?\s+)?(lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo)(?:\s+y\s+(lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo))?', text, re.I)
            if dias_match:
                dias = [d for d in dias_match.groups() if d]
                promo['valid_days'] = ' y '.join([d.title() for d in dias])
        
        # 8. Extraer forma de pago
        if re.search(r'[Cc]r[eé]dito\s+y\s+[Dd][eé]bito|[Dd][eé]bito\s+y\s+[Cc]r[eé]dito|[Dd][eé]b\s+y\s+[Cc]r[eé]d', text):
            promo['payment_type'] = 'Crédito y Débito'
        elif re.search(r'[Cc]r[eé]dito|[Cc]r[eé]d', text):
            promo['payment_type'] = 'Crédito'
        elif re.search(r'[Dd][eé]bito|[Dd][eé]b', text):
            promo['payment_type'] = 'Débito'
        elif re.search(r'dinero\s+en\s+cuenta', text, re.I):
            promo['payment_type'] = 'Dinero en cuenta'
        
        # 9. Buscar información adicional en modales (legales)
        bank = promo.get('bank', '')
        if bank and bank in modal_texts:
            legal_text = modal_texts[bank]
            promo['legal_text'] = legal_text[:3000]
            
            # Extraer información adicional del texto legal
            self._parse_legal_text(promo, legal_text)
        
        # 10. Construir título
        title_parts = []
        if promo.get('bank'):
            title_parts.append(promo['bank'])
        if promo.get('discount'):
            title_parts.append(promo['discount'])
        if promo.get('aplica_en'):
            title_parts.append(f"({promo['aplica_en']})")
        if promo.get('valid_days'):
            title_parts.append(f"- {promo['valid_days']}")
        
        if title_parts:
            promo['title'] = ' '.join(title_parts)
        else:
            promo['title'] = text[:80]
        
        return promo
    
    def _parse_legal_text(self, promo: Dict, legal_text: str):
        """Extrae información adicional del texto legal"""
        
        # Tope si no lo tenemos
        if not promo.get('tope'):
            tope_match = re.search(r'TOPE\s+DE\s+\$?([\d.,]+)', legal_text, re.I)
            if tope_match:
                promo['tope'] = f"${tope_match.group(1)}"
        
        # Frecuencia del beneficio
        freq_match = re.search(r'V[AÁ]LIDO\s+(\d+)\s*\([^)]+\)\s*VEZ\s+POR\s+USUARIO', legal_text, re.I)
        if freq_match:
            promo['frecuencia'] = f"{freq_match.group(1)} vez por usuario"
        
        # Forma de reintegro
        if re.search(r'REINTEGRO\s+SE\s+VER[AÁ]\s+REFLEJADO\s+EN\s+EL\s+ESTADO\s+DE\s+CUENTA', legal_text, re.I):
            promo['forma_reintegro'] = 'Estado de cuenta'
        
        # Días hábiles para reintegro
        dias_habiles_match = re.search(r'DENTRO\s+DE\s+(?:LOS\s+)?\(?\s*(\d+)\s*\)?\s*(?:\w+\s+)?D[IÍ]AS\s+H[AÁ]BILES', legal_text, re.I)
        if dias_habiles_match:
            promo['dias_reintegro'] = f"{dias_habiles_match.group(1)} días hábiles"
        
        # Tipo de consumo
        if re.search(r'CONSUMOS?\s+DE\s+TIPO\s+FAMILIAR', legal_text, re.I):
            promo['tipo_consumo'] = 'Familiar'
        
        # Condiciones especiales
        condiciones = []
        if re.search(r'ENV[IÍ]O\s+EXPRESS', legal_text, re.I):
            condiciones.append('Envío Express')
        if re.search(r'ENV[IÍ]O\s+PROGRAMADO', legal_text, re.I):
            condiciones.append('Envío Programado')
        if re.search(r'RETIRO\s+EN\s+TIENDA', legal_text, re.I):
            condiciones.append('Retiro en Tienda')
        if condiciones:
            promo['condiciones_envio'] = ', '.join(condiciones)
    
    def _identify_bank_from_image(self, img_src: str, img_alt: str) -> str:
        """Identifica el banco analizando la URL o alt de la imagen."""
        if not img_src and not img_alt:
            return ''
        
        combined = f"{img_src} {img_alt}".lower()
        
        # Mapeo de keywords en imagen -> nombre del banco
        image_bank_map = [
            # Bancos específicos
            (r'hipotecario', 'Banco Hipotecario'),
            (r'supervielle', 'Supervielle'),
            (r'galicia', 'Banco Galicia'),
            (r'macro', 'Banco Macro'),
            (r'nacion|bna[^c]', 'Banco Nación'),
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
            
            # Tarjetas
            (r'naranja', 'Naranja X'),
            (r'clarin|365', 'Clarín 365'),
            (r'amex|american', 'American Express'),
            
            # Genéricos
            (r'visa[-_]?master|master[-_]?visa', 'Visa/Mastercard'),
            (r'visa', 'Visa'),
            (r'mastercard|master', 'Mastercard'),
            (r'cabal', 'Cabal'),
        ]
        
        for pattern, bank_name in image_bank_map:
            if re.search(pattern, combined):
                return bank_name
        
        return ''
    
    def _identify_bank(self, text: str) -> str:
        """Identifica el banco/tarjeta del texto"""
        text_upper = text.upper()
        
        banks = [
            (r'\bPREX\b', 'Prex'),
            (r'\bMODO\b', 'MODO'),
            (r'MERCADO\s*PAGO', 'Mercado Pago'),
            (r'BANCO\s+NACI[OÓ]N|BNA\b', 'Banco Nación'),
            (r'BANCO\s+COLUMBIA|COLUMBIA', 'Banco Columbia'),
            (r'BANCO\s+MACRO|MACRO', 'Banco Macro'),
            (r'BANCO\s+GALICIA|GALICIA', 'Banco Galicia'),
            (r'BANCO\s+CIUDAD', 'Banco Ciudad'),
            (r'BANCO\s+PROVINCIA|BAPRO', 'Banco Provincia'),
            (r'BANCO\s+SANTANDER|SANTANDER', 'Banco Santander'),
            (r'\bHSBC\b', 'HSBC'),
            (r'\bBBVA\b', 'BBVA'),
            (r'\bICBC\b', 'ICBC'),
            (r'BANCO\s+PATAGONIA|PATAGONIA', 'Banco Patagonia'),
            (r'BANCO\s+SUPERVIELLE|SUPERVIELLE', 'Supervielle'),
            (r'BANCO\s+COMAFI|COMAFI', 'Banco Comafi'),
            (r'BANCO\s+HIPOTECARIO|HIPOTECARIO', 'Banco Hipotecario'),
            (r'NARANJA\s*X?|TARJETA\s+NARANJA', 'Naranja X'),
            (r'PERSONAL\s+PAY', 'Personal Pay'),
            (r'CUENTA\s+DNI', 'Cuenta DNI'),
            (r'UALA|UAL[AÁ]', 'Ualá'),
            (r'BANCO\s+DEL\s+SOL', 'Banco del Sol'),
            (r'BENEFICIOS\s+ANSES|ANSES', 'Beneficios ANSES'),
            (r'CREDICOOP', 'Banco Credicoop'),
            (r'BANCO\s+FRANCES|FRANC[EÉ]S', 'BBVA'),
        ]
        
        for pattern, bank_name in banks:
            if re.search(pattern, text_upper):
                return bank_name
        
        # Si tiene Visa/Mastercard genérico
        if re.search(r'VISA.*MASTERCARD|MASTERCARD.*VISA', text_upper):
            return 'Visa/Mastercard'
        elif re.search(r'\bVISA\b', text_upper):
            return 'Visa'
        elif re.search(r'\bMASTERCARD\b', text_upper):
            return 'Mastercard'
        elif re.search(r'\bAMEX\b|AMERICAN\s+EXPRESS', text_upper):
            return 'American Express'
        elif re.search(r'\bCABAL\b', text_upper):
            return 'Cabal'
        
        return ''


async def main():
    scraper = DiaScraper()
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
            print(f"   🏪 Aplica en: {promo.get('aplica_en', 'N/A')}")
            print(f"   💵 Tipo pago: {promo.get('payment_type', 'N/A')}")
            print(f"   📅 Días válidos: {promo.get('valid_days', 'N/A')}")
            print(f"   📆 Vigencia: {promo.get('valid_from', promo.get('valid_dates', 'N/A'))} → {promo.get('valid_until', 'N/A')}")
            print(f"   💵 Tope: {promo.get('tope', 'N/A')}")
            print(f"   💰 Monto mínimo: {promo.get('monto_minimo', 'N/A')}")
            print(f"   🔄 Frecuencia: {promo.get('frecuencia', 'N/A')}")
            print(f"   📦 Condiciones envío: {promo.get('condiciones_envio', 'N/A')}")
            print(f"   ⏱️ Días reintegro: {promo.get('dias_reintegro', 'N/A')}")
            
            if promo.get('legal_text'):
                print(f"   📜 Legal: {promo['legal_text'][:200]}...")
            
            raw_text = promo.get('raw_text', '')
            if raw_text:
                print(f"   📝 Texto: {raw_text[:250]}...")
    else:
        print("\n⚠️  No se encontraron promociones.")
        print("   Revisa debug_dia.html y debug_dia.png para analizar la estructura.")


if __name__ == "__main__":
    asyncio.run(main())
