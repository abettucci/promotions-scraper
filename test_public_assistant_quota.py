import tempfile
import unittest
from pathlib import Path

from database import UserDatabase


class PublicAssistantQuotaTests(unittest.TestCase):
    def test_public_quota_is_limited_without_storing_raw_identity(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            db = UserDatabase(Path(temporary_dir) / "users.db")
            identity_hash = "a" * 64

            self.assertEqual(db.consume_public_assistant_quota(identity_hash, 2, 3600), 0)
            self.assertEqual(db.consume_public_assistant_quota(identity_hash, 2, 3600), 0)
            self.assertGreater(db.consume_public_assistant_quota(identity_hash, 2, 3600), 0)

    def test_public_quota_rejects_non_hmac_key(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            db = UserDatabase(Path(temporary_dir) / "users.db")
            self.assertEqual(db.consume_public_assistant_quota("not-an-ip", 5, 3600), 3600)


if __name__ == "__main__":
    unittest.main()
