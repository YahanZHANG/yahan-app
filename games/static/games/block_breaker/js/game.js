import { GAME_CONFIG } from "./config.js";
import { BRICK_TYPES, LEVELS } from "./levels.js";

document.body.classList.add(
    "block-breaker-mode",
);

import {
    POWERUP_TYPES,
    POWERUP_CONFIG,
    createPowerup,
    getPowerupSymbol,
} from "./powerups.js";

const powerupStatus = document.getElementById("powerup-status");
const powerupDisplay = document.getElementById("powerup-display");

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
const laserButton = document.getElementById("laser-button");
const gameShell = document.getElementById("game-shell");
const fullscreenButton = document.getElementById("fullscreen-button");
const exitFullscreenButton = document.getElementById("exit-fullscreen-button");

const stageSelect = document.getElementById(
    "stage-select",
);

const stageSelectButton = document.getElementById(
    "stage-select-button",
);

const scoreSaveUrl =
    gameShell.dataset.scoreUrl;

const rankingUrl =
    gameShell.dataset.rankingUrl;

const csrfToken =
    gameShell.dataset.csrfToken;

const rankingList =
    document.getElementById(
        "block-ranking-list",
    );

const personalBestDisplay =
    document.getElementById(
        "block-personal-best",
    );

canvas.width = GAME_CONFIG.canvasWidth;
canvas.height = GAME_CONFIG.canvasHeight;

const state = {
    score: 0,
    lives: GAME_CONFIG.lives,
    levelIndex: 0,

    rankingEligible: true,
    scoreSubmitted: false,

    running: false,
    paused: false,
    animationFrameId: null,

    powerups: [],
    lasers: [],
    explosions: [],

    combo: {
        enabled: false,
        count: 0,
        multiplier: 1,
        lastHitAt: 0,
        windowMs: 1800,
    },

    effects: {
        fireballActive: false,
        fireballEndsAt: 0,
        fireballPausedRemaining: 0,

        widePaddleActive: false,
        widePaddleEndsAt: 0,
        widePaddlePausedRemaining: 0,

        laserActive: false,
        laserEndsAt: 0,
        laserPausedRemaining: 0,
        lastLaserShotAt: 0,
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


function getCurrentLevel() {
    return LEVELS[state.levelIndex];
}


function updateStatus() {
    scoreDisplay.textContent = state.score;
    livesDisplay.textContent = state.lives;
    stageDisplay.textContent = state.levelIndex + 1;

    if (stageSelect) {
        stageSelect.value = String(
            state.levelIndex
        );
    }
}


function keepPaddleInsideCanvas() {
    state.paddle.x = Math.max(
        0,
        Math.min(
            state.paddle.x,
            canvas.width - state.paddle.width,
        ),
    );
}


function resetPaddle() {
    state.paddle.width = state.paddle.normalWidth;

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

            const initialX = (
                startX
                + columnIndex * (brickWidth + gap)
            );

            const initialY = (
                startY
                + rowIndex * (brickHeight + gap)
            );

            state.bricks.push({
                x: initialX,
                y: initialY,
                homeX: initialX,
                homeY: initialY,

                width: brickWidth,
                height: brickHeight,

                rowIndex,
                columnIndex,

                type,
                hitPoints: (
                    type === BRICK_TYPES.STRONG
                    ? 2
                    : 1
                ),

                destroyed: false,

                powerupType: (
                    level.powerups?.[powerupKey]
                    ?? null
                ),

                movable: Boolean(level.movingBricks),

                moveDirection: (
                    rowIndex % 2 === 0
                    ? 1
                    : -1
                ),
            });
        });
    });
}


function resetCombo() {
    state.combo.count = 0;
    state.combo.multiplier = 1;
    state.combo.lastHitAt = 0;
}


function initialiseLevel() {
    state.powerups = [];
    state.lasers = [];
    state.explosions = [];

    deactivateFireball();
    deactivateWidePaddle();
    deactivateLaser();

    state.combo.enabled = Boolean(
        getCurrentLevel().comboEnabled
    );

    resetCombo();
    resetPaddle();
    resetBall();
    createBricks();
    updateStatus();
}


function activateFireball() {
    state.effects.fireballActive = true;

    state.effects.fireballEndsAt = (
        performance.now()
        + POWERUP_CONFIG.fireballDuration
    );
}


function deactivateFireball() {
    state.effects.fireballActive = false;
    state.effects.fireballEndsAt = 0;
    state.effects.fireballPausedRemaining = 0;
}


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


function activateLaser() {
    state.effects.laserActive = true;

    state.effects.laserEndsAt = (
        performance.now()
        + POWERUP_CONFIG.laserDuration
    );

    if (laserButton) {
        laserButton.disabled = false;
        laserButton.classList.add("is-active");
    }
}


function deactivateLaser() {
    state.effects.laserActive = false;
    state.effects.laserEndsAt = 0;
    state.effects.laserPausedRemaining = 0;
    state.effects.lastLaserShotAt = 0;

    if (laserButton) {
        laserButton.disabled = true;
        laserButton.classList.remove("is-active");
    }
}


function updateTimedEffects(currentTime) {
    if (
        state.effects.fireballActive
        && currentTime >= state.effects.fireballEndsAt
    ) {
        deactivateFireball();
    }

    if (
        state.effects.widePaddleActive
        && currentTime >= state.effects.widePaddleEndsAt
    ) {
        deactivateWidePaddle();
    }

    if (
        state.effects.laserActive
        && currentTime >= state.effects.laserEndsAt
    ) {
        deactivateLaser();
    }

    const labels = [];

    if (state.effects.fireballActive) {
        labels.push(
            `🔥 ${Math.max(
                0,
                (
                    state.effects.fireballEndsAt
                    - currentTime
                ) / 1000,
            ).toFixed(1)}`
        );
    }

    if (state.effects.widePaddleActive) {
        labels.push(
            `↔️ ${Math.max(
                0,
                (
                    state.effects.widePaddleEndsAt
                    - currentTime
                ) / 1000,
            ).toFixed(1)}`
        );
    }

    if (state.effects.laserActive) {
        labels.push(
            `⚡ ${Math.max(
                0,
                (
                    state.effects.laserEndsAt
                    - currentTime
                ) / 1000,
            ).toFixed(1)}`
        );
    }

    if (labels.length === 0) {
        powerupStatus.classList.add("is-hidden");
        powerupDisplay.textContent = "";
    } else {
        powerupDisplay.textContent = labels.join("  ");
        powerupStatus.classList.remove("is-hidden");
    }
}


function registerComboHit() {
    if (!state.combo.enabled) {
        return 1;
    }

    const currentTime = performance.now();

    if (
        state.combo.lastHitAt > 0
        && (
            currentTime
            - state.combo.lastHitAt
        ) <= state.combo.windowMs
    ) {
        state.combo.count += 1;
    } else {
        state.combo.count = 1;
    }

    state.combo.lastHitAt = currentTime;

    state.combo.multiplier = Math.min(
        5,
        Math.floor(
            (state.combo.count - 1) / 2
        ) + 1,
    );

    return state.combo.multiplier;
}


function updateCombo(currentTime) {
    if (
        !state.combo.enabled
        || state.combo.count === 0
    ) {
        return;
    }

    if (
        currentTime - state.combo.lastHitAt
        > state.combo.windowMs
    ) {
        resetCombo();
    }
}


function createExplosion(brick) {
    state.explosions.push({
        x: brick.x + brick.width / 2,
        y: brick.y + brick.height / 2,
        radius: 8,
        maxRadius: 72,
        life: 18,
        maxLife: 18,
    });
}


function dropBrickPowerup(brick) {
    if (
        brick.type !== BRICK_TYPES.POWERUP
        || !brick.powerupType
    ) {
        return;
    }

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


function destroyBrick(brick) {
    if (
        brick.destroyed
        || brick.type === BRICK_TYPES.UNBREAKABLE
    ) {
        return false;
    }

    brick.destroyed = true;

    const multiplier = registerComboHit();
    state.score += 100 * multiplier;

    dropBrickPowerup(brick);

    if (brick.type === BRICK_TYPES.BOMB) {
        explodeBomb(brick);
    }

    updateStatus();
    return true;
}


function explodeBomb(originBrick) {
    createExplosion(originBrick);

    const neighboringBricks = state.bricks.filter((brick) => {
        if (
            brick.destroyed
            || brick.type === BRICK_TYPES.UNBREAKABLE
        ) {
            return false;
        }

        const rowDistance = Math.abs(
            brick.rowIndex - originBrick.rowIndex
        );

        const columnDistance = Math.abs(
            brick.columnIndex - originBrick.columnIndex
        );

        return (
            rowDistance <= 1
            && columnDistance <= 1
            && brick !== originBrick
        );
    });

    neighboringBricks.forEach((brick) => {
        brick.hitPoints = 0;
        destroyBrick(brick);
    });
}


function damageBrick(brick, damage = 1) {
    if (
        brick.destroyed
        || brick.type === BRICK_TYPES.UNBREAKABLE
    ) {
        return false;
    }

    brick.hitPoints -= damage;

    if (brick.hitPoints <= 0) {
        return destroyBrick(brick);
    }

    return false;
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

    if (state.effects.laserActive) {
        context.fillStyle = "#ff6b7d";
        context.shadowBlur = 22;
        context.shadowColor = "rgba(255, 80, 110, 0.95)";
    } else if (state.effects.widePaddleActive) {
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

    if (state.effects.laserActive) {
        context.fillStyle = "#fff3f5";

        context.fillRect(
            state.paddle.x + 8,
            state.paddle.y - 6,
            8,
            8,
        );

        context.fillRect(
            (
                state.paddle.x
                + state.paddle.width
                - 16
            ),
            state.paddle.y - 6,
            8,
            8,
        );
    }

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
        gradient.addColorStop(
            1,
            "rgba(255, 70, 20, 0)",
        );

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
    } else {
        context.fillStyle = "#ffffff";
        context.shadowBlur = 14;
        context.shadowColor = "#b7c4ff";
    }

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

    if (brick.type === BRICK_TYPES.BOMB) {
        return "#2d3242";
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

        if (brick.type === BRICK_TYPES.BOMB) {
            context.shadowBlur = 0;
            context.font = "22px sans-serif";
            context.textAlign = "center";
            context.textBaseline = "middle";

            context.fillText(
                "💣",
                brick.x + brick.width / 2,
                brick.y + brick.height / 2 + 1,
            );
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


function drawLasers() {
    state.lasers.forEach((laser) => {
        context.save();

        context.fillStyle = "#ff4264";
        context.shadowBlur = 16;
        context.shadowColor = "#ff4264";

        context.fillRect(
            laser.x,
            laser.y,
            laser.width,
            laser.height,
        );

        context.restore();
    });
}


function drawExplosions() {
    state.explosions.forEach((explosion) => {
        const alpha = (
            explosion.life
            / explosion.maxLife
        );

        context.save();

        context.globalAlpha = alpha;
        context.strokeStyle = "#ffb13b";
        context.lineWidth = 8;
        context.shadowBlur = 24;
        context.shadowColor = "#ff6338";

        context.beginPath();
        context.arc(
            explosion.x,
            explosion.y,
            explosion.radius,
            0,
            Math.PI * 2,
        );
        context.stroke();

        context.restore();
    });
}


function drawCombo() {
    if (
        !state.combo.enabled
        || state.combo.count < 2
    ) {
        return;
    }

    context.save();

    context.font = "bold 22px sans-serif";
    context.textAlign = "right";
    context.textBaseline = "top";
    context.fillStyle = "#fff2a8";
    context.shadowBlur = 12;
    context.shadowColor = "#ff9f43";

    context.fillText(
        (
            `COMBO ${state.combo.count}`
            + `  ×${state.combo.multiplier}`
        ),
        canvas.width - 18,
        18,
    );

    context.restore();
}


function draw() {
    drawBackground();
    drawBricks();
    drawPowerups();
    drawExplosions();
    drawLasers();
    drawPaddle();
    drawBall();
    drawCombo();
}


function moveBall() {
    state.ball.x += state.ball.dx;
    state.ball.y += state.ball.dy;
}


function moveBricks() {
    const level = getCurrentLevel();

    if (!level.movingBricks) {
        return;
    }

    const movementSpeed = (
        level.brickMovementSpeed
        ?? 1
    );

    const movementRange = (
        level.brickMovementRange
        ?? 24
    );

    state.bricks.forEach((brick) => {
        if (
            brick.destroyed
            || !brick.movable
        ) {
            return;
        }

        brick.x += (
            movementSpeed
            * brick.moveDirection
        );

        const distanceFromHome = (
            brick.x - brick.homeX
        );

        if (distanceFromHome >= movementRange) {
            brick.x = brick.homeX + movementRange;
            brick.moveDirection = -1;
        }

        if (distanceFromHome <= -movementRange) {
            brick.x = brick.homeX - movementRange;
            brick.moveDirection = 1;
        }
    });
}


function movePowerups() {
    state.powerups.forEach((powerup) => {
        if (!powerup.collected) {
            powerup.y += powerup.speed;
        }
    });

    state.powerups = state.powerups.filter((powerup) => {
        return (
            !powerup.collected
            && powerup.y
            < canvas.height + powerup.height
        );
    });
}


function moveLasers() {
    state.lasers.forEach((laser) => {
        laser.y -= laser.speed;
    });

    state.lasers = state.lasers.filter((laser) => {
        return (
            !laser.destroyed
            && laser.y + laser.height > 0
        );
    });
}


function updateExplosions() {
    state.explosions.forEach((explosion) => {
        explosion.life -= 1;

        const progress = (
            1
            - explosion.life / explosion.maxLife
        );

        explosion.radius = (
            8
            + (
                explosion.maxRadius - 8
            ) * progress
        );
    });

    state.explosions = state.explosions.filter(
        (explosion) => explosion.life > 0,
    );
}


function rectanglesOverlap(first, second) {
    return (
        first.x < second.x + second.width
        && first.x + first.width > second.x
        && first.y < second.y + second.height
        && first.y + first.height > second.y
    );
}


function circleTouchesRectangle(ball, rectangle) {
    const nearestX = Math.max(
        rectangle.x,
        Math.min(
            ball.x,
            rectangle.x + rectangle.width,
        ),
    );

    const nearestY = Math.max(
        rectangle.y,
        Math.min(
            ball.y,
            rectangle.y + rectangle.height,
        ),
    );

    const distanceX = ball.x - nearestX;
    const distanceY = ball.y - nearestY;

    return (
        distanceX * distanceX
        + distanceY * distanceY
        <= ball.radius * ball.radius
    );
}


function handlePowerupCollisions() {
    state.powerups.forEach((powerup) => {
        if (
            powerup.collected
            || !rectanglesOverlap(
                powerup,
                state.paddle,
            )
        ) {
            return;
        }

        powerup.collected = true;

        if (powerup.type === POWERUP_TYPES.FIREBALL) {
            activateFireball();
            state.score += 250;
        }

        if (
            powerup.type
            === POWERUP_TYPES.WIDE_PADDLE
        ) {
            activateWidePaddle();
            state.score += 200;
        }

        if (powerup.type === POWERUP_TYPES.LASER) {
            activateLaser();
            state.score += 300;
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

    const touchesPaddle = (
        ball.y + ball.radius >= paddle.y
        && ball.y - ball.radius
        <= paddle.y + paddle.height
        && ball.x + ball.radius >= paddle.x
        && ball.x - ball.radius
        <= paddle.x + paddle.width
        && ball.dy > 0
    );

    if (!touchesPaddle) {
        return;
    }

    ball.y = paddle.y - ball.radius;

    const paddleCenter = (
        paddle.x + paddle.width / 2
    );

    const hitPosition = (
        ball.x - paddleCenter
    ) / (paddle.width / 2);

    const speed = Math.sqrt(
        ball.dx * ball.dx
        + ball.dy * ball.dy
    );

    ball.dx = speed * hitPosition;

    ball.dy = -Math.abs(
        Math.sqrt(
            Math.max(
                1,
                speed * speed
                - ball.dx * ball.dx,
            ),
        ),
    );
}


function bounceBallFromBrick(brick) {
    const ball = state.ball;

    const previousX = ball.x - ball.dx;
    const previousY = ball.y - ball.dy;

    const cameFromLeft = (
        previousX + ball.radius <= brick.x
    );

    const cameFromRight = (
        previousX - ball.radius
        >= brick.x + brick.width
    );

    const cameFromTop = (
        previousY + ball.radius <= brick.y
    );

    const cameFromBottom = (
        previousY - ball.radius
        >= brick.y + brick.height
    );

    if (cameFromLeft && ball.dx > 0) {
        ball.x = brick.x - ball.radius;
        ball.dx *= -1;
        return;
    }

    if (cameFromRight && ball.dx < 0) {
        ball.x = (
            brick.x
            + brick.width
            + ball.radius
        );

        ball.dx *= -1;
        return;
    }

    if (cameFromTop && ball.dy > 0) {
        ball.y = brick.y - ball.radius;
        ball.dy *= -1;
        return;
    }

    if (cameFromBottom && ball.dy < 0) {
        ball.y = (
            brick.y
            + brick.height
            + ball.radius
        );

        ball.dy *= -1;
        return;
    }

    ball.dy *= -1;
}


function handleBrickCollisions() {
    for (const brick of state.bricks) {
        if (
            brick.destroyed
            || !circleTouchesRectangle(
                state.ball,
                brick,
            )
        ) {
            continue;
        }

        const isUnbreakable = (
            brick.type === BRICK_TYPES.UNBREAKABLE
        );

        if (!isUnbreakable) {
            const damage = (
                state.effects.fireballActive
                ? Number.POSITIVE_INFINITY
                : 1
            );

            damageBrick(brick, damage);
        }

        const shouldBounce = (
            isUnbreakable
            || !state.effects.fireballActive
        );

        if (shouldBounce) {
            bounceBallFromBrick(brick);
            break;
        }
    }
}


function handleLaserBrickCollisions() {
    state.lasers.forEach((laser) => {
        if (laser.destroyed) {
            return;
        }

        for (const brick of state.bricks) {
            if (
                brick.destroyed
                || !rectanglesOverlap(laser, brick)
            ) {
                continue;
            }

            laser.destroyed = true;

            if (
                brick.type
                !== BRICK_TYPES.UNBREAKABLE
            ) {
                damageBrick(brick, 1);
            }

            break;
        }
    });

    state.lasers = state.lasers.filter(
        (laser) => !laser.destroyed,
    );
}


function fireLaser() {
    if (
        !state.running
        || state.paused
        || !state.effects.laserActive
    ) {
        return;
    }

    const currentTime = performance.now();

    if (
        currentTime
        - state.effects.lastLaserShotAt
        < POWERUP_CONFIG.laserCooldown
    ) {
        return;
    }

    state.effects.lastLaserShotAt = currentTime;

    const leftLaserX = (
        state.paddle.x + 11
    );

    const rightLaserX = (
        state.paddle.x
        + state.paddle.width
        - 11
        - POWERUP_CONFIG.laserWidth
    );

    const laserY = (
        state.paddle.y
        - POWERUP_CONFIG.laserHeight
    );

    [leftLaserX, rightLaserX].forEach((x) => {
        state.lasers.push({
            x,
            y: laserY,
            width: POWERUP_CONFIG.laserWidth,
            height: POWERUP_CONFIG.laserHeight,
            speed: POWERUP_CONFIG.laserSpeed,
            destroyed: false,
        });
    });
}


function getRemainingBreakableBricks() {
    return state.bricks.filter((brick) => {
        return (
            !brick.destroyed
            && brick.type
            !== BRICK_TYPES.UNBREAKABLE
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
            `次は「${LEVELS[
                state.levelIndex + 1
            ].name}」。`,
            "次のステージ",
        );

        startButton.dataset.action = "next-level";
    } else {

        void submitScoreIfEligible();

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
    resetCombo();
    updateStatus();

    if (state.lives <= 0) {
        state.running = false;
        startButton.dataset.action = "restart";

        void submitScoreIfEligible();

        showOverlay(
            "ゲームオーバー",
            `最終スコアは${state.score}点。`,
            "最初から",
        );

        return;
    }

    state.running = false;
    state.lasers = [];

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

    moveBall();
    moveBricks();
    movePowerups();
    moveLasers();

    handleWallCollisions();
    handlePaddleCollision();
    handleBrickCollisions();
    handleLaserBrickCollisions();
    handlePowerupCollisions();

    const currentTime = performance.now();

    updateTimedEffects(currentTime);
    updateCombo(currentTime);
    updateExplosions();

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

async function lockLandscapeOrientation() {
    if (
        !screen.orientation
        || typeof screen.orientation.lock !== "function"
    ) {
        return;
    }

    try {
        await screen.orientation.lock(
            "landscape",
        );
    } catch (error) {
        console.info(
            "この端末では横向き固定を利用できません。",
            error,
        );
    }
}


function unlockScreenOrientation() {
    if (
        screen.orientation
        && typeof screen.orientation.unlock === "function"
    ) {
        screen.orientation.unlock();
    }
}

async function toggleFullscreen() {
    if (!gameShell) {
        return;
    }

    try {
        if (document.fullscreenElement) {
            unlockScreenOrientation();
            await document.exitFullscreen();
            return;
        }

        if (gameShell.requestFullscreen) {
            await gameShell.requestFullscreen();

            await lockLandscapeOrientation();
            return;
        }

        gameShell.classList.toggle(
            "is-pseudo-fullscreen",
        );

        if (
            gameShell.classList.contains(
                "is-pseudo-fullscreen",
            )
        ) {
            await lockLandscapeOrientation();
        } else {
            unlockScreenOrientation();
        }

        updateFullscreenButton();
    } catch (error) {
        console.warn(
            "全画面または横向き固定を開始できませんでした。",
            error,
        );

        gameShell.classList.toggle(
            "is-pseudo-fullscreen",
        );

        updateFullscreenButton();
    }
}

async function exitFullscreenMode() {
    try {
        if (document.fullscreenElement) {
            unlockScreenOrientation();
            await document.exitFullscreen();
            return;
        }

        if (
            gameShell
            && gameShell.classList.contains(
                "is-pseudo-fullscreen",
            )
        ) {
            gameShell.classList.remove(
                "is-pseudo-fullscreen",
            );

            unlockScreenOrientation();
            updateFullscreenButton();
        }
    } catch (error) {
        console.warn(
            "全画面を終了できませんでした。",
            error,
        );
    }
}

function updateFullscreenButton() {
    if (!fullscreenButton || !gameShell) {
        return;
    }

    const isFullscreen = Boolean(
        document.fullscreenElement
        || gameShell.classList.contains(
            "is-pseudo-fullscreen",
        )
    );

    fullscreenButton.textContent = (
        isFullscreen
        ? "× 全画面を終了"
        : "⛶ 全画面"
    );
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

function renderRanking(data) {

    if (
        !rankingList
        || !personalBestDisplay
    ) {
        return;
    }

    rankingList.innerHTML = "";

    const entries =
        data.entries ?? [];

    if (entries.length === 0) {

        const emptyItem =
            document.createElement("li");

        emptyItem.className =
            "block-ranking-empty";

        emptyItem.textContent =
            "まだランキング記録がない";

        rankingList.appendChild(
            emptyItem
        );

    } else {

        entries.forEach((entry) => {

            const item =
                document.createElement("li");

            if (entry.is_me) {
                item.classList.add(
                    "is-me"
                );
            }


            const position =
                document.createElement(
                    "span"
                );

            position.className =
                "block-ranking-position";

            position.textContent =
                String(entry.rank);


            const name =
                document.createElement(
                    "strong"
                );

            name.textContent =
                entry.name;


            const score =
                document.createElement(
                    "span"
                );

            score.className =
                "block-ranking-score";

            score.textContent =
                `${entry.score} 点`;


            item.append(
                position,
                name,
                score,
            );

            rankingList.appendChild(
                item
            );

        });

    }


    personalBestDisplay.textContent = (
        data.personal_best === null
        ? "--"
        : String(data.personal_best)
    );

}

async function submitScoreIfEligible() {

    if (
        !state.rankingEligible
        || state.scoreSubmitted
        || state.score < 0
    ) {
        return;
    }

    state.scoreSubmitted = true;

    try {

        const response =
            await fetch(
                scoreSaveUrl,
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json",

                        "X-CSRFToken":
                            csrfToken,
                    },

                    credentials:
                        "same-origin",

                    body:
                        JSON.stringify(
                            {
                                game:
                                    "block_breaker",

                                score:
                                    state.score,
                            }
                        ),
                }
            );


        if (!response.ok) {
            throw new Error(
                "Score save failed."
            );
        }


        const data =
            await response.json();

        if (data.ok) {
            renderRanking(data);
        }

    } catch (error) {

        console.warn(
            "ランキングを保存できませんでした。",
            error,
        );

    }

}


function restorePausedEffectTimers() {
    const currentTime = performance.now();

    const timers = [
        [
            "fireballActive",
            "fireballEndsAt",
            "fireballPausedRemaining",
        ],
        [
            "widePaddleActive",
            "widePaddleEndsAt",
            "widePaddlePausedRemaining",
        ],
        [
            "laserActive",
            "laserEndsAt",
            "laserPausedRemaining",
        ],
    ];

    timers.forEach((
        [
            activeKey,
            endsAtKey,
            remainingKey,
        ],
    ) => {
        if (
            state.effects[activeKey]
            && state.effects[remainingKey] > 0
        ) {
            state.effects[endsAtKey] = (
                currentTime
                + state.effects[remainingKey]
            );

            state.effects[remainingKey] = 0;
        }
    });
}


function savePausedEffectTimers() {
    const currentTime = performance.now();

    const timers = [
        [
            "fireballActive",
            "fireballEndsAt",
            "fireballPausedRemaining",
        ],
        [
            "widePaddleActive",
            "widePaddleEndsAt",
            "widePaddlePausedRemaining",
        ],
        [
            "laserActive",
            "laserEndsAt",
            "laserPausedRemaining",
        ],
    ];

    timers.forEach((
        [
            activeKey,
            endsAtKey,
            remainingKey,
        ],
    ) => {
        if (state.effects[activeKey]) {
            state.effects[remainingKey] = Math.max(
                0,
                (
                    state.effects[endsAtKey]
                    - currentTime
                ),
            );
        }
    });
}

function selectStage() {
    if (!stageSelect) {
        return;
    }

    const selectedLevelIndex = Number(
        stageSelect.value
    );

    const isValidLevel = (
        Number.isInteger(selectedLevelIndex)
        && selectedLevelIndex >= 0
        && selectedLevelIndex < LEVELS.length
    );

    if (!isValidLevel) {
        return;
    }

    state.running = false;
    state.paused = false;

    cancelAnimationFrame(
        state.animationFrameId
    );

    state.animationFrameId = null;

    state.levelIndex = selectedLevelIndex;

    // ステージ選択から開始したプレイは
    // 練習扱いにしてランキングへ登録しない。
    state.rankingEligible = false;
    state.scoreSubmitted = false;

    // ステージ選択時もスコアを残したい場合は、selectStage()内のこの2行だけ削除
    // state.score = 0;
    // state.lives = GAME_CONFIG.lives;

    initialiseLevel();
    draw();

    pauseButton.textContent = "一時停止";

    const selectedLevel = getCurrentLevel();

    showOverlay(
        `ステージ${selectedLevel.number}`,
        `「${selectedLevel.name}」を開始する。`,
        "スタート",
    );

    startButton.dataset.action = "start";
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

        state.rankingEligible = true;
        state.scoreSubmitted = false;

        initialiseLevel();
    }

    startButton.dataset.action = "";

    restorePausedEffectTimers();

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
        savePausedEffectTimers();

        pauseButton.textContent = "再開";

        showOverlay(
            "一時停止",
            "準備ができたら再開しよう。",
            "再開",
        );

        return;
    }

    restorePausedEffectTimers();

    hideOverlay();
    pauseButton.textContent = "一時停止";

    state.running = true;

    cancelAnimationFrame(state.animationFrameId);

    state.animationFrameId = requestAnimationFrame(
        gameLoop,
    );
}


function setPaddleFromPointer(clientX) {
    const canvasRectangle = (
        canvas.getBoundingClientRect()
    );

    if (canvasRectangle.width <= 0) {
        return;
    }

    const pointerX = (
        clientX - canvasRectangle.left
    );

    const pointerRatio = Math.max(
        0,
        Math.min(
            1,
            pointerX / canvasRectangle.width,
        ),
    );

    const movableWidth = (
        canvas.width
        - state.paddle.width
    );

    state.paddle.x = (
        movableWidth
        * pointerRatio
    );

    keepPaddleInsideCanvas();

    if (!state.running) {
        state.ball.x = (
            state.paddle.x
            + state.paddle.width / 2
        );

        draw();
    }
}

document.addEventListener("keydown", (event) => {

    if (event.code === "Space") {
        event.preventDefault();
        fireLaser();
    }

    if (event.key === "Escape") {
        event.preventDefault();
        togglePause();
    }
});

canvas.addEventListener(
    "pointerdown",
    (event) => {
        setPaddleFromPointer(
            event.clientX,
        );

        if (event.pointerType === "touch") {
            event.preventDefault();
        }
    },
    { passive: false },
);


canvas.addEventListener(
    "pointermove",
    (event) => {
        setPaddleFromPointer(
            event.clientX,
        );

        if (event.pointerType === "touch") {
            event.preventDefault();
        }
    },
    { passive: false },
);

document.addEventListener(
    "pointermove",
    (event) => {
        if (isInteractiveElement(event.target)) {
            return;
        }

        setPaddleFromPointer(event.clientX);

        if (event.pointerType === "touch") {
            event.preventDefault();
        }
    },
    { passive: false },
);

document.addEventListener(
    "pointerdown",
    (event) => {
        if (isInteractiveElement(event.target)) {
            return;
        }

        setPaddleFromPointer(event.clientX);
    },
);


startButton.addEventListener(
    "click",
    startOrContinueGame,
);

pauseButton.addEventListener(
    "click",
    togglePause,
);

if (fullscreenButton) {
    fullscreenButton.addEventListener(
        "click",
        toggleFullscreen,
    );
}

if (exitFullscreenButton) {
    exitFullscreenButton.addEventListener(
        "click",
        exitFullscreenMode,
    );
}


document.addEventListener(
    "fullscreenchange",
    () => {
        updateFullscreenButton();

        if (!document.fullscreenElement) {
            unlockScreenOrientation();
        }
    },
);

if (stageSelectButton) {
    stageSelectButton.addEventListener(
        "click",
        selectStage,
    );
}

if (laserButton) {
    laserButton.disabled = true;

    laserButton.addEventListener(
        "click",
        fireLaser,
    );
}

startButton.dataset.action = "start";

initialiseLevel();
draw();
