/* ==========================================
   Swiss News - 「通知いりますか？」の確認
========================================== */

(() => {
    "use strict";

    const push = window.SwissNewsPush;

    const prompt = document.getElementById(
        "news-push-prompt"
    );

    if (!push || !prompt) {
        return;
    }

    const acceptButton = prompt.querySelector(
        "[data-push-accept]"
    );

    const declineButton = prompt.querySelector(
        "[data-push-decline]"
    );

    const laterButton = prompt.querySelector(
        "[data-push-later]"
    );

    const message = prompt.querySelector(
        "[data-push-message]"
    );

    // 「あとで」を選んだら、この日数は聞かない
    const LATER_DAYS = 7;

    const SHOW_DELAY_MS = 3000;


    function shouldAsk() {
        const choice = push.readChoice();

        if (choice && choice.value === "declined") {
            return false;
        }

        if (choice && choice.value === "accepted") {
            return false;
        }

        if (
            choice
            && choice.value === "later"
            && Date.now() - choice.at
                < LATER_DAYS * 24 * 60 * 60 * 1000
        ) {
            return false;
        }

        return true;
    }


    function show() {
        prompt.hidden = false;

        requestAnimationFrame(() => {
            prompt.classList.add("is-visible");
        });
    }


    function hide() {
        prompt.classList.remove("is-visible");

        setTimeout(() => {
            prompt.hidden = true;
        }, 250);
    }


    acceptButton.addEventListener(
        "click",
        async () => {

            acceptButton.disabled = true;
            declineButton.disabled = true;

            try {
                const result = await push.subscribe();

                if (result === "subscribed") {
                    push.saveChoice("accepted");

                    message.textContent =
                        "通知をONにしたよ。設定からいつでもOFFにできるよ。";

                } else {
                    push.saveChoice("declined");

                    message.textContent =
                        "通知が許可されなかったよ。"
                        + "あとから設定画面でONにできるよ。";
                }

            } catch (error) {
                console.error(
                    "News Push subscribe failed:",
                    error
                );

                push.saveChoice("later");

                message.textContent =
                    "うまく設定できなかったよ。"
                    + "設定画面からもう一度試してね。";
            }

            setTimeout(hide, 2500);
        }
    );


    declineButton.addEventListener(
        "click",
        () => {
            push.saveChoice("declined");
            hide();
        }
    );


    laterButton.addEventListener(
        "click",
        () => {
            push.saveChoice("later");
            hide();
        }
    );


    async function initialize() {
        if (
            !push.isSupported()
            || !push.isConfigured()
            || push.permission() !== "default"
            || !shouldAsk()
        ) {
            return;
        }

        try {
            if (await push.getSubscription()) {
                return;
            }
        } catch (error) {
            return;
        }

        setTimeout(show, SHOW_DELAY_MS);
    }

    initialize();

})();
