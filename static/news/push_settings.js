/* =====================================================
   Yahan News Push Settings
   ===================================================== */

(() => {

    "use strict";


    const root = document.getElementById(
        "news-push-settings"
    );

    if (!root) {
        return;
    }


    const status = document.getElementById(
        "news-push-status"
    );

    const enableButton = document.getElementById(
        "news-push-enable"
    );

    const disableButton = document.getElementById(
        "news-push-disable"
    );


    const publicKey = root.dataset.publicKey;

    const subscribeUrl = (
        root.dataset.subscribeUrl
    );

    const unsubscribeUrl = (
        root.dataset.unsubscribeUrl
    );


    const csrfToken = document.querySelector(
        "#news-push-form [name=csrfmiddlewaretoken]"
    ).value;


    // =================================================
    // Public key conversion
    // =================================================

    function urlBase64ToUint8Array(base64String) {

        const padding = "=".repeat(
            (4 - base64String.length % 4) % 4
        );

        const base64 = (
            base64String
            .replace(/-/g, "+")
            .replace(/_/g, "/")
            + padding
        );

        const rawData = atob(
            base64
        );

        return Uint8Array.from(

            rawData,

            character => character.charCodeAt(0)

        );

    }


    // =================================================
    // API request
    // =================================================

    async function postJson(url, data) {

        const response = await fetch(

            url,

            {

                method: "POST",

                credentials: "same-origin",

                headers: {

                    "Content-Type": (
                        "application/json"
                    ),

                    "X-CSRFToken": csrfToken,

                },

                body: JSON.stringify(
                    data
                ),

            }

        );


        if (!response.ok) {

            throw new Error(
                "Server request failed."
            );

        }

    }


    // =================================================
    // UI
    // =================================================

    function showEnabled() {

        status.textContent = (
            "✅ この端末では通知がONになっている。"
        );

        enableButton.hidden = true;

        disableButton.hidden = false;

    }


    function showDisabled() {

        status.textContent = (
            "現在、この端末の通知はOFF。"
        );

        enableButton.hidden = false;

        enableButton.disabled = false;

        disableButton.hidden = true;

    }


    // =================================================
    // Initial status
    // =================================================

    async function initialize() {

        if (

            !("serviceWorker" in navigator)

            || !("PushManager" in window)

            || !("Notification" in window)

        ) {

            status.textContent = (
                "この環境ではPush通知を利用できない。"
                + " iPhoneの場合はホーム画面に"
                + " Yahan-appを追加してから開いてね。"
            );

            return;

        }


        if (!publicKey) {

            status.textContent = (
                "Push通知のサーバー設定が未完了。"
            );

            return;

        }


        const registration = (

            await navigator.serviceWorker.getRegistration(
                "/"
            )

        );


        const subscription = registration

            ? await registration.pushManager.getSubscription()

            : null;


        if (subscription) {

            showEnabled();

        } else {

            showDisabled();

        }

    }


    // =================================================
    // Enable Push
    // =================================================

    enableButton.addEventListener(

        "click",

        async () => {

            enableButton.disabled = true;

            status.textContent = (
                "通知を設定中..."
            );


            try {

                // Permission request must originate
                // from a user action.

                const permission = (

                    await Notification.requestPermission()

                );


                if (permission !== "granted") {

                    status.textContent = (
                        "通知が許可されていない。"
                        + " 端末の通知設定を確認してね。"
                    );

                    return;

                }


                // Register the existing PWA worker.

                const registration = (

                    await navigator.serviceWorker.register(

                        "/service-worker.js",

                        {
                            scope: "/",
                        }

                    )

                );


                let subscription = (

                    await registration.pushManager.getSubscription()

                );


                if (!subscription) {

                    subscription = (

                        await registration.pushManager.subscribe({

                            userVisibleOnly: true,

                            applicationServerKey: (
                                urlBase64ToUint8Array(
                                    publicKey
                                )
                            ),

                        })

                    );

                }


                // Save subscription to Django.

                await postJson(

                    subscribeUrl,

                    subscription.toJSON()

                );


                showEnabled();

            } catch (error) {

                status.textContent = (
                    "通知の設定に失敗した。"
                    + " もう一度試してね。"
                );

            } finally {

                enableButton.disabled = false;

            }

        }

    );


    // =================================================
    // Disable Push
    // =================================================

    disableButton.addEventListener(

        "click",

        async () => {

            disableButton.disabled = true;


            try {

                const registration = (

                    await navigator.serviceWorker.getRegistration(
                        "/"
                    )

                );


                const subscription = registration

                    ? await registration.pushManager.getSubscription()

                    : null;


                if (subscription) {

                    // Remove server-side registration
                    // before unsubscribing locally.

                    await postJson(

                        unsubscribeUrl,

                        {
                            endpoint: subscription.endpoint,
                        }

                    );


                    await subscription.unsubscribe();

                }


                showDisabled();

            } catch (error) {

                status.textContent = (
                    "通知の解除を確認できなかった。"
                    + " もう一度試してね。"
                );

            } finally {

                disableButton.disabled = false;

            }

        }

    );


    // =================================================
    // Start
    // =================================================

    initialize().catch(

        () => {

            status.textContent = (
                "通知設定を確認できなかった。"
            );

        }

    );

})();