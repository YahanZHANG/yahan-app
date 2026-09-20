
document.addEventListener("DOMContentLoaded", () => {
    "use strict";

    // オリジナルの横スクロールアクション。外部画像・ゲームライブラリ不要。
    const GAME = "maaario";
    const VIEW_W = 960;
    const VIEW_H = 540;
    const GROUND = 425;
    const HERO_W = 32;
    const HERO_H = 46;
    const GRAVITY = 1700;
    const JUMP_VELOCITY = -660;
    const STEP = 1 / 120;

    
    /* ========================================
    LEVEL SETTINGS
    ======================================== */

    const LEVELS = {

        // ====================================
        // LEVEL 1 - はじまりの草原
        // ====================================

        1: {

            name: "はじまりの草原",

            length: 2550,

            speed: 262,

            enemySpeed: 38,

            time: 120,

            gaps: [
                [775, 74],
                [1490, 82],
            ],

            platforms: [
                [430, 345, 120],
                [1060, 335, 125],
                [1930, 345, 115],
            ],

            enemies: [
                [475, 0.85, 55],
                [1805, 1.0, 70],
            ],

        },


        // ====================================
        // LEVEL 2 - さばくの冒険
        // ====================================

        2: {

            name: "さばくの冒険",

            length: 2920,

            speed: 270,

            enemySpeed: 47,

            time: 110,

            gaps: [
                [615, 90],
                [1270, 95],
                [2080, 95],
            ],

            platforms: [
                [340, 340, 110],
                [780, 315, 100],
                [1100, 345, 115],
                [1540, 325, 95],
                [2200, 340, 110],
                [2670, 310, 100],
            ],

            enemies: [
                [400, 0.9, 60],
                [880, 1.0, 85],
                [1650, 1.1, 80],
                [2460, 1.2, 95],
            ],

        },


        // ====================================
        // LEVEL 3 - まほうの森
        // ====================================

        3: {

            name: "まほうの森",

            length: 3240,

            speed: 280,

            enemySpeed: 56,

            time: 105,

            gaps: [
                [615, 105],
                [1210, 108],
                [1885, 110],
                [2630, 110],
            ],

            platforms: [
                [350, 335, 100],
                [745, 345, 85],
                [1020, 315, 90],
                [1370, 340, 75],
                [1580, 320, 95],
                [2020, 345, 85],
                [2370, 310, 90],
                [2770, 340, 75],
                [3010, 325, 90],
            ],

            enemies: [
                [360, 0.9, 65],
                [940, 1.0, 85],
                [1460, 1.1, 90],
                [1770, 1.15, 90],
                [2250, 1.2, 100],
                [2850, 1.25, 100],
            ],

        },


        // ====================================
        // LEVEL 4 - こおりの世界
        // ====================================

        4: {

            name: "こおりの世界",

            length: 3610,

            speed: 288,

            enemySpeed: 66,

            time: 100,

            gaps: [
                [625, 115],
                [1260, 120],
                [1910, 120],
                [2540, 124],
                [3140, 125],
            ],

            platforms: [
                [315, 345, 90],
                [710, 315, 80],
                [945, 340, 85],
                [1100, 315, 80],
                [1450, 345, 75],
                [1720, 320, 85],
                [2050, 340, 75],
                [2390, 310, 85],
                [2700, 345, 75],
                [2900, 320, 85],
                [3230, 340, 80],
                [3460, 315, 75],
            ],

            enemies: [
                [405, 0.9, 70],
                [885, 1.0, 80],
                [1510, 1.05, 75],
                [1660, 1.1, 90],
                [2180, 1.15, 90],
                [2360, 1.2, 95],
                [2840, 1.25, 100],
                [3380, 1.3, 100],
            ],

        },


        // ====================================
        // LEVEL 5 - さいごの火山
        // ====================================

        5: {

            name: "さいごの火山",

            length: 4000,

            speed: 293,

            enemySpeed: 90,

            time: 85,

            gaps: [
                [630, 130],
                [1220, 132],
                [1800, 134],
                [2370, 138],
                [2980, 140],
                [3540, 140],
            ],

            platforms: [
                [300, 344, 115],
                [545, 314, 65],
                [785, 343, 86],
                [1040, 313, 70],
                [1365, 340, 72],
                [1570, 310, 60],
                [1900, 339, 77],
                [2140, 315, 62],
                [2460, 341, 72],
                [2690, 310, 60],
                [2910, 344, 58],
                [3110, 315, 78],
                [3340, 337, 65],
                [3610, 313, 74],
                [3775, 344, 68],
            ],

            enemies: [
                [410, 0.9, 65],
                [915, 1.0, 85],
                [1140, 1.05, 65],
                [1480, 1.1, 75],
                [1690, 1.15, 80],
                [2220, 1.2, 85],
                [2600, 1.25, 75],
                [2790, 1.3, 100],
                [3240, 1.35, 95],
                [3430, 1.4, 75],
                [3830, 1.5, 65],
            ],

        },

    };
    
    /* ========================================
    World Themes
    ======================================== */

    const STAGE_THEMES = {

        1: {
            skyTop: "#73cfff",
            skyBottom: "#eaffdd",

            ground: "#966b49",
            groundTop: "#59bf70",

            platform: "#b77c50",
            platformTop: "#76d88c",
        },

        2: {
            skyTop: "#ffae73",
            skyBottom: "#ffe3a4",

            ground: "#d79753",
            groundTop: "#f5d276",

            platform: "#b97842",
            platformTop: "#ffd987",
        },

        3: {
            skyTop: "#245b65",
            skyBottom: "#87cba4",

            ground: "#514b48",
            groundTop: "#4eae80",

            platform: "#775b4b",
            platformTop: "#6ad4a2",
        },

        4: {
            skyTop: "#5175b8",
            skyBottom: "#d2efff",

            ground: "#83abc9",
            groundTop: "#f1fbff",

            platform: "#729bc2",
            platformTop: "#e0faff",
        },

        5: {
            skyTop: "#24132f",
            skyBottom: "#b63f4f",

            ground: "#493442",
            groundTop: "#ff7248",

            platform: "#65404b",
            platformTop: "#ff9861",
        },

    };

    const shell = document.getElementById("jump-shell");
    if (!shell) return;
    const canvas = document.getElementById("jump-canvas");
    const ctx = canvas?.getContext("2d");
    if (!ctx) return;

    const $ = id => document.getElementById(id);
    const ui = {
        levelButtons: [...document.querySelectorAll(".jump-level-button")],
        selectedLevel: $("jump-selected-level"), currentLevel: $("jump-current-level"),
        score: $("jump-score"), lives: $("jump-lives"), time: $("jump-time"),
        overlay: $("jump-overlay"), overlayIcon: $("jump-overlay-icon"),
        overlayLabel: $("jump-overlay-label"), overlayTitle: $("jump-overlay-title"),
        overlayMessage: $("jump-overlay-message"), overlayButton: $("jump-overlay-button"),
        pause: $("jump-pause"), quit: $("jump-quit"), action: $("jump-action"),
        fullscreen: $("jump-fullscreen"), exitFullscreen: $("jump-exit-fullscreen"),
        rankingLevel: $("jump-ranking-level"), rankingList: $("jump-ranking-list"),
        personalBest: $("jump-personal-best"), saveStatus: $("jump-save-status"),
    };
    const scoreUrl = shell.dataset.scoreUrl;
    const rankingUrl = shell.dataset.rankingUrl;
    const csrfToken = shell.dataset.csrfToken;
    let selectedLevel = 1;
    let mode = "ready";
    let world = null;
    let hero = null;
    let lives = 3;
    let score = 0;
    let timeLeft = 120;
    let checkpoint = 80;
    let checkpointReached = false;
    let cameraX = 0;
    let invulnerable = 0;
    let jumpBuffer = 0;
    let coyote = 0;
    let particles = [];
    let popup = [];
    let pressed = { left: false, right: false };
    let raf = null;
    let lastFrame = 0;
    let accumulator = 0;
    let requestId = 0;
    let saveRequestId = 0;
    const pointers = new Map();

    const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
    const overlap = (a, b) => a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;
    const rand = (n, seed) => {
        const v = Math.sin(n * 127.1 + seed * 311.7) * 43758.5453;
        return v - Math.floor(v);
    };

    function safeGround(x, gaps, padding = 25) {
        return !gaps.some(([start, width]) => x >= start - padding && x <= start + width + padding);
    }

    function nearestSafe(x, gaps, length) {
        let candidate = clamp(x, 80, length - 210);
        for (let tries = 0; tries < 300 && !safeGround(candidate, gaps, 80); tries++) candidate += 8;
        return clamp(candidate, 80, length - 210);
    }


    /* ========================================
    Create World
    ======================================== */

    function createWorld(level) {

        const config =
            LEVELS[level];

        const gaps =
            config.gaps;

        const surfaces = [];

        let start = 0;


                
        /* ========================================
        Level-specific platforms
        ======================================== */

        config.platforms.forEach(
            ([x, y, w], index) => {

                // LEVEL 5では一部の足場が動く
                const isMoving =
                    level === 5
                    && (
                        index % 2 === 0
                        || index === 13
                    );


                // 動く方向をランダムに決める
                const axis =
                    Math.random() < 0.5
                        ? "horizontal"
                        : "vertical";


                // 移動幅をランダムに決める
                const amplitude =
                    axis === "horizontal"

                        // 左右：45〜90px
                        ? 45 + Math.floor(
                            Math.random() * 46
                        )

                        // 上下：22〜50px
                        : 22 + Math.floor(
                            Math.random() * 29
                        );


                // 移動速度もランダム
                const speed =
                    2.0
                    + Math.random() * 1.3;


                // 最初に進む方向もランダム
                const direction =
                    Math.random() < 0.5
                        ? -1
                        : 1;


                surfaces.push({

                    x: x,
                    y: y,

                    baseX: x,
                    baseY: y,

                    w: w,
                    h: 16,

                    kind: "platform",

                    motion: isMoving

                        ? {

                            axis: axis,

                            amplitude: amplitude,

                            speed: speed,

                            direction: direction,

                        }

                : null,

        });

    }
);

        // Last ground section

        surfaces.push({

            x: start,

            y: GROUND,

            w: config.length - start,

            h: VIEW_H - GROUND + 200,

            kind: "ground",

        });


        // ====================================
        // Level-specific platforms
        // ====================================

        // 足場を自動生成せず、
        // LEVELSで定義した位置に配置する

        for (
            const [x, y, w]
            of config.platforms
        ) {

            surfaces.push({

                x: x,

                y: y,

                w: w,

                h: 16,

                kind: "platform",

            });

        }


        // ====================================
        // Coins
        // ====================================

        const coins = [];


        // Coins on the ground

        for (
            let x = 230, i = 0;
            x < config.length - 120;
            x += 88, i++
        ) {

            if (
                safeGround(
                    x,
                    gaps,
                    27
                )
            ) {

                coins.push({

                    x: x,

                    y:
                        GROUND
                        - (
                            i % 5 === 0
                                ? 105
                                : 33
                        ),

                    taken: false,

                });

            }

        }


        // Coins above holes

        for (
            const [gapX, gapW]
            of gaps
        ) {

            for (
                let j = 0;
                j < 3;
                j++
            ) {

                coins.push({

                    x:
                        gapX
                        + gapW
                        * (j + 1) / 4,

                    y:
                        GROUND
                        - 87
                        - (
                            j === 1
                                ? 16
                                : 0
                        ),

                    taken: false,

                });

            }

        }

        
        /* ========================================
        Coins above platforms
        ======================================== */

        for (
            const platform
            of surfaces.filter(
                p => p.kind === "platform"
            )
        ) {

            coins.push({

                x:
                    platform.x
                    + platform.w / 2,

                y:
                    platform.y - 26,

                taken: false,

                // どの足場の上にあるコインか
                platform: platform,

            });

        }


        /* ========================================
        Coin animation settings
        ======================================== */

        coins.forEach(
            (coin, index) => {

                // 初期位置を保存
                coin.baseX = coin.x;

                coin.baseY = coin.y;

                coin.motionIndex = index;

            }
        );


        // ====================================
        // Checkpoint
        // ====================================

        const checkpointX =
            nearestSafe(

                Math.floor(
                    config.length * 0.5
                ),

                gaps,

                config.length,

            );


        // ====================================
        // Level-specific enemies
        // ====================================

        const enemies = [];


        config.enemies.forEach(

            (
                [
                    x,
                    speedMultiplier,
                    patrolRadius,
                ],

                i,

            ) => {


                // 穴の近くには敵を置かない

                if (
                    !safeGround(
                        x + 16,
                        gaps,
                        40
                    )
                ) {

                    return;

                }


                // 開始地点とチェックポイント
                // のすぐ近くには置かない

                if (
                    x < 200
                    || Math.abs(
                        x - checkpointX
                    ) < 120
                ) {

                    return;

                }


                // =================================
                // Find ground section
                // =================================

                let segmentStart = 0;

                let segmentEnd =
                    config.length;


                for (
                    const [gapX, gapW]
                    of gaps
                ) {

                    const gapEnd =
                        gapX + gapW;


                    if (
                        x >= gapEnd
                    ) {

                        segmentStart =
                            gapEnd;

                    } else if (
                        x < gapX
                    ) {

                        segmentEnd =
                            gapX;

                        break;

                    }

                }


                // =================================
                // Patrol range
                // =================================

                const enemyWidth =
                    33;


                const minX =
                    Math.max(

                        80,

                        segmentStart + 10,

                        x - patrolRadius,

                    );


                const maxX =
                    Math.min(

                        config.length - 115,

                        segmentEnd
                            - enemyWidth
                            - 10,

                        x + patrolRadius,

                    );


                if (
                    minX > maxX
                    || x < minX
                    || x > maxX
                ) {

                    return;

                }


                // =================================
                // Create enemy
                // =================================

                enemies.push({

                    x: x,

                    y:
                        GROUND - 32,

                    w: enemyWidth,

                    h: 32,

                    home: x,

                    min: minX,

                    max: maxX,

                    dir:
                        i % 2 === 0
                            ? -1
                            : 1,

                    speed:
                        config.enemySpeed
                        * speedMultiplier,

                    alive: true,

                });

            }

        );


        // ====================================
        // Return world
        // ====================================

        return {

            ...config,

            surfaces: surfaces,

            coins: coins,

            enemies: enemies,

            checkpointX: checkpointX,

            flagX:
                config.length - 126,

            // 動く足場・コイン用の時間
            motionTime: 0,

        };

    }


    
    /* ========================================
    Moving Platforms and Coins
    ======================================== */

    function updateMovingObjects(dt) {

        if (!world) {
            return;
        }

        // アニメーション時間を進める
        world.motionTime += dt;

        const t = world.motionTime;


                
        /* ========================================
        LEVEL 5 - Moving Platforms
        ======================================== */

        if (selectedLevel === 5) {

            for (
                const platform
                of world.surfaces
            ) {

                if (
                    platform.kind !== "platform"
                    || !platform.motion
                ) {

                    continue;

                }


                const motion =
                    platform.motion;


                // 移動前の位置を保存
                const oldX =
                    platform.x;

                const oldY =
                    platform.y;


                // ====================================
                // Horizontal movement
                // ====================================

                if (
                    motion.axis === "horizontal"
                ) {

                    platform.x =

                        platform.baseX

                        + Math.sin(
                            t * motion.speed
                        )

                        * motion.amplitude

                        * motion.direction;


                    // 上下方向には動かさない
                    platform.y =
                        platform.baseY;

                }


                // ====================================
                // Vertical movement
                // ====================================

                else {

                    platform.y =

                        platform.baseY

                        + Math.sin(
                            t * motion.speed
                        )

                        * motion.amplitude

                        * motion.direction;


                    // 左右方向には動かさない
                    platform.x =
                        platform.baseX;

                }


                // ====================================
                // Calculate movement
                // ====================================

                const dx =
                    platform.x - oldX;

                const dy =
                    platform.y - oldY;


                // ====================================
                // Carry player
                // ====================================

                // 足場に乗っている場合、
                // プレイヤーも一緒に移動する

                if (
                    hero.onGround
                    && hero.support === platform
                ) {

                    hero.x += dx;

                    hero.y += dy;

                }

            }

        }


        // LEVEL 1〜3はコインを動かさない
        if (selectedLevel < 4) {

            return;

        }


        // ====================================
        // LEVEL 4 & 5 - Moving Coins
        // ====================================

        for (
            const coin
            of world.coins
        ) {

            if (coin.taken) {
                continue;
            }

            const index =
                coin.motionIndex;


            // =================================
            // 足場の上にあるコイン
            // =================================

            if (coin.platform) {

                const platform =
                    coin.platform;


                // 足場に追従しながら左右にも動く
                coin.x =
                    platform.x
                    + platform.w / 2
                    + Math.sin(
                        t * (
                            1.5
                            + (index % 4) * 0.25
                        )
                    )
                    * (
                        selectedLevel === 5
                            ? 18
                            : 13
                    );


                // 上下に浮遊
                coin.y =
                    platform.y
                    - 26
                    + Math.sin(
                        t * (
                            2.1
                            + (index % 3) * 0.35
                        )
                    )
                    * 7;

            }


            // =================================
            // 地面・穴の上にあるコイン
            // =================================

            else {

                const amplitudeX =
                    selectedLevel === 5
                        ? 32
                        : 18;

                const amplitudeY =
                    selectedLevel === 5
                        ? 16
                        : 10;


                // 左右移動
                coin.x =
                    coin.baseX
                    + Math.sin(
                        t * (
                            1.4
                            + (index % 5) * 0.28
                        )
                    )
                    * amplitudeX;


                // 上下移動
                coin.y =
                    coin.baseY
                    + Math.sin(
                        t * (
                            1.9
                            + (index % 4) * 0.32
                        )
                    )
                    * amplitudeY;

            }

        }

    }

    function status() {
        ui.selectedLevel.textContent = String(selectedLevel);
        ui.currentLevel.textContent = String(selectedLevel);
        ui.score.textContent = String(score);
        ui.lives.textContent = lives > 0 ? "❤️".repeat(lives) : "0";
        ui.time.textContent = String(Math.max(0, Math.ceil(timeLeft)));
    }

    function overlay(icon, label, title, message, buttonText) {
        ui.overlayIcon.textContent = icon;
        ui.overlayLabel.textContent = label;
        ui.overlayTitle.textContent = title;
        ui.overlayMessage.textContent = message;
        ui.overlayButton.textContent = buttonText;
        ui.overlay.hidden = false;
    }

    function clearInputs() {
        pressed.left = false;
        pressed.right = false;
        jumpBuffer = 0;
        pointers.clear();
        document.querySelectorAll(".jump-direction,.jump-action").forEach(b => b.classList.remove("is-held"));
    }

    function updateControls() {
        const running = mode === "playing" || mode === "paused";
        ui.levelButtons.forEach(b => { b.disabled = running; });
        ui.pause.disabled = !running;
        ui.quit.disabled = !running;
        ui.pause.textContent = mode === "paused" ? "▶ 再開" : "⏸ 一時停止";
    }

    function resetWorld() {
        world = createWorld(selectedLevel);
        hero = {
            x: 82,
            y: GROUND - HERO_H,
            w: HERO_W,
            h: HERO_H,
            vx: 0,
            vy: 0,
            onGround: true,
            // 現在乗っている足場
            support: null,
            face: 1,
        };
        score = 0;
        timeLeft = world.time;
        checkpoint = 82;
        checkpointReached = false;
        cameraX = 0;
        invulnerable = 0;
        jumpBuffer = 0;
        coyote = .12;
        particles = [];
        popup = [];
        clearInputs();
        status();
        render(0);
    }

    function selectLevel(level) {
        if (!LEVELS[level] || mode === "playing" || mode === "paused") return;
        selectedLevel = level;
        mode = "ready";
        ui.levelButtons.forEach(b => {
            const active = Number(b.dataset.level) === level;
            b.classList.toggle("is-active", active);
            b.setAttribute("aria-pressed", String(active));
        });
        resetWorld();
        overlay("🍄", "READY?", `LEVEL ${level}`, `${LEVELS[level].name}：左右に移動してジャンプ！ コインを集めて旗まで進もう。`, "ゲームスタート");
        ui.saveStatus.textContent = "";
        updateControls();
        loadRanking(level);
    }

    function begin() {
        if (raf !== null) cancelAnimationFrame(raf);
        mode = "playing";
        resetWorld();
        ui.overlay.hidden = true;
        ui.saveStatus.textContent = "";
        updateControls();
        lastFrame = 0;
        accumulator = 0;
        raf = requestAnimationFrame(frame);
    }

    function pause() {
        if (mode !== "playing") return;
        mode = "paused";
        clearInputs();
        overlay("⏸", "PAUSED", "一時停止中", "準備ができたら再開しよう！", "▶ 再開");
        updateControls();
    }

    function resume() {
        if (mode !== "paused") return;
        mode = "playing";
        lastFrame = 0;
        accumulator = 0;
        ui.overlay.hidden = true;
        updateControls();
    }

    function quit() {
        if (mode !== "playing" && mode !== "paused") return;
        if (raf !== null) cancelAnimationFrame(raf);
        raf = null;
        mode = "ready";
        resetWorld();
        overlay("🍄", "READY?", `LEVEL ${selectedLevel}`, "レベルを選んで、また挑戦しよう！", "ゲームスタート");
        ui.saveStatus.textContent = "";
        updateControls();
    }

    function addPopup(x, y, text, color = "#fff9ae") {
        popup.push({ x, y, text, color, time: .9 });
    }

    function finish(won) {
        if (mode !== "playing") return;
        if (won) {
            const bonus = 500 + Math.ceil(timeLeft) * 10;
            score += bonus;
            addPopup(hero.x, hero.y - 10, `+${bonus}`);
        }
        const level = selectedLevel;
        const finalScore = score;
        mode = "finished";
        clearInputs();
        status();
        updateControls();
        overlay(won ? "🏆" : "💫", won ? "LEVEL CLEAR!" : "GAME OVER",
            won ? "ゴール！" : "もう一度挑戦！",
            `LEVEL ${level} ／ ${finalScore} 点${won ? "（クリアボーナス込み）" : ""}`,
            "もう一度遊ぶ");
        saveScore(level, finalScore);
    }

    function hurt(force = false) {

        if (
            mode !== "playing"
            || (
                !force
                && invulnerable > 0
            )
        ) {

            return;

        }
        lives--;
        status();
        if (lives <= 0) { finish(false); return; }
        hero.x = checkpoint;
        hero.y = GROUND - HERO_H;
        hero.vx = 0;
        hero.vy = 0;
        hero.onGround = true;
        hero.support = null;
        invulnerable = 1.8;
        coyote = .12;
        jumpBuffer = 0;
        cameraX = clamp(hero.x - 175, 0, world.length - VIEW_W);
        clearInputs();
        addPopup(hero.x, hero.y - 20, "がんばれ！", "#ffef87");
    }

    function update(dt) {
        if (mode !== "playing") return;
        timeLeft = Math.max(0, timeLeft - dt);
        if (timeLeft <= 0) { finish(false); return; }
        invulnerable = Math.max(0, invulnerable - dt);
        jumpBuffer = Math.max(0, jumpBuffer - dt);
        coyote = Math.max(0, coyote - dt);
        updateMovingObjects(dt);

        const horizontal = Number(pressed.right) - Number(pressed.left);
        hero.vx = horizontal * world.speed;
        if (horizontal) hero.face = horizontal;
        if (
            jumpBuffer > 0
            && (
                hero.onGround
                || coyote > 0
            )
        ) {

            hero.vy =
                JUMP_VELOCITY;
            hero.onGround =
                false;
            // 足場から離れた
            hero.support =
                null;
            coyote = 0;
            jumpBuffer = 0;
        }

        hero.x = clamp(hero.x + hero.vx * dt, 0, world.length - hero.w);
        const beforeBottom = hero.y + hero.h;
        hero.vy = Math.min(hero.vy + GRAVITY * dt, 1000);
        hero.y += hero.vy * dt;
                
        /* ========================================
        Landing on Platforms
        ======================================== */

        hero.onGround = false;

        // 現在の足場を解除
        hero.support = null;


        // 上からの着地判定

        if (hero.vy >= 0) {

            for (
                const p
                of world.surfaces
            ) {

                // 足場と横方向が重なっていない
                if (
                    hero.x + hero.w <= p.x
                    || hero.x >= p.x + p.w
                ) {

                    continue;

                }


                // 上から足場に着地した
                if (
                    beforeBottom <= p.y + 5
                    && hero.y + hero.h >= p.y
                ) {

                    hero.y =
                        p.y - hero.h;

                    hero.vy = 0;

                    hero.onGround = true;

                    coyote = 0.11;


                    // 浮いている足場なら記録する
                    hero.support =
                        p.kind === "platform"
                            ? p
                            : null;

                }

            }

        }

        if (hero.y > VIEW_H + 100) {
            hurt(true);
            if (mode !== "playing") {
                return;
            }
        }

        // コインの当たり判定（重心からの距離）。
        const midX = hero.x + hero.w / 2;
        const midY = hero.y + hero.h / 2;
        for (const coin of world.coins) {
            if (!coin.taken && Math.abs(midX - coin.x) < 23 && Math.abs(midY - coin.y) < 30) {
                coin.taken = true;
                score += 50;
                addPopup(coin.x, coin.y, "+50");
            }
        }

        for (const enemy of world.enemies) {
            if (!enemy.alive) continue;
            const nextX =
                enemy.x
                + enemy.dir
                * enemy.speed
                * dt;
            
            for (const enemy of world.enemies) {

                if (!enemy.alive) {
                    continue;
                }

                // 敵ごとの移動速度
                const nextX =
                    enemy.x
                    + enemy.dir
                    * enemy.speed
                    * dt;


                // 巡回範囲の端で方向転換
                if (
                    nextX < enemy.min
                    || nextX > enemy.max
                ) {

                    enemy.dir *= -1;

                } else {

                    enemy.x = nextX;

                }


                // プレイヤーとの接触判定
                if (!overlap(hero, enemy)) {
                    continue;
                }


                // 上から踏んだ場合
                const stomp =
                    hero.vy > 0
                    && beforeBottom <= enemy.y + 14;


                if (stomp) {

                    enemy.alive = false;

                    hero.vy = -480;

                    hero.onGround = false;

                    score += 100;

                    addPopup(
                        enemy.x,
                        enemy.y - 15,
                        "+100"
                    );

                } else if (
                    invulnerable <= 0
                ) {

                    hurt();

                    if (mode !== "playing") {
                        return;
                    }

                    break;

                }

            }

            if (nextX < enemy.min || nextX > enemy.max || !safeGround(nextX + enemy.w / 2, world.gaps, 5)) enemy.dir *= -1;
            else enemy.x = nextX;
            if (!overlap(hero, enemy)) continue;
            const stomp = hero.vy > 0 && beforeBottom <= enemy.y + 14;
            if (stomp) {
                enemy.alive = false;
                hero.vy = -480;
                hero.onGround = false;
                score += 100;
                addPopup(enemy.x, enemy.y - 15, "+100");
            } else if (invulnerable <= 0) {
                hurt();
                if (mode !== "playing") return;
                break;
            }
        }

        if (!checkpointReached && hero.x >= world.checkpointX) {
            checkpointReached = true;
            checkpoint = world.checkpointX;
            addPopup(checkpoint, GROUND - 105, "CHECKPOINT!", "#a3ffce");
        }
        if (hero.x + hero.w >= world.flagX) { finish(true); return; }
        for (const p of popup) { p.time -= dt; p.y -= 25 * dt; }
        popup = popup.filter(p => p.time > 0);
        cameraX += (clamp(hero.x - VIEW_W * .32, 0, world.length - VIEW_W) - cameraX) * Math.min(1, dt * 9);
        status();
    }

    function roundedRect(x, y, w, h, r, fill) {
        ctx.fillStyle = fill;
        ctx.beginPath();
        ctx.roundRect(x, y, w, h, r);
        ctx.fill();
    }

    
    /* ========================================
    World Background
    ======================================== */

    function drawBackground(timestamp = 0) {

        const theme =
            STAGE_THEMES[selectedLevel];

        const level =
            selectedLevel;

        const t =
            timestamp / 1000;


        // ========================================
        // Sky
        // ========================================

        const sky =
            ctx.createLinearGradient(
                0,
                0,
                0,
                VIEW_H
            );

        sky.addColorStop(
            0,
            theme.skyTop
        );

        sky.addColorStop(
            1,
            theme.skyBottom
        );

        ctx.fillStyle = sky;

        ctx.fillRect(
            0,
            0,
            VIEW_W,
            VIEW_H
        );


        // ========================================
        // Drawing helpers
        // ========================================

        function circle(
            x,
            y,
            r,
            color
        ) {

            ctx.fillStyle = color;

            ctx.beginPath();

            ctx.arc(
                x,
                y,
                r,
                0,
                Math.PI * 2
            );

            ctx.fill();

        }


        function hill(
            x,
            y,
            w,
            h,
            color
        ) {

            ctx.fillStyle = color;

            ctx.beginPath();

            ctx.ellipse(
                x,
                y,
                w,
                h,
                0,
                Math.PI,
                0
            );

            ctx.fill();

        }


        function triangle(
            x,
            y,
            w,
            h,
            color
        ) {

            ctx.fillStyle = color;

            ctx.beginPath();

            ctx.moveTo(
                x,
                y
            );

            ctx.lineTo(
                x - w / 2,
                y + h
            );

            ctx.lineTo(
                x + w / 2,
                y + h
            );

            ctx.closePath();

            ctx.fill();

        }


        function cloud(
            x,
            y,
            color = "#ffffffcc"
        ) {

            circle(
                x,
                y,
                20,
                color
            );

            circle(
                x + 23,
                y - 9,
                25,
                color
            );

            circle(
                x + 49,
                y,
                19,
                color
            );

        }


        // ========================================
        // LEVEL 1
        // Green Meadow
        // ========================================

        if (level === 1) {

            // Sun

            circle(
                790 - cameraX * 0.04,
                90,
                44,
                "#fff3ab"
            );


            // Clouds

            for (
                let i = 0;
                i < 12;
                i++
            ) {

                const x =
                    i * 195
                    - cameraX * 0.16;

                cloud(
                    x,
                    70 + (i % 3) * 42
                );

            }


            // Distant hills

            for (
                let i = 0;
                i < 18;
                i++
            ) {

                const x =
                    i * 180
                    - cameraX * 0.28;

                hill(
                    x,
                    GROUND + 26,
                    150,
                    110,
                    "#a8e3a4"
                );

            }


            // Foreground hills

            for (
                let i = 0;
                i < 20;
                i++
            ) {

                const x =
                    i * 155
                    - cameraX * 0.43;

                hill(
                    x,
                    GROUND + 35,
                    115,
                    62,
                    "#79ce91"
                );

            }

        }


        // ========================================
        // LEVEL 2
        // Desert
        // ========================================

        else if (level === 2) {

            // Hot sun

            circle(
                750 - cameraX * 0.025,
                98,
                62,
                "#ffe5a0"
            );


            // Distant dunes

            for (
                let i = 0;
                i < 15;
                i++
            ) {

                const x =
                    i * 230
                    - cameraX * 0.24;

                hill(
                    x,
                    GROUND + 40,
                    190,
                    125,
                    "#edb773"
                );

            }


            // Front dunes

            for (
                let i = 0;
                i < 20;
                i++
            ) {

                const x =
                    i * 175
                    - cameraX * 0.42;

                hill(
                    x,
                    GROUND + 32,
                    140,
                    70,
                    "#f8ce87"
                );

            }


            // Cactuses

            for (
                let i = 0;
                i < 12;
                i++
            ) {

                const x =
                    i * 310 + 115
                    - cameraX * 0.52;

                const y =
                    GROUND - 37;

                ctx.fillStyle =
                    "#4b9b75";

                roundedRect(
                    x,
                    y,
                    15,
                    43,
                    7,
                    "#4b9b75"
                );

                roundedRect(
                    x - 13,
                    y + 13,
                    12,
                    8,
                    4,
                    "#4b9b75"
                );

                roundedRect(
                    x + 14,
                    y + 23,
                    13,
                    8,
                    4,
                    "#4b9b75"
                );

                roundedRect(
                    x - 13,
                    y + 1,
                    8,
                    19,
                    4,
                    "#4b9b75"
                );

                roundedRect(
                    x + 19,
                    y + 10,
                    8,
                    19,
                    4,
                    "#4b9b75"
                );

            }

        }


        // ========================================
        // LEVEL 3
        // Magic Forest
        // ========================================

        else if (level === 3) {

            // Distant forest

            for (
                let i = 0;
                i < 22;
                i++
            ) {

                const x =
                    i * 135
                    - cameraX * 0.22;

                ctx.fillStyle =
                    "#326e65";

                ctx.fillRect(
                    x,
                    165,
                    19,
                    GROUND - 165
                );

                circle(
                    x + 10,
                    170,
                    77,
                    "#39796f"
                );

                circle(
                    x - 32,
                    197,
                    48,
                    "#438b79"
                );

            }


            // Foreground trees

            for (
                let i = 0;
                i < 15;
                i++
            ) {

                const x =
                    i * 220
                    - cameraX * 0.48;

                ctx.fillStyle =
                    "#365b50";

                ctx.fillRect(
                    x,
                    200,
                    25,
                    GROUND - 200
                );

                circle(
                    x + 12,
                    178,
                    65,
                    "#4a9b79"
                );

                circle(
                    x - 31,
                    205,
                    43,
                    "#5cae86"
                );

                circle(
                    x + 48,
                    198,
                    46,
                    "#56a780"
                );

            }


            // Fireflies

            for (
                let i = 0;
                i < 65;
                i++
            ) {

                const x =
                    rand(i, 3) * VIEW_W;

                const y =
                    rand(i, 8) * 370;

                const pulse =
                    0.45
                    + 0.45
                    * Math.sin(
                        t * 2.1 + i
                    );

                ctx.globalAlpha =
                    Math.max(
                        0.08,
                        pulse
                    );

                circle(
                    x,
                    y,
                    2.3,
                    "#eaff9a"
                );

            }

            ctx.globalAlpha = 1;

        }


        // ========================================
        // LEVEL 4
        // Snow World
        // ========================================

        else if (level === 4) {

            // Moon

            circle(
                795 - cameraX * 0.03,
                85,
                38,
                "#f4faff"
            );


            // Distant mountains

            for (
                let i = 0;
                i < 13;
                i++
            ) {

                const x =
                    i * 275
                    - cameraX * 0.22;

                triangle(
                    x,
                    105 + (i % 3) * 28,
                    290,
                    345,
                    "#94badb"
                );

                triangle(
                    x,
                    105 + (i % 3) * 28,
                    94,
                    110,
                    "#eaf7ff"
                );

            }


            // Pine trees

            for (
                let i = 0;
                i < 16;
                i++
            ) {

                const x =
                    i * 190
                    - cameraX * 0.45;

                const y =
                    GROUND;

                ctx.fillStyle =
                    "#557b87";

                ctx.fillRect(
                    x - 5,
                    y - 28,
                    10,
                    28
                );

                triangle(
                    x,
                    y - 115,
                    80,
                    105,
                    "#457e8d"
                );

                triangle(
                    x,
                    y - 145,
                    60,
                    90,
                    "#5a99a3"
                );

                triangle(
                    x,
                    y - 145,
                    32,
                    35,
                    "#f3fcff"
                );

            }


            // Falling snow

            for (
                let i = 0;
                i < 85;
                i++
            ) {

                const x = (
                    rand(i, 4) * VIEW_W
                    + t * (9 + i % 5)
                ) % VIEW_W;

                const y = (
                    rand(i, 9) * VIEW_H
                    + t * (18 + i % 9)
                ) % VIEW_H;

                circle(
                    x,
                    y,
                    1.8 + i % 3,
                    "#ffffffb9"
                );

            }

        }


        // ========================================
        // LEVEL 5
        // Volcano World
        // ========================================

        else if (level === 5) {

            // Red moon

            circle(
                765 - cameraX * 0.03,
                94,
                54,
                "#ff8064"
            );


            // Distant volcanoes

            for (
                let i = 0;
                i < 11;
                i++
            ) {

                const x =
                    i * 310
                    - cameraX * 0.23;

                const top =
                    150 + (i % 3) * 42;

                triangle(
                    x,
                    top,
                    340,
                    GROUND - top + 60,
                    "#483044"
                );


                // Lava flowing down

                ctx.strokeStyle =
                    "#ff653e";

                ctx.lineWidth = 5;

                ctx.beginPath();

                ctx.moveTo(
                    x,
                    top + 7
                );

                ctx.lineTo(
                    x + 20,
                    top + 75
                );

                ctx.lineTo(
                    x + 5,
                    top + 115
                );

                ctx.stroke();

            }


            // Red distant mountains

            for (
                let i = 0;
                i < 17;
                i++
            ) {

                const x =
                    i * 200
                    - cameraX * 0.42;

                triangle(
                    x,
                    GROUND - 105,
                    220,
                    150,
                    "#6b3547"
                );

            }


            // Falling embers

            for (
                let i = 0;
                i < 85;
                i++
            ) {

                const x = (
                    rand(i, 6) * VIEW_W
                    + t * (8 + i % 7)
                ) % VIEW_W;

                const y = (
                    rand(i, 12) * VIEW_H
                    - t * (15 + i % 11)
                    + VIEW_H * 100
                ) % VIEW_H;

                circle(
                    x,
                    y,
                    1.5 + i % 3,
                    i % 2
                        ? "#ffb66c"
                        : "#ff6547"
                );

            }


            // Lava glow

            const lavaGlow =
                ctx.createLinearGradient(
                    0,
                    GROUND - 70,
                    0,
                    VIEW_H
                );

            lavaGlow.addColorStop(
                0,
                "#ff5a3100"
            );

            lavaGlow.addColorStop(
                1,
                "#ff643666"
            );

            ctx.fillStyle =
                lavaGlow;

            ctx.fillRect(
                0,
                GROUND - 70,
                VIEW_W,
                VIEW_H - GROUND + 70
            );

        }

    }

    
    /* ========================================
    World Ground
    ======================================== */

    function drawGround(p) {

        const theme =
            STAGE_THEMES[selectedLevel];

        const x =
            p.x - cameraX;

        if (
            x > VIEW_W + 40
            || x + p.w < -40
        ) {
            return;
        }

        const left =
            Math.max(0, x);

        const width =
            Math.min(
                VIEW_W,
                x + p.w
            ) - left;

        if (width <= 0) {
            return;
        }


        // Ground body

        ctx.fillStyle =
            theme.ground;

        ctx.fillRect(
            left,
            p.y + 8,
            width,
            VIEW_H - p.y + 120
        );


        // Ground surface

        ctx.fillStyle =
            theme.groundTop;

        ctx.fillRect(
            left,
            p.y,
            width,
            13
        );


        // Surface highlight

        ctx.fillStyle =
            selectedLevel === 5
                ? "#ffbd72"
                : "#ffffff77";

        ctx.fillRect(
            left,
            p.y,
            width,
            4
        );


        // Level-specific ground details

        for (
            let wx =
                Math.ceil(p.x / 45) * 45;

            wx < p.x + p.w;

            wx += 45
        ) {

            const sx =
                wx - cameraX;

            if (
                sx < -10
                || sx > VIEW_W + 10
            ) {
                continue;
            }

            const detailY =
                p.y
                + 29
                + (
                    Math.floor(wx / 45) % 2
                ) * 23;


            if (selectedLevel === 1) {

                ctx.fillStyle =
                    "#b88c61";

            } else if (selectedLevel === 2) {

                ctx.fillStyle =
                    "#f1c184";

            } else if (selectedLevel === 3) {

                ctx.fillStyle =
                    "#7e6b5a";

            } else if (selectedLevel === 4) {

                ctx.fillStyle =
                    "#c8e9f6";

            } else {

                ctx.fillStyle =
                    "#ff7447";

            }


            ctx.fillRect(
                sx,
                detailY,
                17,
                9
            );

        }

    }


        
    /* ========================================
    World Platforms
    ======================================== */

    function drawPlatform(p) {

        const theme =
            STAGE_THEMES[selectedLevel];

        const x =
            p.x - cameraX;

        if (
            x + p.w < 0
            || x > VIEW_W
        ) {
            return;
        }


        // Platform body

        roundedRect(
            x,
            p.y,
            p.w,
            17,
            5,
            theme.platform
        );


        // Platform surface

        roundedRect(
            x,
            p.y - 3,
            p.w,
            8,
            4,
            theme.platformTop
        );


        // Highlight

        ctx.fillStyle =
            "#ffffff66";

        ctx.fillRect(
            x + 8,
            p.y + 6,
            p.w - 16,
            2
        );

    }


    function drawHero(t) {
        if (invulnerable > 0 && Math.floor(t / 100) % 2) return;
        const x = hero.x - cameraX;
        const y = hero.y;
        const running = Math.abs(hero.vx) > 0 && hero.onGround;
        const stride = running ? Math.sin(t / 75) * 3 : 0;
        roundedRect(x + 5, y + 28 + stride, 10, 17, 3, "#365d79");
        roundedRect(x + 18, y + 28 - stride, 10, 17, 3, "#365d79");
        roundedRect(x + 3, y + 13, 27, 25, 8, "#59aece");
        roundedRect(x + 7, y + 18, 19, 19, 6, "#8cdbed");
        ctx.fillStyle = "#ffd0a6"; ctx.beginPath(); ctx.arc(x + 16, y + 13, 12, 0, Math.PI * 2); ctx.fill();
        roundedRect(x + 2, y + 0, 28, 8, 5, "#e86985");
        roundedRect(x + 8, y - 7, 17, 10, 5, "#f18198");
        ctx.fillStyle = "#344258";
        ctx.beginPath(); ctx.arc(x + 16 + hero.face * 5, y + 12, 2.5, 0, Math.PI * 2); ctx.fill();
        ctx.fillStyle = "#ffe3bd"; ctx.fillRect(x + 1, y + 27, 6, 7); ctx.fillRect(x + 26, y + 27, 6, 7);
    }

    function drawEnemy(e, t) {
        const x = e.x - cameraX;
        const y = e.y + Math.sin(t / 190 + e.home) * 1.4;
        roundedRect(x + 1, y + 9, e.w - 2, 23, 12, "#b26cd0");
        ctx.fillStyle = "#d394ef";
        ctx.beginPath(); ctx.arc(x + e.w / 2, y + 12, 15, Math.PI, 0); ctx.fill();
        ctx.fillStyle = "white";
        ctx.beginPath(); ctx.arc(x + 11, y + 13, 4, 0, Math.PI * 2); ctx.arc(x + 23, y + 13, 4, 0, Math.PI * 2); ctx.fill();
        ctx.fillStyle = "#49375e";
        ctx.beginPath(); ctx.arc(x + 11 + e.dir, y + 13, 2, 0, Math.PI * 2); ctx.arc(x + 23 + e.dir, y + 13, 2, 0, Math.PI * 2); ctx.fill();
    }

    function render(timestamp) {
        if (!world) return;
        ctx.clearRect(0, 0, VIEW_W, VIEW_H);
        drawBackground(timestamp);
        ctx.fillStyle = "#b5f2d5";
        for (let i = 0; i < world.length / 90; i++) {
            const x = i * 90 - cameraX;
            if (x < -10 || x > VIEW_W + 10) continue;
            ctx.beginPath(); ctx.arc(x, GROUND - 6, 3, 0, Math.PI * 2); ctx.fill();
        }
        for (const surface of world.surfaces) {
            if (surface.kind === "ground") drawGround(surface);
            else drawPlatform(surface);
        }
        const checkX = world.checkpointX - cameraX;
        if (checkX > -30 && checkX < VIEW_W + 30) {
            ctx.fillStyle = "#658276"; ctx.fillRect(checkX, GROUND - 93, 5, 93);
            ctx.fillStyle = checkpointReached ? "#59d69b" : "#d2edbd";
            ctx.beginPath(); ctx.moveTo(checkX + 5, GROUND - 93); ctx.lineTo(checkX + 57, GROUND - 76);
            ctx.lineTo(checkX + 5, GROUND - 62); ctx.fill();
        }
        const flagX = world.flagX - cameraX;
        if (flagX > -60 && flagX < VIEW_W + 60) {
            ctx.fillStyle = "#6a7c96"; ctx.fillRect(flagX, GROUND - 170, 6, 170);
            ctx.fillStyle = "#f5ba59";
            ctx.beginPath(); ctx.moveTo(flagX + 6, GROUND - 166); ctx.lineTo(flagX + 80, GROUND - 144);
            ctx.lineTo(flagX + 6, GROUND - 118); ctx.fill();
            roundedRect(flagX - 17, GROUND - 4, 43, 5, 2, "#798d8c");
        }
        for (const coin of world.coins) {
            if (coin.taken) continue;
            const x = coin.x - cameraX;
            if (x < -15 || x > VIEW_W + 15) continue;
            const y = coin.y + Math.sin(timestamp / 230 + coin.x) * 3;
            ctx.fillStyle = "#e8a83e"; ctx.beginPath(); ctx.ellipse(x, y, 11, 14, 0, 0, Math.PI * 2); ctx.fill();
            ctx.fillStyle = "#ffdf6d"; ctx.beginPath(); ctx.ellipse(x - 2, y - 1, 8, 11, 0, 0, Math.PI * 2); ctx.fill();
            ctx.fillStyle = "#fff9bd"; ctx.fillRect(x - 4, y - 7, 3, 9);
        }
        for (const enemy of world.enemies) if (enemy.alive && enemy.x - cameraX > -50 && enemy.x - cameraX < VIEW_W + 50) drawEnemy(enemy, timestamp);
        drawHero(timestamp);
        for (const p of popup) {
            ctx.save(); ctx.globalAlpha = clamp(p.time * 1.8, 0, 1);
            ctx.fillStyle = p.color; ctx.strokeStyle = "#364356"; ctx.lineWidth = 3;
            ctx.font = "900 22px sans-serif"; ctx.textAlign = "center";
            ctx.strokeText(p.text, p.x - cameraX, p.y); ctx.fillText(p.text, p.x - cameraX, p.y);
            ctx.restore();
        }
        ctx.fillStyle = "#2f624eaa"; ctx.fillRect(23, 20, 235, 9);
        ctx.fillStyle = "#67d5aa"; ctx.fillRect(23, 20, 235 * clamp(hero.x / world.flagX, 0, 1), 9);
        ctx.strokeStyle = "#ffffff88"; ctx.strokeRect(23, 20, 235, 9);
    }

    function frame(timestamp) {
        if (mode !== "playing" && mode !== "paused") { raf = null; return; }
        const elapsed = lastFrame ? Math.min((timestamp - lastFrame) / 1000, .06) : 0;
        lastFrame = timestamp;
        if (mode === "playing") {
            accumulator += elapsed;
            while (accumulator >= STEP && mode === "playing") {
                accumulator -= STEP;
                update(STEP);
            }
        }
        render(timestamp);
        raf = mode === "playing" || mode === "paused" ? requestAnimationFrame(frame) : null;
    }

    function jump() {
        if (mode === "playing") jumpBuffer = .15;
    }

    function setDirection(direction, down) {
        if (mode !== "playing") return;
        if (direction === "jump") { if (down) jump(); return; }
        if (direction === "left" || direction === "right") pressed[direction] = down;
    }

    function renderRanking(data, level) {
        ui.rankingLevel.textContent = String(level);
        ui.personalBest.textContent = data.personal_best == null ? "--" : String(data.personal_best);
        ui.rankingList.replaceChildren();
        if (!data.entries?.length) {
            const li = document.createElement("li");
            li.className = "jump-ranking-empty"; li.textContent = "まだ記録がない";
            ui.rankingList.appendChild(li); return;
        }
        for (const entry of data.entries) {
            const li = document.createElement("li");
            if (entry.is_me) li.classList.add("is-me");
            const rank = document.createElement("span"); rank.className = "jump-rank-position"; rank.textContent = String(entry.rank);
            const name = document.createElement("strong"); name.textContent = entry.name;
            const pts = document.createElement("span"); pts.textContent = `${entry.score} 点`;
            li.append(rank, name, pts); ui.rankingList.appendChild(li);
        }
    }

    async function loadRanking(level) {
        const id = ++requestId;
        ui.rankingLevel.textContent = String(level);
        ui.personalBest.textContent = "--";
        const li = document.createElement("li"); li.className = "jump-ranking-empty";
        li.textContent = "ランキングを読み込み中…"; ui.rankingList.replaceChildren(li);
        try {
            const response = await fetch(`${rankingUrl}?level=${level}`, { credentials: "same-origin" });
            if (!response.ok) throw new Error("ranking failed");
            const data = await response.json();
            if (data.ok && id === requestId && selectedLevel === level) renderRanking(data, level);
        } catch (error) {
            if (id === requestId && selectedLevel === level) li.textContent = "ランキングを読み込めなかった。再読み込みしてね。";
            console.warn("ランキング取得エラー", error);
        }
    }

    async function saveScore(level, resultScore) {
        const id = ++saveRequestId;
        ui.saveStatus.textContent = "スコアを保存中…";
        try {
            const response = await fetch(scoreUrl, {
                method: "POST", credentials: "same-origin",
                headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
                body: JSON.stringify({ game: GAME, level, score: resultScore }),
            });
            if (!response.ok) throw new Error("save failed");
            const data = await response.json();
            if (!data.ok) throw new Error(data.error || "save failed");
            if (selectedLevel === level && id === saveRequestId) {
                requestId++;
                renderRanking(data, level);
                ui.saveStatus.textContent = data.is_new_best ? "🎉 自己ベスト更新！保存したよ。" : "スコアを保存したよ。";
            }
        } catch (error) {
            if (selectedLevel === level && id === saveRequestId) ui.saveStatus.textContent = "保存できなかった。通信状態を確認してね。";
            console.warn("スコア保存エラー", error);
        }
    }

    function syncFullscreen() {
        const active = document.fullscreenElement === shell || shell.classList.contains("is-pseudo-fullscreen");
        shell.classList.toggle("is-fullscreen", active);
        document.body.classList.toggle("jump-fullscreen-active", active);
        ui.fullscreen.hidden = active;
        ui.exitFullscreen.hidden = !active;
    }

    async function enterFullscreen() {
        if (shell.requestFullscreen) {
            try { await shell.requestFullscreen(); syncFullscreen(); return; } catch (error) { /* 擬似全画面に切り替える */ }
        }
        shell.classList.add("is-pseudo-fullscreen"); syncFullscreen();
    }

    async function exitFullscreen() {
        shell.classList.remove("is-pseudo-fullscreen");
        if (document.fullscreenElement === shell) {
            try { await document.exitFullscreen(); } catch (error) { /* ignore */ }
        }
        syncFullscreen();
    }

    function resizeCanvas() {
        const ratio = Math.min(window.devicePixelRatio || 1, 2);
        canvas.width = Math.round(VIEW_W * ratio);
        canvas.height = Math.round(VIEW_H * ratio);
        ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
        if (world) render(0);
    }

    ui.levelButtons.forEach(b => b.addEventListener("click", () => selectLevel(Number(b.dataset.level))));
    ui.overlayButton.addEventListener("click", () => mode === "paused" ? resume() : begin());
    ui.pause.addEventListener("click", () => mode === "paused" ? resume() : pause());
    ui.quit.addEventListener("click", quit);
    ui.fullscreen.addEventListener("click", enterFullscreen);
    ui.exitFullscreen.addEventListener("click", exitFullscreen);
    document.addEventListener("fullscreenchange", syncFullscreen);
    window.addEventListener("resize", resizeCanvas);
    window.addEventListener("blur", pause);
    document.addEventListener("visibilitychange", () => { if (document.hidden) pause(); });

    const keyDirection = {
        ArrowLeft: "left", KeyA: "left", ArrowRight: "right", KeyD: "right",
        Space: "jump", ArrowUp: "jump", KeyW: "jump",
    };
    window.addEventListener("keydown", event => {
        const key = keyDirection[event.code];
        if (key && mode === "playing") {
            event.preventDefault();
            if (key !== "jump" || !event.repeat) setDirection(key, true);
        } else if (event.code === "KeyP" && (mode === "playing" || mode === "paused")) {
            event.preventDefault(); mode === "paused" ? resume() : pause();
        }
    });
    window.addEventListener("keyup", event => {
        const key = keyDirection[event.code];
        if (key && key !== "jump") setDirection(key, false);
    });

    // Pointer capture で左右を押したままジャンプを別の指で押せる。
    document.querySelectorAll(".jump-direction,.jump-action").forEach(button => {
        const direction = button.dataset.direction || "jump";
        button.addEventListener("pointerdown", event => {
            if (mode !== "playing") return;
            event.preventDefault();
            button.setPointerCapture?.(event.pointerId);
            pointers.set(event.pointerId, direction);
            button.classList.add("is-held");
            setDirection(direction, true);
        });
        const release = event => {
            if (pointers.get(event.pointerId) !== direction) return;
            pointers.delete(event.pointerId);
            button.classList.remove("is-held");
            if (direction !== "jump" && ![...pointers.values()].includes(direction)) setDirection(direction, false);
        };
        button.addEventListener("pointerup", release);
        button.addEventListener("pointercancel", release);
        button.addEventListener("lostpointercapture", release);
    });

    resizeCanvas();
    selectLevel(1);
});