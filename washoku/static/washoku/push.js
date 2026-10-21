/* スイスで和食: 返信のプッシュ通知 (マイページのスイッチ)
   Service Worker と端末の購読は Swiss News と共通なので、
   オフにするときもブラウザの購読そのものは解除しない (ニュースの通知が止まらないように)。 */

(function () {
    "use strict";

    var toggle = document.getElementById("washoku-push-toggle");
    if (!toggle) return;

    var description = document.getElementById("washoku-push-description");
    var KEY = "washoku_push_on";

    function supported() {
        return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
    }

    function readOn() {
        try { return localStorage.getItem(KEY) === "1"; } catch (error) { return false; }
    }

    function saveOn(value) {
        try { localStorage.setItem(KEY, value ? "1" : "0"); } catch (error) {}
    }

    function show(on, text) {
        toggle.setAttribute("aria-pressed", String(on));
        description.textContent = text;
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
            headers: { "Content-Type": "application/json", "X-CSRFToken": toggle.dataset.csrfToken },
            body: JSON.stringify(data),
        }).then(function (response) {
            if (!response.ok) throw new Error("push api " + response.status);
        });
    }

    async function registration() {
        var reg = await navigator.serviceWorker.getRegistration("/");
        if (!reg) reg = await navigator.serviceWorker.register("/service-worker.js", { scope: "/" });
        await navigator.serviceWorker.ready;
        return reg;
    }

    async function turnOn() {
        var permission = Notification.permission;
        if (permission === "default") permission = await Notification.requestPermission();
        if (permission !== "granted") {
            show(false, "通知が許可されていません。ブラウザの設定で許可してください。");
            return;
        }
        var reg = await registration();
        var subscription = await reg.pushManager.getSubscription();
        if (!subscription) {
            subscription = await reg.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: toUint8Array(toggle.dataset.publicKey),
            });
        }
        await post(toggle.dataset.subscribeUrl, subscription.toJSON());
        saveOn(true);
        show(true, "返信や質問への答えが届いたら、この端末に通知します");
    }

    async function turnOff() {
        var reg = await navigator.serviceWorker.getRegistration("/");
        var subscription = reg ? await reg.pushManager.getSubscription() : null;
        if (subscription) await post(toggle.dataset.unsubscribeUrl, { endpoint: subscription.endpoint });
        saveOn(false);
        show(false, "オフになっています");
    }

    if (!toggle.dataset.publicKey) {
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
        show(false, "通知が拒否されています。ブラウザの設定で許可してください。");
    } else {
        show(readOn() && Notification.permission === "granted", readOn() ? "返信や質問への答えが届いたら、この端末に通知します" : "オフになっています");
    }

    toggle.addEventListener("click", function () {
        var on = toggle.getAttribute("aria-pressed") === "true";
        toggle.disabled = true;
        (on ? turnOff() : turnOn())
            .catch(function () { show(on, "うまく設定できませんでした。時間をおいてもう一度お試しください。"); })
            .finally(function () { toggle.disabled = false; });
    });
})();
