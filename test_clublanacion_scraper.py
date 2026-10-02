import json
import unittest
from pathlib import Path

from scrapers.clublanacion_scraper import ClubLaNacionScraper, parse_tope

FIXTURE = json.loads((Path(__file__).parent / "tests_fixtures/clublanacion/accounts.json").read_text())


class ClubLaNacionScraperTests(unittest.TestCase):
    def setUp(self):
        self.scraper = ClubLaNacionScraper()
        self.accounts = {a["crmid"]: a for a in FIXTURE["accounts"]}

    def test_only_supermarkets_and_allowlisted_shops(self):
        selected = self.scraper.select_accounts(FIXTURE["accounts"][:3], "supermarket")
        self.assertEqual([a["name"] for a in selected], ["CARREFOUR", "EN COMBO"])

    def test_carrefour_benefits(self):
        promos = [self.scraper.parse_benefit(self.accounts["A38832"], b, "supermarket")
                  for b in FIXTURE["benefits"]["A38832"]["data"]]
        titles = sorted(p["title"] for p in promos)
        self.assertEqual(titles, [
            "Club La Nación 10% en Carrefour - Martes a Domingo (Entrega Inmediata online)",
            "Club La Nación 15% en Carrefour - Lunes (online con cupón)",
            "Club La Nación 15% en Carrefour - Lunes (tiendas físicas)",
        ])
        stores = next(p for p in promos if "tiendas físicas" in p["title"])
        self.assertEqual(stores["store_types"], "Tiendas")
        self.assertEqual(stores["valid_until"], "2027-06-30")
        self.assertEqual(stores["tope"], "Sin tope")
        self.assertIsNone(stores["bank"])
        self.assertEqual(stores["wallet"], "Club La Nación")

    def test_ypf_fuel(self):
        promos = {p["title"]: p for p in (self.scraper.parse_benefit(self.accounts["A10677"], b, "fuel")
                                          for b in FIXTURE["benefits"]["A10677"]["data"])}
        infinia = promos["Club La Nación 10% en YPF - Lunes, Sábado, Domingo (Infinia con App YPF)"]
        self.assertEqual(infinia["tope"], "$3.000 semanal")
        self.assertEqual(infinia["merchant_category"], "fuel")
        full = promos["Club La Nación 15% en YPF - Todos los días (Tiendas Full)"]
        self.assertEqual(full["tope"], "$2.000 mensual")

    def test_parse_tope(self):
        self.assertEqual(parse_tope("Tope de descuento de $25.000/semana."), "$25.000 semanal")
        self.assertEqual(parse_tope("Tope de descuento de $10.000. Aplica mínimo"), "$10.000")


if __name__ == "__main__":
    unittest.main()
