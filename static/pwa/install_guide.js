/* ホーム画面に追加する方法: 端末に合ったタブを開き、Android ではボタン1つで追加できるようにする */
(function () {
    "use strict";

    var guide = document.querySelector("[data-install-guide]");
    if (!guide) return;

    var ua = navigator.userAgent;
    var isIOS = /iPhone|iPad|iPod/.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
    var isAndroid = /Android/.test(ua);
    var standalone = window.matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;

    if (standalone) {
        guide.querySelector("[data-install-standalone]").hidden = false;
    }

    // LINE・Instagram などのアプリ内ブラウザでは追加できない
    if (/Line\/|FBAN|FBAV|FB_IAB|Instagram|MicroMessenger|TikTok|BytedanceWebview|; wv\)/.test(ua)) {
        guide.querySelector("[data-install-inapp]").hidden = false;
    }

    var tabs = guide.querySelectorAll("[data-install-tab]");
    var panels = guide.querySelectorAll("[data-install-panel]");

    function show(name) {
        tabs.forEach(function (tab) {
            var on = tab.dataset.installTab === name;
            tab.classList.toggle("is-active", on);
            tab.setAttribute("aria-selected", on ? "true" : "false");
        });
        panels.forEach(function (panel) {
            panel.hidden = panel.dataset.installPanel !== name;
        });
    }

    tabs.forEach(function (tab) {
        tab.addEventListener("click", function () {
            show(tab.dataset.installTab);
        });
    });

    var first = "pc";
    if (isIOS) first = /CriOS|FxiOS|EdgiOS/.test(ua) ? "ios-chrome" : "ios-safari";
    else if (isAndroid) first = "android";
    show(first);

    // Android の Chrome などでは、ボタン1つで追加できる
    var onetap = guide.querySelector("[data-install-onetap]");
    var deferredPrompt = null;

    window.addEventListener("beforeinstallprompt", function (event) {
        event.preventDefault();
        deferredPrompt = event;
        onetap.hidden = false;
    });

    guide.querySelector("[data-install-button]").addEventListener("click", function () {
        if (!deferredPrompt) return;
        deferredPrompt.prompt();
        deferredPrompt.userChoice.finally(function () {
            deferredPrompt = null;
            onetap.hidden = true;
        });
    });
})();
