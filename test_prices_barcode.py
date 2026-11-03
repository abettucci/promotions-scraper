import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from prices.barcodes import valid_gtin
from prices.history import PriceHistory
from prices.registry import STORES
from prices.sources import vtex


class BarcodeTests(unittest.TestCase):
    def test_gtin_checksum(self):
        self.assertTrue(valid_gtin("7790895007217"))
        self.assertFalse(valid_gtin("7790895007218"))
        self.assertFalse(valid_gtin("00000000"))

    def test_vtex_exact_ean_lookup_filters_items(self):
        product = {"productName": "Gaseosa", "items": [
            {"ean": "7790895007217", "sellers": [{"sellerDefault": True, "commertialOffer": {"Price": 5, "IsAvailable": True}}]},
            {"ean": "7790000000000", "sellers": [{"sellerDefault": True, "commertialOffer": {"Price": 1, "IsAvailable": True}}]},
        ]}
        class Response:
            status_code = 200
            def json(self): return product
        with patch.object(vtex.requests, "get", return_value=Response()) as request:
            offers = vtex.search_ean(STORES[0], "7790895007217")
        self.assertEqual([offer.ean for offer in offers], ["7790895007217"])
        self.assertEqual(request.call_args.kwargs["params"]["field"], "ean")

    def test_history_returns_price_series_per_store(self):
        with tempfile.TemporaryDirectory() as directory:
            history = PriceHistory(Path(directory) / "prices.db")
            group = {"key": "ean:7790895007217", "name": "Producto", "brand": "", "ean": "7790895007217",
                     "offers": [{"store": "dia", "store_name": "Día", "price": 100, "url": "https://dia.example/product", "in_stock": True}]}
            history.record_groups([group], query="7790895007217")
            result = history.series(group["key"], days=7)
            self.assertEqual(result["series"][0]["store"], "dia")
            self.assertEqual(result["series"][0]["points"][-1]["price"], 100)


if __name__ == "__main__":
    unittest.main()
