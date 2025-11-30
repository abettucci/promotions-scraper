"""
Scraper simple para Carrefour usando requests (sin navegador)
Mucho más rápido y evita timeouts de Playwright
"""
import re
import requests
from typing import List, Dict
from bs4 import BeautifulSoup

class CarrefourSimpleScraper:
    def __init__(self):
        self.name = 'Carrefour'
        self.url = 'https://www.carrefour.com.ar/descuentos-bancarios'
        self.session = requests.Session()
        # Nota: requests maneja automáticamente la descompresión si Accept-Encoding está presente
        # Si hay problemas, se puede quitar Accept-Encoding para recibir sin comprimir
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'es-AR,es;q=0.9,en;q=0.8',
            # Comentar la siguiente línea si hay problemas de descompresión:
            # 'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache'
        })
    
    def scrape(self) -> List[Dict]:
        """Scrape sin navegador usando requests"""
        try:
            print(f"🔍 Scraping {self.name} (método simple)...")
            print(f"   🌐 URL: {self.url}")
            
            # Hacer request HTTP simple
            # Importante: requests debería descomprimir automáticamente, pero lo forzamos
            response = self.session.get(self.url, timeout=30)
            print(f"   📡 Status: {response.status_code}")
            
            if response.status_code != 200:
                print(f"   ❌ Error HTTP: {response.status_code}")
                return []
            
            # Verificar encoding
            print(f"   📝 Encoding: {response.encoding}")
            print(f"   📦 Content-Type: {response.headers.get('Content-Type', 'unknown')}")
            
            # Obtener el contenido (debería estar descomprimido automáticamente)
            # Si response.text falla o está vacío, intentar con response.content
            html_content = response.text
            
            # Verificar si el contenido parece estar comprimido
            if len(html_content) > 0 and html_content[0] not in ['<', '\n', ' ', '!']:
                print(f"   ⚠️ El contenido parece estar comprimido, intentando descomprimir...")
                import gzip
                try:
                    html_content = gzip.decompress(response.content).decode('utf-8')
                    print(f"   ✅ Contenido descomprimido exitosamente")
                except:
                    print(f"   ❌ No se pudo descomprimir, usando contenido original")
            
            # Parsear HTML
            soup = BeautifulSoup(html_content, 'html.parser')
            print(f"   📄 HTML recibido: {len(html_content)} caracteres")
            
            # Verificar si es HTML válido
            if '<html' not in html_content.lower() and '<body' not in html_content.lower():
                print(f"   ⚠️ El contenido no parece ser HTML válido")
                # Guardar para debug de todas formas
                with open('debug_carrefour_raw.bin', 'wb') as f:
                    f.write(response.content)
                print(f"   💾 Contenido raw guardado en: debug_carrefour_raw.bin")
            
            # Guardar HTML para debug
            with open('debug_carrefour_simple.html', 'w', encoding='utf-8') as f:
                f.write(html_content)
            print(f"   💾 HTML guardado en: debug_carrefour_simple.html")
            
            # Extraer promociones
            promotions = self._extract_promotions(html_content, soup)
            
            print(f"✅ {self.name}: {len(promotions)} promociones encontradas")
            return promotions
            
        except Exception as e:
            print(f"❌ Error en {self.name}: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _extract_promotions(self, html_text: str, soup: BeautifulSoup) -> List[Dict]:
        """Extrae promociones del HTML"""
        promotions = []
        
        # Método 1: Buscar patrones de descuento en el texto
        discount_pattern = r'(\d+)\s*%\s*(?:de\s*)?descuento'
        matches = list(re.finditer(discount_pattern, html_text, re.IGNORECASE))
        
        print(f"   🔍 Encontrados {len(matches)} patrones de descuento")
        
        for idx, match in enumerate(matches):
            # Extraer contexto alrededor del descuento
            start = max(0, match.start() - 2000)
            end = min(len(html_text), match.end() + 5000)
            context = html_text[start:end]
            
            # Limpiar HTML tags
            text = re.sub(r'<[^>]+>', ' ', context)
            text = re.sub(r'\s+', ' ', text).strip()
            
            discount = match.group(1) + '%'
            
            # Buscar título (texto cerca del descuento)
            title_patterns = [
                r'(\d+%\s*de\s*descuento[^.!?\n]{10,200})',
                r'([^.!?\n]{10,100}\d+%\s*de\s*descuento)',
            ]
            
            title = f"Promoción {discount}"
            for pattern in title_patterns:
                title_match = re.search(pattern, text, re.IGNORECASE)
                if title_match:
                    title = self._clean_text(title_match.group(1))
                    break
            
            # Extraer método de pago
            payment_method = ''
            payment_patterns = [
                r'(?:con|mediante|usando)\s+([^.!\n]{5,80}(?:dni|tarjeta|cuenta|visa|master|banco)[^.!\n]{0,50})',
                r'(cuenta\s+dni[^.!\n]{0,50})',
                r'(tarjeta[^.!\n]{5,80})',
            ]
            
            for pattern in payment_patterns:
                payment_match = re.search(pattern, text, re.IGNORECASE)
                if payment_match:
                    payment_method = self._clean_text(payment_match.group(1))
                    break
            
            # Detectar banco/billetera
            bank = self._extract_bank(text)
            wallet = self._extract_wallet(text)
            
            # Buscar tipos de tienda
            store_types = []
            if re.search(r'carrefour\s*market', text, re.IGNORECASE):
                store_types.append('Carrefour Market')
            if re.search(r'carrefour\s*express', text, re.IGNORECASE):
                store_types.append('Carrefour Express')
            if re.search(r'carrefour\s*maxi', text, re.IGNORECASE):
                store_types.append('Carrefour Maxi')
            if re.search(r'hipermercado', text, re.IGNORECASE):
                store_types.append('Hipermercado Carrefour')
            
            store_types_str = ', '.join(store_types) if store_types else None
            
            # Buscar T&C (texto en mayúsculas largo)
            terms = ''
            terms_match = re.search(r'(PROMOCIÓN[A-ZÁÉÍÓÚÑ\s\d.,;:/()$%-]{200,3000})', text, re.IGNORECASE)
            if terms_match:
                terms = self._clean_text(terms_match.group(1))
            
            # Extraer días válidos
            valid_days = ''
            days_match = re.search(r'(?:todos\s+los|los)\s+(lunes|martes|miércoles|jueves|viernes|sábado|domingo|miercoles|sabado)(?:\s+de\s+\w+)?', text, re.IGNORECASE)
            if days_match:
                valid_days = self._clean_text(days_match.group(0))
            
            # Extraer fechas
            valid_from = ''
            valid_until = ''
            date_match = re.search(r'(?:desde|del)\s+(\d{1,2})\s+(?:al|hasta)\s+(\d{1,2})\s+(?:de\s+)?(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)(?:\s+de\s+)?(\d{4})?', text, re.IGNORECASE)
            
            if date_match:
                month_map = {
                    'enero': '01', 'febrero': '02', 'marzo': '03', 'abril': '04',
                    'mayo': '05', 'junio': '06', 'julio': '07', 'agosto': '08',
                    'septiembre': '09', 'octubre': '10', 'noviembre': '11', 'diciembre': '12'
                }
                day_from = date_match.group(1).zfill(2)
                day_until = date_match.group(2).zfill(2)
                month = month_map.get(date_match.group(3).lower(), '01')
                year = date_match.group(4) or '2025'
                
                valid_from = f"{year}-{month}-{day_from}"
                valid_until = f"{year}-{month}-{day_until}"
            
            # Extraer exclusiones
            exclusions = self._extract_exclusions(text)
            exclusions_str = '; '.join(exclusions[:10]) if exclusions else None
            
            # Extraer requisitos
            requirements = self._extract_requirements(text)
            requirements_str = '; '.join(requirements[:5]) if requirements else None
            
            promo = {
                'title': title,
                'discount': discount,
                'bank': bank,
                'wallet': wallet,
                'card_type': None,
                'payment_method': payment_method or None,
                'store_types': store_types_str,
                'valid_days': valid_days or None,
                'url': self.url,
                'image_url': '',
                'terms_raw': terms,
                'exclusions': exclusions_str,
                'requirements': requirements_str,
                'valid_from': valid_from or None,
                'valid_until': valid_until or None,
            }
            
            promotions.append(promo)
        
        # Deduplicar por título
        seen_titles = set()
        unique_promos = []
        for promo in promotions:
            if promo['title'] not in seen_titles:
                seen_titles.add(promo['title'])
                unique_promos.append(promo)
        
        return unique_promos
    
    def _clean_text(self, text: str) -> str:
        """Limpia texto"""
        if not text:
            return ""
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def _extract_bank(self, text: str) -> str:
        """Extrae banco del texto"""
        text_lower = text.lower()
        
        banks = {
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
        
        for key, value in banks.items():
            if key in text_lower:
                return value
        
        return None
    
    def _extract_wallet(self, text: str) -> str:
        """Extrae billetera digital"""
        text_lower = text.lower()
        
        wallets = {
            'cuenta dni': 'Cuenta DNI',
            'mercado pago': 'Mercado Pago',
            'ualá': 'Ualá',
            'uala': 'Ualá',
            'naranja x': 'Naranja X',
            'modo': 'MODO',
            'personal pay': 'Personal Pay',
        }
        
        for key, value in wallets.items():
            if key in text_lower:
                return value
        
        return None
    
    def _extract_exclusions(self, text: str) -> List[str]:
        """Extrae exclusiones"""
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
                    if item and len(item) > 3 and len(item) < 100:
                        exclusions.append(item.capitalize())
        
        return list(set(exclusions))
    
    def _extract_requirements(self, text: str) -> List[str]:
        """Extrae requisitos"""
        requirements = []
        
        patterns = [
            r'(?:solo|únicamente|exclusivamente)\s+(?:para|con)\s+([^.]{5,80})',
            r'(?:válid[oa]|aplicable)\s+(?:solo|únicamente)\s+(?:para|con)\s+([^.]{5,80})',
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text.lower(), re.IGNORECASE)
            for match in matches:
                req = match.group(1).strip()
                if len(req) > 5 and len(req) < 100:
                    requirements.append(req.capitalize())
        
        return list(set(requirements))

