// Service Worker para Ecclesia Master
const CACHE_NAME = 'ecclesia-v1';

// Arquivos a serem cacheados (ajuste os caminhos conforme sua estrutura)
const urlsToCache = [
  '/',
  '/static/css/premium.css',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css',
  'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css',
  'https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap'
];

// Instalação - cache dos arquivos
self.addEventListener('install', event => {
  console.log('[SW] Instalando...');
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('[SW] Cache aberto, adicionando arquivos');
        return cache.addAll(urlsToCache);
      })
      .catch(err => console.error('[SW] Erro no cache:', err))
  );
  // Força o SW a ativar imediatamente
  self.skipWaiting();
});

// Ativação - limpa caches antigos
self.addEventListener('activate', event => {
  console.log('[SW] Ativando...');
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheName !== CACHE_NAME) {
            console.log('[SW] Removendo cache antigo:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
  // Toma controle das páginas imediatamente
  event.waitUntil(clients.claim());
});

// Fetch - busca do cache ou rede
self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => {
        // Retorna do cache se encontrar
        if (response) {
          return response;
        }
        // Se não, busca na rede
        return fetch(event.request).then(response => {
          // Verifica se é uma resposta válida
          if (!response || response.status !== 200 || response.type !== 'basic') {
            return response;
          }
          // Clona a resposta para cache
          const responseToCache = response.clone();
          caches.open(CACHE_NAME)
            .then(cache => {
              cache.put(event.request, responseToCache);
            });
          return response;
        });
      })
  );
});