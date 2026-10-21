/* スイスで和食: はじめて開いたときと、その1週間後に1回だけ出す案内。
   ホーム画面に追加する方法 (端末ごと) と、会員登録・通知への入り口。
   いつ出したかは、この端末の localStorage にだけ残す。 */

(function () {
    "use strict";

    var sheet = document.getElementById("washoku-welcome");
    if (!sheet) return;

    var FIRST_SEEN = "washoku_first_seen";
    var STAGE = "washoku_welcome_stage";
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

    // ホーム画面に追加の手順を、端末に合わせて1つだけ見せる
    var install = sheet.querySelector("[data-welcome-install]");
    var installButton = sheet.querySelector("[data-install-button]");
    var deferredPrompt = null;

    if (standalone) {
        install.hidden = true;
    } else if (isIOS) {
        var safari = !/CriOS|FxiOS|EdgiOS/.test(ua);
        sheet.querySelector(safari ? "[data-install-ios-safari]" : "[data-install-ios-browser]").hidden = false;
    } else if (isAndroid) {
        sheet.querySelector("[data-install-android]").hidden = false;
    } else {
        sheet.querySelector("[data-install-desktop]").hidden = false;
    }

    // Android の Chrome などでは、ボタン1つで追加できる
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
            sheet.hidden = false;
        });
    });

    // 出すかどうか: 1回目は初めて開いたとき、2回目は1週間たってから
    var now = Date.now();
    var firstSeen = parseInt(read(FIRST_SEEN), 10);

    if (!firstSeen) {
        firstSeen = now;
        write(FIRST_SEEN, String(now));
    }

    var stage = parseInt(read(STAGE), 10) || 0;
    var due = stage === 0 || (stage === 1 && now - firstSeen >= WEEK);

    // ホーム画面から開いていて、会員でもあるなら、通知の案内だけなので2回目は出さない
    var onlyPush = install.hidden && sheet.querySelector("[data-welcome-push]");

    if (!due || (onlyPush && stage > 0)) return;

    write(STAGE, String(stage + 1));

    window.setTimeout(function () {
        sheet.hidden = false;
    }, 1200);
})();
