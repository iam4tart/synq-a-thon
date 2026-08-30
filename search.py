with open('app.py', 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        if '<div class="row g-3 mb-4">' in line or 'function renderCharts' in line or 'function fetchDashboard' in line or 'def download_report' in line:
            print(f'Line {i}: {line.strip()}')
