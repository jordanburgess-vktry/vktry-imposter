// Offline support for the installed app. Every request tries the network first, so new words
// and new versions of the game show up as soon as there's a connection; the cached copy is only
// used when the phone is offline or the network is too slow.
const CACHE = "vktry-imposter-v2";
const CORE = ["./", "index.html", "words.json", "manifest.webmanifest",
  "icons/icon-192.png", "icons/icon-512.png", "icons/apple-touch-icon.png"];
const NETWORK_WAIT_MS = 4000;

self.addEventListener("install", event => {
  event.waitUntil(caches.open(CACHE).then(c => c.addAll(CORE)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim()));
});

self.addEventListener("fetch", event => {
  const req = event.request;
  if (req.method !== "GET" || new URL(req.url).origin !== self.location.origin) return;
  event.respondWith(networkFirst(req));
});

async function networkFirst(req) {
  const cache = await caches.open(CACHE);
  try {
    const res = await Promise.race([
      fetch(req, {cache: "no-store"}),
      new Promise((_, reject) => setTimeout(() => reject(new Error("network too slow")), NETWORK_WAIT_MS)),
    ]);
    if (res.ok) cache.put(req, res.clone());
    return res;
  } catch (err) {
    const cached = await cache.match(req, {ignoreSearch: true});
    if (cached) return cached;
    console.warn("Offline and not cached:", req.url, err);
    throw err;
  }
}
