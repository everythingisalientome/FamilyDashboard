// Photo slideshow: two stacked layers, crossfaded by toggling a class.
// The list comes from /api/photos; a failed refresh keeps the current list.

const layers = Array.from(document.querySelectorAll('.photo-layer'));
const emptyEl = document.getElementById('photo-empty');

let photos = [];
let index = -1;
let visible = 0;
let advancing = false;

export async function startSlideshow({ intervalSeconds, listRefreshSeconds }) {
  await refreshList();
  await advance();
  setInterval(advance, intervalSeconds * 1000);
  setInterval(refreshList, listRefreshSeconds * 1000);
}

async function refreshList() {
  let next;
  try {
    const res = await fetch('/api/photos', { cache: 'no-store' });
    if (!res.ok) throw new Error(`/api/photos returned ${res.status}`);
    const body = await res.json();
    next = (body.data ?? []).map((p) => ({ ...p, src: `${p.url}?v=${p.size}` }));
  } catch (err) {
    console.warn('Photo list refresh failed, keeping current list:', err);
    return;
  }

  // Hold our place across a refresh so adding a photo doesn't restart the loop.
  const currentName = photos[index]?.name;
  photos = next;
  index = currentName ? next.findIndex((p) => p.name === currentName) : -1;

  const empty = photos.length === 0;
  emptyEl.hidden = !empty;
  if (empty) clearLayers();
}

async function advance() {
  if (advancing || photos.length === 0) return;
  advancing = true;
  try {
    // Skip past anything that fails to load rather than freezing on it.
    for (let attempt = 0; attempt < photos.length; attempt++) {
      index = (index + 1) % photos.length;
      const { src } = photos[index];
      try {
        await preload(src);
      } catch (err) {
        console.warn('Skipping unloadable photo:', src, err);
        continue;
      }
      paint(src);
      return;
    }
    console.warn('No loadable photos in the list');
  } finally {
    advancing = false;
  }
}

function paint(src) {
  const nextIndex = (visible + 1) % layers.length;
  const next = layers[nextIndex];
  next.querySelector('.photo-image').src = src;
  next.querySelector('.photo-backdrop').style.backgroundImage = `url("${src}")`;
  next.classList.add('is-visible');
  layers[visible].classList.remove('is-visible');
  visible = nextIndex;
}

function clearLayers() {
  for (const layer of layers) {
    layer.classList.remove('is-visible');
    layer.querySelector('.photo-image').removeAttribute('src');
    layer.querySelector('.photo-backdrop').style.backgroundImage = '';
  }
  visible = 0;
  index = -1;
}

function preload(src) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(src);
    img.onerror = () => reject(new Error('image failed to load'));
    img.src = src;
  });
}
