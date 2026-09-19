import unittest

from scrapers.mercadopago_scraper import MercadoPagoScraper


HTML = """
<div class="kiyo__data--modal">
  <div class="kiyo__data--details-logo"><img src="https://cdn.example/farmacity.jpg"><h3>Farmacity</h3></div>
  <div class="kiyo__cards--badge"><span>20% OFF</span></div>
  <div class="kiyo__cards--badge kiyo__cards--badge2"><span>3 cuotas sin interés</span></div>
  <div class="kiyo__data--details-row1"><p>20% OFF con Tarjeta de Mercado Pago en la tienda online.</p></div>
  <div class="kiyo__data--details-btn"><a href="https://promociones.mercadopago.com.ar/seller/farmacity/">Ir</a></div>
  <div class="kiyo__data--details-row2"><small>Válido del 11 al 17 de mayo de 2026. Tope de reintegro $30.000. Compras desde $70.000.</small></div>
</div>
"""


class MercadoPagoScraperTests(unittest.TestCase):
    def test_parses_public_promotion_card(self):
        promotions = MercadoPagoScraper().parse_html(HTML)

        self.assertEqual(len(promotions), 1)
        promo = promotions[0]
        self.assertEqual(promo["title"], "Farmacity")
        self.assertEqual(promo["wallet"], "Mercado Pago")
        self.assertEqual(promo["discount"], "20% OFF")
        self.assertEqual(promo["valid_from"], "2026-05-11")
        self.assertEqual(promo["valid_until"], "2026-05-17")
        self.assertEqual(promo["tope"], "$30.000")
        self.assertEqual(promo["min_purchase"], "$70.000")
        self.assertIn("Tarjeta de Mercado Pago", promo["terms_raw"])

    def test_omits_campaigns_that_have_already_ended(self):
        self.assertFalse(MercadoPagoScraper._is_current_or_undated({"valid_until": "2020-01-01"}))
        self.assertTrue(MercadoPagoScraper._is_current_or_undated({"valid_until": None}))


if __name__ == "__main__":
    unittest.main()
