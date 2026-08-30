# Meridian Freight: Autonomous Breakdown-to-Resolution Pipeline

[![Tests](https://img.shields.io/badge/tests-16%20passed-brightgreen.svg)]()
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-teal.svg)]()
[![Zero--LLM](https://img.shields.io/badge/architecture-zero--hallucination%20heuristic-orange.svg)]()

Production-grade, offline-capable breakdown automation and human-in-the-loop dispatch system built for Meridian Freight operations.

---

## Key Features

1. **Strict Zero-Leakage PII Redaction**
   - Immediate redaction of Driver Aadhaar, Indian Driving Licenses, and 10-digit mobile numbers at ingestion.
   - Hard assertion checks on all egress communication files (comms_sent.jsonl).

2. **Deterministic Entity Resolution & Normalization**
   - High-tolerance fuzzy matching for client names and vehicle registrations.
   - Geographic OCR correction (e.g., HR 55-0-1234 -> HR55O1234).

3. **Multi-Format Surprise File Tolerance**
   - Dynamic auto-detection for JSON, JSONL, and CSV formats.
   - Robust alias mapping (incident_id -> 	icket_id, cust_name -> client, etc.).

4. **100% Idempotent Processing**
   - Bitwise identical outputs on back-to-back runs (--verify-idempotency).
   - Duplicate ticket isolation without crashes or dropped records.

5. **Human Approval Gate**
   - Isolates drafted communications in outputs/comms_pending.jsonl until dispatcher sign-off.
   - Dispatches approved notifications into outputs/comms_sent.jsonl.

6. **Interactive Real-Time Dashboard**
   - Lightweight, production-styled FastAPI + HTML/JS operational UI with live metrics and inline knowledge Q&A.

---

## Quickstart

### 1. Installation
`ash
pip install -r requirements.txt
`

### 2. Run Test Suite
`ash
pytest tests/ -v
`

### 3. Process Breakdown Queue (CLI)
`ash
# Process default queue (tickets.json)
python run.py --process-queue

# Process queue and approve pending client communications
python run.py --process-queue --approve-comms

# Verify bitwise idempotency
python run.py --verify-idempotency
`

### 4. Launch Live Operations Web Dashboard
`ash
python run.py --web
# Open http://127.0.0.1:8000 in your browser
`

---

## Repository Structure

`
solutions/
├── data/                       # Ingested datasets (fleet, drivers, tickets, logs)
│   ├── tickets.json
│   ├── fleet_master.csv
│   ├── drivers_roster.csv
│   ├── maintenance_log.xlsx
│   ├── meridian_trips.csv
│   ├── dispatcher_interview.txt
│   └── emails/
├── src/                        # Core pipeline modules
│   ├── pii_sanitizer.py        # Regex & contextual masking engine
│   ├── entity_resolution.py    # Plate & client name fuzzy resolution
│   ├── context_store.py        # Reference corpus & transcript parser
│   ├── rules_engine.py         # Deterministic routing & constraint solver
│   ├── human_gate.py           # Approvals & dispatch gate
│   ├── pipeline.py             # 7-step adaptive ingestion pipeline
│   └── query_interface.py     # Grounded Q&A engine with citations
├── tests/                      # Unit & integration tests (16 passing)
├── outputs/                    # Standardized output JSONL ledgers
│   ├── work_orders.jsonl
│   ├── comms_pending.jsonl
│   ├── comms_sent.jsonl
│   └── quarantine.jsonl
├── audit/                      # Compliance audit trail
│   └── audit.jsonl
├── app.py                      # FastAPI Web Interface & API
├── run.py                      # Unified CLI entrypoint
├── requirements.txt            # Python dependencies
├── entity_resolution_report.md # Entity resolution audit report
└── README.md                   # Project documentation
`
