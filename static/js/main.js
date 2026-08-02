"use strict";


/*
 * HTMLを安全にポップアップへ表示するためのエスケープ処理
 */
const escapeHtml = (value) => {
    const div = document.createElement("div");
    div.textContent = String(value ?? "");
    return div.innerHTML;
};


/*
 * datetime-local入力欄へ、端末の現在日時を分単位で設定する
 */
const setDefaultDateTimes = () => {
    const inputs = document.querySelectorAll(
        'input[data-default-now="true"]'
    );

    if (inputs.length === 0) {
        return;
    }

    const now = new Date();

    const year = now.getFullYear();
    const month = String(
        now.getMonth() + 1
    ).padStart(2, "0");
    const day = String(
        now.getDate()
    ).padStart(2, "0");
    const hour = String(
        now.getHours()
    ).padStart(2, "0");
    const minute = String(
        now.getMinutes()
    ).padStart(2, "0");

    const localDateTime = (
        `${year}-${month}-${day}T${hour}:${minute}`
    );

    inputs.forEach((input) => {
        if (!input.value) {
            input.value = localDateTime;
        }
    });
};


/*
 * DjangoのCSRF Cookieを取得する
 */
const getCookie = (name) => {
    const cookies = document.cookie
        ? document.cookie.split(";")
        : [];

    for (const cookie of cookies) {
        const trimmedCookie = cookie.trim();

        if (trimmedCookie.startsWith(`${name}=`)) {
            return decodeURIComponent(
                trimmedCookie.substring(name.length + 1)
            );
        }
    }

    return null;
};


/*
 * 現在地更新の進行状況やエラーを画面へ表示する
 */
const showLocationMessage = (message, type) => {
    const messageElement = document.getElementById(
        "location-share-message"
    );

    if (!messageElement) {
        return;
    }

    messageElement.textContent = message;
    messageElement.className = (
        `location-share-message is-visible is-${type}`
    );
};


/*
 * 緯度・経度から2地点間の直線距離を計算する
 * Haversine公式を使用
 */
const calculateDistanceMeters = (
    latitude1,
    longitude1,
    latitude2,
    longitude2
) => {
    const earthRadiusMeters = 6371000;

    const toRadians = (degrees) => (
        degrees * Math.PI / 180
    );

    const latitudeDelta = toRadians(
        latitude2 - latitude1
    );

    const longitudeDelta = toRadians(
        longitude2 - longitude1
    );

    const firstLatitude = toRadians(latitude1);
    const secondLatitude = toRadians(latitude2);

    const a = (
        Math.sin(latitudeDelta / 2) ** 2
        + Math.cos(firstLatitude)
        * Math.cos(secondLatitude)
        * Math.sin(longitudeDelta / 2) ** 2
    );

    const boundedA = Math.min(
        1,
        Math.max(0, a)
    );

    const angularDistance = (
        2 * Math.atan2(
            Math.sqrt(boundedA),
            Math.sqrt(1 - boundedA)
        )
    );

    return earthRadiusMeters * angularDistance;
};


/*
 * 現在ログインしている端末から、各家族までの距離を表示する
 */
const updateFamilyDistances = (
    currentLatitude,
    currentLongitude
) => {
    const mapDataElement = document.getElementById(
        "family-map-data"
    );

    if (!mapDataElement) {
        return;
    }

    let locations;

    try {
        locations = JSON.parse(
            mapDataElement.textContent
        );
    } catch (error) {
        console.error(
            "家族の位置データを読み込めませんでした。",
            error
        );
        return;
    }

    locations.forEach((location) => {
        const distanceElement = document.querySelector(
            `[data-family-user-id="${location.user_id}"]`
        );

        if (!distanceElement) {
            return;
        }

        const latitude = Number(location.latitude);
        const longitude = Number(location.longitude);

        if (
            !Number.isFinite(latitude)
            || !Number.isFinite(longitude)
        ) {
            distanceElement.textContent = (
                "距離を計算できません"
            );
            return;
        }

        const distanceMeters = calculateDistanceMeters(
            currentLatitude,
            currentLongitude,
            latitude,
            longitude
        );

        if (distanceMeters < 1000) {
            distanceElement.textContent = (
                `現在地から約${Math.round(distanceMeters)}m`
            );
        } else {
            distanceElement.textContent = (
                `現在地から約${(
                    distanceMeters / 1000
                ).toFixed(1)}km`
            );
        }
    });
};


/*
 * ホーム画面を開いたときに現在地を取得する
 *
 * 1回目：
 * 現在地取得 → 距離計算 → Djangoへ保存 → 再読み込み
 *
 * 再読み込み後：
 * 現在地取得 → 距離計算のみ
 *
 * sessionStorageを使って無限再読み込みを防ぐ
 */
const initializeAutomaticLocationUpdate = () => {
    const mapElement = document.getElementById(
        "family-map"
    );

    if (!mapElement) {
        return;
    }

    if (!navigator.geolocation) {
        showLocationMessage(
            "この端末では位置情報を取得できません。",
            "error"
        );
        return;
    }

    const shareUrl = mapElement.dataset.shareUrl;

    if (!shareUrl) {
        showLocationMessage(
            "現在地の保存先を取得できませんでした。",
            "error"
        );
        return;
    }

    const locationWasJustSaved = (
        sessionStorage.getItem(
            "locationJustSaved"
        ) === "1"
    );

    if (locationWasJustSaved) {
        sessionStorage.removeItem(
            "locationJustSaved"
        );
    }

    showLocationMessage(
        locationWasJustSaved
            ? "家族までの距離を計算しています…"
            : "現在地を自動更新しています…",
        "loading"
    );

    navigator.geolocation.getCurrentPosition(
        async (position) => {
            const currentLatitude = (
                position.coords.latitude
            );

            const currentLongitude = (
                position.coords.longitude
            );

            /*
             * 保存処理の有無にかかわらず、
             * 取得した端末位置を使って距離を計算する
             */
            updateFamilyDistances(
                currentLatitude,
                currentLongitude
            );

            /*
             * 保存直後の再読み込みでは、
             * 再保存せず距離計算だけで終了する
             */
            if (locationWasJustSaved) {
                showLocationMessage(
                    "現在地と家族までの距離を更新しました。",
                    "success"
                );
                return;
            }

            const payload = {
                latitude: currentLatitude,
                longitude: currentLongitude,
                accuracy: position.coords.accuracy,
            };

            try {
                const response = await fetch(
                    shareUrl,
                    {
                        method: "POST",
                        headers: {
                            "Content-Type": (
                                "application/json"
                            ),
                            "X-CSRFToken": (
                                getCookie("csrftoken")
                            ),
                        },
                        body: JSON.stringify(payload),
                    }
                );

                let data = {};

                try {
                    data = await response.json();
                } catch {
                    throw new Error(
                        "サーバーから正しい応答を受け取れませんでした。"
                    );
                }

                if (!response.ok || !data.success) {
                    throw new Error(
                        data.error
                        || "現在地を保存できませんでした。"
                    );
                }

                showLocationMessage(
                    "現在地を更新しました。",
                    "success"
                );

                sessionStorage.setItem(
                    "locationJustSaved",
                    "1"
                );

                /*
                 * Djangoから最新座標を取得し直し、
                 * 地図のピンを更新する
                 */
                window.setTimeout(() => {
                    window.location.reload();
                }, 500);
            } catch (error) {
                sessionStorage.removeItem(
                    "locationJustSaved"
                );

                showLocationMessage(
                    error.message
                    || "現在地を保存できませんでした。",
                    "error"
                );
            }
        },
        (error) => {
            let message = (
                "現在地を取得できませんでした。"
            );

            if (
                error.code
                === error.PERMISSION_DENIED
            ) {
                message = (
                    "位置情報の利用が許可されていません。"
                );
            } else if (
                error.code
                === error.POSITION_UNAVAILABLE
            ) {
                message = (
                    "現在地を特定できませんでした。"
                );
            } else if (
                error.code
                === error.TIMEOUT
            ) {
                message = (
                    "現在地の取得がタイムアウトしました。"
                );
            }

            sessionStorage.removeItem(
                "locationJustSaved"
            );

            showLocationMessage(
                message,
                "error"
            );
        },
        {
            enableHighAccuracy: true,
            timeout: 15000,
            maximumAge: 0,
        }
    );
};


/*
 * OpenStreetMap＋Leafletの家族マップを作成する
 */
const initializeFamilyMap = () => {
    const mapElement = document.getElementById(
        "family-map"
    );

    const mapDataElement = document.getElementById(
        "family-map-data"
    );

    if (
        !mapElement
        || !mapDataElement
        || typeof L === "undefined"
    ) {
        return;
    }

    let locations;

    try {
        locations = JSON.parse(
            mapDataElement.textContent
        );
    } catch (error) {
        console.error(
            "地図データを読み込めませんでした。",
            error
        );
        return;
    }

    const map = L.map(
        mapElement,
        {
            zoomControl: true,
        }
    );

    /*
     * 地図領域の大きさをLeafletへ再認識させる
     */
    const refreshMapSize = () => {
        map.invalidateSize({
            pan: false,
        });
    };

    L.tileLayer(
        "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        {
            subdomains: ["a", "b", "c"],
            maxZoom: 19,
            attribution: (
                '&copy; '
                + '<a href="'
                + 'https://www.openstreetmap.org/copyright'
                + '" target="_blank" '
                + 'rel="noopener noreferrer">'
                + 'OpenStreetMap contributors'
                + "</a>"
            ),
        }
    ).addTo(map);

    /*
     * 位置情報が1件もない場合
     */
    if (locations.length === 0) {
        map.setView(
            [47.3769, 8.5417],
            10
        );

        L.popup()
            .setLatLng(
                [47.3769, 8.5417]
            )
            .setContent(
                "現在地はまだ共有されていません。"
            )
            .openOn(map);
    } else {
        const markerCoordinates = [];

        /*
         * ほぼ同じ場所にいる家族を、
         * 1つのグループピンにまとめる
         *
         * 小数点以下5桁：
         * おおよそ1m前後の単位
         */
        const groupedLocations = new Map();

        locations.forEach((location) => {
            const latitude = Number(
                location.latitude
            );

            const longitude = Number(
                location.longitude
            );

            if (
                !Number.isFinite(latitude)
                || !Number.isFinite(longitude)
            ) {
                return;
            }

            const key = (
                `${latitude.toFixed(5)},`
                + `${longitude.toFixed(5)}`
            );

            if (!groupedLocations.has(key)) {
                groupedLocations.set(
                    key,
                    []
                );
            }

            groupedLocations
                .get(key)
                .push({
                    ...location,
                    latitude,
                    longitude,
                });
        });

        groupedLocations.forEach((members) => {
            const firstMember = members[0];

            const coordinates = [
                firstMember.latitude,
                firstMember.longitude,
            ];

            markerCoordinates.push(
                coordinates
            );

            const markerLabel = (
                members.length === 1
                    ? firstMember.label
                    : members.length
            );

            const familyIcon = L.divIcon({
                className: (
                    "family-map-marker-wrapper"
                ),
                html: `
                    <div class="family-map-marker">
                        ${escapeHtml(markerLabel)}
                    </div>
                `,
                iconSize: [44, 44],
                iconAnchor: [22, 22],
                popupAnchor: [0, -24],
            });

            const memberDetails = members
                .map((member) => {
                    const accuracyText = (
                        member.accuracy
                            ? (
                                `<br>精度：約${
                                    escapeHtml(
                                        member.accuracy
                                    )
                                }m`
                            )
                            : ""
                    );

                    return `
                        <div
                            class="family-map-popup-member"
                        >
                            <strong>
                                ${escapeHtml(member.name)}
                            </strong>
                            <br>
                            ${escapeHtml(member.shared_at)}
                            に共有
                            ${accuracyText}
                        </div>
                    `;
                })
                .join("");

            L.marker(
                coordinates,
                {
                    icon: familyIcon,
                }
            )
                .addTo(map)
                .bindPopup(`
                    <div class="family-map-popup">
                        ${memberDetails}
                    </div>
                `);
        });

        if (markerCoordinates.length === 1) {
            map.setView(
                markerCoordinates[0],
                16
            );
        } else if (
            markerCoordinates.length > 1
        ) {
            map.fitBounds(
                markerCoordinates,
                {
                    padding: [45, 45],
                    maxZoom: 16,
                }
            );
        }
    }

    /*
     * 初期表示時に灰色の領域が残る問題へ対応
     */
    map.whenReady(() => {
        refreshMapSize();
    });

    window.requestAnimationFrame(() => {
        window.requestAnimationFrame(() => {
            refreshMapSize();
        });
    });

    window.setTimeout(
        refreshMapSize,
        300
    );

    window.setTimeout(
        refreshMapSize,
        1000
    );

    window.addEventListener(
        "resize",
        refreshMapSize
    );

    if (
        typeof ResizeObserver
        !== "undefined"
    ) {
        const resizeObserver = (
            new ResizeObserver(() => {
                refreshMapSize();
            })
        );

        resizeObserver.observe(
            mapElement
        );
    }
};

const initializeNextScheduleCountdown = () => {
    const card = document.querySelector(
        "[data-next-schedule-time]"
    );

    const countdownElement = document.getElementById(
        "next-schedule-countdown"
    );

    if (!card || !countdownElement) {
        return;
    }

    const scheduleTime = new Date(
        card.dataset.nextScheduleTime
    );

    if (Number.isNaN(scheduleTime.getTime())) {
        countdownElement.textContent = (
            "時刻不明"
        );
        return;
    }

    const updateCountdown = () => {
        const now = new Date();
        const differenceMs = (
            scheduleTime.getTime()
            - now.getTime()
        );

        if (differenceMs <= 0) {
            countdownElement.textContent = (
                "開始時刻です"
            );
            return;
        }

        const totalMinutes = Math.ceil(
            differenceMs / 60000
        );

        if (totalMinutes < 60) {
            countdownElement.textContent = (
                `あと${totalMinutes}分`
            );
            return;
        }

        const hours = Math.floor(
            totalMinutes / 60
        );

        const minutes = totalMinutes % 60;

        if (hours < 24) {
            countdownElement.textContent = (
                minutes === 0
                    ? `あと${hours}時間`
                    : `あと${hours}時間${minutes}分`
            );
            return;
        }

        const days = Math.floor(
            hours / 24
        );

        const remainingHours = hours % 24;

        countdownElement.textContent = (
            remainingHours === 0
                ? `あと${days}日`
                : `あと${days}日${remainingHours}時間`
        );
    };

    updateCountdown();

    window.setInterval(
        updateCountdown,
        30000
    );
};


const initializeFamilyDetails = () => {
    const iconButtons = document.querySelectorAll(
        "[data-family-detail-target]"
    );

    if (iconButtons.length === 0) {
        return;
    }

    iconButtons.forEach((button) => {
        button.addEventListener("click", () => {
            const targetId = (
                button.dataset.familyDetailTarget
            );

            const targetPanel = document.getElementById(
                targetId
            );

            if (!targetPanel) {
                return;
            }

            const wasOpen = (
                button.getAttribute("aria-expanded")
                === "true"
            );

            iconButtons.forEach((otherButton) => {
                otherButton.setAttribute(
                    "aria-expanded",
                    "false"
                );
            });

            document
                .querySelectorAll(".family-detail-panel")
                .forEach((panel) => {
                    panel.hidden = true;
                });

            if (!wasOpen) {
                button.setAttribute(
                    "aria-expanded",
                    "true"
                );

                targetPanel.hidden = false;
            }
        });
    });
};

const initializeUpcomingScheduleCountdowns = () => {
    const scheduleCards = document.querySelectorAll(
        "[data-countdown-target]"
    );

    if (scheduleCards.length === 0) {
        return;
    }

    const updateCountdowns = () => {
        const now = new Date();

        scheduleCards.forEach((card) => {
            const targetText = card.dataset.countdownTarget;
            const countdownElement = card.querySelector(
                ".upcoming-schedule-countdown"
            );

            if (!targetText || !countdownElement) {
                return;
            }

            const target = new Date(targetText);
            const difference = target - now;

            if (difference <= 0) {
                countdownElement.textContent = "開始時刻";
                return;
            }

            const totalMinutes = Math.floor(
                difference / 1000 / 60
            );

            const days = Math.floor(
                totalMinutes / 1440
            );

            const hours = Math.floor(
                (totalMinutes % 1440) / 60
            );

            const minutes = totalMinutes % 60;

            if (days > 0) {
                countdownElement.textContent = (
                    `あと${days}日${hours}時間`
                );
            } else if (hours > 0) {
                countdownElement.textContent = (
                    `あと${hours}時間${minutes}分`
                );
            } else {
                countdownElement.textContent = (
                    `あと${minutes}分`
                );
            }
        });
    };

    updateCountdowns();

    window.setInterval(
        updateCountdowns,
        30000
    );
};

/*
 * ページのHTMLが完成してから各機能を開始する
 */
document.addEventListener(
    "DOMContentLoaded",
    () => {
        setDefaultDateTimes();
        initializeFamilyMap();
        initializeAutomaticLocationUpdate();
        initializeUpcomingScheduleCountdowns();
        initializeFamilyDetails();
    }
);

const initializeExpenseForm = () => {
    const expenseForm = document.querySelector(
        ".expense-form"
    );

    if (!expenseForm) {
        return;
    }

    const totalInput = expenseForm.querySelector(
        '[data-expense-total="true"]'
    );

    const averageButton = document.getElementById(
        "expense-average-button"
    );

    const shareCheckboxes = Array.from(
        expenseForm.querySelectorAll(
            ".expense-share-checkbox"
        )
    );

    const shareInputs = Array.from(
        expenseForm.querySelectorAll(
            ".expense-share-input"
        )
    );

    const shareTotalElement = document.getElementById(
        "expense-share-total"
    );

    const parseAmount = (value) => {
        const number = Number.parseFloat(value);

        if (Number.isNaN(number)) {
            return 0;
        }

        return number;
    };

    const formatAmount = (value) => {
        return value.toLocaleString(
            "ja-JP",
            {
                minimumFractionDigits: 0,
                maximumFractionDigits: 2,
            }
        );
    };

    const updateShareTotal = () => {
        const shareTotal = shareInputs.reduce(
            (total, input) => (
                total + parseAmount(input.value)
            ),
            0
        );

        if (shareTotalElement) {
            shareTotalElement.textContent = (
                formatAmount(shareTotal)
            );
        }

        const totalAmount = totalInput
            ? parseAmount(totalInput.value)
            : 0;

        const difference = totalAmount - shareTotal;

        expenseForm.classList.toggle(
            "expense-total-matches",
            (
                totalAmount > 0
                && Math.abs(difference) < 0.001
            )
        );

        expenseForm.classList.toggle(
            "expense-total-mismatch",
            (
                totalAmount > 0
                && Math.abs(difference) >= 0.001
            )
        );
    };

    const syncCheckboxWithInput = (checkbox) => {
        const inputId = checkbox.dataset.shareInput;
        const shareInput = document.getElementById(
            inputId
        );

        if (!shareInput) {
            return;
        }

        if (!checkbox.checked) {
            shareInput.value = "0";
        }

        shareInput.disabled = !checkbox.checked;

        updateShareTotal();
    };

    shareCheckboxes.forEach((checkbox) => {
        const inputId = checkbox.dataset.shareInput;
        const shareInput = document.getElementById(
            inputId
        );

        if (!shareInput) {
            return;
        }

        const currentAmount = parseAmount(
            shareInput.value
        );

        checkbox.checked = currentAmount > 0;
        shareInput.disabled = !checkbox.checked;

        checkbox.addEventListener(
            "change",
            () => {
                syncCheckboxWithInput(checkbox);
            }
        );
    });

    shareInputs.forEach((input) => {
        input.addEventListener(
            "input",
            updateShareTotal
        );
    });

    if (totalInput) {
        totalInput.addEventListener(
            "input",
            updateShareTotal
        );
    }

    if (averageButton) {
        averageButton.addEventListener(
            "click",
            () => {
                const selectedCheckboxes = (
                    shareCheckboxes.filter(
                        (checkbox) => checkbox.checked
                    )
                );

                if (selectedCheckboxes.length === 0) {
                    window.alert(
                        "負担する人を1人以上選んで。"
                    );
                    return;
                }

                const totalAmount = totalInput
                    ? parseAmount(totalInput.value)
                    : 0;

                if (totalAmount <= 0) {
                    window.alert(
                        "先に合計金額を入力して。"
                    );
                    return;
                }

                const selectedCount = (
                    selectedCheckboxes.length
                );

                const roundedTotal = Math.round(
                    totalAmount * 100
                );

                const baseShare = Math.floor(
                    roundedTotal / selectedCount
                );

                let remainder = (
                    roundedTotal
                    - baseShare * selectedCount
                );

                selectedCheckboxes.forEach(
                    (checkbox) => {
                        const inputId = (
                            checkbox.dataset.shareInput
                        );

                        const shareInput = (
                            document.getElementById(
                                inputId
                            )
                        );

                        if (!shareInput) {
                            return;
                        }

                        let amountInCents = baseShare;

                        if (remainder > 0) {
                            amountInCents += 1;
                            remainder -= 1;
                        }

                        shareInput.disabled = false;
                        shareInput.value = (
                            amountInCents / 100
                        ).toFixed(2);
                    }
                );

                updateShareTotal();
            }
        );
    }

    expenseForm.addEventListener(
        "submit",
        () => {
            shareInputs.forEach((input) => {
                input.disabled = false;
            });
        }
    );

    updateShareTotal();
};

document.addEventListener(
    "DOMContentLoaded",
    initializeExpenseForm
);

