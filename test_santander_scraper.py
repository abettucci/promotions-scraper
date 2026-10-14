import unittest

from scrapers.santander_scraper import SantanderScraper


CARREFOUR = {"id": 86, "name": "Carrefour", "desktopMinImage": "https://image.example/carrefour.png"}
CABIFY = {"id": 58, "name": "Cabify"}


class SantanderScraperTests(unittest.TestCase):
    def setUp(self):
        self.scraper = SantanderScraper()

    def test_carrefour_routes_to_supermarket_with_terms(self):
        promos = self.scraper.parse_item({
            "idPromotion": 123, "monday": True, "topAmount": 15000,
            "startDatePublication": "2026-10-01T00:00:00",
            "endDatePublication": "2026-10-31T00:00:00",
            "customerDiscount": 25, "benefitType": {"code": "A"},
            "texts": {"discount": 25}, "paymentType": {"code": "M"},
            "tag": {"description": "Sorpresa"}, "categories": [{"code": "SOR"}],
            "additionalText": "Pagando con QR desde la App Santander.",
            "legal": "Válido en Carrefour. No acumulable con otras promociones.",
        }, CARREFOUR)
        self.assertEqual(len(promos), 1)
        promo = promos[0]
        self.assertEqual(promo["merchant_brands"], ["Carrefour"])
        self.assertEqual(promo["merchant_category"], "supermarket")
        self.assertEqual(promo["wallet"], "MODO")
        self.assertEqual(promo["tope"], "$15.000")
        self.assertIn("Sorpresa", promo["requirements"][0])
        self.assertIn("No acumulable", promo["terms_raw"])
        self.assertTrue(promo["url"].endswith("brandId=86"))

    def test_cabify_routes_to_mobility_and_keeps_installments(self):
        promos = self.scraper.parse_item({
            "id": 77, "fullWeek": True, "customerDiscount": 20,
            "benefitType": {"code": "D"}, "texts": {"discount": 20, "fees": 3},
            "interestFreeFees": True, "finalQuote": 3,
            "paymentType": {"code": "N"}, "categories": [],
            "legal": "Válido para viajes realizados con Cabify y tarjeta de crédito Santander.",
        }, CABIFY)
        self.assertEqual(len(promos), 2)
        self.assertEqual({promo["mobility_kind"] for promo in promos}, {"ride_hailing"})
        self.assertEqual({promo["merchant_category"] for promo in promos}, {"mobility"})
        self.assertEqual({promo["store_types"] for promo in promos}, {"App"})
        self.assertIn("20% de descuento", promos[0]["title"])
        self.assertIn("3 cuotas sin interés", promos[1]["title"])


if __name__ == "__main__":
    unittest.main()
