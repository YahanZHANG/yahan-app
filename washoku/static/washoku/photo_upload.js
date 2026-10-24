// 写真を送る前に、端末の中で小さな JPEG にする (最大 1600px)。
// 大きすぎる写真や iPhone の HEIC でも送れるようにするため。
// 小さくできなかったときは、元の写真をそのまま送る。
(function () {
    var MAX_SIZE = 1600;
    var QUALITY = 0.85;

    if (!window.DataTransfer || !window.HTMLCanvasElement) return;

    function loadImage(file) {
        return new Promise(function (resolve, reject) {
            var url = URL.createObjectURL(file);
            var image = new Image();
            image.onload = function () { resolve({ image: image, url: url }); };
            image.onerror = function () { URL.revokeObjectURL(url); reject(new Error("unreadable")); };
            image.src = url;
        });
    }

    function shrink(file) {
        return loadImage(file).then(function (loaded) {
            var image = loaded.image;
            var scale = Math.min(1, MAX_SIZE / Math.max(image.naturalWidth, image.naturalHeight));
            var canvas = document.createElement("canvas");
            canvas.width = Math.round(image.naturalWidth * scale);
            canvas.height = Math.round(image.naturalHeight * scale);
            canvas.getContext("2d").drawImage(image, 0, 0, canvas.width, canvas.height);
            URL.revokeObjectURL(loaded.url);
            return new Promise(function (resolve, reject) {
                canvas.toBlob(function (blob) {
                    if (!blob) return reject(new Error("no blob"));
                    var name = (file.name || "photo").replace(/\.[^.]+$/, "") + ".jpg";
                    resolve(new File([blob], name, { type: "image/jpeg" }));
                }, "image/jpeg", QUALITY);
            });
        });
    }

    function setBusy(form, busy) {
        form.dataset.photoBusy = busy ? "1" : "";
        form.querySelectorAll("button[type=submit], button:not([type])").forEach(function (button) {
            button.disabled = busy;
        });
    }

    document.addEventListener("change", function (event) {
        var input = event.target;
        if (!input.matches || !input.matches('input[type="file"][accept^="image"]')) return;
        var file = input.files && input.files[0];
        var form = input.form;
        if (!file || !form || input.dataset.shrunk === file.name) return;

        setBusy(form, true);

        shrink(file).then(function (small) {
            // 元のほうが小さければ、元のまま送る
            if (small.size < file.size || !/^image\/(jpeg|png|webp)$/.test(file.type)) {
                var transfer = new DataTransfer();
                transfer.items.add(small);
                input.files = transfer.files;
                input.dataset.shrunk = small.name;
            }
        }).catch(function () {
            // 小さくできなかったときは元の写真のまま
        }).then(function () {
            setBusy(form, false);
            if (input.hasAttribute("data-autosubmit")) form.submit();
        });
    });

    // 小さくしている途中で送らない
    document.addEventListener("submit", function (event) {
        if (event.target.dataset && event.target.dataset.photoBusy) event.preventDefault();
    }, true);
})();
