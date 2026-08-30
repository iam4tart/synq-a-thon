import sys, os
current_test_dir = os.path.dirname(os.path.abspath(__file__))
sol_dir = os.path.dirname(current_test_dir)
root_dir = os.path.dirname(sol_dir)
for p in [sol_dir, root_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)
"""
Unit tests for Context Store
"""

import unittest
from datetime import date
from src.context_store import ContextStore


class TestContextStore(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.store = ContextStore(base_dir=".")

    def test_fleet_loaded(self):
        self.assertGreater(len(self.store.vehicles), 50)
        v = self.store.get_vehicle("UP17GN7381")
        self.assertIsNotNone(v)
        self.assertEqual(v["canonical_plate"], "UP17GN7381")

    def test_drivers_sanitized_at_ingestion(self):
        d = self.store.get_driver("DRV-001")
        self.assertIsNotNone(d)
        self.assertEqual(d["phone"], "[PHONE_REDACTED]")
        self.assertEqual(d["aadhaar"], "[AADHAAR_REDACTED]")
        self.assertEqual(d["dl_number"], "[DL_REDACTED]")

    def test_maintenance_indexed(self):
        self.assertGreater(len(self.store.maintenance_records), 10)

    def test_interview_citations(self):
        self.assertIn("RULE_NCR_BS4_WINTER", self.store.interview_citations)
        self.assertIn("RULE_50KM_ORIGIN_HUB", self.store.interview_citations)


if __name__ == '__main__':
    unittest.main()
