import sys, os
current_test_dir = os.path.dirname(os.path.abspath(__file__))
sol_dir = os.path.dirname(current_test_dir)
root_dir = os.path.dirname(sol_dir)
for p in [sol_dir, root_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)
"""
Unit tests for Surprise Queue File Ingestion & Change Tolerance
"""

import unittest
import os
import json
import tempfile
from src.pipeline import BreakdownPipeline


class TestSurpriseFileTolerance(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output_dir = os.path.join(self.temp_dir.name, "outputs")
        self.audit_dir = os.path.join(self.temp_dir.name, "audit")
        self.pipeline = BreakdownPipeline(
            base_dir=".",
            output_dir=self.output_dir,
            audit_dir=self.audit_dir
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_surprise_csv_format(self):
        """Simulate surprise ticket queue arriving as CSV with changed column headers."""
        csv_content = """incident_id,reg_no,driver_code,from_hub,target_hub,distance_km,problem,customer,timestamp
TKT-9901,UP-40-IM-3144,DRV-020,Lucknow,Lucknow,20,fuel line leak,Shakti Cement,2026-08-11T19:00:00
TKT-9902,hr??unknown,DRV-010,Gurgaon,Kanpur,47,clutch slipping,Shakti Cement,2026-08-11T19:00:00
"""
        csv_path = os.path.join(self.temp_dir.name, "surprise_tickets.csv")
        with open(csv_path, "w", encoding="utf-8") as f:
            f.write(csv_content)

        stats = self.pipeline.process_queue_file(csv_path)
        self.assertEqual(stats["total_raw"], 2)
        self.assertEqual(stats["processed_valid"], 1)
        self.assertEqual(stats["quarantined"], 1)

    def test_surprise_nested_json(self):
        """Simulate surprise ticket queue with nested wrapper structure."""
        nested_data = {
            "version": "2.0",
            "records": [
                {
                    "ticketId": "TKT-8801",
                    "truck_id": "DL-64-IB-1058",
                    "driver": "DRV-034",
                    "origin": "Delhi",
                    "dest": "Ludhiana",
                    "km": "122 km",
                    "fault": "turbo failure",
                    "account": "Orion Pharma",
                    "date": "2026-03-07T06:00:00"
                }
            ]
        }
        json_path = os.path.join(self.temp_dir.name, "surprise_nested.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(nested_data, f)

        stats = self.pipeline.process_queue_file(json_path)
        self.assertEqual(stats["total_raw"], 1)
        self.assertEqual(stats["processed_valid"], 1)
        self.assertEqual(stats["quarantined"], 0)


if __name__ == '__main__':
    unittest.main()
