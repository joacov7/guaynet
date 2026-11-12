import unittest

from uuid import uuid4

from app.core.smart_permissions import (
    _permission_is_allowed,
    _role_is_valid_for_installation,
    _role_is_valid_for_organization,
)


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


class SmartRoleScopeTests(unittest.TestCase):
    def setUp(self):
        self.organization_id = uuid4()
        self.other_organization_id = uuid4()

    def test_global_installation_role_is_valid(self):
        self.assertTrue(
            _role_is_valid_for_installation("installation", None, self.organization_id)
        )

    def test_same_organization_installation_role_is_valid(self):
        self.assertTrue(
            _role_is_valid_for_installation(
                "installation", self.organization_id, self.organization_id
            )
        )

    def test_foreign_organization_role_is_rejected(self):
        self.assertFalse(
            _role_is_valid_for_installation(
                "installation", self.other_organization_id, self.organization_id
            )
        )

    def test_organization_scope_role_is_rejected(self):
        self.assertFalse(
            _role_is_valid_for_installation("organization", None, self.organization_id)
        )

    def test_global_organization_role_is_valid(self):
        self.assertTrue(
            _role_is_valid_for_organization("organization", None, self.organization_id)
        )

    def test_same_organization_custom_role_is_valid(self):
        self.assertTrue(
            _role_is_valid_for_organization(
                "organization", self.organization_id, self.organization_id
            )
        )

    def test_foreign_organization_role_is_rejected_for_organization(self):
        self.assertFalse(
            _role_is_valid_for_organization(
                "organization", self.other_organization_id, self.organization_id
            )
        )

    def test_installation_role_is_rejected_for_organization(self):
        self.assertFalse(
            _role_is_valid_for_organization("installation", None, self.organization_id)
        )


if __name__ == "__main__":
    unittest.main()
