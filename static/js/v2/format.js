// Date labels for the v2 page. Inputs are the API's YYYY-MM-DD strings,
// already in the display timezone, parsed as local midnight by dates.js.

import { parseDate } from '../dates.js';

const fmt = (iso, options) => parseDate(iso).toLocaleDateString('en-US', options);

const weekdayShort = (iso) => fmt(iso, { weekday: 'short' });
const monthDay = (iso) => fmt(iso, { month: 'short', day: 'numeric' });

// "Thu Oct 22"
export const dayLabel = (iso) => `${weekdayShort(iso)} ${monthDay(iso)}`;

// "Wed, Nov 11"
export const holidayLabel = (iso) => `${weekdayShort(iso)}, ${monthDay(iso)}`;

// "SAT · OCT 31"
export const dotLabel = (iso) => `${weekdayShort(iso)} · ${monthDay(iso)}`.toUpperCase();

// "MON" + "OCT 19" for the 3-day outlook.
export const weekdayUpper = (iso) => weekdayShort(iso).toUpperCase();
export const monthDayUpper = (iso) => monthDay(iso).toUpperCase();

// "Nov 11", "Nov 26–27", "Nov 30–Dec 2" — multi-day spans collapse to one.
export function spanLabel(startIso, endIso) {
  if (!endIso || endIso === startIso) return monthDay(startIso);
  const start = parseDate(startIso);
  const end = parseDate(endIso);
  if (start.getMonth() === end.getMonth()) return `${monthDay(startIso)}–${end.getDate()}`;
  return `${monthDay(startIso)}–${monthDay(endIso)}`;
}

// Cut at a word boundary so the radar line stays scannable.
export function shorten(text, max = 32) {
  if (text.length <= max) return text;
  const cut = text.slice(0, max);
  const space = cut.lastIndexOf(' ');
  const base = space > max / 2 ? cut.slice(0, space) : cut;
  return `${base.replace(/[\s:;,.\-–·/]+$/, '')}…`;
}
