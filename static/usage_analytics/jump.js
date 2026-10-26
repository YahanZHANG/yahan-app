/* =====================================================
   Yapp分析: 右下の ↑ / 🚶 / ↓ ボタン
   (上の方では ↑ を、下の方では ↓ を隠す)
   ===================================================== */

(() => {

    "use strict";

    const buttons = document.querySelectorAll("[data-ya-scroll]");

    if (!buttons.length) {
        return;
    }

    const byName = {};
    buttons.forEach((button) => {
        byName[button.dataset.yaScroll] = button;
    });

    function go(event) {
        const where = event.currentTarget.dataset.yaScroll;

        if (where === "top") {
            event.preventDefault();
            window.scrollTo({ top: 0, behavior: "smooth" });
        } else if (where === "bottom") {
            event.preventDefault();
            window.scrollTo({ top: document.documentElement.scrollHeight, behavior: "smooth" });
        }
        // "visits" は普通のページ内リンクのまま (scroll-margin-top が効く)
    }

    function update() {
        const y = window.scrollY;
        const bottom = document.documentElement.scrollHeight - window.innerHeight;

        byName.top?.classList.toggle("is-hidden", y < 300);
        byName.bottom?.classList.toggle("is-hidden", y > bottom - 300);
    }

    buttons.forEach((button) => button.addEventListener("click", go));
    window.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update);
    update();

})();
