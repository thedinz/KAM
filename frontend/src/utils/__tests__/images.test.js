import { afterEach, describe, expect, it, vi } from 'vitest';
import { canPreload, preloadImages, sizedImageUrl } from '../images.js';

describe('sizedImageUrl', () => {
  it('adds a width to KAM image URLs', () => {
    expect(sizedImageUrl('/fileproxy?path=%2Fassets%2Fposter.jpg&t=1', 400)).toBe(
      '/fileproxy?path=%2Fassets%2Fposter.jpg&t=1&w=400'
    );
    expect(sizedImageUrl('/api/plex/image?path=%2Flibrary%2Fmetadata%2F1%2Fthumb', 200)).toBe(
      '/api/plex/image?path=%2Flibrary%2Fmetadata%2F1%2Fthumb&w=200'
    );
  });

  it('leaves other URLs and already sized URLs alone', () => {
    expect(sizedImageUrl('/fallback.png', 400)).toBe('/fallback.png');
    expect(sizedImageUrl('http://plex.local/library/metadata/1/thumb', 400)).toBe(
      'http://plex.local/library/metadata/1/thumb'
    );
    expect(sizedImageUrl('/fileproxy?path=a&w=200', 400)).toBe('/fileproxy?path=a&w=200');
    expect(sizedImageUrl(null, 400)).toBe(null);
  });
});

describe('preloading', () => {
  const originalConnection = Object.getOwnPropertyDescriptor(navigator, 'connection');

  afterEach(() => {
    if (originalConnection) {
      Object.defineProperty(navigator, 'connection', originalConnection);
    } else {
      delete navigator.connection;
    }
    vi.useRealTimers();
  });

  function setConnection(value) {
    Object.defineProperty(navigator, 'connection', { value, configurable: true });
  }

  it('is skipped with data saver or a 2G connection', () => {
    setConnection({ saveData: true, effectiveType: '4g' });
    expect(canPreload()).toBe(false);
    setConnection({ saveData: false, effectiveType: 'slow-2g' });
    expect(canPreload()).toBe(false);
    setConnection({ saveData: false, effectiveType: '3g' });
    expect(canPreload()).toBe(true);
  });

  it('loads each image once when idle and can be cancelled first', () => {
    vi.useFakeTimers();
    setConnection({ saveData: false, effectiveType: '4g' });
    const loaded = [];
    const OriginalImage = window.Image;
    window.Image = class {
      set src(value) {
        if (value) loaded.push(value);
      }
    };
    try {
      const cancel = preloadImages(['/a.jpg', '/a.jpg', '/b.jpg']);
      expect(loaded).toEqual([]);
      vi.runAllTimers();
      expect(loaded).toEqual(['/a.jpg', '/b.jpg']);
      cancel();

      loaded.length = 0;
      const cancelEarly = preloadImages(['/c.jpg']);
      cancelEarly();
      vi.runAllTimers();
      expect(loaded).toEqual([]);
    } finally {
      window.Image = OriginalImage;
    }
  });
});
