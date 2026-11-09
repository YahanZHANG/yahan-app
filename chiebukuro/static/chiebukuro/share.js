// 質問・つぶやきを、インスタのストーリーなどに貼れる画像カード (1080x1920) にしてシェアする。
// 端末のシェア画面が画像に対応していればそこから (インスタ・LINE など)、なければ画像を保存してリンクをコピー。
(function () {
    var W = 1080, H = 1920;

    function wrap(ctx, text, maxWidth, maxLines) {
        var lines = [], line = "";
        Array.from(text.replace(/\s+/g, " ")).forEach(function (ch) {
            if (ctx.measureText(line + ch).width > maxWidth) { lines.push(line); line = ch.trim(); } else { line += ch; }
        });
        if (line) lines.push(line);
        if (lines.length > maxLines) { lines = lines.slice(0, maxLines); lines[maxLines - 1] = lines[maxLines - 1].slice(0, -1) + "…"; }
        return lines;
    }

    function loadIcon(src) {
        return new Promise(function (resolve) {
            var img = new Image();
            img.onload = function () { resolve(img); };
            img.onerror = function () { resolve(null); };
            img.src = src;
        });
    }

    function draw(box, icon) {
        var canvas = document.createElement("canvas");
        canvas.width = W; canvas.height = H;
        var ctx = canvas.getContext("2d");
        var brand = getComputedStyle(document.documentElement).getPropertyValue("--brand").trim() || "#c8102e";
        var font = '"Hiragino Sans", "Hiragino Kaku Gothic ProN", "Noto Sans JP", "Yu Gothic", Meiryo, sans-serif';

        var bg = ctx.createLinearGradient(0, 0, W, H);
        bg.addColorStop(0, brand); bg.addColorStop(1, "#1d2340");
        ctx.fillStyle = bg; ctx.fillRect(0, 0, W, H);

        // カード (中身の量に合わせた高さで、上下のまん中に置く)
        var x = 80, w = W - 160;
        ctx.font = "800 64px " + font;
        var lines = wrap(ctx, box.dataset.text, w - 140, 8);
        ctx.font = "500 44px " + font;
        var subLines = box.dataset.sub ? wrap(ctx, box.dataset.sub, w - 140, 6) : [];
        var h = 150 + lines.length * 92 + (subLines.length ? 70 + subLines.length * 66 : 0) + 60;
        var y = Math.max(330, Math.round((330 + 1580 - h) / 2));
        ctx.fillStyle = "#ffffff";
        ctx.beginPath(); if (ctx.roundRect) ctx.roundRect(x, y, w, h, 48); else ctx.rect(x, y, w, h); ctx.fill();

        ctx.fillStyle = brand;
        ctx.font = "800 44px " + font;
        ctx.fillText(box.dataset.label, x + 70, y + 100);

        ctx.fillStyle = "#1d2125";
        ctx.font = "800 64px " + font;
        lines.forEach(function (line, i) { ctx.fillText(line, x + 70, y + 200 + i * 92); });

        if (subLines.length) {
            var top = y + 150 + lines.length * 92;
            ctx.fillStyle = "#e5e7eb";
            ctx.fillRect(x + 70, top, w - 140, 3);
            ctx.fillStyle = "#4b5563";
            ctx.font = "500 44px " + font;
            subLines.forEach(function (line, i) { ctx.fillText(line, x + 70, top + 80 + i * 66); });
        }

        // 下: アプリ名とアドレス
        if (icon) ctx.drawImage(icon, 80, 1640, 120, 120);
        ctx.fillStyle = "#ffffff";
        ctx.font = "800 56px " + font;
        ctx.fillText("スイス生活の知恵袋", icon ? 230 : 80, 1700);
        ctx.font = "500 38px " + font;
        ctx.globalAlpha = .85;
        ctx.fillText(box.dataset.url.replace(/^https?:\/\//, "").replace(/\?.*$/, ""), icon ? 230 : 80, 1760);
        ctx.globalAlpha = 1;
        ctx.font = "700 46px " + font;
        ctx.fillText("スイスで暮らす日本人の掲示板", 80, 250);
        return canvas;
    }

    function say(box, text) {
        var msg = box.querySelector("[data-share-msg]");
        msg.textContent = text; msg.hidden = false;
    }

    document.addEventListener("click", function (event) {
        var button = event.target.closest && event.target.closest("[data-share-image]");
        if (!button) return;
        var box = button.closest("[data-share]");
        // 先にリンクをコピー (インスタのストーリーの「リンク」スタンプに貼れるように)。押した直後でないとコピーできない
        if (navigator.clipboard) navigator.clipboard.writeText(box.dataset.url).catch(function () {});
        button.disabled = true;
        loadIcon(box.dataset.icon).then(function (icon) {
            var canvas = draw(box, icon);
            canvas.toBlob(function (blob) {
                button.disabled = false;
                if (!blob) return;
                var file = new File([blob], "swiss-chiebukuro.png", { type: "image/png" });
                var data = { files: [file], text: box.dataset.text + " " + box.dataset.url };
                if (navigator.canShare && navigator.canShare({ files: [file] })) {
                    navigator.share(data).catch(function () {});
                    say(box, "リンクもコピーしました。インスタのストーリーでは「リンク」スタンプに貼れます。");
                    return;
                }
                // シェア画面がないとき (パソコンなど): 画像を保存して、リンクをコピー
                var link = document.createElement("a");
                link.href = URL.createObjectURL(blob);
                link.download = file.name;
                document.body.appendChild(link); link.click(); link.remove();
                say(box, "画像を保存しました。リンクもコピーしたので、インスタのストーリーなどに貼ってください。");
            }, "image/png");
        });
    });
})();
