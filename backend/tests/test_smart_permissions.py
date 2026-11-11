import unittest

from app.core.smart_permissions import _permission_is_allowed


class SmartPermissionPolicyTests(unittest.TestCase):
    def test_role_grant_allows_normal_permission(self):
        self.assertTrue(_permission_is_allowed(True, None, "normal"))

    def test_default_deny(self):
        self.assertFalse(_permission_is_allowed(False, None, "normal"))

    def test_explicit_deny_wins_over_role_grant(self):
        self.assertFalse(_permission_is_allowed(True, "deny", "normal"))

    def test_explicit_grant_can_add_noncritical_permission(self):
        self.assertTrue(_permission_is_allowed(False, "grant", "sensitive"))

    def test_critical_permission_cannot_be_granted_by_generic_override(self):
        self.assertFalse(_permission_is_allowed(True, "grant", "critical"))
        self.assertFalse(_permission_is_allowed(False, "grant", "critical"))

    def test_unknown_override_falls_back_to_role(self):
        self.assertTrue(_permission_is_allowed(True, "unknown", "normal"))
        self.assertFalse(_permission_is_allowed(False, "unknown", "normal"))


if __name__ == "__main__":
    unittest.main()
