"""
Grounded Query & Citation Interface
Meridian Freight Automation

Query flow:
  1. Fast path: deterministic keyword matching for known rules (zero latency, zero cost)
  2. LLM path:  for queries that don't hit a keyword, LLM answers strictly from corpus text
  3. Safe degradation: INSUFFICIENT DATA if LLM is off or corpus has no grounding
"""

from typing import Dict, Any, Optional
from datetime import date
from .context_store import ContextStore
from .entity_resolution import EntityResolver
from .pii_sanitizer import PIISanitizer


class GroundedQueryInterface:
    """Answers operational questions strictly grounded in the ingested corpus."""

    def __init__(self, context_store: ContextStore, llm=None):
        self.store = context_store
        self.llm = llm  # LLMResolver instance or None

    def _corpus_snapshot(self) -> str:
        """Builds a compact text snapshot of the loaded corpus for LLM grounding."""
        parts = []
        for rule, citation in self.store.interview_citations.items():
            parts.append(f"[{rule}] {citation}")
        for client, agreement in self.store.client_agreements.items():
            parts.append(f"[CLIENT_AGREEMENT:{client}] {agreement}")
        return "\n".join(parts)

    def query(self, question: str) -> Dict[str, Any]:
        q_lower = question.lower()

        # Fast path: Vehicle lookup
        for plate, v in self.store.vehicles.items():
            if plate.lower() in q_lower or v.get("raw_plate", "").lower() in q_lower:
                return {
                    "answer": f"Vehicle {plate} ({v.get('model')}, Year {v.get('year')}) is {v.get('bs_stage')} rated, at {v.get('home_hub')} Hub, status: {v.get('status')}.",
                    "citations": [f"fleet_master.csv:plate_{plate}"],
                    "confidence": "HIGH"
                }

        # LLM path: question not matched deterministically, ask LLM grounded on corpus
        if self.llm is not None:
            corpus = self._corpus_snapshot()
            result = self.llm.answer_grounded_query(
                question,
                corpus,
                citation_map=self.store.interview_citations
            )
            return result

        # Safe degradation
        return {
            "answer": "INSUFFICIENT DATA: No grounded source records found in corpus to support an answer.",
            "citations": [],
            "confidence": "INSUFFICIENT_DATA"
        }
