import '@testing-library/jest-dom/vitest';
import { afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';

// Node 25+ has its own localStorage/sessionStorage globals, which are undefined
// without --localstorage-file and stop vitest from installing jsdom's. Use jsdom's.
for (const name of ['localStorage', 'sessionStorage']) {
  Object.defineProperty(globalThis, name, {
    configurable: true,
    value: globalThis.jsdom.window[name],
  });
}

afterEach(() => {
  cleanup();
});
