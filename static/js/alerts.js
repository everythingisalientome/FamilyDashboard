// Alert pill on the photo panel, drawn from /api/alerts. One alert shows at a
// time and rotates to the next every few seconds. The pill is hidden most of
// the time and fades in for a short window on a timer (default: 1 minute every
// 30). A failed poll keeps whatever is cached — stale beats a blanked warning.

const overlayEl = document.getElementById('alerts-overlay');

let current = [];
let index = 0;
let showSeconds = 60;
let rotateSeconds = 7;
let rotateTimer = null;
let windowTimer = null;

export function startAlerts(settings) {
  showSeconds = settings.alert_show_seconds ?? 60;
  rotateSeconds = settings.alert_rotate_seconds ?? 7;
  const cycleSeconds = settings.alert_cycle_seconds ?? 1800;

  overlayEl.hidden = false; // JS is alive — visibility is now the class's job

  // First reveal shortly after load (confirms it works), then on the cycle.
  refresh().then(reveal);
  setInterval(refresh, settings.data_refresh_seconds * 1000);
  setInterval(reveal, cycleSeconds * 1000);
}

async function refresh() {
  let data;
  try {
    const res = await fetch('/api/alerts', { cache: 'no-store' });
    if (!res.ok) throw new Error(`/api/alerts returned ${res.status}`);
    data = (await res.json()).data;
  } catch (err) {
    console.warn('Alert refresh failed, keeping what is on screen:', err);
    return;
  }
  current = data.alerts ?? [];
  if (current.length === 0) endWindow(); // nothing left — fade out now
}

// Bring the pill on screen for showSeconds, rotating one alert at a time.
function reveal() {
  if (current.length === 0) return;
  index = 0;
  showCurrent();
  overlayEl.classList.add('is-showing');

  clearInterval(rotateTimer);
  rotateTimer = setInterval(advance, rotateSeconds * 1000);
  clearTimeout(windowTimer);
  windowTimer = setTimeout(endWindow, showSeconds * 1000);
}

function advance() {
  if (current.length === 0) {
    endWindow();
    return;
  }
  index = (index + 1) % current.length;
  showCurrent();
}

function endWindow() {
  clearInterval(rotateTimer);
  rotateTimer = null;
  overlayEl.classList.remove('is-showing');
}

function showCurrent() {
  const alert = current[index % current.length];
  if (alert) overlayEl.replaceChildren(pill(alert));
}

function pill(alert) {
  const node = el('div', `alert-pill tone-${alert.tone}`);
  if (alert.tone === 'custom' && alert.color) {
    node.style.setProperty('--alert-color', alert.color);
  }
  node.append(el('span', 'alert-pill-title', alert.title));
  if (alert.text) node.append(el('span', 'alert-pill-text', alert.text));
  return node;
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
