"""
AI Extractor - Extracción de promociones usando Claude Vision
Toma screenshots de las páginas y usa IA para extraer datos estructurados
"""
import os
import base64
import json
import asyncio
from typing import List, Dict, Optional
from datetime import datetime

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


class AIExtractor:
    """
    Extractor de promociones usando Claude Vision.
    Toma screenshots de páginas web y extrae promociones bancarias estructuradas.
    """
    
    def __init__(self, api_key: str = None, model: str = None, max_tokens: int = 4096):
        if not ANTHROPIC_AVAILABLE:
            raise ImportError(
                "El paquete 'anthropic' no está instalado. "
                "Ejecuta: pip install anthropic"
            )
        
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "API key de Anthropic no configurada. "
                "Configura la variable de entorno ANTHROPIC_API_KEY o pasa api_key al constructor."
            )
        
        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.model = model or os.getenv("AI_MODEL", "claude-sonnet-4-20250514")
        self.max_tokens = max_tokens
        
        # Prompt del sistema para extracción de promociones
        self.system_prompt = """Eres un experto en extraer información de promociones bancarias de supermercados argentinos.

Tu tarea es analizar la imagen de una página web de promociones y extraer TODAS las promociones bancarias visibles.

Para cada promoción, extrae la siguiente información en formato JSON:
- title: Título o descripción principal de la promoción
- discount: Porcentaje de descuento (ej: "20%", "30%", "3x2")
- bank: Nombre del banco (ej: "Banco Galicia", "Santander", "BBVA", "Macro", etc.)
- wallet: Billetera digital si aplica (ej: "Mercado Pago", "Ualá", "Naranja X", "MODO")
- card_type: Tipo de tarjeta si se especifica (ej: "Crédito", "Débito", "Todas")
- payment_method: Método de pago específico si se menciona
- store_types: Tipos de tienda donde aplica (ej: "Hipermercado", "Express", "Market")
- valid_days: Días de validez (ej: "Lunes y Martes", "Todos los días", "Fines de semana")
- valid_from: Fecha de inicio en formato YYYY-MM-DD si está visible
- valid_until: Fecha de fin en formato YYYY-MM-DD si está visible
- terms_raw: Términos y condiciones visibles (texto completo si es legible)
- tope: Tope de reintegro/descuento si se menciona (ej: "$5000", "$10000")
- exclusions: Lista de exclusiones mencionadas
- requirements: Lista de requisitos (ej: "Nivel Black", "Paquete Select")
- image_description: Breve descripción de la imagen/banner de la promo si hay

IMPORTANTE:
- Extrae TODAS las promociones visibles en la imagen
- Si un campo no está visible o no aplica, usa null
- Los descuentos pueden ser porcentajes (20%), montos ($500 OFF), o formatos especiales (3x2, 2do al 50%)
- Presta atención a los días de validez ya que muchas promos son solo ciertos días
- Los términos y condiciones suelen estar en letra pequeña
- Si hay múltiples bancos en una misma promo, crea entradas separadas

Responde ÚNICAMENTE con un JSON válido con la siguiente estructura:
{
    "promotions": [
        {
            "title": "...",
            "discount": "...",
            "bank": "...",
            ...
        }
    ],
    "extraction_notes": "Notas sobre la extracción (problemas, elementos no legibles, etc.)"
}"""

    async def extract_from_screenshot(
        self, 
        page, 
        supermarket_name: str,
        url: str = None,
        scroll_and_capture: bool = True
    ) -> List[Dict]:
        """
        Extrae promociones de una página usando Claude Vision.
        
        Args:
            page: Página de Playwright
            supermarket_name: Nombre del supermercado para contexto
            url: URL de la página (opcional, para contexto)
            scroll_and_capture: Si True, hace scroll y captura múltiples screenshots
            
        Returns:
            Lista de diccionarios con las promociones extraídas
        """
        print(f"   🤖 Extrayendo promociones con IA para {supermarket_name}...")
        
        all_promotions = []
        screenshots = []
        
        try:
            if scroll_and_capture:
                # Capturar múltiples screenshots haciendo scroll
                screenshots = await self._capture_scrolling_screenshots(page)
            else:
                # Capturar solo un screenshot de la página completa
                screenshot_bytes = await page.screenshot(full_page=True)
                screenshots = [screenshot_bytes]
            
            print(f"   📸 {len(screenshots)} screenshot(s) capturado(s)")
            
            # Procesar cada screenshot con Claude Vision
            for i, screenshot_bytes in enumerate(screenshots):
                print(f"   🔍 Analizando screenshot {i+1}/{len(screenshots)}...")
                
                promotions = await self._extract_from_image(
                    screenshot_bytes, 
                    supermarket_name,
                    url,
                    screenshot_index=i+1,
                    total_screenshots=len(screenshots)
                )
                
                # Agregar promociones evitando duplicados
                for promo in promotions:
                    if not self._is_duplicate(promo, all_promotions):
                        all_promotions.append(promo)
            
            print(f"   ✅ {len(all_promotions)} promociones extraídas con IA")
            return all_promotions
            
        except Exception as e:
            print(f"   ❌ Error en extracción con IA: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    async def _capture_scrolling_screenshots(self, page, max_screenshots: int = 5) -> List[bytes]:
        """
        Captura múltiples screenshots haciendo scroll en la página.
        """
        screenshots = []
        
        # Obtener altura total de la página
        total_height = await page.evaluate("document.body.scrollHeight")
        viewport_height = await page.evaluate("window.innerHeight")
        
        # Calcular número de screenshots necesarios
        num_screenshots = min(
            max_screenshots,
            max(1, (total_height // viewport_height) + 1)
        )
        
        # Scroll al inicio
        await page.evaluate("window.scrollTo(0, 0)")
        await asyncio.sleep(0.5)
        
        for i in range(num_screenshots):
            # Capturar screenshot del viewport actual
            screenshot = await page.screenshot()
            screenshots.append(screenshot)
            
            if i < num_screenshots - 1:
                # Scroll hacia abajo
                scroll_amount = viewport_height * 0.8  # 80% del viewport para overlap
                await page.evaluate(f"window.scrollBy(0, {scroll_amount})")
                await asyncio.sleep(0.5)
        
        return screenshots
    
    async def _extract_from_image(
        self, 
        image_bytes: bytes, 
        supermarket_name: str,
        url: str = None,
        screenshot_index: int = 1,
        total_screenshots: int = 1
    ) -> List[Dict]:
        """
        Envía una imagen a Claude Vision y extrae las promociones.
        """
        # Convertir imagen a base64
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        
        # Construir mensaje con contexto
        user_message = f"""Analiza esta imagen de la página de promociones de {supermarket_name}.
{"URL: " + url if url else ""}
Screenshot {screenshot_index} de {total_screenshots}.

Extrae TODAS las promociones bancarias visibles en la imagen.
Responde ÚNICAMENTE con JSON válido."""

        try:
            # Llamar a Claude Vision
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=self.system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": image_base64
                                }
                            },
                            {
                                "type": "text",
                                "text": user_message
                            }
                        ]
                    }
                ]
            )
            
            # Extraer texto de la respuesta
            response_text = response.content[0].text
            
            # Parsear JSON
            promotions = self._parse_response(response_text)
            return promotions
            
        except anthropic.APIError as e:
            print(f"      ⚠️ Error de API Anthropic: {e}")
            return []
        except Exception as e:
            print(f"      ⚠️ Error procesando imagen: {e}")
            return []
    
    def _parse_response(self, response_text: str) -> List[Dict]:
        """
        Parsea la respuesta JSON de Claude.
        """
        try:
            # Intentar encontrar JSON en la respuesta
            # A veces Claude incluye texto antes/después del JSON
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                print("      ⚠️ No se encontró JSON en la respuesta")
                return []
            
            json_str = response_text[json_start:json_end]
            data = json.loads(json_str)
            
            promotions = data.get('promotions', [])
            
            # Notas de extracción (para debug)
            if data.get('extraction_notes'):
                print(f"      📝 Notas: {data['extraction_notes']}")
            
            # Normalizar y limpiar promociones
            cleaned_promotions = []
            for promo in promotions:
                cleaned = self._normalize_promotion(promo)
                if cleaned:
                    cleaned_promotions.append(cleaned)
            
            return cleaned_promotions
            
        except json.JSONDecodeError as e:
            print(f"      ⚠️ Error parseando JSON: {e}")
            print(f"      Respuesta: {response_text[:500]}...")
            return []
    
    def _normalize_promotion(self, promo: Dict) -> Optional[Dict]:
        """
        Normaliza y valida una promoción extraída.
        """
        # Campos requeridos mínimos
        if not promo.get('title') and not promo.get('discount'):
            return None
        
        # Estructura normalizada
        normalized = {
            'title': promo.get('title', '').strip() if promo.get('title') else '',
            'discount': promo.get('discount', '').strip() if promo.get('discount') else '',
            'bank': promo.get('bank'),
            'wallet': promo.get('wallet'),
            'card_type': promo.get('card_type'),
            'payment_method': promo.get('payment_method'),
            'store_types': promo.get('store_types'),
            'valid_days': promo.get('valid_days'),
            'valid_from': self._parse_date(promo.get('valid_from')),
            'valid_until': self._parse_date(promo.get('valid_until')),
            'terms_raw': promo.get('terms_raw'),
            'tope': promo.get('tope'),
            'exclusions': promo.get('exclusions', []),
            'requirements': promo.get('requirements', []),
            'url': promo.get('url'),
            'image_url': promo.get('image_url'),
            'extracted_by': 'ai_vision',
            'extracted_at': datetime.now().isoformat()
        }
        
        # Convertir listas a strings si es necesario (para compatibilidad con DB)
        if isinstance(normalized['exclusions'], list):
            normalized['exclusions'] = json.dumps(normalized['exclusions'], ensure_ascii=False)
        if isinstance(normalized['requirements'], list):
            normalized['requirements'] = json.dumps(normalized['requirements'], ensure_ascii=False)
        
        return normalized
    
    def _parse_date(self, date_str: Optional[str]) -> Optional[str]:
        """
        Intenta parsear una fecha a formato YYYY-MM-DD.
        """
        if not date_str:
            return None
        
        # Si ya está en formato correcto
        if len(date_str) == 10 and date_str[4] == '-' and date_str[7] == '-':
            return date_str
        
        # Intentar parsear formatos comunes
        import re
        
        # DD/MM/YYYY o DD-MM-YYYY
        match = re.match(r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})', date_str)
        if match:
            day, month, year = match.groups()
            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        
        # DD/MM o DD-MM (asumir año actual)
        match = re.match(r'(\d{1,2})[/-](\d{1,2})', date_str)
        if match:
            day, month = match.groups()
            year = datetime.now().year
            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        
        return None
    
    def _is_duplicate(self, promo: Dict, existing: List[Dict]) -> bool:
        """
        Verifica si una promoción ya existe en la lista.
        """
        for existing_promo in existing:
            # Comparar por título y banco
            if (promo.get('title') == existing_promo.get('title') and
                promo.get('bank') == existing_promo.get('bank') and
                promo.get('discount') == existing_promo.get('discount')):
                return True
        return False


# Función de utilidad para pruebas
async def test_ai_extractor():
    """
    Función de prueba para el AIExtractor.
    """
    from playwright.async_api import async_playwright
    
    extractor = AIExtractor()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Probar con Carrefour
        url = "https://www.carrefour.com.ar/descuentos-bancarios"
        print(f"\n🧪 Probando AIExtractor con {url}")
        
        await page.goto(url, wait_until='networkidle', timeout=60000)
        await asyncio.sleep(3)
        
        promotions = await extractor.extract_from_screenshot(
            page, 
            "Carrefour",
            url
        )
        
        print(f"\n📊 Resultados:")
        print(f"   Total promociones: {len(promotions)}")
        
        for i, promo in enumerate(promotions[:3]):  # Mostrar primeras 3
            print(f"\n   Promo {i+1}:")
            print(f"   - Título: {promo.get('title', 'N/A')}")
            print(f"   - Descuento: {promo.get('discount', 'N/A')}")
            print(f"   - Banco: {promo.get('bank', 'N/A')}")
            print(f"   - Días: {promo.get('valid_days', 'N/A')}")
        
        await browser.close()


if __name__ == "__main__":
    asyncio.run(test_ai_extractor())
