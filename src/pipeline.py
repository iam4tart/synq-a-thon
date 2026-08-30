import os
import json
import csv
import re
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Set, Tuple

from .pii_sanitizer import PIISanitizer
from .entity_resolution import EntityResolver
from .context_store import ContextStore
from .rules_engine import RulesEngine, DecisionResult


class BreakdownPipeline:

    def __init__(self, base_dir: str = ".", output_dir: str = "solutions/outputs", audit_dir: str = "solutions/audit"):
        self.base_dir = base_dir
        self.output_dir = output_dir
        self.audit_dir = audit_dir
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.audit_dir, exist_ok=True)
        self.store = ContextStore(base_dir=base_dir)
        self.rules_engine = RulesEngine(self.store)
        self.processed_ticket_ids: Set[str] = set()

    def process_queue_file(self, queue_file_path: str, is_append: bool = False) -> Dict[str, int]:
        raw_records = self._load_queue_records(queue_file_path)
        stats = {
            "total_raw": len(raw_records),
            "processed_valid": 0,
            "quarantined": 0,
            "duplicates_skipped": 0
        }
        if not is_append:
            self._init_output_files()
            self.processed_ticket_ids.clear()

        for raw_item in raw_records:
            try:
                normalized, err = self._normalize_ticket(raw_item)
                if err:
                    self._write_quarantine(raw_item, err)
                    stats["quarantined"] += 1
                    continue

                ticket_id = normalized["ticket_id"]
                if ticket_id in self.processed_ticket_ids:
                    stats["duplicates_skipped"] += 1
                    self._log_audit(ticket_id, "VALIDATION", "Duplicate ticket skipped", "RULE_DEDUPLICATION", {"raw": raw_item})
                    continue

                self.processed_ticket_ids.add(ticket_id)
                decision = self.rules_engine.evaluate_breakdown(normalized)
                self._write_work_order(normalized, decision)
                self._write_comms_pending(normalized, decision)
                self._log_audit(
                    ticket_id=ticket_id,
                    step="RESOLUTION",
                    decision=f"Assigned replacement {decision.eligible_replacement_plate or 'NONE'} from {decision.replacement_source_hub}",
                    rule=",".join(decision.rules_applied),
                    details={
                        "sla_hours": decision.sla_hours,
                        "citations": decision.citations,
                        "audit_notes": decision.audit_notes
                    }
                )
                stats["processed_valid"] += 1
            except Exception as e:
                self._write_quarantine(raw_item, f"PIPELINE_ERROR: {str(e)}")
                stats["quarantined"] += 1

        return stats

    def _load_queue_records(self, path: str) -> List[Dict[str, Any]]:
        resolved_path = path
        if not os.path.exists(resolved_path):
            candidates = [
                os.path.join(self.base_dir, path),
                os.path.join(self.base_dir, "data", path),
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", path),
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", path),
            ]
            for c in candidates:
                if os.path.exists(c):
                    resolved_path = c
                    break
        if not os.path.exists(resolved_path):
            return []
        path = resolved_path
        records = []
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read().strip()
                if not content:
                    return []
                if content.startswith("[") or content.startswith("{"):
                    try:
                        parsed = json.loads(content)
                        if isinstance(parsed, list):
                            return parsed
                        elif isinstance(parsed, dict):
                            for key in ("records", "tickets", "data", "items", "events"):
                                if key in parsed and isinstance(parsed[key], list):
                                    return parsed[key]
                            return [parsed]
                    except json.JSONDecodeError:
                        pass
                lines = content.splitlines()
                jsonl_records = []
                for line in lines:
                    line = line.strip()
                    if line:
                        try:
                            jsonl_records.append(json.loads(line))
                        except Exception:
                            pass
                if jsonl_records:
                    return jsonl_records
                reader = csv.DictReader(content.splitlines())
                return [dict(row) for row in reader]
        except Exception:
            pass
        return records

    def _normalize_ticket(self, raw: Any) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        if not isinstance(raw, dict):
            return None, "RECORD_NOT_A_DICT"

        def get_val(keys: List[str], default=None):
            for k in keys:
                if k in raw and raw[k] is not None and str(raw[k]).strip() != "":
                    return raw[k]
                for rk, rv in raw.items():
                    if rk.lower() == k.lower() and rv is not None and str(rv).strip() != "":
                        return rv
            return default

        ticket_id = get_val(["ticket_id", "ticketId", "id", "incident_id", "breakdown_id"])
        if not ticket_id or not str(ticket_id).strip():
            return None, "MISSING_CRITICAL_FIELD: ticket_id"
        ticket_id = str(ticket_id).strip()

        vehicle_raw = get_val(["vehicle", "vehicle_reg", "reg_no", "truck_id", "plate", "registration_number"])
        if not vehicle_raw:
            return None, "MISSING_CRITICAL_FIELD: vehicle"
        canonical_plate = EntityResolver.canonicalize_plate(str(vehicle_raw))
        if not canonical_plate:
            return None, f"CORRUPTED_VEHICLE_PLATE: {vehicle_raw}"

        origin_hub = get_val(["origin_hub", "origin", "from_hub", "source_hub", "hub"])
        destination = get_val(["destination", "dest", "to_hub", "target_hub"])
        issue = get_val(["issue", "problem", "fault", "description", "breakdown_reason"])
        if not origin_hub:
            return None, "MISSING_CRITICAL_FIELD: origin_hub"
        if not destination:
            return None, "MISSING_CRITICAL_FIELD: destination"
        if not issue:
            return None, "MISSING_CRITICAL_FIELD: issue"

        raw_km = get_val(["km_from_origin_hub", "km_from_origin", "distance_km", "distance", "km"], 0)
        try:
            km_num = float(re.sub(r'[^\d\.]', '', str(raw_km)) or 0)
        except Exception:
            km_num = 0.0

        normalized = {
            "ticket_id": ticket_id,
            "created_at": str(get_val(["created_at", "timestamp", "time", "date", "reported_at"], datetime.now().isoformat())),
            "vehicle": canonical_plate,
            "driver_id": str(get_val(["driver_id", "driver", "emp_id", "driver_code"], "UNKNOWN")),
            "origin_hub": str(origin_hub).strip(),
            "destination": str(destination).strip(),
            "km_from_origin_hub": km_num,
            "issue": str(issue).strip(),
            "severity": str(get_val(["severity", "priority", "level"], "MEDIUM")).strip().upper(),
            "client": EntityResolver.canonicalize_client(str(get_val(["client", "customer", "account"], "Standard Client")))
        }
        return normalized, None

    def _init_output_files(self):
        for filename in ("work_orders.jsonl", "comms_pending.jsonl", "comms_sent.jsonl", "quarantine.jsonl"):
            filepath = os.path.join(self.output_dir, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                pass
        audit_file = os.path.join(self.audit_dir, "audit.jsonl")
        with open(audit_file, "w", encoding="utf-8") as f:
            pass

    def _write_work_order(self, ticket: Dict[str, Any], decision: DecisionResult):
        wo_id = f"WO-{ticket['ticket_id']}-01"
        wo_record = {
            "work_order_id": wo_id,
            "ticket_id": ticket["ticket_id"],
            "vehicle_reg": ticket["vehicle"],
            "created_at": ticket.get("created_at"),
            "citations": decision.citations
        }
        sanitized = PIISanitizer.sanitize_record(wo_record)
        path = os.path.join(self.output_dir, "work_orders.jsonl")
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(sanitized) + "\n")

    def _write_comms_pending(self, ticket: Dict[str, Any], decision: DecisionResult):
        client_name = ticket["client"]
        rep_plate = decision.eligible_replacement_plate or "Backup Truck En Route"
        body = (
            f"Dear {client_name} Operations Team, Vehicle {ticket['vehicle']} on trip from {ticket['origin_hub']} "
            f"to {ticket['destination']} experienced a mechanical delay ({ticket['issue']}). "
            f"Replacement vehicle {rep_plate} has been dispatched from {decision.replacement_source_hub} "
            f"under {decision.sla_hours}-hour commitment window. {decision.delivery_instructions} "
            f"For updates, contact Meridian Central Dispatch at ops@meridianfreight.example.in."
        )
        msg_record = {
            "ticket_id": ticket["ticket_id"],
            "client": client_name,
            "recipient": f"dispatch@{client_name.lower().replace(' ', '')}.example.in",
            "body": PIISanitizer.sanitize_text(body),
            "context_summary": {
                "broken_vehicle": ticket["vehicle"],
                "replacement_vehicle": rep_plate,
                "origin_hub": ticket["origin_hub"],
                "destination": ticket["destination"],
                "sla_hours": decision.sla_hours,
                "rules_applied": decision.rules_applied
            },
            "citations": decision.citations,
            "status": "PENDING_APPROVAL"
        }
        sanitized = PIISanitizer.sanitize_record(msg_record)
        path = os.path.join(self.output_dir, "comms_pending.jsonl")
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(sanitized) + "\n")

    def _write_quarantine(self, raw_record: Any, reason: str):
        quarantine_rec = {
            "quarantined_at": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
            "raw_record": PIISanitizer.sanitize_record(raw_record)
        }
        path = os.path.join(self.output_dir, "quarantine.jsonl")
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(quarantine_rec) + "\n")

    def _log_audit(self, ticket_id: str, step: str, decision: str, rule: str, details: Dict[str, Any]):
        audit_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "ticket_id": ticket_id,
            "step": step,
            "decision": decision,
            "rule": rule,
            "details": PIISanitizer.sanitize_record(details)
        }
        path = os.path.join(self.audit_dir, "audit.jsonl")
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(audit_entry) + "\n")
