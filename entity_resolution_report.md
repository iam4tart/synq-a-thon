# Meridian Freight: Entity Resolution & Context Ingestion Report
**Synq AI Forward Deployment Challenge — Hour 3 Checkpoint**

---

## 1. Executive Summary
This report documents the ingestion, entity resolution, conflict resolution, and personal data (PII) sanitization architecture implemented for Meridian Freight Private Limited.

---

## 2. Ingress PII Sanitization & Security Shield
To comply with the non-negotiable security hard gate (any leaked raw PII caps the score at 50/100), an automated regex-based PII scrubber was deployed at the ingestion boundary:
* **Driver Phone Numbers** (e.g. `+91 93118 40522`, `+91 8361473242`): Redacted to `[PHONE_REDACTED]`.
* **Aadhaar Numbers** (e.g. `6515 3369 7284`): Redacted to `[AADHAAR_REDACTED]`.
* **Driving License Numbers** (e.g. `HR16 20128663605`, `DL-0420110023456`): Redacted to `[DL_REDACTED]`.

---

## 3. Entity Resolution & Canonicalization

### A. Vehicle Registration Plates
* **Input Formats**: Varied formats across systems (`UP-40-IM-3144`, `up86cm7252`, `DL-64-IB-1058`, `CH40IK6238`, `HR 16 SP 9238`).
* **Normalization Engine**: Strips whitespace, hyphens, and casing to produce canonical uppercase alphanumeric strings (e.g., `UP40IM3144`, `UP86CM7252`).
* **Validation & Corrupt Plate Handling**: Non-standard strings (e.g., `hr??unknown`) are caught and diverted to quarantine.

### B. Client Entity Mapping & Precedence
* **Client Aliases**: Variations such as `Shakti`, `shakticement.example.in`, `Apex`, `orion pharma` are mapped to canonical brand identities.
* **Conflict Precedence Hierarchy**:
  1. *Level 1 (Highest Precedence)*: Verified email confirmations and operating interview agreements (e.g., **Shakti Cement 36-hour operational window** overrides the 48-hour paper contract).
  2. *Level 2*: Active maintenance logs (recent repairs within 7–30 days override static active status).
  3. *Level 3*: Static fleet inventory and contract text.

---

## 4. Dispatcher Operating Rules Codification (*Rajender Pal Yadav*)

| Rule ID | Domain Constraint | Citation |
| :--- | :--- | :--- |
| `RULE_NCR_BS4_WINTER` | Oct–Feb: No BS4 vehicle allowed on Delhi NCR routes (BS6 mandatory). | `dispatcher_interview.txt:L15-L25` |
| `RULE_HILL_ROADS` | Rudrapur/Nainital hill routes require engine heater + 0 brake repairs in 30 days. | `dispatcher_interview.txt:L27-L35` |
| `RULE_SHAKTI_SLA_36H` | Shakti Cement dispatches run on a 36-hour operational SLA. | `dispatcher_interview.txt:L37-L45` |
| `RULE_VERTEX_6PM_CUTOFF` | Vertex Ludhiana deliveries after 18:00 held for 08:00 AM next day. | `dispatcher_interview.txt:L47-L55` |
| `RULE_APEX_PLATE_ROTATION` | Vehicles with recent breakdowns rotated away from Apex runs. | `dispatcher_interview.txt:L57-L63` |
| `RULE_ORION_PHARMA` | Orion Pharma requires refrigerated transport + 2020+ vehicle year. | `dispatcher_interview.txt:L65-L70` |
| `RULE_MONSOON_EAST_BUFFER` | Jul–Sep: Routes east of Lucknow receive +20% duration buffer. | `dispatcher_interview.txt:L72-L80` |
| `RULE_50KM_ORIGIN_HUB` | Breakdowns $\le 50$ km from origin hub source replacement from origin hub. | `dispatcher_interview.txt:L82-L95` |
| `RULE_GROUNDED_OVERDUE_SERVICE` | Vehicles $> 30$ days overdue for scheduled maintenance are grounded. | `dispatcher_interview.txt:L90-L95` |
| `RULE_GUDDU_TEMPORARY_PATCH` | Guddu's temporary roadside patch expires in 7 days; vehicle restricted to home region. | `dispatcher_interview.txt:L97-L105` |

---

## 5. Verification & Test Summary
* **Unit Tests Executed**: 15 tests passed (`test_pii.py`, `test_entity_resolution.py`, `test_context_store.py`, `test_rules.py`, `test_surprise_file.py`).
* **Idempotency**: Back-to-back queue executions produce bitwise identical outputs with zero duplicate work orders or communications.
