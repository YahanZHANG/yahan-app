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


// =====================================================
// Receive Push
// =====================================================

self.addEventListener(

    "push",

    (event) => {

        let data = {};

        try {

            data = event.data
                ? event.data.json()
                : {};

        } catch (error) {

            data = {};

        }


        // Yahan News専用

        const title = (
            data.title
            || "Yahan News"
        );

        const body = (
            data.body
            || "スイスニュースが更新されたよ！"
        );


        event.waitUntil(

            self.registration.showNotification(

                title,

                {

                    body: body,

                    // Different update batches can
                    // have separate notifications.

                    tag: (
                        "yahan-news-"
                        + (data.batch_id || "update")
                    ),

                    data: {
                        url: "/news/",
                    },

                }

            )

        );

    }

);


// =====================================================
// Notification click
// =====================================================

self.addEventListener(

    "notificationclick",

    (event) => {

        event.notification.close();


        event.waitUntil(

            (async () => {

                const destination = (
                    self.location.origin
                    + "/news/"
                );


                const windows = (

                    await self.clients.matchAll({

                        type: "window",

                        includeUncontrolled: true,

                    })

                );


                for (const client of windows) {

                    if (

                        client.url.startsWith(
                            self.location.origin
                        )

                    ) {

                        await client.navigate(
                            destination
                        );

                        await client.focus();

                        return;

                    }

                }


                await self.clients.openWindow(
                    destination
                );

            })()

        );

    }

);