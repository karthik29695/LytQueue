from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["dashboard"])

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Job Platform Monitor</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', sans-serif; background: #0f1117; color: #e2e8f0; min-height: 100vh; }
  header { background: #1a1d2e; border-bottom: 1px solid #2d3748; padding: 16px 32px;
           display: flex; align-items: center; justify-content: space-between; }
  header h1 { font-size: 1.2rem; font-weight: 600; color: #a78bfa; }
  #last-updated { font-size: 0.75rem; color: #64748b; }
  main { padding: 24px 32px; max-width: 1400px; margin: 0 auto; }
  h2 { font-size: 0.7rem; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase;
       color: #64748b; margin-bottom: 12px; margin-top: 28px; }
  .cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; }
  .card { background: #1a1d2e; border: 1px solid #2d3748; border-radius: 10px;
          padding: 16px; display: flex; flex-direction: column; gap: 4px; }
  .card .label { font-size: 0.7rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; }
  .card .value { font-size: 1.8rem; font-weight: 700; color: #e2e8f0; }
  .card.green .value { color: #34d399; }
  .card.blue  .value { color: #60a5fa; }
  .card.yellow .value { color: #fbbf24; }
  .card.red   .value { color: #f87171; }
  .card.purple .value { color: #a78bfa; }

  table { width: 100%; border-collapse: collapse; background: #1a1d2e;
          border: 1px solid #2d3748; border-radius: 10px; overflow: hidden; font-size: 0.82rem; }
  th { background: #12141f; padding: 10px 14px; text-align: left; font-size: 0.68rem;
       text-transform: uppercase; letter-spacing: 0.08em; color: #64748b; font-weight: 600; }
  td { padding: 10px 14px; border-top: 1px solid #1e2433; color: #cbd5e1; }
  tr:hover td { background: #1e2433; }

  .badge { display: inline-block; padding: 2px 8px; border-radius: 9999px;
           font-size: 0.68rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; }
  .badge-QUEUED    { background: #1e3a5f; color: #60a5fa; }
  .badge-RUNNING   { background: #1a3a2a; color: #34d399; }
  .badge-COMPLETED { background: #14532d; color: #4ade80; }
  .badge-FAILED    { background: #3b1d1d; color: #f87171; }
  .badge-DEAD      { background: #2d1b1b; color: #ef4444; }
  .badge-IDLE      { background: #1e293b; color: #94a3b8; }
  .badge-OFFLINE   { background: #1c1c1c; color: #4b5563; }

  .mono { font-family: 'Consolas', monospace; font-size: 0.75rem; color: #94a3b8; }
  .hb-ok  { color: #34d399; }
  .hb-old { color: #f87171; }
  #error-banner { background: #3b1d1d; color: #f87171; padding: 10px 32px;
                  font-size: 0.8rem; display: none; }
</style>
</head>
<body>
<header>
  <h1>⚡ Distributed Job Platform — Monitor</h1>
  <span id="last-updated">Loading...</span>
</header>
<div id="error-banner">⚠ Cannot reach API — retrying...</div>
<main>
  <h2>Job Metrics</h2>
  <div class="cards" id="job-cards">
    <div class="card"><span class="label">Total</span><span class="value" id="m-total">—</span></div>
    <div class="card blue"><span class="label">Queued</span><span class="value" id="m-queued">—</span></div>
    <div class="card green"><span class="label">Completed</span><span class="value" id="m-completed">—</span></div>
    <div class="card yellow"><span class="label">Running</span><span class="value" id="m-running">—</span></div>
    <div class="card red"><span class="label">Failed</span><span class="value" id="m-failed">—</span></div>
    <div class="card red"><span class="label">Dead (DLQ)</span><span class="value" id="m-dead">—</span></div>
    <div class="card purple"><span class="label">Success Rate</span><span class="value" id="m-rate">—</span></div>
    <div class="card"><span class="label">Avg Runtime</span><span class="value" id="m-avg">—</span></div>
  </div>

  <h2>Queue Depths</h2>
  <div class="cards">
    <div class="card red"><span class="label">High Priority</span><span class="value" id="q-high">—</span></div>
    <div class="card yellow"><span class="label">Medium Priority</span><span class="value" id="q-medium">—</span></div>
    <div class="card blue"><span class="label">Low Priority</span><span class="value" id="q-low">—</span></div>
    <div class="card"><span class="label">Dead Letter Queue</span><span class="value" id="q-dlq">—</span></div>
  </div>

  <h2>Workers</h2>
  <table>
    <thead><tr>
      <th>Worker ID</th><th>Status</th><th>Current Job</th>
      <th>Jobs Processed</th><th>Last Heartbeat</th>
    </tr></thead>
    <tbody id="workers-tbody"><tr><td colspan="5" style="color:#4b5563">No workers registered</td></tr></tbody>
  </table>

  <h2>Recent Jobs</h2>
  <table>
    <thead><tr>
      <th>ID</th><th>Type</th><th>Priority</th><th>Status</th>
      <th>Worker</th><th>Retries</th><th>Created</th>
    </tr></thead>
    <tbody id="jobs-tbody"><tr><td colspan="7" style="color:#4b5563">No jobs yet</td></tr></tbody>
  </table>
</main>

<script>
const API = '';

function badge(status) {
  return `<span class="badge badge-${status}">${status}</span>`;
}

function fmtTime(iso) {
  if (!iso) return '<span style="color:#4b5563">—</span>';
  const d = new Date(iso);
  return d.toLocaleTimeString();
}

function hbStatus(iso) {
  if (!iso) return '<span class="hb-old">never</span>';
  const age = (Date.now() - new Date(iso)) / 1000;
  const t = new Date(iso).toLocaleTimeString();
  return age < 15
    ? `<span class="hb-ok">✓ ${t}</span>`
    : `<span class="hb-old">⚠ ${t} (${Math.round(age)}s ago)</span>`;
}

async function refresh() {
  try {
    const [metrics, jobs] = await Promise.all([
      fetch(`${API}/metrics`).then(r => r.json()),
      fetch(`${API}/jobs`).then(r => r.json()),
    ]);

    document.getElementById('error-banner').style.display = 'none';

    // Job metric cards
    const s = metrics.jobs.by_status || {};
    document.getElementById('m-total').textContent     = metrics.jobs.total;
    document.getElementById('m-queued').textContent    = s.QUEUED    || 0;
    document.getElementById('m-completed').textContent = s.COMPLETED || 0;
    document.getElementById('m-running').textContent   = s.RUNNING   || 0;
    document.getElementById('m-failed').textContent    = s.FAILED    || 0;
    document.getElementById('m-dead').textContent      = s.DEAD      || 0;
    document.getElementById('m-rate').textContent      = metrics.jobs.success_rate_pct + '%';
    document.getElementById('m-avg').textContent       =
      metrics.jobs.avg_runtime_seconds != null ? metrics.jobs.avg_runtime_seconds + 's' : '—';

    // Queue depths
    document.getElementById('q-high').textContent   = metrics.queues.high;
    document.getElementById('q-medium').textContent = metrics.queues.medium;
    document.getElementById('q-low').textContent    = metrics.queues.low;
    document.getElementById('q-dlq').textContent    = metrics.queues.dlq;

    // Workers table
    const workers = metrics.workers || [];
    const wtbody = document.getElementById('workers-tbody');
    if (workers.length === 0) {
      wtbody.innerHTML = '<tr><td colspan="5" style="color:#4b5563">No workers registered</td></tr>';
    } else {
      wtbody.innerHTML = workers.map(w => `
        <tr>
          <td class="mono">${w.worker_id}</td>
          <td>${badge(w.status)}</td>
          <td class="mono">${w.current_job_id ? w.current_job_id.substring(0,8)+'...' : '—'}</td>
          <td>${w.jobs_processed}</td>
          <td>${hbStatus(w.last_heartbeat)}</td>
        </tr>`).join('');
    }

    // Recent jobs table (last 20)
    const recent = jobs.slice(0, 20);
    const jtbody = document.getElementById('jobs-tbody');
    if (recent.length === 0) {
      jtbody.innerHTML = '<tr><td colspan="7" style="color:#4b5563">No jobs yet</td></tr>';
    } else {
      jtbody.innerHTML = recent.map(j => `
        <tr>
          <td class="mono">${j.id.substring(0,8)}...</td>
          <td>${j.type}</td>
          <td>${j.priority}</td>
          <td>${badge(j.status)}</td>
          <td class="mono">${j.worker_id || '—'}</td>
          <td>${j.retry_count}</td>
          <td>${fmtTime(j.created_at)}</td>
        </tr>`).join('');
    }

    document.getElementById('last-updated').textContent =
      'Updated ' + new Date().toLocaleTimeString();

  } catch (e) {
    document.getElementById('error-banner').style.display = 'block';
    document.getElementById('last-updated').textContent = 'Connection error';
  }
}

refresh();
setInterval(refresh, 3000);
</script>
</body>
</html>"""


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    return HTMLResponse(content=DASHBOARD_HTML)
