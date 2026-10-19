/* ==========================================
   Swiss News - Push client
   push_toggle.js / push_prompt.js から共通で使う
========================================== */

(() => {
    "use strict";

    const config = document.getElementById(
        "news-push-config"
    );

    if (!config) {
        return;
    }

    const publicKey = config.dataset.publicKey;
    const csrfToken = config.dataset.csrfToken;
    const subscribeUrl = config.dataset.subscribeUrl;
    const unsubscribeUrl = config.dataset.unsubscribeUrl;


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

        // pushManager.subscribe は active な
        // Service Worker が必要
        await navigator.serviceWorker.ready;

        return registration;
    }


    // ブラウザがPushに対応しているか
    // （iPhoneはホーム画面に追加したアプリのみ対応）
    function isSupported() {
        return (
            "serviceWorker" in navigator
            && "PushManager" in window
            && "Notification" in window
        );
    }


    function isConfigured() {
        return Boolean(publicKey);
    }


    function permission() {
        return isSupported()
            ? Notification.permission
            : "unsupported";
    }


    async function getSubscription() {
        if (!isSupported()) {
            return null;
        }

        const registration =
            await navigator.serviceWorker.getRegistration("/");

        return registration
            ? await registration.pushManager.getSubscription()
            : null;
    }


    // クリックなどユーザー操作の中から呼ぶこと。
    // 戻り値: "subscribed" / "denied"
    async function subscribe() {
        let result = Notification.permission;

        if (result === "default") {
            result = await Notification.requestPermission();
        }

        if (result !== "granted") {
            return "denied";
        }

        if (!publicKey) {
            throw new Error(
                "VAPID public key is missing."
            );
        }

        const registration = await getRegistration();

        const subscription =
            await registration.pushManager.subscribe({
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
            // サーバーに保存できなかった購読は残さない
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

        return "subscribed";
    }


    async function unsubscribe() {
        const subscription = await getSubscription();

        if (!subscription) {
            return;
        }

        await postJson(
            unsubscribeUrl,
            {
                endpoint: subscription.endpoint,
            }
        );

        await subscription.unsubscribe();
    }


    // 「いりますか？」への回答を端末に保存する
    const choiceKey = "swiss_news_push_choice";

    function readChoice() {
        try {
            return JSON.parse(
                localStorage.getItem(choiceKey)
            );
        } catch (error) {
            return null;
        }
    }

    function saveChoice(value) {
        try {
            localStorage.setItem(
                choiceKey,
                JSON.stringify({
                    value: value,
                    at: Date.now(),
                })
            );
        } catch (error) {
            // 保存できない環境では毎回聞くことになるが動作は続ける
        }
    }


    window.SwissNewsPush = {
        isSupported,
        isConfigured,
        permission,
        getSubscription,
        subscribe,
        unsubscribe,
        readChoice,
        saveChoice,
    };

})();
