/* ==========================================
   Yahan News - Inline Push Toggle
========================================== */

(() => {
    "use strict";

    const root = document.getElementById(
        "news-push-settings"
    );

    if (!root) {
        return;
    }

    const button = document.getElementById(
        "news-push-toggle"
    );

    const state = document.getElementById(
        "news-push-toggle-state"
    );

    const status = document.getElementById(
        "news-push-status"
    );

    const publicKey = root.dataset.publicKey;
    const csrfToken = root.dataset.csrfToken;

    const subscribeUrl = root.dataset.subscribeUrl;
    const unsubscribeUrl = root.dataset.unsubscribeUrl;


    /* ======================================
       Helpers
    ====================================== */

    function toUint8Array(base64String) {
        const padding = "=".repeat(
            (4 - base64String.length % 4) % 4
        );

        const base64 = (
            base64String
                .replace(/-/g, "+")
                .replace(/_/g, "/")
            + padding
        );

        return Uint8Array.from(
            atob(base64),
            character => character.charCodeAt(0)
        );
    }


    async function postJson(url, data) {
        const response = await fetch(url, {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken,
            },
            body: JSON.stringify(data),
        });

        if (!response.ok) {
            throw new Error(
                `Push API failed: ${response.status}`
            );
        }
    }


    async function getRegistration() {
        let registration =
            await navigator.serviceWorker.getRegistration("/");

        if (!registration) {
            registration =
                await navigator.serviceWorker.register(
                    "/service-worker.js",
                    {
                        scope: "/",
                    }
                );
        }

        return registration;
    }


    /* ======================================
       UI
    ====================================== */

    function updateUI(isOn) {
        button.classList.toggle(
            "is-on",
            isOn
        );

        button.setAttribute(
            "aria-pressed",
            String(isOn)
        );

        state.textContent = isOn
            ? "ON"
            : "OFF";

        status.textContent = isOn
            ? "この端末では通知がONになっているよ。"
            : "この端末では通知がOFFになっているよ。";

        button.disabled = false;
    }


    /* ======================================
       Check current subscription
    ====================================== */

    async function refresh() {
        const registration =
            await navigator.serviceWorker.getRegistration("/");

        const subscription = registration
            ? await registration.pushManager.getSubscription()
            : null;

        updateUI(Boolean(subscription));

        if (Notification.permission === "denied") {
            status.textContent =
                "ブラウザ側で通知がブロックされているよ。"
                + " 端末の通知設定を確認してね。";
        }
    }


    /* ======================================
       ON / OFF
    ====================================== */

    button.addEventListener(
        "click",
        async () => {

            button.disabled = true;

            status.textContent =
                "通知設定を変更中...";

            try {
                const registration =
                    await navigator.serviceWorker.getRegistration("/");

                const currentSubscription = registration
                    ? await registration.pushManager.getSubscription()
                    : null;


                /* ==========================
                   Turn OFF
                ========================== */

                if (currentSubscription) {
                    await postJson(
                        unsubscribeUrl,
                        {
                            endpoint:
                                currentSubscription.endpoint,
                        }
                    );

                    const removed =
                        await currentSubscription.unsubscribe();

                    if (!removed) {
                        throw new Error(
                            "Browser unsubscribe failed."
                        );
                    }

                    updateUI(false);
                    return;
                }


                /* ==========================
                   Turn ON
                ========================== */

                // Request permission directly
                // from the user's click action.

                let permission =
                    Notification.permission;

                if (permission === "default") {
                    permission =
                        await Notification.requestPermission();
                }

                if (permission !== "granted") {
                    status.textContent =
                        "通知が許可されていないよ。"
                        + " ブラウザや端末の設定を確認してね。";

                    return;
                }

                if (!publicKey) {
                    throw new Error(
                        "VAPID public key is missing."
                    );
                }

                const readyRegistration =
                    await getRegistration();

                const subscription =
                    await readyRegistration.pushManager.subscribe({
                        userVisibleOnly: true,
                        applicationServerKey:
                            toUint8Array(publicKey),
                    });

                try {
                    await postJson(
                        subscribeUrl,
                        subscription.toJSON()
                    );
                } catch (error) {
                    // Do not leave a browser subscription
                    // that was not saved in Django.
                    try {
                        await subscription.unsubscribe();
                    } catch (cleanupError) {
                        console.warn(
                            "Push cleanup failed:",
                            cleanupError
                        );
                    }

                    throw error;
                }

                updateUI(true);

            } catch (error) {
                console.error(
                    "News Push toggle failed:",
                    error
                );

                try {
                    await refresh();
                } catch (refreshError) {
                    console.warn(
                        "Push refresh failed:",
                        refreshError
                    );
                }

                status.textContent =
                    "通知設定を変更できなかったよ。"
                    + " もう一度試してね。";

            } finally {
                button.disabled = false;
            }

        }
    );


    /* ======================================
       Initialize
    ====================================== */

    async function initialize() {
        if (
            !("serviceWorker" in navigator)
            || !("PushManager" in window)
            || !("Notification" in window)
        ) {
            status.textContent =
                "この環境ではPush通知を利用できないよ。"
                + " iPhoneの場合はホーム画面から開いてね。";

            state.textContent = "—";
            return;
        }

        if (!publicKey) {
            status.textContent =
                "Push通知のサーバー設定が未完了だよ。";

            state.textContent = "—";
            return;
        }

        try {
            await refresh();
        } catch (error) {
            console.error(
                "Push initialization failed:",
                error
            );

            status.textContent =
                "通知の状態を確認できなかったよ。";

            state.textContent = "—";
        }
    }

    initialize();

})();