/* =====================================================
   Yahan App - Online Users Dashboard
   ===================================================== */

(() => {

    "use strict";


    // =================================================
    // Configuration
    // =================================================

    const REFRESH_INTERVAL = 5000;


    // =================================================
    // Elements
    // =================================================

    const section = document.getElementById(
        "analytics-online"
    );

    if (!section) {
        return;
    }


    const onlineUrl = (
        section.dataset.onlineUrl
    );


    const countElement = document.getElementById(
        "analytics-online-count"
    );


    const statusElement = document.getElementById(
        "analytics-online-status"
    );


    const usersElement = document.getElementById(
        "analytics-online-users"
    );


    const checkedAtElement = document.getElementById(
        "analytics-online-checked-at"
    );


    if (
        !onlineUrl ||
        !countElement ||
        !statusElement ||
        !usersElement ||
        !checkedAtElement
    ) {
        return;
    }


    // =================================================
    // Request state
    // =================================================

    let loading = false;


    // =================================================
    // Create safe HTML element
    // =================================================

    function createElement(
        tag,
        className,
        text
    ) {

        const element = document.createElement(
            tag
        );


        if (className) {

            element.className = className;

        }


        if (
            text !== undefined &&
            text !== null
        ) {

            element.textContent = String(
                text
            );

        }


        return element;

    }


    // =================================================
    // Online status
    // =================================================

    function updateStatus(
        message,
        type
    ) {

        statusElement.className =
            "analytics-online-status";


        if (type) {

            statusElement.classList.add(
                "is-" + type
            );

        }


        statusElement.textContent = message;

    }


    // =================================================
    // Format checked time
    // =================================================

    function formatCheckedAt(value) {

        if (!value) {
            return "—";
        }


        const date = new Date(
            value
        );


        if (
            Number.isNaN(
                date.getTime()
            )
        ) {
            return "—";
        }


        return new Intl.DateTimeFormat(
            "ja-JP",
            {

                timeZone: "Europe/Zurich",

                hour: "2-digit",

                minute: "2-digit",

                second: "2-digit",

                hour12: false,

            }
        ).format(
            date
        );

    }


    // =================================================
    // Format last seen
    // =================================================

    function formatSecondsAgo(
        value
    ) {

        const seconds = Number(
            value
        );


        if (
            !Number.isFinite(seconds)
            || seconds < 0
        ) {

            return "確認中";

        }


        if (seconds === 0) {

            return "たった今";

        }


        return (
            Math.floor(seconds)
            + "秒前"
        );

    }


    // =================================================
    // Create online user card
    // =================================================

    function createUserCard(
        user
    ) {

        // ---------------------------------------------
        // User data
        // ---------------------------------------------

        const displayName = (
            user.display_name
            || user.username
            || "ユーザー"
        );


        const username = (
            user.username
            || ""
        );


        const apps = (
            Array.isArray(user.apps)
                ? user.apps
                : []
        );


        // ---------------------------------------------
        // Card
        // ---------------------------------------------

        const card = createElement(

            "div",

            "analytics-online-user"

        );


        // ---------------------------------------------
        // Avatar
        // ---------------------------------------------

        const avatar = createElement(

            "div",

            "analytics-online-avatar",

            Array.from(displayName)[0] || "?"

        );


        // ---------------------------------------------
        // User information
        // ---------------------------------------------

        const userInfo = createElement(

            "div",

            "analytics-online-user-info"

        );


        const name = createElement(

            "strong",

            "",

            "🟢 " + displayName

        );


        const id = createElement(

            "small",

            "",

            "@" + username

        );


        const appList = createElement(

            "div",

            "analytics-online-apps",

            apps.join("・")

        );


        userInfo.append(

            name,

            id,

            appList

        );


        // ---------------------------------------------
        // Last seen badge
        // ---------------------------------------------

        const time = createElement(

            "span",

            "analytics-online-time",

            formatSecondsAgo(
                user.seconds_ago
            )

        );


        // ---------------------------------------------
        // Assemble
        // ---------------------------------------------

        card.append(

            avatar,

            userInfo,

            time

        );


        return card;

    }


    // =================================================
    // Render online users
    // =================================================

    function renderOnlineUsers(
        data
    ) {

        const users = data.users;


        const count = users.length;


        // ---------------------------------------------
        // Online count
        // ---------------------------------------------

        countElement.textContent = (
            count
        );


        // ---------------------------------------------
        // Last checked
        // ---------------------------------------------

        checkedAtElement.textContent = (

            "最終確認："

            + formatCheckedAt(
                data.checked_at
            )

        );


        // ---------------------------------------------
        // Clear previous user list
        // ---------------------------------------------

        usersElement.replaceChildren();


        // ---------------------------------------------
        // Nobody online
        // ---------------------------------------------

        if (count === 0) {

            updateStatus(

                "現在オンラインと推定される"
                + "ユーザーはいない。"
                + "ただし、デプロイ時の"
                + "安全を保証するものではない。",

                "empty"

            );

            return;

        }


        // ---------------------------------------------
        // Online users found
        // ---------------------------------------------

        updateStatus(

            "現在"

            + count

            + "人がアプリを"
            + "利用している可能性がある。",

            "active"

        );


        // ---------------------------------------------
        // Build user list
        // ---------------------------------------------

        const fragment = (
            document.createDocumentFragment()
        );


        for (const user of users) {

            fragment.appendChild(

                createUserCard(
                    user
                )

            );

        }


        usersElement.appendChild(
            fragment
        );

    }


    // =================================================
    // Render error
    // =================================================

    function renderError() {

        countElement.textContent = "—";


        usersElement.replaceChildren();


        updateStatus(

            "⚠ オンライン状況を取得できない。"
            + "現在の利用状況は不明。",

            "error"

        );


        checkedAtElement.textContent = (
            "最終確認：取得失敗"
        );

    }


    // =================================================
    // Fetch online users
    // =================================================

    async function fetchOnlineUsers() {

        // ---------------------------------------------
        // Skip hidden dashboard
        // ---------------------------------------------

        if (
            document.visibilityState
            !== "visible"
        ) {

            return;

        }


        // ---------------------------------------------
        // Prevent overlapping requests
        // ---------------------------------------------

        if (loading) {
            return;
        }


        loading = true;


        try {

            const response = await fetch(

                onlineUrl,

                {

                    method: "GET",

                    credentials: "same-origin",

                    cache: "no-store",

                    headers: {

                        "Accept":
                            "application/json",

                    },

                }

            );


            // -----------------------------------------
            // HTTP error
            // -----------------------------------------

            if (!response.ok) {

                throw new Error(
                    "Online API error."
                );

            }


            // -----------------------------------------
            // Parse response
            // -----------------------------------------

            const data = await (
                response.json()
            );


            // -----------------------------------------
            // Validate response
            // -----------------------------------------

            if (
                !data
                || !Array.isArray(
                    data.users
                )
            ) {

                throw new Error(
                    "Invalid online data."
                );

            }


            // -----------------------------------------
            // Render
            // -----------------------------------------

            renderOnlineUsers(
                data
            );


        } catch (error) {

            renderError();

        } finally {

            loading = false;

        }

    }


    // =================================================
    // Initial fetch
    // =================================================

    fetchOnlineUsers();


    // =================================================
    // Automatic refresh
    // =================================================

    setInterval(

        fetchOnlineUsers,

        REFRESH_INTERVAL

    );


    // =================================================
    // Refresh when tab becomes visible
    // =================================================

    document.addEventListener(

        "visibilitychange",

        () => {

            if (
                document.visibilityState
                === "visible"
            ) {

                fetchOnlineUsers();

            }

        }

    );


})();