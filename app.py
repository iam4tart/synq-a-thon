import os
import json
import time
import logging
import asyncio
import io
import csv
from functools import wraps
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel
import uvicorn

import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from src.pipeline import BreakdownPipeline
    from src.human_gate import HumanApprovalGate
    from src.query_interface import GroundedQueryInterface
    from src.context_store import ContextStore
    from src.llm_resolver import LLMResolver
except ImportError:
    from solutions.src.pipeline import BreakdownPipeline
    from solutions.src.human_gate import HumanApprovalGate
    from solutions.src.query_interface import GroundedQueryInterface
    from solutions.src.context_store import ContextStore
    from solutions.src.llm_resolver import LLMResolver

app = FastAPI(title="Meridian Freight - Operations Dashboard")

BASE_DIR = current_dir if (os.path.exists(os.path.join(current_dir, "tickets.json")) or os.path.exists(os.path.join(current_dir, "data"))) else parent_dir
OUTPUT_DIR = os.path.join(current_dir, "outputs")
AUDIT_DIR = os.path.join(current_dir, "audit")

llm = LLMResolver()  # Reads LLM_PROVIDER + API key from env; gracefully disabled if no key
pipeline = BreakdownPipeline(base_dir=BASE_DIR, output_dir=OUTPUT_DIR, audit_dir=AUDIT_DIR)
gate = HumanApprovalGate(output_dir=OUTPUT_DIR)
store = ContextStore(base_dir=BASE_DIR)
query_engine = GroundedQueryInterface(store, llm=llm)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("meridian-ops")

def graceful_api(operation: str):
    """Custom decorator for API observability and graceful failure handling."""
    def decorator(func):
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                start = time.time()
                try:
                    result = await func(*args, **kwargs)
                    logger.info(f"[{operation}] SUCCESS in {time.time()-start:.3f}s")
                    return result
                except Exception as e:
                    logger.error(f"[{operation}] FAILED: {str(e)}")
                    raise HTTPException(status_code=500, detail=f"{operation} failed: {str(e)}")
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                start = time.time()
                try:
                    result = func(*args, **kwargs)
                    logger.info(f"[{operation}] SUCCESS in {time.time()-start:.3f}s")
                    return result
                except Exception as e:
                    logger.error(f"[{operation}] FAILED: {str(e)}")
                    raise HTTPException(status_code=500, detail=f"{operation} failed: {str(e)}")
            return sync_wrapper
    return decorator

class QueryRequest(BaseModel):
    query: str

def read_jsonl(filepath: str) -> List[Dict[str, Any]]:
    if not os.path.exists(filepath):
        return []
    records = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    records.append(json.loads(line.strip()))
                except Exception:
                    pass
    return records


@app.get("/", response_class=HTMLResponse)
def get_dashboard():
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Meridian Ops</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
    <style>
        body { background: #fafafa; color: #111; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; font-size: 13px; }
        .navbar { border-bottom: 1px solid #eaeaea; background: #fff; padding: 12px 24px; }
        .brand { font-weight: 600; font-size: 14px; letter-spacing: -0.5px; }
        .card { background: #fff; border: 1px solid #eaeaea; border-radius: 6px; box-shadow: none; }
        .kpi-title { font-size: 10px; font-weight: 600; color: #888; text-transform: uppercase; letter-spacing: 0.5px; }
        .kpi-value { font-size: 24px; font-weight: 600; letter-spacing: -0.5px; margin-top: 4px; min-height: 36px; }
        .table { font-size: 12px; margin-bottom: 0; }
        .table th { border-bottom: 1px solid #eaeaea; color: #888; font-weight: 500; text-transform: uppercase; font-size: 10px; letter-spacing: 0.5px; padding: 12px; background: #fff; }
        .table td { border-bottom: 1px solid #fafafa; padding: 12px; vertical-align: middle; color: #333; }
        .nav-pills .nav-link { color: #888; font-size: 12px; padding: 6px 12px; border-radius: 4px; margin-right: 4px; cursor: pointer; }
        .nav-pills .nav-link.active { background: #111; color: #fff; }
        .btn-custom { font-size: 12px; font-weight: 500; border-radius: 4px; padding: 6px 14px; transition: all 0.2s; }
        .btn-primary { background: #111; border: none; color: #fff; }
        .btn-primary:hover { background: #333; color: #fff; }
        .btn-light { background: #fff; border: 1px solid #ddd; color: #111; }
        .btn-light:hover { background: #f5f5f5; border-color: #ccc; }
        .badge-custom { font-size: 10px; font-weight: 500; padding: 3px 6px; border-radius: 3px; }
        .bg-gray { background: #f4f4f5; color: #3f3f46; border: 1px solid #e4e4e7; }
        .search-box { background: #f4f4f5; border: 1px solid transparent; font-size: 12px; border-radius: 4px; padding: 6px 12px; width: 220px; transition: all 0.2s; outline: none; }
        .search-box:focus { background: #fff; border-color: #ddd; }
        .text-success { color: #10b981 !important; }
        .text-primary { color: #3b82f6 !important; }
        .text-danger { color: #ef4444 !important; }
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #ddd; border-radius: 3px; }
        .table-responsive { min-height: 340px; }
        .truncate { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 250px; display: inline-block; vertical-align: middle; cursor: help; }
        
        /* Focussed Micro-Animations */
        .btn-custom:active { transform: scale(0.96); }
        .table tbody tr { transition: background-color 0.15s ease; }
        .table tbody tr:hover { background-color: #f4f4f5; }
        .card { transition: box-shadow 0.25s ease; }
        .card:hover { box-shadow: 0 8px 16px rgba(0,0,0,0.04) !important; }
    </style>
</head>
<body>
    <nav class="navbar d-flex justify-content-between align-items-center mb-4">
        <div class="brand">Meridian Ops</div>
        <div class="d-flex gap-2">
            <input type="text" class="search-box" id="topSearch" placeholder="Search rules..." onkeydown="if(event.key==='Enter') executeTopQuery()">
            <button class="btn btn-light btn-custom" onclick="document.getElementById('fileInput').click()">Upload Data</button>
            <input type="file" id="fileInput" class="d-none" onchange="uploadFile(this)">
            <button class="btn btn-light btn-custom border" onclick="window.location.href='/api/download-report'">Download Audit</button>
            <button class="btn btn-primary btn-custom" onclick="runPipeline()">Process</button>
        </div>
    </nav>

    <div class="container-fluid px-4">
        <div id="dashboardContent">
            <div class="row g-3 mb-4">
            <div class="col-md-3">
                <div class="card p-3">
                    <div class="kpi-title">Inbound</div>
                    <div class="kpi-value" id="val-total">-</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card p-3">
                    <div class="kpi-title">Resolved</div>
                    <div class="kpi-value text-success" id="val-valid">-</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card p-3">
                    <div class="kpi-title">Pending</div>
                    <div class="kpi-value text-primary" id="val-pending">-</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card p-3">
                    <div class="kpi-title">Alerts</div>
                    <div class="kpi-value text-danger" id="val-quarantine">-</div>
                </div>
            </div>
        </div>

        <div class="row g-3 mb-4">
            <div class="col-lg-3">
                <div class="card p-3 mb-3">
                    <div class="kpi-title mb-2">Status</div>
                    <div style="height: 140px;"><canvas id="pipelineChart"></canvas></div>
                </div>
                <div class="card p-3">
                    <div class="kpi-title mb-2">Clients</div>
                    <div style="height: 140px;"><canvas id="clientChart"></canvas></div>
                </div>
            </div>

            <div class="col-lg-9">
                <div class="card p-3">
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <ul class="nav nav-pills" id="tabs" role="tablist">
                            <li class="nav-item"><a class="nav-link active" data-bs-toggle="pill" data-bs-target="#tab-pending">Approvals</a></li>
                            <li class="nav-item"><a class="nav-link" data-bs-toggle="pill" data-bs-target="#tab-sent">Sent Mails</a></li>
                            <li class="nav-item"><a class="nav-link" data-bs-toggle="pill" data-bs-target="#tab-orders">Work Orders</a></li>
                            <li class="nav-item"><a class="nav-link" data-bs-toggle="pill" data-bs-target="#tab-quarantine">Alerts</a></li>
                            <li class="nav-item"><a class="nav-link" data-bs-toggle="pill" data-bs-target="#tab-audit">Audit</a></li>
                        </ul>
                        <button class="btn btn-light btn-custom text-success border" id="btn-approve-all" onclick="approveAll()">Approve All</button>
                    </div>

                    <div class="tab-content">
                        <div class="tab-pane fade show active" id="tab-pending">
                            <div class="table-responsive">
                                <table class="table">
                                    <thead><tr>
                                        <th style="cursor:pointer;" onclick="sortTable('tbody-pending', 0, false)">ID ⇕</th>
                                        <th style="cursor:pointer;" onclick="sortTable('tbody-pending', 1, false)">Client ⇕</th>
                                        <th style="cursor:pointer;" onclick="sortTable('tbody-pending', 2, false)">Route ⇕</th>
                                        <th style="cursor:pointer;" onclick="sortTable('tbody-pending', 3, false)">Action ⇕</th>
                                        <th style="cursor:pointer;" onclick="sortTable('tbody-pending', 4, true)">SLA ⇕</th>
                                        <th class="text-end"></th>
                                    </tr></thead>
                                    <tbody id="tbody-pending"></tbody>
                                </table>
                            </div>
                        </div>
                        <div class="tab-pane fade" id="tab-sent">
                            <div class="table-responsive">
                                <table class="table">
                                    <thead><tr>
                                        <th>ID</th>
                                        <th>Recipient</th>
                                        <th>Sent Email Body (Drafted by AI)</th>
                                        <th class="text-end">Action</th>
                                    </tr></thead>
                                    <tbody id="tbody-sent"></tbody>
                                </table>
                            </div>
                        </div>
                        <div class="tab-pane fade" id="tab-orders">
                            <div class="table-responsive">
                                <table class="table">
                                    <thead><tr>
                                        <th style="cursor:pointer;" onclick="sortTable('tbody-orders', 0, false)">WO ID ⇕</th>
                                        <th style="cursor:pointer;" onclick="sortTable('tbody-orders', 1, false)">Ticket ⇕</th>
                                        <th style="cursor:pointer;" onclick="sortTable('tbody-orders', 2, false)">Vehicle ⇕</th>
                                        <th style="cursor:pointer;" onclick="sortTable('tbody-orders', 3, false)">Created ⇕</th>
                                        <th style="cursor:pointer;" onclick="sortTable('tbody-orders', 4, false)">Rules ⇕</th>
                                    </tr></thead>
                                    <tbody id="tbody-orders"></tbody>
                                </table>
                            </div>
                        </div>
                        <div class="tab-pane fade" id="tab-quarantine">
                            <div class="table-responsive">
                                <table class="table">
                                    <thead><tr>
                                        <th style="cursor:pointer;" onclick="sortTable('tbody-quarantine', 0, false)">Time ⇕</th>
                                        <th style="cursor:pointer;" onclick="sortTable('tbody-quarantine', 1, false)">Reason ⇕</th>
                                        <th style="cursor:pointer;" onclick="sortTable('tbody-quarantine', 2, false)">Data ⇕</th>
                                    </tr></thead>
                                    <tbody id="tbody-quarantine"></tbody>
                                </table>
                            </div>
                        </div>
                        <div class="tab-pane fade" id="tab-audit">
                            <div class="table-responsive">
                                <table class="table">
                                    <thead><tr>
                                        <th style="cursor:pointer;" onclick="sortTable('tbody-audit', 0, false)">Time ⇕</th>
                                        <th style="cursor:pointer;" onclick="sortTable('tbody-audit', 1, false)">Ticket ⇕</th>
                                        <th style="cursor:pointer;" onclick="sortTable('tbody-audit', 2, false)">Step ⇕</th>
                                        <th style="cursor:pointer;" onclick="sortTable('tbody-audit', 3, false)">Decision ⇕</th>
                                        <th style="cursor:pointer;" onclick="sortTable('tbody-audit', 4, false)">Rule ⇕</th>
                                    </tr></thead>
                                    <tbody id="tbody-audit"></tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        </div>

        <div id="queryResults" class="d-none">
            <div class="d-flex justify-content-between align-items-center mb-3">
                <div style="font-size: 16px; font-weight: 600; letter-spacing: -0.5px;">Knowledge Base Query</div>
                <button class="btn btn-light btn-custom border text-dark" onclick="clearQuery()">Close Query</button>
            </div>
            <div class="card p-4">
                <p class="kpi-title mb-1">Query</p>
                <p id="inlineQuestion" class="fw-bold fs-6 mb-4"></p>
                <p class="kpi-title mb-1">Answer</p>
                <p id="inlineAnswer" class="bg-gray p-3 rounded text-dark lh-sm mb-4" style="font-size: 14px;"></p>
                <p class="kpi-title mb-1">Sources</p>
                <ul id="inlineCitations" class="text-muted ps-3 mb-0" style="font-size: 13px;"></ul>
            </div>
        </div>
    </div>

    <!-- Gentle Transparency Toast Notification -->
    <div class="toast-container position-fixed bottom-0 end-0 p-3" style="z-index: 1055;">
        <div id="actionToast" class="toast align-items-center text-bg-dark border-0 shadow-lg" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="d-flex">
                <div class="toast-body" id="toastMessage" style="font-size: 13px; font-weight: 500;">
                    Action completed.
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        let chart1, chart2;
        let lastDataHash = "";

        function showToast(msg) {
            document.getElementById('toastMessage').innerText = msg;
            const toastEl = document.getElementById('actionToast');
            const toast = new bootstrap.Toast(toastEl, { delay: 4000 });
            toast.show();
        }

        function sortTable(tbodyId, colIndex, isNumeric) {
            const tbody = document.getElementById(tbodyId);
            const rows = Array.from(tbody.querySelectorAll('tr'));
            if (rows.length === 0 || (rows.length === 1 && rows[0].innerText.includes('No pending'))) return;
            
            let dir = tbody.getAttribute('data-sort-dir') === 'asc' ? 'desc' : 'asc';
            tbody.setAttribute('data-sort-dir', dir);
            
            rows.sort((a, b) => {
                let valA = a.children[colIndex].innerText.trim();
                let valB = b.children[colIndex].innerText.trim();
                if (isNumeric) {
                    valA = parseFloat(valA.replace(/[^0-9.-]+/g,"")) || 0;
                    valB = parseFloat(valB.replace(/[^0-9.-]+/g,"")) || 0;
                    return dir === 'asc' ? valA - valB : valB - valA;
                }
                return dir === 'asc' ? valA.localeCompare(valB) : valB.localeCompare(valA);
            });
            tbody.innerHTML = '';
            rows.forEach(r => tbody.appendChild(r));
        }

        async function fetchDashboard() {
            try {
                const res = await fetch('/api/dashboard-data');
                if (!res.ok) throw new Error("API Offline");
                const d = await res.json();
                
                const currentHash = JSON.stringify(d.stats) + d.pending.length + d.quarantine.length + d.work_orders.length + d.audit.length;
                if (currentHash === lastDataHash) return;
                lastDataHash = currentHash;
            
            document.getElementById('val-total').innerText = d.stats.total_raw;
            document.getElementById('val-valid').innerText = d.stats.processed_valid;
            document.getElementById('val-pending').innerText = d.pending.length;
            document.getElementById('val-quarantine').innerText = d.quarantine.length;
            
            const tbP = document.getElementById('tbody-pending');
            if(d.pending.length===0){
                tbP.innerHTML = '<tr><td colspan="4" class="text-center text-muted py-4">No pending approvals</td></tr>';
                document.getElementById('btn-approve-all').style.display='none';
            }else{
                document.getElementById('btn-approve-all').style.display='block';
                tbP.innerHTML = d.pending.map(m=><tr>
                    <td class="fw-medium"></td>
                    <td><span class="badge-custom bg-gray"></span></td>
                    <td style="white-space: pre-wrap; font-size: 11px; color: #444; max-width: 400px;"><strong>Subject: Delay Notification</strong>
</td>
                    <td class="text-end"><button class="btn btn-primary btn-custom py-1 px-2" onclick="approveSingle('')">Approve Mail</button></td>
                </tr>).join('');
            }
            
            const tbS = document.getElementById('tbody-sent');
            if(d.sent.length===0){
                tbS.innerHTML = '<tr><td colspan="4" class="text-center text-muted py-4">No sent emails</td></tr>';
            }else{
                tbS.innerHTML = d.sent.map(m=><tr>
                    <td class="fw-medium"></td>
                    <td><span class="badge-custom bg-gray"></span></td>
                    <td style="white-space: pre-wrap; font-size: 11px; color: #444; max-width: 400px;"><strong>Subject: Delay Notification</strong>
</td>
                    <td class="text-end"><button class="btn btn-light btn-custom border text-danger py-1 px-2" onclick="unapproveSingle('')">Undo</button></td>
                </tr>).join('');
            }
            document.getElementById('tbody-orders').innerHTML = d.work_orders.map(w=>`<tr>
                <td class="fw-medium">${w.work_order_id}</td><td>${w.ticket_id}</td>
                <td class="fw-medium">${w.vehicle_reg}</td><td>${w.created_at.split('T')[1].split('.')[0]}</td>
                <td><span class="badge-custom bg-gray truncate" title="${w.citations ? w.citations.join(', ').replace(/'/g, "&apos;") : ''}">${w.citations ? w.citations[0] : ''}</span></td>
            </tr>`).join('');
            
            document.getElementById('tbody-quarantine').innerHTML = d.quarantine.map(q=>`<tr>
                <td>${q.quarantined_at.split('T')[1].split('.')[0]}</td>
                <td class="text-danger fw-medium">${q.reason}</td>
                <td><span class="truncate" title='${JSON.stringify(q.raw_record).replace(/'/g, "&apos;")}'><code class="text-muted" style="font-size: 11px;">${JSON.stringify(q.raw_record).substring(0,60)}...</code></span></td>
            </tr>`).join('');
            
            document.getElementById('tbody-audit').innerHTML = d.audit.slice(-20).reverse().map(a=>`<tr>
                <td>${a.timestamp.split('T')[1].split('.')[0]}</td>
                <td class="fw-medium">${a.ticket_id}</td><td>${a.step}</td>
                <td><span class="truncate" title="${a.decision.replace(/'/g, "&apos;")}">${a.decision}</span></td>
                <td><span class="badge-custom bg-gray truncate" title="${a.rule||'System'}">${a.rule||'System'}</span></td>
            </tr>`).join('');
            
            renderCharts(d);
            } catch (err) {
                document.getElementById('status-indicator').innerHTML = '<span class="text-danger">● Offline</span>';
                console.error("Dashboard fetch failed:", err);
            }
        }
        
        function renderCharts(d) {
            const c1 = document.getElementById('pipelineChart').getContext('2d');
            if(chart1) chart1.destroy();
            chart1 = new Chart(c1, {
                type: 'doughnut',
                data: {
                    labels: ['Valid', 'Alerts', 'Dups'],
                    datasets: [{ data: [d.stats.processed_valid, d.quarantine.length, d.stats.duplicates_skipped], backgroundColor: ['#111', '#ef4444', '#e4e4e7'], borderWidth: 0 }]
                },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom', labels: {boxWidth: 8, font: {size: 10}} } }, cutout: '75%' }
            });
            
            const c2 = document.getElementById('clientChart').getContext('2d');
            if(chart2) chart2.destroy();
            chart2 = new Chart(c2, {
                type: 'bar',
                data: {
                    labels: ['S. Cement', 'Apex', 'Orion', 'Vertex'],
                    datasets: [{ data: [10, 8, 7, 5], backgroundColor: '#111', borderRadius: 4, maxBarThickness: 32 }]
                },
                options: {
                    responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } },
                    scales: { y: { display: false }, x: { grid: { display: false }, border: {display: false}, ticks: { font: { size: 10 } } } }
                }
            });
        }
        
        async function runPipeline() { 
            const res = await fetch('/api/process-queue', {method:'POST'}); 
            const data = await res.json();
            showToast(`Processed queue: ${data.stats.processed_valid} resolved, ${data.stats.quarantined} alerts.`);
            fetchDashboard(); 
        }
        async function approveAll() { 
            const res = await fetch('/api/approve-comms', {method:'POST'}); 
            const data = await res.json();
            showToast(`Approved and dispatched ${data.approved_count} pending operations.`);
            fetchDashboard(); 
        }
        async function approveSingle(id) { 
            await fetch('/api/approve-comms?ticket_id='+id, {method:'POST'}); 
            showToast(Approved email for ticket .);
            fetchDashboard(); 
        }
        async function unapproveSingle(id) { 
            await fetch('/api/unapprove-comms?ticket_id='+id, {method:'POST'}); 
            showToast(Undo: Recalled email for ticket .);
            fetchDashboard(); 
        }); 
            const data = await res.json();
            showToast(`Approved operation for ticket ${id}.`);
            fetchDashboard(); 
        }
        async function uploadFile(inp) {
            if(!inp.files[0]) return;
            const fd = new FormData(); fd.append('file', inp.files[0]);
            const res = await fetch('/api/upload-queue', {method:'POST', body: fd});
            const data = await res.json();
            showToast(`Ingested ${inp.files[0].name}: ${data.stats.processed_valid} resolved, ${data.stats.quarantined} alerts.`);
            fetchDashboard();
        }
        async function executeTopQuery() {
            const q = document.getElementById('topSearch').value; if(!q) return;

            // Show loading state
            document.getElementById('dashboardContent').classList.add('d-none');
            document.getElementById('queryResults').classList.remove('d-none');
            document.getElementById('inlineQuestion').innerText = q;
            document.getElementById('inlineAnswer').innerText = 'Searching knowledge base...';
            document.getElementById('inlineCitations').innerHTML = '';

            const res = await fetch('/api/query', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({query:q}) });
            const data = await res.json();

            // Sanitize answer: if LLM leaked JSON, try to extract the "answer" field
            let answer = data.answer || 'INSUFFICIENT DATA';
            try {
                const parsed = JSON.parse(answer);
                if (parsed && parsed.answer) answer = parsed.answer;
            } catch(e) {}

            // Confidence badge
            const conf = data.confidence || 'UNKNOWN';
            const badgeColor = conf === 'HIGH' ? '#10b981' : conf === 'LLM_GROUNDED' ? '#3b82f6' : '#888';
            const badgeLabel = conf === 'HIGH' ? 'Rule-Grounded' : conf === 'LLM_GROUNDED' ? 'LLM-Grounded' : 'Insufficient Data';

            document.getElementById('inlineQuestion').innerText = q;
            document.getElementById('inlineAnswer').innerHTML =
                `<span style="display:inline-block;font-size:10px;font-weight:600;color:#fff;background:${badgeColor};padding:2px 7px;border-radius:3px;margin-bottom:10px;letter-spacing:0.3px;">${badgeLabel}</span><br>${answer}`;

            // Citations: render as labelled source references
            if (data.citations && data.citations.length > 0) {
                document.getElementById('inlineCitations').innerHTML = data.citations.map(c => {
                    const parts = c.split(':');
                    const file = parts[0] || c;
                    const ref = parts.slice(1).join(':') || '';
                    return `<li><code style="font-size:11px;background:#f4f4f5;padding:1px 5px;border-radius:3px;">${file}</code>${ref ? ' <span class="text-muted">'+ref+'</span>' : ''}</li>`;
                }).join('');
            } else {
                document.getElementById('inlineCitations').innerHTML = '<li class="text-muted" style="font-size:12px;">No traceable source found in corpus.</li>';
            }
        }
        
        function clearQuery() {
            document.getElementById('topSearch').value = '';
            document.getElementById('queryResults').classList.add('d-none');
            document.getElementById('dashboardContent').classList.remove('d-none');
        }
        
        fetchDashboard(); setInterval(fetchDashboard, 5000);
    </script>
</body>
</html>
"""
    return HTMLResponse(content=html_content)


@app.get("/api/dashboard-data")
@graceful_api("Fetch Dashboard Data")
def get_dashboard_data():
    work_orders = read_jsonl(os.path.join(OUTPUT_DIR, "work_orders.jsonl"))
    pending = read_jsonl(os.path.join(OUTPUT_DIR, "comms_pending.jsonl"))
    sent = read_jsonl(os.path.join(OUTPUT_DIR, "comms_sent.jsonl"))
    quarantine = read_jsonl(os.path.join(OUTPUT_DIR, "quarantine.jsonl"))
    audit = read_jsonl(os.path.join(AUDIT_DIR, "audit.jsonl"))

    # Calculate raw totals accurately by reading tickets file
    tickets_path = os.path.join(BASE_DIR, "tickets.json")
    if not os.path.exists(tickets_path):
        tickets_path = os.path.join(BASE_DIR, "data", "tickets.json")
    
    total_raw = 0
    if os.path.exists(tickets_path):
        try:
            with open(tickets_path, "r", encoding="utf-8") as f:
                total_raw = len(json.load(f))
        except Exception:
            # Maybe it's a JSONL or CSV if it's the surprise file
            pass

    if total_raw == 0:
        # Fallback to sum of outputs if source file is missing
        total_raw = len(work_orders) + len(quarantine)

    return {
        "stats": {
            "total_raw": total_raw,
            "processed_valid": len(work_orders),
            "duplicates_skipped": max(0, total_raw - len(work_orders) - len(quarantine))
        },
        "work_orders": work_orders,
        "pending": pending,
        "sent": sent,
        "quarantine": quarantine,
        "audit": audit
    }


@app.post("/api/process-queue")
@graceful_api("Process Queue")
def process_queue():
    queue_path = os.path.join(BASE_DIR, "tickets.json")
    stats = pipeline.process_queue_file(queue_path)
    return {"status": "SUCCESS", "stats": stats}


@app.post("/api/approve-comms")
@graceful_api("Approve Comms")
def approve_comms(ticket_id: Optional[str] = None):
    approved = gate.approve(approver_name="Ops_Manager", ticket_id=ticket_id)
    return {"status": "SUCCESS", "approved_count": approved}


@app.post("/api/query")
@graceful_api("Knowledge Query")
@app.post("/api/unapprove-comms")
@graceful_api("Unapprove Comms")
def unapprove_comms(ticket_id: str):
    success = gate.unapprove(ticket_id=ticket_id)
    return {"status": "SUCCESS", "unapproved": success}

@app.post("/api/query")
@graceful_api("Knowledge Query")
def ask_query(payload: QueryRequest):
    res = query_engine.query(payload.query)
    return res


@app.get("/api/download-report")
@graceful_api("Download Report")
def download_report():
    audit_records = read_jsonl(os.path.join(AUDIT_DIR, "audit.jsonl"))
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Timestamp", "Ticket_ID", "Step", "Decision", "Rule_Applied"])
    for a in audit_records:
        writer.writerow([a.get("timestamp"), a.get("ticket_id"), a.get("step"), a.get("decision"), a.get("rule", "")])
    
    return PlainTextResponse(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=meridian_compliance_audit.csv"}
    )


@app.post("/api/upload-queue")
@graceful_api("Upload Queue")
async def upload_queue(file: UploadFile = File(...)):
    temp_path = os.path.join(current_dir, f"temp_{file.filename}")
    with open(temp_path, "wb") as f:
        f.write(await file.read())
    stats = pipeline.process_queue_file(temp_path, is_append=True)
    if os.path.exists(temp_path):
        os.remove(temp_path)
    return {"status": "SUCCESS", "stats": stats}


if __name__ == '__main__':
    uvicorn.run("solutions.app:app", host="127.0.0.1", port=8000, reload=False)

