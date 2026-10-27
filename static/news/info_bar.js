/* ==========================================
   Swiss News - HOME の為替・天気バーと、設定の「天気を表示する地域」

   天気の地域（最大2つ）はこの端末に保存する。
   まだ選んでいない端末は「暮らしのお知らせ」で選んだ地域と同じ。
   どちらもなければチューリッヒ。
========================================== */

(() => {
    "use strict";

    const WEATHER_KEY = "swissnews_weather_regions";
    const LIFE_KEY = "swissnews_info_regions";
    const MAX_WEATHER = 2;

    function escape(text) {
        const div = document.createElement("div");
        div.textContent = String(text);
        return div.innerHTML;
    }

    function readStorage(storage, key) {
        try {
            const saved = storage.getItem(key);
            return saved === null ? null : JSON.parse(saved);
        } catch (error) {
            return null;
        }
    }

    function writeStorage(storage, key, value) {
        try {
            if (value === null) {
                storage.removeItem(key);
            } else {
                storage.setItem(key, JSON.stringify(value));
            }
        } catch (error) {
            // 保存できない環境（プライベートモードなど）では何もしない
        }
    }

    // この端末の通知で選んだ「暮らしのお知らせ」の地域（なければ空）
    async function lifeRegions() {
        const saved = readStorage(sessionStorage, LIFE_KEY);

        if (saved !== null) {
            return saved;
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

        writeStorage(sessionStorage, LIFE_KEY, regions);

        return regions;
    }

    // 天気の地域。設定で選んでいればそれ、なければ暮らしのお知らせと同じ
    async function weatherRegions() {
        const saved = readStorage(localStorage, WEATHER_KEY);
        return saved !== null ? saved : lifeRegions();
    }


    /* ==========================================
       HOME のバー
    ========================================== */

    function arrow(value) {
        if (!value) {
            return "";
        }
        return value > 0
            ? '<span class="news-info-change is-up" aria-label="上昇">▲</span>'
            : '<span class="news-info-change is-down" aria-label="下落">▼</span>';
    }

    function change(value) {
        if (value === null || value === undefined || value === 0) {
            return "";
        }
        const up = value > 0;
        return `<span class="news-info-change ${up ? "is-up" : "is-down"}">${up ? "▲" : "▼"}${Math.abs(value).toFixed(1)}%</span>`;
    }

    function rate(code, info) {
        return info.rate.toFixed(code === "JPY" ? 1 : 3);
    }

    function setupBar(bar) {
        const strip = bar.querySelector(".news-info-strip");
        const detail = bar.querySelector(".news-info-detail");

        function render(data) {
            const parts = [];
            const fx = data.fx;

            if (fx) {
                const jpy = fx.rates.JPY;
                parts.push(
                    `<span class="news-info-item">1CHF=${rate("JPY", jpy)}円${arrow(jpy.change)}</span>`
                );
            }

            data.weather.forEach((place) => {
                parts.push(
                    `<span class="news-info-item">${place.emoji} ${escape(place.name)} ${place.temp}°</span>`
                );
            });

            if (!parts.length) {
                return;
            }

            strip.innerHTML = `<span class="news-info-items">${parts.join('<span class="news-info-sep" aria-hidden="true"></span>')}</span>`
                + '<span class="news-info-toggle" aria-hidden="true"></span>';

            let html = "";

            data.weather.forEach((place) => {
                html += `<div class="news-info-block"><h3>${escape(place.name)}の天気</h3>`;

                if (place.hours && place.hours.length) {
                    html += '<div class="news-info-hours">';
                    place.hours.forEach((hour) => {
                        html += `<div class="news-info-hour"><span>${escape(hour.label)}</span><span class="news-info-hour-emoji">${hour.emoji}</span><strong>${hour.temp}°</strong></div>`;
                    });
                    html += "</div>";
                }

                html += "<table>";
                place.days.forEach((day) => {
                    html += `<tr><th>${escape(day.label)}</th><td>${day.emoji} ${escape(day.text)}</td><td><span class="news-info-max">${day.max}°</span> / <span class="news-info-min">${day.min}°</span></td></tr>`;
                });
                html += "</table></div>";
            });

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

            html += '<p class="news-info-note">天気の地域は<a href="/news/settings/#news-weather-settings">設定</a>で変えられます（2つまで）。</p>';

            detail.innerHTML = html;
            bar.hidden = false;
        }

        strip.addEventListener("click", () => {
            const open = detail.hidden;
            detail.hidden = !open;
            strip.setAttribute("aria-expanded", String(open));
            bar.classList.toggle("is-open", open);
        });

        (async () => {
            try {
                const regions = await weatherRegions();
                const url = `${bar.dataset.url}?regions=${encodeURIComponent(regions.join(","))}`;
                const response = await fetch(url, { credentials: "same-origin" });

                if (response.ok) {
                    render(await response.json());
                }
            } catch (error) {
                console.warn(error);
            }
        })();
    }


    /* ==========================================
       設定の「天気を表示する地域」
    ========================================== */

    function setupSettings(card) {
        const inputs = Array.from(card.querySelectorAll("input[type=checkbox]"));
        const selected = document.getElementById("news-weather-selected");
        const reset = document.getElementById("news-weather-reset");
        const status = document.getElementById("news-weather-status");

        function names() {
            return inputs
                .filter((input) => input.checked)
                .map((input) => input.nextElementSibling.textContent.trim());
        }

        function show(isCustom) {
            const picked = names();
            const full = picked.length >= MAX_WEATHER;

            inputs.forEach((input) => {
                input.disabled = full && !input.checked;
            });

            if (!picked.length) {
                selected.textContent = "選んでいないので、チューリッヒの天気を表示します";
            } else if (isCustom) {
                selected.textContent = `表示中：${picked.join("・")}`;
            } else {
                selected.textContent = `表示中：${picked.join("・")}（暮らしのお知らせと同じ）`;
            }

            reset.hidden = !isCustom;
        }

        function check(slugs) {
            const wanted = slugs.slice(0, MAX_WEATHER);
            inputs.forEach((input) => {
                input.checked = wanted.includes(input.value);
            });
        }

        async function load() {
            const saved = readStorage(localStorage, WEATHER_KEY);

            if (saved !== null) {
                check(saved);
                show(true);
                return;
            }

            // 暮らしのお知らせの地域は、設定画面の並び順で最初の2つ
            const life = await lifeRegions();
            check(inputs.map((input) => input.value).filter((slug) => life.includes(slug)));
            show(false);
        }

        card.addEventListener("change", () => {
            const slugs = inputs
                .filter((input) => input.checked)
                .map((input) => input.value);

            writeStorage(localStorage, WEATHER_KEY, slugs);
            show(true);
            status.textContent = "保存しました。";
        });

        reset.addEventListener("click", async () => {
            writeStorage(localStorage, WEATHER_KEY, null);
            writeStorage(sessionStorage, LIFE_KEY, null);
            await load();
            status.textContent = "暮らしのお知らせと同じ地域にもどしました。";
        });

        // 暮らしのお知らせの地域を変えたら、まだ天気を自分で選んでいない人は一緒に変わる
        document.addEventListener("swissnews:life-regions-changed", () => {
            if (readStorage(localStorage, WEATHER_KEY) === null) {
                load();
            }
        });

        load();
    }


    const bar = document.getElementById("news-info-bar");
    const card = document.getElementById("news-weather-settings");

    if (bar) {
        setupBar(bar);
    }

    if (card) {
        setupSettings(card);
    }
})();
