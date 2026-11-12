import unittest

from pydantic import ValidationError

from app.api.v1.endpoints.smart import (
    GatewayInventorySync, InstallationCreate, OrganizationCreate,
)


class SmartBootstrapSchemaTests(unittest.TestCase):
    def test_valid_family_organization(self):
        payload = OrganizationCreate(name="Casa", organization_type="family")
        self.assertEqual(payload.name, "Casa")

    def test_organization_name_is_trimmed(self):
        payload = OrganizationCreate(name=" Casa ")
        self.assertEqual(payload.name, "Casa")

    def test_whitespace_only_organization_name_is_rejected(self):
        with self.assertRaises(ValidationError):
            OrganizationCreate(name="   ")

    def test_invalid_organization_type_is_rejected(self):
        with self.assertRaises(ValidationError):
            OrganizationCreate(name="Empresa", organization_type="unknown")

    def test_valid_home_installation(self):
        payload = InstallationCreate(name="Casa principal", installation_type="home")
        self.assertEqual(payload.installation_type, "home")

    def test_installation_name_is_trimmed(self):
        payload = InstallationCreate(name=" Casa ", installation_type="home")
        self.assertEqual(payload.name, "Casa")

    def test_whitespace_only_installation_name_is_rejected(self):
        with self.assertRaises(ValidationError):
            InstallationCreate(name="   ", installation_type="home")

    def test_invalid_installation_type_is_rejected(self):
        with self.assertRaises(ValidationError):
            InstallationCreate(name="Casa", installation_type="vehicle")


    def test_gateway_inventory_accepts_devices_and_entities(self):
        payload = GatewayInventorySync(
            devices=[{
                "external_device_id": "light.kitchen",
                "name": "Luz cocina",
                "availability": "available",
            }],
            entities=[{
                "external_entity_id": "light.kitchen",
                "external_device_id": "light.kitchen",
                "domain": "light",
                "name": "Luz cocina",
                "state": "on",
            }],
        )
        self.assertEqual(len(payload.devices), 1)
        self.assertEqual(len(payload.entities), 1)

    def test_gateway_inventory_rejects_invalid_availability(self):
        with self.assertRaises(ValidationError):
            GatewayInventorySync(devices=[{
                "external_device_id": "switch.test",
                "name": "Interruptor",
                "availability": "sleeping",
            }])

    def test_gateway_inventory_enforces_batch_limits(self):
        with self.assertRaises(ValidationError):
            GatewayInventorySync(entities=[{}] * 2001)

    def test_short_names_are_rejected(self):
        with self.assertRaises(ValidationError):
            OrganizationCreate(name="A")
        with self.assertRaises(ValidationError):
            InstallationCreate(name="A", installation_type="home")


if __name__ == "__main__":
    unittest.main()
