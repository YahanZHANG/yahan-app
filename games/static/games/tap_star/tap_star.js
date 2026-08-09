document.addEventListener("DOMContentLoaded", function () {
    const GAME_DURATION = 30;

    const gameArea = document.getElementById("tap-star-game-area");
    const scoreDisplay = document.getElementById("tap-star-score");
    const timeDisplay = document.getElementById("tap-star-time");

    const readyScreen = document.getElementById("tap-star-ready");
    const resultScreen = document.getElementById("tap-star-result");

    const startButton = document.getElementById("tap-star-start-button");
    const restartButton = document.getElementById("tap-star-restart-button");

    const target = document.getElementById("tap-star-target");

    const finalScore = document.getElementById("tap-star-final-score");
    const resultMessage = document.getElementById("tap-star-result-message");

    let score = 0;
    let remainingTime = GAME_DURATION;
    let timerId = null;
    let gameRunning = false;


    // 必要なHTML要素があるか確認
    if (
        !gameArea ||
        !scoreDisplay ||
        !timeDisplay ||
        !readyScreen ||
        !resultScreen ||
        !startButton ||
        !restartButton ||
        !target ||
        !finalScore ||
        !resultMessage
    ) {
        console.error("Star Tap: 必要なHTML要素が見つからない");
        return;
    }


    function startGame() {
        console.log("Star Tap: game started");

        if (timerId) {
            clearInterval(timerId);
        }

        score = 0;
        remainingTime = GAME_DURATION;
        gameRunning = true;

        scoreDisplay.textContent = "0";
        timeDisplay.textContent = String(GAME_DURATION);

        readyScreen.hidden = true;
        resultScreen.hidden = true;
        target.hidden = false;

        moveTarget();

        timerId = setInterval(function () {
            remainingTime -= 1;

            timeDisplay.textContent = String(remainingTime);

            if (remainingTime <= 0) {
                endGame();
            }
        }, 1000);
    }


    function endGame() {
        gameRunning = false;

        if (timerId) {
            clearInterval(timerId);
            timerId = null;
        }

        target.hidden = true;

        finalScore.textContent = String(score);
        resultMessage.textContent = getResultMessage(score);

        resultScreen.hidden = false;
    }


    function moveTarget() {
        if (!gameRunning) {
            return;
        }

        const areaWidth = gameArea.clientWidth;
        const areaHeight = gameArea.clientHeight;

        const targetWidth = target.offsetWidth || 82;
        const targetHeight = target.offsetHeight || 82;

        const padding = 12;

        const availableWidth =
            Math.max(0, areaWidth - targetWidth - padding * 2);

        const availableHeight =
            Math.max(0, areaHeight - targetHeight - padding * 2);

        const x =
            padding + Math.random() * availableWidth;

        const y =
            padding + Math.random() * availableHeight;

        target.style.left = `${x}px`;
        target.style.top = `${y}px`;

        restartTargetAnimation();
    }


    function restartTargetAnimation() {
        target.style.animation = "none";

        void target.offsetWidth;

        target.style.animation = "";
    }


    function hitTarget(event) {
        event.preventDefault();

        if (!gameRunning) {
            return;
        }

        score += 1;

        scoreDisplay.textContent = String(score);

        moveTarget();
    }


    function getResultMessage(currentScore) {
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


    startButton.addEventListener("click", startGame);

    restartButton.addEventListener("click", startGame);

    target.addEventListener("pointerdown", hitTarget);


    window.addEventListener("resize", function () {
        if (gameRunning) {
            moveTarget();
        }
    });


    console.log("Star Tap: JavaScript loaded");
});