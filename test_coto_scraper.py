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

    def test_branch_card_uses_published_quota_benefit_and_not_a_generic_label(self):
        promo = self.scraper._parse_multichannel_promotion({
            "id": "267",
            "descripcion": (
                "Exclusivo en sucursales. 3 cuotas sin interés con tarjeta de crédito "
                "Mercado Pago. Pagando con QR."
            ),
            "observacion": (
                "Pagando con QR tarjeta de crédito Mercado Pago en compras a partir de "
                "$150.000. No válido para venta online (Coto Digital)."
            ),
            "textoDescuento": "3 CUOTAS SIN INTERÉS",
            "icono": "logo_mercadopago.png",
        }, is_digital=False)

        self.assertEqual(promo["discount"], "3 cuotas sin interés")
        self.assertIn("3 cuotas sin interés", promo["title"])
        self.assertIn("Sucursal", promo["title"])
        self.assertEqual(promo["store_types"], "Presencial")
        self.assertEqual(promo["min_purchase"], "$150.000")
        self.assertIn("Pago con QR", promo["requirements"])
        self.assertEqual(promo["source_id"], "coto-267")

    def test_benefit_falls_back_to_dynamic_card_text_when_label_is_empty(self):
        promo = self.scraper._parse_multichannel_promotion({
            "id": "dynamic-card",
            "descripcion": "Exclusivo online. 20% de reintegro con Banco Ejemplo",
            "observacion": "Válido pagando con QR.",
            "textoDescuento": "",
            "icono": "logo_mercadopago.png",
        }, is_digital=True)

        self.assertEqual(promo["discount"], "20% reintegro")
        self.assertEqual(promo["store_types"], "Online")


if __name__ == "__main__":
    unittest.main()
