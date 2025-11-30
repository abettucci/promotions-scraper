"""
Scraper genérico que funciona para la mayoría de supermercados
Puede ser utilizado como fallback o base para otros scrapers
"""
from typing import List, Dict
from playwright.async_api import Page
from .base_scraper import BaseScraper

class GenericScraper(BaseScraper):
    """
    Scraper genérico que intenta múltiples selectores comunes
    Funciona bien para la mayoría de sitios de supermercados argentinos
    """
    
    async def scrape(self, page: Page) -> List[Dict]:
        """Scraper genérico con múltiples estrategias"""
        try:
            print(f"🔍 Scraping {self.name}...")
            
            await page.goto(self.url, wait_until='domcontentloaded', timeout=30000)
            await self.random_delay(2, 4)
            
            # Scroll para cargar contenido lazy
            await self.scroll_page(page, scrolls=4)
            await self.random_delay(1, 2)
            
            # Extraer promociones con selectores genéricos
            promotions = await page.evaluate("""() => {
                const items = [];
                
                // Selectores comunes en sitios de supermercados
                const containerSelectors = [
                    '.promotion-card', '.promo-card', '.card-promocion',
                    '[data-promo]', '[data-promotion]',
                    '.ofertas-item', '.oferta-card',
                    '.banco-promo', '.promo-banco',
                    'article[class*="promo"]', 'article[class*="oferta"]',
                    'div[class*="promocion"]', 'div[class*="promotion"]',
                    '.product-promo', '.tarjeta-promo',
                    '[class*="PromotionCard"]', '[class*="PromoCard"]'
                ];
                
                let elements = [];
                for (const selector of containerSelectors) {
                    elements = document.querySelectorAll(selector);
                    if (elements.length > 0) {
                        console.log(`Found ${elements.length} items with selector: ${selector}`);
                        break;
                    }
                }
                
                // Si no encuentra con los selectores específicos, buscar por estructura
                if (elements.length === 0) {
                    // Buscar divs que contengan imágenes y texto de promoción
                    const allDivs = document.querySelectorAll('div, article, section');
                    allDivs.forEach(div => {
                        const text = div.innerText?.toLowerCase() || '';
                        const hasImg = div.querySelector('img') !== null;
                        const hasPromoKeywords = /promocion|descuento|off|banco|tarjeta|%/.test(text);
                        
                        if (hasImg && hasPromoKeywords && text.length > 20 && text.length < 500) {
                            if (!Array.from(elements).includes(div)) {
                                elements = [...elements, div];
                            }
                        }
                    });
                }
                
                elements.forEach(el => {
                    // Selectores para título
                    const titleSelectors = [
                        'h1', 'h2', 'h3', 'h4', 'h5',
                        '.title', '.titulo', '.heading',
                        '[class*="title"]', '[class*="Title"]',
                        '[class*="heading"]'
                    ];
                    
                    let titleEl = null;
                    for (const sel of titleSelectors) {
                        titleEl = el.querySelector(sel);
                        if (titleEl) break;
                    }
                    
                    // Selectores para descuento
                    const discountSelectors = [
                        '.discount', '.descuento', '.porcentaje',
                        '[class*="discount"]', '[class*="Discount"]',
                        '.off', '.percentage', '.rebate'
                    ];
                    
                    let discountEl = null;
                    for (const sel of discountSelectors) {
                        discountEl = el.querySelector(sel);
                        if (discountEl) break;
                    }
                    
                    // Selectores para banco
                    const bankSelectors = [
                        '.bank', '.banco', '.payment-method',
                        '[class*="bank"]', '[class*="Bank"]',
                        '[class*="payment"]'
                    ];
                    
                    let bankEl = null;
                    for (const sel of bankSelectors) {
                        bankEl = el.querySelector(sel);
                        if (bankEl) break;
                    }
                    
                    // Selectores para términos
                    const termsSelectors = [
                        '.terms', '.terminos', '.condiciones',
                        '[class*="terms"]', '[class*="Terms"]',
                        'small', '.legal', '.disclaimer',
                        '[class*="condition"]'
                    ];
                    
                    let termsEl = null;
                    for (const sel of termsSelectors) {
                        termsEl = el.querySelector(sel);
                        if (termsEl) break;
                    }
                    
                    const imgEl = el.querySelector('img');
                    const linkEl = el.querySelector('a');
                    
                    const title = titleEl?.innerText || el.innerText?.split('\\n')[0] || '';
                    const discount = discountEl?.innerText || '';
                    const bank = bankEl?.innerText || '';
                    const terms = termsEl?.innerText || '';
                    const image = imgEl?.src || imgEl?.dataset?.src || '';
                    const url = linkEl?.href || window.location.href;
                    
                    // Filtrar ruido: solo agregar si tiene título válido
                    if (title && title.length > 3 && title.length < 200) {
                        items.push({
                            title: title.trim(),
                            discount: discount.trim(),
                            bank: bank.trim(),
                            terms: terms.trim(),
                            image_url: image,
                            url: url
                        });
                    }
                });
                
                return items;
            }""")
            
            # Procesar y enriquecer promociones
            processed_promos = []
            seen_titles = set()  # Para evitar duplicados
            
            for promo in promotions:
                title = self.clean_text(promo.get('title', ''))
                
                # Evitar duplicados
                if title in seen_titles or len(title) < 5:
                    continue
                seen_titles.add(title)
                
                # Texto completo para extraer información
                raw_text = f"{title} {promo.get('discount', '')} {promo.get('bank', '')} {promo.get('terms', '')}"
                
                processed = {
                    'title': title,
                    'discount': self.extract_discount(promo.get('discount', '') or title),
                    'bank': self.extract_bank(raw_text),
                    'wallet': self.extract_wallet(raw_text),
                    'card_type': None,
                    'url': promo.get('url', ''),
                    'image_url': promo.get('image_url', ''),
                    'terms_raw': self.clean_text(promo.get('terms', '')),
                }
                
                # Extraer fechas de validez
                dates = self.extract_dates(promo.get('terms', '') or title)
                processed.update(dates)
                
                processed_promos.append(processed)
            
            print(f"✅ {self.name}: {len(processed_promos)} promociones encontradas")
            return processed_promos
            
        except Exception as e:
            print(f"❌ Error en {self.name}: {e}")
            import traceback
            traceback.print_exc()
            return []

