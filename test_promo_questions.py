import unittest
from datetime import date

from promo_questions import answer_promo_question, is_allowed_promo_question


PROMOTIONS = [
    {
        "supermarket_name": "Coto Digital", "category": "supermarket",
        "title": "30% todos los productos", "discount": "30%", "bank": "Banco Uno",
        "valid_days": "Todos los días", "exclusions": "Quedan excluidos vinos Alaris y bebidas alcohólicas",
        "terms_raw": "Válido hoy", "tope": "$10.000",
    },
    {
        "supermarket_name": "Carrefour", "category": "supermarket",
        "title": "25% en bebidas", "discount": "25%", "wallet": "MODO",
        "valid_days": "Todos los días", "exclusions": "", "terms_raw": "Aplica en vinos", "tope": "$5.000",
    },
    {
        "supermarket_name": "Shell", "category": "fuel",
        "title": "20% en combustibles", "discount": "20%", "bank": "Banco Galicia",
        "valid_days": "Todos los días", "exclusions": "", "terms_raw": "", "tope": "$3.000",
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
            "valid_days": "Todos los días", "tope": "$10.000",
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


class PromoQueryInterpretationTests(unittest.TestCase):
    """Preguntas libres: comercio, banco, día, rubro, método y 'el mejor'."""

    FRIDAY = date(2026, 10, 2)
    PROMOS = [
        {"supermarket_name": "Coto Digital", "category": "supermarket", "title": "MP 25% viernes",
         "discount": "25% descuento", "wallet": "Mercado Pago", "payment_method": "QR Mercado Pago",
         "valid_days": "Viernes", "store_types": "Tiendas", "tope": "Sin tope"},
        {"supermarket_name": "Coto Digital", "category": "supermarket", "title": "Ciudad 25% lunes",
         "discount": "25% descuento", "bank": "Banco Ciudad", "valid_days": "Lunes",
         "store_types": "Online", "tope": "$30.000"},
        {"supermarket_name": "Supermercados Día", "category": "supermarket", "title": "BNA MODO 10%",
         "discount": "10% reintegro", "bank": "Banco Nación", "wallet": "MODO",
         "payment_method": "QR MODO", "valid_days": "Viernes, Sábado", "min_purchase": "$35.000"},
        {"supermarket_name": "Carrefour", "category": "supermarket", "title": "Club La Nación 15%",
         "discount": "15%", "wallet": "Club La Nación", "valid_days": "Lunes"},
        {"supermarket_name": "Shell", "category": "fuel", "title": "Comafi 20% domingo",
         "discount": "20% reintegro", "bank": "Banco Comafi", "wallet": "MODO",
         "payment_method": "QR MODO", "valid_days": "Domingo", "tope": "$6.000 semanal"},
        {"supermarket_name": "YPF", "category": "fuel", "title": "Macro 30% miércoles",
         "discount": "30% reintegro", "bank": "Banco Macro", "wallet": "MODO", "valid_days": "Miércoles"},
    ]

    def ask(self, question):
        return answer_promo_question(question, self.PROMOS, [], today=self.FRIDAY)

    def test_today_in_a_merchant_alias(self):
        answer = self.ask("¿Qué hay hoy en Coto?")
        self.assertIn("<b>25% descuento</b> con Mercado Pago", answer)
        self.assertNotIn("Banco Ciudad", answer)

    def test_best_fuel_discount_for_a_weekday(self):
        answer = self.ask("¿Cuál es el mejor descuento en nafta el domingo?")
        self.assertIn("Shell", answer)
        self.assertNotIn("YPF", answer)
        self.assertNotIn("Coto", answer)

    def test_bna_alias_does_not_match_club_la_nacion(self):
        answer = self.ask("promos con BNA")
        self.assertIn("Banco Nación", answer)
        self.assertIn("mín. $35.000", answer)
        self.assertNotIn("Club La Nación", answer)

    def test_method_and_channel_filters(self):
        self.assertIn("Supermercados Día", self.ask("descuentos con QR en el super mañana"))
        online = self.ask("promos online en coto")
        self.assertIn("Banco Ciudad", online)
        self.assertNotIn("Mercado Pago", online)

    def test_empty_result_suggests_other_days(self):
        answer = self.ask("¿Hay algo con Comafi el lunes?")
        self.assertIn("No encontré", answer)
        self.assertIn("domingo", answer)

    def test_help_lists_varied_examples(self):
        answer = self.ask("hola, ¿qué podés hacer?")
        self.assertIn("nafta", answer)
        self.assertIn("Galicia", answer)
        self.assertTrue(is_allowed_promo_question("hola, ¿qué podés hacer?"))
        self.assertTrue(is_allowed_promo_question("¿Qué hay hoy en Coto?"))


if __name__ == "__main__":
    unittest.main()
