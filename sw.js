/* PCA Constitution — service worker: offline-first app shell + runtime-cached fonts.
   Bump VERSION when shipping new content/markup to roll the cache. */
const VERSION = 'pcacon-v18';
const CORE = VERSION + '-core';
const FONTS = VERSION + '-fonts';

/* Everything the reader needs to run fully offline. */
const SHELL = [
  '.', 'index.html', 'manifest.webmanifest',
  'icon-192.png', 'icon-512.png', 'apple-touch-icon.png',
  'content/wsc.js', 'content/wlc.js', 'content/wcf.js',
  'content/bco.js', 'content/proofs.js', 'content/verses.js', 'content/citations.js',
  'content/ramsay.js',
];

const FONT_HOSTS = ['fonts.googleapis.com', 'fonts.gstatic.com'];

self.addEventListener('install', e => {
  e.waitUntil((async () => {
    const c = await caches.open(CORE);
    // cache individually so one failure can't abort the whole install
    await Promise.allSettled(SHELL.map(u => c.add(new Request(u, {cache: 'reload'}))));
    self.skipWaiting();
  })());
});

self.addEventListener('activate', e => {
  e.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter(k => k !== CORE && k !== FONTS).map(k => caches.delete(k)));
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);

  // Google Fonts (CSS + font files): cache-first, so type renders offline after first visit.
  if (FONT_HOSTS.includes(url.hostname)) {
    e.respondWith((async () => {
      const cache = await caches.open(FONTS);
      const hit = await cache.match(req);
      if (hit) return hit;
      try {
        const res = await fetch(req);
        if (res && (res.ok || res.type === 'opaque')) cache.put(req, res.clone());
        return res;
      } catch (_) {
        return hit || Response.error();
      }
    })());
    return;
  }

  // Same-origin app assets: cache-first, fall back to network, fall back to shell for navigations.
  if (url.origin === self.location.origin) {
    e.respondWith((async () => {
      const cache = await caches.open(CORE);
      const hit = await cache.match(req, {ignoreSearch: true});
      if (hit) return hit;
      try {
        const res = await fetch(req);
        if (res && res.ok) cache.put(req, res.clone());
        return res;
      } catch (_) {
        if (req.mode === 'navigate') {
          return (await cache.match('index.html')) || (await cache.match('.')) || Response.error();
        }
        return Response.error();
      }
    })());
  }
  // other origins (e.g. the external GA Minutes corpus): pass through to network
});
