import unittest

from app.services.dhcp_identity import normalize_mac


class NormalizeMacTests(unittest.TestCase):
    def test_colon_format(self):
        self.assertEqual(normalize_mac("AA:BB:CC:DD:EE:FF"), "aa:bb:cc:dd:ee:ff")

    def test_hyphen_format(self):
        self.assertEqual(normalize_mac("AA-BB-CC-DD-EE-FF"), "aa:bb:cc:dd:ee:ff")

    def test_dotted_format(self):
        self.assertEqual(normalize_mac("aabb.ccdd.eeff"), "aa:bb:cc:dd:ee:ff")

    def test_compact_format(self):
        self.assertEqual(normalize_mac("AABBCCDDEEFF"), "aa:bb:cc:dd:ee:ff")

    def test_invalid_values(self):
        for value in ("", None, "not-a-mac", "aa:bb:cc", "gg:bb:cc:dd:ee:ff", "aa:bb:cc:dd:ee:ff:00"):
            with self.subTest(value=value):
                self.assertEqual(normalize_mac(value), "")


if __name__ == "__main__":
    unittest.main()
