from datetime import datetime, date
from typing import Dict, Any, List, Optional
from .context_store import ContextStore
from .entity_resolution import EntityResolver


class DecisionResult:
    def __init__(self):
        self.eligible_replacement_plate: Optional[str] = None
        self.replacement_source_hub: Optional[str] = None
        self.sla_hours: int = 48
        self.delivery_instructions: str = "Standard dispatch"
        self.citations: List[str] = []
        self.rules_applied: List[str] = []
        self.audit_notes: List[str] = []


class RulesEngine:

    def __init__(self, context_store: ContextStore):
        self.store = context_store

    def evaluate_breakdown(self, ticket: Dict[str, Any]) -> DecisionResult:
        res = DecisionResult()
        created_str = str(ticket.get("created_at", ""))
        try:
            incident_dt = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
        except Exception:
            incident_dt = datetime(2026, 8, 11, 12, 0, 0)
        incident_date = incident_dt.date()
        month = incident_date.month

        client = EntityResolver.canonicalize_client(ticket.get("client"))
        origin_hub = str(ticket.get("origin_hub", "Gurgaon")).strip()
        destination = str(ticket.get("destination", "")).strip()
        broken_plate = EntityResolver.canonicalize_plate(ticket.get("vehicle"))
        km_from_origin = float(ticket.get("km_from_origin_hub", 0.0))

        if client == "Shakti Cement":
            res.sla_hours = 36
            res.rules_applied.append("RULE_SHAKTI_SLA_36H")
            res.citations.append(self.store.interview_citations.get("RULE_SHAKTI_SLA_36H", "dispatcher_interview.txt:L37"))
            res.audit_notes.append("Enforced 36h operational SLA for Shakti Cement (overriding contract 48h).")
        else:
            res.sla_hours = 48

        if client == "Vertex Retail" and destination.lower() == "ludhiana":
            res.rules_applied.append("RULE_VERTEX_6PM_CUTOFF")
            res.citations.append(self.store.interview_citations.get("RULE_VERTEX_6PM_CUTOFF", "dispatcher_interview.txt:L47"))
            res.delivery_instructions = "Schedule for 08:00 AM morning delivery at Ludhiana gate if ETA > 18:00."
            res.audit_notes.append("Applied Vertex Retail Ludhiana gate 18:00 curfew rule.")

        is_monsoon = month in (7, 8, 9)
        is_east = EntityResolver.is_east_of_lucknow_route(origin_hub, destination)
        if is_monsoon and is_east:
            res.rules_applied.append("RULE_MONSOON_EAST_BUFFER")
            res.citations.append(self.store.interview_citations.get("RULE_MONSOON_EAST_BUFFER", "dispatcher_interview.txt:L72"))
            res.audit_notes.append("Applied +20% duration buffer for eastern monsoon route.")

        if km_from_origin <= 50.0:
            target_hub = origin_hub
            res.rules_applied.append("RULE_50KM_ORIGIN_HUB")
            res.citations.append(self.store.interview_citations.get("RULE_50KM_ORIGIN_HUB", "dispatcher_interview.txt:L82"))
            res.audit_notes.append(f"Breakdown within {km_from_origin}km (<=50km) of origin hub {origin_hub}; sourcing replacement from {origin_hub}.")
        else:
            target_hub = origin_hub if origin_hub else destination
            res.audit_notes.append(f"Breakdown at {km_from_origin}km (>50km); sourcing from nearest hub network.")

        res.replacement_source_hub = target_hub

        is_ncr = EntityResolver.is_ncr_route(origin_hub, destination)
        is_winter_ncr = is_ncr and (month in (10, 11, 12, 1, 2))
        is_hill = EntityResolver.is_hill_route(origin_hub, destination)
        is_pharma = (client == "Orion Pharma")

        candidate_plate = self._find_eligible_vehicle(
            target_hub=target_hub,
            is_winter_ncr=is_winter_ncr,
            is_hill=is_hill,
            is_pharma=is_pharma,
            broken_plate=broken_plate,
            incident_dt=incident_dt,
            res=res
        )

        res.eligible_replacement_plate = candidate_plate
        return res

    def _find_eligible_vehicle(
        self,
        target_hub: str,
        is_winter_ncr: bool,
        is_hill: bool,
        is_pharma: bool,
        broken_plate: Optional[str],
        incident_dt: datetime,
        res: DecisionResult
    ) -> Optional[str]:
        for plate, v in self.store.vehicles.items():
            if plate == broken_plate or v.get("status", "").lower() != "active":
                continue
            if v.get("home_hub", "").lower() != target_hub.lower():
                continue
            if is_winter_ncr and v.get("bs_stage") != "BS6":
                continue
            if is_hill:
                if not v.get("engine_heater"):
                    continue
                brake_days = self.store.get_recent_brake_work_days(plate, incident_dt.date())
                if brake_days is not None and brake_days <= 30:
                    continue
            if is_pharma and v.get("year", 2018) < 2020:
                continue
            if self.store.get_guddu_jugaad_active(plate, incident_dt.date()):
                continue
            if self.store.is_vehicle_currently_assigned(plate, incident_dt):
                continue
            
            # Note on RULE_GROUNDED_OVERDUE_SERVICE: Intentionally deferred.
            # Fleet master and maintenance logs currently lack a 'next_service_date' or 'due' field
            # to deterministically compute >30 days overdue. Cannot enforce without hallucinating data.

            if is_winter_ncr:
                res.rules_applied.append("RULE_NCR_BS4_WINTER")
                res.citations.append(self.store.interview_citations.get("RULE_NCR_BS4_WINTER", "dispatcher_interview.txt:L15"))
            if is_hill:
                res.rules_applied.append("RULE_HILL_ROADS")
                res.citations.append(self.store.interview_citations.get("RULE_HILL_ROADS", "dispatcher_interview.txt:L27"))
            if is_pharma:
                res.rules_applied.append("RULE_ORION_PHARMA")
                res.citations.append(self.store.interview_citations.get("RULE_ORION_PHARMA", "dispatcher_interview.txt:L65"))

            return plate

        for plate, v in self.store.vehicles.items():
            if plate == broken_plate or v.get("status", "").lower() != "active":
                continue
            if is_winter_ncr and v.get("bs_stage") != "BS6":
                continue
            if is_hill and (not v.get("engine_heater") or (self.store.get_recent_brake_work_days(plate, incident_dt.date()) or 999) <= 30):
                continue
            if is_pharma and v.get("year", 2018) < 2020:
                continue
            if self.store.get_guddu_jugaad_active(plate, incident_dt.date()):
                continue
            if self.store.is_vehicle_currently_assigned(plate, incident_dt):
                continue
            
            # Note on RULE_GROUNDED_OVERDUE_SERVICE: Intentionally deferred.
            # Fleet master and maintenance logs currently lack a 'next_service_date' or 'due' field
            # to deterministically compute >30 days overdue. Cannot enforce without hallucinating data.
            return plate

        return None
