import re

with open("src/rules_engine.py", "r", encoding="utf-8") as f:
    code = f.read()

target = 'if self.store.get_guddu_jugaad_active(plate, incident_date):\n                continue'
replacement = target + '''
            if self.store.is_vehicle_currently_assigned(plate, res.ticket_time):
                continue
            
            # Note on RULE_GROUNDED_OVERDUE_SERVICE: Intentionally deferred.
            # Fleet master and maintenance logs currently lack a 'next_service_date' or 'due' field
            # to deterministically compute >30 days overdue. Cannot enforce without hallucinating data.'''

code = code.replace(target, replacement)

with open("src/rules_engine.py", "w", encoding="utf-8") as f:
    f.write(code)
