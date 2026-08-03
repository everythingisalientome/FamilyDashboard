// Month grid + "next 5 upcoming" list, both drawn from one /api/events call.
// A failed poll leaves whatever is already on screen: stale beats blank.

import { datesBetween, daysApart, isoDate, parseDate, todayIso } from './dates.js';

const monthLabelEl = document.getElementById('month-label');
const legendEl = document.getElementById('legend');
const weekdaysEl = document.getElementById('weekdays');
const gridEl = document.getElementById('month-grid');
const agendaEl = document.getElementById('agenda-list');
const tickerEl = document.getElementById('ticker-list');

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const AGENDA_COUNT = 5;
const DEFAULT_COLOR = '#8b93a3';

// Category colours (holiday=red, school=gold, quarter=purple, ...) are decided
// server-side from keyword lists in .env and arrive on each event as its
// `category` key; this map turns that key into its colour and precedence.
let categories = {};

// A categorised event is drawn in its category colour instead of its feed's.
function eventColor(event, sourceColors) {
  const cat = event.category ? categories[event.category] : null;
  return cat?.color ?? sourceColors.get(event.source) ?? DEFAULT_COLOR;
}

let timeZone = 'America/New_York';

export async function startCalendar(settings) {
  timeZone = settings.timezone;
  weekdaysEl.replaceChildren(
    ...WEEKDAYS.map((name) => el('div', 'weekday', name)),
  );

  // How many chips fit in a cell is measured, so don't measure until text
  // metrics are final.
  await document.fonts.ready;

  refresh();
  setInterval(refresh, settings.data_refresh_seconds * 1000);
}

async function refresh() {
  let data;
  try {
    const res = await fetch('/api/events', { cache: 'no-store' });
    if (!res.ok) throw new Error(`/api/events returned ${res.status}`);
    data = (await res.json()).data;
  } catch (err) {
    console.warn('Event refresh failed, keeping what is on screen:', err);
    return;
  }
  render(data);
}

function render(data) {
  const colors = new Map(data.sources.map((s) => [s.key, s.color]));
  categories = data.categories ?? {};
  const byDate = bucketByDate(data.events);

  renderLegend(data.sources);
  renderMonth(data.today, byDate, colors);
  renderAgenda(data.events, colors);
  renderTicker(data.highlights ?? []);
}

function renderTicker(highlights) {
  if (highlights.length === 0) {
    tickerEl.replaceChildren(el('span', 'ticker-empty', 'Nothing coming up'));
    return;
  }
  tickerEl.replaceChildren(
    ...highlights.map((h) => {
      const item = el('span', 'ticker-item');
      item.append(
        el('span', 'ticker-date', h.date_label),
        el('span', 'ticker-title', h.title),
      );
      return item;
    }),
  );
}

// A multi-day event has to appear in every cell it covers, so it is fanned
// out across its own date span here rather than at render time.
function bucketByDate(events) {
  const buckets = new Map();
  for (const event of events) {
    for (const day of datesBetween(event.start_date, event.end_date)) {
      if (!buckets.has(day)) buckets.set(day, []);
      buckets.get(day).push(event);
    }
  }
  return buckets;
}

function renderLegend(sources) {
  legendEl.replaceChildren(
    ...sources.map((source) => {
      const item = el('span', 'legend-item');
      const dot = el('span', 'dot');
      dot.style.background = source.color;
      item.append(dot, document.createTextNode(source.label));
      return item;
    }),
  );
}

function renderMonth(todayIso, byDate, colors) {
  const today = parseDate(todayIso);
  const first = new Date(today.getFullYear(), today.getMonth(), 1);
  const monthEnd = new Date(today.getFullYear(), today.getMonth() + 1, 0);

  monthLabelEl.textContent = first.toLocaleDateString('en-US', {
    month: 'long',
    year: 'numeric',
  });

  // Whole weeks only: back up to the Sunday on or before the 1st, then run
  // out to the Saturday on or after the last — 5 or 6 rows depending on month.
  const cursor = new Date(first);
  cursor.setDate(1 - first.getDay());
  const last = new Date(monthEnd);
  last.setDate(monthEnd.getDate() + (6 - monthEnd.getDay()));

  const cells = [];
  let weeks = 0;
  while (cursor <= last) {
    if (cursor.getDay() === 0) weeks += 1;
    cells.push(dayCell(cursor, today, first.getMonth(), byDate, colors));
    cursor.setDate(cursor.getDate() + 1);
  }

  gridEl.style.setProperty('--weeks', weeks);
  gridEl.replaceChildren(...cells);

  // Only now do the cells have a height, so how many chips fit is measurable.
  for (const cell of cells) trimToFit(cell);
}

function dayCell(day, today, month, byDate, colors) {
  const iso = isoDate(day);
  const events = byDate.get(iso) ?? [];
  const cell = el('div', 'day');
  if (day.getMonth() !== month) cell.classList.add('is-outside');
  if (iso === isoDate(today)) cell.classList.add('is-today');

  // Tint the cell with the day's top-precedence category, so a multi-day span
  // (a break week) shows as one continuous coloured run across its cells.
  const tint = dominantCategory(events);
  if (tint) {
    cell.classList.add('has-category');
    cell.style.setProperty('--cat-color', tint.color);
  }

  const head = el('div', 'day-head');
  head.append(el('div', 'day-number', String(day.getDate())), el('span', 'day-more'));
  cell.append(head);

  const list = el('div', 'day-events');
  for (const event of events) {
    const chip = el('div', 'chip', event.title);
    chip.style.setProperty('--chip-color', eventColor(event, colors));
    if (event.category) chip.classList.add('is-category');
    if (!event.all_day && event.time_label) {
      chip.prepend(el('span', 'chip-time', event.time_label));
    }
    list.append(chip);
  }
  cell.append(list);
  return cell;
}

// The categorised event with the lowest order (highest precedence) on a day.
function dominantCategory(events) {
  let best = null;
  for (const event of events) {
    const cat = event.category ? categories[event.category] : null;
    if (cat && (best === null || cat.order < best.order)) best = cat;
  }
  return best;
}

// Drop chips off the bottom until the rest fit whole, and count what went.
// Beats a fixed per-cell limit: a 5-week month has taller cells than a
// 6-week one, and Phase 3's banner will shorten them again.
function trimToFit(cell) {
  const list = cell.querySelector('.day-events');
  const total = list.children.length;
  if (total === 0) return;

  let shown = total;
  while (shown > 0 && list.scrollHeight > list.clientHeight + 1) {
    list.children[--shown].remove();
  }
  if (shown < total) {
    cell.querySelector('.day-more').textContent = `+${total - shown}`;
  }
}

function renderAgenda(events, colors) {
  const now = Date.now();
  const upcoming = events
    .filter((event) => endTime(event) >= now)
    .slice(0, AGENDA_COUNT);

  if (upcoming.length === 0) {
    agendaEl.replaceChildren(el('li', 'agenda-empty', 'Nothing scheduled'));
    return;
  }

  agendaEl.replaceChildren(
    ...upcoming.map((event) => {
      const item = el('li', 'agenda-item');
      item.style.setProperty('--chip-color', eventColor(event, colors));
      if (event.category) item.classList.add('is-category');
      item.append(
        el('div', 'agenda-when', whenLabel(event)),
        el('div', 'agenda-title', event.title),
      );
      return item;
    }),
  );
}

function whenLabel(event) {
  const days = daysApart(todayIso(timeZone), event.start_date);
  const start = parseDate(event.start_date);

  let day;
  if (days <= 0) day = 'Today';
  else if (days === 1) day = 'Tomorrow';
  else if (days < 7) day = start.toLocaleDateString('en-US', { weekday: 'long' });
  else day = start.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

  return event.time_label ? `${day} · ${event.time_label}` : day;
}

// An all-day event stays "upcoming" until its day is over, so the agenda uses
// the end of the event rather than its start.
function endTime(event) {
  return new Date(event.end_utc ?? event.start_utc).getTime();
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
