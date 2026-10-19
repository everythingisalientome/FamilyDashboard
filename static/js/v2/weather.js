// Header weather from /api/weather: current block, metrics, six hourly slots
// and the next three days. Icons are the local SVG symbols, never emoji.

import { todayIso } from '../dates.js';
import { monthDayUpper, weekdayUpper } from './format.js';
import { el, poll, setText, symbolHref, wxIcon } from './util.js';

const $ = (id) => document.getElementById(id);
const DAYS_SHOWN = 3;

let timeZone = 'America/New_York';

export function startWeather(settings) {
  timeZone = settings.timezone;
  poll('/api/weather', settings.data_refresh_seconds, render);
}

function render(data) {
  const today = todayIso(timeZone);
  const daily = data.daily ?? [];
  if (data.current) renderCurrent(data.current, daily.find((d) => d.date === today));
  if (data.hourly?.length) $('wx-hourly').replaceChildren(...data.hourly.slice(0, 6).map(hourSlot));
  const ahead = daily.filter((d) => d.date > today).slice(0, DAYS_SHOWN);
  if (ahead.length) $('wx-daily').replaceChildren(...ahead.map(dayRow));
}

// High/low come from today's daily row; after ~6 PM NWS drops it, so the
// current block's own high/low (often just the overnight low) fills in.
function renderCurrent(current, todayRow) {
  $('wx-now-icon').setAttribute('href', symbolHref(current.icon));
  setText($('wx-now-temp'), deg(current.temp_f));
  setText($('wx-now-temp-c'), current.temp_f == null ? '' : `(${toCelsius(current.temp_f)}°C)`);
  setText($('wx-now-cond'), current.condition ?? '');

  const high = todayRow?.high_f ?? current.high_f;
  const low = todayRow?.low_f ?? current.low_f;
  const hilo = [high != null && `H ${deg(high)}`, low != null && `L ${deg(low)}`];
  setText($('wx-now-hilo'), hilo.filter(Boolean).join(' · '));

  setText($('wx-feels'), deg(current.feels_like_f));
  setText($('wx-humidity'), current.humidity_pct == null ? '--' : `${Math.round(current.humidity_pct)}%`);
  setText($('wx-uv'), current.uv_index == null ? '--' : `${current.uv_index} ${uvBand(current.uv_index)}`);
}

function hourSlot(hour) {
  return el('div', 'hour',
    el('span', 'label', hour.label ?? ''),
    wxIcon(hour.icon),
    el('span', 'temp', deg(hour.temp_f)));
}

function dayRow(day) {
  const name = el('span', 'day-name', weekdayUpper(day.date), ' ', el('small', '', monthDayUpper(day.date)));
  const temps = el('span', 'day-temps', deg(day.high_f), ' ', el('small', '', deg(day.low_f)));
  return el('div', 'day-row', name, wxIcon(day.icon), el('span', 'day-cond', day.condition ?? ''), temps);
}

// WHO/EPA UV index bands.
function uvBand(uv) {
  if (uv < 3) return 'Low';
  if (uv < 6) return 'Moderate';
  if (uv < 8) return 'High';
  if (uv < 11) return 'Very High';
  return 'Extreme';
}

const deg = (f) => (f == null ? '--' : `${Math.round(f)}°`);
const toCelsius = (f) => Math.round(((f - 32) * 5) / 9);
