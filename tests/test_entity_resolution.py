import sys, os
current_test_dir = os.path.dirname(os.path.abspath(__file__))
sol_dir = os.path.dirname(current_test_dir)
root_dir = os.path.dirname(sol_dir)
for p in [sol_dir, root_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)
import unittest
from src.entity_resolution import EntityResolver


class TestEntityResolver(unittest.TestCase):

    def test_plate_canonicalization(self):
        self.assertEqual(EntityResolver.canonicalize_plate("UP-40-IM-3144"), "UP40IM3144")
        self.assertEqual(EntityResolver.canonicalize_plate("up86cm7252"), "UP86CM7252")
        self.assertEqual(EntityResolver.canonicalize_plate("DL-64-IB-1058"), "DL64IB1058")
        self.assertEqual(EntityResolver.canonicalize_plate("HR 16 SP 9238"), "HR16SP9238")
        self.assertIsNone(EntityResolver.canonicalize_plate("hr??unknown"))
        self.assertIsNone(EntityResolver.canonicalize_plate(""))

    def test_fuzzy_plate_fleet_matching(self):
        known_fleet = {"UP40IM3144", "DL64IB1058", "HR16SP9238"}
        self.assertEqual(EntityResolver.canonicalize_plate("UP401M3144", known_fleet=known_fleet), "UP40IM3144")

    def test_fuzzy_client_matching(self):
        self.assertEqual(EntityResolver.canonicalize_client("Shakthi Cements"), "Shakti Cement")
        self.assertEqual(EntityResolver.canonicalize_client("apex chem"), "Apex Chemicals")
        self.assertEqual(EntityResolver.canonicalize_client("Orion Pharmaceuticals"), "Orion Pharma")
        self.assertEqual(EntityResolver.canonicalize_client("Vertx Retail Ltd"), "Vertex Retail")

    def test_geography_detection(self):
        self.assertTrue(EntityResolver.is_ncr_route("Gurgaon", "Kanpur"))
        self.assertTrue(EntityResolver.is_ncr_route("Jaipur", "Delhi"))
        self.assertFalse(EntityResolver.is_ncr_route("Lucknow", "Varanasi"))
        self.assertTrue(EntityResolver.is_hill_route("Ambala", "Rudrapur"))
        self.assertFalse(EntityResolver.is_hill_route("Delhi", "Jaipur"))
        self.assertTrue(EntityResolver.is_east_of_lucknow_route("Lucknow", "Patna"))


if __name__ == '__main__':
    unittest.main()
