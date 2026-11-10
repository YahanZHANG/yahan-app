/* スイス掲示板: この端末のプッシュ通知 (設定ページのスイッチとテスト通知)
   Service Worker と端末の購読は Swiss News・和食と共通。オフにしても、ブラウザの購読そのものは
   解除しない (ほかのアプリの通知が止まらないように)。この掲示板の登録だけを消す。 */
(function () {
    "use strict";

    var config = document.getElementById("cb-push-config");
    var toggle = document.getElementById("cb-push-toggle");
    if (!config || !toggle) return;
    var test = document.getElementById("cb-push-test");
    var description = document.getElementById("cb-push-description");
    var KEY = "chiebukuro_push_on";
    var ON_TEXT = "この端末に通知します（頻度と種類は下で選べます）";

    function read() { try { return localStorage.getItem(KEY); } catch (error) { return null; } }
    function save(value) { try { localStorage.setItem(KEY, value); } catch (error) {} }

    function show(on, text) {
        toggle.setAttribute("aria-pressed", String(on));
        description.textContent = text;
        if (test) test.hidden = !on;
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
            if (!response.ok) throw new Error("push api " + response.status);
            return response.json();
        });
    }

    async function registration() {
        var reg = await navigator.serviceWorker.getRegistration("/");
        if (!reg) reg = await navigator.serviceWorker.register("/service-worker.js", { scope: "/" });
        await navigator.serviceWorker.ready;
        return reg;
    }

    async function subscribe() {
        var reg = await registration();
        var subscription = await reg.pushManager.getSubscription();
        if (!subscription) {
            subscription = await reg.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: toUint8Array(config.dataset.publicKey),
            });
        }
        await post(config.dataset.subscribeUrl, subscription.toJSON());
        return subscription;
    }

    async function turnOn() {
        var permission = Notification.permission;
        if (permission === "default") permission = await Notification.requestPermission();
        if (permission !== "granted") {
            show(false, "通知が許可されていません。端末の設定で許可してください。");
            return;
        }
        await subscribe();
        save("1");
        show(true, ON_TEXT);
    }

    async function turnOff() {
        var reg = await navigator.serviceWorker.getRegistration("/");
        var subscription = reg ? await reg.pushManager.getSubscription() : null;
        if (subscription) await post(config.dataset.unsubscribeUrl, { endpoint: subscription.endpoint });
        save("0");
        show(false, "オフになっています");
    }

    if (!config.dataset.publicKey) {
        toggle.disabled = true;
        show(false, "いまは使えません");
        return;
    }
    if (!("serviceWorker" in navigator && "PushManager" in window && "Notification" in window)) {
        toggle.disabled = true;
        show(false, "iPhone では、ホーム画面に追加したアプリから使えます");
        return;
    }

    var on = read() === "1" && Notification.permission === "granted";
    if (Notification.permission === "denied") {
        show(false, "通知が拒否されています。端末の設定で許可してください。");
    } else {
        show(on, on ? ON_TEXT : "オフになっています");
    }
    // オンの端末は、開くたびに登録を送り直す (購読が変わっていても届くように)
    if (on) subscribe().catch(function () {});

    toggle.addEventListener("click", function () {
        var wasOn = toggle.getAttribute("aria-pressed") === "true";
        toggle.disabled = true;
        (wasOn ? turnOff() : turnOn())
            .catch(function () { show(wasOn, "うまく設定できませんでした。時間をおいてもう一度お試しください。"); })
            .finally(function () { toggle.disabled = false; });
    });

    if (test) {
        var button = test.querySelector("button");
        var status = test.querySelector("[role=status]");
        button.addEventListener("click", function () {
            button.disabled = true;
            status.textContent = "送っています…";
            subscribe()
                .then(function (subscription) { return post(config.dataset.testUrl, { endpoint: subscription.endpoint }); })
                .then(function () { status.textContent = "送りました。届かないときは、端末の設定で通知が許可されているか確認してください。"; })
                .catch(function () { status.textContent = "送れませんでした。一度オフにして、もう一度オンにしてください。"; })
                .finally(function () { button.disabled = false; });
        });
    }
})();
