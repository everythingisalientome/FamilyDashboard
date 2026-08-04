// Ambient background driver. Reads only data the server already serves — the
// local clock, the sun times + current condition from /api/weather, and the
// date — and translates them into phase / weather / season classes plus the
// celestial-position CSS vars on #scene. All the drawing lives in
// background.css; this file just decides which layers are active. Keeping the
// Pi dumb: no new fetch, everything derived on the client from cached data.

const PHASES = [
  'twilight-dawn', 'dawn', 'sunrise', 'morning', 'noon',
  'afternoon', 'sunset', 'dusk', 'twilight-dusk', 'night',
];
const SEASONS = ['spring', 'summer', 'autumn', 'winter'];
const WEATHERS = ['clear', 'sunny', 'partly', 'cloudy', 'rain', 'thunder', 'snow', 'fog', 'wind'];

// NWS icon token (from /api/weather) -> weather layer state. Resolves the
// spec's overlaps: clear-by-day is Sunny-ish (handled by the sun), clear-by-
// night is the starfield; thunder carries the lightning flash; sleet reads as
// snow. Anything unknown falls back to a calm clear sky.
const TOKEN_TO_WEATHER = {
  clear: 'clear', 'clear-night': 'clear', hot: 'sunny',
  partly: 'partly', 'partly-night': 'partly', cloudy: 'cloudy',
  rain: 'rain', thunder: 'thunder', snow: 'snow', sleet: 'snow',
  fog: 'fog', wind: 'wind',
};

// Sensible defaults so the scene tracks day/night before the first weather
// poll lands (roughly Harrisburg NC, in minutes-since-local-midnight).
const DEFAULT_SUNRISE = 6 * 60 + 30;
const DEFAULT_SUNSET = 19 * 60 + 30;

export function startBackground(settings) {
  const scene = document.getElementById('scene');
  if (!scene) return;

  const tz = settings.timezone;
  let sun = { sunrise: DEFAULT_SUNRISE, sunset: DEFAULT_SUNSET };
  const last = { phase: null, season: null, weather: null };
  const photo = layerPhotos(scene);

  const applyClockDriven = () => {
    const season = seasonFor(tz);
    const now = nowMinutes(tz);
    const phase = phaseFor(now, sun.sunrise, sun.sunset);
    setGroup(scene, 'season-', season, SEASONS, last, 'season');
    setGroup(scene, 'phase-', phase, PHASES, last, 'phase');
    setCelestial(scene, now, sun.sunrise, sun.sunset);
    photo.apply(`${season}-${phase}`);
  };

  const pollWeather = async () => {
    try {
      const res = await fetch('/api/weather', { cache: 'no-store' });
      if (!res.ok) throw new Error(`/api/weather returned ${res.status}`);
      const current = (await res.json()).data?.current;
      if (!current) return;                 // nothing cached — keep the scene

      const sr = isoMinutes(current.sunrise_at);
      const ss = isoMinutes(current.sunset_at);
      if (sr != null && ss != null && ss > sr) sun = { sunrise: sr, sunset: ss };

      const weather = TOKEN_TO_WEATHER[current.icon] ?? 'clear';
      setGroup(scene, 'weather-', weather, WEATHERS, last, 'weather');
      scene.classList.toggle('windy', weather === 'wind');

      applyClockDriven();                    // fold in refreshed sun times now
    } catch (err) {
      console.warn('Background weather poll failed, keeping the scene:', err);
    }
  };

  applyClockDriven();
  setInterval(applyClockDriven, 60 * 1000);  // phase + celestial creep

  pollWeather();
  setInterval(pollWeather, settings.data_refresh_seconds * 1000);

  // Learn which pre-rendered backdrops exist, then re-apply so a matching image
  // swaps in. Until this resolves (and if it fails) the SVG scene shows.
  loadBackgrounds().then((keys) => {
    photo.setAvailable(keys);
    applyClockDriven();
  });
}

async function loadBackgrounds() {
  try {
    const res = await fetch('/api/backgrounds', { cache: 'no-store' });
    if (!res.ok) throw new Error(`/api/backgrounds returned ${res.status}`);
    return (await res.json()).data ?? [];
  } catch (err) {
    console.warn('No background manifest, using the SVG scene:', err);
    return [];
  }
}

// ----- pre-rendered backdrop swap -----------------------------------------

// Crossfades a /img/bg/<key>.jpg backdrop in over the SVG scene when one exists
// for the current season-phase, and falls back to the live SVG when it doesn't
// (so combinations that haven't been generated yet still render). Preloads the
// candidate first, so a 404 never flashes an empty layer on the wall.
function layerPhotos(scene) {
  const layers = scene.querySelectorAll('.scene-photo-layer');
  let available = null;   // Set of existing keys; null until the manifest loads
  let key = null;         // season-phase currently requested
  let active = -1;        // index of the visible layer, or -1 when on the SVG

  const toSvg = () => {
    layers.forEach((l) => l.classList.remove('is-visible'));
    active = -1;
    scene.classList.remove('has-photo');
  };

  const apply = (nextKey) => {
    if (available === null) return;          // wait for the manifest
    if (nextKey === key) return;
    key = nextKey;

    if (!available.has(nextKey)) {           // not generated yet → SVG scene
      toSvg();
      return;
    }

    const url = `/img/bg/${nextKey}.jpg`;
    const probe = new Image();               // preload so the crossfade is clean
    probe.onload = () => {
      if (key !== nextKey) return;           // superseded while loading
      const next = active === 0 ? 1 : 0;
      layers[next].style.backgroundImage = `url("${url}")`;
      layers[next].classList.add('is-visible');
      if (active >= 0 && active !== next) layers[active].classList.remove('is-visible');
      active = next;
      scene.classList.add('has-photo');
    };
    probe.onerror = () => { if (key === nextKey) toSvg(); };  // deleted mid-flight
    probe.src = url;
  };

  const setAvailable = (keys) => { available = new Set(keys); };

  return { apply, setAvailable };
}

// ----- time / date helpers (all in the display timezone) ------------------

function nowMinutes(tz) {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: tz, hour: '2-digit', minute: '2-digit', hour12: false,
  }).formatToParts(new Date());
  const grab = (t) => Number(parts.find((p) => p.type === t)?.value ?? 0);
  return (grab('hour') % 24) * 60 + grab('minute');
}

function isoMinutes(iso) {
  const m = /T(\d{2}):(\d{2})/.exec(iso ?? '');
  return m ? Number(m[1]) * 60 + Number(m[2]) : null;
}

function seasonFor(tz) {
  const month = Number(
    new Intl.DateTimeFormat('en-US', { timeZone: tz, month: 'numeric' }).format(new Date()),
  );
  if (month === 12 || month <= 2) return 'winter';
  if (month <= 5) return 'spring';
  if (month <= 8) return 'summer';
  return 'autumn';
}

// ----- the three dimensions -----------------------------------------------

// Phase boundaries are offsets (minutes) around sunrise/sunset, not fixed
// clock hours — dawn/dusk track the real sun. Evaluated in clock order.
function phaseFor(now, sr, ss) {
  const noon = (sr + ss) / 2;
  if (now < sr - 90 || now >= ss + 90) return 'night';
  if (now < sr - 40) return 'twilight-dawn';
  if (now < sr - 10) return 'dawn';
  if (now < sr + 25) return 'sunrise';
  if (now < noon - 75) return 'morning';
  if (now < noon + 75) return 'noon';
  if (now < ss - 25) return 'afternoon';
  if (now < ss + 10) return 'sunset';
  if (now < ss + 40) return 'dusk';
  return 'twilight-dusk';
}

// Sun rides an arc from sunrise to sunset; the moon rides the night the same
// way. Position is written as CSS vars (x across, y as height) once a minute.
function setCelestial(scene, now, sr, ss) {
  if (now >= sr && now <= ss && ss > sr) {
    const p = (now - sr) / (ss - sr);
    setVars(scene, '--sun', p);
  } else {
    setVars(scene, '--sun', -1);            // parked off-screen (opacity 0 too)
  }

  const nightLen = (1440 - ss) + sr;
  const q = now >= ss ? (now - ss) / nightLen : (now + 1440 - ss) / nightLen;
  setVars(scene, '--moon', q >= 0 && q <= 1 ? q : -1);
}

function setVars(scene, name, progress) {
  if (progress < 0) {
    scene.style.setProperty(`${name}-y`, '-12%');
    return;
  }
  const height = Math.sin(progress * Math.PI);       // 0 at horizon, 1 at peak
  scene.style.setProperty(`${name}-x`, `${(progress * 100).toFixed(1)}%`);
  scene.style.setProperty(`${name}-y`, `${(5 + height * 68).toFixed(1)}%`);
}

// Toggle exactly one class in a group, only touching the DOM on a real change.
function setGroup(scene, prefix, value, all, last, key) {
  if (last[key] === value) return;
  all.forEach((v) => scene.classList.toggle(prefix + v, v === value));
  last[key] = value;
}
