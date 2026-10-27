/* ==========================================
   Swiss News - 要約の閲覧を記録 (解析用)
   カードの6割以上が3秒以上映ったら「読んだ」。
   何件も同時に映るとき (PC) は、その件数で割った重みにする。
   マウスが乗っているカードは、そのカードだけを読んでいるとみなす。
========================================== */

(() => {
    "use strict";

    const config = document.getElementById("news-read-config");
    const cards = document.querySelectorAll(".news-card[data-article-id]");

    if (!config || !cards.length || !("IntersectionObserver" in window)) {
        return;
    }

    const READ_SECONDS = 3;
    const TICK_MS = 500;
    const url = config.dataset.url;

    const visible = new Set();
    const stats = new Map();   // card -> {seconds, weighted}
    const reported = new Set();
    let queue = [];
    let hovered = null;

    const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
            // 画面より長いカードは、画面の6割以上を占めていれば映っているとみなす
            const screen = entry.rootBounds ? entry.rootBounds.height : window.innerHeight;
            if (entry.intersectionRatio >= 0.6 || entry.intersectionRect.height >= screen * 0.6) {
                visible.add(entry.target);
            } else {
                visible.delete(entry.target);
            }
        });
    }, { threshold: [0, 0.2, 0.4, 0.6, 0.8, 1] });

    cards.forEach((card) => {
        observer.observe(card);
        card.addEventListener("mouseenter", () => { hovered = card; });
        card.addEventListener("mouseleave", () => {
            if (hovered === card) hovered = null;
        });
    });

    function tick() {
        if (document.visibilityState !== "visible" || !visible.size) return;

        const seconds = TICK_MS / 1000;
        const focus = hovered && visible.has(hovered) ? hovered : null;

        visible.forEach((card) => {
            if (reported.has(card)) return;

            const share = focus ? (card === focus ? 1 : 0) : 1 / visible.size;
            const row = stats.get(card) || { seconds: 0, weighted: 0 };

            row.seconds += seconds;
            row.weighted += seconds * share;
            stats.set(card, row);

            // 重み付きの時間が0のまま (ほかのカードにマウスがある) なら数えない
            if (row.seconds >= READ_SECONDS && row.weighted > 0) {
                reported.add(card);
                queue.push({
                    id: card.dataset.articleId,
                    w: Math.round((row.weighted / row.seconds) * 100) / 100,
                });
            }
        });
    }

    function flush() {
        if (!queue.length) return;

        const body = JSON.stringify({ reads: queue });
        queue = [];

        try {
            if (navigator.sendBeacon) {
                navigator.sendBeacon(url, new Blob([body], { type: "application/json" }));
            } else {
                fetch(url, { method: "POST", body, credentials: "same-origin", keepalive: true })
                    .catch(() => {});
            }
        } catch (error) {}
    }

    setInterval(tick, TICK_MS);
    setInterval(flush, 10000);

    document.addEventListener("visibilitychange", () => {
        if (document.visibilityState === "hidden") flush();
    });
    window.addEventListener("pagehide", flush);
})();
