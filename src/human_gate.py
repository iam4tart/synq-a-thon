"""
Human-in-the-loop Approval Gate
Meridian Freight Breakdown Automation

Purpose:
Reviews drafted communications in outputs/comms_pending.jsonl
and transitions approved notifications to outputs/comms_sent.jsonl.
Strictly ensures zero personal data is present in sent messages.
"""

import os
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from .pii_sanitizer import PIISanitizer


class HumanApprovalGate:
    """Manages the human review and dispatch of pending client messages."""

    def __init__(self, output_dir: str = "solutions/outputs"):
        self.output_dir = output_dir
        self.pending_path = os.path.join(self.output_dir, "comms_pending.jsonl")
        self.sent_path = os.path.join(self.output_dir, "comms_sent.jsonl")

    def get_pending_messages(self) -> List[Dict[str, Any]]:
        """Returns all messages currently pending human approval."""
        if not os.path.exists(self.pending_path):
            return []
        
        messages = []
        with open(self.pending_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    messages.append(json.loads(line.strip()))
        return messages

    def approve(self, approver_name: str = "Ops_Manager", ticket_id: Optional[str] = None) -> int:
        """Approves and dispatches messages to outputs/comms_sent.jsonl. Removes from pending."""
        pending = self.get_pending_messages()
        if not pending:
            return 0

        # Read existing sent message IDs to prevent duplicates
        existing_sent_ids = set()
        if os.path.exists(self.sent_path):
            with open(self.sent_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        rec = json.loads(line.strip())
                        existing_sent_ids.add(rec.get("ticket_id"))

        approved_count = 0
        remaining_pending = []
        
        with open(self.sent_path, "a", encoding="utf-8") as f_sent:
            for msg in pending:
                t_id = msg.get("ticket_id")
                
                # If specific ticket requested and this isn't it, keep it in pending
                if ticket_id and t_id != ticket_id:
                    remaining_pending.append(msg)
                    continue

                if t_id in existing_sent_ids:
                    continue  # Already sent

                sent_record = {
                    "message_id": f"MSG-{t_id}",
                    "ticket_id": t_id,
                    "recipient": msg.get("recipient"),
                    "body": PIISanitizer.sanitize_text(msg.get("body", "")),
                    "approved_by": approver_name,
                    "sent_at": datetime.now(timezone.utc).isoformat()
                }

                # Final Egress PII assertion
                assert not PIISanitizer.contains_raw_pii(sent_record["body"]), "Egress PII Violation!"

                f_sent.write(json.dumps(sent_record) + "\n")
                existing_sent_ids.add(t_id)
                approved_count += 1
                
        # Overwrite pending file to remove approved items
        with open(self.pending_path, "w", encoding="utf-8") as f_pending:
            for msg in remaining_pending:
                f_pending.write(json.dumps(msg) + "\n")

        return approved_count
