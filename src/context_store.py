import os
import glob
import re
from datetime import datetime, date
from typing import Dict, List, Any, Optional
import pandas as pd

from .pii_sanitizer import PIISanitizer
from .entity_resolution import EntityResolver


class ContextStore:

    def __init__(self, base_dir: str = "."):
        self.base_dir = base_dir
        self.vehicles: Dict[str, Dict[str, Any]] = {}
        self.drivers: Dict[str, Dict[str, Any]] = {}
        self.maintenance_records: Dict[str, List[Dict[str, Any]]] = {}
        self.client_agreements: Dict[str, Dict[str, Any]] = {}
        self.interview_citations: Dict[str, str] = {}
        self._load_all()

    def _find_path(self, filename: str) -> Optional[str]:
        candidates = [
            os.path.join(self.base_dir, filename),
            os.path.join(self.base_dir, "data", filename),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", filename),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", filename),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", filename),
        ]
        for c in candidates:
            if os.path.exists(c):
                return os.path.abspath(c)
        return None

    def _load_all(self):
        self._load_fleet_master()
        self._load_drivers_roster()
        self._load_maintenance_logs()
        self._load_emails()
        self._load_interview_transcript()

    def _load_fleet_master(self):
        path = self._find_path("fleet_master.csv")
        if not path or not os.path.exists(path):
            return
        df = pd.read_csv(path)
        for _, row in df.iterrows():
            canonical_plate = EntityResolver.canonicalize_plate(str(row.get("registration_number", "")))
            if not canonical_plate:
                continue
            heater_val = str(row.get("engine_heater", "")).strip().lower()
            has_heater = heater_val in ("true", "1", "yes", "y")
            v_info = {
                "vehicle_id": str(row.get("vehicle_id", "")).strip(),
                "canonical_plate": canonical_plate,
                "raw_plate": str(row.get("registration_number", "")).strip(),
                "model": str(row.get("model", "")).strip(),
                "year": int(row.get("year", 2018)) if pd.notnull(row.get("year")) else 2018,
                "bs_stage": str(row.get("bs_stage", "BS4")).strip().upper(),
                "engine_heater": has_heater,
                "home_hub": str(row.get("home_hub", "Gurgaon")).strip(),
                "capacity_tonnes": float(row.get("capacity_tonnes", 30.0)) if pd.notnull(row.get("capacity_tonnes")) else 30.0,
                "status": str(row.get("status", "Active")).strip(),
                "source_citation": "fleet_master.csv"
            }
            self.vehicles[canonical_plate] = v_info
            if v_info["vehicle_id"]:
                self.vehicles[v_info["vehicle_id"]] = v_info

    def _load_drivers_roster(self):
        path = self._find_path("drivers_roster.csv")
        if not path or not os.path.exists(path):
            return
        df = pd.read_csv(path)
        for _, row in df.iterrows():
            driver_id = str(row.get("driver_id", "")).strip()
            if not driver_id:
                continue
            sanitized = PIISanitizer.sanitize_record(row.to_dict())
            self.drivers[driver_id] = {
                "driver_id": driver_id,
                "name": str(sanitized.get("name", "")).strip(),
                "joining_date": str(sanitized.get("joining_date", "")).strip(),
                "home_hub": str(sanitized.get("home_hub", "")).strip(),
                "phone": sanitized.get("phone"),
                "dl_number": sanitized.get("dl_number"),
                "aadhaar": sanitized.get("aadhaar"),
                "source_citation": "drivers_roster.csv"
            }

    def _load_maintenance_logs(self):
        path = self._find_path("maintenance_log.xlsx")
        if not path or not os.path.exists(path):
            return
        df = pd.read_excel(path)
        for _, row in df.iterrows():
            canonical_plate = EntityResolver.canonicalize_plate(str(row.get("vehicle", "")))
            if not canonical_plate:
                continue
            raw_date = row.get("date")
            parsed_date = None
            if isinstance(raw_date, (datetime, date)):
                parsed_date = raw_date
            elif pd.notnull(raw_date):
                try:
                    parsed_date = datetime.strptime(str(raw_date).split("T")[0], "%Y-%m-%d").date()
                except Exception:
                    pass
            notes = str(row.get("notes", "")).strip()
            mechanic = str(row.get("mechanic", "")).strip()
            is_brake_work = bool(re.search(r'\bbrake\b|\bpad\b|\bdrum\b', notes, re.IGNORECASE))
            is_guddu_jugaad = bool(re.search(r'\bjugaad\b|\btemporary\b', notes, re.IGNORECASE) or "guddu" in mechanic.lower())
            rec = {
                "date": parsed_date,
                "vehicle": canonical_plate,
                "odometer_km": int(row.get("odometer_km", 0)) if pd.notnull(row.get("odometer_km")) else 0,
                "mechanic": mechanic,
                "notes": notes,
                "is_brake_work": is_brake_work,
                "is_guddu_jugaad": is_guddu_jugaad,
                "source_citation": "maintenance_log.xlsx"
            }
            if canonical_plate not in self.maintenance_records:
                self.maintenance_records[canonical_plate] = []
            self.maintenance_records[canonical_plate].append(rec)

    def _load_emails(self):
        email_dir = self._find_path("emails")
        if not email_dir or not os.path.exists(email_dir):
            return
        email_pattern = os.path.join(email_dir, "*")
        for filepath in glob.glob(email_pattern):
            try:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                if "shakticement" in content.lower() or "shakti" in content.lower():
                    if "36 hour" in content.lower() or "36 hours" in content.lower():
                        self.client_agreements["Shakti Cement"] = {
                            "operational_sla_hours": 36,
                            "contract_sla_hours": 48,
                            "rule_reason": "Plant scheduling runs on 36 hours as confirmed by Prakash Nair in email",
                            "source_citation": os.path.basename(filepath)
                        }
            except Exception:
                pass

    def _load_interview_transcript(self):
        path = self._find_path("dispatcher_interview.txt")
        if not path or not os.path.exists(path):
            return
        self.interview_citations = {
            "RULE_NCR_BS4_WINTER": "dispatcher_interview.txt:L15-L25 (Oct-Feb BS4 NCR border restriction)",
            "RULE_HILL_ROADS": "dispatcher_interview.txt:L27-L35 (Rudrapur/Nainital: engine heater + 30-day zero brake work)",
            "RULE_SHAKTI_SLA_36H": "dispatcher_interview.txt:L37-L45 (Shakti Cement operational 36h delivery window)",
            "RULE_VERTEX_6PM_CUTOFF": "dispatcher_interview.txt:L47-L55 (Vertex Retail Ludhiana 18:00 cutoff -> 08:00 AM delivery)",
            "RULE_APEX_PLATE_ROTATION": "dispatcher_interview.txt:L57-L63 (Apex Chemicals problem plate rotation)",
            "RULE_ORION_PHARMA": "dispatcher_interview.txt:L65-L70 (Orion Pharma: 2020+ vehicle year and refrigerated)",
            "RULE_MONSOON_EAST_BUFFER": "dispatcher_interview.txt:L72-L80 (July-Sept east of Lucknow +20% duration buffer)",
            "RULE_50KM_ORIGIN_HUB": "dispatcher_interview.txt:L82-L95 (<=50km origin hub sends; >50km nearest eligible hub)",
            "RULE_GROUNDED_OVERDUE_SERVICE": "dispatcher_interview.txt:L90-L95 (>30 days overdue for service is grounded)",
            "RULE_GUDDU_TEMPORARY_PATCH": "dispatcher_interview.txt:L97-L105 (Guddu jugaad: 7-day clock + restricted to home region)",
            "RULE_DRIVER_NIGHT_PAIRING": "dispatcher_interview.txt:L107-L120 (Driver <6 months tenure requires pairing for night dispatches)"
        }

    def get_vehicle(self, plate_or_id: str) -> Optional[Dict[str, Any]]:
        canonical = EntityResolver.canonicalize_plate(plate_or_id)
        if canonical and canonical in self.vehicles:
            return self.vehicles[canonical]
        return self.vehicles.get(plate_or_id)

    def get_driver(self, driver_id: str) -> Optional[Dict[str, Any]]:
        return self.drivers.get(driver_id)

    def get_recent_brake_work_days(self, canonical_plate: str, as_of_date: date) -> Optional[int]:
        records = self.maintenance_records.get(canonical_plate, [])
        days_min = None
        for r in records:
            if r.get("is_brake_work") and r.get("date"):
                delta = (as_of_date - r["date"]).days
                if delta >= 0 and (days_min is None or delta < days_min):
                    days_min = delta
        return days_min

    def get_guddu_jugaad_active(self, canonical_plate: str, as_of_date: date) -> bool:
        records = self.maintenance_records.get(canonical_plate, [])
        for r in records:
            if r.get("is_guddu_jugaad") and r.get("date"):
                delta = (as_of_date - r["date"]).days
                if 0 <= delta <= 7:
                    return True
        return False
