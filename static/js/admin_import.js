// Admin "Add events": paste extraction JSON -> validate -> review -> commit to
// the family Google Calendar. Vanilla JS, no framework. The server re-checks
// every row on commit; this page only decides which rows are ticked.

(() => {
  const $ = (id) => document.getElementById(id);
  let rows = []; // validate results, each with .include / .deleteOld / edits

  function el(tag, attrs = {}, ...kids) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (k === "class") node.className = v;
      else if (k in node) node[k] = v;
      else node.setAttribute(k, v);
    }
    for (const kid of kids) if (kid != null) node.append(kid);
    return node;
  }

  async function post(url, body) {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const json = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(json.detail ? String(json.detail) : `HTTP ${res.status}`);
    return json.data;
  }

  async function loadPersons() {
    const select = $("imp-person");
    let persons = [];
    try {
      const res = await fetch("/api/events?days=1", { cache: "no-store" });
      persons = (await res.json()).data.persons || [];
    } catch {
      /* the Family option still works */
    }
    for (const p of persons) select.append(el("option", { value: p.key, textContent: p.label }));
    select.append(el("option", { value: "family", textContent: "Family" }));
  }

  // The JSON may arrive wrapped in a markdown fence or with prose around it.
  function parsePaste(text) {
    const start = text.indexOf("[");
    const end = text.lastIndexOf("]");
    if (start < 0 || end < start) throw new Error("no JSON array found");
    return JSON.parse(text.slice(start, end + 1));
  }

  async function validate() {
    const note = $("imp-note");
    $("imp-result").hidden = true;
    let events;
    try {
      events = parsePaste($("imp-json").value);
    } catch (err) {
      note.textContent = `Can't read that: ${err.message}`;
      return;
    }
    note.textContent = "Checking…";
    $("imp-validate").disabled = true;
    try {
      const data = await post("/api/admin/import/validate", {
        person: $("imp-person").value || null,
        events,
      });
      rows = data.rows.map((r) => ({
        ...r,
        include: r.ok && !r.exists && !r.past,
        deleteOld: Boolean(r.supersedes_id),
      }));
      const bad = rows.filter((r) => !r.ok).length;
      note.textContent = `${rows.length} rows${bad ? ` · ${bad} with problems` : ""}`;
      render();
    } catch (err) {
      note.textContent = `Validate failed: ${err.message}`;
    } finally {
      $("imp-validate").disabled = false;
    }
  }

  function status(r) {
    if (!r.ok) return el("span", { class: "chip chip-err", textContent: r.errors.join("; ") });
    if (r.exists) return el("span", { class: "chip chip-exists", textContent: "already on calendar" });
    const chip = r.past
      ? el("span", { class: "chip chip-past", textContent: "past" })
      : el("span", { class: "chip chip-ok", textContent: "ok" });
    if (!r.warnings.length) return chip;
    return el("span", {}, chip, el("span", { class: "chip-warn", textContent: r.warnings.join("; ") }));
  }

  function timeText(n) {
    if (n.all_day) return n.end_date ? `all day → ${n.end_date}` : "all day";
    return n.end_time ? `${n.start_time}–${n.end_time}` : n.start_time;
  }

  function render() {
    const box = $("imp-rows");
    box.replaceChildren();
    for (const r of rows) {
      const n = r.normalised || {};
      const locked = !r.ok || r.exists;
      const tick = el("input", { type: "checkbox", checked: r.include, disabled: locked });
      tick.addEventListener("change", () => { r.include = tick.checked; count(); });
      const dateIn = el("input", { type: "date", value: n.date || "", disabled: locked, class: "imp-input" });
      dateIn.addEventListener("change", () => { n.date = dateIn.value; });
      const titleIn = el("input", { type: "text", value: n.title || "", disabled: locked, class: "imp-input", maxLength: 80 });
      titleIn.addEventListener("input", () => { n.title = titleIn.value; });

      let replaces = null;
      if (r.supersedes_id) {
        const del = el("input", { type: "checkbox", checked: r.deleteOld });
        del.addEventListener("change", () => { r.deleteOld = del.checked; count(); });
        replaces = el("label", { class: "imp-replaces" }, del,
          ` replaces ${n.supersedes.date} — delete old`);
      }

      box.append(el("div", { class: `imp-row${locked ? " locked" : ""}` },
        el("label", { class: "imp-tick" }, tick),
        el("div", { class: "imp-date" }, dateIn),
        el("div", {
          class: "imp-time muted",
          textContent: n.all_day == null ? "" : timeText(n),
          "data-who": `${n.person || "—"} · ${n.kind || "—"}`, // phone layout's meta line
        }),
        el("div", { class: "imp-title" }, titleIn, replaces),
        el("div", { class: "imp-person muted", textContent: n.person || "—" }),
        el("div", { class: "imp-kind muted", textContent: n.kind || "—" }),
        el("div", { class: "imp-status" }, status(r)),
      ));
    }
    $("imp-review").hidden = rows.length === 0;
    count();
  }

  function count() {
    const adds = rows.filter((r) => r.include).length;
    const dels = rows.filter((r) => r.supersedes_id && r.deleteOld && r.include).length;
    const btn = $("imp-commit");
    btn.textContent = `Add ${adds} event${adds === 1 ? "" : "s"} to calendar` +
      (dels ? ` (delete ${dels} old)` : "");
    btn.disabled = adds === 0;
  }

  async function commit() {
    const picked = rows.filter((r) => r.include);
    const body = {
      rows: picked.map((r) => r.normalised),
      delete_ids: picked.filter((r) => r.supersedes_id && r.deleteOld).map((r) => r.supersedes_id),
    };
    const btn = $("imp-commit");
    btn.disabled = true;
    btn.textContent = "Adding…";
    const out = $("imp-result");
    try {
      const d = await post("/api/admin/import/commit", body);
      let line = `${d.created} added · ${d.exists} already there`;
      if (d.deleted) line += ` · ${d.deleted} old deleted`;
      if (d.errors.length) line += ` · problems: ${d.errors.join("; ")}`;
      out.textContent = `${line}. The wall updates within a few minutes.`;
      out.className = `imp-result ${d.errors.length ? "err" : "ok"}`;
      $("imp-json").value = "";
      $("imp-note").textContent = "";
      rows = [];
      render();
    } catch (err) {
      out.textContent = `Add failed: ${err.message}`;
      out.className = "imp-result err";
      count();
    }
    out.hidden = false;
  }

  $("imp-validate").addEventListener("click", validate);
  $("imp-commit").addEventListener("click", commit);
  loadPersons();
})();
