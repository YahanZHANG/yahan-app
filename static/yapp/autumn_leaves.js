// 秋のデザイン: <canvas data-autumn-leaves> に、紅葉とイチョウの葉が風に舞うアニメーションを描く。
// 和食の HOME と Yapp トップで共通。画面に見えていないとき・タブが裏にあるときは止める。
(function () {
    var canvases = document.querySelectorAll("canvas[data-autumn-leaves]");
    if (!canvases.length || !window.Path2D) return;

    var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    // 100x100 の箱に描いたもみじとイチョウ (中心が 50,50)
    var MAPLE = new Path2D("M50 4 L57 23 L68 15 L65 35 L84 27 L78 43 L96 45 L80 57 L86 67 L62 63 L58 76 L52 74 L51 96 L49 96 L48 74 L42 76 L38 63 L14 67 L20 57 L4 45 L22 43 L16 27 L35 35 L32 15 L43 23 Z");
    var GINKGO = new Path2D("M49 96 L49 62 C24 60 6 40 10 14 C22 22 36 22 47 30 L50 24 L53 30 C64 22 78 22 90 14 C94 40 76 60 51 62 L51 96 Z");
    var VEIN = new Path2D("M50 92 L50 30 M50 58 L24 46 M50 58 L76 46 M50 46 L36 24 M50 46 L64 24");

    var MAPLE_COLORS = ["#C8341F", "#D9472A", "#E8642C", "#EF7F2E", "#B52A1C", "#F09A35", "#A8321E"];
    var GINKGO_COLORS = ["#F2C14E", "#EBB33B", "#F5CF66"];

    function rand(min, max) { return min + Math.random() * (max - min); }

    function setup(canvas) {

        var ctx = canvas.getContext("2d");
        var mode = canvas.dataset.autumnLeaves || "box";
        var leaves = [];
        var motes = [];
        var width = 0;
        var height = 0;
        var running = false;
        var visible = true;
        var last = 0;
        var time = 0;

        function makeLeaf(anywhere) {
            var ginkgo = Math.random() < 0.22;
            var depth = rand(0.45, 1);
            var base = mode === "hero" ? 30 : Math.min(22 + width / 90, 32);
            return {
                x: rand(-0.1, 1.1) * width,
                y: anywhere ? rand(-0.1, 1) * height : rand(-0.25, -0.05) * height,
                size: base * depth * rand(0.75, 1.25),
                depth: depth,
                speed: (mode === "hero" ? 38 : 22) * (0.55 + depth * 0.7),
                rot: rand(0, Math.PI * 2),
                spin: rand(-1.4, 1.4),
                flip: rand(0, Math.PI * 2),
                flipSpeed: rand(1.2, 2.6),
                sway: rand(14, 34) * depth,
                swaySpeed: rand(0.6, 1.3),
                phase: rand(0, Math.PI * 2),
                color: ginkgo ? GINKGO_COLORS[Math.floor(Math.random() * GINKGO_COLORS.length)] : MAPLE_COLORS[Math.floor(Math.random() * MAPLE_COLORS.length)],
                ginkgo: ginkgo,
            };
        }

        function makeMote() {
            return {
                x: rand(0, width),
                y: rand(0, height),
                r: rand(1.2, mode === "hero" ? 3.6 : 2.4),
                speed: rand(4, 12),
                phase: rand(0, Math.PI * 2),
            };
        }

        function resize() {
            var rect = canvas.getBoundingClientRect();
            var ratio = Math.min(window.devicePixelRatio || 1, 2);
            width = Math.max(rect.width, 1);
            height = Math.max(rect.height, 1);
            canvas.width = Math.round(width * ratio);
            canvas.height = Math.round(height * ratio);
            ctx.setTransform(ratio, 0, 0, ratio, 0, 0);

            var count = Math.round(Math.min(Math.max(width * height / (mode === "hero" ? 26000 : 7000), 12), mode === "hero" ? 46 : 26));
            leaves = [];
            for (var i = 0; i < count; i++) leaves.push(makeLeaf(true));
            leaves.sort(function (a, b) { return a.depth - b.depth; });
            motes = [];
            for (var j = 0; j < Math.round(count * 0.6); j++) motes.push(makeMote());
            draw(0);
        }

        // ときどき強い風が吹く
        function wind(t) {
            return 10 + Math.sin(t * 0.35) * 14 + Math.max(0, Math.sin(t * 0.13)) * 46;
        }

        function draw(dt) {
            time += dt;
            ctx.clearRect(0, 0, width, height);

            // 夕日の中をただよう光の粒
            for (var m = 0; m < motes.length; m++) {
                var mote = motes[m];
                mote.y -= mote.speed * dt;
                mote.x += Math.sin(time * 0.8 + mote.phase) * 6 * dt;
                if (mote.y < -6) { mote.y = height + 6; mote.x = rand(0, width); }
                var glow = 0.25 + 0.25 * Math.sin(time * 1.6 + mote.phase);
                ctx.beginPath();
                ctx.fillStyle = "rgba(255, 214, 140," + glow.toFixed(3) + ")";
                ctx.arc(mote.x, mote.y, mote.r, 0, Math.PI * 2);
                ctx.fill();
            }

            var gust = wind(time);

            for (var i = 0; i < leaves.length; i++) {
                var leaf = leaves[i];

                leaf.y += leaf.speed * dt;
                leaf.x += (gust * leaf.depth + Math.sin(time * leaf.swaySpeed + leaf.phase) * leaf.sway) * dt;
                leaf.rot += leaf.spin * dt;
                leaf.flip += leaf.flipSpeed * dt;

                if (leaf.y > height + leaf.size || leaf.x > width + leaf.size * 2 || leaf.x < -leaf.size * 3) {
                    leaves[i] = makeLeaf(false);
                    leaves[i].depth = leaf.depth;
                    continue;
                }

                var scale = leaf.size / 100;
                ctx.save();
                ctx.translate(leaf.x, leaf.y);
                ctx.rotate(leaf.rot);
                // 葉がくるくる裏返るように、横だけ縮める
                ctx.scale(scale * (0.25 + 0.75 * Math.abs(Math.cos(leaf.flip))), scale);
                ctx.translate(-50, -50);
                ctx.globalAlpha = 0.55 + leaf.depth * 0.45;
                ctx.fillStyle = leaf.color;
                ctx.fill(leaf.ginkgo ? GINKGO : MAPLE);
                if (!leaf.ginkgo && leaf.size > 14) {
                    ctx.strokeStyle = "rgba(90, 20, 10, 0.35)";
                    ctx.lineWidth = 2.2;
                    ctx.stroke(VEIN);
                }
                ctx.restore();
            }
            ctx.globalAlpha = 1;
        }

        function frame(now) {
            if (!running) return;
            var dt = last ? Math.min((now - last) / 1000, 0.05) : 0;
            last = now;
            draw(dt);
            requestAnimationFrame(frame);
        }

        function update() {
            var should = visible && !document.hidden && !reduce;
            if (should && !running) {
                running = true;
                last = 0;
                requestAnimationFrame(frame);
            } else if (!should) {
                running = false;
            }
        }

        resize();
        window.addEventListener("resize", resize);
        document.addEventListener("visibilitychange", update);

        if (window.IntersectionObserver) {
            new IntersectionObserver(function (entries) {
                visible = entries[0].isIntersecting;
                update();
            }).observe(canvas);
        }

        update();
    }

    Array.prototype.forEach.call(canvases, setup);
})();
