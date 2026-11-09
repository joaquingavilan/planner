{% load static %}/* Service worker — versión {{ version }} */
const V = 'mi-semana-{{ version }}';
const SHELL = ['/', '/lanzamiento/', '/configuracion/',
  {% for f in assets %}"{% static f %}"{% if not forloop.last %},{% endif %}{% endfor %}];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(V).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== V).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  const r = e.request, u = new URL(r.url);
  if (r.method !== 'GET' || u.origin !== location.origin || u.pathname.startsWith('/admin')) return;
  const isStatic = u.pathname.startsWith('/static/');
  e.respondWith(isStatic ? cacheFirst(r) : networkFirst(r));   // páginas y /api/state: red primero, caché como respaldo
});
async function cacheFirst(r) {
  return (await caches.match(r)) || fetch(r).then(res => { const c = res.clone(); caches.open(V).then(x => x.put(r, c)); return res; });
}
async function networkFirst(r) {
  try {
    const res = await fetch(r);
    if (res.ok) { const c = res.clone(); caches.open(V).then(x => x.put(r, c)); }
    return res;
  } catch (err) {
    const hit = await caches.match(r, {ignoreSearch: r.url.includes('/api/state/') ? false : true});
    if (hit) return hit;
    if (r.url.includes('/api/')) return new Response(JSON.stringify({errors: {__all__: ['Sin conexión']}}), {status: 503, headers: {'Content-Type': 'application/json'}});
    throw err;
  }
}
