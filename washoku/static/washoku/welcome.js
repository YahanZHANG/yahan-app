/* スイスで和食: 下から出る案内。いちどに1つだけ出す。
   1. 携帯のブラウザで開いているとき: ホーム画面に追加 (初めて開いたときと、その1週間後)
   2. ホーム画面から開いたとき (または追加できない PC): 会員なら通知、未ログインなら会員登録 (1回だけ)
   いつ出したかは、この端末の localStorage にだけ残す。 */

(function () {
    "use strict";

    var sheet = document.getElementById("washoku-welcome");
    if (!sheet) return;

    var FIRST_SEEN = "washoku_first_seen";
    var INSTALL_STAGE = "washoku_welcome_stage";
    var NEXT_SHOWN = "washoku_welcome_next_shown";
    var WEEK = 7 * 24 * 60 * 60 * 1000;

    function read(key) {
        try { return localStorage.getItem(key); } catch (error) { return null; }
    }

    function write(key, value) {
        try { localStorage.setItem(key, value); } catch (error) {}
    }

    var ua = navigator.userAgent;
    var isIOS = /iPhone|iPad|iPod/.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
    var isAndroid = /Android/.test(ua);
    var standalone = window.matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;

    var steps = {};
    sheet.querySelectorAll("[data-welcome-step]").forEach(function (section) {
        steps[section.dataset.welcomeStep] = section;
    });

    // ホーム画面に追加の手順を、端末に合わせて1つだけ見せる
    if (isIOS) {
        var safari = !/CriOS|FxiOS|EdgiOS/.test(ua);
        sheet.querySelector(safari ? "[data-install-ios-safari]" : "[data-install-ios-browser]").hidden = false;
    } else if (isAndroid) {
        sheet.querySelector("[data-install-android]").hidden = false;
    } else {
        sheet.querySelector("[data-install-desktop]").hidden = false;
    }

    // Android の Chrome などでは、ボタン1つで追加できる
    var installButton = sheet.querySelector("[data-install-button]");
    var deferredPrompt = null;

    window.addEventListener("beforeinstallprompt", function (event) {
        event.preventDefault();
        deferredPrompt = event;
        installButton.hidden = false;
    });

    installButton.addEventListener("click", function () {
        if (!deferredPrompt) return;
        deferredPrompt.prompt();
        deferredPrompt.userChoice.finally(function () {
            deferredPrompt = null;
            installButton.hidden = true;
        });
    });

    function open(name) {
        Object.keys(steps).forEach(function (key) {
            steps[key].hidden = key !== name;
        });
        sheet.hidden = false;
    }

    function close() {
        sheet.hidden = true;
    }

    sheet.querySelectorAll("[data-welcome-close]").forEach(function (button) {
        button.addEventListener("click", close);
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape") close();
    });

    // マイページの「ホーム画面に追加する方法」から、いつでも開ける
    document.querySelectorAll("[data-welcome-open]").forEach(function (button) {
        button.addEventListener("click", function () {
            open("install");
        });
    });

    // どれを出すか決める
    var now = Date.now();
    var firstSeen = parseInt(read(FIRST_SEEN), 10);

    if (!firstSeen) {
        firstSeen = now;
        write(FIRST_SEEN, String(now));
    }

    var mobile = isIOS || isAndroid;
    var step = null;

    if (mobile && !standalone) {

        var stage = parseInt(read(INSTALL_STAGE), 10) || 0;

        if (stage === 0 || (stage === 1 && now - firstSeen >= WEEK)) {
            write(INSTALL_STAGE, String(stage + 1));
            step = "install";
        }

    } else if (!read(NEXT_SHOWN)) {

        // 通知がもう許可されている会員には、通知の案内はいらない
        var pushDone = "Notification" in window && Notification.permission === "granted" && read("washoku_push_on") === "1";
        var next = steps.push ? (pushDone ? null : "push") : "join";

        if (next) {
            write(NEXT_SHOWN, "1");
            step = next;
        }
    }

    if (step) {
        window.setTimeout(function () {
            open(step);
        }, 1200);
    }
})();
