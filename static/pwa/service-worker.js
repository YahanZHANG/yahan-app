/* =====================================================
   App Service Worker
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


        // Swiss News と スイスで和食 で共通。
        // url / tag がなければ Swiss News の通知として扱う。

        const title = (
            data.title
            || "Swiss News"
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
                        data.tag
                        || (
                            "Swiss-news-"
                            + (data.batch_id || "update")
                        )
                    ),

                    data: {
                        url: (
                            typeof data.url === "string"
                            && data.url.startsWith("/")
                            && !data.url.startsWith("//")
                        )
                            ? data.url
                            : "/news/",
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

                const path = (
                    event.notification.data
                    && event.notification.data.url
                ) || "/news/";

                const destination = (
                    self.location.origin
                    + path
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