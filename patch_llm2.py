import re

with open("src/llm_resolver.py", "r", encoding="utf-8") as f:
    code = f.read()

target = 'full_prompt = f"{context}\\n\\n{prompt}".strip() if context else prompt'
replacement = target + '\\n        \\n        # [BUG 4 FIX] PII guard before outbound LLM calls\\n        full_prompt = PIISanitizer.sanitize_text(full_prompt)'

code = code.replace(target, replacement)

with open("src/llm_resolver.py", "w", encoding="utf-8") as f:
    f.write(code)
