// "SUNDAY October 18" under the clock. The time itself comes from the shared
// js/clock.js; v1's date format differs, so this line is drawn here.

import { setText } from './util.js';

export function startDateLine(timeZone) {
  const weekdayEl = document.getElementById('date-weekday');
  const dayEl = document.getElementById('date-day');
  const weekdayFmt = new Intl.DateTimeFormat('en-US', { timeZone, weekday: 'long' });
  const dayFmt = new Intl.DateTimeFormat('en-US', { timeZone, month: 'long', day: 'numeric' });

  const tick = () => {
    const now = new Date();
    setText(weekdayEl, weekdayFmt.format(now));
    setText(dayEl, dayFmt.format(now));
  };
  tick();
  setInterval(tick, 15000);
}
