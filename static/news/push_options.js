/* ==========================================
   Swiss News - 通知の頻度・暮らしのお知らせの地域 (設定画面)
   この端末の通知がONのときだけ表示する
========================================== */

(() => {
    "use strict";

    const push = window.SwissNewsPush;

    const box = document.getElementById("news-push-options");

    const config = document.getElementById("news-push-config");

    if (!push || !box || !config) {
        return;
    }

    const frequency = document.getElementById("news-push-frequency");
    const region = document.getElementById("news-push-region");
    const status = document.getElementById("news-push-options-status");

    let endpoint = null;


    async function send(data) {
        const response = await fetch(config.dataset.optionsUrl, {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": config.dataset.csrfToken,
            },
            body: JSON.stringify(
                Object.assign({ endpoint: endpoint }, data)
            ),
        });

        if (!response.ok) {
            throw new Error(`Push options failed: ${response.status}`);
        }

        return response.json();
    }


    async function load() {
        const subscription = await push.getSubscription();

        if (!subscription) {
            box.hidden = true;
            return;
        }

        endpoint = subscription.endpoint;

        try {
            const options = await send({});

            frequency.value = options.frequency;
            region.value = options.alert_region;
            box.hidden = false;
        } catch (error) {
            console.warn(error);
            box.hidden = true;
        }
    }


    async function save(data) {
        status.textContent = "保存中...";

        try {
            await send(data);
            status.textContent = "保存しました。";
        } catch (error) {
            console.error(error);
            status.textContent = "保存できませんでした。もう一度お試しください。";
        }
    }


    frequency.addEventListener("change", () => {
        save({ frequency: frequency.value });
    });

    region.addEventListener("change", () => {
        save({ alert_region: region.value });
    });

    document.addEventListener("swissnews:push-changed", (event) => {
        if (event.detail.isOn) {
            load();
        } else {
            box.hidden = true;
        }
    });

    if (push.isSupported()) {
        load();
    }
})();
