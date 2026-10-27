/* ==========================================
   Swiss News - HOME の為替・天気バー
   通知で選んだ「暮らしのお知らせ」の地域（最大2つ）の天気を出す。
   地域を選んでいない端末はチューリッヒ。押すと EUR・USD と3日間の天気が開く。
========================================== */

(() => {
    "use strict";

    const bar = document.getElementById("news-info-bar");

    if (!bar) {
        return;
    }

    const strip = bar.querySelector(".news-info-strip");
    const detail = bar.querySelector(".news-info-detail");
    const REGIONS_KEY = "swissnews_info_regions";

    function escape(text) {
        const div = document.createElement("div");
        div.textContent = String(text);
        return div.innerHTML;
    }

    function change(value) {
        if (value === null || value === undefined || value === 0) {
            return "";
        }
        const up = value > 0;
        return `<span class="news-info-change ${up ? "is-up" : "is-down"}">${up ? "▲" : "▼"}${Math.abs(value).toFixed(1)}%</span>`;
    }

    // バーには矢印だけ（細かい%は開いた画面で）
    function arrow(value) {
        if (!value) {
            return "";
        }
        return value > 0
            ? '<span class="news-info-change is-up" aria-label="上昇">▲</span>'
            : '<span class="news-info-change is-down" aria-label="下落">▼</span>';
    }

    function rate(code, info) {
        const digits = code === "JPY" ? 1 : 3;
        return info.rate.toFixed(digits);
    }

    // この端末の通知で選んだ地域（なければ空）
    async function deviceRegions() {
        try {
            const saved = sessionStorage.getItem(REGIONS_KEY);
            if (saved !== null) {
                return JSON.parse(saved);
            }
        } catch (error) {
            // sessionStorage が使えないときは毎回たずねる
        }

        let regions = [];
        const push = window.SwissNewsPush;
        const config = document.getElementById("news-push-config");

        try {
            const subscription = push && push.isSupported()
                ? await push.getSubscription()
                : null;

            if (subscription && config) {
                const response = await fetch(config.dataset.optionsUrl, {
                    method: "POST",
                    credentials: "same-origin",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": config.dataset.csrfToken,
                    },
                    body: JSON.stringify({ endpoint: subscription.endpoint }),
                });
                if (response.ok) {
                    regions = (await response.json()).alert_regions || [];
                }
            }
        } catch (error) {
            console.warn(error);
        }

        try {
            sessionStorage.setItem(REGIONS_KEY, JSON.stringify(regions));
        } catch (error) {
            // 何もしない
        }

        return regions;
    }

    function render(data) {
        const parts = [];
        const fx = data.fx;

        if (fx) {
            const jpy = fx.rates.JPY;
            parts.push(
                `<span class="news-info-item">💴 1CHF=${rate("JPY", jpy)}円${arrow(jpy.change)}</span>`
            );
        }

        data.weather.forEach((place) => {
            parts.push(
                `<span class="news-info-item">${place.emoji} ${escape(place.name)} ${place.temp}°</span>`
            );
        });

        if (!parts.length) {
            return false;
        }

        strip.innerHTML = parts.join('<span class="news-info-sep" aria-hidden="true"></span>');

        let html = "";

        if (fx) {
            const date = new Date(`${fx.date}T12:00:00`);
            html += '<div class="news-info-block"><h3>為替（1 CHF あたり）</h3><table>';
            [["JPY", "円"], ["EUR", "ユーロ"], ["USD", "ドル"]].forEach(([code, name]) => {
                const info = fx.rates[code];
                if (info) {
                    html += `<tr><th>${name}</th><td>${rate(code, info)} ${code}</td><td>${change(info.change)}</td></tr>`;
                }
            });
            html += `</table><p class="news-info-note">${date.getMonth() + 1}/${date.getDate()} の欧州中央銀行のレート（平日1日1回更新・前の営業日比）</p></div>`;
        }

        data.weather.forEach((place) => {
            html += `<div class="news-info-block"><h3>${escape(place.name)}の天気</h3><table>`;
            place.days.forEach((day) => {
                html += `<tr><th>${escape(day.label)}</th><td>${day.emoji} ${escape(day.text)}</td><td><span class="news-info-max">${day.max}°</span> / <span class="news-info-min">${day.min}°</span></td></tr>`;
            });
            html += "</table></div>";
        });

        html += '<p class="news-info-note">天気の地域は、<a href="/news/settings/">設定</a>の「暮らしのお知らせ」で選んだ地域です（最大2つ）。</p>';

        detail.innerHTML = html;
        bar.hidden = false;
        return true;
    }

    strip.addEventListener("click", () => {
        const open = detail.hidden;
        detail.hidden = !open;
        strip.setAttribute("aria-expanded", String(open));
        bar.classList.toggle("is-open", open);
    });

    (async () => {
        try {
            const regions = await deviceRegions();
            const url = `${bar.dataset.url}?regions=${encodeURIComponent(regions.join(","))}`;
            const response = await fetch(url, { credentials: "same-origin" });

            if (response.ok) {
                render(await response.json());
            }
        } catch (error) {
            console.warn(error);
        }
    })();
})();
