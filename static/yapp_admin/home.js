/* =====================================================
   Yapp Admin のトップ
   - 開いた / 閉じたアプリを覚えておく (このブラウザだけ)
   - 「さがす」で、名前が合うものだけを出す
   ===================================================== */

(() => {

    "use strict";

    const root = document.querySelector(".yh");

    if (!root) {
        return;
    }

    const PREFIX = "yapp-admin-open:";
    const folds = Array.from(root.querySelectorAll("details[data-yh-key]"));

    function load(key) {
        try {
            return localStorage.getItem(PREFIX + key);
        } catch (error) {
            return null;
        }
    }

    function save(key, value) {
        try {
            localStorage.setItem(PREFIX + key, value);
        } catch (error) {
            // 保存できなくても困らない
        }
    }

    // ---------- 開閉を覚える ----------

    let filtering = false;

    folds.forEach((fold) => {
        const saved = load(fold.dataset.yhKey);
        if (saved === "1") fold.open = true;
        if (saved === "0") fold.open = false;

        fold.addEventListener("toggle", () => {
            if (!filtering) save(fold.dataset.yhKey, fold.open ? "1" : "0");
        });
    });

    // ---------- さがす ----------

    const input = document.getElementById("yh-filter");
    const noHit = document.getElementById("yh-no-hit");
    const remembered = new Map();

    if (!input) {
        return;
    }

    function filter() {
        const words = input.value.trim().toLowerCase().split(/\s+/).filter(Boolean);
        const active = words.length > 0;

        // さがし始めたら今の開閉を覚え、やめたら元に戻す
        if (active && !filtering) {
            folds.forEach((fold) => remembered.set(fold, fold.open));
        }
        filtering = true;

        let hits = 0;

        root.querySelectorAll(".yh-model").forEach((row) => {
            const text = (row.dataset.yhName + " " + row.textContent).toLowerCase();
            const match = !active || words.every((word) => text.includes(word));
            row.classList.toggle("is-filtered-out", !match);
            if (match) hits += 1;
        });

        root.querySelectorAll(".yh-group, .yh-app, .yh-rare").forEach((box) => {
            const visible = !active || box.querySelector(".yh-model:not(.is-filtered-out)");
            box.classList.toggle("is-filtered-out", !visible);
            if (active && visible) box.open = true;
        });

        root.querySelectorAll(".yh-heading").forEach((heading) => {
            const next = heading.nextElementSibling;
            heading.classList.toggle("is-filtered-out", active && !(next && next.querySelector(".yh-model:not(.is-filtered-out)")));
        });

        if (noHit) noHit.hidden = !active || hits > 0;

        if (!active) {
            remembered.forEach((open, fold) => {
                fold.open = open;
            });
            remembered.clear();
        }

        // toggle イベントは後から届くので、少し待ってから保存を再開する
        setTimeout(() => {
            filtering = active;
        }, 0);
    }

    input.addEventListener("input", filter);

    // Enter で、いちばん上に見つかったものを開く
    input.addEventListener("keydown", (event) => {
        if (event.key !== "Enter") return;
        const first = root.querySelector(".yh-model:not(.is-filtered-out) a.yh-model-link");
        if (first && input.value.trim()) {
            event.preventDefault();
            window.location.href = first.href;
        }
    });

})();
