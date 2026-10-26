/* ==========================================
   Swiss News - 記事のシェア
   スマホはOSの共有メニュー、PCは LINE / Facebook / コピー
========================================== */

(() => {
    "use strict";

    function lineUrl(url, title) {
        return "https://line.me/R/share?text="
            + encodeURIComponent(title + "\n" + url);
    }

    function facebookUrl(url) {
        return "https://www.facebook.com/sharer/sharer.php?u="
            + encodeURIComponent(url);
    }

    async function copy(url, button) {
        try {
            await navigator.clipboard.writeText(url);
        } catch (error) {
            window.prompt("このリンクをコピーしてください", url);
            return;
        }

        const label = button.textContent;
        button.textContent = "コピーしました";

        setTimeout(() => {
            button.textContent = label;
        }, 1800);
    }

    function buildMenu(url, title) {
        const menu = document.createElement("div");
        menu.className = "news-share-menu";

        menu.innerHTML = `
            <a class="news-share-line" target="_blank" rel="noopener noreferrer">LINE</a>
            <a class="news-share-facebook" target="_blank" rel="noopener noreferrer">Facebook</a>
            <button type="button" class="news-share-copy">リンクをコピー</button>
        `;

        menu.querySelector(".news-share-line").href = lineUrl(url, title);
        menu.querySelector(".news-share-facebook").href = facebookUrl(url);

        const copyButton = menu.querySelector(".news-share-copy");

        copyButton.addEventListener("click", () => copy(url, copyButton));

        return menu;
    }

    // 記事ページの LINE / Facebook / コピー ボタン
    document.querySelectorAll("[data-share-links]").forEach((box) => {
        box.replaceWith(
            buildMenu(box.dataset.shareUrl, box.dataset.shareTitle)
        );
    });

    document.addEventListener("click", async (event) => {
        const button = event.target.closest
            && event.target.closest(".news-share-button");

        if (!button) {
            return;
        }

        const url = button.dataset.shareUrl;
        const title = button.dataset.shareTitle || "Swiss News";

        // スマホ: OSの共有メニュー（LINE・Facebook・メッセージなど）
        if (navigator.share && window.matchMedia("(pointer: coarse)").matches) {
            try {
                await navigator.share({ title: title, url: url });
            } catch (error) {
                // 閉じただけ
            }
            return;
        }

        const next = button.nextElementSibling;

        if (next && next.classList.contains("news-share-menu")) {
            next.remove();
            return;
        }

        button.after(buildMenu(url, title));
    });
})();
