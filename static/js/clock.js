// Clock and date. Rendered entirely in the browser — no server round trip,
// so the time keeps ticking even if the server goes away.

const timeEl = document.getElementById('time');
const meridiemEl = document.getElementById('meridiem');
const dateEl = document.getElementById('date');

export function startClock(timeZone) {
  const timeFmt = new Intl.DateTimeFormat('en-US', {
    timeZone,
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });
  const dateFmt = new Intl.DateTimeFormat('en-US', {
    timeZone,
    weekday: 'long',
    month: 'short',
    day: 'numeric',
  });

  const tick = () => {
    const now = new Date();
    const parts = timeFmt.formatToParts(now);
    const grab = (type) => parts.find((p) => p.type === type)?.value ?? '';

    // Write only on change — this runs 86,400 times a day for weeks on end.
    // One compact line: "6:44pm  Sunday, Aug 2".
    setText(timeEl, `${grab('hour')}:${grab('minute')}`);
    setText(meridiemEl, grab('dayPeriod').toLowerCase());
    setText(dateEl, dateFmt.format(now));
  };

  tick();
  setInterval(tick, 1000);
}

function setText(el, value) {
  if (el && el.textContent !== value) el.textContent = value;
}
