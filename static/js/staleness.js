// Subtle stale-data indicator. Polls /api/staleness on the shared data-refresh
// cadence and shows a quiet corner dot when any active feed's cache is older
// than ~2x its refresh interval. Never blocks anything; on any error it just
// hides the dot — the wall must never nag or show a spinner.

export function startStaleness({ data_refresh_seconds }) {
  const dot = document.getElementById('stale-dot');
  if (!dot) return;

  async function poll() {
    try {
      const res = await fetch('/api/staleness', { cache: 'no-store' });
      if (!res.ok) throw new Error(`/api/staleness returned ${res.status}`);
      const { data } = await res.json();
      if (data.stale) {
        dot.hidden = false;
        dot.title = `Stale: ${data.stale_jobs.join(', ')}`;
      } else {
        dot.hidden = true;
        dot.removeAttribute('title');
      }
    } catch (err) {
      // A status blip should never surface on the wall — hide and try again.
      dot.hidden = true;
    }
  }

  poll();
  setInterval(poll, Math.max(30, data_refresh_seconds) * 1000);
}
