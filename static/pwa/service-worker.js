/* =====================================================
   Yahan App Service Worker
   ===================================================== */


// =====================================================
// Install
// =====================================================

self.addEventListener(

    "install",

    (event) => {

        event.waitUntil(

            self.skipWaiting()

        );

    }

);


// =====================================================
// Activate
// =====================================================

self.addEventListener(

    "activate",

    (event) => {

        event.waitUntil(

            self.clients.claim()

        );

    }

);


/* =====================================================
   Future features

   - Web Push notifications
   - Notification click handling

   No fetch interception or offline cache yet.
   ===================================================== */