import os
import tempfile
import unittest
from unittest.mock import patch

import config
from database import Database, UserDatabase
from payment_preferences import promotion_matches_payment_methods


class PaymentPreferencesTests(unittest.TestCase):
    def test_credit_only_profile_excludes_debit_only_promotion(self):
        promotion = {"bank": "Banco Uno", "card_type": "Tarjeta de débito", "title": "20%"}
        self.assertFalse(promotion_matches_payment_methods(promotion, [{"name": "Banco Uno", "card_mode": "credit"}]))

    def test_unknown_card_type_remains_available_to_avoid_false_negative(self):
        promotion = {"bank": "Banco Uno", "title": "20%", "payment_method": "QR"}
        self.assertTrue(promotion_matches_payment_methods(promotion, [{"name": "Banco Uno", "card_mode": "debit"}]))

    def test_explicit_brubank_ultra_promo_requires_ultra_in_profile(self):
        promotion = {"bank": "Brubank", "title": "Brubank 20% en Axion (Plan Ultra)", "requirements": ["Clientes suscriptos a Plan Ultra"]}
        self.assertFalse(promotion_matches_payment_methods(promotion, [{"name": "Brubank", "card_mode": "both", "tiers": []}]))
        self.assertTrue(promotion_matches_payment_methods(promotion, [{"name": "Brubank", "card_mode": "both", "tiers": ["ultra"]}]))

    def test_general_promotion_remains_visible_without_tier(self):
        promotion = {"bank": "Brubank", "title": "Brubank 10% en Coto", "requirements": ["Pago con tarjeta Brubank"]}
        self.assertTrue(promotion_matches_payment_methods(promotion, [{"name": "Brubank", "card_mode": "both", "tiers": []}]))

    def test_payment_preferences_are_persisted_and_old_default_is_both(self):
        with tempfile.TemporaryDirectory() as directory:
            db = UserDatabase(os.path.join(directory, "users.db"))
            user_id = db.create_user("test@example.com", "hash")
            db.set_user_payment_methods(user_id, [
                {"name": "Banco Uno", "type": "bank", "card_mode": "debit"},
                {"name": "MODO", "type": "wallet", "tiers": []},
            ])
            self.assertEqual(db.get_user_payment_methods(user_id), [
                {"name": "Banco Uno", "type": "bank", "card_mode": "debit", "tiers": []},
                {"name": "MODO", "type": "wallet", "card_mode": "both", "tiers": []},
            ])

    def test_personalized_promotions_respect_explicit_card_type(self):
        with tempfile.TemporaryDirectory() as directory:
            promotions_path = os.path.join(directory, "promotions.db")
            promotions_db = Database(promotions_path)
            supermarket_id = promotions_db.insert_supermarket("Comercio", "https://example.com")
            promotions_db.insert_promotion(supermarket_id, {
                "title": "20% crédito", "bank": "Banco Uno", "card_type": "Tarjeta de crédito",
            })
            promotions_db.insert_promotion(supermarket_id, {
                "title": "15% débito", "bank": "Banco Uno", "card_type": "Tarjeta de débito",
            })
            users_db = UserDatabase(os.path.join(directory, "users.db"))
            user_id = users_db.create_user("test@example.com", "hash")
            users_db.set_user_payment_methods(user_id, [
                {"name": "Banco Uno", "type": "bank", "card_mode": "debit"},
            ])
            with patch.object(config, "DATABASE_PATH", promotions_path):
                promotions = users_db.get_promotions_for_user(user_id, today_only=False)
            self.assertEqual([promo["title"] for promo in promotions], ["15% débito"])


if __name__ == "__main__":
    unittest.main()
