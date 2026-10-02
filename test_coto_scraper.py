import asyncio
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from scrapers.coto_scraper import CotoScraper

FIXTURE = Path(__file__).parent / "tests_fixtures" / "coto" / "multicanal.json"


class CotoScraperTests(unittest.TestCase):
    def setUp(self):
        self.scraper = CotoScraper()

    def _by_id(self):
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        return {p["source_id"]: p for p in self.scraper._parse_payload(payload)}

    def test_fixture_parses_every_published_card(self):
        promos = self._by_id()
        self.assertEqual(len(promos), 13)
        titles = [p["title"] for p in promos.values()]
        self.assertEqual(len(titles), len(set(titles)))
        for promo in promos.values():
            self.assertIn(promo["store_types"], ("Online", "Tiendas"))
            self.assertTrue(promo["discount"])
            self.assertNotIn(promo["tope"], ("$.", "$,", "$"))

    def test_tope_variants(self):
        promos = self._by_id()
        self.assertEqual(promos["coto-356"]["tope"], "$20.000")            # "Tope de Reintegro de $20.000"
        self.assertEqual(promos["coto-344"]["tope"], "$30.000")            # "Tope $30.000."
        self.assertEqual(promos["coto-382"]["tope"], "$12.000 semanal")
        self.assertEqual(promos["coto-370"]["tope"], "Sin tope")           # "Sin límite de reintegro"
        self.assertEqual(promos["coto-363"]["tope"], "Sin tope")
        self.assertEqual(promos["coto-343"]["tope"], "$30.000 por transacción")
        self.assertTrue(promos["coto-368"]["tope"].startswith("$15.000 por transacción"))

    def test_icon_wins_over_copied_description(self):
        promos = self._by_id()
        # Icono Columbia, texto "app de Comafi" → Columbia + MODO.
        self.assertEqual(promos["coto-363"]["bank"], "Banco Columbia")
        self.assertEqual(promos["coto-363"]["wallet"], "MODO")
        self.assertEqual(promos["coto-343"]["bank"], "Banco Ciudad")
        self.assertEqual(promos["coto-343"]["wallet"], "MODO")
        # Ciudadanía Porteña no es Banco Ciudad.
        self.assertIsNone(promos["coto-394"]["bank"])
        self.assertIn("Ciudadanía Porteña", promos["coto-394"]["title"])
        self.assertEqual(promos["coto-394"]["valid_days"], "Martes, Jueves")

    def test_debit_cards_without_bank_are_kept(self):
        promos = self._by_id()
        for sid in ("coto-390", "coto-293"):
            self.assertIsNone(promos[sid]["bank"])
            self.assertEqual(promos[sid]["payment_method"], "Débito")
            self.assertEqual(promos[sid]["card_type"], "Débito")
            self.assertEqual(promos[sid]["discount"], "15% descuento")
        self.assertEqual(promos["coto-390"]["valid_days"], "Viernes")
        self.assertIsNone(promos["coto-293"]["valid_days"])

    def test_validity_comes_from_observation(self):
        promo = self._by_id()["coto-425"]
        self.assertEqual((promo["valid_from"], promo["valid_until"]), ("2026-10-01", "2026-10-31"))
        self.assertEqual(promo["discount"], "Hasta 18 cuotas sin interés")
        self.assertEqual(promo["valid_days"], "Viernes, Sábado, Domingo")
        self.assertEqual(promo["card_type"], "Crédito")

    def test_naranja_plans_and_channels(self):
        promos = self._by_id()
        self.assertEqual(promos["coto-382"]["title"], "Naranja X 30% descuento (Plan Épico) - Martes - Online")
        self.assertEqual(promos["coto-382"]["card_type"], "Crédito, Débito")
        self.assertEqual(promos["coto-386"]["min_purchase"], "$50.000")
        self.assertEqual(promos["coto-386"]["wallet"], "Mercado Pago")
        self.assertEqual(promos["coto-386"]["store_types"], "Tiendas")

    def test_primary_source_uses_browser_user_agent_and_follows_coto_redirect(self):
        calls = []
        payload = {"result": {"promocionesDigitales": [], "promocionesSucursalesFisicas": [{
            "id": "1",
            "descripcion": "Tarjetas de débito y crédito Cabal Credicoop con MODO",
            "observacion": "Aplican exclusiones. Ver legal.",
            "textoDescuento": "30% DE DESCUENTO",
            "diasVigencia": "Lunes",
            "icono": "logo_credicoop.png",
        }]}}

        class Response:
            def __init__(self, location=None):
                self.is_redirect = bool(location)
                self.headers = {"Location": location} if location else {}

            def raise_for_status(self):
                return None

            def json(self):
                return payload

        def get(url, **kwargs):
            calls.append((url, kwargs))
            if "cotodigital" in url:
                return Response(url.replace("www.cotodigital.com.ar", "www.coto.com.ar"))
            return Response()

        with patch.dict(sys.modules, {"requests": types.SimpleNamespace(get=get)}):
            fetched = asyncio.run(self.scraper._fetch_multichannel_payload())

        self.assertEqual(fetched, payload)
        self.assertIn("Mozilla", calls[0][1]["headers"]["User-Agent"])
        self.assertFalse(calls[0][1]["allow_redirects"])
        promos = self.scraper._parse_payload(fetched)
        self.assertEqual(promos[0]["store_types"], "Tiendas")
        self.assertEqual(promos[0]["wallet"], "MODO")

    def test_failure_returns_empty_without_html_fallback(self):
        def get(url, **kwargs):
            raise OSError("boom")

        with patch.dict(sys.modules, {"requests": types.SimpleNamespace(get=get)}), \
                patch.object(CotoScraper, "_fetch_payload_with_browser", return_value=None):
            self.assertEqual(asyncio.run(self.scraper.scrape()), [])

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
