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
    const regionBox = document.getElementById("news-push-regions");

    const regionInputs = Array.from(
        regionBox.querySelectorAll("input[type=checkbox]")
    );
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
            regionInputs.forEach((input) => {
                input.checked = options.alert_regions.includes(input.value);
            });
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

    regionBox.addEventListener("change", () => {
        save({
            alert_regions: regionInputs
                .filter((input) => input.checked)
                .map((input) => input.value),
        });
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
