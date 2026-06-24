from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["dashboard"])

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Job Platform Monitor v4</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', sans-serif; background: #0f1117; color: #e2e8f0; min-height: 100vh; }
  header { background: #1a1d2e; border-bottom: 1px solid #2d3748; padding: 14px 32px;
           display: flex; align-items: center; justify-content: space-between; }
  header h1 { font-size: 1.1rem; font-weight: 600; color: #a78bfa; }
  #last-updated { font-size: 0.72rem; color: #64748b; }
  main { padding: 20px 32px; max-width: 1500px; margin: 0 auto; }
  h2 { font-size: 0.68rem; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase;
       color: #64748b; margin-bottom: 10px; margin-top: 24px; }
  .cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; }
  .card { background: #1a1d2e; border: 1px solid #2d3748; border-radius: 10px;
          padding: 14px 16px; display: flex; flex-direction: column; gap: 3px; }
  .card .label { font-size: 0.67rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; }
  .card .value { font-size: 1.7rem; font-weight: 700; color: #e2e8f0; }
  .card.green  .value { color: #34d399; }
  .card.blue   .value { color: #60a5fa; }
  .card.yellow .value { color: #fbbf24; }
  .card.red    .value { color: #f87171; }
  .card.purple .value { color: #a78bfa; }
  .charts-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 10px; }
  .chart-box { background: #1a1d2e; border: 1px solid #2d3748; border-radius: 10px; padding: 16px 20px; }
  .chart-box h3 { font-size: 0.72rem; color: #94a3b8; text-transform: uppercase;
                  letter-spacing: 0.08em; margin-bottom: 14px; }
  /* SVG bar chart styles */
  .bar-chart { width: 100%; height: 160px; }
  .bar-label { font-size: 9px; fill: #64748b; }
  .bar-value { font-size: 9px; fill: #94a3b8; }
  /* Donut */
  .donut-wrap { display: flex; align-items: center; gap: 16px; height: 160px; }
  .donut-legend { display: flex; flex-direction: column; gap: 6px; }
  .legend-item { display: flex; align-items: center; gap: 6px; font-size: 0.72rem; color: #94a3b8; }
  .legend-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
  .workers-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 10px; }
  .worker-card { background: #1a1d2e; border: 1px solid #2d3748; border-radius: 10px; padding: 14px 18px; }
  .worker-card.offline { border-color: #ef4444; opacity: 0.6; }
  .worker-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
  .worker-name { font-size: 0.88rem; font-weight: 600; }
  .worker-stats { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; margin-bottom: 8px; }
  .wstat .wlabel { font-size: 0.62rem; color: #64748b; text-transform: uppercase; }
  .wstat .wvalue { font-size: 0.95rem; font-weight: 600; color: #e2e8f0; }
  table { width: 100%; border-collapse: collapse; background: #1a1d2e;
          border: 1px solid #2d3748; border-radius: 10px; overflow: hidden; font-size: 0.8rem; }
  th { background: #12141f; padding: 9px 12px; text-align: left; font-size: 0.65rem;
       text-transform: uppercase; letter-spacing: 0.08em; color: #64748b; font-weight: 600; }
  td { padding: 9px 12px; border-top: 1px solid #1e2433; color: #cbd5e1; }
  tr:hover td { background: #1e2433; }
  .badge { display: inline-block; padding: 2px 7px; border-radius: 9999px;
           font-size: 0.65rem; font-weight: 600; text-transform: uppercase; }
  .badge-QUEUED    { background: #1e3a5f; color: #60a5fa; }
  .badge-RUNNING   { background: #1a3a2a; color: #34d399; }
  .badge-COMPLETED { background: #14532d; color: #4ade80; }
  .badge-FAILED    { background: #3b1d1d; color: #f87171; }
  .badge-DEAD      { background: #2d1b1b; color: #ef4444; }
  .badge-IDLE      { background: #1e293b; color: #94a3b8; }
  .badge-OFFLINE   { background: #1c1c1c; color: #ef4444; }
  .mono { font-family: 'Consolas', monospace; font-size: 0.73rem; color: #94a3b8; }
  .hb-ok   { color: #34d399; font-size: 0.75rem; }
  .hb-warn { color: #fbbf24; font-size: 0.75rem; }
  .hb-dead { color: #f87171; font-size: 0.75rem; }
  .alert { border-radius: 8px; padding: 9px 14px; font-size: 0.78rem; margin-bottom: 10px; display: none; }
  .alert-red    { background: #3b1d1d; border: 1px solid #ef4444; color: #f87171; }
  .alert-yellow { background: #2d2000; border: 1px solid #fbbf24; color: #fbbf24; }
  #error-banner { background: #3b1d1d; color: #f87171; padding: 8px 32px; font-size: 0.78rem; display: none; }
  .prog-bar { height: 6px; background: #1e2433; border-radius: 3px; margin-top: 4px; }
  .prog-fill { height: 100%; border-radius: 3px; background: #a78bfa; }
  .empty-chart { display: flex; align-items: center; justify-content: center;
                 height: 160px; color: #4b5563; font-size: 0.8rem; }
</style>
</head>
<body>
<header>
  <h1>⚡ Distributed Job Platform — Monitor v4</h1>
  <span id="last-updated">Loading...</span>
</header>
<div id="error-banner">⚠ Cannot reach API — retrying...</div>
<main>
  <div id="crash-alert" class="alert alert-red"></div>
  <div id="slow-alert"  class="alert alert-yellow"></div>

  <h2>Job Overview</h2>
  <div class="cards">
    <div class="card"><span class="label">Total</span><span class="value" id="m-total">—</span></div>
    <div class="card blue"><span class="label">Queued</span><span class="value" id="m-queued">—</span></div>
    <div class="card green"><span class="label">Completed</span><span class="value" id="m-completed">—</span></div>
    <div class="card yellow"><span class="label">Running</span><span class="value" id="m-running">—</span></div>
    <div class="card red"><span class="label">Failed/Dead</span><span class="value" id="m-failed">—</span></div>
    <div class="card purple"><span class="label">Success Rate</span><span class="value" id="m-rate">—</span></div>
    <div class="card"><span class="label">Avg Runtime</span><span class="value" id="m-avg">—</span></div>
    <div class="card blue"><span class="label">Jobs/min</span><span class="value" id="m-tput">—</span></div>
  </div>

  <h2>Queue Depths</h2>
  <div class="cards">
    <div class="card red"><span class="label">High</span><span class="value" id="q-high">—</span></div>
    <div class="card yellow"><span class="label">Medium</span><span class="value" id="q-medium">—</span></div>
    <div class="card blue"><span class="label">Low</span><span class="value" id="q-low">—</span></div>
    <div class="card"><span class="label">DLQ</span><span class="value" id="q-dlq">—</span></div>
  </div>

  <h2>Charts</h2>
  <div class="charts-grid">
    <div class="chart-box">
      <h3>Jobs by Status</h3>
      <div class="donut-wrap">
        <svg id="donut-svg" width="140" height="140" viewBox="0 0 140 140"></svg>
        <div class="donut-legend" id="donut-legend"></div>
      </div>
    </div>
    <div class="chart-box">
      <h3>Throughput — completions per minute</h3>
      <div id="tput-chart-wrap"></div>
    </div>
    <div class="chart-box">
      <h3>Avg Runtime by Job Type (s)</h3>
      <div id="runtime-chart-wrap"></div>
    </div>
    <div class="chart-box">
      <h3>Jobs Processed per Worker</h3>
      <div id="worker-chart-wrap"></div>
    </div>
  </div>

  <h2>Workers</h2>
  <div class="workers-grid" id="workers-grid"></div>

  <h2>Runtime Stats by Job Type</h2>
  <table>
    <thead><tr><th>Type</th><th>Count</th><th>Avg (s)</th><th>Min (s)</th><th>Max (s)</th><th>Distribution</th></tr></thead>
    <tbody id="runtime-tbody"><tr><td colspan="6" style="color:#4b5563">No data yet</td></tr></tbody>
  </table>

  <h2>Recent Jobs</h2>
  <table>
    <thead><tr><th>ID</th><th>Type</th><th>Priority</th><th>Status</th><th>Worker</th><th>Retries</th><th>Created</th></tr></thead>
    <tbody id="jobs-tbody"><tr><td colspan="7" style="color:#4b5563">No jobs yet</td></tr></tbody>
  </table>
</main>

<script>
function badge(s) { return `<span class="badge badge-${s}">${s}</span>`; }
function fmtTime(iso) {
  if (!iso) return '<span style="color:#4b5563">—</span>';
  return new Date(iso).toLocaleTimeString();
}
function hbBadge(w) {
  const age = w.heartbeat_age_seconds;
  if (age == null) return '<span class="hb-dead">never</span>';
  if (age < 10)    return `<span class="hb-ok">✓ ${age}s ago</span>`;
  if (age < 20)    return `<span class="hb-warn">⚠ ${age}s ago</span>`;
  return `<span class="hb-dead">✗ ${age}s ago</span>`;
}

// ── SVG bar chart ─────────────────────────────────────────────────────────────
function svgBarChart(container, labels, values, color) {
  if (!labels.length) {
    container.innerHTML = '<div class="empty-chart">No data yet</div>';
    return;
  }
  const W = container.clientWidth || 380, H = 160;
  const pad = { top: 20, right: 10, bottom: 28, left: 36 };
  const chartW = W - pad.left - pad.right;
  const chartH = H - pad.top - pad.bottom;
  const maxVal = Math.max(...values, 1);
  const barW   = Math.max(4, Math.floor(chartW / labels.length) - 4);

  let bars = '', xLabels = '', yLabels = '';

  // Y axis labels
  for (let i = 0; i <= 4; i++) {
    const v = Math.round(maxVal * i / 4);
    const y = pad.top + chartH - (chartH * i / 4);
    yLabels += `<line x1="${pad.left}" y1="${y}" x2="${pad.left + chartW}" y2="${y}"
      stroke="rgba(255,255,255,0.06)" stroke-width="1"/>
      <text x="${pad.left - 4}" y="${y + 3}" text-anchor="end" class="bar-label">${v}</text>`;
  }

  // Bars
  values.forEach((v, i) => {
    const barH = Math.max(2, (v / maxVal) * chartH);
    const x    = pad.left + (i * chartW / labels.length) + (chartW / labels.length - barW) / 2;
    const y    = pad.top + chartH - barH;
    bars += `<rect x="${x}" y="${y}" width="${barW}" height="${barH}"
      fill="${Array.isArray(color) ? color[i % color.length] : color}" rx="2"/>`;
    if (v > 0) {
      bars += `<text x="${x + barW/2}" y="${y - 4}" text-anchor="middle" class="bar-value">${v}</text>`;
    }
    // X label — truncate long labels
    const lbl = labels[i].length > 8 ? labels[i].substring(0, 7) + '…' : labels[i];
    xLabels += `<text x="${x + barW/2}" y="${H - 6}" text-anchor="middle" class="bar-label">${lbl}</text>`;
  });

  container.innerHTML = `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">
    ${yLabels}
    <line x1="${pad.left}" y1="${pad.top}" x2="${pad.left}" y2="${pad.top + chartH}"
      stroke="rgba(255,255,255,0.1)" stroke-width="1"/>
    ${bars}${xLabels}
  </svg>`;
}

// ── SVG donut chart ───────────────────────────────────────────────────────────
const DONUT_COLORS = { COMPLETED:'#4ade80', QUEUED:'#60a5fa', RUNNING:'#fbbf24',
                       FAILED:'#f87171', DEAD:'#ef4444' };

function svgDonut(labels, values) {
  const total = values.reduce((a, b) => a + b, 0);
  if (!total) {
    document.getElementById('donut-svg').innerHTML =
      '<text x="70" y="75" text-anchor="middle" fill="#4b5563" font-size="11">No data</text>';
    document.getElementById('donut-legend').innerHTML = '';
    return;
  }
  const cx = 70, cy = 70, r = 52, inner = 30;
  let angle = -Math.PI / 2, paths = '';

  values.forEach((v, i) => {
    const slice = (v / total) * 2 * Math.PI;
    const x1 = cx + r * Math.cos(angle), y1 = cy + r * Math.sin(angle);
    const x2 = cx + r * Math.cos(angle + slice), y2 = cy + r * Math.sin(angle + slice);
    const ix1 = cx + inner * Math.cos(angle), iy1 = cy + inner * Math.sin(angle);
    const ix2 = cx + inner * Math.cos(angle + slice), iy2 = cy + inner * Math.sin(angle + slice);
    const large = slice > Math.PI ? 1 : 0;
    const color = DONUT_COLORS[labels[i]] || '#94a3b8';
    paths += `<path d="M ${ix1} ${iy1} L ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2}
      L ${ix2} ${iy2} A ${inner} ${inner} 0 ${large} 0 ${ix1} ${iy1} Z"
      fill="${color}" opacity="0.9"/>`;
    angle += slice;
  });

  document.getElementById('donut-svg').innerHTML = paths +
    `<text x="${cx}" y="${cy - 4}" text-anchor="middle" fill="#e2e8f0" font-size="16" font-weight="700">${total}</text>
     <text x="${cx}" y="${cy + 14}" text-anchor="middle" fill="#64748b" font-size="9">TOTAL</text>`;

  document.getElementById('donut-legend').innerHTML = labels.map((l, i) =>
    `<div class="legend-item">
       <div class="legend-dot" style="background:${DONUT_COLORS[l] || '#94a3b8'}"></div>
       <span>${l}: ${values[i]}</span>
     </div>`
  ).join('');
}

// ── Main refresh ──────────────────────────────────────────────────────────────
async function refresh() {
  try {
    const [metrics, jobs, workers, obs] = await Promise.all([
      fetch('/metrics').then(r => r.json()),
      fetch('/jobs').then(r => r.json()),
      fetch('/workers').then(r => r.json()),
      fetch('/observability').then(r => r.json()),
    ]);
    document.getElementById('error-banner').style.display = 'none';

    // Cards
    const s = metrics.jobs.by_status || {};
    document.getElementById('m-total').textContent     = metrics.jobs.total;
    document.getElementById('m-queued').textContent    = s.QUEUED    || 0;
    document.getElementById('m-completed').textContent = s.COMPLETED || 0;
    document.getElementById('m-running').textContent   = s.RUNNING   || 0;
    document.getElementById('m-failed').textContent    = (s.FAILED||0) + (s.DEAD||0);
    document.getElementById('m-rate').textContent      = metrics.jobs.success_rate_pct + '%';
    document.getElementById('m-avg').textContent       =
      metrics.jobs.avg_runtime_seconds != null ? metrics.jobs.avg_runtime_seconds + 's' : '—';
    document.getElementById('m-tput').textContent      = obs.throughput.avg_per_minute;
    document.getElementById('q-high').textContent      = metrics.queues.high;
    document.getElementById('q-medium').textContent    = metrics.queues.medium;
    document.getElementById('q-low').textContent       = metrics.queues.low;
    document.getElementById('q-dlq').textContent       = metrics.queues.dlq;

    // Alerts
    const offline = workers.filter(w => w.status === 'OFFLINE');
    const crashEl = document.getElementById('crash-alert');
    crashEl.style.display = offline.length ? 'block' : 'none';
    if (offline.length) crashEl.textContent =
      `⚠ ${offline.length} worker(s) OFFLINE: ${offline.map(w=>w.worker_id).join(', ')} — jobs recovering automatically`;

    const slow   = obs.slow_jobs || [];
    const slowEl = document.getElementById('slow-alert');
    slowEl.style.display = slow.length ? 'block' : 'none';
    if (slow.length) slowEl.textContent =
      `🐌 ${slow.length} slow job(s): ${slow.map(j=>j.id.substring(0,8)+'… ('+j.running_for_s+'s)').join(', ')}`;

    // Donut
    const statusLabels = Object.keys(s);
    svgDonut(statusLabels, statusLabels.map(k => s[k]));

    // Throughput chart
    const buckets = obs.throughput.buckets || [];
    svgBarChart(
      document.getElementById('tput-chart-wrap'),
      buckets.map(b => b.minute.substring(11,16)),
      buckets.map(b => b.count),
      '#6366f1'
    );

    // Runtime by type chart
    const rt     = obs.runtime_by_type || {};
    const rtKeys = Object.keys(rt);
    svgBarChart(
      document.getElementById('runtime-chart-wrap'),
      rtKeys,
      rtKeys.map(k => rt[k].avg_s || 0),
      ['#a78bfa','#34d399','#fbbf24','#60a5fa']
    );

    // Worker jobs chart
    const wp = obs.worker_performance || [];
    svgBarChart(
      document.getElementById('worker-chart-wrap'),
      wp.map(w => w.worker_id),
      wp.map(w => w.jobs_processed),
      '#06b6d4'
    );

    // Worker cards
    document.getElementById('workers-grid').innerHTML = workers.length === 0
      ? '<div style="color:#4b5563;font-size:0.8rem">No workers registered</div>'
      : workers.map(w => {
          const perf = wp.find(p => p.worker_id === w.worker_id) || {};
          return `<div class="worker-card ${w.status==='OFFLINE'?'offline':''}">
            <div class="worker-header">
              <span class="worker-name">⚙ ${w.worker_id}</span>${badge(w.status)}
            </div>
            <div class="worker-stats">
              <div class="wstat"><span class="wlabel">Processed</span><span class="wvalue">${w.jobs_processed}</span></div>
              <div class="wstat"><span class="wlabel">Success</span><span class="wvalue">${perf.success_rate??'—'}%</span></div>
              <div class="wstat"><span class="wlabel">Avg(s)</span><span class="wvalue">${perf.avg_runtime_s??'—'}</span></div>
            </div>
            <div>${hbBadge(w)}</div>
          </div>`;
        }).join('');

    // Runtime table
    const maxAvg = Math.max(...rtKeys.map(k => rt[k].avg_s||0), 1);
    document.getElementById('runtime-tbody').innerHTML = rtKeys.length === 0
      ? '<tr><td colspan="6" style="color:#4b5563">No completed jobs yet</td></tr>'
      : rtKeys.map(k => {
          const r = rt[k], pct = Math.round((r.avg_s||0)/maxAvg*100);
          return `<tr><td>${k}</td><td>${r.count}</td><td>${r.avg_s??'—'}</td>
            <td>${r.min_s??'—'}</td><td>${r.max_s??'—'}</td>
            <td style="min-width:120px"><div class="prog-bar"><div class="prog-fill" style="width:${pct}%"></div></div></td></tr>`;
        }).join('');

    // Recent jobs
    document.getElementById('jobs-tbody').innerHTML = jobs.length === 0
      ? '<tr><td colspan="7" style="color:#4b5563">No jobs yet</td></tr>'
      : jobs.slice(0,20).map(j => `<tr>
          <td class="mono">${j.id.substring(0,8)}…</td><td>${j.type}</td><td>${j.priority}</td>
          <td>${badge(j.status)}</td><td class="mono">${j.worker_id||'—'}</td>
          <td>${j.retry_count}</td><td>${fmtTime(j.created_at)}</td></tr>`).join('');

    document.getElementById('last-updated').textContent = 'Updated ' + new Date().toLocaleTimeString();

  } catch(e) {
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
