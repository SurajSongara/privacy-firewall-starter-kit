"""The review UI page — fully self-contained HTML/CSS/JS (no CDN)."""

PAGE_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Privacy Firewall — Review</title>
<style>
  :root {
    --redact: #16803c; --ask: #b45309; --keep: #6b7280;
    --bg: #f5f5f4; --panel: #ffffff; --line: #d6d3d1; --text: #1c1917;
  }
  * { box-sizing: border-box; }
  body { margin: 0; font: 14px/1.45 system-ui, sans-serif; background: var(--bg); color: var(--text); }
  header {
    display: flex; align-items: center; gap: 16px; padding: 10px 16px;
    background: var(--panel); border-bottom: 1px solid var(--line);
    position: sticky; top: 0; z-index: 10;
  }
  header h1 { font-size: 15px; margin: 0; }
  header .meta { color: #78716c; font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  header .spacer { flex: 1; }
  .pill { padding: 2px 9px; border-radius: 999px; font-size: 12px; font-weight: 600; color: #fff; }
  .pill.redact { background: var(--redact); } .pill.ask { background: var(--ask); } .pill.keep { background: var(--keep); }
  button.apply {
    background: var(--redact); color: #fff; border: 0; border-radius: 6px;
    padding: 8px 18px; font-size: 14px; font-weight: 600; cursor: pointer;
  }
  button.apply:disabled { opacity: .5; cursor: default; }
  #banner {
    display: none; padding: 10px 16px; background: #dcfce7; color: #14532d;
    border-bottom: 1px solid #86efac; font-weight: 600; word-break: break-all;
  }
  main { display: flex; gap: 16px; padding: 16px; align-items: flex-start; justify-content: center; }
  #sidebar { width: 360px; flex-shrink: 0; position: sticky; top: 64px; max-height: calc(100vh - 90px); overflow-y: auto; }
  #sidebar.empty { display: none; }
  .empty-note {
    background: #fffbeb; border: 1px solid #fcd34d; color: #78350f;
    border-radius: 8px; padding: 14px 18px; margin: 0 auto 16px; max-width: 900px;
  }
  .group { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; margin-bottom: 12px; }
  .group h2 {
    display: flex; align-items: center; gap: 8px; font-size: 13px; margin: 0;
    padding: 8px 12px; border-bottom: 1px solid var(--line);
  }
  .group h2 .bulk { margin-left: auto; display: flex; gap: 6px; }
  .group h2 .bulk button {
    font-size: 11px; border: 1px solid var(--line); background: #fafaf9;
    border-radius: 4px; padding: 2px 8px; cursor: pointer;
  }
  .entry { padding: 8px 12px; border-bottom: 1px solid #f0efee; cursor: pointer; }
  .entry:last-child { border-bottom: 0; }
  .entry:hover { background: #fafaf9; }
  .entry .row1 { display: flex; align-items: center; gap: 8px; }
  .entry code { font-size: 13px; word-break: break-all; }
  .entry .page { color: #a8a29e; font-size: 11px; margin-left: auto; white-space: nowrap; }
  .entry .why { color: #78716c; font-size: 11px; margin-top: 3px; }
  .entry select { font-size: 12px; padding: 1px 4px; border-radius: 4px; border: 1px solid var(--line); }
  #pages { flex: 1; min-width: 0; max-width: 940px; }
  .page-wrap { position: relative; margin: 0 auto 20px; background: #fff; box-shadow: 0 1px 4px rgba(0,0,0,.15); }
  .page-wrap img { display: block; width: 100%; height: auto; }
  .overlay { position: absolute; border: 2px solid; border-radius: 2px; cursor: pointer; }
  .overlay.redact { border-color: var(--redact); background: rgba(22,128,60,.18); }
  .overlay.ask { border-color: var(--ask); background: rgba(180,83,9,.20); }
  .overlay.keep { border-color: var(--keep); background: rgba(107,114,128,.10); border-style: dashed; }
  .overlay:hover { filter: brightness(1.15); }
  .legend { color: #78716c; font-size: 12px; margin: 0 0 10px; }
</style>
</head>
<body>
<header>
  <h1>Privacy Firewall</h1>
  <span class="meta" id="meta"></span>
  <span class="spacer"></span>
  <span class="pill redact" id="count-redact">0</span>
  <span class="pill ask" id="count-ask">0</span>
  <span class="pill keep" id="count-keep">0</span>
  <button class="apply" id="apply">Apply &amp; export redacted PDF</button>
</header>
<div id="banner"></div>
<main>
  <aside id="sidebar"></aside>
  <section id="pages">
    <p class="legend">Click a box or use the sidebar to toggle. Green = will be redacted,
    amber = needs review (redacted unless you keep it), grey dashed = kept.</p>
  </section>
</main>
<script>
"use strict";
let PLAN = null;

async function api(path, body) {
  const opts = body ? {method: "POST", headers: {"Content-Type": "application/json"},
                       body: JSON.stringify(body)} : {};
  const res = await fetch(path, opts);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function esc(s) {
  return s.replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}

function render() {
  const counts = {redact: 0, ask: 0, keep: 0};
  PLAN.entries.forEach(e => counts[e.effective_action]++);
  for (const k of ["redact", "ask", "keep"]) {
    document.getElementById("count-" + k).textContent = counts[k] + " " + k;
  }
  document.getElementById("meta").textContent =
    PLAN.source + " · policy: " + PLAN.policy + " · " + PLAN.pipeline;
  document.getElementById("sidebar").classList.toggle("empty", PLAN.entries.length === 0);
  document.getElementById("apply").disabled = PLAN.entries.length === 0;
  renderEmptyNote();
  renderSidebar();
  renderOverlays();
}

function renderEmptyNote() {
  const existing = document.querySelector(".empty-note");
  if (existing) existing.remove();
  if (PLAN.entries.length > 0) return;
  const note = document.createElement("div");
  note.className = "empty-note";
  note.innerHTML = "<strong>No PII detected.</strong> Pipeline used: " + esc(PLAN.pipeline) +
    ". If this document is scanned and looks like it should have detections, restart with " +
    "<code>--ocr</code> (or <code>--ocr-engine rapidocr</code>).";
  const pages = document.getElementById("pages");
  pages.insertBefore(note, pages.firstChild);
}

function renderSidebar() {
  const groups = {};
  PLAN.entries.forEach(e => (groups[e.type] = groups[e.type] || []).push(e));
  const el = document.getElementById("sidebar");
  el.innerHTML = "";
  Object.keys(groups).sort().forEach(type => {
    const g = document.createElement("div");
    g.className = "group";
    g.innerHTML = `<h2>${type} <span style="color:#a8a29e">(${groups[type].length})</span>
      <span class="bulk">
        <button data-type="${type}" data-act="redact">redact all</button>
        <button data-type="${type}" data-act="keep">keep all</button>
      </span></h2>`;
    groups[type].forEach(e => {
      const row = document.createElement("div");
      row.className = "entry";
      row.innerHTML = `
        <div class="row1">
          <select data-id="${e.detection_id}">
            <option value="redact"${e.effective_action === "redact" ? " selected" : ""}>redact</option>
            <option value="keep"${e.effective_action === "keep" ? " selected" : ""}>keep</option>
          </select>
          <code>${esc(e.text)}</code>
          <span class="page">p.${e.page_number} · ${e.confidence.toFixed(2)}</span>
        </div>
        <div class="why">${esc(e.reasons.join(" · "))}</div>`;
      g.appendChild(row);
    });
    el.appendChild(g);
  });

  el.querySelectorAll("select").forEach(s =>
    s.addEventListener("change", () => decide(s.dataset.id, s.value)));
  el.querySelectorAll(".bulk button").forEach(b =>
    b.addEventListener("click", async () => {
      for (const e of PLAN.entries.filter(e => e.type === b.dataset.type)) {
        await decide(e.detection_id, b.dataset.act, true);
      }
      render();
    }));
}

function renderOverlays() {
  const el = document.getElementById("pages");
  el.querySelectorAll(".page-wrap").forEach(n => n.remove());
  PLAN.pages.forEach(p => {
    const wrap = document.createElement("div");
    wrap.className = "page-wrap";
    wrap.style.maxWidth = "900px";
    wrap.innerHTML = `<img src="/api/page/${p.page_number}" alt="page ${p.page_number}">`;
    PLAN.entries.filter(e => e.page_number === p.page_number).forEach(e => {
      const o = document.createElement("div");
      o.className = "overlay " + (e.decision ? e.decision : e.effective_action);
      o.title = `${e.type}: ${e.text}\\n${e.reasons.join("\\n")}`;
      o.style.left = (e.bbox.x0 / p.width * 100) + "%";
      o.style.top = (e.bbox.y0 / p.height * 100) + "%";
      o.style.width = ((e.bbox.x1 - e.bbox.x0) / p.width * 100) + "%";
      o.style.height = ((e.bbox.y1 - e.bbox.y0) / p.height * 100) + "%";
      o.addEventListener("click", () =>
        decide(e.detection_id, e.effective_action === "keep" ? "redact" : "keep"));
      wrap.appendChild(o);
    });
    el.appendChild(wrap);
  });
}

async function decide(id, decision, skipRender) {
  await api("/api/decision", {detection_id: id, decision: decision});
  const entry = PLAN.entries.find(e => e.detection_id === id);
  entry.decision = decision;
  entry.effective_action = decision;
  if (!skipRender) render();
}

document.getElementById("apply").addEventListener("click", async () => {
  const btn = document.getElementById("apply");
  btn.disabled = true;
  btn.textContent = "Applying…";
  try {
    const result = await api("/api/apply", {});
    const banner = document.getElementById("banner");
    banner.style.display = "block";
    banner.textContent = `Redacted PDF written: ${result.output_path} ` +
      `(${result.redactions} redactions). Review record: ${result.plan_path}`;
  } catch (err) {
    alert("Apply failed: " + err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "Apply & export redacted PDF";
  }
});

api("/api/plan").then(plan => { PLAN = plan; render(); });
</script>
</body>
</html>
"""
