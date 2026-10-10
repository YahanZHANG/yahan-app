"use strict";


document.addEventListener("DOMContentLoaded", () => {

    // =====================================================
    // Scroll to top
    // =====================================================

    const scrollTopButton = document.getElementById(
        "sb-scroll-top"
    );

    const updateScrollButton = () => {

        if (!scrollTopButton) {
            return;
        }

        scrollTopButton.hidden = (
            window.scrollY <= 400
        );
    };


    if (scrollTopButton) {

        window.addEventListener(
            "scroll",
            updateScrollButton,
            { passive: true }
        );

        updateScrollButton();


        scrollTopButton.addEventListener("click", () => {

            const reducedMotion = window.matchMedia(
                "(prefers-reduced-motion: reduce)"
            ).matches;

            window.scrollTo({
                top: 0,
                behavior: reducedMotion ? "instant" : "smooth",
            });

        });

    }


    // =====================================================
    // Preview notification
    // =====================================================

    const previewMessage = document.getElementById(
        "sb-preview-message"
    );

    let messageTimeout = null;


    const previewLabels = {
        search: "検索画面は次の工程で実装します。",
        menu: "カテゴリー一覧は次の工程で実装します。",
        post: "投稿フォームは準備中です。",
        mypage: "マイページは準備中です。",
        region: "地域の絞り込みは準備中です。",
        sort: "並び替えは準備中です。",
        category: "カテゴリー別一覧は準備中です。",
        topic: "トピック検索は準備中です。",
        detail: "投稿詳細画面は準備中です。",
        recipes: "レシピアプリの一般公開後に接続します。",
    };


    document.querySelectorAll("[data-preview]").forEach(
        (button) => {

            button.addEventListener("click", () => {

                if (!previewMessage) {
                    return;
                }

                const key = button.dataset.preview;

                const label = (
                    previewLabels[key]
                    || "この機能は準備中です。"
                );

                const name = (
                    button.dataset.previewName || ""
                );

                previewMessage.textContent = (
                    name
                        ? `${name}：${label}`
                        : label
                );

                previewMessage.hidden = false;

                if (messageTimeout) {
                    clearTimeout(messageTimeout);
                }

                messageTimeout = setTimeout(() => {
                    previewMessage.hidden = true;
                }, 3000);

            });

        }
    );

});