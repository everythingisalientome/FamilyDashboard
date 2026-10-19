// Night mode: from settings.night_mode_start (default midnight) until the
// day's sunrise, <html> carries the class "night" and css/v2/base.css swaps in
// the dark palette. Sunrise comes from the weather renderer's /api/weather
// poll via setSunrise() — this module never fetches anything itself.

const FALLBACK_SUNRISE = 6 * 60 + 30; // 06:30, while the weather cache is empty

let timeZone = 'America/New_York';
let startMinute = 0;
let sunriseMinute = null;

export function startNight(settings) {
  timeZone = settings.timezone;
  startMinute = minutesOf(settings.night_mode_start) ?? 0;
  tick();
}

// Called with /api/weather's current.sunrise_at ("2026-10-19T07:26", local).
export function setSunrise(iso) {
  const minute = minutesOf(iso?.slice(11, 16));
  if (minute == null || minute === sunriseMinute) return;
  sunriseMinute = minute;
  apply();
}

// Re-check on every minute boundary, so the flip lands on the minute.
function tick() {
  apply();
  setTimeout(tick, 60000 - (Date.now() % 60000) + 50);
}

function apply() {
  const now = localMinute();
  const sunrise = sunriseMinute ?? FALLBACK_SUNRISE;
  // A start after sunrise (e.g. 23:00) wraps past midnight.
  const night = startMinute <= sunrise
    ? now >= startMinute && now < sunrise
    : now >= startMinute || now < sunrise;
  document.documentElement.classList.toggle('night', night);
}

function localMinute() {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone, hour: '2-digit', minute: '2-digit', hour12: false,
  }).formatToParts(new Date());
  const num = (type) => Number(parts.find((p) => p.type === type)?.value ?? 0);
  return (num('hour') % 24) * 60 + num('minute'); // "24" is midnight in some ICU
}

function minutesOf(hhmm) {
  const match = /^(\d{2}):(\d{2})$/.exec(hhmm ?? '');
  return match ? Number(match[1]) * 60 + Number(match[2]) : null;
}
