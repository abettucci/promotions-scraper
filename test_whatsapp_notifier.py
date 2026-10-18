import unittest

from whatsapp_notifier import normalize_phone


class WhatsAppNotifierTests(unittest.TestCase):
    def test_normalizes_e164_phone_for_sidecar_chat_id(self):
        self.assertEqual(normalize_phone("+54 9 11 2345-6789"), "5491123456789")

    def test_rejects_non_international_phone(self):
        with self.assertRaises(ValueError):
            normalize_phone("1123456789")


if __name__ == "__main__":
    unittest.main()
