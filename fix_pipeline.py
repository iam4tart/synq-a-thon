import re

with open('src/pipeline.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('        def _load_processed_state(self):', '    def _load_processed_state(self):')

with open('src/pipeline.py', 'w', encoding='utf-8') as f:
    f.write(content)
