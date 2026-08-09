document.addEventListener("DOMContentLoaded", function () {

    const GAME_DURATION = 30;


    // ========================================
    // Level Settings
    // ========================================

    const LEVELS = {
        1: {
            name: "やさしい",
            size: 88,
            fontSize: 52,
            moveInterval: null
        },

        2: {
            name: "ふつう",
            size: 76,
            fontSize: 44,
            moveInterval: 1500
        },

        3: {
            name: "むずかしい",
            size: 62,
            fontSize: 35,
            moveInterval: 900
        },

        4: {
            name: "激ムズ",
            size: 48,
            fontSize: 27,
            moveInterval: 550
        },

        5: {
            name: "鬼",
            size: 30,
            fontSize: 17,
            moveInterval: 250
        }
    };


    // ========================================
    // Elements
    // ========================================

    const gameArea =
        document.getElementById("tap-star-game-area");

    const scoreDisplay =
        document.getElementById("tap-star-score");

    const timeDisplay =
        document.getElementById("tap-star-time");

    const currentLevelDisplay =
        document.getElementById("tap-star-current-level");

    const selectedLevelDisplay =
        document.getElementById("tap-star-selected-level");

    const levelButtons =
        document.querySelectorAll(".tap-star-level-button");

    const readyScreen =
        document.getElementById("tap-star-ready");

    const resultScreen =
        document.getElementById("tap-star-result");

    const pauseOverlay =
        document.getElementById("tap-star-pause-overlay");

    const startButton =
        document.getElementById("tap-star-start-button");

    const restartButton =
        document.getElementById("tap-star-restart-button");

    const pauseButton =
        document.getElementById("tap-star-pause-button");

    const quitButton =
        document.getElementById("tap-star-quit-button");

    const gameControls =
        document.getElementById("tap-star-game-controls");

    const target =
        document.getElementById("tap-star-target");

    const finalScore =
        document.getElementById("tap-star-final-score");

    const resultLevel =
        document.getElementById("tap-star-result-level");

    const resultMessage =
        document.getElementById("tap-star-result-message");


    // ========================================
    // State
    // ========================================

    let selectedLevel = 1;
    let score = 0;
    let remainingTime = GAME_DURATION;

    let timerId = null;
    let targetMoveTimerId = null;

    let gameRunning = false;
    let isPaused = false;


    // ========================================
    // Level Selection
    // ========================================

    function selectLevel(level) {

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

            button.classList.toggle(
                "is-active",
                buttonLevel === selectedLevel
            );

        });

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


    levelButtons.forEach(function (button) {

        button.addEventListener("click", function () {

            const level =
                Number(button.dataset.level);

            selectLevel(level);

        });

    });


    // ========================================
    // Start Game
    // ========================================

    function startGame() {

        clearGameTimers();

        score = 0;
        remainingTime = GAME_DURATION;

        gameRunning = true;
        isPaused = false;

        scoreDisplay.textContent = "0";
        timeDisplay.textContent = String(GAME_DURATION);

        currentLevelDisplay.textContent =
            String(selectedLevel);

        readyScreen.hidden = true;
        resultScreen.hidden = true;
        pauseOverlay.hidden = true;

        target.hidden = false;
        gameControls.hidden = false;

        pauseButton.textContent = "⏸ 一時停止";

        disableLevelButtons();

        applyLevelSettings();

        moveTarget();

        startTimers();

    }


    // ========================================
    // Timers
    // ========================================

    function startTimers() {

        timerId = setInterval(function () {

            if (!gameRunning || isPaused) {
                return;
            }

            remainingTime -= 1;

            timeDisplay.textContent =
                String(remainingTime);

            if (remainingTime <= 0) {
                endGame();
            }

        }, 1000);


        startTargetMovement();

    }


    function startTargetMovement() {

        const settings = LEVELS[selectedLevel];

        if (!settings.moveInterval) {
            return;
        }

        targetMoveTimerId =
            setInterval(function () {

                if (gameRunning && !isPaused) {
                    moveTarget();
                }

            }, settings.moveInterval);

    }


    function clearGameTimers() {

        if (timerId) {
            clearInterval(timerId);
            timerId = null;
        }

        if (targetMoveTimerId) {
            clearInterval(targetMoveTimerId);
            targetMoveTimerId = null;
        }

    }


    // ========================================
    // Pause / Resume
    // ========================================

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

        pauseButton.textContent = "▶ 再開";

        target.classList.add("is-paused");

    }


    function resumeGame() {

        isPaused = false;

        pauseOverlay.hidden = true;

        pauseButton.textContent = "⏸ 一時停止";

        target.classList.remove("is-paused");

        startTimers();

    }


    // ========================================
    // Quit Game
    // ========================================

    function quitGame() {

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

        enableLevelButtons();

    }


    // ========================================
    // Difficulty
    // ========================================

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


    // ========================================
    // Move Star
    // ========================================

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

        const availableWidth =
            Math.max(
                0,
                areaWidth -
                targetWidth -
                padding * 2
            );

        const availableHeight =
            Math.max(
                0,
                areaHeight -
                targetHeight -
                padding * 2
            );

        const x =
            padding +
            Math.random() * availableWidth;

        const y =
            padding +
            Math.random() * availableHeight;

        target.style.left =
            `${x}px`;

        target.style.top =
            `${y}px`;

        restartTargetAnimation();

    }


    // ========================================
    // Hit
    // ========================================

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


    // ========================================
    // End Game
    // ========================================

    function endGame() {

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

    }


    // ========================================
    // Result Message
    // ========================================

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


    // ========================================
    // Events
    // ========================================

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


    window.addEventListener(
        "resize",
        function () {

            if (gameRunning && !isPaused) {
                moveTarget();
            }

        }
    );


    // ========================================
    // Initial State
    // ========================================

    selectLevel(1);

});