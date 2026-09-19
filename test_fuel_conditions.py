import unittest

from fuel_conditions import extract_fuel_conditions


class FuelConditionsTests(unittest.TestCase):
    def test_extracts_program_and_user_eligibility(self):
        requirements, exclusions = extract_fuel_conditions(
            "Beneficio exclusivo para clientes adheridos a Shell Box que paguen con la app. "
            "No acumulable con otras promociones ni válido para cuentas corporativas."
        )

        self.assertTrue(any("Shell Box" in item for item in requirements))
        self.assertTrue(any("No acumulable" in item for item in exclusions))

    def test_preserves_structured_values_without_inventing_conditions(self):
        requirements, exclusions = extract_fuel_conditions(
            "Válido todos los martes.",
            requirements=["Pago con QR"],
            exclusions=["No aplica a GNC"],
        )

        self.assertEqual(requirements, ["Pago con QR"])
        self.assertEqual(exclusions, ["No aplica a GNC"])


if __name__ == "__main__":
    unittest.main()
