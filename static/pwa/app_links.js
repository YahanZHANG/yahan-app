/*
 * Yapp のアプリ間リンクと、LINE・Instagram などのアプリ内ブラウザの案内。
 * templates/includes/app_icons.html から全アプリで読み込む。
 *
 * 1) ほかの Yapp アプリ (ヘルプ・サポートのページも含む) へのリンクは、
 *    今の画面ではなく新しいタブ (target=_blank) で開く。ブラウザでも、
 *    ホーム画面のアプリでも同じ (2026-11-09 Taro)。
 *    ホーム画面のアプリから: iPhone は Safari、Android は Chrome で開く
 *    (端末の設定で追加済みのアプリが開くこともある)。PC の Chrome / Edge は
 *    「対応リンクを開く」がオンなら追加済みのアプリ、オフならブラウザのタブ。
 *    ※ ホーム画面の別のアプリを、リンクから必ず開く方法はどの端末にもない。
 *    同じアプリの中のリンク、ログインなどのページへのリンクは今の画面のまま。
 *    ヘルプ・サポートのページの中のリンクも今の画面のまま (すでに新しいタブなので)。
 * 2) LINE・Instagram などのアプリの中で開いたとき、下に細い案内を出し、
 *    ボタンで Safari / Chrome に移れるようにする。
 *
 * アプリとして扱う URL の先頭は config/pwa.py の APP_PATHS
 * (この script タグの data-apps)。リンクごとに止めたいときは data-same-app を付ける。
 */
(function () {
    "use strict";

    var html = document.documentElement;
    var script = document.currentScript;
    var apps = ((script && script.getAttribute("data-apps")) || "").split(",");
    var ua = navigator.userAgent;

    var standalone = window.matchMedia("(display-mode: standalone)").matches
        || navigator.standalone === true;

    // 新しいタブで開く行き先: 各アプリと、ヘルプ・サポートのページ
    var newTabKeys = apps.concat(["help", "support"]);

    // 「/news/123/」→「news」、「/」→「」
    function keyOf(path) {
        return (path || "/").replace(/^\/+/, "").split("/")[0];
    }

    function storageGet(store, key) {
        try { return window[store].getItem(key); } catch (error) { return null; }
    }

    function storageSet(store, key, value) {
        try { window[store].setItem(key, value); } catch (error) {}
    }

    // ---------------------------------------------------------
    // 1) ほかのアプリへのリンクは新しいタブで
    // ---------------------------------------------------------

    var current = keyOf(location.pathname);

    if (apps.indexOf(current) !== -1) {
        document.addEventListener("click", function (event) {
            if (event.defaultPrevented || event.button !== 0) return;
            if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;

            var link = event.target.closest && event.target.closest("a[href]");
            if (!link || link.hasAttribute("download") || link.hasAttribute("data-same-app")) return;
            if (link.target && link.target !== "_self") return;

            var url;
            try { url = new URL(link.href, location.href); } catch (error) { return; }
            if (url.origin !== location.origin) return;

            var target = keyOf(url.pathname);
            if (target === current || newTabKeys.indexOf(target) === -1) return;

            // 既定の動き (リンクを開く) はそのままに、開く先だけ新しいタブにする
            link.target = "_blank";
            link.rel = ((link.rel || "") + " noopener").trim();
        }, true);
    }

    if (standalone) return;

    // ---------------------------------------------------------
    // 2) LINE・Instagram などのアプリ内ブラウザ
    // ---------------------------------------------------------

    var IN_APPS = [
        [/Line\//, "LINE"],
        [/Instagram/, "Instagram"],
        [/FBAN\/Messenger|FB_IAB\/MESSENGER/, "Messenger"],
        [/FBAN|FBAV|FB_IAB/, "Facebook"],
        [/MicroMessenger/, "WeChat"],
        [/TikTok|BytedanceWebview|musical_ly/, "TikTok"],
        [/Twitter/, "X"],
        [/; wv\)/, ""],
    ];

    var inAppName = null;
    for (var i = 0; i < IN_APPS.length; i++) {
        if (IN_APPS[i][0].test(ua)) { inAppName = IN_APPS[i][1]; break; }
    }
    if (inAppName === null) return;

    html.classList.add("yapp-inapp");

    var CLOSED_KEY = "yapp_inapp_bar_closed";
    var closedAt = parseInt(storageGet("localStorage", CLOSED_KEY), 10) || 0;
    if (storageGet("sessionStorage", CLOSED_KEY) || Date.now() - closedAt < 24 * 60 * 60 * 1000) return;

    var android = /Android/.test(ua);
    var ios = /iPhone|iPad|iPod/.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);

    function externalUrl() {
        var here = new URL(location.href);
        if (inAppName === "LINE") {
            // LINE はこの印が付いた URL を Safari / Chrome で開く
            here.searchParams.set("openExternalBrowser", "1");
            return here.href;
        }
        if (android) {
            return "intent://" + here.host + here.pathname + here.search + here.hash
                + "#Intent;scheme=https;package=com.android.chrome;S.browser_fallback_url="
                + encodeURIComponent(here.href) + ";end";
        }
        if (ios) {
            // iOS 17 以降の Safari で開く。アプリによっては開かない
            return "x-safari-" + here.href;
        }
        return null;
    }

    var place = inAppName ? inAppName + "の中" : "アプリの中";
    var hint = ios
        ? "開かないときは、画面の「…」や共有ボタンから「Safari で開く」を選んでください。"
        : "開かないときは、画面の「…」から「ブラウザで開く」を選んでください。";

    function build() {
        var bar = document.createElement("div");
        bar.className = "yapp-inapp-bar";
        bar.setAttribute("role", "region");
        bar.setAttribute("aria-label", "ブラウザで開く案内");
        bar.innerHTML =
            '<div class="yapp-inapp-bar-body">'
            + '<p class="yapp-inapp-bar-title"></p>'
            + '<p class="yapp-inapp-bar-text">ホーム画面に追加済みならそちらから、まだならブラウザで開くのがおすすめです。</p>'
            + '<p class="yapp-inapp-bar-hint" hidden></p>'
            + '<a class="yapp-inapp-bar-open" href="#">ブラウザで開く</a>'
            + '</div>'
            + '<button type="button" class="yapp-inapp-bar-close" aria-label="閉じる">×</button>';
        bar.querySelector(".yapp-inapp-bar-title").textContent = place + "で開いています";
        var hintEl = bar.querySelector(".yapp-inapp-bar-hint");
        hintEl.textContent = hint;

        var open = bar.querySelector(".yapp-inapp-bar-open");
        var target = externalUrl();
        if (target) {
            open.href = target;
        } else {
            open.hidden = true;
            hintEl.hidden = false;
        }
        open.addEventListener("click", function () {
            // 開けなかったとき (まだこの画面にいるとき) は手順を見せる
            setTimeout(function () {
                if (document.visibilityState === "visible") hintEl.hidden = false;
            }, 1500);
        });

        bar.querySelector(".yapp-inapp-bar-close").addEventListener("click", function () {
            bar.remove();
            storageSet("sessionStorage", CLOSED_KEY, "1");
            storageSet("localStorage", CLOSED_KEY, String(Date.now()));
        });

        // ページのいちばん上に入れる (下のタブバーと重ならないように)
        document.body.insertBefore(bar, document.body.firstChild);
    }

    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", build);
    else build();
})();
