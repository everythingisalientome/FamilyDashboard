// Admin page: poll status + logs, render the tables, wire refresh/remove
// buttons. Vanilla JS, no framework — same rule as the rest of static/.

const POLL_MS = 5000;
const LOG_TAIL_LINES = 800;

async function refreshAll() {
  await Promise.all([loadStatus(), loadLogs(), loadLogFiles()]);
}

// --- Status ----------------------------------------------------------------

async function loadStatus() {
  try {
    const res = await fetch("/api/admin/status", { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const { data } = await res.json();
    renderButtons(data.fetchers || []);
    renderRows(data.jobs || []);
    note("");
  } catch (err) {
    note(`status unreachable (${err.message}) — retrying`);
  }
}

function renderButtons(fetchers) {
  const box = document.getElementById("refresh-buttons");
  const want = fetchers.join(",");
  if (box.dataset.for === want) return; // don't stomp a mid-click button
  box.dataset.for = want;
  box.innerHTML = "";
  for (const name of fetchers) {
    const btn = document.createElement("button");
    btn.className = "refresh";
    btn.textContent = name;
    btn.addEventListener("click", () => refresh(name, btn));
    box.appendChild(btn);
  }
}

async function refresh(name, btn) {
  btn.disabled = true;
  const label = btn.textContent;
  btn.textContent = `${name}…`;
  try {
    const res = await fetch(`/api/admin/refresh/${name}`, { method: "POST" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    btn.textContent = `${name} ✓`;
    setTimeout(refreshAll, 1500); // let the background fetch land, then refresh
  } catch (err) {
    btn.textContent = `${name} failed: ${err.message}`;
  } finally {
    setTimeout(() => {
      btn.textContent = label;
      btn.disabled = false;
    }, 2500);
  }
}

function renderRows(jobs) {
  const body = document.getElementById("status-rows");
  if (!jobs.length) {
    body.innerHTML = `<tr><td colspan="6" class="muted">No fetch jobs yet.</td></tr>`;
    return;
  }
  body.innerHTML = "";
  for (const j of jobs) {
    const tr = document.createElement("tr");
    if (j.orphaned) tr.classList.add("orphaned");

    const state = j.last_success_utc ? (j.stale ? "stale" : "fresh") : "unknown";
    const showId = j.label !== j.job;

    tr.innerHTML = `
      <td>
        <div class="job-cell">
          <span class="dot ${state}" title="${state}"></span>
          <span>
            <span class="job-name">${esc(j.label)}</span>
            ${showId ? `<span class="job-id">${esc(j.job)}</span>` : ""}
            ${j.orphaned ? `<span class="tag-orphan" title="No configured source produces this job — safe to clear">orphaned</span>` : ""}
          </span>
        </div>
      </td>
      <td class="src-cell">${sourceCell(j.source)}</td>
      <td class="nowrap">${freshness(j)}</td>
      <td class="nowrap">${j.last_attempt_utc ? ago(j.last_attempt_utc) : "<span class='muted'>—</span>"}</td>
      <td class="nowrap muted">${interval(j)}</td>
      <td>${errorCell(j)}</td>
    `;

    if (j.orphaned) {
      const btn = document.createElement("button");
      btn.className = "remove";
      btn.textContent = "✕ clear";
      btn.title = "Remove this stale status row (and any leftover events)";
      btn.addEventListener("click", () => removeJob(j.job, btn));
      tr.querySelector(".job-cell > span").appendChild(btn);
    }
    body.appendChild(tr);
  }
}

async function removeJob(job, btn) {
  if (!window.confirm(`Clear orphaned job "${job}"?`)) return;
  btn.disabled = true;
  try {
    const res = await fetch(`/api/admin/jobs/${encodeURIComponent(job)}`, {
      method: "DELETE",
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    loadStatus();
  } catch (err) {
    btn.textContent = `failed: ${err.message}`;
    btn.disabled = false;
  }
}

function sourceCell(url) {
  if (!url) return "<span class='muted'>manual / none</span>";
  return `<a href="${esc(url)}" target="_blank" rel="noopener" title="${esc(url)}">${esc(url)}</a>`;
}

function errorCell(j) {
  if (!j.last_error) return "<span class='muted'>—</span>";
  return `<span class="err">${esc(j.last_error)}</span>`;
}

function freshness(j) {
  if (!j.last_success_utc) return "<span class='muted'>never</span>";
  const cls = j.stale ? "err" : "";
  return `<span class="${cls}" title="${localTime(j.last_success_utc)}">${relative(j.age_seconds)}${j.stale ? " · stale" : ""}</span>`;
}

function interval(j) {
  if (j.interval_seconds == null) return "nightly";
  return `every ${duration(j.interval_seconds)}`;
}

function ago(iso) {
  const secs = (Date.now() - new Date(iso).getTime()) / 1000;
  return `<span title="${localTime(iso)}">${relative(secs)}</span>`;
}

// --- Logs ------------------------------------------------------------------

async function loadLogs() {
  const view = document.getElementById("log-view");
  try {
    const res = await fetch(`/api/admin/logs?lines=${LOG_TAIL_LINES}`, {
      cache: "no-store",
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const { data } = await res.json();
    document.getElementById("log-file").textContent = data.file;
    view.classList.remove("muted");
    if (!data.exists) {
      view.textContent = "(no log file yet — it appears on the first log line)";
      return;
    }
    view.textContent = data.text || "(empty)";
    const trunc = data.truncated ? ` (showing last ${data.line_count})` : "";
    document.getElementById("log-meta").textContent =
      `${data.line_count} lines${trunc}`;
    if (document.getElementById("log-follow").checked) {
      view.scrollTop = view.scrollHeight;
    }
  } catch (err) {
    document.getElementById("log-meta").textContent = `log unreachable (${err.message})`;
  }
}

async function loadLogFiles() {
  const list = document.getElementById("log-files");
  try {
    const res = await fetch("/api/admin/logs/files", { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const { data } = await res.json();
    if (!data.files.length) {
      list.innerHTML = "<li class='muted'>No log files yet.</li>";
      return;
    }
    list.innerHTML = "";
    for (const f of data.files) {
      const li = document.createElement("li");
      const tag = f.is_current ? " <span class='muted'>(current)</span>" : "";
      li.innerHTML =
        `<a href="/api/admin/logs/download?name=${encodeURIComponent(f.name)}">${esc(f.name)}</a>` +
        `<span class="muted"> — ${kb(f.size)}, ${localTime(f.modified_utc)}</span>${tag}`;
      list.appendChild(li);
    }
  } catch (err) {
    list.innerHTML = `<li class='muted'>file list unreachable (${esc(err.message)})</li>`;
  }
}

// --- formatting helpers ----------------------------------------------------

function relative(secs) {
  if (secs == null) return "—";
  if (secs < 60) return `${Math.round(secs)}s ago`;
  if (secs < 3600) return `${Math.round(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.round(secs / 3600)}h ago`;
  return `${Math.round(secs / 86400)}d ago`;
}

function duration(secs) {
  if (secs % 3600 === 0) return `${secs / 3600}h`;
  if (secs % 60 === 0) return `${secs / 60}m`;
  return `${secs}s`;
}

function kb(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function localTime(iso) {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function note(msg) {
  document.getElementById("poll-note").textContent = msg;
}

function start() {
  refreshAll();
  setInterval(refreshAll, POLL_MS);
}

start();
