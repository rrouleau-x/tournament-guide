/* Tournament Guide — service worker
 *
 * Strategy
 *  - App shell + JSON: NETWORK-FIRST WITH A TIMEOUT. Fresh content wins whenever the
 *    network answers promptly; if it has not answered in NET_TIMEOUT ms (one bar at
 *    the fields) the cached copy is served instead of leaving the parent on a spinner.
 *    The slow response still lands in the cache for the next visit.
 *  - Everything else same-origin (PDFs, icons): CACHE-FIRST, refreshed in the
 *    background, so a 350 KB guide is not re-downloaded on every open.
 *
 * Two rules that have bitten this app before:
 *  1. Cache deletion is SCOPED to our own prefix. A bare
 *     keys.filter(k => k !== CACHE) nukes every other cache on the origin.
 *  2. Never precache large binaries (PDFs). They get cached on first view.
 */
const CACHE = 'tournament-guide-v36';
const PREFIX = 'tournament-guide-';
const SHELL = ['./', './tournaments.json', './teams.json', './manifest.json'];
const NET_TIMEOUT = 3000;

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c =>
      // fail-soft: one missing entry must not abort the whole install
      Promise.all(SHELL.map(u => c.add(new Request(u, { cache: 'reload' })).catch(() => null)))
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

  // Query strings (?t=…&team=…, old ?_=<ts> cache-busters) never change the file that is
  // served, so the cache key is the bare URL: one entry per file, reused by every link.
  url.search = '';
  let cacheKey = url.href;
  if (cacheKey.endsWith('/index.html')) cacheKey = cacheKey.slice(0, -'index.html'.length);

  const isFresh = req.mode === 'navigate' || /\.(json|html)$/.test(url.pathname) || url.pathname.endsWith('/');

  e.respondWith((async () => {
    const cache = await caches.open(CACHE);
    const network = fetch(req, { cache: 'no-cache' }).then(res => {
      if (res && res.status === 200) cache.put(cacheKey, res.clone());
      return res;
    });

    if (!isFresh) {
      const hit = await cache.match(cacheKey);
      if (hit) { e.waitUntil(network.catch(() => null)); return hit; }
      return network;
    }

    const cached = await cache.match(cacheKey);
    if (!cached) return network;                      // nothing saved yet: the network is the only option
    e.waitUntil(network.catch(() => null));           // let a slow response finish and update the cache
    const timeout = new Promise(resolve => setTimeout(() => resolve(null), NET_TIMEOUT));
    try {
      const res = await Promise.race([network, timeout]);
      return (res && res.status === 200) ? res : cached;
    } catch (_) {
      return cached;                                  // offline
    }
  })());
});
