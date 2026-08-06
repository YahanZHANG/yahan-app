import { GAME_CONFIG } from "./config.js";
import { BRICK_TYPES, LEVELS } from "./levels.js";
import {
    POWERUP_TYPES,
    POWERUP_CONFIG,
    createPowerup,
    getPowerupSymbol,
} from "./powerups.js";

const powerupStatus = document.getElementById(
    "powerup-status",
);

const powerupDisplay = document.getElementById(
    "powerup-display",
);

const canvas = document.getElementById("game-canvas");
const context = canvas.getContext("2d");

const scoreDisplay = document.getElementById("score-display");
const livesDisplay = document.getElementById("lives-display");
const stageDisplay = document.getElementById("stage-display");

const overlay = document.getElementById("game-overlay");
const overlayTitle = document.getElementById("overlay-title");
const overlayMessage = document.getElementById("overlay-message");
const startButton = document.getElementById("start-button");

const pauseButton = document.getElementById("pause-button");
const moveLeftButton = document.getElementById("move-left-button");
const moveRightButton = document.getElementById("move-right-button");

canvas.width = GAME_CONFIG.canvasWidth;
canvas.height = GAME_CONFIG.canvasHeight;

const state = {
    score: 0,
    lives: GAME_CONFIG.lives,
    levelIndex: 0,

    running: false,
    paused: false,
    animationFrameId: null,

    moveLeft: false,
    moveRight: false,

    powerups: [],

    effects: {
        fireballActive: false,
        fireballEndsAt: 0,
        fireballPausedRemaining: 0,

        widePaddleActive: false,
        widePaddleEndsAt: 0,
        widePaddlePausedRemaining: 0,
    },

    paddle: {
        x: 0,
        y: 0,
        width: GAME_CONFIG.paddle.width,
        normalWidth: GAME_CONFIG.paddle.width,
        height: GAME_CONFIG.paddle.height,
        speed: GAME_CONFIG.paddle.speed,
    },

    ball: {
        x: 0,
        y: 0,
        radius: GAME_CONFIG.ball.radius,
        dx: 0,
        dy: 0,
    },

    bricks: [],
};

function activateWidePaddle() {
    const oldCenter = (
        state.paddle.x
        + state.paddle.width / 2
    );

    state.effects.widePaddleActive = true;

    state.effects.widePaddleEndsAt = (
        performance.now()
        + POWERUP_CONFIG.widePaddleDuration
    );

    state.paddle.width = (
        state.paddle.normalWidth
        * POWERUP_CONFIG.widePaddleMultiplier
    );

    state.paddle.x = (
        oldCenter
        - state.paddle.width / 2
    );

    keepPaddleInsideCanvas();
}


function deactivateWidePaddle() {
    const oldCenter = (
        state.paddle.x
        + state.paddle.width / 2
    );

    state.effects.widePaddleActive = false;
    state.effects.widePaddleEndsAt = 0;
    state.effects.widePaddlePausedRemaining = 0;

    state.paddle.width = state.paddle.normalWidth;

    state.paddle.x = (
        oldCenter
        - state.paddle.width / 2
    );

    keepPaddleInsideCanvas();
}


function updateWidePaddleEffect(currentTime) {
    if (!state.effects.widePaddleActive) {
        return;
    }

    const remainingMilliseconds = (
        state.effects.widePaddleEndsAt
        - currentTime
    );

    if (remainingMilliseconds <= 0) {
        deactivateWidePaddle();
    }
}

function getCurrentLevel() {
    return LEVELS[state.levelIndex];
}


function resetPaddle() {
    state.paddle.x = (
        canvas.width - state.paddle.width
    ) / 2;

    state.paddle.y = (
        canvas.height
        - GAME_CONFIG.paddle.bottomMargin
        - state.paddle.height
    );
}


function resetBall() {
    const level = getCurrentLevel();
    const speed = level.ballSpeed;

    state.ball.x = canvas.width / 2;
    state.ball.y = state.paddle.y - state.ball.radius - 4;

    state.ball.dx = speed * 0.75;
    state.ball.dy = -speed;
}


function createBricks() {
    const level = getCurrentLevel();
    const layout = level.layout;

    const columnCount = layout[0].length;
    const brickWidth = GAME_CONFIG.brick.width;
    const brickHeight = GAME_CONFIG.brick.height;
    const gap = GAME_CONFIG.brick.gap;

    const totalWidth = (
        columnCount * brickWidth
        + (columnCount - 1) * gap
    );

    const startX = (canvas.width - totalWidth) / 2;
    const startY = GAME_CONFIG.brick.topMargin;

    state.bricks = [];

    layout.forEach((row, rowIndex) => {
        row.forEach((type, columnIndex) => {
            if (type === BRICK_TYPES.EMPTY) {
                return;
            }

            const powerupKey = `${rowIndex}-${columnIndex}`;

            state.bricks.push({
                x: startX + columnIndex * (brickWidth + gap),
                y: startY + rowIndex * (brickHeight + gap),
                width: brickWidth,
                height: brickHeight,
                type,
                hitPoints: type === BRICK_TYPES.STRONG ? 2 : 1,
                destroyed: false,
                powerupType: level.powerups?.[powerupKey] ?? null,
            });
        });
    });
}


function initialiseLevel() {
    state.powerups = [];

    deactivateFireball();
    deactivateWidePaddle();

    resetPaddle();
    resetBall();
    createBricks();
    updateStatus();
}


function updateStatus() {
    scoreDisplay.textContent = state.score;
    livesDisplay.textContent = state.lives;
    stageDisplay.textContent = state.levelIndex + 1;
}


function activateFireball() {
    state.effects.fireballActive = true;

    state.effects.fireballEndsAt = (
        performance.now()
        + POWERUP_CONFIG.fireballDuration
    );

    powerupStatus.classList.remove("is-hidden");
}


function deactivateFireball() {
    state.effects.fireballActive = false;
    state.effects.fireballEndsAt = 0;

    powerupStatus.classList.add("is-hidden");
}


function updateFireballEffect(currentTime) {
    if (!state.effects.fireballActive) {
        return;
    }

    const remainingMilliseconds = (
        state.effects.fireballEndsAt - currentTime
    );

    if (remainingMilliseconds <= 0) {
        deactivateFireball();
        return;
    }

    const remainingSeconds = (
        remainingMilliseconds / 1000
    ).toFixed(1);

    powerupDisplay.textContent = (
        `🔥 ${remainingSeconds}`
    );
}

function drawBackground() {
    const gradient = context.createLinearGradient(
        0,
        0,
        0,
        canvas.height,
    );

    gradient.addColorStop(0, "#1f2742");
    gradient.addColorStop(1, "#101523");

    context.fillStyle = gradient;
    context.fillRect(0, 0, canvas.width, canvas.height);
}


function drawPaddle() {
    context.save();

    if (state.effects.widePaddleActive) {
        context.fillStyle = "#8ff0d0";
        context.shadowBlur = 18;
        context.shadowColor = "rgba(100, 255, 210, 0.9)";
    } else {
        context.fillStyle = "#f0f3ff";
        context.shadowBlur = 12;
        context.shadowColor = "rgba(150, 170, 255, 0.75)";
    }

    context.beginPath();
    context.roundRect(
        state.paddle.x,
        state.paddle.y,
        state.paddle.width,
        state.paddle.height,
        8,
    );
    context.fill();

    context.restore();
}


function drawBall() {
    context.save();

    if (state.effects.fireballActive) {
        const gradient = context.createRadialGradient(
            state.ball.x,
            state.ball.y,
            1,
            state.ball.x,
            state.ball.y,
            state.ball.radius * 2.4,
        );

        gradient.addColorStop(0, "#fff8aa");
        gradient.addColorStop(0.35, "#ffcf4a");
        gradient.addColorStop(0.7, "#ff5b2e");
        gradient.addColorStop(1, "rgba(255, 70, 20, 0)");

        context.fillStyle = gradient;
        context.shadowBlur = 24;
        context.shadowColor = "#ff5a1f";

        context.beginPath();
        context.arc(
            state.ball.x,
            state.ball.y,
            state.ball.radius * 2.4,
            0,
            Math.PI * 2,
        );
        context.fill();

        context.fillStyle = "#fff7c7";

        context.beginPath();
        context.arc(
            state.ball.x,
            state.ball.y,
            state.ball.radius,
            0,
            Math.PI * 2,
        );
        context.fill();
    } else {
        context.fillStyle = "#ffffff";
        context.shadowBlur = 14;
        context.shadowColor = "#b7c4ff";

        context.beginPath();
        context.arc(
            state.ball.x,
            state.ball.y,
            state.ball.radius,
            0,
            Math.PI * 2,
        );
        context.fill();
    }

    context.restore();
}

function getBrickColor(brick, index) {
    const colors = [
        "#ff7f8f",
        "#ffa45c",
        "#f5d76e",
        "#79d6a8",
        "#72b7f2",
        "#a68cf0",
    ];

    if (brick.type === BRICK_TYPES.STRONG) {
        return "#d889ff";
    }

    if (brick.type === BRICK_TYPES.UNBREAKABLE) {
        return "#6f778c";
    }

    if (brick.type === BRICK_TYPES.POWERUP) {
        return "#ffca55";
    }

    return colors[index % colors.length];
}


function drawBricks() {
    state.bricks.forEach((brick, index) => {
        if (brick.destroyed) {
            return;
        }

        context.save();

        context.fillStyle = getBrickColor(brick, index);
        context.shadowBlur = 7;
        context.shadowColor = "rgba(0, 0, 0, 0.25)";

        context.beginPath();
        context.roundRect(
            brick.x,
            brick.y,
            brick.width,
            brick.height,
            6,
        );
        context.fill();

        if (
            brick.type === BRICK_TYPES.STRONG
            && brick.hitPoints === 2
        ) {
            context.strokeStyle = "rgba(255, 255, 255, 0.9)";
            context.lineWidth = 3;

            context.beginPath();
            context.roundRect(
                brick.x + 3,
                brick.y + 3,
                brick.width - 6,
                brick.height - 6,
                4,
            );
            context.stroke();
        }

        context.restore();
    });
}

function drawPowerups() {
    state.powerups.forEach((powerup) => {
        if (powerup.collected) {
            return;
        }

        context.save();

        context.fillStyle = "rgba(255, 255, 255, 0.95)";
        context.shadowBlur = 12;
        context.shadowColor = "#ff8a45";

        context.beginPath();
        context.roundRect(
            powerup.x,
            powerup.y,
            powerup.width,
            powerup.height,
            10,
        );
        context.fill();

        context.shadowBlur = 0;
        context.font = "22px sans-serif";
        context.textAlign = "center";
        context.textBaseline = "middle";

        context.fillText(
            getPowerupSymbol(powerup.type),
            powerup.x + powerup.width / 2,
            powerup.y + powerup.height / 2 + 1,
        );

        context.restore();
    });
}

function draw() {
    drawBackground();
    drawBricks();
    drawPowerups();
    drawPaddle();
    drawBall();
}

function keepPaddleInsideCanvas() {
    if (state.paddle.x < 0) {
        state.paddle.x = 0;
    }

    const maximumX = (
        canvas.width
        - state.paddle.width
    );

    if (state.paddle.x > maximumX) {
        state.paddle.x = maximumX;
    }
}

function movePaddle() {
    if (state.moveLeft) {
        state.paddle.x -= state.paddle.speed;
    }

    if (state.moveRight) {
        state.paddle.x += state.paddle.speed;
    }

    keepPaddleInsideCanvas();
}


function moveBall() {
    state.ball.x += state.ball.dx;
    state.ball.y += state.ball.dy;
}

function movePowerups() {
    state.powerups.forEach((powerup) => {
        if (powerup.collected) {
            return;
        }

        powerup.y += powerup.speed;
    });

    state.powerups = state.powerups.filter((powerup) => {
        return (
            !powerup.collected
            && powerup.y < canvas.height + powerup.height
        );
    });
}

function rectanglesOverlap(first, second) {
    return (
        first.x < second.x + second.width
        && first.x + first.width > second.x
        && first.y < second.y + second.height
        && first.y + first.height > second.y
    );
}


function handlePowerupCollisions() {
    state.powerups.forEach((powerup) => {
        if (powerup.collected) {
            return;
        }

        if (!rectanglesOverlap(powerup, state.paddle)) {
            return;
        }

        powerup.collected = true;

        if (powerup.type === POWERUP_TYPES.FIREBALL) {
            activateFireball();
            state.score += 250;
        }

        if (powerup.type === POWERUP_TYPES.WIDE_PADDLE) {
            activateWidePaddle();
            state.score += 200;
        }

        updateStatus();
    });
}


function handleWallCollisions() {
    const ball = state.ball;

    if (
        ball.x - ball.radius <= 0
        && ball.dx < 0
    ) {
        ball.x = ball.radius;
        ball.dx *= -1;
    }

    if (
        ball.x + ball.radius >= canvas.width
        && ball.dx > 0
    ) {
        ball.x = canvas.width - ball.radius;
        ball.dx *= -1;
    }

    if (
        ball.y - ball.radius <= 0
        && ball.dy < 0
    ) {
        ball.y = ball.radius;
        ball.dy *= -1;
    }
}


function handlePaddleCollision() {
    const ball = state.ball;
    const paddle = state.paddle;

    const ballBottom = ball.y + ball.radius;
    const ballTop = ball.y - ball.radius;
    const ballRight = ball.x + ball.radius;
    const ballLeft = ball.x - ball.radius;

    const touchesPaddle = (
        ballBottom >= paddle.y
        && ballTop <= paddle.y + paddle.height
        && ballRight >= paddle.x
        && ballLeft <= paddle.x + paddle.width
        && ball.dy > 0
    );

    if (!touchesPaddle) {
        return;
    }

    ball.y = paddle.y - ball.radius;

    const paddleCenter = paddle.x + paddle.width / 2;
    const hitPosition = (
        ball.x - paddleCenter
    ) / (paddle.width / 2);

    const speed = Math.sqrt(
        ball.dx * ball.dx + ball.dy * ball.dy
    );

    ball.dx = speed * hitPosition;
    ball.dy = -Math.abs(
        Math.sqrt(
            Math.max(
                1,
                speed * speed - ball.dx * ball.dx,
            ),
        ),
    );
}


function circleTouchesRectangle(ball, rectangle) {
    const nearestX = Math.max(
        rectangle.x,
        Math.min(ball.x, rectangle.x + rectangle.width),
    );

    const nearestY = Math.max(
        rectangle.y,
        Math.min(ball.y, rectangle.y + rectangle.height),
    );

    const distanceX = ball.x - nearestX;
    const distanceY = ball.y - nearestY;

    return (
        distanceX * distanceX + distanceY * distanceY
        <= ball.radius * ball.radius
    );
}


function handleBrickCollisions() {
    for (const brick of state.bricks) {
        if (brick.destroyed) {
            continue;
        }

        if (!circleTouchesRectangle(state.ball, brick)) {
            continue;
        }

        if (brick.type !== BRICK_TYPES.UNBREAKABLE) {
            if (state.effects.fireballActive) {
                brick.hitPoints = 0;
            } else {
                brick.hitPoints -= 1;
            }

            if (brick.hitPoints <= 0) {
                brick.destroyed = true;
                state.score += 100;

                if (
                    brick.type === BRICK_TYPES.POWERUP
                    && brick.powerupType
                ) {
                    const powerup = createPowerup(
                        brick.powerupType,
                        (
                            brick.x
                            + brick.width / 2
                            - POWERUP_CONFIG.width / 2
                        ),
                        brick.y,
                    );

                    state.powerups.push(powerup);
                }

                updateStatus();
            }
        }

        if (!state.effects.fireballActive) {
            state.ball.dy *= -1;
            break;
        }
    }
}


function getRemainingBreakableBricks() {
    return state.bricks.filter((brick) => {
        return (
            !brick.destroyed
            && brick.type !== BRICK_TYPES.UNBREAKABLE
        );
    });
}


function checkStageClear() {
    const remaining = getRemainingBreakableBricks();

    if (remaining.length > 0) {
        return false;
    }

    state.running = false;
    cancelAnimationFrame(state.animationFrameId);

    const currentLevel = getCurrentLevel();
    const nextLevelExists = (
        state.levelIndex < LEVELS.length - 1
    );

    if (nextLevelExists) {
        showOverlay(
            `ステージ${currentLevel.number}クリア！`,
            `次は「${LEVELS[state.levelIndex + 1].name}」。`,
            "次のステージ",
        );

        startButton.dataset.action = "next-level";
    } else {
        showOverlay(
            "全ステージクリア！",
            `最終スコアは${state.score}点。`,
            "最初から",
        );

        startButton.dataset.action = "restart";
    }

    return true;
}


function handleBallLoss() {
    if (
        state.ball.y - state.ball.radius
        <= canvas.height
    ) {
        return;
    }

    state.lives -= 1;
    updateStatus();

    if (state.lives <= 0) {
        state.running = false;
        startButton.dataset.action = "restart";

        showOverlay(
            "ゲームオーバー",
            `最終スコアは${state.score}点。`,
            "最初から",
        );

        return;
    }

    state.running = false;
    resetPaddle();
    resetBall();
    draw();

    startButton.dataset.action = "continue";

    showOverlay(
        "ボールを落とした！",
        `残り${state.lives}回。`,
        "続ける",
    );
}


function gameLoop() {
    if (!state.running || state.paused) {
        return;
    }

    movePaddle();
    moveBall();
    movePowerups();

    handleWallCollisions();
    handlePaddleCollision();
    handleBrickCollisions();
    handlePowerupCollisions();

    const currentTime = performance.now();

    updateFireballEffect(currentTime);
    updateWidePaddleEffect(currentTime);

    if (checkStageClear()) {
        draw();
        return;
    }

    handleBallLoss();
    draw();

    if (state.running) {
        state.animationFrameId = requestAnimationFrame(
            gameLoop,
        );
    }
}


function hideOverlay() {
    overlay.classList.add("is-hidden");
}


function showOverlay(title, message, buttonText) {
    overlayTitle.textContent = title;
    overlayMessage.textContent = message;
    startButton.textContent = buttonText;
    overlay.classList.remove("is-hidden");
}


function startOrContinueGame() {
    const action = startButton.dataset.action;

    if (action === "next-level") {
        state.levelIndex += 1;
        initialiseLevel();
    }

    if (
        action === "restart"
        || state.lives <= 0
    ) {
        state.score = 0;
        state.lives = GAME_CONFIG.lives;
        state.levelIndex = 0;

        initialiseLevel();
    }

    startButton.dataset.action = "";

    // 中央の「再開」ボタンを押したとき、
    // 一時停止前のパワーアップ残り時間を復元する
    const currentTime = performance.now();

    if (
        state.effects.fireballActive
        && state.effects.fireballPausedRemaining > 0
    ) {
        state.effects.fireballEndsAt = (
            currentTime
            + state.effects.fireballPausedRemaining
        );

        state.effects.fireballPausedRemaining = 0;
    }

    if (
        state.effects.widePaddleActive
        && state.effects.widePaddlePausedRemaining > 0
    ) {
        state.effects.widePaddleEndsAt = (
            currentTime
            + state.effects.widePaddlePausedRemaining
        );

        state.effects.widePaddlePausedRemaining = 0;
    }

    hideOverlay();

    state.paused = false;
    state.running = true;
    pauseButton.textContent = "一時停止";

    cancelAnimationFrame(state.animationFrameId);

    state.animationFrameId = requestAnimationFrame(
        gameLoop,
    );
}



function togglePause() {
    if (!state.running && !state.paused) {
        return;
    }

    state.paused = !state.paused;

    // 一時停止に入る
    if (state.paused) {
        const currentTime = performance.now();

        if (state.effects.fireballActive) {
            state.effects.fireballPausedRemaining = Math.max(
                0,
                state.effects.fireballEndsAt - currentTime,
            );
        }

        if (state.effects.widePaddleActive) {
            state.effects.widePaddlePausedRemaining = Math.max(
                0,
                state.effects.widePaddleEndsAt - currentTime,
            );
        }

        pauseButton.textContent = "再開";

        showOverlay(
            "一時停止",
            "準備ができたら再開しよう。",
            "再開",
        );

        return;
    }

    // 下の「一時停止／再開」ボタンで再開する
    const currentTime = performance.now();

    if (
        state.effects.fireballActive
        && state.effects.fireballPausedRemaining > 0
    ) {
        state.effects.fireballEndsAt = (
            currentTime
            + state.effects.fireballPausedRemaining
        );

        state.effects.fireballPausedRemaining = 0;
    }

    if (
        state.effects.widePaddleActive
        && state.effects.widePaddlePausedRemaining > 0
    ) {
        state.effects.widePaddleEndsAt = (
            currentTime
            + state.effects.widePaddlePausedRemaining
        );

        state.effects.widePaddlePausedRemaining = 0;
    }

    hideOverlay();
    pauseButton.textContent = "一時停止";

    state.running = true;

    cancelAnimationFrame(state.animationFrameId);

    state.animationFrameId = requestAnimationFrame(
        gameLoop,
    );
}


function setPaddleFromPointer(clientX) {
    const rectangle = canvas.getBoundingClientRect();

    const scaleX = canvas.width / rectangle.width;
    const pointerX = (clientX - rectangle.left) * scaleX;

    state.paddle.x = (
        pointerX - state.paddle.width / 2
    );

    const maximumX = canvas.width - state.paddle.width;

    state.paddle.x = Math.max(
        0,
        Math.min(state.paddle.x, maximumX),
    );

    if (!state.running) {
        state.ball.x = (
            state.paddle.x + state.paddle.width / 2
        );
        draw();
    }
}


document.addEventListener("keydown", (event) => {
    if (event.key === "ArrowLeft") {
        event.preventDefault();
        state.moveLeft = true;
    }

    if (event.key === "ArrowRight") {
        event.preventDefault();
        state.moveRight = true;
    }

    if (event.key === " " || event.key === "Escape") {
        event.preventDefault();
        togglePause();
    }
});


document.addEventListener("keyup", (event) => {
    if (event.key === "ArrowLeft") {
        state.moveLeft = false;
    }

    if (event.key === "ArrowRight") {
        state.moveRight = false;
    }
});


canvas.addEventListener("mousemove", (event) => {
    setPaddleFromPointer(event.clientX);
});


canvas.addEventListener(
    "touchmove",
    (event) => {
        event.preventDefault();

        const touch = event.touches[0];

        if (touch) {
            setPaddleFromPointer(touch.clientX);
        }
    },
    { passive: false },
);


function bindHoldButton(button, direction) {
    const startMoving = (event) => {
        event.preventDefault();
        state[direction] = true;
    };

    const stopMoving = (event) => {
        event.preventDefault();
        state[direction] = false;
    };

    button.addEventListener("pointerdown", startMoving);
    button.addEventListener("pointerup", stopMoving);
    button.addEventListener("pointercancel", stopMoving);
    button.addEventListener("pointerleave", stopMoving);
}


bindHoldButton(moveLeftButton, "moveLeft");
bindHoldButton(moveRightButton, "moveRight");

startButton.addEventListener(
    "click",
    startOrContinueGame,
);

pauseButton.addEventListener(
    "click",
    togglePause,
);

startButton.dataset.action = "start";

initialiseLevel();
draw();