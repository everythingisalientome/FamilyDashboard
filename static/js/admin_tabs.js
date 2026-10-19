// Admin page tabs (hash-routed: #status, #events, #settings, #logs) and the
// in-page modal used instead of window.confirm, which is unreliable in kiosk /
// embedded browsers. A tab may install a guard that can veto leaving it.

window.AdminTabs = (() => {
  const TABS = ["status", "events", "settings", "logs"];
  const $ = (id) => document.getElementById(id);
  let current = null;
  let guard = null; // async (from, to) => true to allow leaving `from`
  let pending = null; // resolver of the open modal, if any

  const fromHash = () => {
    const tab = window.location.hash.slice(1);
    return TABS.includes(tab) ? tab : "status";
  };

  function show(tab) {
    current = tab;
    for (const panel of document.querySelectorAll("[data-panel]")) {
      panel.hidden = panel.dataset.panel !== tab;
    }
    for (const link of document.querySelectorAll(".tab")) {
      const on = link.dataset.tab === tab;
      link.classList.toggle("active", on);
      link.setAttribute("aria-selected", String(on));
    }
    window.dispatchEvent(new CustomEvent("admin:tab", { detail: tab }));
  }

  async function go(want) {
    if (want === current) return;
    if (guard && !(await guard(current, want))) {
      if (fromHash() !== current) history.replaceState(null, "", `#${current}`);
      return;
    }
    show(want);
    if (fromHash() !== want) history.pushState(null, "", `#${want}`);
  }

  // ask("text", [{id, label, primary?}], cancelId) → Promise<id>. Escape or a
  // newer ask() answers cancelId.
  function ask(text, buttons, cancelId) {
    if (pending) pending(pending.cancelId);
    $("modal-text").textContent = text;
    const box = $("modal-buttons");
    box.replaceChildren();
    return new Promise((resolve) => {
      const done = (id) => {
        pending = null;
        $("modal").hidden = true;
        document.removeEventListener("keydown", onKey);
        resolve(id);
      };
      const onKey = (ev) => { if (ev.key === "Escape") done(cancelId); };
      pending = done;
      pending.cancelId = cancelId;
      for (const b of buttons) {
        const btn = document.createElement("button");
        btn.className = `imp-btn${b.primary ? " imp-primary" : ""}`;
        btn.textContent = b.label;
        btn.addEventListener("click", () => done(b.id));
        box.append(btn);
      }
      document.addEventListener("keydown", onKey);
      $("modal").hidden = false;
      box.querySelector(".imp-primary, button").focus();
    });
  }

  function start() {
    for (const link of document.querySelectorAll(".tab")) {
      link.addEventListener("click", (ev) => {
        ev.preventDefault();
        go(link.dataset.tab);
      });
    }
    window.addEventListener("hashchange", () => go(fromHash()));
    show(fromHash());
  }

  return {
    current: () => current || fromHash(),
    setGuard: (fn) => { guard = fn; },
    ask,
    start,
  };
})();

window.AdminTabs.start();
