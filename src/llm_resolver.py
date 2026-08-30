"""
LLM Resolver - Ambiguity Layer
Meridian Freight Automation

Providers:
  groq        : Llama 3.1 8B via Groq (DEFAULT - fastest, free)
  openrouter  : Mistral Small via OpenRouter (secondary)
  huggingface : Mistral-7B via HuggingFace Inference API (tertiary)

Configure via .env or environment variables:
  LLM_PROVIDER=groq
  GROQ_API_KEY=gsk_...
  OPENROUTER_API_KEY=sk-or-v1-...
  HF_API_KEY=hf_...
"""

import os
import json
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger("meridian-llm")

# Load .env if present (no hard dependency on python-dotenv)
def _load_dotenv():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())

_load_dotenv()

SYSTEM_PROMPT = (
    "You are a strict data extraction assistant for a freight logistics company. "
    "RULES: "
    "1. Answer ONLY using the facts and documents provided to you in the user message. "
    "2. If the answer is not clearly stated in the provided context, respond with exactly: INSUFFICIENT DATA "
    "3. Never infer, guess, or hallucinate. Never add information not present in the context. "
    "4. When extracting structured data, respond ONLY with a valid JSON object. "
    "5. Keep answers concise and precise."
)


class LLMResolver:
    """
    Thin LLM abstraction layer for ambiguity resolution.
    Sits upstream of the deterministic pipeline.
    Returns None gracefully on any failure — deterministic fallbacks always run.
    """

    def __init__(self, provider: Optional[str] = None, api_key: Optional[str] = None):
        self.provider = (provider or os.getenv("LLM_PROVIDER", "groq")).lower()
        self.api_key = api_key or self._resolve_key()
        self.enabled = bool(self.api_key)
        if not self.enabled:
            logger.warning(
                f"[LLM] No API key for '{self.provider}'. LLM disabled — deterministic fallbacks active."
            )
        else:
            logger.info(f"[LLM] Provider: {self.provider} | Status: ACTIVE")

    def _resolve_key(self) -> Optional[str]:
        key_map = {
            "groq": "GROQ_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
            "huggingface": "HF_API_KEY",
        }
        env_var = key_map.get(self.provider)
        return os.getenv(env_var) if env_var else None

    def resolve(self, prompt: str, context: str = "") -> Optional[str]:
        """
        Core method. Returns string response or None.
        None = LLM unavailable or failed → caller uses deterministic fallback.
        """
        if not self.enabled:
            return None
        full_prompt = f"{context}\n\n{prompt}".strip() if context else prompt
        try:
            if self.provider == "groq":
                return self._call_groq(full_prompt)
            elif self.provider == "openrouter":
                return self._call_openrouter(full_prompt)
            elif self.provider == "huggingface":
                return self._call_huggingface(full_prompt)
        except Exception as e:
            logger.warning(f"[LLM] {self.provider} call failed: {e}. Deterministic fallback active.")
        return None

    def resolve_json(self, prompt: str, context: str = "") -> Optional[Dict[str, Any]]:
        """Returns a parsed JSON dict or None on failure."""
        raw = self.resolve(prompt, context)
        if not raw:
            return None
        try:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(raw[start:end])
        except Exception:
            pass
        return None

    # ── Provider Implementations ───────────────────────────────────────────────

    def _call_groq(self, prompt: str) -> Optional[str]:
        from groq import Groq
        client = Groq(api_key=self.api_key)
        response = client.chat.completions.create(
            model="qwen/qwen3.8-27b",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0,
            max_tokens=512,
        )
        return response.choices[0].message.content.strip()

    def _call_openrouter(self, prompt: str) -> Optional[str]:
        import requests
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "HTTP-Referer": "http://localhost:8000",
                "X-Title": "Meridian Freight Ops",
            },
            json={
                "model": "mistralai/mistral-small-2603",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 512,
                "temperature": 0.0,
            },
            timeout=30
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()

    def _call_huggingface(self, prompt: str) -> Optional[str]:
        import requests
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {
            "inputs": f"{SYSTEM_PROMPT}\n\n{prompt}",
            "parameters": {"max_new_tokens": 512, "temperature": 0.01, "return_full_text": False}
        }
        response = requests.post(
            "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.3",
            headers=headers, json=payload, timeout=30
        )
        response.raise_for_status()
        result = response.json()
        if isinstance(result, list) and result:
            return result[0].get("generated_text", "").strip()
        return None

    # ── High-Level Task Methods ────────────────────────────────────────────────

    def resolve_client(self, raw_name: str, known_clients: List[str]) -> Optional[str]:
        """
        Resolves ambiguous client name to canonical.
        Returns None if uncertain → deterministic fuzzy match runs.
        """
        prompt = (
            f"Known clients: {known_clients}\n"
            f"Raw input: \"{raw_name}\"\n"
            f"Return a JSON object with the best match: {{\"client\": \"<canonical name>\"}}\n"
            f"If no confident match, return: {{\"client\": null}}\n"
            f"Respond ONLY with JSON."
        )
        result = self.resolve_json(prompt)
        if result and result.get("client") in known_clients:
            return result["client"]
        return None

    def resolve_column_mapping(self, headers: List[str], known_schema: List[str]) -> Optional[Dict[str, str]]:
        """
        Maps unknown surprise-file column headers to canonical schema fields.
        """
        prompt = (
            f"Canonical field names: {known_schema}\n"
            f"Unknown file headers: {headers}\n"
            f"Return a JSON mapping of unknown_header -> canonical_field.\n"
            f"Only include confident mappings. Respond ONLY with JSON."
        )
        return self.resolve_json(prompt)

    def answer_grounded_query(self, question: str, corpus_text: str) -> Dict[str, Any]:
        """
        Answers an operational question strictly grounded in corpus.
        If not found, returns INSUFFICIENT DATA — never guesses.
        """
        prompt = (
            f"Question: {question}\n\n"
            f"Answer strictly from this corpus only. "
            f"If not found, respond: INSUFFICIENT DATA"
        )
        raw = self.resolve(prompt, context=f"CORPUS:\n{corpus_text[:4000]}")
        if not raw:
            return {"answer": "INSUFFICIENT DATA", "citations": [], "confidence": "INSUFFICIENT_DATA"}
        is_insufficient = "INSUFFICIENT DATA" in raw.upper()
        return {
            "answer": raw,
            "citations": ["LLM-grounded from loaded corpus"],
            "confidence": "INSUFFICIENT_DATA" if is_insufficient else "LLM_GROUNDED"
        }
