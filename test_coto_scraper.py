import asyncio
import sys
import types
import unittest
from unittest.mock import patch

from scrapers.coto_scraper import CotoScraper


class CotoScraperTests(unittest.TestCase):
    def setUp(self):
        self.scraper = CotoScraper()

    def test_digital_promotion_keeps_online_requirement_and_exclusions(self):
        promo = self.scraper._parse_multichannel_promotion({
            "descripcion": "Banco Credicoop 30% fin de semana exclusivo compras online con tarjetas de crédito y débito",
            "observacion": "Tope de reintegro $15.000. Aplican exclusiones. Ver legal.",
            "textoDescuento": "30% DE DESCUENTO",
            "diasVigencia": "Sábado y Domingo",
            "icono": "logo_credicoop.png",
        }, is_digital=True)

        self.assertIsNotNone(promo)
        self.assertEqual(promo["bank"], "Banco Credicoop")
        self.assertEqual(promo["store_types"], "Online")
        self.assertIn("compras online", promo["requirements"])
        self.assertIn("Aplican exclusiones", promo["exclusions"])
        self.assertIn("Ver legal", promo["terms_raw"])

    def test_primary_source_keeps_physical_promotions_as_presencial(self):
        calls = []

        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {"result": {"promocionesDigitales": [], "promocionesSucursalesFisicas": [{
                    "descripcion": "Tarjetas de débito y crédito Cabal Credicoop con MODO",
                    "observacion": "Aplican exclusiones. Ver legal.",
                    "textoDescuento": "30% DE DESCUENTO",
                    "diasVigencia": "Lunes",
                    "icono": "logo_credicoop.png",
                }]}}

        def get(*args, **kwargs):
            calls.append((args, kwargs))
            return Response()

        with patch.dict(sys.modules, {"requests": types.SimpleNamespace(get=get)}):
            promotions = asyncio.run(self.scraper._scrape_multichannel_promotions())

        self.assertEqual(len(promotions), 1)
        self.assertEqual(promotions[0]["store_types"], "Presencial")
        self.assertFalse(calls[0][1]["allow_redirects"])
        self.assertEqual(calls[0][1]["timeout"], (8, 30))


if __name__ == "__main__":
    unittest.main()
