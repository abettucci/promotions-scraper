"""
Scraper base con funcionalidades comunes
"""
import asyncio
import random
from typing import List, Dict, Optional
from abc import ABC, abstractmethod
from playwright.async_api import Page, Browser
import re

class BaseScraper(ABC):
    def __init__(self, name: str, url: str):
        self.name = name
        self.url = url
        self.promotions = []
    
    @abstractmethod
    async def scrape(self, page: Page) -> List[Dict]:
        """
        Método abstracto que debe implementar cada scraper
        Retorna lista de promociones encontradas
        """
        pass
    
    async def random_delay(self, min_sec: float = 1, max_sec: float = 3):
        """Delay aleatorio para simular comportamiento humano"""
        await asyncio.sleep(random.uniform(min_sec, max_sec))
    
    async def scroll_page(self, page: Page, scrolls: int = 3):
        """Scroll aleatorio en la página"""
        for _ in range(scrolls):
            await page.evaluate(f"""
                window.scrollBy({{
                    top: window.innerHeight * {random.uniform(0.3, 0.8)},
                    behavior: 'smooth'
                }});
            """)
            await self.random_delay(0.5, 1.5)
    
    async def wait_for_content(self, page: Page, timeout: int = 10000):
        """Espera a que cargue el contenido principal"""
        try:
            # Esperar a que la página no esté en loading
            await page.wait_for_load_state('networkidle', timeout=timeout)
        except:
            pass  # Continuar si timeout
    
    def extract_discount(self, text: str) -> str:
        """Extrae porcentaje o monto de descuento del texto"""
        if not text:
            return ""
        
        # Buscar porcentaje (ej: "40%", "40% OFF")
        percent_match = re.search(r'(\d+)\s*%', text)
        if percent_match:
            return f"{percent_match.group(1)}%"
        
        # Buscar "X por Y" (ej: "3x2", "2x1")
        xpory_match = re.search(r'(\d+)\s*x\s*(\d+)', text, re.IGNORECASE)
        if xpory_match:
            return f"{xpory_match.group(1)}x{xpory_match.group(2)}"
        
        # Buscar monto (ej: "$500 OFF")
        amount_match = re.search(r'\$\s*(\d+[\d.,]*)', text)
        if amount_match:
            return f"${amount_match.group(1)}"
        
        return text[:50] if text else ""
    
    def extract_bank(self, text: str) -> Optional[str]:
        """Extrae el nombre del banco del texto"""
        if not text:
            return None
        
        text_lower = text.lower()
        
        # Lista de bancos comunes en Argentina
        # Order matters: more specific patterns first to avoid false matches
        banks = {
            'carrefour banco': 'Carrefour Banco',
            'carrefour crédito': 'Carrefour Banco',
            'carrefour credito': 'Carrefour Banco',
            'mi carrefour': 'Carrefour Banco',
            'cuenta digital': 'Carrefour Banco',
            'club la naci': 'Club La Nación',
            'galicia': 'Banco Galicia',
            'santander': 'Santander',
            'bbva': 'BBVA',
            'macro': 'Macro',
            'icbc': 'ICBC',
            'hsbc': 'HSBC',
            'ciudad': 'Banco Ciudad',
            'nacion': 'Banco Nación',
            'patagonia': 'Banco Patagonia',
            'credicoop': 'Credicoop',
            'supervielle': 'Supervielle',
            'frances': 'Banco Francés',
            'itau': 'Itaú',
            'comafi': 'Comafi',
            'piano': 'Piano',
            'bind': 'Bind',
        }
        
        for key, value in banks.items():
            if key in text_lower:
                return value
        
        return None
    
    def extract_wallet(self, text: str) -> Optional[str]:
        """Extrae el nombre de la billetera digital del texto"""
        if not text:
            return None
        
        text_lower = text.lower()
        
        wallets = {
            'mercado pago': 'Mercado Pago',
            'ualá': 'Ualá',
            'uala': 'Ualá',
            'naranjax': 'Naranja X',
            'naranja x': 'Naranja X',
            'modo': 'MODO',
            'personal pay': 'Personal Pay',
            'cuenta dni': 'Cuenta DNI',
            'claro pay': 'Claro Pay',
            'tap': 'Tap',
            'bimo': 'Bimo',
            'prex': 'Prex',
        }
        
        for key, value in wallets.items():
            if key in text_lower:
                return value
        
        return None
    
    def extract_dates(self, text: str) -> Dict[str, Optional[str]]:
        """Extrae fechas de validez del texto"""
        dates = {'valid_from': None, 'valid_until': None}
        
        if not text:
            return dates
        
        # Buscar "válido hasta DD/MM" o "hasta DD/MM"
        until_match = re.search(r'hasta\s+(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?', text, re.IGNORECASE)
        if until_match:
            day = until_match.group(1).zfill(2)
            month = until_match.group(2).zfill(2)
            year = until_match.group(3) if until_match.group(3) else '2025'
            if len(year) == 2:
                year = f"20{year}"
            dates['valid_until'] = f"{year}-{month}-{day}"
        
        # Buscar "desde DD/MM" o "del DD/MM"
        from_match = re.search(r'(?:desde|del)\s+(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?', text, re.IGNORECASE)
        if from_match:
            day = from_match.group(1).zfill(2)
            month = from_match.group(2).zfill(2)
            year = from_match.group(3) if from_match.group(3) else '2025'
            if len(year) == 2:
                year = f"20{year}"
            dates['valid_from'] = f"{year}-{month}-{day}"
        
        return dates
    
    def clean_text(self, text: str) -> str:
        """Limpia y normaliza texto"""
        if not text:
            return ""
        
        # Remover espacios múltiples
        text = re.sub(r'\s+', ' ', text)
        # Remover caracteres especiales molestos
        text = text.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
        return text.strip()

