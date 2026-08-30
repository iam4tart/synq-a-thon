import sys, os
current_test_dir = os.path.dirname(os.path.abspath(__file__))
sol_dir = os.path.dirname(current_test_dir)
root_dir = os.path.dirname(sol_dir)
for p in [sol_dir, root_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)
"""
Unit tests for PII Sanitizer & Egress Guardrail
"""

import unittest
from src.pii_sanitizer import PIISanitizer, REPLACEMENT_PHONE, REPLACEMENT_AADHAAR, REPLACEMENT_DL


class TestPIISanitizer(unittest.TestCase):

    def test_phone_masking(self):
        # Ravi's phone from dispatcher_interview.txt
        sample = "Ravi's number is +91 93118 40522 if you ever need the pairing"
        sanitized = PIISanitizer.sanitize_text(sample)
        self.assertNotIn("93118", sanitized)
        self.assertIn(REPLACEMENT_PHONE, sanitized)
        self.assertFalse(PIISanitizer.contains_raw_pii(sanitized))

    def test_aadhaar_masking(self):
        sample = "Driver Aadhaar: 5482 9102 3847 confirmed."
        sanitized = PIISanitizer.sanitize_text(sample)
        self.assertNotIn("5482", sanitized)
        self.assertIn(REPLACEMENT_AADHAAR, sanitized)
        self.assertFalse(PIISanitizer.contains_raw_pii(sanitized))

    def test_dl_masking(self):
        sample = "License verified: DL-0420110023456 active."
        sanitized = PIISanitizer.sanitize_text(sample)
        self.assertNotIn("0420110023456", sanitized)
        self.assertIn(REPLACEMENT_DL, sanitized)
        self.assertFalse(PIISanitizer.contains_raw_pii(sanitized))

    def test_nested_record_sanitization(self):
        record = {
            "ticket_id": "TKT-0001",
            "driver": {
                "name": "Advik Maharaj",
                "phone": "+91 9876543210",
                "aadhaar": "9876 5432 1098",
                "dl_number": "HR-2620150098765"
            },
            "notes": ["Contact at 9876543210 immediately"]
        }
        sanitized = PIISanitizer.sanitize_record(record)
        self.assertEqual(sanitized["driver"]["phone"], REPLACEMENT_PHONE)
        self.assertEqual(sanitized["driver"]["aadhaar"], REPLACEMENT_AADHAAR)
        self.assertEqual(sanitized["driver"]["dl_number"], REPLACEMENT_DL)
        self.assertIn(REPLACEMENT_PHONE, sanitized["notes"][0])


if __name__ == '__main__':
    unittest.main()
