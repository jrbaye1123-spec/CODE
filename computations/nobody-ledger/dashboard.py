"""Nobody Ledger Dashboard — FastAPI/uvicorn app.

Usage:
    cd ~/nobody-ledger
    python -m uvicorn dashboard:app --host 0.0.0.0 --port 8090
"""

import hashlib
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

HERE = Path(__file__).resolve().parent
CHAIN_PATH = HERE / "nobody_chain.json"

app = FastAPI(title="Nobody Ledger Dashboard")

# ── Cached chain data ────────────────────────────────────────────────────────
_chain_cache: dict | None = None
_chain_mtime: float = 0.0


def _load_chain() -> dict:
    """Load nobody_chain.json, caching until file changes."""
    global _chain_cache, _chain_mtime
    mtime = CHAIN_PATH.stat().st_mtime if CHAIN_PATH.exists() else 0.0
    if _chain_cache is not None and mtime == _chain_mtime:
        return _chain_cache
    if CHAIN_PATH.exists():
        _chain_cache = json.loads(CHAIN_PATH.read_text())
        _chain_mtime = mtime
    else:
        _chain_cache = {"entries": [], "count": 0, "nullified_indices": []}
    return _chain_cache


# ── HTML ─────────────────────────────────────────────────────────────────────

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Nobody Ledger — Hash Chain Dashboard</title>
<style>
:root {
  --bg: #0d0d0d; --surface: #1a1a1a; --border: #2a2a2a;
  --text: #d4d4d4; --text-dim: #666; --accent: #c4a35a;
  --danger: #c0392b; --genesis: #e6c97a; --green: #27ae60;
}
* { margin:0; padding:0; box-sizing:border-box; }
body {
  background: var(--bg); color: var(--text);
  font-family: 'Fira Code', 'Cascadia Code', 'JetBrains Mono', monospace;
  height: 100vh; display:flex; flex-direction:column; overflow:hidden;
}
header {
  background: var(--surface); border-bottom: 1px solid var(--border);
  padding: 12px 24px; display:flex; justify-content:space-between; align-items:center;
}
header h1 { font-size: 18px; font-weight: 600; color: var(--genesis); letter-spacing: 1px; }
header .status { font-size: 12px; color: var(--text-dim); }
header .status span { color: var(--green); }
main { display:flex; flex:1; overflow:hidden; }
#timeline-panel {
  width: 380px; min-width: 380px; background: var(--surface);
  border-right: 1px solid var(--border); overflow-y: auto; padding: 16px 0;
}
#timeline-panel::-webkit-scrollbar { width: 4px; }
#timeline-panel::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }
.entry {
  padding: 10px 20px; cursor:pointer; border-left:3px solid transparent;
  transition: background .15s, border-color .15s;
}
.entry:hover { background: rgba(255,255,255,.03); }
.entry.active { border-left-color: var(--accent); }
.entry.genesis { border-left-color: var(--genesis); }
.entry.genesis .entry-index { color: var(--genesis); text-shadow: 0 0 8px rgba(230,201,122,.4); }
.entry.nullified { opacity: .35; }
.entry.nullified .entry-how { text-decoration: line-through; }
.entry.selected { background: rgba(196,163,90,.1); }
.entry-index { font-size: 11px; color: var(--text-dim); margin-bottom: 2px; }
.entry-header { display:flex; align-items:center; gap:8px; margin-bottom:3px; }
.entry-entity { font-size: 12px; color: var(--text); max-width:200px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.entry-badge { font-size:9px; padding:1px 6px; border-radius:3px; text-transform:uppercase; letter-spacing:.5px; white-space:nowrap; }
.badge-genesis { background: rgba(230,201,122,.15); color: var(--genesis); }
.badge-decree { background: rgba(196,163,90,.15); color: var(--accent); }
.badge-nullify { background: rgba(192,57,43,.15); color: var(--danger); }
.badge-intrusion { background: rgba(192,57,43,.2); color: var(--danger); }
.badge-witness { background: rgba(39,174,96,.15); color: var(--green); }
.entry-how { font-size: 11px; color: var(--text-dim); margin-top: 2px; }
.entry-hash { font-size: 10px; color: var(--text-dim); font-family: monospace; }
#detail-panel { flex:1; overflow-y:auto; padding:24px; }
.witness-card { background: var(--surface); border:1px solid var(--border); border-radius:6px; padding:24px; max-width:700px; }
.witness-card h2 { font-size: 16px; color: var(--accent); margin-bottom: 16px; }
.witness-row { display:flex; padding:8px 0; border-bottom:1px solid var(--border); }
.witness-row:last-child { border-bottom:none; }
.witness-label { width: 140px; color: var(--text-dim); font-size: 12px; flex-shrink:0; }
.witness-value { font-size: 12px; word-break:break-all; color: var(--text); }
.witness-value.hash { font-family: monospace; font-size: 11px; }
.verify-row { margin-top:16px; padding-top:16px; border-top:1px solid var(--border); display:flex; align-items:center; gap:8px; }
.verify-indicator { width:16px; height:16px; border-radius:50%; display:inline-block; }
.verify-pass { background: var(--green); box-shadow: 0 0 8px rgba(39,174,96,.4); }
.verify-fail { background: var(--danger); box-shadow: 0 0 8px rgba(192,57,43,.4); }
.verify-btn {
  background: var(--accent); color: var(--bg); border:none;
  padding: 8px 20px; border-radius:4px; cursor:pointer;
  font-family: inherit; font-size: 12px; font-weight: 600; margin-top: 12px;
}
.verify-btn:hover { opacity: .9; }
.arrow-link { text-align:center; color: var(--accent); font-size:20px; padding:8px 0; }
#stats-bar {
  background: var(--surface); border-top:1px solid var(--border);
  padding: 12px 24px; display:flex; gap:32px; align-items:center; font-size:12px; flex-wrap:wrap;
}
.stat { display:flex; align-items:center; gap:6px; }
.stat-label { color: var(--text-dim); }
.stat-value { font-weight: 600; }
.stat-value.gold { color: var(--accent); }
.stat-value.red { color: var(--danger); }
.stat-value.green { color: var(--green); }
.lawvere-quote { margin-left:auto; color: var(--text-dim); font-style:italic; font-size:11px; white-space:nowrap; }
.loading { padding:40px; text-align:center; color: var(--text-dim); }
.error { padding:40px; text-align:center; color: var(--danger); }
</style>
</head>
<body>
<header>
  <h1>&#9672; NOBODY LEDGER</h1>
  <div class="status">chain: <span id="chain-status">loading</span></div>
</header>
<main>
  <div id="timeline-panel"><div class="loading">loading chain...</div></div>
  <div id="detail-panel"><div class="loading">select an entry</div></div>
</main>
<div id="stats-bar"></div>

<script>
let chainData = null;

async function loadChain() {
  try {
    const resp = await fetch('/api/chain');
    chainData = await resp.json();
    document.getElementById('chain-status').innerHTML = '<span>live</span> &middot; ' + chainData.count + ' entries';
    renderTimeline();
    renderStats();
  } catch(e) {
    document.getElementById('chain-status').textContent = 'offline';
    document.getElementById('timeline-panel').innerHTML = '<div class="error">Failed to load chain: ' + e.message + '</div>';
  }
}

function renderTimeline() {
  var panel = document.getElementById('timeline-panel');
  var nulled = new Set(chainData.nullified_indices || []);
  var html = '';
  chainData.entries.forEach(function(entry, i) {
    var isNulled = nulled.has(entry.index) || (entry.voided_by !== undefined);
    var isGenesis = entry.event === 'genesis';
    var cls = ['entry', isNulled ? 'nullified' : 'active', isGenesis ? 'genesis' : ''].filter(Boolean).join(' ');
    var badgeClass = 'badge-' + entry.event;
    var entity = entry.entity === 'the void' ? '\u2300 the void' : entry.entity.substring(0, 14) + (entry.entity.length > 14 ? '...' : '');
    html += '<div class="' + cls + '" onclick="selectEntry(' + i + ')" data-index="' + i + '">';
    html += '<div class="entry-index">#' + entry.index + ' \u00b7 ' + formatTime(entry.timestamp) + '</div>';
    html += '<div class="entry-header">';
    html += '<span class="entry-entity">' + escapeHtml(entity) + '</span>';
    html += '<span class="entry-badge ' + badgeClass + '">' + entry.event + '</span>';
    html += '</div>';
    html += '<div class="entry-how">' + escapeHtml(entry.how) + '</div>';
    html += '<div class="entry-hash">' + (entry.hash || '').substring(0, 14) + '</div>';
    html += '</div>';
  });
  panel.innerHTML = html;
}

function selectEntry(i) {
  document.querySelectorAll('.entry').forEach(function(e) { e.classList.remove('selected'); });
  document.querySelector('[data-index="' + i + '"]').classList.add('selected');
  renderDetail(i);
}

function renderDetail(i) {
  var panel = document.getElementById('detail-panel');
  var entry = chainData.entries[i];
  var prev = i > 0 ? chainData.entries[i - 1] : null;
  var nulled = new Set(chainData.nullified_indices || []);
  var isNulled = nulled.has(entry.index) || (entry.voided_by !== undefined);
  var prevHash = entry.previous_hash || (prev ? prev.hash : '');

  var html = '<div class="witness-card">';
  html += '<h2>Entry #' + entry.index + '</h2>';
  html += row('Timestamp', formatTime(entry.timestamp));
  html += row('Entity', escapeHtml(entry.entity));
  html += row('Event', '<span class="entry-badge badge-' + entry.event + '">' + entry.event.toUpperCase() + '</span>');
  html += row('How', isNulled ? '<s>' + escapeHtml(entry.how) + '</s>' : escapeHtml(entry.how));

  if (prev) {
    html += '<div class="arrow-link">\u2193</div>';
    html += row('Previous Hash', '<span class="hash">' + prevHash.substring(0, 14) + '...</span>');
    html += row('This Hash', '<span class="hash">' + (entry.hash || '').substring(0, 14) + '...</span>');
  }

  if (entry.hash) {
    html += row('Full Hash', '<span class="hash" style="font-size:10px">' + entry.hash + '</span>');
  }

  if (entry.voided_by !== undefined) {
    html += row('Voided By', 'Entry #' + entry.voided_by + ' <span class="entry-badge badge-nullify">VOIDED</span>');
  }

  // Hash verification happens server-side now
  html += '<div id="entry-verify-' + i + '" class="verify-row" style="display:none"></div>';
  html += '<button class="verify-btn" onclick="verifyEntry(' + i + ')">Verify This Link</button>';
  html += '<button class="verify-btn" onclick="verifyFullChain()" style="margin-left:8px">Verify Full Chain</button>';
  html += '<div id="full-verify-result" style="margin-top:8px;font-size:12px;"></div>';
  html += '</div>';
  panel.innerHTML = html;
}

function row(label, value) {
  return '<div class="witness-row"><span class="witness-label">' + label + '</span><span class="witness-value">' + value + '</span></div>';
}

async function verifyEntry(i) {
  var entry = chainData.entries[i];
  if (i === 0) {
    showVerifyResult('entry-verify-' + i, true, 'Genesis entry — no previous hash to verify');
    return;
  }
  var prev = chainData.entries[i - 1];
  var prevHash = entry.previous_hash || prev.hash;
  try {
    var resp = await fetch('/api/verify', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({index: entry.index, prev_hash: prevHash, hash: entry.hash,
        timestamp: entry.timestamp, entity: entry.entity, event: entry.event, how: entry.how})
    });
    var data = await resp.json();
    showVerifyResult('entry-verify-' + i, data.valid, data.valid ? 'SHA256 link verified' : 'SHA256 MISMATCH');
  } catch(e) {
    showVerifyResult('entry-verify-' + i, false, 'Verification error: ' + e.message);
  }
}

async function verifyFullChain() {
  var resultEl = document.getElementById('full-verify-result');
  resultEl.textContent = 'Verifying...';
  try {
    var resp = await fetch('/api/verify-full');
    var data = await resp.json();
    resultEl.innerHTML = data.valid
      ? '<span style="color:var(--green)">\u2713 Full chain verified — ' + data.links + ' links intact</span>'
      : '<span style="color:var(--danger)">\u2717 Chain integrity broken at link ' + data.failed_at + '</span>';
  } catch(e) {
    resultEl.innerHTML = '<span style="color:var(--danger)">Verification error: ' + e.message + '</span>';
  }
}

function showVerifyResult(id, ok, msg) {
  var el = document.getElementById(id);
  el.style.display = 'flex';
  el.innerHTML = '<span class="verify-indicator ' + (ok ? 'verify-pass' : 'verify-fail') + '"></span><span>' + msg + '</span>';
}

function renderStats() {
  var bar = document.getElementById('stats-bar');
  var nulled = new Set(chainData.nullified_indices || []);
  var active = 0, nf = 0, events = {};
  chainData.entries.forEach(function(e) {
    if (nulled.has(e.index) || e.voided_by !== undefined) nf++;
    else active++;
    events[e.event] = (events[e.event] || 0) + 1;
  });
  var evtStr = Object.entries(events).map(function(kv) { return kv[0] + '(' + kv[1] + ')'; }).join(' ');
  bar.innerHTML =
    '<div class="stat"><span class="stat-label">Total</span><span class="stat-value">' + chainData.count + '</span></div>' +
    '<div class="stat"><span class="stat-label">Active</span><span class="stat-value green">' + active + '</span></div>' +
    '<div class="stat"><span class="stat-label">Nullified</span><span class="stat-value red">' + nf + '</span></div>' +
    '<div class="stat"><span class="stat-label">Events</span><span class="stat-value gold">' + evtStr + '</span></div>' +
    '<div class="stat"><span class="stat-label">Head</span><span class="stat-value" style="font-size:10px">' + (chainData.entries[chainData.entries.length-1].hash || '').substring(0,14) + '</span></div>' +
    '<div class="lawvere-quote">' + nf + ' entries voided. The gap does not close.</div>';
}

function formatTime(ts) {
  try {
    var d = new Date(ts);
    return d.toLocaleDateString('en-US', {month:'short',day:'numeric'}) + ' ' +
           d.toLocaleTimeString('en-US', {hour:'2-digit',minute:'2-digit'});
  } catch(e) { return ts; }
}

function escapeHtml(s) { var d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

loadChain();
</script>
</body>
</html>"""


# ── Routes ───────────────────────────────────────────────────────────────────


@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the Nobody Ledger dashboard."""
    return DASHBOARD_HTML


@app.get("/api/chain")
async def api_chain():
    """Return the full chain as JSON."""
    return JSONResponse(_load_chain())


@app.post("/api/verify")
async def api_verify_entry(data: dict):
    """Verify a single chain link."""
    entry = data
    computed = _compute_hash(entry)
    valid = computed == entry.get("hash", "")
    return JSONResponse({"valid": valid, "computed": computed})


@app.get("/api/verify-full")
async def api_verify_full():
    """Verify every link in the chain."""
    chain = _load_chain()
    entries = chain.get("entries", [])
    verified = 0
    for i in range(1, len(entries)):
        prev = entries[i - 1]
        entry = entries[i]
        prev_hash = entry.get("previous_hash") or prev.get("hash", "")
        entry_data = {
            "index": entry["index"],
            "timestamp": entry["timestamp"],
            "entity": entry["entity"],
            "event": entry["event"],
            "how": entry["how"],
            "prev_hash": prev_hash,
        }
        computed = _compute_hash(entry_data)
        if computed != entry.get("hash", ""):
            return JSONResponse({
                "valid": False,
                "failed_at": i,
                "expected": entry.get("hash"),
                "computed": computed,
                "links": verified,
            })
        verified += 1
    return JSONResponse({"valid": True, "links": verified})


# ── Hash computation ─────────────────────────────────────────────────────────


def _compute_hash(entry: dict) -> str:
    """Recompute the SHA256 hash for a chain entry."""
    prev_hash = entry.get("prev_hash", "")
    data = (
        f"{entry['index']}|{entry['timestamp']}|{entry['entity']}|"
        f"{entry['event']}|{entry['how']}|{prev_hash}"
    )
    return hashlib.sha256(data.encode()).hexdigest()
