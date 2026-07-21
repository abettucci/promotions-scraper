"""
Scraper específico para Carrefour - Descuentos Bancarios

Soporta 3 modos de scraping:
1. Playwright (default) - Browser automation con playwright-stealth
2. Simple (requests) - HTTP requests sin browser, más rápido
3. Scrapling - Adaptive scraping con bypass de anti-bot integrado

Configurar via env vars:
- USE_SIMPLE_SCRAPER=true -> Usa requests
- USE_SCRAPLING=true -> Usa Scrapling (recomendado para sitios que cambian)
"""
from typing import List, Dict
from playwright.async_api import Page
from .base_scraper import BaseScraper
import re
import os

class CarrefourScraper(BaseScraper):
    def __init__(self, use_simple_scraper=None, use_scrapling=None):
        super().__init__(
            name='Carrefour',
            url='https://www.carrefour.com.ar/descuentos-bancarios'
        )
        # Auto-detectar modo de scraping (env var o parámetro)
        if use_simple_scraper is None:
            use_simple_scraper = os.environ.get('USE_SIMPLE_SCRAPER', 'false').lower() == 'true'
        self.use_simple_scraper = use_simple_scraper
        
        if use_scrapling is None:
            use_scrapling = os.environ.get('USE_SCRAPLING', 'false').lower() == 'true'
        self.use_scrapling = use_scrapling
    
    async def scrape(self, page: Page) -> List[Dict]:
        """Scraper para Carrefour - Descuentos Bancarios"""
        
        # Prioridad: Scrapling > Simple > Playwright
        if self.use_scrapling:
            print(f"🔍 Scraping {self.name} con Scrapling (adaptive)...")
            return await self._scrape_scrapling()
        
        # Si se configuró para usar scraper simple, usarlo directamente
        if self.use_simple_scraper:
            print(f"🔍 Scraping {self.name} con método simple (sin navegador)...")
            return await self._scrape_simple()
        
        try:
            print(f"🔍 Scraping {self.name}...")
            print(f"   🌐 URL: {self.url}")
            
            # Intentar con diferentes estrategias de carga
            response = None
            page_loaded = False
            
            for wait_strategy in ['domcontentloaded', 'load', 'commit']:
                try:
                    print(f"   🔄 Intentando con wait_until='{wait_strategy}'...")
                    response = await page.goto(self.url, wait_until=wait_strategy, timeout=30000)
                    print(f"   ✅ Página cargada con '{wait_strategy}'")
                    page_loaded = True
                    break
                except Exception as e:
                    print(f"   ⚠️ Falló con '{wait_strategy}': {str(e)[:100]}")
                    if wait_strategy == 'commit':  # Último intento
                        # Si todos fallan, intentar método simple
                        print(f"   🔄 Todos los métodos de carga fallaron, intentando método simple...")
                        return await self._scrape_simple()
            
            if not page_loaded:
                print(f"   ⚠️ No se pudo cargar la página, intentando método simple...")
                return await self._scrape_simple()
            
            print(f"   📡 Status: {response.status if response else 'unknown'}")

            # Esperar a que cargue el JavaScript. Configurable vía env vars
            # CARREFOUR_DELAY_MIN / CARREFOUR_DELAY_MAX para tunear en Railway.
            delay_min = float(os.environ.get('CARREFOUR_DELAY_MIN', '5'))
            delay_max = float(os.environ.get('CARREFOUR_DELAY_MAX', '8'))
            await self.random_delay(delay_min, delay_max)
            
            # Esperar a que el contenido cargue
            try:
                await page.wait_for_selector('body', timeout=10000)
            except:
                pass
            
            # Scroll para cargar contenido lazy
            print(f"   📜 Scrolling para cargar contenido...")
            await self.scroll_page(page, scrolls=5)
            await self.random_delay(2, 3)
            
            # DEBUG: Guardar screenshot si está en modo debug
            if os.environ.get('DEBUG_SCRAPER'):
                try:
                    await page.screenshot(path='debug_carrefour.png')
                    print(f"   📸 Screenshot guardado: debug_carrefour.png")
                except:
                    pass
            
            # Extraer todas las promociones bancarias
            promotions = await self._extract_bank_promotions(page)
            
            print(f"✅ {self.name}: {len(promotions)} promociones encontradas")
            return promotions
            
        except Exception as e:
            print(f"❌ Error en {self.name}: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    async def _extract_bank_promotions(self, page: Page) -> List[Dict]:
        """Extrae las promociones bancarias de la página"""
        promotions = []
        
        try:
            # Primero intentar expandir "Ver legal" cuidadosamente sin causar navegación
            try:
                # Buscar botones de "Ver legal" que no causen navegación
                legal_buttons = await page.query_selector_all('button, a, div[role="button"], span[role="button"]')
                expanded_count = 0
                
                for button in legal_buttons[:20]:  # Limitar a 20 para no ser demasiado lento
                    try:
                        text_content = await button.text_content()
                        if text_content and ('ver legal' in text_content.lower() or 
                                            'ver términos' in text_content.lower() or
                                            'condiciones' in text_content.lower()):
                            # Solo hacer click si no es un enlace que cause navegación
                            href = await button.get_attribute('href')
                            if not href or href == '#' or href.startswith('javascript:'):
                                await button.click(timeout=1000)
                                expanded_count += 1
                                await self.random_delay(0.2, 0.5)
                    except:
                        pass  # Ignorar errores individuales
                
                if expanded_count > 0:
                    print(f"   📋 Expandidos {expanded_count} términos y condiciones")
                    await self.random_delay(1, 2)
            except Exception as e:
                print(f"   ⚠️ No se pudieron expandir T&C: {e}")
            
            # Ahora extraer el contenido de la página de forma segura
            promo_data = []
            
            try:
                # Obtener todo el HTML de la página para parsing
                page_content = await page.content()
                
                # Extraer información de promociones usando JavaScript
                promo_data = await page.evaluate("""() => {
                    const promos = [];

                    try {
                        // Buscar elementos que contengan texto de promoción
                        const allElements = document.querySelectorAll('div, section, article');
                        const promoElements = [];

                        allElements.forEach(el => {
                            try {
                                const text = el.textContent || '';
                                const hasDiscount = /\\d+\\s*%/.test(text);
                                // Require explicit bank/wallet info — "carrefour" alone is NOT enough
                                // since every element on carrefour.com.ar contains the word "carrefour"
                                const hasBankInfo = /banco|cuenta digital|santander|galicia|bbva|macro|icbc|hsbc|credicoop|supervielle|patagonia|naci[oó]n|provincia|frances|itau|comafi|mercado pago|cuenta dni|personal pay|naranja|ual[aá]|modo|anses/i.test(text);

                                // Require both discount AND bank info; keep only reasonably-sized containers
                                if (hasDiscount && hasBankInfo && text.length > 50 && text.length < 5000) {
                                    promoElements.push(el);
                                }
                            } catch (e) {
                                // Ignorar errores en elementos individuales
                            }
                        });

                        // Keep only LEAF promo nodes — elements that don't contain any other promo element.
                        // This prevents the same promo appearing as both a parent container and its children.
                        const leafPromos = promoElements.filter(el =>
                            !promoElements.some(other => other !== el && el.contains(other))
                        );

                        console.log('Found promotion elements:', leafPromos.length);

                        leafPromos.forEach((el) => {
                            try {
                                const fullText = el.textContent || '';
                                
                                // Extraer título
                                let title = '';
                                const headings = el.querySelectorAll('h1, h2, h3, h4, h5, h6, [class*="title"], [class*="titulo"]');
                                if (headings.length > 0) {
                                    title = headings[0].textContent?.trim() || '';
                                }
                                
                                if (!title) {
                                    // Buscar línea con descuento como título
                                    const lines = fullText.split('\\n').filter(l => l.trim().length > 10);
                                    for (const line of lines) {
                                        if ((line.includes('descuento') || line.includes('%')) && line.length < 200) {
                                            title = line.trim();
                                            break;
                                        }
                                    }
                                }
                                
                                // Extraer descuento
                                const discountMatch = fullText.match(/(\\d+)\\s*%/);
                                const discount = discountMatch ? discountMatch[1] + '%' : '';
                                
                                // Extraer imágenes
                                const imgs = el.querySelectorAll('img');
                                const imageUrls = Array.from(imgs)
                                    .map(img => img.src || img.getAttribute('data-src'))
                                    .filter(src => src && !src.includes('data:image'));
                                
                                // Detectar tipos de tienda
                                const storeTypes = [];
                                if (/carrefour\\s*market/i.test(fullText)) storeTypes.push('Carrefour Market');
                                if (/carrefour\\s*express/i.test(fullText)) storeTypes.push('Carrefour Express');
                                if (/carrefour\\s*maxi/i.test(fullText)) storeTypes.push('Carrefour Maxi');
                                if (/hipermercado/i.test(fullText)) storeTypes.push('Hipermercado Carrefour');
                                if (/carrefour\\.com/i.test(fullText)) storeTypes.push('Carrefour.com.ar');
                                
                                // Buscar T&C
                                let terms = '';
                                const termsMatch = fullText.match(/PROMOCIÓN[\\s\\S]{100,}/i);
                                if (termsMatch) {
                                    terms = termsMatch[0];
                                } else {
                                    // Buscar bloques en mayúsculas
                                    const upperMatches = fullText.match(/[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\\s\\d.,;:/()$%-]{200,}/g);
                                    if (upperMatches && upperMatches.length > 0) {
                                        terms = upperMatches.join(' ');
                                    }
                                }
                                
                                // Método de pago
                                const paymentMatch = fullText.match(/(?:con|mediante|usando|través de|a través)\\s+([^\\n.]{5,80}(?:dni|pago|tarjeta|visa|master|amex|cuenta)[^\\n.]{0,30})/i);
                                const paymentMethod = paymentMatch ? paymentMatch[1].trim() : '';
                                
                                // Días válidos
                                const daysMatch = fullText.match(/(?:todos los|los)\\s+(lunes|martes|miércoles|jueves|viernes|sábado|domingo|miercoles|sabado)(?:\\s+de)?(?:\\s+\\w+)?/i);
                                const validDays = daysMatch ? daysMatch[0].trim() : '';
                                
                                // Fechas
                                const dateMatch = fullText.match(/(?:desde|del)\\s+(\\d{1,2})\\s+(?:al|hasta)\\s+(\\d{1,2})\\s+(?:de\\s+)?(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)(?:\\s+de\\s+)?(\\d{4})?/i);
                                let validFrom = '';
                                let validUntil = '';
                                
                                if (dateMatch) {
                                    const monthMap = {
                                        'enero': '01', 'febrero': '02', 'marzo': '03', 'abril': '04',
                                        'mayo': '05', 'junio': '06', 'julio': '07', 'agosto': '08',
                                        'septiembre': '09', 'octubre': '10', 'noviembre': '11', 'diciembre': '12'
                                    };
                                    const dayFrom = dateMatch[1].padStart(2, '0');
                                    const dayUntil = dateMatch[2].padStart(2, '0');
                                    const month = monthMap[dateMatch[3].toLowerCase()] || '01';
                                    const year = dateMatch[4] || '2025';
                                    
                                    validFrom = `${year}-${month}-${dayFrom}`;
                                    validUntil = `${year}-${month}-${dayUntil}`;
                                }
                                
                                if (title || discount) {
                                    promos.push({
                                        title: title || 'Promoción Carrefour',
                                        discount: discount,
                                        fullText: fullText,
                                        terms: terms,
                                        imageUrls: imageUrls,
                                        storeTypes: storeTypes,
                                        paymentMethod: paymentMethod,
                                        validDays: validDays,
                                        validFrom: validFrom,
                                        validUntil: validUntil
                                    });
                                }
                            } catch (e) {
                                console.error('Error processing element:', e);
                            }
                        });
                    } catch (e) {
                        console.error('Error in evaluation:', e);
                    }
                    
                    return promos;
                }""")
            
            except Exception as e:
                print(f"   ⚠️ Error en evaluación JavaScript: {e}")
                print(f"   🔄 Intentando método alternativo con parsing HTML...")
                
                # Método alternativo: parsear el HTML directamente
                try:
                    page_content = await page.content()
                    promo_data = self._parse_html_content(page_content)
                except Exception as e2:
                    print(f"   ❌ Error en método alternativo: {e2}")
            
            print(f"   📊 Extraídos {len(promo_data)} elementos de promoción")

            # Procesar cada promoción
            for idx, promo in enumerate(promo_data):
                try:
                    processed = await self._process_promotion(promo)
                    if processed:
                        promotions.append(processed)
                except Exception as e:
                    print(f"   ⚠️ Error procesando promoción {idx+1}: {e}")

            # Final dedup: one promo per (bank/wallet, discount, valid_days, store_types) — safety net
            # for any remaining duplicates. Include valid_days and store_types so same-bank promos
            # that differ by day or store type (e.g. Carrefour Banco 15% lunes vs 15% sábados) are kept.
            seen = set()
            unique_promotions = []
            for p in promotions:
                entity = (p.get('bank') or p.get('wallet') or '').lower().strip()
                discount = (p.get('discount') or '').strip()
                valid_days = (p.get('valid_days') or '').lower().strip()
                store_types = (p.get('store_types') or '').lower().strip()
                title = (p.get('title') or '').lower().strip()[:80]
                key = (entity, discount, valid_days, store_types, title)
                if key not in seen:
                    seen.add(key)
                    unique_promotions.append(p)
            promotions = unique_promotions
            print(f"   🧹 Después de dedup: {len(promotions)} promociones únicas")

        except Exception as e:
            print(f"   ⚠️ Error extrayendo promociones: {e}")
            import traceback
            traceback.print_exc()
        
        return promotions
    
    def _parse_html_content(self, html_content: str) -> List[Dict]:
        """Método alternativo: parsear HTML directamente con regex"""
        promos = []

        try:
            # Strip ALL embedded data that causes duplicate matches on VTEX/Next.js pages
            cleaned = re.sub(r'<script[^>]*>[\s\S]*?</script>', ' ', html_content, flags=re.IGNORECASE)
            cleaned = re.sub(r'<template[^>]*>[\s\S]*?</template>', ' ', cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r'<style[^>]*>[\s\S]*?</style>', ' ', cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r'<noscript[^>]*>[\s\S]*?</noscript>', ' ', cleaned, flags=re.IGNORECASE)

            text = re.sub(r'<[^>]+>', ' ', cleaned)
            text = re.sub(r'\s+', ' ', text).strip()

            discount_pattern = r'(\d+)\s*%\s*de\s*descuento'
            matches = list(re.finditer(discount_pattern, text, re.IGNORECASE))
            
            for match in matches:
                start = max(0, match.start() - 1000)
                end = min(len(text), match.end() + 3000)
                context = text[start:end]
                
                discount = match.group(1) + '%'

                bank = self.extract_bank(context)
                wallet = self.extract_wallet(context)
                if not bank and not wallet:
                    continue
                
                title_match = re.search(r'(\d+%\s*de\s*descuento[^.!?\n]{10,150})', context, re.IGNORECASE)
                title = title_match.group(1).strip() if title_match else f"Promoción {discount}"
                
                terms_match = re.search(r'(PROMOCIÓN[A-ZÁÉÍÓÚÑ\s\d.,;:/()$%-]{200,})', context, re.IGNORECASE)
                terms = terms_match.group(1) if terms_match else ''
                
                store_types = []
                if re.search(r'carrefour\s*market', context, re.IGNORECASE):
                    store_types.append('Carrefour Market')
                if re.search(r'carrefour\s*express', context, re.IGNORECASE):
                    store_types.append('Carrefour Express')
                if re.search(r'carrefour\s*maxi', context, re.IGNORECASE):
                    store_types.append('Carrefour Maxi')
                if re.search(r'hipermercado', context, re.IGNORECASE):
                    store_types.append('Hipermercado Carrefour')
                
                promos.append({
                    'title': title,
                    'discount': discount,
                    'fullText': context,
                    'terms': terms,
                    'imageUrls': [],
                    'storeTypes': store_types,
                    'paymentMethod': '',
                    'validDays': '',
                    'validFrom': '',
                    'validUntil': ''
                })
        
        except Exception as e:
            print(f"   ❌ Error parseando HTML: {e}")
        
        return promos
    
    async def _process_promotion(self, promo_data: Dict) -> Dict:
        """Procesa y estructura los datos de una promoción"""
        try:
            title = self.clean_text(promo_data.get('title', ''))
            full_text = promo_data.get('fullText', '')
            terms = promo_data.get('terms', '')
            
            # Si no hay términos extraídos, buscar en el texto completo
            if not terms and full_text:
                # Buscar bloques largos de texto en mayúsculas (típico de T&C)
                terms_matches = re.findall(r'[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s\d.,;:/()$%-]{100,}', full_text)
                if terms_matches:
                    terms = ' '.join(terms_matches)
            
            # Extraer información estructurada
            discount = promo_data.get('discount', '') or self.extract_discount(full_text)
            payment_method = promo_data.get('paymentMethod', '')
            
            # Extraer banco o billetera
            bank = self.extract_bank(full_text)
            wallet = self.extract_wallet(full_text)
            
            # Extraer fechas si no están ya
            valid_from = promo_data.get('validFrom', '')
            valid_until = promo_data.get('validUntil', '')
            
            if not valid_from or not valid_until:
                dates = self.extract_dates(terms or full_text)
                valid_from = valid_from or dates.get('valid_from', '')
                valid_until = valid_until or dates.get('valid_until', '')
            
            # Store types
            store_types = promo_data.get('storeTypes', [])
            store_types_str = ', '.join(store_types) if store_types else None
            
            # Días válidos
            valid_days = promo_data.get('validDays', '')
            
            # Extraer exclusiones del texto de T&C
            exclusions = self._extract_exclusions(terms or full_text)
            exclusions_str = '; '.join(exclusions) if exclusions else None
            
            # Extraer requisitos
            requirements = self._extract_requirements(terms or full_text)
            requirements_str = '; '.join(requirements) if requirements else None
            
            # Imagen principal (primera imagen si hay)
            image_url = promo_data.get('imageUrls', [''])[0] if promo_data.get('imageUrls') else ''
            
            processed = {
                'title': title,
                'discount': discount,
                'bank': bank,
                'wallet': wallet,
                'card_type': None,  # Por ahora no lo extraemos
                'payment_method': payment_method or None,
                'store_types': store_types_str,
                'valid_days': valid_days or None,
                'url': self.url,
                'image_url': image_url,
                'terms_raw': self.clean_text(terms),
                'exclusions': exclusions_str,
                'requirements': requirements_str,
                'valid_from': valid_from or None,
                'valid_until': valid_until or None,
            }
            
            return processed
            
        except Exception as e:
            print(f"   ⚠️ Error procesando promoción: {e}")
            return None
    
    def _extract_exclusions(self, text: str) -> List[str]:
        """Extrae productos/categorías excluidas de los T&C"""
        if not text:
            return []
        
        text_lower = text.lower()
        exclusions = []
        
        # Patrones para encontrar exclusiones
        patterns = [
            r'se\s+excluyen?\s+(?:de\s+la\s+promoción\s+)?([^.]+)',
            r'exclu(?:ye|ído)(?:s)?\s+([^.]+)',
            r'no\s+(?:incluye|aplica|válid[oa])\s+(?:para|en)\s+([^.]+)',
            r'excepto\s+([^.]+)',
            r'no\s+(?:se\s+)?(?:puede|podrá)\s+(?:utilizar|usar|aplicar)\s+(?:en|con|para)\s+([^.]+)',
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text_lower, re.IGNORECASE)
            for match in matches:
                exclusion_text = match.group(1).strip()
                # Limpiar y dividir por comas/y
                items = re.split(r'[,y]', exclusion_text)
                for item in items:
                    item = item.strip()
                    if item and len(item) > 3 and len(item) < 100:
                        exclusions.append(item.capitalize())
        
        # Remover duplicados
        return list(set(exclusions))[:10]  # Limitar a 10
    
    def _extract_requirements(self, text: str) -> List[str]:
        """Extrae requisitos de elegibilidad"""
        if not text:
            return []
        
        text_lower = text.lower()
        requirements = []
        
        # Buscar requisitos específicos
        patterns = [
            r'(?:solo|únicamente|exclusivamente)\s+(?:para|con)\s+([^.]{5,80})',
            r'(?:válid[oa]|aplicable)\s+(?:solo|únicamente)\s+(?:para|con)\s+([^.]{5,80})',
            r'requiere\s+([^.]{5,80})',
            r'debe\s+(?:tener|ser|contar)\s+([^.]{5,80})',
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text_lower, re.IGNORECASE)
            for match in matches:
                req = match.group(1).strip()
                if len(req) > 5 and len(req) < 100:
                    # Limpiar
                    req = req.split('.')[0]  # Tomar hasta el primer punto
                    requirements.append(req.capitalize())
        
        # Buscar niveles de app
        nivel_match = re.search(r'nivel\s+(\d+|[a-z]+)', text_lower)
        if nivel_match:
            requirements.append(f"Nivel {nivel_match.group(1)}")
        
        # Buscar tipos de tarjeta premium
        card_types = ['black', 'platinum', 'signature', 'gold', 'infinite']
        for card_type in card_types:
            if card_type in text_lower:
                requirements.append(f"Tarjeta {card_type.title()}")
        
        return list(set(requirements))[:5]
    
    async def _scrape_simple(self) -> List[Dict]:
        """Método alternativo: scraping sin navegador usando requests"""
        try:
            from .carrefour_simple_scraper import CarrefourSimpleScraper
            
            simple_scraper = CarrefourSimpleScraper()
            # El método scrape del simple scraper es síncrono, lo llamamos directamente
            promotions = simple_scraper.scrape()
            return promotions
            
        except Exception as e:
            print(f"   ❌ Error en método simple: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    async def _scrape_scrapling(self) -> List[Dict]:
        """
        Método con Scrapling: adaptive scraping con bypass de anti-bot.
        Ventajas:
        - Encuentra elementos aunque cambien los selectores (adaptive)
        - Bypass integrado de Cloudflare y otros anti-bot
        - API unificada para requests y browser automation
        """
        try:
            from .carrefour_scrapling import CarrefourScraplingScraper
            
            headless = os.environ.get('HEADLESS', 'true').lower() == 'true'
            use_adaptive = os.environ.get('SCRAPLING_ADAPTIVE', 'false').lower() == 'true'
            
            scrapling_scraper = CarrefourScraplingScraper(
                use_adaptive=use_adaptive,
                headless=headless
            )
            
            # Scrapling tiene método async disponible
            promotions = await scrapling_scraper.scrape_async()
            return promotions
            
        except ImportError as e:
            print(f"   ⚠️ Scrapling no disponible: {e}")
            print(f"   🔄 Instalá con: pip install 'scrapling[fetchers]' && scrapling install")
            print(f"   🔄 Fallback a método simple...")
            return await self._scrape_simple()
            
        except Exception as e:
            print(f"   ❌ Error en Scrapling: {e}")
            import traceback
            traceback.print_exc()
            print(f"   🔄 Fallback a método simple...")
            return await self._scrape_simple()

