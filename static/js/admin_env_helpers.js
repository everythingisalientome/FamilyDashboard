// Admin Settings tab: the add-feed / add-person helpers. They stage only
// their fixed CAL_<KEY>_* / PERSON_<KEY>_* template keys — there is no
// free-form key entry anywhere — and list what they staged until it is saved.

window.EnvHelpers = (() => {
  const E = () => window.EnvEdit;
  const S = () => E().state;

  const TEMPLATES = [
    { prefix: "CAL", title: "+ Add calendar feed", fields: [
      ["URL", "ICS URL", { type: "url", required: true, placeholder: "https://…/calendar.ics" }],
      ["LABEL", "Label", { placeholder: "Soccer" }],
      ["COLOR", "Colour", { type: "color", value: "#f783ac" }],
      ["ORDER", "Order", { type: "number", value: "100" }]] },
    { prefix: "PERSON", title: "+ Add person", fields: [
      ["LABEL", "Name", { required: true, placeholder: "Ava" }],
      ["COLOR", "Colour", { type: "color", value: "#a78bfa" }],
      ["ORDER", "Order", { type: "number", value: "3" }],
      ["FEEDS", "Feeds", { placeholder: "comma list, e.g. school" }],
      ["KEYWORDS", "Keywords", { placeholder: "comma list, e.g. ava" }]] },
  ];

  // The add helper for a section that holds CAL_<KEY> / PERSON_<KEY> groups.
  function helper(sec) {
    const t = TEMPLATES.find((tp) => sec.keys.some((k) => (k.group || "").startsWith(`${tp.prefix}_`)));
    if (!t) return null;
    const el = E().el;
    const keyInput = el("input", { name: "key", required: true, pattern: "[a-z0-9]+",
      placeholder: t.prefix === "CAL" ? "soccer" : "ava", title: "lowercase letters and digits" });
    const inputs = t.fields.map(([suffix, , attrs]) => el("input", { name: suffix, ...attrs }));
    const err = el("p", { class: "env-bad", hidden: true });
    const form = el("form", { class: "env-form" },
      el("label", {}, "Key ", keyInput),
      ...t.fields.map(([, label], i) => el("label", {}, `${label} `, inputs[i])),
      el("button", { class: "imp-btn", textContent: "Stage" }), err);
    form.addEventListener("submit", (ev) => {
      ev.preventDefault();
      const key = keyInput.value.trim();
      const group = `${t.prefix}_${key.toUpperCase()}`;
      const taken = E().state.view.sections.some((s) => s.keys.some((k) => k.group === group))
        || Object.keys(S().staged).some((k) => k.startsWith(`${group}_`));
      err.hidden = /^[a-z0-9]+$/.test(key) && !taken;
      err.textContent = taken ? `"${key}" already exists.` : "Key must be lowercase letters and digits only.";
      if (!err.hidden) return;
      t.fields.forEach(([suffix], i) => E().stage(`${group}_${suffix}`, inputs[i].value.trim()));
      E().render();
    });
    return el("details", { class: "env-helper" }, el("summary", { textContent: t.title }), form);
  }

  // Template keys staged by a helper (they have no row until saved).
  function newKeys() {
    const fresh = Object.keys(S().staged).filter((k) => !E().find(k));
    if (!fresh.length) return null;
    const el = E().el;
    const box = el("div", { class: "env-new" }, el("h3", { textContent: "New (staged)" }));
    for (const key of fresh) {
      const unstage = el("button", { class: "env-link", type: "button", textContent: "unstage" });
      unstage.addEventListener("click", () => { delete S().staged[key]; E().render(); });
      box.append(el("div", { class: "env-new-row" },
        el("span", { class: "mono", textContent: `${key}=${S().staged[key]}` }), unstage));
    }
    return box;
  }

  return { helper, newKeys };
})();
