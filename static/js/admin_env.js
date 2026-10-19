// Admin Settings tab: one sub-tab per .env.example section, keys shown
// read-only; ✎ turns a row into an input, ✓ stages that edit, ✕ cancels it.
// Staged edits only ever belong to the open sub-tab (leaving it asks first);
// Save / Revert and drift live in admin_env_save.js, the add helpers in
// admin_env_helpers.js.

window.EnvEdit = (() => {
  const $ = (id) => document.getElementById(id);
  const state = { view: null, staged: {}, editing: new Set(), sub: null };

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
  const section = () => state.view.sections.find((s) => s.title === state.sub);
  const dirty = () => Object.keys(state.staged).length > 0;
  const shown = (v) => (v === "" ? "(blank)" : v);

  async function load() {
    const res = await fetch("/api/admin/env", { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    state.view = (await res.json()).data;
    if (!section()) state.sub = state.view.sections[0].title;
    window.AdminRestart.update(state.view);
    render();
  }

  // Staging the live value (or removing an absent key) unstages instead.
  function stage(key, value) {
    const item = find(key);
    const live = item && item.in_env ? item.value : undefined;
    if (value === live || (value === null && live === undefined)) delete state.staged[key];
    else state.staged[key] = value;
  }

  function inputFor(item, value) {
    if (/_COLOR$/.test(item.key)) {
      const text = el("input", { type: "text", value, class: "env-input", placeholder: "#rrggbb",
        spellcheck: false });
      const pick = el("input", { type: "color", class: "env-swatch",
        value: /^#[0-9a-f]{6}$/i.test(value) ? value : "#000000" });
      pick.addEventListener("input", () => { text.value = pick.value; });
      text.addEventListener("input", () => {
        if (/^#[0-9a-f]{6}$/i.test(text.value)) pick.value = text.value;
      });
      return { node: el("span", { class: "env-color" }, pick, text), input: text };
    }
    const numeric = /(_SECONDS|_DAYS|_HOUR|_MINUTE|_MAX)$/.test(item.key);
    const input = el("input", { type: numeric ? "number" : "text", value, class: "env-input",
      spellcheck: false, autocomplete: "off" });
    return { node: input, input };
  }

  function iconBtn(label, title, onClick, cls = "") {
    const b = el("button", { class: `env-icon ${cls}`, textContent: label, title, type: "button" });
    b.setAttribute("aria-label", `${title}`);
    b.addEventListener("click", onClick);
    return b;
  }

  function editRow(item, value) {
    const field = inputFor(item, value);
    const commit = () => { stage(item.key, field.input.value); state.editing.delete(item.key); render(); };
    const cancel = () => { state.editing.delete(item.key); render(); };
    field.input.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter") commit();
      if (ev.key === "Escape") cancel();
    });
    return el("div", { class: "env-value env-editing" }, field.node,
      iconBtn("✓", `Stage ${item.key}`, commit, "env-ok-btn"),
      iconBtn("✕", "Cancel this edit", cancel));
  }

  function keyRow(item, showHelp = true) {
    const isStaged = item.key in state.staged;
    const removing = state.staged[item.key] === null;
    const value = isStaged && !removing ? state.staged[item.key] : item.value;
    const row = el("div", { class: "env-row" });
    row.dataset.key = item.key;
    row.classList.toggle("staged", isStaged);
    row.classList.toggle("removing", removing);
    row.classList.toggle("absent", !item.in_env);

    let valueBox;
    if (state.editing.has(item.key)) {
      valueBox = editRow(item, value);
    } else {
      const text = removing ? "(will be removed)" : item.in_env || isStaged ? shown(value) : "(not set)";
      valueBox = el("div", { class: "env-value" },
        el("span", { class: `env-shown mono${value === "" || removing ? " muted" : ""}`, textContent: text }));
      if (/_COLOR$/.test(item.key) && /^#[0-9a-f]{3,6}$/i.test(value) && !removing) {
        valueBox.prepend(el("span", { class: "env-chip", style: `background:${value}` }));
      }
      if (!removing) {
        valueBox.append(iconBtn("✎", `Edit ${item.key}`, () => { state.editing.add(item.key); render(); }));
      }
      if (isStaged) {
        valueBox.append(iconBtn("↺", "Undo this staged edit", () => {
          delete state.staged[item.key];
          render();
        }));
      }
    }

    const meta = el("div", { class: "env-meta" });
    if (isStaged && !removing) meta.append(el("div", { class: "env-was", textContent: `was: ${item.in_env ? shown(item.value) : "(not set)"}` }));
    if (item.comment && showHelp) meta.append(el("div", { class: "env-help", textContent: item.comment }));
    if (item.default != null && item.default !== value) {
      meta.append(el("div", { class: "env-default", textContent: `default: ${shown(item.default)}` }));
    }
    if (!item.in_example) meta.append(el("div", { class: "env-tag", textContent: "not in .env.example" }));
    row.append(el("div", { class: "env-key mono", textContent: item.key }), valueBox, meta);
    return row;
  }

  function groupBox(name, items, first) {
    const kind = name.startsWith("CAL_") ? "Calendar feed" : "Person";
    const tag = name.replace(/^(CAL|PERSON)_/, "").toLowerCase();
    const rm = el("button", { class: "env-link env-danger", textContent: "Remove", type: "button" });
    rm.addEventListener("click", () => window.EnvSave.removeGroup(name, kind, tag));
    const head = el("div", { class: "env-group-head" }, el("span", { textContent: `${kind}: ${tag}` }), rm);
    return el("div", { class: "env-group" }, head, ...items.map((k) => keyRow(k, first.has(k.key))));
  }

  function rows(sec) {
    // A run of keys shares one comment block: show it on the first key only.
    const first = new Set(sec.keys.filter((k, i) => i === 0 || sec.keys[i - 1].comment !== k.comment)
      .map((k) => k.key));
    const out = [];
    const groups = new Map();
    for (const item of sec.keys) {
      if (!item.group) { out.push(keyRow(item, first.has(item.key))); continue; }
      if (!groups.has(item.group)) { groups.set(item.group, []); out.push(item.group); }
      groups.get(item.group).push(item);
    }
    return out.map((r) => (typeof r === "string" ? groupBox(r, groups.get(r), first) : r));
  }

  function subtabs() {
    const bar = $("env-subtabs");
    bar.replaceChildren(...state.view.sections.map((s) => {
      const btn = el("button", { class: "subtab", type: "button", textContent: s.title });
      btn.setAttribute("role", "tab");
      btn.setAttribute("aria-selected", String(s.title === state.sub));
      btn.classList.toggle("active", s.title === state.sub);
      btn.addEventListener("click", () => window.EnvSave.switchSub(s.title));
      return btn;
    }));
    const active = bar.querySelector(".active");
    if (active) active.scrollIntoView({ block: "nearest", inline: "nearest" });
  }

  function render() {
    if (!state.view) return;
    $("env-path").textContent = state.view.env_path;
    window.EnvSave.drift(state.view.drift);
    subtabs();
    const sec = section();
    const pane = $("env-pane");
    const intro = sec.intro
      ? el("details", { class: "env-intro" }, el("summary", { textContent: "About this section" }),
        el("pre", { textContent: sec.intro }))
      : null;
    pane.replaceChildren(...[intro, window.EnvHelpers.helper(sec), window.EnvHelpers.newKeys(),
      el("div", { class: "env-rows" }, ...rows(sec)), window.EnvSave.footer()].filter(Boolean));
  }

  return { state, el, load, stage, render, find, dirty, section };
})();
