import json
import unittest
from pathlib import Path

from scrapers.personalpay_scraper import PersonalPayScraper, days_label

FIXTURE = json.loads((Path(__file__).parent / "tests_fixtures/personalpay/benefits.json").read_text())


class PersonalPayScraperTests(unittest.TestCase):
    def parse(self, key, category="supermarket"):
        return PersonalPayScraper().parse_benefit(FIXTURE[key]["item"], FIXTURE[key]["detail"], category)

    def test_la_reina_tope_and_min_purchase(self):
        promo = self.parse("9212")
        self.assertEqual(promo["title"], "Personal Pay 10% en La Reina - Sábado")
        self.assertEqual(promo["discount"], "10% reintegro")
        self.assertEqual(promo["tope"], "$7.000 semanal")
        self.assertEqual(promo["min_purchase"], "$30.000")
        self.assertEqual(promo["valid_until"], "2026-10-31")

    def test_coto_uses_legal_end_date_and_stores_only(self):
        promo = self.parse("9403")
        self.assertEqual(promo["merchant_brands"], ["Coto Digital"])
        self.assertEqual(promo["valid_until"], "2026-10-01")
        self.assertEqual(promo["store_types"], "Tiendas")

    def test_changomas_days_and_fuel(self):
        chango = self.parse("9416")
        self.assertEqual(chango["merchant_brands"], ["Más Online (ChangoMás)"])
        self.assertEqual(chango["valid_days"], "Viernes, Sábado, Domingo")
        self.assertEqual(chango["tope"], "Sin tope")
        wico = self.parse("9121", "fuel")
        self.assertEqual(wico["merchant_category"], "fuel")
        self.assertEqual(wico["discount"], "5%")

    def test_days_label(self):
        self.assertEqual(days_label(["Do", "Vi", "Sá"]), "Viernes, Sábado, Domingo")
        self.assertEqual(days_label(["Todos los días"]), "Todos los días")


if __name__ == "__main__":
    unittest.main()
