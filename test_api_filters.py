import sqlite3
import unittest

import api


class FilterQueryTests(unittest.TestCase):
    def test_store_and_payment_filters_use_any_selected_value(self):
        stores, store_params = [], []
        api._append_supermarket_filter(stores, store_params, "Carrefour,Disco")
        self.assertIn("LOWER(s.name) IN (?,?)", stores[0])
        self.assertEqual(store_params, ["carrefour", "disco"])

        banks, bank_params = [], []
        api._append_bank_filter(banks, bank_params, "Banco Nación,Modo")
        self.assertIn(" OR ", banks[0])
        self.assertEqual(bank_params, ["%banco nación%"] * 3 + ["%modo%"] * 3)

    def test_province_matches_explicit_region_and_keeps_unscoped_promotions(self):
        conditions, params = [], []
        api._append_province_filter(conditions, params, "cordoba")
        connection = sqlite3.connect(":memory:")
        connection.execute("CREATE TABLE promotions (title TEXT, terms_raw TEXT, exclusions TEXT, requirements TEXT, store_types TEXT)")
        connection.executemany("INSERT INTO promotions VALUES (?, ?, '', '', '')", [
            ("Beneficio regional", "Válido sólo en la provincia de Córdoba"),
            ("Beneficio nacional", "Válido en todo el país"),
            ("Beneficio ajeno", "Válido sólo en la provincia de Salta"),
        ])
        rows = connection.execute(f"SELECT title FROM promotions p WHERE {' AND '.join(conditions)} ORDER BY title", params).fetchall()
        self.assertEqual([row[0] for row in rows], ["Beneficio nacional", "Beneficio regional"])

    def test_buenos_aires_does_not_match_caba_only_terms(self):
        conditions, params = [], []
        api._append_province_filter(conditions, params, "buenos aires")
        connection = sqlite3.connect(":memory:")
        connection.execute("CREATE TABLE promotions (title TEXT, terms_raw TEXT, exclusions TEXT, requirements TEXT, store_types TEXT)")
        connection.executemany("INSERT INTO promotions VALUES (?, ?, '', '', '')", [
            ("CABA", "Válido en CABA y Capital Federal"),
            ("PBA", "Válido en la provincia de Buenos Aires"),
        ])
        rows = connection.execute(f"SELECT title FROM promotions p WHERE {' AND '.join(conditions)} ORDER BY title", params).fetchall()
        self.assertEqual([row[0] for row in rows], ["PBA"])


if __name__ == "__main__":
    unittest.main()
