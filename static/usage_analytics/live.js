/* =====================================================
   Yapp分析: 「いまの状況」を30秒ごとに読み直す
   (タブが見えているときだけ)
   ===================================================== */

(() => {

    "use strict";

    const box = document.getElementById("ya-live");

    if (!box || !box.dataset.url) {
        return;
    }

    const INTERVAL = 30000;

    async function refresh() {
        if (document.hidden) return;
        try {
            const response = await fetch(box.dataset.url, {
                credentials: "same-origin",
                headers: { "X-Requested-With": "fetch" },
            });
            if (response.ok) {
                box.innerHTML = await response.text();
            }
        } catch (error) {
            // 通信に失敗しても、次の更新でまた試す
        }
    }

    setInterval(refresh, INTERVAL);

    document.addEventListener("visibilitychange", () => {
        if (!document.hidden) refresh();
    });

})();
