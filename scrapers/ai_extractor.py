"""
AI Extractor — extracción de promociones con visión por IA.
Soporta Gemini (gratis, prioridad) y Claude (Anthropic).

Prioridad de proveedor:
  1. GEMINI_API_KEY  → google-generativeai (gemini-2.0-flash por defecto)
  2. ANTHROPIC_API_KEY → anthropic (claude-haiku-4-5-20251001 por defecto)
"""
import os
import base64
import json
import asyncio
from typing import List, Dict, Optional
from datetime import datetime

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

# Ordered preference list — first available wins
_GEMINI_PRIORITY = [
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
]


def _resolve_gemini_model(preferred: str) -> str:
    """
    Query the Gemini API for available models and return the best one.
    Honours `preferred` if it's available; otherwise picks from _GEMINI_PRIORITY.
    Falls back to `preferred` unchanged if the API call fails.
    """
    if not GEMINI_AVAILABLE:
        return preferred
    try:
        available = {
            m.name.removeprefix("models/")
            for m in genai.list_models()
            if "generateContent" in (m.supported_generation_methods or [])
        }
        if preferred in available:
            return preferred
        for candidate in _GEMINI_PRIORITY:
            if candidate in available:
                print(f"   ⚠️ Modelo '{preferred}' no disponible → usando '{candidate}'")
                return candidate
        # Last resort: any flash/pro that supports generateContent
        for candidate in sorted(available):
            if "flash" in candidate or "pro" in candidate:
                print(f"   ⚠️ Usando modelo de fallback: '{candidate}'")
                return candidate
    except Exception as e:
        print(f"   ⚠️ No se pudo listar modelos Gemini ({e}), usando '{preferred}'")
    return preferred

try:
    import anthropic as _anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

_SYSTEM_PROMPT = """Eres un experto en extraer información de promociones bancarias de supermercados argentinos.

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

IMPORTANTE:
- Extrae TODAS las promociones visibles en la imagen
- Si un campo no está visible o no aplica, usa null
- Los descuentos pueden ser porcentajes (20%), montos ($500 OFF), o formatos especiales (3x2, 2do al 50%)
- Presta atención a los días de validez ya que muchas promos son solo ciertos días
- Si hay múltiples bancos en una misma promo, crea entradas separadas

Responde ÚNICAMENTE con un JSON válido con la siguiente estructura:
{
    "promotions": [
        {"title": "...", "discount": "...", "bank": "...", ...}
    ],
    "extraction_notes": "Notas sobre la extracción"
}"""


class AIExtractor:
    """
    Extractor de promociones con visión por IA.
    Usa Gemini si GEMINI_API_KEY está configurada, sino Claude.
    """

    def __init__(self, model: str = None, max_tokens: int = 4096):
        gemini_key = os.getenv("GEMINI_API_KEY")
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")

        if gemini_key and GEMINI_AVAILABLE:
            self.provider = "gemini"
            genai.configure(api_key=gemini_key)
            preferred = model or os.getenv("AI_MODEL", "gemini-2.0-flash")
            self.model_name = _resolve_gemini_model(preferred)
            self._gemini_model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=_SYSTEM_PROMPT,
            )
            print(f"   🤖 AI provider: Gemini ({self.model_name})")
        elif anthropic_key and ANTHROPIC_AVAILABLE:
            self.provider = "anthropic"
            self._anthropic_client = _anthropic.Anthropic(api_key=anthropic_key)
            self.model_name = model or os.getenv("AI_MODEL", "claude-haiku-4-5-20251001")
            self.max_tokens = max_tokens
            print(f"   🤖 AI provider: Claude ({self.model_name})")
        else:
            missing = []
            if not gemini_key:
                missing.append("GEMINI_API_KEY")
            if not anthropic_key:
                missing.append("ANTHROPIC_API_KEY")
            raise ValueError(
                f"No hay API key configurada. Configurá alguna de: {', '.join(missing)}"
            )

        self.system_prompt = _SYSTEM_PROMPT

    async def extract_from_screenshot(
        self,
        page,
        supermarket_name: str,
        url: str = None,
        scroll_and_capture: bool = True,
    ) -> List[Dict]:
        print(f"   🤖 Extrayendo con {self.provider} para {supermarket_name}...")

        screenshots = []
        try:
            if scroll_and_capture:
                screenshots = await self._capture_scrolling_screenshots(page)
            else:
                screenshots = [await page.screenshot(full_page=True)]

            print(f"   📸 {len(screenshots)} screenshot(s)")

            all_promotions: List[Dict] = []
            for i, shot in enumerate(screenshots):
                print(f"   🔍 Analizando screenshot {i+1}/{len(screenshots)}...")
                user_msg = (
                    f"Analiza esta imagen de la página de promociones de {supermarket_name}.\n"
                    + (f"URL: {url}\n" if url else "")
                    + f"Screenshot {i+1} de {len(screenshots)}.\n\n"
                    "Extrae TODAS las promociones bancarias visibles. Responde ÚNICAMENTE con JSON válido."
                )
                promos = await self._extract_from_image(shot, user_msg)
                for p in promos:
                    if not self._is_duplicate(p, all_promotions):
                        all_promotions.append(p)

            print(f"   ✅ {len(all_promotions)} promociones extraídas")
            return all_promotions

        except Exception as e:
            print(f"   ❌ Error en extracción con IA: {e}")
            import traceback
            traceback.print_exc()
            return []

    async def _extract_from_image(self, image_bytes: bytes, user_message: str) -> List[Dict]:
        if self.provider == "gemini":
            return await self._extract_gemini(image_bytes, user_message)
        return await self._extract_anthropic(image_bytes, user_message)

    async def _extract_gemini(self, image_bytes: bytes, user_message: str) -> List[Dict]:
        try:
            image_part = {"mime_type": "image/png", "data": image_bytes}
            response = await asyncio.to_thread(
                self._gemini_model.generate_content,
                [user_message, image_part],
            )
            return self._parse_response(response.text)
        except Exception as e:
            print(f"      ⚠️ Error Gemini: {e}")
            return []

    async def _extract_anthropic(self, image_bytes: bytes, user_message: str) -> List[Dict]:
        try:
            image_b64 = base64.b64encode(image_bytes).decode("utf-8")
            response = await asyncio.to_thread(
                self._anthropic_client.messages.create,
                model=self.model_name,
                max_tokens=self.max_tokens,
                system=self.system_prompt,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image_b64}},
                        {"type": "text", "text": user_message},
                    ],
                }],
            )
            return self._parse_response(response.content[0].text)
        except Exception as e:
            print(f"      ⚠️ Error Anthropic: {e}")
            return []

    async def _capture_scrolling_screenshots(self, page, max_screenshots: int = 5) -> List[bytes]:
        total_height = await page.evaluate("document.body.scrollHeight")
        viewport_height = await page.evaluate("window.innerHeight")
        num = min(max_screenshots, max(1, (total_height // viewport_height) + 1))

        await page.evaluate("window.scrollTo(0, 0)")
        await asyncio.sleep(0.5)

        shots = []
        for i in range(num):
            shots.append(await page.screenshot())
            if i < num - 1:
                await page.evaluate(f"window.scrollBy(0, {viewport_height * 0.8})")
                await asyncio.sleep(0.5)
        return shots

    def _parse_response(self, text: str) -> List[Dict]:
        try:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start == -1 or end == 0:
                return []
            data = json.loads(text[start:end])
            if data.get("extraction_notes"):
                print(f"      📝 {data['extraction_notes']}")
            return [self._normalize(p) for p in data.get("promotions", []) if self._normalize(p)]
        except json.JSONDecodeError as e:
            print(f"      ⚠️ JSON inválido: {e} — respuesta: {text[:300]}")
            return []

    def _normalize(self, promo: Dict) -> Optional[Dict]:
        if not promo.get("title") and not promo.get("discount"):
            return None
        exclusions = promo.get("exclusions", [])
        requirements = promo.get("requirements", [])
        return {
            "title": (promo.get("title") or "").strip(),
            "discount": (promo.get("discount") or "").strip(),
            "bank": promo.get("bank"),
            "wallet": promo.get("wallet"),
            "card_type": promo.get("card_type"),
            "payment_method": promo.get("payment_method"),
            "store_types": promo.get("store_types"),
            "valid_days": promo.get("valid_days"),
            "valid_from": self._parse_date(promo.get("valid_from")),
            "valid_until": self._parse_date(promo.get("valid_until")),
            "terms_raw": promo.get("terms_raw"),
            "tope": promo.get("tope"),
            "exclusions": json.dumps(exclusions, ensure_ascii=False) if isinstance(exclusions, list) else exclusions,
            "requirements": json.dumps(requirements, ensure_ascii=False) if isinstance(requirements, list) else requirements,
            "extracted_by": f"ai_vision_{self.provider}",
            "extracted_at": datetime.now().isoformat(),
        }

    def _parse_date(self, s: Optional[str]) -> Optional[str]:
        if not s:
            return None
        if len(s) == 10 and s[4] == "-":
            return s
        import re
        m = re.match(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", s)
        if m:
            d, mo, y = m.groups()
            return f"{y}-{mo.zfill(2)}-{d.zfill(2)}"
        return None

    def _is_duplicate(self, promo: Dict, existing: List[Dict]) -> bool:
        for e in existing:
            if (promo.get("title") == e.get("title")
                    and promo.get("bank") == e.get("bank")
                    and promo.get("discount") == e.get("discount")):
                return True
        return False
