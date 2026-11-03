const CACHE_NAME = "taskflow-v3";
const STATIC_ASSETS = [
  "/static/css/style.css",
  "/static/js/app.js",
  "/static/manifest.json",
  "/static/icons/icon-192x192.png",
  "/static/icons/icon-512x512.png"
];

// Offline fallback HTML
const OFFLINE_FALLBACK = `
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>TaskFlow - Offline</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body { background-color: #0a0a0f; color: #fff; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; text-align: center; }
    .card { background: rgba(18, 18, 28, 0.85); border: 1px solid rgba(139, 92, 246, 0.3); border-radius: 16px; padding: 32px; max-width: 400px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
    h2 { color: #8b5cf6; margin-bottom: 12px; }
    p { color: #a1a1aa; line-height: 1.5; }
    button { background: #8b5cf6; border: none; color: #fff; padding: 10px 20px; border-radius: 8px; font-weight: 600; cursor: pointer; margin-top: 16px; }
  </style>
</head>
<body>
  <div class="card">
    <h2>You're Offline</h2>
    <p>TaskFlow requires a network connection to synchronize your tasks. Please check your internet connection.</p>
    <button onclick="window.location.reload()">Retry Connection</button>
  </div>
</body>
</html>
`;

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      // Cache core assets & offline fallback
      cache.put(new Request('/offline/'), new Response(OFFLINE_FALLBACK, {
        headers: { 'Content-Type': 'text/html' }
      }));
      return cache.addAll(STATIC_ASSETS).catch(err => console.warn('PWA caching warning:', err));
    }).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);

  // Strategy 1: Cache-First for static assets (/static/)
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(request).then((cachedResponse) => {
        if (cachedResponse) {
          return cachedResponse;
        }
        return fetch(request).then((networkResponse) => {
          if (networkResponse && networkResponse.status === 200) {
            const responseClone = networkResponse.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, responseClone));
          }
          return networkResponse;
        });
      })
    );
    return;
  }

  // Strategy 2: Network-First with offline fallback for HTML/navigation requests
  if (request.mode === 'navigate' || (request.method === 'GET' && request.headers.get('accept')?.includes('text/html'))) {
    event.respondWith(
      fetch(request).catch(() => {
        return caches.match('/offline/').then(res => res || new Response("Offline", { status: 503 }));
      })
    );
    return;
  }

  // Default: Network fetch
  event.respondWith(fetch(request));
});

// Push notifications listener
self.addEventListener('push', function(event) {
  let data = {};
  if (event.data) {
    try {
      data = event.data.json();
    } catch(e) {
      data = { title: 'TaskFlow Reminder', body: event.data.text() };
    }
  }

  const options = {
    body: data.body || 'You have an upcoming task reminder!',
    icon: '/static/icons/icon-192x192.png',
    badge: '/static/icons/icon-72x72.png',
    vibrate: [150, 50, 150],
    data: {
      url: data.url || '/'
    }
  };

  event.waitUntil(
    self.registration.showNotification(data.title || 'TaskFlow', options)
  );
});

self.addEventListener('notificationclick', function(event) {
  event.notification.close();
  const targetUrl = event.notification.data ? event.notification.data.url : '/';

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function(clientList) {
      for (let i = 0; i < clientList.length; i++) {
        let client = clientList[i];
        if (client.url.includes(targetUrl) && 'focus' in client) {
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(targetUrl);
      }
    })
  );
});
