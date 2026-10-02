import json
import unittest
from pathlib import Path

from scrapers.cuentadni_scraper import CuentaDniScraper, normalize_days, parse_dotnet_date

FIXTURE = json.loads((Path(__file__).parent / "tests_fixtures/cuentadni/details.json").read_text())


class CuentaDniScraperTests(unittest.TestCase):
    def setUp(self):
        self.scraper = CuentaDniScraper()

    def test_dia_splits_nfc_and_account_tiers(self):
        promos = self.scraper.parse_detail(FIXTURE["1076"])
        self.assertEqual([p["discount"] for p in promos], ["20% reintegro", "10% reintegro"])
        nfc, account = promos
        self.assertEqual(nfc["merchant_brands"], ["Supermercados Día"])
        self.assertEqual(nfc["merchant_category"], "supermarket")
        self.assertEqual(nfc["card_type"], "Crédito")
        self.assertEqual(nfc["tope"], "Sin tope")
        self.assertIn("Supermercados Día", nfc["title"])
        self.assertNotEqual(nfc["title"], account["title"])
        # fecha_hasta es exclusiva (1/1 ART) y el legal dice 1/10–31/12.
        self.assertEqual((nfc["valid_from"], nfc["valid_until"]), ("2026-10-01", "2026-12-31"))
        self.assertEqual(nfc["valid_days"], "Lunes")

    def test_tope_comes_from_legal_not_marketing_bajada(self):
        nini = self.scraper.parse_detail(FIXTURE["1077"])[0]
        self.assertEqual(nini["title"], "Cuenta DNI 15% en Mayorista Nini - Martes")
        self.assertEqual(nini["tope"], "$20.000 por día")
        self.assertEqual(nini["valid_until"], "2026-10-31")

    def test_generic_network_min_purchase_and_days(self):
        promo = self.scraper.parse_detail(FIXTURE["1052"])[0]
        self.assertEqual(promo["merchant_brands"], ["Supermercados de cercanía"])
        self.assertEqual(promo["valid_days"], "Martes, Miércoles")
        self.assertEqual(promo["tope"], "$6.000 semanal")
        self.assertEqual(promo["min_purchase"], "$30.000")

    def test_carrefour_and_ypf_full(self):
        carrefour = self.scraper.parse_detail(FIXTURE["1072"])[0]
        self.assertEqual((carrefour["tope"], carrefour["min_purchase"]), ("Sin tope", "$15.000"))
        ypf = self.scraper.parse_detail(FIXTURE["1065"])[0]
        self.assertEqual(ypf["merchant_brands"], ["YPF"])
        self.assertEqual(ypf["merchant_category"], "fuel")
        self.assertIn("Tiendas Full", ypf["title"])
        self.assertEqual(ypf["tope"], "$8.000 semanal")

    def test_other_rubros_are_dropped(self):
        self.assertEqual(self.scraper.parse_detail(FIXTURE["1046"]), [])

    def test_helpers(self):
        self.assertEqual(normalize_days("Lunes a viernes"), "Lunes, Martes, Miércoles, Jueves, Viernes")
        self.assertEqual(normalize_days("Todos los días"), "Todos los días")
        self.assertEqual(parse_dotnet_date("/Date(1793502000000)/", shift_days=-1), "2026-10-31")


if __name__ == "__main__":
    unittest.main()
