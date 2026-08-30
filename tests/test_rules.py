import sys, os
current_test_dir = os.path.dirname(os.path.abspath(__file__))
sol_dir = os.path.dirname(current_test_dir)
root_dir = os.path.dirname(sol_dir)
for p in [sol_dir, root_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)
"""
Unit tests for Expert Rules Engine
"""

import unittest
from src.context_store import ContextStore
from src.rules_engine import RulesEngine


class TestRulesEngine(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.store = ContextStore(base_dir=".")
        cls.engine = RulesEngine(cls.store)

    def test_shakti_36h_rule(self):
        ticket = {
            "ticket_id": "TKT-0027",
            "created_at": "2026-08-11T19:00:00",
            "vehicle": "UP-40-IM-3144",
            "origin_hub": "Lucknow",
            "km_from_origin_hub": 20,
            "destination": "Lucknow",
            "client": "Shakti Cement"
        }
        res = self.engine.evaluate_breakdown(ticket)
        self.assertEqual(res.sla_hours, 36)
        self.assertIn("RULE_SHAKTI_SLA_36H", res.rules_applied)
        self.assertIn("RULE_50KM_ORIGIN_HUB", res.rules_applied)

    def test_orion_pharma_2020_plus(self):
        ticket = {
            "ticket_id": "TKT-0017",
            "created_at": "2026-04-30T07:00:00",
            "vehicle": "up86cm7252",
            "origin_hub": "Kanpur",
            "km_from_origin_hub": 22,
            "destination": "Delhi",
            "client": "Orion Pharma"
        }
        res = self.engine.evaluate_breakdown(ticket)
        self.assertIn("RULE_ORION_PHARMA", res.rules_applied)
        if res.eligible_replacement_plate:
            v = self.store.get_vehicle(res.eligible_replacement_plate)
            self.assertGreaterEqual(v["year"], 2020)


if __name__ == '__main__':
    unittest.main()
