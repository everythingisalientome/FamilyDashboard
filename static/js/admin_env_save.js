// Admin Settings tab: the per-sub-tab footer (Save / Revert), the unsaved-
// changes guard and the drift banner's one-click "Add missing keys". The add
// helpers are admin_env_helpers.js; restarting is the page-wide banner
// (admin_restart.js).

window.EnvSave = (() => {
  const $ = (id) => document.getElementById(id);
  const E = () => window.EnvEdit;
  const S = () => E().state;
  const count = () => Object.keys(S().staged).length;
  let busy = false;
  let last = null; // {ok, text, data?} — the footer's last result

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

  // Dry-run, then write just these keys; every other line of .env is untouched.
  async function write(changes) {
    const check = await post("/api/admin/env/validate", { changes });
    if (!check.ok) return check;
    return post("/api/admin/env/save", { changes, restart: false });
  }

  async function save() {
    if (!count() || busy) return false;
    busy = true;
    E().render();
    const changes = { ...S().staged };
    try {
      const data = await write(changes);
      if (!data.ok) {
        last = { ok: false, text: "Not saved: the dry-run failed, nothing was written.", data };
        return false;
      }
      S().staged = {};
      S().editing.clear();
      const n = Object.keys(changes).length;
      last = { ok: true, text: `Saved ${n} key${n === 1 ? "" : "s"}. Backup: ${data.backup || "none (new file)"}.` };
      await E().load();
      return true;
    } catch (err) {
      last = { ok: false, text: `Save failed: ${err.message}` };
      return false;
    } finally {
      busy = false;
      E().render();
    }
  }

  function revert() {
    S().staged = {};
    S().editing.clear();
    last = null;
    E().render();
  }

  // Save / Discard / Stay. Resolves true when it is fine to move on.
  async function resolveUnsaved() {
    const n = count();
    const answer = await window.AdminTabs.ask(
      `You have ${n} unsaved change${n === 1 ? "" : "s"} in "${S().sub}".`,
      [{ id: "save", label: "Save", primary: true }, { id: "discard", label: "Discard" },
        { id: "stay", label: "Stay" }], "stay");
    if (answer === "save") return save();
    if (answer === "discard") { revert(); return true; }
    return false;
  }

  async function switchSub(title) {
    if (title === S().sub || (E().dirty() && !(await resolveUnsaved()))) return;
    S().sub = title;
    S().editing.clear();
    last = null;
    E().render();
  }

  async function removeGroup(name, kind, tag) {
    const own = E().state.view.sections.flatMap((s) => s.keys).filter((k) => k.group === name);
    const answer = await window.AdminTabs.ask(
      `Remove ${kind.toLowerCase()} "${tag}"? Its ${own.length} keys are staged for removal; Save to apply.`,
      [{ id: "remove", label: "Remove", primary: true }, { id: "cancel", label: "Cancel" }], "cancel");
    if (answer !== "remove") return;
    for (const k of own) E().stage(k.key, null);
    for (const key of Object.keys(S().staged)) {
      if (key.startsWith(`${name}_`) && !E().find(key)) delete S().staged[key];
    }
    E().render();
  }

  function footer() {
    const el = E().el;
    const n = count();
    const saveBtn = el("button", { class: "imp-btn imp-primary", type: "button",
      textContent: busy ? "Saving…" : "Save", disabled: !n || busy });
    saveBtn.addEventListener("click", save);
    const revertBtn = el("button", { class: "imp-btn", type: "button", textContent: "Revert",
      disabled: !n || busy });
    revertBtn.addEventListener("click", revert);
    const box = el("div", { class: "env-footer" },
      el("div", { class: "env-footer-bar" },
        el("span", { class: "env-count", textContent: `${n} staged` }), saveBtn, revertBtn));
    if (last) {
      const msg = el("div", { class: `env-result ${last.ok ? "ok" : "err"}` }, el("p", { textContent: last.text }));
      if (last.data) msg.append(diffList(last.data.diff));
      if (last.data && last.data.stderr_tail) msg.append(el("pre", { class: "env-stderr", textContent: last.data.stderr_tail }));
      box.append(msg);
    }
    return box;
  }

  function diffList(diff) {
    const el = E().el;
    const show = (v) => (v == null ? "(absent)" : v === "" ? "(blank)" : v);
    return el("ul", { class: "env-diff" }, ...Object.entries(diff).map(([k, d]) => el("li", {},
      el("span", { class: "mono", textContent: k }), `: ${show(d.old)} → `,
      el("span", { class: "env-newv", textContent: d.new == null ? "(removed)" : show(d.new) }))));
  }

  // One click: write .env.example's defaults for every key .env lacks.
  async function addMissing(keys, btn) {
    btn.disabled = true;
    const changes = Object.fromEntries(keys.map((k) => [k, E().find(k).default ?? ""]));
    try {
      const data = await write(changes);
      if (!data.ok) throw new Error(data.stderr_tail || "dry-run failed");
      await E().load();
    } catch (err) {
      btn.disabled = false;
      btn.after(E().el("span", { class: "env-bad", textContent: ` Not added: ${err.message}` }));
    }
  }

  function drift(d) {
    const el = E().el;
    const box = $("env-drift");
    box.replaceChildren();
    if (d.missing_in_env.length) {
      const n = d.missing_in_env.length;
      const add = el("button", { class: "imp-btn", type: "button", textContent: "Add missing keys with defaults" });
      add.addEventListener("click", () => addMissing(d.missing_in_env, add));
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

  function start() {
    window.AdminTabs.setGuard(async (from) => from !== "settings" || !E().dirty() || resolveUnsaved());
    window.addEventListener("beforeunload", (ev) => {
      if (!E().dirty()) return;
      ev.preventDefault();
      ev.returnValue = "";
    });
    E().load().catch((err) => {
      $("env-pane").textContent = `Settings unreachable (${err.message})`;
    });
  }

  return { drift, footer, removeGroup, switchSub, start };
})();

window.EnvSave.start();
