import os
import tempfile
import unittest
from datetime import datetime, timedelta

from database import Database
from scrape_result_cache import ScrapeResultCache, promotions_fingerprint


PROMOTIONS = [
    {"title": "30%", "bank": "Banco Uno", "terms_raw": "Válido sábado", "exclusions": ["Vinos"]},
    {"title": "20%", "wallet": "MODO", "terms_raw": "Válido domingo"},
]


class ScrapeResultCacheTests(unittest.TestCase):
    def test_fingerprint_is_independent_of_card_order(self):
        self.assertEqual(promotions_fingerprint(PROMOTIONS), promotions_fingerprint(list(reversed(PROMOTIONS))))

    def test_cache_remembers_only_an_identical_result(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = ScrapeResultCache(os.path.join(directory, "results.json"))
            self.assertFalse(cache.unchanged("coto", PROMOTIONS))
            cache.remember("coto", PROMOTIONS)
            self.assertTrue(cache.unchanged("coto", list(reversed(PROMOTIONS))))
            changed = [dict(PROMOTIONS[0], title="35%"), PROMOTIONS[1]]
            self.assertFalse(cache.unchanged("coto", changed))

    def test_verified_source_is_not_expired_by_stale_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Database(os.path.join(directory, "promotions.db"))
            verified_id = db.insert_supermarket("Verificado", "https://example.com")
            stale_id = db.insert_supermarket("No verificado", "https://example.org")
            for supermarket_id, title in ((verified_id, "Verificada"), (stale_id, "Vencida")):
                db.insert_promotion(supermarket_id, {"title": title, "bank": "Banco", "terms_raw": ""})

            old_date = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
            with db.get_connection() as connection:
                connection.execute("UPDATE promotions SET scraped_at = ?", (old_date,))
                connection.commit()

            self.assertEqual(db.deactivate_stale_promotions(2, {verified_id}), 1)
            promotions = db.get_active_promotions()
            self.assertEqual([promo["supermarket_name"] for promo in promotions], ["Verificado"])

    def test_get_supermarket_id_does_not_create_an_unknown_merchant(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Database(os.path.join(directory, "promotions.db"))
            supermarket_id = db.insert_supermarket("Existente", "https://example.com")
            self.assertEqual(db.get_supermarket_id("Existente"), supermarket_id)
            self.assertIsNone(db.get_supermarket_id("No existe"))

if __name__ == "__main__":
    unittest.main()
