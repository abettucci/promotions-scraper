"""
Scraper de Carrefour usando Scrapling - Adaptive Web Scraping
Usa StealthyFetcher para bypass de anti-bot y adaptive scraping para
resistir cambios en la estructura del sitio.
"""
import re
import os
from typing import List, Dict, Optional


class CarrefourScraplingError(Exception):
    """Error específico del scraper de Carrefour con Scrapling"""
    pass


class CarrefourScraplingScraper:
    def __init__(self, use_adaptive: bool = True, headless: bool = True):
        """
        Args:
            use_adaptive: Si True, usa adaptive scraping para encontrar elementos
                         aunque cambien los selectores
            headless: Si True, ejecuta el browser sin interfaz gráfica
        """
        self.name = 'Carrefour'
        self.url = 'https://www.carrefour.com.ar/descuentos-bancarios'
        self.use_adaptive = use_adaptive
        self.headless = headless
        
        self._banks = {
            'galicia': 'Banco Galicia',
            'santander': 'Santander',
            'bbva': 'BBVA',
            'macro': 'Macro',
            'icbc': 'ICBC',
            'hsbc': 'HSBC',
            'ciudad': 'Banco Ciudad',
            'nacion': 'Banco Nación',
            'provincia': 'Banco Provincia',
            'patagonia': 'Banco Patagonia',
            'credicoop': 'Credicoop',
            'supervielle': 'Supervielle',
            'frances': 'Banco Francés',
            'itau': 'Itaú',
        }
        
        self._wallets = {
            'cuenta dni': 'Cuenta DNI',
            'mercado pago': 'Mercado Pago',
            'ualá': 'Ualá',
            'uala': 'Ualá',
            'naranja x': 'Naranja X',
            'modo': 'MODO',
            'personal pay': 'Personal Pay',
        }

    def scrape(self) -> List[Dict]:
        """
        Scrape síncrono de promociones de Carrefour usando Scrapling.
        Retorna lista de promociones encontradas.
        """
        try:
            from scrapling.fetchers import StealthyFetcher
        except ImportError:
            raise CarrefourScraplingError(
                "Scrapling no está instalado. Ejecuta: pip install 'scrapling[fetchers]' && scrapling install"
            )
        
        try:
            print(f"🔍 Scraping {self.name} con Scrapling...")
            print(f"   🌐 URL: {self.url}")
            print(f"   🎯 Modo adaptive: {self.use_adaptive}")
            
            StealthyFetcher.adaptive = self.use_adaptive
            
            page = StealthyFetcher.fetch(
                self.url,
                headless=self.headless,
                network_idle=True,
                timeout=30000,
            )
            
            print(f"   ✅ Página cargada correctamente")
            
            if os.environ.get('DEBUG_SCRAPER'):
                debug_path = 'debug_carrefour_scrapling.html'
                with open(debug_path, 'w', encoding='utf-8') as f:
                    f.write(str(page.html_content))
                print(f"   💾 HTML guardado en: {debug_path}")
            
            promotions = self._extract_promotions(page)
            
            print(f"✅ {self.name}: {len(promotions)} promociones encontradas")
            return promotions
            
        except Exception as e:
            print(f"❌ Error en {self.name} (Scrapling): {e}")
            import traceback
            traceback.print_exc()
            return []

    async def scrape_async(self) -> List[Dict]:
        """
        Scrape asíncrono de promociones de Carrefour usando Scrapling.
        Útil para integración con el sistema existente que usa async.
        Corre el fetch sync en un thread para evitar conflictos con el event loop.
        """
        import asyncio
        print(f"🔍 Scraping {self.name} con Scrapling (async)...")
        return await asyncio.to_thread(self.scrape)

    def _extract_promotions(self, page) -> List[Dict]:
        """
        Extrae promociones de la página usando selectores adaptativos.
        Si el sitio cambia estructura, Scrapling intentará encontrar
        elementos similares automáticamente.
        """
        promotions = []
        
        promo_selectors = [
            'div[class*="promo"]',
            'div[class*="descuento"]',
            'div[class*="card"]',
            'article',
            'section[class*="promo"]',
        ]
        
        promo_elements = []
        for selector in promo_selectors:
            try:
                if self.use_adaptive:
                    elements = page.css(selector, adaptive=True)
                else:
                    elements = page.css(selector)
                
                if elements:
                    for el in elements:
                        text = el.text or ''
                        if self._is_promo_element(text):
                            promo_elements.append(el)
            except Exception:
                continue
        
        print(f"   📊 Encontrados {len(promo_elements)} elementos de promoción")
        
        if not promo_elements:
            print(f"   🔄 Intentando extracción por texto...")
            promotions = self._extract_from_full_text(page)
        else:
            for idx, element in enumerate(promo_elements):
                try:
                    promo = self._parse_promo_element(element)
                    if promo:
                        promotions.append(promo)
                except Exception as e:
                    print(f"   ⚠️ Error procesando elemento {idx+1}: {e}")
        
        seen = set()
        unique_promos = []
        for promo in promotions:
            entity = (promo.get('bank') or promo.get('wallet') or '').lower()
            # Use title prefix to catch near-identical promos from different context windows
            title_prefix = promo.get('title', '')[:80].lower().strip()
            key = (entity, promo.get('discount', ''), title_prefix)
            if key not in seen:
                seen.add(key)
                unique_promos.append(promo)

        return unique_promos

    def _is_promo_element(self, text: str) -> bool:
        """Determina si un texto corresponde a una promoción"""
        if not text or len(text) < 50:
            return False
        
        text_lower = text.lower()
        
        has_discount = bool(re.search(r'\d+\s*%', text))
        has_bank_info = any(bank in text_lower for bank in self._banks.keys())
        has_wallet_info = any(wallet in text_lower for wallet in self._wallets.keys())
        has_promo_keywords = any(kw in text_lower for kw in ['descuento', 'promoción', 'oferta', 'ahorro'])
        
        return has_discount and (has_bank_info or has_wallet_info or has_promo_keywords)

    def _parse_promo_element(self, element) -> Optional[Dict]:
        """Parsea un elemento de promoción y extrae datos estructurados"""
        try:
            full_text = element.text or ''
            if not full_text or len(full_text) < 30:
                return None
            
            title = ''
            title_el = element.css('h1, h2, h3, h4, h5, h6, [class*="title"], [class*="titulo"]')
            if title_el:
                title = title_el[0].text or ''
            
            if not title:
                title_match = re.search(r'(\d+%\s*(?:de\s*)?descuento[^.\n]{0,100})', full_text, re.IGNORECASE)
                if title_match:
                    title = title_match.group(1).strip()
            
            if not title:
                title = f"Promoción Carrefour"
            
            discount = self._extract_discount(full_text)
            bank = self._extract_bank(full_text)
            wallet = self._extract_wallet(full_text)
            
            terms = self._extract_terms(full_text)
            
            store_types = self._extract_store_types(full_text)
            valid_days = self._extract_valid_days(full_text)
            dates = self._extract_dates(full_text)
            
            payment_method = self._extract_payment_method(full_text)
            exclusions = self._extract_exclusions(full_text)
            requirements = self._extract_requirements(full_text)
            
            img_el = element.css('img')
            image_url = ''
            if img_el:
                image_url = img_el[0].attrib.get('src', '') or img_el[0].attrib.get('data-src', '')
            
            return {
                'title': self._clean_text(title),
                'discount': discount,
                'bank': bank,
                'wallet': wallet,
                'card_type': None,
                'payment_method': payment_method,
                'store_types': ', '.join(store_types) if store_types else None,
                'valid_days': valid_days,
                'url': self.url,
                'image_url': image_url,
                'terms_raw': self._clean_text(terms),
                'exclusions': '; '.join(exclusions[:10]) if exclusions else None,
                'requirements': '; '.join(requirements[:5]) if requirements else None,
                'valid_from': dates.get('valid_from'),
                'valid_until': dates.get('valid_until'),
            }
            
        except Exception as e:
            print(f"   ⚠️ Error parseando elemento: {e}")
            return None

    def _extract_from_full_text(self, page) -> List[Dict]:
        """Extracción fallback usando el texto completo de la página"""
        promotions = []
        
        try:
            html_content = str(page.html_content)
            
            text = re.sub(r'<[^>]+>', ' ', html_content)
            text = re.sub(r'\s+', ' ', text).strip()
            
            discount_pattern = r'(\d+)\s*%\s*(?:de\s*)?descuento'
            matches = list(re.finditer(discount_pattern, text, re.IGNORECASE))
            
            print(f"   🔍 Encontrados {len(matches)} patrones de descuento en texto")
            
            for match in matches:
                start = max(0, match.start() - 1500)
                end = min(len(text), match.end() + 3000)
                context = text[start:end]
                
                discount = match.group(1) + '%'
                
                title_match = re.search(r'(\d+%\s*(?:de\s*)?descuento[^.!?\n]{10,150})', context, re.IGNORECASE)
                title = title_match.group(1).strip() if title_match else f"Promoción {discount}"
                
                bank = self._extract_bank(context)
                wallet = self._extract_wallet(context)
                store_types = self._extract_store_types(context)
                terms = self._extract_terms(context)
                valid_days = self._extract_valid_days(context)
                dates = self._extract_dates(context)
                payment_method = self._extract_payment_method(context)
                exclusions = self._extract_exclusions(context)
                requirements = self._extract_requirements(context)
                
                promo = {
                    'title': self._clean_text(title),
                    'discount': discount,
                    'bank': bank,
                    'wallet': wallet,
                    'card_type': None,
                    'payment_method': payment_method,
                    'store_types': ', '.join(store_types) if store_types else None,
                    'valid_days': valid_days,
                    'url': self.url,
                    'image_url': '',
                    'terms_raw': self._clean_text(terms),
                    'exclusions': '; '.join(exclusions[:10]) if exclusions else None,
                    'requirements': '; '.join(requirements[:5]) if requirements else None,
                    'valid_from': dates.get('valid_from'),
                    'valid_until': dates.get('valid_until'),
                }
                
                promotions.append(promo)
                
        except Exception as e:
            print(f"   ❌ Error en extracción por texto: {e}")
        
        return promotions

    def _extract_discount(self, text: str) -> str:
        """Extrae porcentaje de descuento"""
        if not text:
            return ""
        
        percent_match = re.search(r'(\d+)\s*%', text)
        if percent_match:
            return f"{percent_match.group(1)}%"
        
        return ""

    def _extract_bank(self, text: str) -> Optional[str]:
        """Extrae banco del texto"""
        if not text:
            return None
        
        text_lower = text.lower()
        for key, value in self._banks.items():
            if key in text_lower:
                return value
        return None

    def _extract_wallet(self, text: str) -> Optional[str]:
        """Extrae billetera digital del texto"""
        if not text:
            return None
        
        text_lower = text.lower()
        for key, value in self._wallets.items():
            if key in text_lower:
                return value
        return None

    def _extract_terms(self, text: str) -> str:
        """Extrae términos y condiciones"""
        if not text:
            return ""
        
        terms_match = re.search(r'(PROMOCIÓN[A-ZÁÉÍÓÚÑ\s\d.,;:/()$%-]{200,3000})', text, re.IGNORECASE)
        if terms_match:
            return terms_match.group(1)
        
        upper_matches = re.findall(r'[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s\d.,;:/()$%-]{100,}', text)
        if upper_matches:
            return ' '.join(upper_matches[:3])
        
        return ""

    def _extract_store_types(self, text: str) -> List[str]:
        """Extrae tipos de tienda"""
        store_types = []
        
        if re.search(r'carrefour\s*market', text, re.IGNORECASE):
            store_types.append('Carrefour Market')
        if re.search(r'carrefour\s*express', text, re.IGNORECASE):
            store_types.append('Carrefour Express')
        if re.search(r'carrefour\s*maxi', text, re.IGNORECASE):
            store_types.append('Carrefour Maxi')
        if re.search(r'hipermercado', text, re.IGNORECASE):
            store_types.append('Hipermercado Carrefour')
        if re.search(r'carrefour\.com', text, re.IGNORECASE):
            store_types.append('Carrefour.com.ar')
        
        return store_types

    def _extract_valid_days(self, text: str) -> Optional[str]:
        """Extrae días válidos de la promoción"""
        days_match = re.search(
            r'(?:todos\s+los|los)\s+(lunes|martes|miércoles|jueves|viernes|sábado|domingo|miercoles|sabado)(?:\s+de\s+\w+)?',
            text, re.IGNORECASE
        )
        if days_match:
            return self._clean_text(days_match.group(0))
        return None

    def _extract_dates(self, text: str) -> Dict[str, Optional[str]]:
        """Extrae fechas de validez"""
        dates = {'valid_from': None, 'valid_until': None}
        
        if not text:
            return dates
        
        date_match = re.search(
            r'(?:desde|del)\s+(\d{1,2})\s+(?:al|hasta)\s+(\d{1,2})\s+(?:de\s+)?(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)(?:\s+de\s+)?(\d{4})?',
            text, re.IGNORECASE
        )
        
        if date_match:
            month_map = {
                'enero': '01', 'febrero': '02', 'marzo': '03', 'abril': '04',
                'mayo': '05', 'junio': '06', 'julio': '07', 'agosto': '08',
                'septiembre': '09', 'octubre': '10', 'noviembre': '11', 'diciembre': '12'
            }
            day_from = date_match.group(1).zfill(2)
            day_until = date_match.group(2).zfill(2)
            month = month_map.get(date_match.group(3).lower(), '01')
            year = date_match.group(4) or '2026'
            
            dates['valid_from'] = f"{year}-{month}-{day_from}"
            dates['valid_until'] = f"{year}-{month}-{day_until}"
        
        return dates

    def _extract_payment_method(self, text: str) -> Optional[str]:
        """Extrae método de pago"""
        payment_match = re.search(
            r'(?:con|mediante|usando|través de|a través)\s+([^\n.]{5,80}(?:dni|pago|tarjeta|visa|master|amex|cuenta)[^\n.]{0,30})',
            text, re.IGNORECASE
        )
        if payment_match:
            return self._clean_text(payment_match.group(1))
        return None

    def _extract_exclusions(self, text: str) -> List[str]:
        """Extrae exclusiones de la promoción"""
        if not text:
            return []
        
        exclusions = []
        patterns = [
            r'se\s+excluyen?\s+(?:de\s+la\s+promoción\s+)?([^.]+)',
            r'exclu(?:ye|ído)(?:s)?\s+([^.]+)',
            r'no\s+(?:incluye|aplica|válid[oa])\s+(?:para|en)\s+([^.]+)',
            r'excepto\s+([^.]+)',
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text.lower(), re.IGNORECASE)
            for match in matches:
                exclusion_text = match.group(1).strip()
                items = re.split(r'[,y]', exclusion_text)
                for item in items:
                    item = item.strip()
                    if item and 3 < len(item) < 100:
                        exclusions.append(item.capitalize())
        
        return list(set(exclusions))

    def _extract_requirements(self, text: str) -> List[str]:
        """Extrae requisitos de la promoción"""
        if not text:
            return []
        
        requirements = []
        patterns = [
            r'(?:solo|únicamente|exclusivamente)\s+(?:para|con)\s+([^.]{5,80})',
            r'(?:válid[oa]|aplicable)\s+(?:solo|únicamente)\s+(?:para|con)\s+([^.]{5,80})',
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text.lower(), re.IGNORECASE)
            for match in matches:
                req = match.group(1).strip()
                if 5 < len(req) < 100:
                    requirements.append(req.capitalize())
        
        nivel_match = re.search(r'nivel\s+(\d+|[a-z]+)', text.lower())
        if nivel_match:
            requirements.append(f"Nivel {nivel_match.group(1)}")
        
        card_types = ['black', 'platinum', 'signature', 'gold', 'infinite']
        for card_type in card_types:
            if card_type in text.lower():
                requirements.append(f"Tarjeta {card_type.title()}")
        
        return list(set(requirements))

    def _clean_text(self, text: str) -> str:
        """Limpia y normaliza texto"""
        if not text:
            return ""
        text = re.sub(r'\s+', ' ', text)
        text = text.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
        return text.strip()
