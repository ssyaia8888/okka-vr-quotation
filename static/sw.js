/* OKKA VR Quotation - Service Worker (PWA) */
const CACHE_NAME = 'okka-vr-v1';
const CORE_ASSETS = [
  '/',
  '/static/manifest.json',
  '/static/css/mobile.css'
];

// 安裝時快取核心資源
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(CORE_ASSETS))
      .then(() => self.skipWaiting())
  );
});

// 啟動時激活 + 清除舊快取
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys.filter(k => k !== CACHE_NAME)
            .map(k => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

// 離線優先 + 網絡回退
self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;

  event.respondWith(
    caches.match(event.request)
      .then((cached) => {
        if (cached) return cached;
        return fetch(event.request)
          .then((response) => {
            // 快取成功嘅 GET 請求
            if (response.status === 200 && response.type === 'basic') {
              const clone = response.clone();
              caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
            }
            return response;
          })
          .catch(() => {
            // 離線回退: 返回離線頁面
            if (event.request.destination === 'document') {
              return new Response(
                '<!DOCTYPE html><html><head><meta charset="utf-8"><title>離線</title>' +
                '<style>body{font-family:sans-serif;background:#1a1a2e;color:#fff;text-align:center;padding:50px}' +
                '.box{background:#16213e;padding:30px;border-radius:10px;max-width:400px;margin:auto}</style>' +
                '</head><body><div class="box"><h1>📱 離線模式</h1>' +
                '<p>而家冇網絡連接。</p><p>報價單頁面需要網絡載入 3D 模型。</p>' +
                '<p>恢復網絡後重試。</p></div></body></html>',
                {status: 503, headers: {'Content-Type': 'text/html; charset=utf-8'}}
              );
            }
            return new Response('', {status: 503});
          });
      })
  );
});
