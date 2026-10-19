// Gold hero card from /api/events: per-person NEXT UP + NEXT HOLIDAY, the
// family line and the waste strip. Everything is decided server-side
// (hero/waste blocks); this only lays it out.

import { dayLabel, dotLabel, holidayLabel } from './format.js';
import { el, joinSep } from './util.js';

const kidsEl = document.getElementById('hero-kids');
const familyEl = document.getElementById('family-body');
const stripEl = document.getElementById('waste-strip');
const wasteEl = document.getElementById('waste-body');
const stateEl = document.getElementById('waste-state');

const HERO_PERSONS = 2;
const WEEK_LABELS = { regular: 'REGULAR WEEK', recycle: 'RECYCLING WEEK', bulky: 'BULKY WEEK' };

export function renderHero(data) {
  const persons = new Map((data.persons ?? []).map((p) => [p.key, p]));
  const columns = (data.hero?.persons ?? []).slice(0, HERO_PERSONS);
  kidsEl.replaceChildren(...columns.map((col) => personColumn(col, persons.get(col.key))));
  renderFamily(data.hero?.family ?? {});
  renderWaste(data.waste ?? {});
}

function personColumn(col, person) {
  const section = el('section', 'person');
  section.style.setProperty('--pc', person?.color ?? 'currentColor');
  section.setAttribute('aria-label', person?.label ?? col.key);

  const heading = el('div', 'person-heading',
    el('span', 'person-dot'), person?.label ?? col.key, el('span', 'next-label', 'NEXT UP'));

  const next = col.next;
  const title = el('div', 'person-title', next?.title ?? 'Nothing scheduled');
  const details = el('div', 'person-details');
  if (next) {
    details.append(...joinSep([dayLabel(next.start_date), next.all_day ? null : next.time_label, next.location]));
  }

  const holiday = col.next_holiday;
  const holidayLine = el('div', 'holiday-line', el('span', 'k', 'NEXT HOLIDAY'));
  if (holiday) {
    holidayLine.classList.add('has-holiday');
    holidayLine.append(el('span', 'when', holidayLabel(holiday.start_date)), el('span', 'what', holiday.title));
  } else {
    holidayLine.append(el('span', 'when'), el('span', 'what', 'No holiday in the next 30 days'));
  }

  section.append(heading, title, details, holidayLine);
  return section;
}

function renderFamily({ next, following }) {
  if (!next) {
    familyEl.replaceChildren(el('span', 'none', 'Nothing on the family calendar'));
    return;
  }
  const parts = [el('span', 'when', dotLabel(next.start_date)), el('span', 'what', next.title)];
  if (following) {
    parts.push(el('span', 'then', 'THEN'),
      el('span', 'when', dotLabel(following.start_date)), el('span', 'what', following.title));
  }
  familyEl.replaceChildren(...parts);
}

function renderWaste({ next, following, week_kind: kind }) {
  const week = WEEK_LABELS[kind] ? kind : 'regular';
  stripEl.dataset.week = week;
  stateEl.replaceChildren(el('i'), ` ${WEEK_LABELS[week]}`);

  if (!next) {
    wasteEl.replaceChildren(el('span', 'waste-type', 'No pickups found'));
    return;
  }
  const parts = [el('span', 'waste-day', dotLabel(next.date)), el('span', 'waste-type', items(next))];
  if (following) {
    parts.push(el('span', 'waste-divider'),
      el('span', 'waste-extra', `Then ${dayLabel(following.date)} · ${items(following)}`));
  }
  wasteEl.replaceChildren(...parts);
}

const items = (pickup) => (pickup.items?.length ? pickup.items.join(' · ') : pickup.title);
