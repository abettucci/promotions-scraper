import unittest

from promo_questions import answer_promo_question


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


if __name__ == "__main__":
    unittest.main()
