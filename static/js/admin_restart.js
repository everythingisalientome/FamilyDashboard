// "Settings saved — restart to apply" banner. Shown when the .env on disk no
// longer matches the one this server booted with (hashes from /api/admin/env).
// Restart now = POST /api/admin/restart (NSSM only), then wait for a new boot.

window.AdminRestart = (() => {
  const $ = (id) => document.getElementById(id);
  let canRestart = false;

  function update(view) {
    $("restart-banner").hidden = view.env_loaded_hash === view.env_file_hash;
    canRestart = view.can_restart;
    const btn = $("restart-now");
    btn.disabled = !canRestart;
    btn.title = canRestart ? "Restart the service now (the wall keeps showing cached data)"
      : "Not running as the NSSM service — restart the dev server by hand";
  }

  async function bootId() {
    const res = await fetch("/healthz", { cache: "no-store" });
    return (await res.json()).boot;
  }

  // The old process answers for ~1 s after the request, so wait for a new boot id.
  async function waitForRestart(oldBoot) {
    const overlay = $("env-restarting");
    overlay.hidden = false;
    const started = Date.now();
    for (;;) {
      await new Promise((r) => setTimeout(r, 2000));
      try {
        if ((await bootId()) !== oldBoot) return window.location.reload();
      } catch { /* down mid-restart */ }
      if (Date.now() - started > 60000) {
        overlay.textContent =
          "Still restarting after 60 s… check: nssm status FamilyDashboard (data\\logs\\dashboard.err.log)";
      }
    }
  }

  async function restart() {
    if (!canRestart) return;
    const btn = $("restart-now");
    btn.disabled = true;
    try {
      const boot = await bootId();
      const res = await fetch("/api/admin/restart", { method: "POST" });
      const { data } = await res.json();
      if (data.restarting) return waitForRestart(boot);
      btn.title = data.note || "restart refused";
    } catch (err) {
      btn.title = `restart failed: ${err.message}`;
    }
    btn.disabled = !canRestart;
  }

  $("restart-now").addEventListener("click", restart);
  return { update };
})();
