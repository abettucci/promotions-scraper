import unittest
from datetime import date
from unittest import mock

from scrapers import mercadopago_scraper
from scrapers.mercadopago_scraper import MercadoPagoScraper


HTML = """
<div class="kiyo__data--modal">
  <div class="kiyo__data--details-logo"><img src="https://cdn.example/jumbo.jpg"><h3>Jumbo</h3></div>
  <div class="kiyo__cards--badge"><span>20% OFF</span></div>
  <div class="kiyo__cards--badge kiyo__cards--badge2"><span>3 cuotas sin interés</span></div>
  <div class="kiyo__data--details-row1"><p>20% OFF con Tarjeta de Mercado Pago en la tienda online.</p></div>
  <div class="kiyo__data--details-btn"><a href="https://promociones.mercadopago.com.ar/seller/jumbo/">Ir</a></div>
  <div class="kiyo__data--details-row2"><small>Válido del 11 al 17 de mayo de 2026. Tope de reintegro $30.000. Compras desde $70.000.</small></div>
</div>
<div class="kiyo__data--modal">
  <div class="kiyo__data--details-logo"><img src="https://cdn.example/dia.jpg"><h3>DIA</h3></div>
  <div class="kiyo__cards--badge"><span>Hasta 20% OFF</span></div>
  <div class="kiyo__data--details-row1"><p>¡Aprovechá hasta 20% OFF sin mínimo de compra y sin tope de reintegro!</p></div>
  <div class="kiyo__data--details-row2"><small>Válido 11/05, 13/05</small></div>
</div>
"""


class MercadoPagoScraperTests(unittest.TestCase):
    def test_parses_public_promotion_card(self):
        promotions = MercadoPagoScraper().parse_html(HTML)

        self.assertEqual(len(promotions), 2)
        promo = promotions[0]
        self.assertEqual(promo["title"], "Mercado Pago 20% en Jumbo")
        self.assertEqual(promo["merchant_brands"], ["Jumbo (Cencosud)"])
        self.assertEqual(promo["merchant_category"], "supermarket")
        self.assertEqual(promo["wallet"], "Mercado Pago")
        self.assertEqual(promo["discount"], "20% OFF")
        self.assertEqual(promo["valid_from"], "2026-05-11")
        self.assertEqual(promo["valid_until"], "2026-05-17")
        self.assertEqual(promo["tope"], "$30.000")
        self.assertEqual(promo["min_purchase"], "$70.000")
        self.assertIn("Tarjeta de Mercado Pago", promo["terms_raw"])

    def test_parses_ddmm_dates_without_year(self):
        with mock.patch.object(mercadopago_scraper, "date", wraps=date) as fake_date:
            fake_date.today.return_value = date(2026, 10, 2)
            dia = MercadoPagoScraper().parse_html(HTML)[1]
        self.assertEqual(dia["merchant_brands"], ["Supermercados Día"])
        self.assertEqual(dia["valid_from"], "2026-05-11")
        self.assertEqual(dia["valid_until"], "2026-05-13")

    def test_omits_ended_and_undated_campaigns(self):
        self.assertFalse(MercadoPagoScraper._is_current({"valid_until": "2020-01-01"}))
        self.assertFalse(MercadoPagoScraper._is_current({"valid_until": None}))
        self.assertTrue(MercadoPagoScraper._is_current({"valid_until": "2999-01-01"}))


if __name__ == "__main__":
    unittest.main()
