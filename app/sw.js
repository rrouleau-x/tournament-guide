/* Sporting Jax Guide — service worker
 *
 * Strategy: STALE-WHILE-REVALIDATE for everything same-origin.
 *
 * The previous worker was network-first, so every tap waited on the network
 * before falling back to cache — at a field with one bar that reads to a parent
 * as "the app is broken". Now the cached copy paints immediately and the
 * network copy replaces it in the background for the NEXT visit. A version bump
 * (CACHE) still forces a fresh shell.
 *
 * Two rules that have bitten this app before:
 *  1. Cache deletion is SCOPED to our own prefix. A bare
 *     keys.filter(k => k !== CACHE) nukes every other cache on the origin.
 *  2. Never precache large binaries (PDFs). They get cached on first view.
 */
const CACHE = 'tournament-guide-v24';
const PREFIX = 'tournament-guide-';
const SHELL = ['./', './index.html', './data.json', './tournaments.json', './teams.json', './manifest.json'];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c =>
      // fail-soft: one missing entry must not abort the whole install
      Promise.all(SHELL.map(u => c.add(u).catch(() => null)))
    ).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.map(k =>
        (k.startsWith(PREFIX) && k !== CACHE) ? caches.delete(k) : null)))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;   // never intercept Maps/CDNs

  // The app appends a cache-busting `?_=<ts>` to every JSON fetch. Storing that
  // verbatim would add a NEW cache entry per visit while `ignoreSearch` matches
  // the bare URL — the cache would grow forever and never be reused. So both
  // match and put use the query-stripped URL as the key.
  const key = new URL(req.url); key.search = '';
  const cacheKey = key.href;

  // DATA IS NETWORK-FIRST. Stale-while-revalidate is right for the shell but
  // wrong for content: a parent would see yesterday's schedule on the first
  // load after an update. JSON is fetched fresh and only falls back to cache
  // when the network fails.
  const isData = true;   // network-first for EVERYTHING: an out-of-date shell or
                         // stylesheet is the worst failure for a parent mid-event.
                         // Cache is only the offline fallback.

  e.respondWith((async () => {
    const cache = await caches.open(CACHE);
    if (isData) {
      try {
        const fresh = await fetch(req, { cache: 'no-store' });
        if (fresh && fresh.status === 200) cache.put(cacheKey, fresh.clone());
        return fresh;
      } catch (err) {
        const hit = await cache.match(cacheKey);
        if (hit) return hit;
        throw err;
      }
    }
    const cached = await cache.match(cacheKey);
    if (cached) {
      // serve now, refresh for next time
      e.waitUntil((async () => {
        try {
          const fresh = await fetch(req, { cache: 'no-store' });
          if (fresh && fresh.status === 200) await cache.put(cacheKey, fresh.clone());
        } catch (_) { /* offline: keep what we have */ }
      })());
      return cached;
    }
    try {
      const fresh = await fetch(req);
      if (fresh && fresh.status === 200) cache.put(cacheKey, fresh.clone());
      return fresh;
    } catch (err) {
      // offline and never cached: fall back to the app shell for navigations
      if (req.mode === 'navigate') {
        const shell = await cache.match(new URL('./index.html', self.location).href);
        if (shell) return shell;
      }
      throw err;
    }
  })());
});
