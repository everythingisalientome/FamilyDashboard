// Nightly self-reload. Chromium in kiosk mode runs for months; reloading at
// 3am picks up new frontend code and sheds any accumulated memory.

export function scheduleNightlyReload(timeZone, hour) {
  const delay = msUntilNextLocalHour(timeZone, hour);
  console.info(`Nightly reload in ${Math.round(delay / 60000)} min`);
  setTimeout(() => window.location.reload(), delay);
}

// Wall-clock hour in `timeZone`, expressed as a delay from now. Derived from
// the zone's own formatted output so DST shifts are handled for free.
function msUntilNextLocalHour(timeZone, hour) {
  const fmt = new Intl.DateTimeFormat('en-US', {
    timeZone,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
  const now = new Date();
  const parts = fmt.formatToParts(now);
  const num = (type) => Number(parts.find((p) => p.type === type)?.value ?? 0);

  // "24" shows up for midnight in some ICU versions.
  const secondsNow = (num('hour') % 24) * 3600 + num('minute') * 60 + num('second');
  const secondsTarget = hour * 3600;
  let delta = secondsTarget - secondsNow;
  if (delta <= 0) delta += 24 * 3600;
  return delta * 1000;
}
