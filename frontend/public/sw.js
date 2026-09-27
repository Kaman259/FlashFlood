const CACHE_NAME = "flashflood-shell-v1";
const MAP_TILE_CACHE_NAME = "flashflood-map-tiles-v1";
const MAP_TILE_CACHE_LIMIT = 160;

const APP_SHELL = [
  "/",
  "/index.html",
];

const ACTIVE_FLASHFLOOD_CACHES = new Set([
  CACHE_NAME,
  MAP_TILE_CACHE_NAME,
]);

function isOpenStreetMapTileRequest(request, url) {
  const hostname = url.hostname.toLowerCase();

  return (
    request.method === "GET" &&
    request.destination === "image" &&
    (
      hostname === "tile.openstreetmap.org" ||
      hostname.endsWith(".tile.openstreetmap.org")
    )
  );
}

function canCacheMapTileResponse(response) {
  if (!response) {
    return false;
  }

  // With the current Leaflet <img> tile loading path, cross-origin tile
  // responses may be opaque. Cache Storage may safely replay such responses
  // to the same image request, even though JavaScript cannot inspect their
  // status/body. The strict OSM hostname + image-destination allowlist above
  // prevents this exception from becoming generic third-party caching.
  if (response.type === "opaque") {
    return true;
  }

  return response.ok && response.status === 200;
}

async function cacheMapTile(request, response) {
  try {
    const cache = await caches.open(MAP_TILE_CACHE_NAME);
    await cache.put(request, response);

    const keys = await cache.keys();

    if (keys.length > MAP_TILE_CACHE_LIMIT) {
      const excess = keys.length - MAP_TILE_CACHE_LIMIT;
      const oldestKeys = keys.slice(0, excess);

      await Promise.all(
        oldestKeys.map((oldRequest) => cache.delete(oldRequest)),
      );
    }
  } catch {
    // Tile caching is best-effort and must never break online map rendering.
  }
}

function handleMapTileRequest(event, request) {
  const networkRequest = fetch(request);

  // Register caching as background lifetime work without delaying the
  // network response. The same network request is used for both paths.
  event.waitUntil(
    networkRequest
      .then((response) => {
        if (!canCacheMapTileResponse(response)) {
          return undefined;
        }

        return cacheMapTile(request, response.clone());
      })
      .catch(() => undefined),
  );

  return networkRequest.catch(async () => {
    const cache = await caches.open(MAP_TILE_CACHE_NAME);
    const cachedResponse = await cache.match(request);

    return cachedResponse || Response.error();
  });
}

// Install the service worker and cache the basic application shell.
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(APP_SHELL);
    }),
  );

  self.skipWaiting();
});

// Take control of open pages immediately after activation.
// Preserve the Stage 13A shell cache and the Stage 13C map-tile cache while
// removing obsolete FlashFlood-owned cache versions only.
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter(
            (cacheName) =>
              cacheName.startsWith("flashflood-") &&
              !ACTIVE_FLASHFLOOD_CACHES.has(cacheName),
          )
          .map((cacheName) => caches.delete(cacheName)),
      );
    }),
  );

  self.clients.claim();
});

// Network first, then cache fallback.
// Application-shell caching remains separate from OSM tile caching.
self.addEventListener("fetch", (event) => {
  const request = event.request;

  if (request.method !== "GET") {
    return;
  }

  const url = new URL(request.url);

  // Never place API/backend traffic in the shell or map-tile cache.
  if (
    url.origin === self.location.origin &&
    url.pathname.startsWith("/api/")
  ) {
    return;
  }

  if (isOpenStreetMapTileRequest(request, url)) {
    event.respondWith(
      handleMapTileRequest(event, request),
    );
    return;
  }

  event.respondWith(
    fetch(request)
      .then((response) => {
        if (
          response &&
          response.status === 200 &&
          response.type === "basic"
        ) {
          const responseClone = response.clone();

          caches.open(CACHE_NAME).then((cache) => {
            cache.put(request, responseClone);
          });
        }

        return response;
      })
      .catch(() => {
        return caches.match(request).then((cachedResponse) => {
          if (cachedResponse) {
            return cachedResponse;
          }

          // For navigation requests, fall back to the cached application shell.
          if (request.mode === "navigate") {
            return caches.match("/index.html");
          }

          return Response.error();
        });
      }),
  );
});