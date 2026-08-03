// Calendar date arithmetic.
//
// Dates from /api/* are plain YYYY-MM-DD strings already converted to the
// display timezone, so they are parsed as *local* midnight. Passing them to
// `new Date(iso)` instead would read them as UTC and shift every event a day
// backwards for anyone west of Greenwich.

export function parseDate(iso) {
  const [year, month, day] = iso.split('-').map(Number);
  return new Date(year, month - 1, day);
}

export function isoDate(date) {
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${date.getFullYear()}-${month}-${day}`;
}

// Today according to the *display* timezone, which is not necessarily the
// browser's — the server is authoritative about where the wall is.
export function todayIso(timeZone) {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date());
}

export function datesBetween(startIso, endIso) {
  const days = [];
  const cursor = parseDate(startIso);
  const end = parseDate(endIso);
  while (cursor <= end) {
    days.push(isoDate(cursor));
    cursor.setDate(cursor.getDate() + 1);
  }
  return days;
}

export function daysApart(fromIso, toIso) {
  return Math.round((parseDate(toIso) - parseDate(fromIso)) / 86400000);
}
