import json
import unittest
from pathlib import Path

from scrapers.buepp_scraper import BueppScraper, days_from_mask

FIXTURE = json.loads((Path(__file__).parent / "tests_fixtures/buepp/benefits.json").read_text())


class BueppScraperTests(unittest.TestCase):
    def parse(self, key):
        return BueppScraper().parse_benefit(FIXTURE[key]["list"], FIXTURE[key]["detail"])

    def test_coto_monday_credit_online_and_stores(self):
        promo = self.parse("15956")
        self.assertEqual(promo["title"], "Buepp 25% en Coto - Lunes (crédito)")
        self.assertEqual(promo["merchant_brands"], ["Coto Digital"])
        self.assertEqual(promo["tope"], "$30.000 semanal")
        self.assertEqual(promo["store_types"], "Online, Tiendas")
        self.assertEqual((promo["valid_from"], promo["valid_until"]), ("2026-09-07", "2026-12-31"))
        self.assertEqual(promo["bank"], "Banco Ciudad")

    def test_masgo_routes_to_changomas_with_label(self):
        promo = self.parse("15942")
        self.assertEqual(promo["merchant_brands"], ["Más Online (ChangoMás)"])
        self.assertIn("MásGO", promo["title"])
        self.assertEqual(promo["valid_days"], "Domingo")
        self.assertEqual(promo["tope"], "$20.000 mensual")
        self.assertEqual(promo["min_purchase"], "$30.000")
        # La legal manda sobre fechaDesde (27/08, no 20/07).
        self.assertEqual(self.parse("15949")["valid_from"], "2026-08-27")

    def test_day_mask(self):
        self.assertEqual(days_from_mask("L------"), "Lunes")
        self.assertEqual(days_from_mask("----VSD"), "Viernes, Sábado, Domingo")
        self.assertEqual(days_from_mask("LMMJVSD"), "Todos los días")


if __name__ == "__main__":
    unittest.main()
