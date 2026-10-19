// Month card from /api/events: Sunday-first grid of whole weeks, chips fitted
// to each cell after layout, and the "on the radar" footer + legend.

import { datesBetween, isoDate, parseDate } from '../dates.js';
import { shorten, spanLabel } from './format.js';
import { el } from './util.js';

const labelEl = document.getElementById('month-label');
const todayNumEl = document.getElementById('today-num');
const todayTextEl = document.getElementById('today-text');
const gridEl = document.getElementById('month-grid');
const radarEl = document.getElementById('radar');
const legendEl = document.getElementById('legend');

const WEEKDAYS = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT'];
const FALLBACK_COLOR = '#8b93a3';

export function renderMonth(data) {
  const today = parseDate(data.today);
  renderHeading(today);
  renderGrid(today, bucketByDate(data.events ?? []), data.categories ?? {});
  renderRadar(data.radar ?? []);
  renderLegend([...(data.persons ?? []), ...(data.sources ?? [])]);
}

function renderHeading(today) {
  labelEl.replaceChildren(
    today.toLocaleDateString('en-US', { month: 'long' }), ' ',
    el('span', '', String(today.getFullYear())));
  todayNumEl.textContent = String(today.getDate());
  todayTextEl.replaceChildren(
    today.toLocaleDateString('en-US', { weekday: 'long' }).toUpperCase(), el('br'), 'TODAY');
}

// A multi-day event appears in every cell it covers.
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

function renderGrid(today, byDate, categories) {
  const first = new Date(today.getFullYear(), today.getMonth(), 1);
  const monthEnd = new Date(today.getFullYear(), today.getMonth() + 1, 0);

  // Whole weeks: the Sunday on/before the 1st to the Saturday on/after the last.
  const cursor = new Date(first);
  cursor.setDate(1 - first.getDay());
  const last = new Date(monthEnd);
  last.setDate(monthEnd.getDate() + (6 - monthEnd.getDay()));

  const cells = [];
  while (cursor <= last) {
    cells.push(dayCell(cursor, today, first.getMonth(), byDate, categories));
    cursor.setDate(cursor.getDate() + 1);
  }

  gridEl.style.setProperty('--weeks', cells.length / 7);
  gridEl.replaceChildren(...WEEKDAYS.map((d) => el('div', 'weekday', d)), ...cells);

  // Cells only have a height now, so how many chips fit is measurable.
  for (const cell of cells) trimToFit(cell);
}

function dayCell(day, today, month, byDate, categories) {
  const iso = isoDate(day);
  const events = byDate.get(iso) ?? [];
  const isToday = iso === isoDate(today);

  const cell = el('div', 'cell');
  if (day.getMonth() !== month) cell.classList.add('outside');
  if (isToday) cell.classList.add('today');

  // Same rule as v1: tint with the day's top-precedence category, so a break
  // week reads as one continuous run.
  const tint = dominantCategory(events, categories);
  if (tint && !isToday) {
    cell.classList.add('tint');
    cell.style.setProperty('--tint', tint.color);
  }

  const top = el('div', 'day-top', el('span', 'num', String(day.getDate())));
  if (isToday) top.append(el('span', 'today-tag', 'TODAY'));
  top.append(el('span', 'more'));

  cell.append(top, el('div', 'events', ...events.map(chip)));
  return cell;
}

function chip(event) {
  const text = el('span', '');
  if (!event.all_day && event.time_label) text.append(el('b', '', event.time_label));
  text.append(event.title);

  const node = el('div', event.category ? 'chip cat' : 'chip', el('i'), text);
  node.style.setProperty('--c', event.color ?? FALLBACK_COLOR);
  return node;
}

function dominantCategory(events, categories) {
  let best = null;
  for (const event of events) {
    const cat = event.category ? categories[event.category] : null;
    if (cat && (best === null || cat.order < best.order)) best = cat;
  }
  return best;
}

// Drop chips off the bottom until the rest fit whole, and count what went.
function trimToFit(cell) {
  const list = cell.querySelector('.events');
  const total = list.children.length;
  let shown = total;
  while (shown > 0 && list.scrollHeight > list.clientHeight + 1) {
    list.children[--shown].remove();
  }
  if (shown < total) cell.querySelector('.more').textContent = `+${total - shown}`;
}

function renderRadar(items) {
  if (items.length === 0) {
    radarEl.replaceChildren('Nothing on the radar');
    return;
  }
  const parts = [];
  items.forEach((item, i) => {
    if (i > 0) parts.push(' ·  ');
    parts.push(el('b', '', spanLabel(item.start_date, item.end_date)), ` ${shorten(item.title)}`);
  });
  radarEl.replaceChildren(...parts);
}

function renderLegend(entries) {
  legendEl.replaceChildren(...entries.map((entry) => {
    const item = el('span', '', el('i'), entry.label);
    item.style.setProperty('--c', entry.color);
    return item;
  }));
}
