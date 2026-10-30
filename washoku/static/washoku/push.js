/* スイスで和食: プッシュ通知 (マイページのスイッチ・月曜のお知らせ・テスト通知)
   Service Worker と端末の購読は Swiss News と共通なので、
   オフにするときもブラウザの購読そのものは解除しない (ニュースの通知が止まらないように)。

   通知をオンにした端末では、どのページを開いても (1日1回) 購読をサーバーに送り直す。
   Swiss News 側で通知を解除して購読が変わったときや、サーバーで期限切れとして消したときも、
   アプリを開けばまた届くようになる。 */

(function () {
    "use strict";

    var config = document.getElementById("washoku-push-config");
    if (!config) return;

    var toggle = document.getElementById("washoku-push-toggle");
    var weekly = document.getElementById("washoku-push-weekly");
    var test = document.getElementById("washoku-push-test");
    var description = document.getElementById("washoku-push-description");
    var KEY = "washoku_push_on";
    var SYNC_KEY = "washoku_push_synced";
    var SYNC_HOURS = 24;
    var ON_TEXT = "返事が来たときなど、この端末に通知します";

    function supported() {
        return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
    }

    function read(key) {
        try { return localStorage.getItem(key); } catch (error) { return null; }
    }

    function save(key, value) {
        try { localStorage.setItem(key, value); } catch (error) {}
    }

    function readOn() {
        return read(KEY) === "1";
    }

    function show(on, text) {
        if (!toggle) return;
        toggle.setAttribute("aria-pressed", String(on));
        description.textContent = text;
        if (weekly) weekly.hidden = !on;
        if (test) test.hidden = !on;
    }

    function showWeekly(on) {
        if (weekly) weekly.setAttribute("aria-pressed", String(on));
    }

    function toUint8Array(base64String) {
        var padding = "=".repeat((4 - base64String.length % 4) % 4);
        var base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
        return Uint8Array.from(atob(base64), function (c) { return c.charCodeAt(0); });
    }

    function post(url, data) {
        return fetch(url, {
            method: "POST",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json", "X-CSRFToken": config.dataset.csrfToken },
            body: JSON.stringify(data),
        }).then(function (response) {
            return response.json().catch(function () { return {}; }).then(function (body) {
                if (!response.ok) {
                    var error = new Error("push api " + response.status);
                    error.status = response.status;
                    error.body = body;
                    throw error;
                }
                return body;
            });
        });
    }

    async function registration() {
        var reg = await navigator.serviceWorker.getRegistration("/");
        if (!reg) reg = await navigator.serviceWorker.register("/service-worker.js", { scope: "/" });
        await navigator.serviceWorker.ready;
        return reg;
    }

    // この端末の購読 (なければ作る) をサーバーに送る。月曜のお知らせのオン・オフを返す
    async function subscribe() {
        var reg = await registration();
        var subscription = await reg.pushManager.getSubscription();
        if (!subscription) {
            subscription = await reg.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: toUint8Array(config.dataset.publicKey),
            });
        }
        var result = await post(config.dataset.subscribeUrl, subscription.toJSON());
        save(SYNC_KEY, String(Date.now()));
        return { subscription: subscription, weekly: result.weekly !== false };
    }

    async function currentEndpoint() {
        var reg = await navigator.serviceWorker.getRegistration("/");
        var subscription = reg ? await reg.pushManager.getSubscription() : null;
        return subscription ? subscription.endpoint : null;
    }

    async function turnOn() {
        var permission = Notification.permission;
        if (permission === "default") permission = await Notification.requestPermission();
        if (permission !== "granted") {
            show(false, "通知が許可されていません。端末の設定で許可してください。");
            return;
        }
        var result = await subscribe();
        save(KEY, "1");
        show(true, ON_TEXT);
        showWeekly(result.weekly);
    }

    async function turnOff() {
        var endpoint = await currentEndpoint();
        if (endpoint) await post(config.dataset.unsubscribeUrl, { endpoint: endpoint });
        save(KEY, "0");
        show(false, "オフになっています");
    }

    var usable = config.dataset.publicKey && supported();
    var on = usable && readOn() && Notification.permission === "granted";

    // どのページでも: オンにした端末の購読を、1日1回サーバーに送り直す (マイページでは毎回)
    if (on) {
        var last = parseInt(read(SYNC_KEY) || "0", 10) || 0;
        if (toggle || Date.now() - last > SYNC_HOURS * 3600 * 1000) {
            subscribe()
                .then(function (result) { showWeekly(result.weekly); })
                .catch(function () {});
        }
    }

    if (!toggle) return;

    if (!config.dataset.publicKey) {
        toggle.disabled = true;
        show(false, "いまは使えません");
        return;
    }

    if (!supported()) {
        toggle.disabled = true;
        show(false, "iPhone では、ホーム画面に追加したアプリから使えます");
        return;
    }

    if (Notification.permission === "denied") {
        show(false, "通知が拒否されています。端末の設定で許可してください。");
    } else {
        show(on, on ? ON_TEXT : "オフになっています");
    }

    toggle.addEventListener("click", function () {
        var wasOn = toggle.getAttribute("aria-pressed") === "true";
        toggle.disabled = true;
        (wasOn ? turnOff() : turnOn())
            .catch(function () { show(wasOn, "うまく設定できませんでした。時間をおいてもう一度お試しください。"); })
            .finally(function () { toggle.disabled = false; });
    });

    if (weekly) {
        weekly.addEventListener("click", function () {
            var next = weekly.getAttribute("aria-pressed") !== "true";
            weekly.disabled = true;
            currentEndpoint()
                .then(function (endpoint) {
                    if (!endpoint) throw new Error("no subscription");
                    return post(config.dataset.weeklyUrl, { endpoint: endpoint, weekly: next });
                })
                .then(function (result) { showWeekly(result.weekly); })
                .catch(function () {})
                .finally(function () { weekly.disabled = false; });
        });
    }

    if (test) {
        var button = test.querySelector("button");
        var status = test.querySelector("[role=status]");
        button.addEventListener("click", function () {
            button.disabled = true;
            status.textContent = "送っています…";
            subscribe()
                .then(function (result) { return post(config.dataset.testUrl, { endpoint: result.subscription.endpoint }); })
                .then(function () {
                    status.textContent = "送りました。届かないときは、端末の「設定」で通知が許可されているか確認してください。";
                })
                .catch(function () {
                    status.textContent = "送れませんでした。一度オフにして、もう一度オンにしてください。";
                })
                .finally(function () { button.disabled = false; });
        });
    }
})();
