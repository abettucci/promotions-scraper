import unittest

from promo_questions import answer_promo_question, is_allowed_promo_question


PROMOTIONS = [
    {
        "supermarket_name": "Coto Digital", "category": "supermarket",
        "title": "30% todos los productos", "discount": "30%", "bank": "Banco Uno",
        "valid_days": "Sábado", "exclusions": "Quedan excluidos vinos Alaris y bebidas alcohólicas",
        "terms_raw": "Válido hoy", "tope": "$10.000",
    },
    {
        "supermarket_name": "Carrefour", "category": "supermarket",
        "title": "25% en bebidas", "discount": "25%", "wallet": "MODO",
        "valid_days": "Sábado", "exclusions": "", "terms_raw": "Aplica en vinos", "tope": "$5.000",
    },
    {
        "supermarket_name": "Shell", "category": "fuel",
        "title": "20% en combustibles", "discount": "20%", "bank": "Banco Galicia",
        "valid_days": "Sábado", "exclusions": "", "terms_raw": "", "tope": "$3.000",
    },
]


class PromoQuestionsTests(unittest.TestCase):
    def test_confirms_explicit_exclusion(self):
        answer = answer_promo_question(
            "El vino Alaris está excluido de la promoción de Coto hoy?", PROMOTIONS,
        )
        self.assertIn("Sí", answer)
        self.assertIn("Alaris", answer)

    def test_does_not_treat_a_generic_wine_exclusion_as_a_brand_exclusion(self):
        promotions = [{
            "supermarket_name": "Coto Digital", "category": "supermarket",
            "title": "30% todos los productos", "discount": "30%", "bank": "Banco Uno",
            "valid_days": "Sábado", "tope": "$10.000",
            "exclusions": "No incluye vinos en tetrabrik ni bebidas alcohólicas",
            "terms_raw": "Válido hoy",
        }]
        answer = answer_promo_question(
            "¿El vino Alaris está excluido en Coto hoy?", promotions,
        )
        self.assertIn("no figura mencionado", answer)
        self.assertNotIn("figura excluido", answer)
        self.assertIn("vinos en tetrabrik", answer)

    def test_confirms_category_for_a_generic_product_question(self):
        answer = answer_promo_question(
            "¿El vino está excluido en Coto hoy?", PROMOTIONS,
        )
        self.assertIn("Sí", answer)
        self.assertIn("vinos Alaris", answer)

    def test_recommendation_respects_linked_payment_methods(self):
        answer = answer_promo_question(
            "En qué súper me conviene comprar vino hoy?", PROMOTIONS, [{"name": "MODO"}],
        )
        self.assertIn("Carrefour", answer)
        self.assertNotIn("Coto Digital", answer)

    def test_lists_fuel_promotions_in_plain_language(self):
        answer = answer_promo_question("¿Qué promos de combustible hay con Galicia?", PROMOTIONS)
        self.assertIn("Shell", answer)
        self.assertIn("Banco Galicia", answer)

    def test_assistant_allowlist_rejects_unrelated_or_oversized_questions(self):
        self.assertTrue(is_allowed_promo_question("¿En qué súper me conviene comprar vino hoy?"))
        self.assertTrue(is_allowed_promo_question("¿Alaris está excluido en Coto?"))
        self.assertFalse(is_allowed_promo_question("Escribí un poema sobre mi compra"))
        self.assertFalse(is_allowed_promo_question("promo " * 60))


if __name__ == "__main__":
    unittest.main()
