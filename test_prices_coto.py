import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests

from prices.registry import STORES
from prices.sources import coto

FIXTURE = Path(__file__).parent / "tests_fixtures" / "prices" / "coto_search.json"
STORE = next(s for s in STORES if s.key == "coto")


class CotoPricesTests(unittest.TestCase):
    def setUp(self):
        self.payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.offers = {o.ean: o for o in coto.parse_search(STORE, self.payload)}

    def test_parses_every_record(self):
        self.assertEqual(len(self.offers), 6)
        for offer in self.offers.values():
            self.assertEqual(offer.store, "coto")
            self.assertEqual(offer.merchant, "Coto Digital")
            self.assertTrue(offer.in_stock)
            self.assertTrue(offer.image.startswith("https://static.cotodigital3.com.ar/"))
            self.assertTrue(offer.url.startswith("https://www.coto.com.ar/productos/"))
            self.assertIn("/_/R-", offer.url)

    def test_plain_product(self):
        offer = self.offers["7790742352101"]
        self.assertEqual(offer.title, "Leche La Serenísima Protein 1 Litro")
        self.assertEqual(offer.brand, "LA SERENISIMA")
        self.assertEqual(offer.price, 2378.0)
        self.assertIsNone(offer.list_price)
        self.assertEqual(
            offer.url,
            "https://www.coto.com.ar/productos/leche-la-seren%C3%ADsima-protein-1-litro"
            "/_/R-00633499-00633499-200",
        )

    def test_direct_discount_applies(self):
        offer = self.offers["7790742333605"]          # "25%Dto"
        self.assertEqual(offer.price, 2338.5)
        self.assertEqual(offer.list_price, 3118.0)
        self.assertEqual(offer.percentage_off, 25)

    def test_label_without_discount_keeps_price(self):
        offer = self.offers["7790742448101"]          # "Precio Contado" sin textoDescuento
        self.assertEqual(offer.price, 2050.0)
        self.assertIsNone(offer.list_price)

    def test_multibuy_and_conditional_promos_ignored(self):
        self.assertEqual(self.offers["7798383430011"].price, 1802.0)      # 2x1
        self.assertIsNone(self.offers["7798383430011"].list_price)
        self.assertEqual(self.offers["8806094365580"].price, 1049999.0)   # "1 Pago 20%"
        self.assertIsNone(self.offers["8806094365580"].list_price)

    def test_installments(self):
        self.assertEqual(self.offers["7790070012050"].installments, 3)
        self.assertEqual(self.offers["8806094365580"].installments, 12)
        self.assertEqual(self.offers["7790742352101"].installments, 0)
        self.assertEqual(self.offers["7790070012050"].title, "Aceite Girasol COCINERO Botella 900 Ml")

    def test_search_uses_endpoint_and_limit(self):
        response = MagicMock(status_code=200)
        response.json.return_value = self.payload
        with patch("prices.sources.coto.requests.get", return_value=response) as get:
            offers = coto.search(STORE, "leche", limit=2)
        self.assertEqual(len(offers), 2)
        url = get.call_args.args[0]
        params = get.call_args.kwargs["params"]
        self.assertEqual(url, "https://www.coto.com.ar/sitios/cdigi/categoria")
        self.assertEqual(params, {"Ntt": "leche", "Nrpp": 2, "format": "json"})
        self.assertIn("Mozilla", get.call_args.kwargs["headers"]["User-Agent"])

    def test_search_never_raises(self):
        with patch("prices.sources.coto.requests.get", side_effect=requests.Timeout()):
            self.assertEqual(coto.search(STORE, "leche"), [])
        bad = MagicMock(status_code=403)
        with patch("prices.sources.coto.requests.get", return_value=bad):
            self.assertEqual(coto.search(STORE, "leche"), [])
        broken = MagicMock(status_code=200)
        broken.json.side_effect = ValueError("not json")
        with patch("prices.sources.coto.requests.get", return_value=broken):
            self.assertEqual(coto.search(STORE, "leche"), [])
        self.assertEqual(coto.parse_search(STORE, {"contents": []}), [])


if __name__ == "__main__":
    unittest.main()
