/* ==========================================
   Swiss News - Push ON/OFF (設定画面)
========================================== */

(() => {
    "use strict";

    const push = window.SwissNewsPush;

    const button = document.getElementById(
        "news-push-toggle"
    );

    if (!push || !button) {
        return;
    }

    const state = document.getElementById(
        "news-push-toggle-state"
    );

    const status = document.getElementById(
        "news-push-status"
    );


    function updateUI(isOn) {
        button.classList.toggle(
            "is-on",
            isOn
        );

        button.setAttribute(
            "aria-pressed",
            String(isOn)
        );

        state.textContent = isOn
            ? "ON"
            : "OFF";

        status.textContent = isOn
            ? "この端末では通知がONになっているよ。"
            : "この端末では通知がOFFになっているよ。";

        button.disabled = false;
    }


    function disable(message) {
        button.disabled = true;
        state.textContent = "—";
        status.textContent = message;
    }


    async function refresh() {
        const subscription =
            await push.getSubscription();

        updateUI(Boolean(subscription));

        if (push.permission() === "denied") {
            status.textContent =
                "ブラウザ側で通知がブロックされているよ。"
                + " 端末の通知設定を確認してね。";
        }
    }


    button.addEventListener(
        "click",
        async () => {

            button.disabled = true;

            status.textContent =
                "通知設定を変更中...";

            try {
                const current =
                    await push.getSubscription();

                if (current) {
                    await push.unsubscribe();
                    push.saveChoice("declined");
                    updateUI(false);
                    return;
                }

                const result = await push.subscribe();

                if (result !== "subscribed") {
                    updateUI(false);

                    status.textContent =
                        "通知が許可されていないよ。"
                        + " ブラウザや端末の設定を確認してね。";

                    return;
                }

                push.saveChoice("accepted");
                updateUI(true);

            } catch (error) {
                console.error(
                    "News Push toggle failed:",
                    error
                );

                try {
                    await refresh();
                } catch (refreshError) {
                    console.warn(
                        "Push refresh failed:",
                        refreshError
                    );
                }

                status.textContent =
                    "通知設定を変更できなかったよ。"
                    + " もう一度試してね。";

            } finally {
                button.disabled = false;
            }

        }
    );


    async function initialize() {
        if (!push.isSupported()) {
            disable(
                "この環境ではPush通知を利用できないよ。"
                + " iPhoneの場合はSafariの共有メニューから"
                + "「ホーム画面に追加」して開いてね。"
            );

            return;
        }

        if (!push.isConfigured()) {
            disable(
                "Push通知のサーバー設定が未完了だよ。"
            );

            return;
        }

        try {
            await refresh();
        } catch (error) {
            console.error(
                "Push initialization failed:",
                error
            );

            disable(
                "通知の状態を確認できなかったよ。"
            );
        }
    }

    initialize();

})();
