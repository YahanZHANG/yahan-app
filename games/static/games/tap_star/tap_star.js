
document.addEventListener("DOMContentLoaded", function () {

    // =========================================================
    // Configuration
    // =========================================================

    const GAME_DURATION = 30;

    const LEVELS = {
        1: {
            name: "やさしい",
            size: 88,
            fontSize: 52,
            moveInterval: null,
        },
        2: {
            name: "ふつう",
            size: 76,
            fontSize: 44,
            moveInterval: 1500,
        },
        3: {
            name: "むずかしい",
            size: 62,
            fontSize: 35,
            moveInterval: 900,
        },
        4: {
            name: "激ムズ",
            size: 48,
            fontSize: 27,
            moveInterval: 550,
        },
        5: {
            name: "鬼",
            size: 30,
            fontSize: 17,
            moveInterval: 250,
        },
    };

    const PENDING_SCORE_KEY =
        "yapp:tap_star:pending_score";

    const PENDING_SCORE_MAX_AGE =
        30 * 60 * 1000;

    const MAX_SAVED_SCORE = 1_000_000;


    // =========================================================
    // Elements
    // =========================================================

    const page = document.querySelector(
        ".tap-star-page"
    );

    if (!page) {
        return;
    }

    const gameArea = document.getElementById(
        "tap-star-game-area"
    );

    const scoreDisplay = document.getElementById(
        "tap-star-score"
    );

    const timeDisplay = document.getElementById(
        "tap-star-time"
    );

    const currentLevelDisplay = document.getElementById(
        "tap-star-current-level"
    );

    const selectedLevelDisplay = document.getElementById(
        "tap-star-selected-level"
    );

    const levelButtons = [
        ...document.querySelectorAll(
            ".tap-star-level-button"
        ),
    ];

    const readyScreen = document.getElementById(
        "tap-star-ready"
    );

    const resultScreen = document.getElementById(
        "tap-star-result"
    );

    const pauseOverlay = document.getElementById(
        "tap-star-pause-overlay"
    );

    const startButton = document.getElementById(
        "tap-star-start-button"
    );

    const restartButton = document.getElementById(
        "tap-star-restart-button"
    );

    const pauseButton = document.getElementById(
        "tap-star-pause-button"
    );

    const quitButton = document.getElementById(
        "tap-star-quit-button"
    );

    const gameControls = document.getElementById(
        "tap-star-game-controls"
    );

    const target = document.getElementById(
        "tap-star-target"
    );

    const finalScore = document.getElementById(
        "tap-star-final-score"
    );

    const resultLevel = document.getElementById(
        "tap-star-result-level"
    );

    const resultMessage = document.getElementById(
        "tap-star-result-message"
    );

    const rankingList = document.getElementById(
        "tap-star-ranking-list"
    );

    const rankingLevelDisplay = document.getElementById(
        "tap-star-ranking-level"
    );

    const personalBestDisplay = document.getElementById(
        "tap-star-personal-best"
    );

    const saveStatus = document.getElementById(
        "tap-star-save-status"
    );

    const loginScoreButton = document.getElementById(
        "tap-star-login-score-button"
    );


    // =========================================================
    // Authentication / URLs
    // =========================================================

    const scoreSaveUrl =
        page.dataset.scoreUrl;

    const rankingUrl =
        page.dataset.rankingUrl;

    const csrfToken =
        page.dataset.csrfToken;

    const isAuthenticated =
        page.dataset.isAuthenticated === "true";

    const loginUrl =
        page.dataset.loginUrl;


    // =========================================================
    // Game State
    // =========================================================

    let selectedLevel = 1;

    let score = 0;

    let remainingTime = GAME_DURATION;

    let timerId = null;

    let targetMoveTimerId = null;

    let gameRunning = false;

    let isPaused = false;

    let gameSessionId = 0;

    let rankingRequestId = 0;

    let lastFinishedResult = null;


    // =========================================================
    // Helpers
    // =========================================================

    function setSaveStatus(message) {

        if (saveStatus) {
            saveStatus.textContent = message;
        }
    }


    function isValidLevel(level) {

        return (
            Number.isInteger(level)
            && Object.prototype.hasOwnProperty.call(
                LEVELS,
                level
            )
        );
    }


    function updateLoginScoreButton(show) {

        if (!loginScoreButton) {
            return;
        }

        loginScoreButton.hidden =
            isAuthenticated || !show;
    }


    // =========================================================
    // Level Selection
    // =========================================================

    function selectLevel(level) {

        if (!isValidLevel(level)) {
            return;
        }

        if (gameRunning) {
            return;
        }

        selectedLevel = level;

        selectedLevelDisplay.textContent =
            String(selectedLevel);

        currentLevelDisplay.textContent =
            String(selectedLevel);

        levelButtons.forEach(function (button) {

            const buttonLevel =
                Number(button.dataset.level);

            const active =
                buttonLevel === selectedLevel;

            button.classList.toggle(
                "is-active",
                active
            );

            button.setAttribute(
                "aria-pressed",
                String(active)
            );
        });

        void loadRanking(selectedLevel);
    }


    function disableLevelButtons() {

        levelButtons.forEach(function (button) {
            button.disabled = true;
        });
    }


    function enableLevelButtons() {

        levelButtons.forEach(function (button) {
            button.disabled = false;
        });
    }


    // =========================================================
    // Start Game
    // =========================================================

    function startGame() {

        clearGameTimers();

        gameSessionId += 1;

        score = 0;
        remainingTime = GAME_DURATION;

        gameRunning = true;
        isPaused = false;

        scoreDisplay.textContent = "0";

        timeDisplay.textContent =
            String(GAME_DURATION);

        currentLevelDisplay.textContent =
            String(selectedLevel);

        readyScreen.hidden = true;
        resultScreen.hidden = true;
        pauseOverlay.hidden = true;

        target.hidden = false;
        gameControls.hidden = false;

        target.classList.remove("is-paused");

        pauseButton.textContent =
            "⏸ 一時停止";

        updateLoginScoreButton(false);

        setSaveStatus("");

        disableLevelButtons();

        applyLevelSettings();

        moveTarget();

        startTimers();
    }


    // =========================================================
    // Timers
    // =========================================================

    function startTimers() {

        timerId = setInterval(function () {

            if (!gameRunning || isPaused) {
                return;
            }

            remainingTime -= 1;

            timeDisplay.textContent =
                String(Math.max(0, remainingTime));

            if (remainingTime <= 0) {
                endGame();
            }

        }, 1000);

        startTargetMovement();
    }


    function startTargetMovement() {

        const settings =
            LEVELS[selectedLevel];

        if (!settings.moveInterval) {
            return;
        }

        targetMoveTimerId = setInterval(
            function () {

                if (gameRunning && !isPaused) {
                    moveTarget();
                }

            },
            settings.moveInterval
        );
    }


    function clearGameTimers() {

        if (timerId !== null) {

            clearInterval(timerId);
            timerId = null;
        }

        if (targetMoveTimerId !== null) {

            clearInterval(targetMoveTimerId);
            targetMoveTimerId = null;
        }
    }


    // =========================================================
    // Pause / Resume
    // =========================================================

    function togglePause() {

        if (!gameRunning) {
            return;
        }

        if (isPaused) {
            resumeGame();
        } else {
            pauseGame();
        }
    }


    function pauseGame() {

        isPaused = true;

        clearGameTimers();

        pauseOverlay.hidden = false;

        pauseButton.textContent =
            "▶ 再開";

        target.classList.add("is-paused");
    }


    function resumeGame() {

        isPaused = false;

        pauseOverlay.hidden = true;

        pauseButton.textContent =
            "⏸ 一時停止";

        target.classList.remove("is-paused");

        startTimers();
    }


    // =========================================================
    // Quit Game
    // =========================================================

    function quitGame() {

        gameSessionId += 1;

        clearGameTimers();

        gameRunning = false;
        isPaused = false;

        score = 0;
        remainingTime = GAME_DURATION;

        target.hidden = true;

        target.classList.remove("is-paused");

        pauseOverlay.hidden = true;
        resultScreen.hidden = true;
        readyScreen.hidden = false;

        gameControls.hidden = true;

        scoreDisplay.textContent = "0";

        timeDisplay.textContent =
            String(GAME_DURATION);

        pauseButton.textContent =
            "⏸ 一時停止";

        updateLoginScoreButton(false);

        setSaveStatus("");

        enableLevelButtons();
    }


    // =========================================================
    // Difficulty
    // =========================================================

    function applyLevelSettings() {

        const settings =
            LEVELS[selectedLevel];

        target.style.width =
            `${settings.size}px`;

        target.style.height =
            `${settings.size}px`;

        target.style.fontSize =
            `${settings.fontSize}px`;
    }


    // =========================================================
    // Move Star
    // =========================================================

    function moveTarget() {

        if (!gameRunning || isPaused) {
            return;
        }

        const areaWidth =
            gameArea.clientWidth;

        const areaHeight =
            gameArea.clientHeight;

        const targetWidth =
            target.offsetWidth;

        const targetHeight =
            target.offsetHeight;

        const padding = 10;

        const availableWidth = Math.max(
            0,
            areaWidth - targetWidth - padding * 2
        );

        const availableHeight = Math.max(
            0,
            areaHeight - targetHeight - padding * 2
        );

        const x =
            padding + Math.random() * availableWidth;

        const y =
            padding + Math.random() * availableHeight;

        target.style.left =
            `${x}px`;

        target.style.top =
            `${y}px`;

        restartTargetAnimation();
    }


    // =========================================================
    // Hit
    // =========================================================

    function hitTarget(event) {

        event.preventDefault();

        if (!gameRunning || isPaused) {
            return;
        }

        score += 1;

        scoreDisplay.textContent =
            String(score);

        moveTarget();
    }


    function restartTargetAnimation() {

        target.style.animation = "none";

        void target.offsetWidth;

        target.style.animation = "";
    }


    // =========================================================
    // Ranking Rendering
    // =========================================================

    function renderRanking(data, level) {

        if (!data || !Array.isArray(data.entries)) {
            return;
        }

        rankingLevelDisplay.textContent =
            String(level);

        rankingList.replaceChildren();

        if (data.entries.length === 0) {

            const emptyItem =
                document.createElement("li");

            emptyItem.className =
                "tap-star-ranking-empty";

            emptyItem.textContent =
                "まだ記録がない";

            rankingList.appendChild(emptyItem);

        } else {

            data.entries.forEach(function (entry) {

                const item =
                    document.createElement("li");

                if (entry.is_me) {

                    item.classList.add("is-me");
                }

                const position =
                    document.createElement("span");

                position.className =
                    "tap-star-ranking-position";

                position.textContent =
                    String(entry.rank);

                const name =
                    document.createElement("strong");

                name.textContent =
                    String(entry.name);

                const scoreElement =
                    document.createElement("span");

                scoreElement.textContent =
                    `${entry.score} 回`;

                item.append(
                    position,
                    name,
                    scoreElement
                );

                rankingList.appendChild(item);
            });
        }

        personalBestDisplay.textContent =
            data.personal_best == null
            ? "--"
            : String(data.personal_best);
    }


    // =========================================================
    // Ranking API
    // =========================================================

    async function loadRanking(level) {

        const requestId =
            ++rankingRequestId;

        rankingLevelDisplay.textContent =
            String(level);

        personalBestDisplay.textContent = "--";

        rankingList.replaceChildren();

        const loading =
            document.createElement("li");

        loading.className =
            "tap-star-ranking-empty";

        loading.textContent =
            "ランキングを読み込み中…";

        rankingList.appendChild(loading);

        try {

            const response = await fetch(
                `${rankingUrl}?level=${level}`,
                {
                    credentials: "same-origin",
                }
            );

            if (!response.ok) {

                throw new Error(
                    `Ranking failed: ${response.status}`
                );
            }

            const data = await response.json();

            if (
                data.ok
                && selectedLevel === level
                && requestId === rankingRequestId
            ) {

                renderRanking(data, level);
            }

        } catch (error) {

            if (
                selectedLevel === level
                && requestId === rankingRequestId
            ) {

                loading.textContent =
                    "ランキングを取得できませんでした。";
            }

            console.warn(
                "ランキング取得エラー:",
                error
            );
        }
    }


    // =========================================================
    // Score API
    // =========================================================

    async function postGameScore(level, currentScore) {

        const response = await fetch(
            scoreSaveUrl,
            {
                method: "POST",
                credentials: "same-origin",

                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken,
                },

                body: JSON.stringify({
                    game: "tap_star",
                    level: level,
                    score: currentScore,
                }),
            }
        );

        if (!response.ok) {

            throw new Error(
                `Score save failed: ${response.status}`
            );
        }

        const data = await response.json();

        if (!data.ok) {

            throw new Error(
                data.error || "Score save failed"
            );
        }

        return data;
    }


    // =========================================================
    // Submit Score
    // =========================================================

    async function saveScore(level, currentScore, session) {

        // Guests can play but cannot save scores.

        if (!isAuthenticated) {

            setSaveStatus(
                "今回のスコアは未保存です。ログインすると記録できます。"
            );

            return;
        }

        setSaveStatus(
            "スコアを保存中…"
        );

        try {

            const data = await postGameScore(
                level,
                currentScore
            );

            if (
                selectedLevel === level
                && gameSessionId === session
            ) {

                rankingRequestId += 1;

                renderRanking(data, level);

                setSaveStatus(
                    data.is_new_best
                    ? "🎉 自己ベスト更新！"
                    : "スコアを保存したよ。"
                );
            }

        } catch (error) {

            if (
                selectedLevel === level
                && gameSessionId === session
            ) {

                setSaveStatus(
                    "スコアを保存できませんでした。"
                );
            }

            console.warn(
                "スコア保存エラー:",
                error
            );
        }
    }


    // =========================================================
    // Pending Score Storage
    // =========================================================

    function clearPendingScore() {

        try {

            sessionStorage.removeItem(
                PENDING_SCORE_KEY
            );

        } catch (error) {

            console.warn(
                "一時スコア削除エラー:",
                error
            );
        }
    }


    function savePendingScore() {

        const pending = {
            game: "tap_star",
            level: lastFinishedResult?.level ?? selectedLevel,
            score: lastFinishedResult?.score ?? score,
            createdAt: Date.now(),
        };

        try {

            sessionStorage.setItem(
                PENDING_SCORE_KEY,
                JSON.stringify(pending)
            );

            return true;

        } catch (error) {

            console.warn(
                "スコアを一時保存できませんでした。",
                error
            );

            return false;
        }
    }


    function readPendingScore() {

        let raw = null;

        try {

            raw = sessionStorage.getItem(
                PENDING_SCORE_KEY
            );

        } catch (error) {

            return null;
        }

        if (!raw) {
            return null;
        }

        try {

            const pending = JSON.parse(raw);

            const now = Date.now();

            const isValid = (
                pending !== null
                && typeof pending === "object"
                && pending.game === "tap_star"
                && isValidLevel(pending.level)
                && Number.isInteger(pending.score)
                && pending.score >= 0
                && pending.score <= MAX_SAVED_SCORE
                && Number.isFinite(pending.createdAt)
                && pending.createdAt <= now
                && now - pending.createdAt
                    <= PENDING_SCORE_MAX_AGE
            );

            if (!isValid) {

                clearPendingScore();
                return null;
            }

            return pending;

        } catch (error) {

            clearPendingScore();
            return null;
        }
    }


    // =========================================================
    // Redirect to Login
    // =========================================================

    function getLoginRedirectUrl() {

        const url = new URL(
            loginUrl,
            window.location.origin
        );

        url.searchParams.set(
            "next",
            window.location.pathname
                + window.location.search
        );

        return url.toString();
    }


    function goToLoginWithScore(event) {

        event.preventDefault();

        if (isAuthenticated) {
            return;
        }

        if (!loginUrl) {

            console.warn(
                "ログインURLが設定されていません。"
            );

            return;
        }

        const stored = savePendingScore();

        if (!stored) {

            setSaveStatus(
                "点数を一時保存できませんでした。ブラウザの設定を確認してください。"
            );

            return;
        }

        window.location.assign(
            getLoginRedirectUrl()
        );
    }


    // =========================================================
    // Restore Score After Login
    // =========================================================

    async function restorePendingScoreAfterLogin() {

        if (!isAuthenticated) {
            return;
        }

        const pending = readPendingScore();

        if (!pending) {
            return;
        }

        // Remove first to prevent duplicate submissions.
        clearPendingScore();

        setSaveStatus(
            "ログイン前のスコアを記録中…"
        );

        try {

            const data = await postGameScore(
                pending.level,
                pending.score
            );

            if (selectedLevel === pending.level) {

                rankingRequestId += 1;

                renderRanking(
                    data,
                    pending.level
                );

            } else {

                await loadRanking(selectedLevel);
            }

            setSaveStatus(
                data.is_new_best
                ? `🎉 LEVEL ${pending.level} の自己ベストを更新したよ！`
                : `LEVEL ${pending.level} のスコアを記録したよ。`
            );

        } catch (error) {

            try {

                sessionStorage.setItem(
                    PENDING_SCORE_KEY,
                    JSON.stringify(pending)
                );

            } catch (storageError) {

                console.warn(
                    "一時スコアを復元できませんでした。",
                    storageError
                );
            }

            setSaveStatus(
                "ログインできましたが、点数を保存できませんでした。ページを再読み込みしてください。"
            );

            console.warn(
                "ログイン前スコア保存エラー:",
                error
            );
        }
    }


    // =========================================================
    // End Game
    // =========================================================

    function endGame() {

        if (!gameRunning) {
            return;
        }

        gameRunning = false;
        isPaused = false;

        clearGameTimers();

        target.hidden = true;

        pauseOverlay.hidden = true;

        gameControls.hidden = true;

        finalScore.textContent =
            String(score);

        resultLevel.textContent =
            String(selectedLevel);

        resultMessage.textContent =
            getResultMessage(
                selectedLevel,
                score
            );

        resultScreen.hidden = false;

        enableLevelButtons();

        updateLoginScoreButton(
            !isAuthenticated
        );

        const finishedLevel = selectedLevel;
        const finishedScore = score;
        const finishedSession = gameSessionId;

        lastFinishedResult = {
            level: finishedLevel,
            score: finishedScore,
        };

        void saveScore(
            finishedLevel,
            finishedScore,
            finishedSession
        );
    }


    // =========================================================
    // Result Message
    // =========================================================

    function getResultMessage(level, currentScore) {

        if (level === 5) {

            if (currentScore >= 20) {

                return "え、速すぎる。LEVEL 5を完全攻略！";
            }

            if (currentScore >= 10) {

                return "すごい！鬼レベルで二桁はかなり強い！";
            }

            if (currentScore >= 5) {

                return "LEVEL 5でこれはかなりすごい！";
            }

            if (currentScore >= 1) {

                return "捕まえた！LEVEL 5は本気で鬼難易度。";
            }

            return "0回でも正常。LEVEL 5はそういうゲーム。";
        }

        if (level === 4) {

            if (currentScore >= 30) {

                return "激ムズなのに速すぎる！";
            }

            if (currentScore >= 15) {

                return "かなりいい記録！";
            }
        }

        if (currentScore >= 50) {

            return "すごすぎる！スタータップマスター！";
        }

        if (currentScore >= 35) {

            return "めっちゃ速い！すごい！";
        }

        if (currentScore >= 20) {

            return "ナイス！かなりいい記録！";
        }

        if (currentScore >= 10) {

            return "いい感じ！もう一回挑戦してみよう！";
        }

        return "次はもっといける！もう一度チャレンジ！";
    }


    // =========================================================
    // Events
    // =========================================================

    levelButtons.forEach(function (button) {

        button.addEventListener(
            "click",
            function () {

                selectLevel(
                    Number(button.dataset.level)
                );
            }
        );
    });


    startButton.addEventListener(
        "click",
        startGame
    );


    restartButton.addEventListener(
        "click",
        startGame
    );


    pauseButton.addEventListener(
        "click",
        togglePause
    );


    quitButton.addEventListener(
        "click",
        quitGame
    );


    target.addEventListener(
        "pointerdown",
        hitTarget
    );


    if (loginScoreButton) {

        loginScoreButton.addEventListener(
            "click",
            goToLoginWithScore
        );
    }


    window.addEventListener(
        "resize",
        function () {

            if (gameRunning && !isPaused) {
                moveTarget();
            }
        }
    );


    // =========================================================
    // Initial State
    // =========================================================

    selectLevel(1);

    void restorePendingScoreAfterLogin();

});
