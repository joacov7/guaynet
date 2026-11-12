import unittest

from fastapi.routing import APIRoute

from app.api.v1.endpoints.smart import router as smart_router


class SmartRouteRegistrationTests(unittest.TestCase):
    def test_expected_routes_and_methods_are_registered(self):
        routes = {
            (route.path, method)
            for route in smart_router.routes
            if isinstance(route, APIRoute)
            for method in route.methods
        }
        expected = {
            ("/organizations", "POST"),
            ("/organizations", "GET"),
            ("/installations", "GET"),
            ("/installations/{installation_id}", "GET"),
            ("/organizations/{organization_id}/installations", "POST"),
        }
        self.assertTrue(expected.issubset(routes))


if __name__ == "__main__":
    unittest.main()
