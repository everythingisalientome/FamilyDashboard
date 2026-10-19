// Admin "Settings (.env)": drift banner, add-feed / add-person helpers and the
// staged-changes bar (Review → dry-run, Save, Save & restart, Discard).

window.EnvBar = (() => {
  const $ = (id) => document.getElementById(id);
  const E = () => window.EnvEdit;
  const staged = () => E().state.staged;
  const count = () => Object.keys(staged()).length;

  async function post(url, body) {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const json = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(json.detail ? JSON.stringify(json.detail) : `HTTP ${res.status}`);
    return json.data;
  }

  function update() {
    const n = count();
    $("env-bar").hidden = n === 0;
    document.body.classList.toggle("env-bar-open", n > 0);
    $("env-count").textContent = `${n} staged change${n === 1 ? "" : "s"}`;
    $("env-review").hidden = true; // any edit makes an earlier review stale
    const restart = $("env-save-restart");
    const can = E().state.view && E().state.view.can_restart;
    restart.disabled = !can;
    restart.title = can ? "Save, then restart the service so the change applies"
      : "Not running as the NSSM service — Save, then restart the dev server by hand";
  }

  function drift(d) {
    const box = $("env-drift");
    box.replaceChildren();
    const el = E().el;
    if (d.missing_in_env.length) {
      const add = el("button", { class: "imp-btn", textContent: "Add with defaults" });
      add.disabled = d.missing_in_env.every((k) => k in staged());
      add.addEventListener("click", () => {
        for (const k of d.missing_in_env) E().stage(k, E().find(k).default);
        E().render();
      });
      const n = d.missing_in_env.length;
      box.append(el("p", {}, `${n} key${n === 1 ? "" : "s"} from .env.example ${n === 1 ? "is" : "are"} not in .env: `,
        el("span", { class: "mono", textContent: d.missing_in_env.join(", ") }), " ", add));
    }
    if (d.unknown_in_env.length) {
      const n = d.unknown_in_env.length;
      box.append(el("p", {}, `${n} key${n === 1 ? "" : "s"} in .env ${n === 1 ? "is" : "are"} not in .env.example: `,
        el("span", { class: "mono", textContent: d.unknown_in_env.join(", ") })));
    }
    box.hidden = !box.childNodes.length;
  }

  function diffList(diff) {
    const el = E().el;
    const show = (v) => (v == null ? "(absent)" : v === "" ? "(blank)" : v);
    const rows = Object.entries(diff).map(([k, d]) => el("li", {},
      el("span", { class: "mono env-diff-key", textContent: k }), ": ",
      el("span", { class: "env-old", textContent: show(d.old) }), " → ",
      el("span", { class: d.new == null ? "env-old" : "env-newv", textContent: d.new == null ? "(removed)" : show(d.new) })));
    return el("ul", { class: "env-diff" }, ...rows);
  }

  function showReview(data) {
    const el = E().el;
    const box = $("env-review");
    const verdict = data.ok
      ? el("p", { class: "env-ok", textContent: "✓ Dry-run passed — the server boots with these settings." })
      : el("p", { class: "env-bad", textContent: "✗ Dry-run failed — this would not be saved." });
    box.replaceChildren(el("h3", { textContent: "Review" }), diffList(data.diff), verdict);
    if (data.stderr_tail) box.append(el("pre", { class: "env-stderr", textContent: data.stderr_tail }));
    box.hidden = false;
  }

  function result(text, ok) {
    const p = $("env-result");
    p.textContent = text;
    p.className = `imp-result ${ok ? "ok" : "err"}`;
    p.hidden = false;
  }

  async function busy(fn) {
    const btns = ["env-review-btn", "env-save", "env-save-restart", "env-discard"].map($);
    const was = btns.map((b) => b.disabled);
    btns.forEach((b) => { b.disabled = true; });
    try {
      await fn();
    } catch (err) {
      result(`Request failed: ${err.message}`, false);
    } finally {
      btns.forEach((b, i) => { b.disabled = was[i]; });
    }
  }

  const review = () => busy(async () => {
    showReview(await post("/api/admin/env/validate", { changes: staged() }));
  });

  const save = (restart) => busy(async () => {
    const boot = await bootId();
    const data = await post("/api/admin/env/save", { changes: staged(), restart });
    if (!data.ok) {
      showReview(data);
      result("Save refused: the dry-run failed, nothing was written.", false);
      return;
    }
    for (const k of Object.keys(staged())) delete staged()[k];
    if (data.restarting) return waitForRestart(boot);
    const backup = data.backup ? ` Backup: ${data.backup}.` : "";
    const apply = E().state.view.can_restart
      ? "Restart the service to apply (nssm restart FamilyDashboard)."
      : `Not running as the NSSM service: ${data.note || "restart the dev server by hand"} to apply.`;
    result(`Saved .env.${backup} ${apply}`, true);
    await E().load();
  });

  async function bootId() {
    const res = await fetch("/healthz", { cache: "no-store" });
    return (await res.json()).boot;
  }

  // The old process answers for ~1 s after the save, so wait for a new boot id.
  async function waitForRestart(oldBoot) {
    $("env-restarting").hidden = false;
    const started = Date.now();
    for (;;) {
      await new Promise((r) => setTimeout(r, 2000));
      try {
        if ((await bootId()) !== oldBoot) return window.location.reload();
      } catch { /* down mid-restart */ }
      if (Date.now() - started > 60000) {
        $("env-restarting").textContent =
          "Still restarting after 60 s… check: nssm status FamilyDashboard (data\\logs\\dashboard.err.log)";
      }
    }
  }

  function discard() {
    if (!window.confirm(`Discard ${count()} staged change(s)?`)) return;
    for (const k of Object.keys(staged())) delete staged()[k];
    E().render();
  }

  // Add-feed / add-person helpers: stage a whole CAL_<KEY>_* / PERSON_<KEY>_* set.
  function helper(formId, prefix, anchor, fields) {
    const form = $(formId);
    form.addEventListener("submit", (ev) => {
      ev.preventDefault();
      const f = new FormData(form);
      const key = String(f.get("key")).trim().toUpperCase().replace(/[^A-Z0-9_]/g, "_");
      const name = `${prefix}_${key}`;
      if (!key || E().find(`${name}_${anchor}`) || `${name}_${anchor}` in staged()) {
        window.alert(`${name}_${anchor} already exists (or the key is blank).`);
        return;
      }
      for (const [field, suffix] of fields) E().stage(`${name}_${suffix}`, String(f.get(field) || "").trim());
      form.reset();
      form.closest("details").open = false;
      E().render();
    });
  }

  function start() {
    $("env-review-btn").addEventListener("click", review);
    $("env-save").addEventListener("click", () => save(false));
    $("env-save-restart").addEventListener("click", () => save(true));
    $("env-discard").addEventListener("click", discard);
    helper("env-add-feed", "CAL", "URL",
      [["url", "URL"], ["label", "LABEL"], ["color", "COLOR"], ["order", "ORDER"]]);
    helper("env-add-person", "PERSON", "LABEL", [["label", "LABEL"], ["color", "COLOR"],
      ["order", "ORDER"], ["feeds", "FEEDS"], ["keywords", "KEYWORDS"]]);
    E().load().catch((err) => {
      $("env-sections").textContent = `Settings unreachable (${err.message})`;
    });
  }

  return { update, drift, start };
})();

window.EnvBar.start();
