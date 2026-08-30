import re, json, os

with open("app.py", "r", encoding="utf-8") as f:
    app_code = f.read()

upload_code = '''
@app.post("/api/upload-queue")
@graceful_api("Upload Queue")
async def upload_queue(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename)[1] or ".json"
    target_path = os.path.join(BASE_DIR, f"tickets{ext}")
    content = await file.read()
    with open(target_path, "wb") as f:
        f.write(content)
        
    # Read the JSON to validate duplicates and return count
    try:
        data = json.loads(content.decode("utf-8"))
        record_count = len(data)
        
        # Check for self-overlap (duplicates inside the file)
        ticket_ids = [str(d.get("ticket_id", d.get("id", ""))) for d in data if isinstance(d, dict)]
        unique_ids = set([tid for tid in ticket_ids if tid])
        
        if len(unique_ids) < len(ticket_ids) * 0.8:  # arbitrarily 20% duplicate rate
            # Log warning
            audit_path = os.path.join(AUDIT_DIR, "audit.jsonl")
            with open(audit_path, "a", encoding="utf-8") as af:
                import datetime
                af.write(json.dumps({
                    "timestamp": datetime.datetime.now().isoformat(),
                    "ticket_id": "SYSTEM",
                    "step": "UPLOAD",
                    "decision": "WARNING_HIGH_DUPLICATION",
                    "rule": "UPLOAD_VALIDATION",
                    "details": {"record_count": record_count, "unique_ids": len(unique_ids)}
                }) + "\\n")
    except:
        record_count = 0
        
    return {"status": "SUCCESS", "parsed_record_count": record_count, "stats": {"processed_valid": 0, "quarantined": 0}}
'''
app_code = re.sub(r'@app\.post\("/api/upload-queue"\).*?return \{"status": "SUCCESS", "stats": stats\}', upload_code.strip(), app_code, flags=re.DOTALL)

with open("app.py", "w", encoding="utf-8") as f:
    f.write(app_code)
