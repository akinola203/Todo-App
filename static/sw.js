const CACHE_NAME = "taskflow-v1";
const urlsToCache = [
  "/",
  "/static/css/style.css",
  "/static/js/app.js",
  "/accounts/login/",
  "/static/manifest.json",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(urlsToCache)),
  );
});

self.addEventListener("fetch", (event) => {
  event.respondWith(
    caches.match(event.request).then((response) => {
      if (response) return response;
      return fetch(event.request);
    }),
  );
});
