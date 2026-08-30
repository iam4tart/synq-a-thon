import re
from typing import Any, Dict, List, Union

RE_DL = re.compile(
    r'\b[A-Z]{2}[-\s]?\d{2}[-\s]?(?:19|20)?\d{2}[-\s]?\d{7,11}\b|\b[A-Z]{2}\d{13,15}\b',
    re.IGNORECASE
)
RE_AADHAAR = re.compile(
    r'\b[2-9]\d{3}[-\s]\d{4}[-\s]\d{4}\b|\b[2-9]\d{11}\b'
)
RE_PHONE = re.compile(
    r'(?:\+91[-\s]?)?[6-9]\d{4}[-\s]?\d{5}|\b[6-9]\d{9}\b|\b0[6-9]\d{9}\b'
)

REPLACEMENT_PHONE = "[PHONE_REDACTED]"
REPLACEMENT_AADHAAR = "[AADHAAR_REDACTED]"
REPLACEMENT_DL = "[DL_REDACTED]"


class PIISanitizer:

    @classmethod
    def sanitize_text(cls, text: str) -> str:
        if not text or not isinstance(text, str):
            return text
        text = RE_DL.sub(REPLACEMENT_DL, text)
        text = RE_AADHAAR.sub(REPLACEMENT_AADHAAR, text)
        text = RE_PHONE.sub(REPLACEMENT_PHONE, text)
        return text

    @classmethod
    def sanitize_record(cls, record: Union[Dict[str, Any], List[Any], str, Any]) -> Any:
        if isinstance(record, str):
            return cls.sanitize_text(record)
        elif isinstance(record, dict):
            sanitized = {}
            for key, val in record.items():
                key_lower = str(key).lower()
                if key_lower in ('phone', 'phone_number', 'mobile', 'contact_no'):
                    sanitized[key] = REPLACEMENT_PHONE
                elif key_lower in ('aadhaar', 'aadhaar_number', 'national_id', 'id_number'):
                    sanitized[key] = REPLACEMENT_AADHAAR
                elif key_lower in ('dl_number', 'driving_license', 'license_number'):
                    sanitized[key] = REPLACEMENT_DL
                else:
                    sanitized[key] = cls.sanitize_record(val)
            return sanitized
        elif isinstance(record, list):
            return [cls.sanitize_record(item) for item in record]
        return record

    @classmethod
    def contains_raw_pii(cls, text: str) -> bool:
        if not isinstance(text, str):
            text = str(text)
        phone_matches = RE_PHONE.findall(text)
        for match in phone_matches:
            cleaned = re.sub(r'[-\s\+]', '', match)
            if cleaned.startswith('91') and len(cleaned) == 12:
                cleaned = cleaned[2:]
            if len(cleaned) == 10 and cleaned[0] in '6789':
                return True
        if RE_AADHAAR.search(text) or RE_DL.search(text):
            return True
        return False
