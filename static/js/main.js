// Boot the display. Every piece degrades on its own: if /api/settings is
// unreachable we fall back to these defaults rather than showing nothing.

import { startAlerts } from './alerts.js';
import { startCalendar } from './calendar.js';
import { startClock } from './clock.js';
import { startSlideshow } from './photos.js';
import { scheduleNightlyReload } from './reload.js';
import { startWeather } from './weather.js';

const DEFAULTS = {
  timezone: 'America/New_York',
  photo_interval_seconds: 60,
  photo_list_refresh_seconds: 1800,
  nightly_reload_hour: 3,
  data_refresh_seconds: 300,
  alert_show_seconds: 60,
  alert_cycle_seconds: 1800,
  alert_rotate_seconds: 7,
};

async function loadSettings() {
  try {
    const res = await fetch('/api/settings', { cache: 'no-store' });
    if (!res.ok) throw new Error(`/api/settings returned ${res.status}`);
    const body = await res.json();
    return { ...DEFAULTS, ...(body.data ?? {}) };
  } catch (err) {
    console.warn('Using default settings:', err);
    return DEFAULTS;
  }
}

const settings = await loadSettings();

startClock(settings.timezone);
scheduleNightlyReload(settings.timezone, settings.nightly_reload_hour);
startSlideshow({
  intervalSeconds: settings.photo_interval_seconds,
  listRefreshSeconds: settings.photo_list_refresh_seconds,
});
startCalendar(settings);
startWeather(settings);
startAlerts(settings);
