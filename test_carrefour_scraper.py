import asyncio
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from scrapers.carrefour_scraper import CarrefourScraper

FIXTURE = Path(__file__).parent / "tests_fixtures" / "carrefour" / "documents.json"


def document(fields):
    return {
        "fields": [{"key": key, "value": value} for key, value in fields.items()]
    }


def fixture_documents():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["data"]["documents"]


class Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class CarrefourScraperTests(unittest.TestCase):
    def setUp(self):
        self.scraper = CarrefourScraper()
        # Fixture capturado el 2026-10-02: congelar "hoy" para que no venza.
        patcher = patch.object(CarrefourScraper, "_today", staticmethod(lambda: "2026-10-02"))
        patcher.start()
        self.addCleanup(patcher.stop)

    def parse_fixture(self):
        promos = [self.scraper._parse_vtex_document(doc) for doc in fixture_documents()]
        promos = CarrefourScraper._ensure_unique_titles([p for p in promos if p])
        return {p["source_id"][len("carrefour-"):][:8]: p for p in promos}

    def test_fixture_documents_are_all_kept_with_unique_titles(self):
        promos = self.parse_fixture()
        self.assertEqual(len(promos), 12)
        titles = [p["title"] for p in promos.values()]
        self.assertEqual(len(titles), len(set(titles)))
        for promo in promos.values():
            self.assertTrue(promo["source_id"].startswith("carrefour-"))
            self.assertEqual(promo["valid_until"], "2026-10-31")  # active_to exclusivo - 1 día
            self.assertNotIn(promo["discount"], ("", "0%"))

    def test_cuenta_digital_from_image_with_weekly_tope(self):
        promo = self.parse_fixture()["433c8d83"]
        self.assertEqual(promo["bank"], "Carrefour Banco")
        self.assertEqual(promo["payment_method"], "Cuenta Digital Carrefour Banco")
        self.assertEqual(promo["discount"], "20%")
        self.assertEqual(promo["valid_days"], "Jueves")
        self.assertEqual(promo["store_types"], "Online")
        self.assertEqual(promo["valid_from"], "2026-10-01")
        self.assertEqual(promo["tope"], "$10.000 semanal")

    def test_credit_plus_digital_is_not_merged_with_digital_only(self):
        promos = self.parse_fixture()
        both, digital = promos["dc756f22"], promos["433c8d83"]
        self.assertEqual(both["card_type"], "Crédito")
        self.assertNotEqual(both["title"], digital["title"])

    def test_mercado_pago_odd_image_name_and_payment_qualifiers(self):
        promos = self.parse_fixture()
        self.assertEqual(promos["23af46b4"]["wallet"], "Mercado Pago")
        self.assertEqual(promos["23af46b4"]["payment_method"], "Dinero en cuenta Mercado Pago")
        self.assertEqual(promos["23af46b4"]["tope"], "Sin tope")
        qr = promos["03141397"]
        self.assertEqual(qr["discount"], "Hasta 3 cuotas sin interés")
        self.assertEqual(qr["min_purchase"], "$150.000")
        self.assertEqual(qr["valid_days"], "Todos los días")

    def test_patagonia_store_tiers_take_tope_from_subtitle(self):
        promos = self.parse_fixture()
        self.assertEqual(promos["2be11499"]["tope"], "$10.000 mensual")
        self.assertIn("Plan Sueldo", promos["2be11499"]["title"])
        self.assertEqual(promos["ad2d57fe"]["tope"], "$20.000 mensual")
        self.assertIn("Plan Sueldo Singular", promos["ad2d57fe"]["title"])

    def test_cuenta_dni_variants_by_store(self):
        promos = self.parse_fixture()
        tiendas, maxi = promos["35d30d5f"], promos["804da576"]
        self.assertEqual(tiendas["wallet"], "Cuenta DNI")
        self.assertEqual(tiendas["min_purchase"], "$15.000")
        self.assertEqual(tiendas["tope"], "Sin tope")
        self.assertEqual(maxi["store_types"], "Maxi")
        self.assertNotEqual(tiendas["title"], maxi["title"])

    def test_general_and_unidentified_promos_use_all_payment_methods(self):
        promos = self.parse_fixture()
        general = promos["60dcece5"]
        self.assertEqual(general["payment_method"], "Todos los medios de pago")
        self.assertIsNone(general["bank"])
        self.assertEqual(general["tope"], "$8.000 semanal")
        empleados = promos["4f9ac242"]
        self.assertEqual(empleados["payment_method"], "Todos los medios de pago")
        self.assertEqual(empleados["tope"], "$20.000 mensual")

    def test_legal_fallback_dates_with_two_digit_year_and_expiry(self):
        promo = self.scraper._parse_vtex_document(document({
            "id": "x1",
            "title": "10% de descuento con todos los medios de pago",
            "discount_percentage": "10",
            "hyper": "true",
            "monday": "true",
            "legal": "PROMOCIÓN VÁLIDA LOS DÍAS LUNES HASTA EL 31/10/26.",
        }))
        self.assertEqual(promo["valid_until"], "2026-10-31")

        expired = self.scraper._parse_vtex_document(document({
            "title": "20% con Banco ejemplo",
            "discount_percentage": "20",
            "legal": "VÁLIDO TODOS LOS JUEVES DE ENERO 2020.",
        }))
        self.assertIsNone(expired)

    def test_uses_public_persisted_query_with_validity_filter(self):
        calls = []

        def get(*args, **kwargs):
            calls.append(kwargs)
            return Response({"data": {"documents": fixture_documents()[:2]}})

        def post(*args, **kwargs):  # pragma: no cover - no debería usarse
            raise AssertionError("no debería caer al fallback")

        fake_requests = types.SimpleNamespace(get=get, post=post)
        with patch.dict(sys.modules, {"requests": fake_requests}):
            promotions = asyncio.run(self.scraper._scrape_vtex_graphql())

        self.assertEqual(len(promotions), 2)
        self.assertFalse(calls[0]["allow_redirects"])
        self.assertEqual(calls[0]["timeout"], (8, 30))
        extensions = json.loads(calls[0]["params"]["extensions"])
        import base64
        variables = json.loads(base64.b64decode(extensions["variables"]))
        self.assertIn("active=true", variables["where"])
        self.assertEqual(variables["account"], "carrefourar")

    def test_falls_back_to_private_graphql_and_returns_empty_on_failure(self):
        def get(*args, **kwargs):
            raise RuntimeError("down")

        posted = []

        def post(*args, **kwargs):
            posted.append(kwargs)
            return Response({"data": {"documents": fixture_documents()[:1]}})

        with patch.dict(sys.modules, {"requests": types.SimpleNamespace(get=get, post=post)}):
            promotions = asyncio.run(self.scraper._scrape_vtex_graphql())
        self.assertEqual(len(promotions), 1)
        self.assertIn("where", posted[0]["json"]["variables"])

        def broken_post(*args, **kwargs):
            raise RuntimeError("down")

        with patch.dict(sys.modules, {"requests": types.SimpleNamespace(get=get, post=broken_post)}):
            self.assertEqual(asyncio.run(self.scraper._scrape_vtex_graphql()), [])


if __name__ == "__main__":
    unittest.main()
