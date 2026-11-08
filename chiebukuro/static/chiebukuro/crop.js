// プロフィール写真: 選んだ写真をズーム・移動して、丸い範囲で切り取る (600px の正方形の JPEG にして送る)
(function () {
    var dialog = document.getElementById("cb-crop");
    var canvas = document.getElementById("cb-crop-canvas");
    var zoomInput = document.getElementById("cb-crop-zoom");
    if (!dialog || !dialog.showModal || !canvas || !window.DataTransfer) return;

    var ctx = canvas.getContext("2d");
    var SIZE = canvas.width;      // 表示用キャンバス (正方形)
    var OUT = 600;                // 送る写真の大きさ
    var image = null, input = null, original = null;
    var base = 1, zoom = 1, cx = 0, cy = 0;   // cx, cy = 画像の中で、枠のまん中に来る点
    var pointers = {}, lastDist = 0;

    function scale() { return base * zoom; }

    function clamp() {
        // 枠の外に余白が出ないようにする
        var half = SIZE / 2 / scale();
        cx = Math.min(Math.max(cx, half), image.naturalWidth - half);
        cy = Math.min(Math.max(cy, half), image.naturalHeight - half);
    }

    function draw(target, size) {
        var c = target.getContext("2d");
        var s = scale() * size / SIZE;
        c.fillStyle = "#fff";
        c.fillRect(0, 0, size, size);
        c.drawImage(image, size / 2 - cx * s, size / 2 - cy * s, image.naturalWidth * s, image.naturalHeight * s);
    }

    function redraw() { clamp(); draw(canvas, SIZE); }

    function open(file, target) {
        var url = URL.createObjectURL(file);
        var img = new Image();
        img.onload = function () {
            image = img; input = target; original = file;
            base = SIZE / Math.min(img.naturalWidth, img.naturalHeight);
            zoom = 1; zoomInput.value = "1";
            cx = img.naturalWidth / 2; cy = img.naturalHeight / 2;
            redraw();
            dialog.showModal();
        };
        img.onerror = function () { URL.revokeObjectURL(url); };   // 読めない写真 (HEIC など) はそのまま送る
        img.src = url;
    }

    function setZoom(value) {
        zoom = Math.min(4, Math.max(1, value));
        zoomInput.value = String(zoom);
        redraw();
    }

    // 写真を選んだら、ほかの処理 (写真を小さくする処理) より先に切り取り画面を出す
    document.addEventListener("change", function (event) {
        var target = event.target;
        if (!target.matches || !target.matches("input[type=file][data-crop]")) return;
        var file = target.files && target.files[0];
        if (!file || target.dataset.cropped === file.name) return;
        event.stopImmediatePropagation();
        open(file, target);
    }, true);

    zoomInput.addEventListener("input", function () { setZoom(parseFloat(zoomInput.value)); });

    canvas.addEventListener("wheel", function (event) {
        event.preventDefault();
        setZoom(zoom * (event.deltaY < 0 ? 1.08 : 1 / 1.08));
    }, { passive: false });

    canvas.addEventListener("pointerdown", function (event) {
        canvas.setPointerCapture(event.pointerId);
        pointers[event.pointerId] = { x: event.clientX, y: event.clientY };
        lastDist = 0;
    });
    canvas.addEventListener("pointermove", function (event) {
        var prev = pointers[event.pointerId];
        if (!prev || !image) return;
        var ids = Object.keys(pointers);
        var ratio = SIZE / canvas.getBoundingClientRect().width;   // 画面の大きさ -> キャンバスの大きさ
        if (ids.length === 2) {
            pointers[event.pointerId] = { x: event.clientX, y: event.clientY };
            var a = pointers[ids[0]], b = pointers[ids[1]];
            var dist = Math.hypot(a.x - b.x, a.y - b.y);
            if (lastDist) setZoom(zoom * dist / lastDist);
            lastDist = dist;
            return;
        }
        cx -= (event.clientX - prev.x) * ratio / scale();
        cy -= (event.clientY - prev.y) * ratio / scale();
        pointers[event.pointerId] = { x: event.clientX, y: event.clientY };
        redraw();
    });
    function lift(event) { delete pointers[event.pointerId]; lastDist = 0; }
    canvas.addEventListener("pointerup", lift);
    canvas.addEventListener("pointercancel", lift);

    function finish(keep) {
        dialog.close();
        if (!input) return;
        if (!keep) {
            input.value = "";
            input.dispatchEvent(new Event("change", { bubbles: true }));
            return;
        }
        var out = document.createElement("canvas");
        out.width = OUT; out.height = OUT;
        draw(out, OUT);
        out.toBlob(function (blob) {
            if (!blob) return;
            var name = (original.name || "photo").replace(/\.[^.]+$/, "") + "-face.jpg";
            var transfer = new DataTransfer();
            transfer.items.add(new File([blob], name, { type: "image/jpeg" }));
            input.files = transfer.files;
            input.dataset.cropped = name;
            input.dataset.shrunk = name;   // もう小さいので、写真を小さくする処理は飛ばす
            input.dispatchEvent(new Event("change", { bubbles: true }));
        }, "image/jpeg", 0.9);
    }

    document.getElementById("cb-crop-ok").addEventListener("click", function () { finish(true); });
    document.getElementById("cb-crop-cancel").addEventListener("click", function () { finish(false); });
    dialog.addEventListener("cancel", function (event) { event.preventDefault(); finish(false); });
})();
