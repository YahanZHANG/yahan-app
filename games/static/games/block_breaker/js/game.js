import { GAME_CONFIG } from "./config.js";
import { BRICK_TYPES, LEVELS } from "./levels.js";

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

    paddle: {
        x: 0,
        y: 0,
        width: GAME_CONFIG.paddle.width,
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

            state.bricks.push({
                x: startX + columnIndex * (brickWidth + gap),
                y: startY + rowIndex * (brickHeight + gap),
                width: brickWidth,
                height: brickHeight,
                type,
                hitPoints: type === BRICK_TYPES.STRONG ? 2 : 1,
                destroyed: false,
            });
        });
    });
}


function initialiseLevel() {
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

    context.fillStyle = "#f0f3ff";
    context.shadowBlur = 12;
    context.shadowColor = "rgba(150, 170, 255, 0.75)";

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

function draw() {
    drawBackground();
    drawBricks();
    drawPaddle();
    drawBall();
}


function movePaddle() {
    if (state.moveLeft) {
        state.paddle.x -= state.paddle.speed;
    }

    if (state.moveRight) {
        state.paddle.x += state.paddle.speed;
    }

    if (state.paddle.x < 0) {
        state.paddle.x = 0;
    }

    const maximumX = canvas.width - state.paddle.width;

    if (state.paddle.x > maximumX) {
        state.paddle.x = maximumX;
    }
}


function moveBall() {
    state.ball.x += state.ball.dx;
    state.ball.y += state.ball.dy;
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
            brick.hitPoints -= 1;

            if (brick.hitPoints <= 0) {
                brick.destroyed = true;
                state.score += 100;
                updateStatus();
            }
        }

        state.ball.dy *= -1;
        break;
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

    handleWallCollisions();
    handlePaddleCollision();
    handleBrickCollisions();

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

    if (state.paused) {
        pauseButton.textContent = "再開";

        showOverlay(
            "一時停止",
            "準備ができたら再開しよう。",
            "再開",
        );

        return;
    }

    hideOverlay();
    pauseButton.textContent = "一時停止";

    state.running = true;
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