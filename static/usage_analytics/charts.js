/* =====================================================
   Yapp分析: 積み上げ棒グラフ (SVG, ライブラリなし)

   <div data-ya-chart="chart-id"></div> と
   {{ data|json_script:"chart-id" }} を置くと描く。
   data = {labels: [...], series: [{name, color, values}], unit}
   ===================================================== */

(() => {

    "use strict";

    const SVG_NS = "http://www.w3.org/2000/svg";
    const HEIGHT = 220;
    const PAD = { top: 12, right: 8, bottom: 26, left: 34 };
    const GAP = 2;

    function el(name, attrs, parent) {
        const node = document.createElementNS(SVG_NS, name);
        for (const [key, value] of Object.entries(attrs || {})) {
            node.setAttribute(key, value);
        }
        if (parent) parent.appendChild(node);
        return node;
    }

    function niceMax(value) {
        if (value <= 4) return 4;
        const power = Math.pow(10, Math.floor(Math.log10(value)));
        for (const step of [1, 2, 2.5, 5, 10]) {
            const candidate = step * power;
            if (candidate >= value) return candidate;
        }
        return 10 * power;
    }

    // 上の角だけ丸い棒 (下は軸に付けたまま)
    function topRoundedBar(x, y, w, h, r) {
        r = Math.min(r, w / 2, h);
        return [
            `M${x},${y + h}`,
            `V${y + r}`,
            `Q${x},${y} ${x + r},${y}`,
            `H${x + w - r}`,
            `Q${x + w},${y} ${x + w},${y + r}`,
            `V${y + h}`,
            "Z",
        ].join(" ");
    }

    function escapeHtml(text) {
        const span = document.createElement("span");
        span.textContent = text;
        return span.innerHTML;
    }

    function format(n) {
        return Number(n).toLocaleString("ja-JP");
    }

    function buildLegend(root, data) {
        if (data.series.length < 2) return;
        const legend = document.createElement("div");
        legend.className = "ya-legend";
        for (const series of data.series) {
            const item = document.createElement("span");
            item.className = "ya-legend-item";
            const swatch = document.createElement("i");
            swatch.className = `ya-swatch ya-${series.color}`;
            item.append(swatch, series.name);
            legend.appendChild(item);
        }
        root.appendChild(legend);
    }

    function buildTable(root, data) {
        const details = document.createElement("details");
        details.className = "ya-table-toggle";
        const summary = document.createElement("summary");
        summary.textContent = "表で見る";
        details.appendChild(summary);

        const wrap = document.createElement("div");
        wrap.className = "ya-table-wrap";
        const table = document.createElement("table");
        table.className = "ya-table ya-table-compact";

        const head = table.createTHead().insertRow();
        for (const text of ["", ...data.series.map((s) => s.name), "合計"]) {
            const th = document.createElement("th");
            th.textContent = text;
            head.appendChild(th);
        }

        const body = table.createTBody();
        data.labels.forEach((label, i) => {
            const row = body.insertRow();
            row.insertCell().textContent = label;
            let total = 0;
            for (const series of data.series) {
                total += series.values[i];
                const cell = row.insertCell();
                cell.textContent = format(series.values[i]);
                cell.className = "ya-num";
            }
            const cell = row.insertCell();
            cell.textContent = format(total);
            cell.className = "ya-num";
        });

        wrap.appendChild(table);
        details.appendChild(wrap);
        root.appendChild(details);
    }

    function draw(holder, data) {
        holder.querySelector("svg")?.remove();

        const width = Math.max(holder.clientWidth, 280);
        const plotW = width - PAD.left - PAD.right;
        const plotH = HEIGHT - PAD.top - PAD.bottom;
        const count = data.labels.length;

        const totals = data.labels.map((_, i) =>
            data.series.reduce((sum, s) => sum + s.values[i], 0)
        );
        const max = niceMax(Math.max(0, ...totals));

        const svg = el("svg", {
            viewBox: `0 0 ${width} ${HEIGHT}`,
            width,
            height: HEIGHT,
            role: "img",
            "aria-label": holder.dataset.label || "グラフ",
        });

        // 目盛りと横線
        for (let i = 0; i <= 4; i++) {
            const value = (max / 4) * i;
            const y = PAD.top + plotH - (plotH * i) / 4;
            el("line", {
                x1: PAD.left, x2: width - PAD.right, y1: y, y2: y,
                class: i === 0 ? "ya-axis" : "ya-gridline",
            }, svg);
            const text = el("text", {
                x: PAD.left - 6, y: y + 4, class: "ya-tick", "text-anchor": "end",
            }, svg);
            text.textContent = Number.isInteger(value) ? format(value) : value.toFixed(1);
        }

        const slot = plotW / count;
        const barW = Math.max(2, Math.min(28, slot * 0.7));

        // 横軸のラベルは重ならない間隔で
        const every = Math.ceil(count / Math.max(1, Math.floor(plotW / 54)));

        data.labels.forEach((label, i) => {
            const x = PAD.left + slot * i + (slot - barW) / 2;
            let y = PAD.top + plotH;

            const visible = data.series
                .map((s) => ({ series: s, value: s.values[i] }))
                .filter((item) => item.value > 0);

            visible.forEach((item, index) => {
                const h = (item.value / max) * plotH;
                const isTop = index === visible.length - 1;
                const drawnH = Math.max(1, h - (isTop ? 0 : GAP));
                y -= h;
                if (isTop) {
                    el("path", {
                        d: topRoundedBar(x, y, barW, drawnH, 4),
                        class: `ya-fill-${item.series.color}`,
                    }, svg);
                } else {
                    el("rect", {
                        x, y: y + GAP, width: barW, height: drawnH,
                        class: `ya-fill-${item.series.color}`,
                    }, svg);
                }
            });

            if (i % every === 0) {
                const text = el("text", {
                    x: x + barW / 2, y: HEIGHT - 8, class: "ya-tick", "text-anchor": "middle",
                }, svg);
                text.textContent = label.replace(/\(.\)$/, "");
            }

            // ホバー用の透明な列 (棒より広い)
            const hit = el("rect", {
                x: PAD.left + slot * i, y: PAD.top, width: slot, height: plotH,
                class: "ya-hit", "data-index": i,
            }, svg);
            hit.addEventListener("mouseenter", () => show(holder, data, i, hit));
            hit.addEventListener("click", () => show(holder, data, i, hit));
        });

        svg.addEventListener("mouseleave", () => hide(holder));
        holder.appendChild(svg);
    }

    function show(holder, data, i, hit) {
        let tip = holder.querySelector(".ya-tooltip");
        if (!tip) {
            tip = document.createElement("div");
            tip.className = "ya-tooltip";
            holder.appendChild(tip);
        }

        holder.querySelectorAll(".ya-hit.is-active").forEach((n) => n.classList.remove("is-active"));
        hit.classList.add("is-active");

        const unit = data.unit || "";
        let total = 0;
        const rows = data.series.map((series) => {
            total += series.values[i];
            return `<div class="ya-tip-row"><i class="ya-swatch ya-${series.color}"></i>`
                + `<span>${escapeHtml(series.name)}</span><b>${format(series.values[i])}${unit}</b></div>`;
        });

        tip.innerHTML = `<div class="ya-tip-title">${escapeHtml(data.labels[i])}</div>${rows.join("")}`
            + (data.series.length > 1
                ? `<div class="ya-tip-row ya-tip-total"><span>合計</span><b>${format(total)}${unit}</b></div>`
                : "");

        const box = holder.getBoundingClientRect();
        const hitBox = hit.getBoundingClientRect();
        const center = hitBox.left - box.left + hitBox.width / 2;
        tip.style.display = "block";
        const left = Math.min(Math.max(center - tip.offsetWidth / 2, 0), box.width - tip.offsetWidth);
        tip.style.left = `${left}px`;
        tip.style.top = "0px";
    }

    function hide(holder) {
        const tip = holder.querySelector(".ya-tooltip");
        if (tip) tip.style.display = "none";
        holder.querySelectorAll(".ya-hit.is-active").forEach((n) => n.classList.remove("is-active"));
    }

    function init(root) {
        const source = document.getElementById(root.dataset.yaChart);
        if (!source) return;
        const data = JSON.parse(source.textContent);

        if (!data.series.length || data.series.every((s) => s.values.every((v) => !v))) {
            root.innerHTML = '<p class="ya-empty">この期間の記録はまだありません。</p>';
            return;
        }

        buildLegend(root, data);
        const holder = document.createElement("div");
        holder.className = "ya-chart";
        holder.dataset.label = root.dataset.label || "";
        root.appendChild(holder);
        buildTable(root, data);

        draw(holder, data);

        let width = holder.clientWidth;
        new ResizeObserver(() => {
            if (Math.abs(holder.clientWidth - width) > 8) {
                width = holder.clientWidth;
                draw(holder, data);
            }
        }).observe(holder);
    }

    document.querySelectorAll("[data-ya-chart]").forEach(init);

})();
