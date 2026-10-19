// Shared plumbing for the v2 renderers: polling and element building.

// Fetch one /api/* envelope every `seconds`, handing `data` to `render`.
// A failed poll is logged and skipped, so the region keeps what it shows —
// stale beats blank, and the wall never shows an error or a spinner.
export function poll(url, seconds, render) {
  const refresh = async () => {
    let data;
    try {
      const res = await fetch(url, { cache: 'no-store' });
      if (!res.ok) throw new Error(`${url} returned ${res.status}`);
      data = (await res.json()).data;
    } catch (err) {
      console.warn(`${url} refresh failed, keeping what is on screen:`, err);
      return;
    }
    render(data);
  };
  refresh();
  setInterval(refresh, seconds * 1000);
}

// el('span', 'when', 'Oct 21') — children may be strings or nodes.
export function el(tag, className, ...children) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  node.append(...children);
  return node;
}

// "Thu Oct 22 · 6:30 PM" with the dimmed separators, dropping empty parts.
export function joinSep(parts) {
  const out = [];
  for (const part of parts.filter(Boolean)) {
    if (out.length) out.push(el('span', 'sep', '·'));
    out.push(part);
  }
  return out;
}

export function setText(node, value) {
  if (node && node.textContent !== value) node.textContent = value;
}

// One weather glyph from the <symbol> set in v2.html.
const SVG = 'http://www.w3.org/2000/svg';
const KNOWN_ICONS = new Set([
  'clear', 'clear-night', 'partly', 'partly-night', 'cloudy', 'rain',
  'thunder', 'snow', 'sleet', 'fog', 'wind', 'hot',
]);

export function symbolHref(icon) {
  return KNOWN_ICONS.has(icon) ? `#wx-${icon}` : '#wx-clear';
}

export function wxIcon(icon) {
  const svg = document.createElementNS(SVG, 'svg');
  svg.setAttribute('class', 'wx-icon');
  svg.setAttribute('aria-hidden', 'true');
  const use = document.createElementNS(SVG, 'use');
  use.setAttribute('href', symbolHref(icon));
  svg.append(use);
  return svg;
}
