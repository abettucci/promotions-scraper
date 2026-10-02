import asyncio
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from scrapers.cencosud_scraper import CencosudScraper

FIXTURE = Path(__file__).parent / "tests_fixtures" / "cencosud" / "bankDiscount.json"
# 2026-10-02 11:00 ART (viernes), momento en que se capturó el fixture.
NOW = 1790949600


def fixture_items():
    return json.loads(json.loads(FIXTURE.read_text(encoding="utf-8"))["value"])


class CencosudScraperTests(unittest.TestCase):
    def setUp(self):
        self.scraper = CencosudScraper()
        self.promos = self.scraper.parse_items(fixture_items(), now=NOW)
        self.by_title = {p["title"]: p for p in self.promos}

    def find(self, prefix):
        matches = [p for t, p in self.by_title.items() if t.startswith(prefix)]
        self.assertEqual(len(matches), 1, f"{prefix!r}: {list(self.by_title)}")
        return matches[0]

    def test_filters_site_and_validity(self):
        # 13 items en el fixture: 1 vencido y 1 que no es del sitio Jumbo.
        self.assertEqual(len(self.promos), 11)
        titles = [p["title"] for p in self.promos]
        self.assertEqual(len(titles), len(set(titles)))
        for promo in self.promos:
            self.assertTrue(promo["source_id"].startswith("jumbo-"))
            self.assertTrue(promo["terms_raw"])
            self.assertNotIn(promo["discount"], ("", "0%", "00%", "99%"))

    def test_rounds_api_decimals(self):
        turbo = self.find("Naranja X 25% reintegro")
        self.assertEqual(turbo["discount"], "25% reintegro")
        self.assertEqual(turbo["tope"], "$9.500 semanal")
        self.assertEqual(turbo["valid_days"], "Martes")
        cuotas = self.find("Naranja X 12 cuotas")
        self.assertEqual(cuotas["discount"], "12 cuotas sin interés")
        self.assertEqual(cuotas["valid_days"], "Todos los días")

    def test_jubilados_medios_de_pago(self):
        promo = self.find("Jubilados 15%")
        self.assertIsNone(promo["bank"])
        self.assertEqual(promo["payment_method"], "Todos los medios de pago")
        self.assertEqual(promo["discount"], "15%")
        self.assertIn("20% con CencoPay", promo["title"])
        self.assertEqual(promo["store_types"], "Online, Tiendas")
        self.assertEqual(promo["valid_days"], "Miércoles")

    def test_cencopay_variants(self):
        combo = self.find("CencoPay 3, 6 y 12 cuotas")
        self.assertEqual(combo["discount"], "3, 6 y 12 cuotas sin interés")
        online = self.find("CencoPay 20%")
        self.assertEqual(online["store_types"], "Online")
        self.assertIn("3 cuotas sin interés", online["title"])
        galletitas = self.find("CencoPay Cuenta 40%")
        self.assertEqual(galletitas["tope"], "$15.000 diario")
        self.assertEqual(galletitas["valid_days"], "Viernes, Sábado, Domingo")
        self.assertEqual(galletitas["store_types"], "Tiendas")
        cuenta = self.find("CencoPay Cuenta 25%")
        self.assertEqual(cuenta["discount"], "25% reintegro")
        self.assertEqual(cuenta["tope"], "$15.000 mensual")
        dia = self.find("CencoPay Cuenta 30%")
        self.assertEqual(dia["tope"], "$25.000 diario")
        self.assertEqual(dia["valid_from"], "2026-10-02")
        self.assertEqual(dia["valid_until"], "2026-10-02")

    def test_patagonia_visa_and_amex_are_distinct(self):
        visa = self.find("Banco Patagonia 30% Visa")
        amex = self.find("Banco Patagonia 30% American Express")
        self.assertEqual(visa["tope"], "$20.000 mensual")
        self.assertEqual(visa["valid_until"], "2026-10-31")
        self.assertEqual(amex["card_type"], "Crédito")
        self.assertEqual(amex["store_types"], "Tiendas")

    def test_weekend_promos_add_sunday_from_legal(self):
        macro = self.find("Banco Macro 3 cuotas")
        self.assertEqual(macro["valid_days"], "Jueves, Viernes, Sábado, Domingo")
        self.assertEqual(macro["store_types"], "Online")

    def test_scrape_returns_empty_when_api_fails(self):
        with patch.object(CencosudScraper, "_fetch_items", side_effect=RuntimeError("down")):
            self.assertEqual(asyncio.run(self.scraper.scrape()), [])


if __name__ == "__main__":
    unittest.main()
