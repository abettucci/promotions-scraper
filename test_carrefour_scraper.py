import asyncio
import sys
import types
import unittest
from unittest.mock import patch

from scrapers.carrefour_scraper import CarrefourScraper


def document(fields):
    return {
        "fields": [{"key": key, "value": value} for key, value in fields.items()]
    }


class CarrefourScraperTests(unittest.TestCase):
    def setUp(self):
        self.scraper = CarrefourScraper()

    def test_parses_current_vtex_document_with_full_legal(self):
        promo = self.scraper._parse_vtex_document(document({
            "title": "20% de descuento en un pago con Cuenta Digital de Carrefour Banco",
            "sub_title": "Tope de devolución $10.000",
            "discount_percentage": "20",
            "img_card": "Cuenta-Digital.webp",
            "ecommerce": "true",
            "thursday": "true",
            "legal": (
                "DESCUENTO EXCLUSIVO ABONANDO CON CUENTA DIGITAL DE CARREFOUR BANCO. "
                "VÁLIDO TODOS LOS JUEVES DE SEPTIEMBRE 2026 PARA LAS COMPRAS ONLINE "
                "EN CARREFOUR.COM.AR. QUEDAN EXCLUIDOS DEL DESCUENTO BODEGAS RUTINI Y CHANDON."
            ),
        }))

        self.assertIsNotNone(promo)
        self.assertEqual(promo["bank"], "Carrefour Banco")
        self.assertEqual(promo["card_type"], "Cuenta Digital Carrefour")
        self.assertEqual(promo["discount"], "20%")
        self.assertEqual(promo["valid_days"], "Jueves")
        self.assertEqual(promo["store_types"], "Online")
        self.assertEqual(promo["valid_from"], "2026-09-01")
        self.assertEqual(promo["valid_until"], "2026-09-30")
        self.assertIn("BODEGAS RUTINI", promo["terms_raw"])

    def test_keeps_general_payment_method_promotions(self):
        promo = self.scraper._parse_vtex_document(document({
            "title": "10% de descuento con todos los medios de pago",
            "discount_percentage": "10",
            "hyper": "true",
            "monday": "true",
            "legal": "VÁLIDO TODOS LOS LUNES DE SEPTIEMBRE 2026.",
        }))

        self.assertIsNotNone(promo)
        self.assertEqual(promo["payment_method"], "Todos los medios de pago")
        self.assertEqual(promo["bank"], None)

    def test_skips_an_expired_document(self):
        promo = self.scraper._parse_vtex_document(document({
            "title": "20% con Banco ejemplo",
            "discount_percentage": "20",
            "legal": "VÁLIDO TODOS LOS JUEVES DE ENERO 2020.",
        }))

        self.assertIsNone(promo)

    def test_uses_vtex_source_as_primary_and_does_not_follow_redirects(self):
        calls = []

        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {"data": {"documents": [document({
                    "title": "20% con Cuenta DNI",
                    "discount_percentage": "20",
                    "monday": "true",
                    "legal": "VÁLIDO TODOS LOS LUNES DE SEPTIEMBRE 2026.",
                })]}}

        def post(*args, **kwargs):
            calls.append((args, kwargs))
            return Response()

        fake_requests = types.SimpleNamespace(post=post)
        with patch.dict(sys.modules, {"requests": fake_requests}):
            promotions = asyncio.run(self.scraper._scrape_vtex_graphql())

        self.assertEqual(len(promotions), 1)
        self.assertEqual(promotions[0]["wallet"], "Cuenta DNI")
        self.assertEqual(promotions[0]["bank"], "Banco Provincia")
        self.assertFalse(calls[0][1]["allow_redirects"])
        self.assertEqual(calls[0][1]["timeout"], (8, 30))


if __name__ == "__main__":
    unittest.main()
