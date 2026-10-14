// Image URLs served by KAM can be resized on the server. Grids ask for small
// versions so a page of posters stays light on slow connections.

export const SMALL_IMAGE_WIDTH = 200;
export const GRID_IMAGE_WIDTH = 400;
export const PREVIEW_IMAGE_WIDTH = 800;

const RESIZABLE_PREFIXES = ['/fileproxy?', '/api/plex/image?'];
const PRELOAD_CONCURRENCY = 3;

export function sizedImageUrl(url, width) {
  if (typeof url !== 'string' || !width) return url;
  if (!RESIZABLE_PREFIXES.some((prefix) => url.startsWith(prefix))) return url;
  if (/[?&]w=/.test(url)) return url;
  return `${url}&w=${width}`;
}

// Respect the browser's data saver and very slow connections.
export function canPreload() {
  if (typeof navigator === 'undefined') return false;
  const connection = navigator.connection;
  if (!connection) return true;
  if (connection.saveData) return false;
  return !/(^|-)2g$/.test(String(connection.effectiveType || ''));
}

export function whenIdle(callback) {
  if (typeof window === 'undefined') return () => {};
  if (typeof window.requestIdleCallback === 'function') {
    const handle = window.requestIdleCallback(callback, { timeout: 2000 });
    return () => window.cancelIdleCallback?.(handle);
  }
  const handle = window.setTimeout(callback, 500);
  return () => window.clearTimeout(handle);
}

// Warm the browser cache with *urls* once the page is idle, a few at a time so
// images the user is looking at still load first. Returns a cancel function.
export function preloadImages(urls) {
  const queue = [...new Set((urls || []).filter((url) => typeof url === 'string' && url))];
  if (!queue.length || !canPreload() || typeof Image === 'undefined') return () => {};

  let cancelled = false;
  const pending = new Set();

  const next = () => {
    if (cancelled) return;
    const url = queue.shift();
    if (!url) return;
    const image = new Image();
    pending.add(image);
    image.onload = image.onerror = () => {
      pending.delete(image);
      next();
    };
    image.src = url;
  };

  const cancelIdle = whenIdle(() => {
    for (let i = 0; i < PRELOAD_CONCURRENCY; i += 1) next();
  });

  return () => {
    cancelled = true;
    cancelIdle();
    pending.forEach((image) => {
      image.onload = image.onerror = null;
      image.src = '';
    });
    pending.clear();
  };
}
