// Current conditions + 4-day outlook from /api/weather. Icons are local SVG
// symbols; nothing here reaches api.weather.gov.

const iconEl = document.getElementById('now-icon');
const tempEl = document.getElementById('now-temp');
const tempCEl = document.getElementById('now-temp-c');
const conditionEl = document.getElementById('now-condition');
const line2El = document.getElementById('now-l2');
const line3El = document.getElementById('now-l3');
const line4El = document.getElementById('now-l4');
const forecastEl = document.getElementById('forecast');

const DOT = '  ·  ';

const KNOWN_ICONS = new Set([
  'clear', 'clear-night', 'partly', 'partly-night', 'cloudy', 'rain',
  'thunder', 'snow', 'sleet', 'fog', 'wind', 'hot',
]);

export function startWeather(settings) {
  refresh();
  setInterval(refresh, settings.data_refresh_seconds * 1000);
}

async function refresh() {
  let data;
  try {
    const res = await fetch('/api/weather', { cache: 'no-store' });
    if (!res.ok) throw new Error(`/api/weather returned ${res.status}`);
    data = (await res.json()).data;
  } catch (err) {
    console.warn('Weather refresh failed, keeping what is on screen:', err);
    return;
  }
  renderCurrent(data.current);
  renderForecast(data.daily ?? []);
}

function renderCurrent(current) {
  if (!current) return;              // nothing cached yet — leave the dashes

  iconEl.setAttribute('href', symbol(current.icon));

  // Line 1: 77°(23°C) - Partly Cloudy
  tempEl.textContent = `${round(current.temp_f)}°`;
  tempCEl.textContent =
    current.temp_f != null ? `(${toCelsius(current.temp_f)}°C)` : '';
  conditionEl.textContent = current.condition ? `- ${current.condition}` : '';

  // Line 2: Feels 79°  ·  Low 71°
  const l2 = [];
  if (current.feels_like_f != null) l2.push(`Feels ${round(current.feels_like_f)}°`);
  if (current.low_f != null) l2.push(`Low ${round(current.low_f)}°`);
  line2El.textContent = l2.join(DOT);

  // Line 3: Humidity 79%  ·  UV 6  ·  Wind 8 mph NW
  const l3 = [];
  if (current.humidity_pct != null) l3.push(`Humidity ${round(current.humidity_pct)}%`);
  if (current.uv_index != null) l3.push(`UV ${current.uv_index}`);
  if (current.wind_mph != null) {
    l3.push(`Wind ${round(current.wind_mph)} mph${current.wind_dir ? ` ${current.wind_dir}` : ''}`);
  }
  line3El.textContent = l3.join(DOT);

  // Line 4: Sunset 8:14 PM  ·  🌖 Waning Gibbous
  const l4 = [];
  if (current.sunset) l4.push(`Sunset ${current.sunset}`);
  if (current.moon_phase) l4.push(`${current.moon_icon ?? ''} ${current.moon_phase}`.trim());
  line4El.textContent = l4.join(DOT);
}

function toCelsius(fahrenheit) {
  return Math.round(((fahrenheit - 32) * 5) / 9);
}

function renderForecast(days) {
  forecastEl.replaceChildren(...days.map(dayCard));
}

function dayCard(day) {
  const card = document.createElement('li');
  card.className = 'forecast-day';

  const label = document.createElement('div');
  label.className = 'forecast-label';
  label.textContent = day.label;

  const icon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  icon.setAttribute('class', 'wx-icon');
  const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
  use.setAttribute('href', symbol(day.icon));
  icon.append(use);

  const temps = document.createElement('div');
  temps.className = 'forecast-temps';
  temps.append(
    span('hi', day.high_f == null ? '--' : `${round(day.high_f)}°`),
    span('lo', day.low_f == null ? '--' : `${round(day.low_f)}°`),
  );

  card.append(label, icon, temps);

  // Only worth the pixels when rain is actually plausible.
  if (day.precip_pct != null && day.precip_pct >= 10) {
    const precip = document.createElement('div');
    precip.className = 'forecast-precip';
    precip.textContent = `${day.precip_pct}%`;
    card.append(precip);
  }
  return card;
}

function span(className, text) {
  const node = document.createElement('span');
  node.className = className;
  node.textContent = text;
  return node;
}

function symbol(icon) {
  return KNOWN_ICONS.has(icon) ? `#wx-${icon}` : '#wx-clear';
}

function round(value) {
  return Math.round(value);
}
