import re
import difflib
from typing import Optional, List, Dict, Set

NCR_HUBS = {"delhi", "gurgaon", "faridabad", "noida", "ghaziabad", "kundli"}
HILL_DESTINATIONS = {"rudrapur", "nainital", "almora", "haldwani", "kathgodam"}
EAST_OF_LUCKNOW = {
    "lucknow", "varanasi", "patna", "gorakhpur", "muzaffarpur",
    "kolkata", "ranchi", "siliguri", "guwahati", "gaya", "darbhanga"
}

CANONICAL_CLIENTS = ["Shakti Cement", "Apex Chemicals", "Orion Pharma", "Vertex Retail"]


class EntityResolver:

    @staticmethod
    def canonicalize_plate(plate_str: Optional[str], known_fleet: Optional[Set[str]] = None) -> Optional[str]:
        if not plate_str or not isinstance(plate_str, str):
            return None
        cleaned = re.sub(r'[\s\-_\.]', '', plate_str).upper()
        if '?' in cleaned or len(cleaned) < 6:
            return None

        if re.match(r'^[A-Z]{2}\d{1,2}[A-Z]{1,3}\d{4}$', cleaned) or re.match(r'^[A-Z0-9]{8,11}$', cleaned):
            if known_fleet and cleaned in known_fleet:
                return cleaned
            if not known_fleet:
                return cleaned

        if known_fleet:
            close_matches = difflib.get_close_matches(cleaned, list(known_fleet), n=1, cutoff=0.88)
            if close_matches:
                return close_matches[0]

        if re.match(r'^[A-Z]{2}\d{1,2}[A-Z]{1,3}\d{4}$', cleaned) or re.match(r'^[A-Z0-9]{8,11}$', cleaned):
            return cleaned

        return None

    @staticmethod
    def canonicalize_client(client_str: Optional[str]) -> str:
        if not client_str or not isinstance(client_str, str):
            return "Standard Client"
        cleaned = client_str.strip()
        matches = difflib.get_close_matches(cleaned, CANONICAL_CLIENTS, n=1, cutoff=0.35)
        if matches:
            return matches[0]
        cleaned_lower = cleaned.lower()
        for canonical in CANONICAL_CLIENTS:
            canonical_tokens = canonical.lower().split()
            if any(token in cleaned_lower for token in canonical_tokens):
                return canonical
        return cleaned

    @staticmethod
    def canonicalize_hub(hub_str: Optional[str], known_hubs: Optional[List[str]] = None) -> str:
        if not hub_str or not isinstance(hub_str, str):
            return "Gurgaon"
        cleaned = hub_str.strip()
        if known_hubs:
            matches = difflib.get_close_matches(cleaned, known_hubs, n=1, cutoff=0.6)
            if matches:
                return matches[0]
        return cleaned

    @staticmethod
    def is_ncr_route(origin: Optional[str], destination: Optional[str]) -> bool:
        orig = str(origin).strip().lower() if origin else ""
        dest = str(destination).strip().lower() if destination else ""
        return any(h in orig for h in NCR_HUBS) or any(h in dest for h in NCR_HUBS)

    @staticmethod
    def is_hill_route(origin: Optional[str], destination: Optional[str]) -> bool:
        orig = str(origin).strip().lower() if origin else ""
        dest = str(destination).strip().lower() if destination else ""
        return any(h in orig for h in HILL_DESTINATIONS) or any(h in dest for h in HILL_DESTINATIONS)

    @staticmethod
    def is_east_of_lucknow_route(origin: Optional[str], destination: Optional[str]) -> bool:
        orig = str(origin).strip().lower() if origin else ""
        dest = str(destination).strip().lower() if destination else ""
        return any(h in orig for h in EAST_OF_LUCKNOW) or any(h in dest for h in EAST_OF_LUCKNOW)
