// Service Worker pour AI Fitness Coach PWA
const CACHE_NAME = 'fitness-coach-v1.2.0';
const STATIC_CACHE = 'static-cache-v1';
const DYNAMIC_CACHE = 'dynamic-cache-v1';

// Ressources à mettre en cache immédiatement
const STATIC_ASSETS = [
  '/',
  '/static/css/style.css',
  '/static/manifest.json',
  '/track',
  '/progress',
  // Icônes
  '/static/icons/icon-192x192.png',
  '/static/icons/icon-512x512.png',
  // Polices Google Fonts (si utilisées)
  'https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap'
];

// Ressources dynamiques à mettre en cache après la première utilisation
const DYNAMIC_ASSETS = [
  '/static/icons/',
  '/static/screenshots/'
];

// Installation du Service Worker
self.addEventListener('install', event => {
  console.log('Service Worker: Installation...');
  
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then(cache => {
        console.log('Service Worker: Cache statique ouvert');
        return cache.addAll(STATIC_ASSETS);
      })
      .then(() => {
        console.log('Service Worker: Ressources statiques mises en cache');
        return self.skipWaiting(); // Force l'activation immédiate
      })
      .catch(error => {
        console.error('Service Worker: Erreur lors de la mise en cache:', error);
      })
  );
});

// Activation du Service Worker
self.addEventListener('activate', event => {
  console.log('Service Worker: Activation...');
  
  event.waitUntil(
    caches.keys()
      .then(cacheNames => {
        return Promise.all(
          cacheNames.map(cacheName => {
            // Supprimer les anciens caches
            if (cacheName !== STATIC_CACHE && cacheName !== DYNAMIC_CACHE) {
              console.log('Service Worker: Suppression ancien cache:', cacheName);
              return caches.delete(cacheName);
            }
          })
        );
      })
      .then(() => {
        console.log('Service Worker: Nettoyage terminé');
        return self.clients.claim(); // Prendre le contrôle immédiatement
      })
  );
});

// Interception des requêtes réseau
self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);
  
  // Ignorer les requêtes non-HTTP
  if (!request.url.startsWith('http')) {
    return;
  }

  // Stratégie Cache First pour les ressources statiques
  if (isStaticAsset(request.url)) {
    event.respondWith(cacheFirst(request));
    return;
  }

  // Stratégie Network First pour les pages HTML et API
  if (request.destination === 'document' || request.url.includes('/api/')) {
    event.respondWith(networkFirst(request));
    return;
  }

  // Stratégie Cache First par défaut
  event.respondWith(cacheFirst(request));
});

// Vérifier si c'est une ressource statique
function isStaticAsset(url) {
  return url.includes('/static/') || 
         url.includes('.css') || 
         url.includes('.js') || 
         url.includes('.png') || 
         url.includes('.jpg') || 
         url.includes('.jpeg') || 
         url.includes('.svg') ||
         url.includes('fonts.googleapis.com');
}

// Stratégie Cache First
async function cacheFirst(request) {
  try {
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
      console.log('Service Worker: Ressource servie depuis le cache:', request.url);
      return cachedResponse;
    }

    console.log('Service Worker: Ressource non trouvée en cache, récupération réseau:', request.url);
    const networkResponse = await fetch(request);
    
    // Mettre en cache si la réponse est valide
    if (networkResponse.status === 200) {
      const cache = await caches.open(DYNAMIC_CACHE);
      cache.put(request, networkResponse.clone());
    }
    
    return networkResponse;
  } catch (error) {
    console.error('Service Worker: Erreur Cache First:', error);
    
    // Page de fallback pour les erreurs de réseau
    if (request.destination === 'document') {
      return caches.match('/') || new Response('Application hors ligne', {
        status: 503,
        headers: { 'Content-Type': 'text/plain; charset=utf-8' }
      });
    }
    
    throw error;
  }
}

// Stratégie Network First
async function networkFirst(request) {
  try {
    console.log('Service Worker: Tentative réseau:', request.url);
    const networkResponse = await fetch(request);
    
    // Mettre en cache si la réponse est valide
    if (networkResponse.status === 200) {
      const cache = await caches.open(DYNAMIC_CACHE);
      cache.put(request, networkResponse.clone());
    }
    
    return networkResponse;
  } catch (error) {
    console.log('Service Worker: Réseau indisponible, tentative cache:', request.url);
    
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
      return cachedResponse;
    }
    
    // Page de fallback
    if (request.destination === 'document') {
      const fallbackResponse = await caches.match('/');
      if (fallbackResponse) {
        return fallbackResponse;
      }
    }
    
    throw error;
  }
}

// Gestion des messages depuis l'application
self.addEventListener('message', event => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    console.log('Service Worker: Activation forcée depuis l\'application');
    self.skipWaiting();
  }
  
  if (event.data && event.data.type === 'GET_VERSION') {
    event.ports[0].postMessage({ version: CACHE_NAME });
  }
});

// Synchronisation en arrière-plan (pour les futures fonctionnalités)
self.addEventListener('sync', event => {
  console.log('Service Worker: Synchronisation en arrière-plan:', event.tag);
  
  if (event.tag === 'background-sync') {
    event.waitUntil(doBackgroundSync());
  }
});

async function doBackgroundSync() {
  try {
    // Ici vous pourriez synchroniser les données hors ligne
    console.log('Service Worker: Synchronisation des données...');
    
    // Exemple: envoyer les données en attente au serveur
    // const pendingData = await getStoredData();
    // await sendDataToServer(pendingData);
    
  } catch (error) {
    console.error('Service Worker: Erreur lors de la synchronisation:', error);
  }
}

// Notification push (pour les futures fonctionnalités)
self.addEventListener('push', event => {
  console.log('Service Worker: Notification push reçue');
  
  const options = {
    body: event.data ? event.data.text() : 'Nouvelle notification!',
    icon: '/static/icons/icon-192x192.png',
    badge: '/static/icons/icon-72x72.png',
    vibrate: [100, 50, 100],
    data: {
      dateOfArrival: Date.now(),
      primaryKey: '1'
    },
    actions: [
      {
        action: 'explore',
        title: 'Voir l\'application',
        icon: '/static/icons/icon-96x96.png'
      },
      {
        action: 'close',
        title: 'Fermer',
        icon: '/static/icons/close.png'
      }
    ]
  };
  
  event.waitUntil(
    self.registration.showNotification('AI Fitness Coach', options)
  );
});

// Gestion des clics sur notifications
self.addEventListener('notificationclick', event => {
  console.log('Service Worker: Clic sur notification');
  
  event.notification.close();
  
  if (event.action === 'explore') {
    event.waitUntil(
      clients.openWindow('/')
    );
  } else if (event.action === 'close') {
    // Fermer simplement la notification
  } else {
    // Clic sur la notification principale
    event.waitUntil(
      clients.openWindow('/')
    );
  }
});