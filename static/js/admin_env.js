// Admin "Settings (.env)": render every .env.example key by section and stage
// edits locally. Nothing is sent until Review / Save (admin_env_bar.js). The
// server dry-runs every save; this page only collects {KEY: value|null}.

window.EnvEdit = (() => {
  const $ = (id) => document.getElementById(id);
  const state = { view: null, staged: {}, open: new Set() };

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

  const keys = () => state.view.sections.flatMap((s) => s.keys);
  const find = (key) => keys().find((k) => k.key === key);

  async function load() {
    const res = await fetch("/api/admin/env", { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    state.view = (await res.json()).data;
    render();
  }

  // Stage one change; staging the live value (or removing an absent key) unstages.
  function stage(key, value) {
    const item = find(key);
    const live = item && item.in_env ? item.value : undefined;
    if (value === live || (value === null && live === undefined)) delete state.staged[key];
    else state.staged[key] = value;
    window.EnvBar.update();
  }

  function inputFor(item, value) {
    const k = item.key;
    if (/_COLOR$/.test(k)) {
      const text = el("input", { type: "text", value, class: "env-input env-color-text",
        placeholder: "#rrggbb", spellcheck: false });
      const pick = el("input", { type: "color", class: "env-swatch",
        value: /^#[0-9a-f]{6}$/i.test(value) ? value : "#000000" });
      pick.addEventListener("input", () => { text.value = pick.value; changed(item, text.value); });
      text.addEventListener("input", () => {
        if (/^#[0-9a-f]{6}$/i.test(text.value)) pick.value = text.value;
        changed(item, text.value);
      });
      return el("span", { class: "env-color" }, pick, text);
    }
    const numeric = /(_SECONDS|_DAYS|_HOUR|_MINUTE|_MAX)$/.test(k);
    const input = el("input", { type: numeric ? "number" : "text", value,
      class: "env-input", spellcheck: false, autocomplete: "off" });
    input.addEventListener("input", () => changed(item, input.value));
    return input;
  }

  function changed(item, value) {
    stage(item.key, value);
    const row = document.querySelector(`[data-key="${item.key}"]`);
    if (row) row.classList.toggle("staged", item.key in state.staged);
  }

  function keyRow(item) {
    const removing = state.staged[item.key] === null;
    const value = item.key in state.staged && !removing ? state.staged[item.key] : item.value;
    const row = el("div", { class: "env-row" });
    row.dataset.key = item.key;
    if (item.key in state.staged) row.classList.add("staged");
    if (removing) row.classList.add("removing");
    if (!item.in_env) row.classList.add("absent");
    const label = el("label", { class: "env-key mono", textContent: item.key });
    const meta = el("div", { class: "env-meta" });
    if (item.comment) meta.append(el("div", { class: "env-help", textContent: item.comment }));
    if (item.default != null && item.default !== value) {
      meta.append(el("div", { class: "env-default", textContent: `default: ${item.default || "(blank)"}` }));
    }
    if (!item.in_env) meta.append(el("div", { class: "env-tag", textContent: "not in .env" }));
    if (!item.in_example) meta.append(el("div", { class: "env-tag", textContent: "not in .env.example" }));
    if (removing) {
      const undo = el("button", { class: "env-link", textContent: "undo remove" });
      undo.addEventListener("click", () => { stage(item.key, item.value); render(); });
      meta.append(undo);
    }
    const input = removing
      ? el("span", { class: "env-input muted", textContent: "(will be removed)" })
      : inputFor(item, value);
    row.append(label, input, meta);
    return row;
  }

  function groupBox(name, items) {
    const kind = name.startsWith("CAL_") ? "Calendar feed" : "Person";
    const tag = name.replace(/^(CAL|PERSON)_/, "");
    const rm = el("button", { class: "env-link env-danger", textContent: "Remove" });
    rm.addEventListener("click", () => removeGroup(name, kind, tag));
    const head = el("div", { class: "env-group-head" },
      el("span", { textContent: `${kind}: ${tag.toLowerCase()}` }), rm);
    return el("div", { class: "env-group" }, head, ...items.map(keyRow));
  }

  function removeGroup(name, kind, tag) {
    const own = keys().filter((k) => k.group === name);
    if (!window.confirm(`Remove ${kind.toLowerCase()} "${tag.toLowerCase()}" (${own.length} keys)?`)) return;
    for (const k of own) stage(k.key, null);
    for (const key of Object.keys(state.staged)) {
      if (key.startsWith(`${name}_`) && !find(key)) delete state.staged[key];
    }
    render();
  }

  function sectionBox(section) {
    const touched = section.keys.some((k) => k.key in state.staged || !k.in_env || !k.in_example);
    const box = el("details", { class: "env-section", open: touched || state.open.has(section.title) });
    box.addEventListener("toggle", () => {
      if (box.open) state.open.add(section.title); else state.open.delete(section.title);
    });
    const count = el("span", { class: "muted", textContent: ` · ${section.keys.length}` });
    box.append(el("summary", {}, section.title, count));
    if (section.intro) box.append(el("p", { class: "env-intro", textContent: section.intro }));
    const groups = new Map();
    for (const item of section.keys) {
      if (!item.group) { box.append(keyRow(item)); continue; }
      if (!groups.has(item.group)) {
        groups.set(item.group, []);
        box.append(el("div", { "data-group": item.group }));
      }
      groups.get(item.group).push(item);
    }
    for (const [name, items] of groups) {
      box.querySelector(`[data-group="${name}"]`).replaceWith(groupBox(name, items));
    }
    return box;
  }

  // Staged keys with no row of their own (from the add-feed / add-person helpers).
  function newKeysBox() {
    const fresh = Object.keys(state.staged).filter((k) => !find(k));
    if (!fresh.length) return null;
    const box = el("div", { class: "env-new" }, el("h3", { textContent: "New keys (staged)" }));
    for (const key of fresh) {
      const unstage = el("button", { class: "env-link", textContent: "unstage" });
      unstage.addEventListener("click", () => { delete state.staged[key]; render(); window.EnvBar.update(); });
      box.append(el("div", { class: "env-new-row" },
        el("span", { class: "mono", textContent: `${key}=${state.staged[key]}` }), unstage));
    }
    return box;
  }

  function render() {
    if (!state.view) return;
    $("env-path").textContent = state.view.env_path;
    window.EnvBar.drift(state.view.drift);
    const host = $("env-sections");
    host.replaceChildren(...[newKeysBox(), ...state.view.sections.map(sectionBox)].filter(Boolean));
    window.EnvBar.update();
  }

  return { state, el, load, stage, render, find };
})();
