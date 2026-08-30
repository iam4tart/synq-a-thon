import re
with open("app.py", "r", encoding="utf-8") as f:
    app_code = f.read()

old_toast = 'showToast(Ingested :  resolved,  alerts.);'
new_toast = 'showToast(Ingested :  total records parsed.);'

app_code = app_code.replace(old_toast, new_toast)

with open("app.py", "w", encoding="utf-8") as f:
    f.write(app_code)
