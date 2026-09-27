import sys
import types
import unittest

# El entorno de tests de handlers no instala el parser HTML; para este unit test
# sólo se necesita importar la clase y el card se reemplaza por un doble mínimo.
sys.modules.setdefault("bs4", types.SimpleNamespace(BeautifulSoup=object))

from scrapers.masonline_scraper import MasOnlineScraper


class FakeCard:
    def find(self, _name):
        return None


class MasOnlineScraperTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
