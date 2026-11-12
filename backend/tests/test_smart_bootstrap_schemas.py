import unittest

from pydantic import ValidationError

from app.api.v1.endpoints.smart import InstallationCreate, OrganizationCreate


class SmartBootstrapSchemaTests(unittest.TestCase):
    def test_valid_family_organization(self):
        payload = OrganizationCreate(name="Casa", organization_type="family")
        self.assertEqual(payload.name, "Casa")

    def test_organization_name_is_trimmed_by_endpoint_not_schema(self):
        payload = OrganizationCreate(name=" Casa ")
        self.assertEqual(payload.name, " Casa ")

    def test_invalid_organization_type_is_rejected(self):
        with self.assertRaises(ValidationError):
            OrganizationCreate(name="Empresa", organization_type="unknown")

    def test_valid_home_installation(self):
        payload = InstallationCreate(name="Casa principal", installation_type="home")
        self.assertEqual(payload.installation_type, "home")

    def test_invalid_installation_type_is_rejected(self):
        with self.assertRaises(ValidationError):
            InstallationCreate(name="Casa", installation_type="vehicle")

    def test_short_names_are_rejected(self):
        with self.assertRaises(ValidationError):
            OrganizationCreate(name="A")
        with self.assertRaises(ValidationError):
            InstallationCreate(name="A", installation_type="home")


if __name__ == "__main__":
    unittest.main()
