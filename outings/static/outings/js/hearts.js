// Heart (favourite) buttons on every Outings page.
// A form with data-heart-key is sent in the background; the server's answer
// decides the state, and every button for the same item is updated.
(function () {
    "use strict";

    function setState(key, hearted, count) {
        document.querySelectorAll('form[data-heart-key="' + key + '"]').forEach(function (form) {
            var button = form.querySelector("button");
            var icon = button && button.querySelector("i");
            if (!button) return;
            button.classList.toggle("is-hearted", hearted);
            button.classList.toggle("hearted", hearted);
            button.setAttribute("aria-pressed", String(hearted));
            if (icon) {
                icon.classList.toggle("bi-heart-fill", hearted);
                icon.classList.toggle("bi-heart", !hearted);
            }
            var counter = form.querySelector("[data-heart-count]");
            if (counter && typeof count === "number") counter.textContent = count;
        });
    }

    document.addEventListener("submit", function (event) {
        var form = event.target.closest("form[data-heart-key]");
        if (!form) return;
        event.preventDefault();
        var button = form.querySelector("button");
        if (button && button.disabled) return;
        if (button) button.disabled = true;
        fetch(form.action, {
            method: "POST",
            credentials: "same-origin",
            headers: { "X-Requested-With": "XMLHttpRequest" },
            body: new FormData(form),
        })
            .then(function (response) {
                if (!response.ok) throw new Error("HTTP " + response.status);
                return response.json();
            })
            .then(function (data) {
                setState(form.dataset.heartKey, Boolean(data.hearted), data.count);
            })
            .catch(function () {
                // Fall back to a normal form post.
                form.submit();
            })
            .finally(function () {
                if (button) button.disabled = false;
            });
    });
})();
