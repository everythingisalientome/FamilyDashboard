// Boot the v2 wall. Every region degrades on its own: if /api/settings is
// unreachable these defaults stand in, and a failed poll keeps what is shown.

import { startClock } from '../clock.js';
import { startSlideshow } from '../photos.js';
import { scheduleNightlyReload } from '../reload.js';
import { startDateLine } from './date-line.js';
import { renderHero } from './hero.js';
import { renderMonth } from './month.js';
import { poll } from './util.js';
import { startWeather } from './weather.js';

const DEFAULTS = {
  timezone: 'America/New_York',
  photo_interval_seconds: 60,
  photo_list_refresh_seconds: 1800,
  nightly_reload_hour: 3,
  data_refresh_seconds: 300,
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
startDateLine(settings.timezone);
scheduleNightlyReload(settings.timezone, settings.nightly_reload_hour);
startSlideshow({
  intervalSeconds: settings.photo_interval_seconds,
  listRefreshSeconds: settings.photo_list_refresh_seconds,
});
startWeather(settings);

// Chip fit is measured, so wait for final text metrics before the first grid.
await document.fonts.ready;
poll('/api/events', settings.data_refresh_seconds, (data) => {
  renderHero(data);
  renderMonth(data);
});
