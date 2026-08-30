import re

with open("src/pipeline.py", "r", encoding="utf-8") as f:
    code = f.read()

code = code.replace('"Duplicate ticket skipped"', '"SKIPPED_ALREADY_PROCESSED"')

with open("src/pipeline.py", "w", encoding="utf-8") as f:
    f.write(code)
