/* =====================================================
   Yahan App Heartbeat
   ===================================================== */

(() => {

    "use strict";


    // =================================================
    // Configuration
    // =================================================

    const HEARTBEAT_INTERVAL = 5000;

    const TAB_STORAGE_KEY =
        "yahan_heartbeat_tab_id";


    const script = document.currentScript;

    if (!script) {
        return;
    }


    const heartbeatUrl =
        script.dataset.heartbeatUrl;

    const csrfToken =
        script.dataset.csrfToken;


    if (!heartbeatUrl || !csrfToken) {
        return;
    }


    // =================================================
    // App detection
    // =================================================

    function getAppKey(path) {

        // ---------------------------------------------
        // Portal
        // ---------------------------------------------

        if (
            path === "/" ||
            path === "/apps/manage/"
        ) {
            return "portal";
        }


        // ---------------------------------------------
        // Application paths
        // ---------------------------------------------

        const appPaths = {

            "/news": "news",

            "/feeding": "feeding",

            "/vaccination": "vaccination",

            "/recipes": "recipes",

            "/games": "games",

            "/colorcheck": "colorcheck",

        };


        for (
            const [prefix, appKey]
            of Object.entries(appPaths)
        ) {

            if (
                path === prefix ||
                path.startsWith(prefix + "/")
            ) {

                return appKey;

            }

        }


        return null;

    }


    // =================================================
    // Current app
    // =================================================

    const appKey = getAppKey(
        window.location.pathname
    );


    // 対象外のページでは何もしない

    if (!appKey) {
        return;
    }


    // =================================================
    // Tab ID
    // =================================================

    function createTabId() {

        return crypto.randomUUID();

    }


    function getTabId() {

        try {

            let tabId = sessionStorage.getItem(
                TAB_STORAGE_KEY
            );


            if (!tabId) {

                tabId = createTabId();

                sessionStorage.setItem(
                    TAB_STORAGE_KEY,
                    tabId
                );

            }


            return tabId;

        } catch (error) {

            // sessionStorageが利用できない場合

            return createTabId();

        }

    }


    const tabId = getTabId();


    // =================================================
    // Heartbeat
    // =================================================

    let sending = false;


    async function sendHeartbeat() {

        // ---------------------------------------------
        // Hidden tab
        // ---------------------------------------------

        if (
            document.visibilityState !== "visible"
        ) {
            return;
        }


        // ---------------------------------------------
        // Prevent overlapping requests
        // ---------------------------------------------

        if (sending) {
            return;
        }


        sending = true;


        try {

            const body = new URLSearchParams({

                app_key: appKey,

                tab_id: tabId,

            });


            await fetch(
                heartbeatUrl,
                {

                    method: "POST",

                    credentials: "same-origin",

                    headers: {

                        "X-CSRFToken": csrfToken,

                        "Content-Type":
                            "application/x-www-form-urlencoded;charset=UTF-8",

                    },

                    body: body.toString(),

                    cache: "no-store",

                }
            );

        } catch (error) {

            // 通信失敗時も通常のアプリ利用は
            // 妨げない。

        } finally {

            sending = false;

        }

    }


    // =================================================
    // Start heartbeat
    // =================================================

    sendHeartbeat();


    setInterval(

        sendHeartbeat,

        HEARTBEAT_INTERVAL

    );


    // =================================================
    // Visibility change
    // =================================================

    document.addEventListener(

        "visibilitychange",

        () => {

            if (
                document.visibilityState === "visible"
            ) {

                sendHeartbeat();

            }

        }

    );


    // =================================================
    // Back-forward cache
    // =================================================

    window.addEventListener(

        "pageshow",

        (event) => {

            if (event.persisted) {

                sendHeartbeat();

            }

        }

    );


})();