// 上にタブ (サブページのボタン) があるページでは、HOMEと同じように左右にスワイプしても隣のページへ移れる
// スマホは指で、パソコンはトラックパッドの2本指の横スワイプで
(function () {
    var tabs = document.querySelector(".washoku-subtabs");
    var main = document.querySelector(".washoku-main");
    if (!tabs || !main) return;

    var links = Array.prototype.slice.call(tabs.querySelectorAll("a[href]"));
    var current = links.findIndex(function (link) { return link.classList.contains("active"); });
    if (current === -1) return;

    var THRESHOLD = 70;   // これ以上横に動かしたらページを変える (px)
    var EDGE = 24;        // 画面の端から始めたスワイプは、ブラウザの「戻る」に任せる
    var start = null;
    var horizontal = null;
    var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    // 入力欄や、横にスクロールできる場所 (表・スライドなど) から始めたスワイプは使わない
    function ignored(target) {
        for (var node = target; node && node !== document.body; node = node.parentElement) {
            if (/^(INPUT|TEXTAREA|SELECT|BUTTON)$/.test(node.tagName) || node.isContentEditable) return true;
            if (node.hasAttribute && node.hasAttribute("data-no-swipe")) return true;
            if (node.scrollWidth > node.clientWidth + 2) {
                var overflow = getComputedStyle(node).overflowX;
                if (overflow === "auto" || overflow === "scroll") return true;
            }
        }
        return false;
    }

    function neighbour(dx) {
        return dx < 0 ? links[current + 1] : links[current - 1];
    }

    function reset() {
        main.style.transition = reduced ? "" : "transform .2s ease, opacity .2s ease";
        main.style.transform = "";
        main.style.opacity = "";
    }

    document.addEventListener("touchstart", function (event) {
        var touch = event.touches[0];
        start = null;
        horizontal = null;
        if (event.touches.length !== 1) return;
        if (touch.clientX < EDGE || touch.clientX > window.innerWidth - EDGE) return;
        if (ignored(event.target)) return;
        if (document.documentElement.classList.contains("washoku-say-open")) return;
        start = { x: touch.clientX, y: touch.clientY };
    }, { passive: true });

    document.addEventListener("touchmove", function (event) {
        if (!start) return;
        var touch = event.touches[0];
        var dx = touch.clientX - start.x;
        var dy = touch.clientY - start.y;

        if (horizontal === null && (Math.abs(dx) > 10 || Math.abs(dy) > 10)) {
            horizontal = Math.abs(dx) > Math.abs(dy) * 1.5;
        }
        if (!horizontal || reduced) return;

        // 隣のページがない方向には、少しだけ動かす
        var pull = neighbour(dx) ? dx * 0.5 : dx * 0.15;
        main.style.transition = "none";
        main.style.transform = "translateX(" + pull + "px)";
        main.style.opacity = String(1 - Math.min(Math.abs(pull) / 600, 0.3));
    }, { passive: true });

    document.addEventListener("touchend", function (event) {
        if (!start) return;
        var touch = event.changedTouches[0];
        var dx = touch.clientX - start.x;
        var dy = touch.clientY - start.y;
        var next = neighbour(dx);
        var move = horizontal && next && Math.abs(dx) > THRESHOLD && Math.abs(dx) > Math.abs(dy) * 1.5;
        start = null;

        if (!move) {
            reset();
            return;
        }

        go(next, dx);
    });

    function go(next, dx) {
        tabs.querySelectorAll("a").forEach(function (link) { link.classList.toggle("active", link === next); });

        if (!reduced) {
            main.style.transition = "transform .18s ease-in, opacity .18s ease-in";
            main.style.transform = "translateX(" + (dx < 0 ? -40 : 40) + "%)";
            main.style.opacity = "0";
        }
        window.location.href = next.href;
    }

    // トラックパッドの横スワイプ (パソコン)。一定以上たまったら1回だけ移る
    var wheelX = 0;
    var wheelTimer = null;
    var leaving = false;

    // このページでは、横スワイプをブラウザの「戻る・進む」ではなくタブの切り替えに使う
    document.documentElement.classList.add("washoku-swipe-tabs");

    document.addEventListener("wheel", function (event) {
        if (leaving || Math.abs(event.deltaX) <= Math.abs(event.deltaY) || ignored(event.target)) return;
        wheelX += event.deltaX;
        clearTimeout(wheelTimer);
        wheelTimer = setTimeout(function () { wheelX = 0; reset(); }, 250);

        var next = neighbour(-wheelX);
        if (!reduced) {
            var pull = next ? -wheelX * 0.4 : -wheelX * 0.1;
            main.style.transition = "none";
            main.style.transform = "translateX(" + Math.max(-80, Math.min(80, pull)) + "px)";
        }
        if (next && Math.abs(wheelX) > 150) {
            leaving = true;
            go(next, -wheelX);
        }
    }, { passive: true });

    document.addEventListener("touchcancel", function () {
        start = null;
        reset();
    });

    // 戻るボタンでこのページに戻ったとき、ずらしたままにしない
    window.addEventListener("pageshow", function () {
        leaving = false;
        wheelX = 0;
        main.style.transition = "";
        main.style.transform = "";
        main.style.opacity = "";
        tabs.querySelectorAll("a").forEach(function (link, i) { link.classList.toggle("active", i === current); });
    });
})();
