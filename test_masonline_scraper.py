import sys
import types
import unittest

# El entorno de tests de handlers no instala el parser HTML; para este unit test
# sólo se necesita importar la clase y el card se reemplaza por un doble mínimo.
sys.modules.setdefault("bs4", types.SimpleNamespace(BeautifulSoup=object))

from scrapers.masonline_scraper import (
    MasOnlineScraper,
    _JS_EXPAND_VER_LEGAL,
    _JS_WAIT_FOR_PROMOTIONS,
)
from terms_parser import TermsParser


class FakeCard:
    def find(self, _name):
        return None


class MasOnlineScraperTests(unittest.TestCase):
    def test_legal_expansion_waits_for_controls_and_clicks_each_once(self):
        self.assertIn("ver\\s*legal", _JS_WAIT_FOR_PROMOTIONS)
        self.assertIn("no hay promociones vigentes", _JS_WAIT_FOR_PROMOTIONS)
        self.assertIn("new Set", _JS_EXPAND_VER_LEGAL)
        self.assertIn("aria-expanded", _JS_EXPAND_VER_LEGAL)
        self.assertIn("childHasLabel", _JS_EXPAND_VER_LEGAL)

    def test_expanded_legal_is_sent_to_the_terms_pipeline(self):
        legal = (
            "15% de descuento MásClub Presencial y online ¡SIN TOPE! "
            "Promoción exclusiva para todos los socios de MásClub. "
            "Válida del 01/04/2026 al 31/12/2026 únicamente para compras "
            "realizadas los días Miércoles y Jueves. No acumulable con otras "
            "promociones. EXCLUIDOS-NO INCLUYE: CARNICERÍA, GRANJA, VINOS Y "
            "ELECTRODOMÉSTICOS."
        )

        promo = MasOnlineScraper()._parse_promo(
            FakeCard(), legal, "Miércoles", "https://www.masonline.com.ar/promociones-bancarias?dia=miercoles",
        )

        self.assertEqual(promo["terms_raw"], legal)
        self.assertNotIn("raw_text", promo)
        self.assertEqual(promo["requirements"], "Exclusiva para socios de MásClub")
        self.assertIn("No", promo["acumulable"])
        self.assertIn("CARNICERÍA", promo["exclusions"])

    def test_included_products_are_explained_as_an_exclusion_boundary(self):
        legal = (
            "PROMOCIÓN EXCLUSIVA PARA BENEFICIARIOS DE ANSES. "
            "ÚNICAMENTE EN LOS PRODUCTOS DETALLADOS A CONTINUACIÓN: CONSERVA "
            "DE TOMATES, PASTAS SECAS, ARROZ, CAFÉ, TÉ Y VINOS. NO ACUMULA "
            "CON OTRAS PROMOCIONES VIGENTES."
        )

        terms = TermsParser().parse(legal)

        self.assertTrue(terms["exclusions"])
        self.assertIn("todo producto fuera de esta lista queda excluido", terms["exclusions"])
        self.assertIn("PASTAS SECAS", terms["exclusions"])
        self.assertNotIn("ÚNICAMENTE EN LOS PRODUCTOS", terms["requirements"])


if __name__ == "__main__":
    unittest.main()
