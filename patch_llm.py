import re

with open("src/llm_resolver.py", "r", encoding="utf-8") as f:
    code = f.read()

if "from .pii_sanitizer import PIISanitizer" not in code:
    code = code.replace("from typing import Optional", "from .pii_sanitizer import PIISanitizer\nfrom typing import Optional")

resolve_old = '''    def resolve(self, prompt: str, context: str = "") -> Optional[str]:
        """
        Core method. Returns string response or None.
        None = LLM unavailable or failed +' caller uses deterministic fallback.
        """
        if not self.enabled:
            return None
        full_prompt = f"{context}\\n\\n{prompt}".strip() if context else prompt
        try:
            if self.provider == "groq":'''

resolve_new = '''    def resolve(self, prompt: str, context: str = "") -> Optional[str]:
        """
        Core method. Returns string response or None.
        None = LLM unavailable or failed +' caller uses deterministic fallback.
        """
        if not self.enabled:
            return None
        full_prompt = f"{context}\\n\\n{prompt}".strip() if context else prompt
        
        # [BUG 4 FIX] PII guard before outbound LLM calls
        full_prompt = PIISanitizer.sanitize_text(full_prompt)
        
        try:
            if self.provider == "groq":'''
            
code = code.replace(resolve_old, resolve_new)

with open("src/llm_resolver.py", "w", encoding="utf-8") as f:
    f.write(code)
