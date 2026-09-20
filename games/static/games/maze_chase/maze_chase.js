
document.addEventListener("DOMContentLoaded", () => {
    "use strict";

    const WIDTH = 19;
    const HEIGHT = 19;
    const TILE = 30;
    const WALL = 1;
    const DOT = 2;
    const POWER = 3;
    const EMPTY = 0;
    const GAME = "maze_chase";

    const DIRECTIONS = {
        up: { x: 0, y: -1, angle: -Math.PI / 2 },
        down: { x: 0, y: 1, angle: Math.PI / 2 },
        left: { x: -1, y: 0, angle: Math.PI },
        right: { x: 1, y: 0, angle: 0 },
    };

    const LEVELS = {
        1: { name: "やさしい", enemies: 2, ghostMs: 590, playerMs: 145, random: .50, wall: "#354aa4" },
        2: { name: "ふつう", enemies: 2, ghostMs: 480, playerMs: 138, random: .39, wall: "#366cba" },
        3: { name: "むずかしい", enemies: 3, ghostMs: 380, playerMs: 132, random: .28, wall: "#684bb9" },
        4: { name: "激ムズ", enemies: 3, ghostMs: 310, playerMs: 125, random: .20, wall: "#a34d96" },
        5: { name: "鬼", enemies: 4, ghostMs: 245, playerMs: 120, random: .12, wall: "#b44670" },
    };

    const shell = document.getElementById("maze-shell");
    if (!shell) return;

    const canvas = document.getElementById("maze-canvas");
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const elements = {
        levels: [...document.querySelectorAll(".maze-level-button")],
        selectedLevel: document.getElementById("maze-selected-level"),
        currentLevel: document.getElementById("maze-current-level"),
        score: document.getElementById("maze-score"),
        lives: document.getElementById("maze-lives"),
        dots: document.getElementById("maze-dots"),
        overlay: document.getElementById("maze-overlay"),
        overlayIcon: document.getElementById("maze-overlay-icon"),
        overlayLabel: document.getElementById("maze-overlay-label"),
        overlayTitle: document.getElementById("maze-overlay-title"),
        overlayMessage: document.getElementById("maze-overlay-message"),
        overlayButton: document.getElementById("maze-overlay-button"),
        pause: document.getElementById("maze-pause"),
        quit: document.getElementById("maze-quit"),
        fullscreen: document.getElementById("maze-fullscreen"),
        exitFullscreen: document.getElementById("maze-exit-fullscreen"),
        rankingList: document.getElementById("maze-ranking-list"),
        rankingLevel: document.getElementById("maze-ranking-level"),
        personalBest: document.getElementById("maze-personal-best"),
        saveStatus: document.getElementById("maze-save-status"),
    };

    const scoreUrl = shell.dataset.scoreUrl;
    const rankingUrl = shell.dataset.rankingUrl;
    const csrfToken = shell.dataset.csrfToken;

    let selectedLevel = 1;
    let state = "ready"; // ready, playing, paused, finished
    let grid = [];
    let player = { x: 1, y: 1 };
    let direction = null;
    let requestedDirection = null;
    let ghosts = [];
    let dots = 0;
    let lives = 3;
    let score = 0;
    let elapsed = 0;
    let invincible = 0;
    let frightened = 0;
    let ghostCombo = 0;
    let playerAccumulator = 0;
    let ghostAccumulator = 0;
    let frameId = null;
    let lastFrame = 0;
    let rankingRequestId = 0;
    let swipeStart = null;
    let eatenPopup = null;

    function setWall(map, x, y) {
        if (x > 0 && x < WIDTH - 1 && y > 0 && y < HEIGHT - 1) {
            map[y][x] = WALL;
        }
    }

    function vertical(map, x, start, end, gaps = []) {
        for (let y = start; y <= end; y++) {
            if (!gaps.includes(y)) setWall(map, x, y);
        }
    }

    function horizontal(map, y, start, end, gaps = []) {
        for (let x = start; x <= end; x++) {
            if (!gaps.includes(x)) setWall(map, x, y);
        }
    }

    function cellKey(x, y) {
        return y * WIDTH + x;
    }

    function inBounds(x, y) {
        return x >= 0 && y >= 0 && x < WIDTH && y < HEIGHT;
    }

    function isOpen(x, y) {
        return inBounds(x, y) && grid[y][x] !== WALL;
    }

    function neighbours(x, y) {
        return Object.values(DIRECTIONS)
            .map(dir => ({ x: x + dir.x, y: y + dir.y, dir }))
            .filter(pos => isOpen(pos.x, pos.y));
    }

    // 各レベルで壁の配置を変える。孤立した通路は後で壁にしてクリア不能を防ぐ。
    function makeMaze(level) {
        const map = Array.from({ length: HEIGHT }, (_, y) =>
            Array.from({ length: WIDTH }, (_, x) =>
                (x === 0 || y === 0 || x === WIDTH - 1 || y === HEIGHT - 1) ? WALL : DOT
            )
        );

        if (level === 1) {
            vertical(map, 4, 2, 16, [5, 10, 15]);
            vertical(map, 9, 2, 16, [4, 9, 14]);
            vertical(map, 14, 2, 16, [5, 10, 15]);
            horizontal(map, 5, 2, 16, [3, 7, 11, 15]);
            horizontal(map, 13, 2, 16, [3, 7, 11, 15]);
        } else if (level === 2) {
            horizontal(map, 4, 2, 16, [3, 9, 15]);
            horizontal(map, 9, 2, 16, [3, 9, 15]);
            horizontal(map, 14, 2, 16, [3, 9, 15]);
            vertical(map, 6, 2, 16, [3, 8, 13, 16]);
            vertical(map, 12, 2, 16, [3, 8, 13, 16]);
        } else if (level === 3) {
            horizontal(map, 3, 3, 15, [5, 9, 13]);
            horizontal(map, 15, 3, 15, [5, 9, 13]);
            vertical(map, 3, 3, 15, [5, 9, 13]);
            vertical(map, 15, 3, 15, [5, 9, 13]);
            horizontal(map, 6, 6, 12, [9]);
            horizontal(map, 12, 6, 12, [9]);
            vertical(map, 6, 6, 12, [9]);
            vertical(map, 12, 6, 12, [9]);
            horizontal(map, 9, 2, 5, [3]);
            horizontal(map, 9, 13, 16, [15]);
        } else if (level === 4) {
            for (const x of [3, 7, 11, 15]) {
                vertical(map, x, 2, 16, [4, 8, 12, 16]);
            }
            for (const y of [4, 8, 12, 16]) {
                horizontal(map, y, 2, 16, [2, 5, 9, 13, 16]);
            }
        } else {
            for (const y of [3, 6, 9, 12, 15]) {
                horizontal(map, y, 2, 16, y % 2 ? [3, 9] : [9, 15]);
            }
            vertical(map, 5, 2, 16, [4, 8, 11, 16]);
            vertical(map, 13, 2, 16, [2, 5, 10, 14]);
            vertical(map, 9, 2, 16, [3, 6, 9, 12, 15]);
        }

        map[1][1] = EMPTY;
        grid = map;

        const connected = new Set([cellKey(1, 1)]);
        const queue = [{ x: 1, y: 1 }];
        for (let head = 0; head < queue.length; head++) {
            const { x, y } = queue[head];
            for (const next of neighbours(x, y)) {
                const key = cellKey(next.x, next.y);
                if (connected.has(key)) continue;
                connected.add(key);
                queue.push({ x: next.x, y: next.y });
            }
        }
        for (let y = 1; y < HEIGHT - 1; y++) {
            for (let x = 1; x < WIDTH - 1; x++) {
                if (!connected.has(cellKey(x, y))) map[y][x] = WALL;
            }
        }

        // 四隅に近い到達可能なマスにパワーアイテムを配置する。
        const targets = [{ x: 1, y: 17 }, { x: 17, y: 1 }, { x: 17, y: 17 }, { x: 1, y: 9 }];
        const used = new Set([cellKey(1, 1)]);
        for (const target of targets) {
            const pos = queue
                .filter(p => !used.has(cellKey(p.x, p.y)))
                .sort((a, b) =>
                    (Math.abs(a.x - target.x) + Math.abs(a.y - target.y)) -
                    (Math.abs(b.x - target.x) + Math.abs(b.y - target.y))
                )[0];
            if (pos) {
                map[pos.y][pos.x] = POWER;
                used.add(cellKey(pos.x, pos.y));
            }
        }

        // ゴーストは中央付近の通行可能な別々のマスから出現させる。
        ghosts = [];
        const homes = [{ x: 9, y: 9 }, { x: 8, y: 9 }, { x: 10, y: 9 }, { x: 9, y: 10 }];
        const colors = ["#ff6e91", "#5ce2e6", "#ffba62", "#bc8cff"];
        for (let i = 0; i < LEVELS[level].enemies; i++) {
            const target = homes[i];
            const pos = queue
                .filter(p => !used.has(cellKey(p.x, p.y)) && p.x + p.y >= 8)
                .sort((a, b) =>
                    (Math.abs(a.x - target.x) + Math.abs(a.y - target.y)) -
                    (Math.abs(b.x - target.x) + Math.abs(b.y - target.y))
                )[0];
            if (!pos) continue;
            map[pos.y][pos.x] = EMPTY;
            used.add(cellKey(pos.x, pos.y));
            ghosts.push({ x: pos.x, y: pos.y, home: { ...pos }, direction: null, color: colors[i], stunUntil: 0 });
        }

        dots = map.flat().filter(cell => cell === DOT || cell === POWER).length;
    }

    function updateStatus() {
        elements.selectedLevel.textContent = String(selectedLevel);
        elements.currentLevel.textContent = String(selectedLevel);
        elements.score.textContent = String(score);
        elements.lives.textContent = lives > 0 ? "❤️".repeat(lives) : "0";
        elements.dots.textContent = String(dots);
    }

    function setOverlay({ icon, label, title, message, button }) {
        elements.overlayIcon.textContent = icon;
        elements.overlayLabel.textContent = label;
        elements.overlayTitle.textContent = title;
        elements.overlayMessage.textContent = message;
        elements.overlayButton.textContent = button;
        elements.overlay.hidden = false;
    }

    function updateControls() {
        const running = state === "playing" || state === "paused";
        elements.levels.forEach(button => { button.disabled = running; });
        elements.pause.disabled = !running;
        elements.quit.disabled = !running;
        elements.pause.textContent = state === "paused" ? "▶ 再開" : "⏸ 一時停止";
    }

    function resetBoard() {
        makeMaze(selectedLevel);
        player = { x: 1, y: 1 };
        direction = null;
        requestedDirection = null;
        eatenPopup = null;
        lives = 3;
        score = 0;
        elapsed = 0;
        frightened = 0;
        invincible = 0;
        ghostCombo = 0;
        playerAccumulator = 0;
        ghostAccumulator = 0;
        updateStatus();
        draw(0);
    }

    function selectLevel(level) {
        if (state === "playing" || state === "paused" || !LEVELS[level]) return;
        selectedLevel = level;
        elements.levels.forEach(button => {
            const isActive = Number(button.dataset.level) === level;
            button.classList.toggle("is-active", isActive);
            button.setAttribute("aria-pressed", String(isActive));
        });
        state = "ready";
        resetBoard();
        setOverlay({ icon: "🟡", label: "READY?", title: `LEVEL ${level}`, message: `${LEVELS[level].name}：ドットをすべて食べよう。大きなドットで敵が青くなる！`, button: "ゲームスタート" });
        elements.saveStatus.textContent = "";
        updateControls();
        loadRanking(level);
    }

    function startGame() {
        if (frameId !== null) cancelAnimationFrame(frameId);
        state = "playing";
        resetBoard();
        elements.overlay.hidden = true;
        elements.saveStatus.textContent = "";
        updateControls();
        lastFrame = 0;
        frameId = requestAnimationFrame(frame);
    }

    function pauseGame() {
        if (state !== "playing") return;
        state = "paused";
        setOverlay({ icon: "⏸", label: "PAUSED", title: "一時停止中", message: "準備ができたら、再開しよう！", button: "▶ 再開" });
        updateControls();
    }

    function resumeGame() {
        if (state !== "paused") return;
        state = "playing";
        lastFrame = 0; // 停止中の経過時間を進めない
        elements.overlay.hidden = true;
        updateControls();
    }

    function quitGame() {
        if (state !== "playing" && state !== "paused") return;
        if (frameId !== null) cancelAnimationFrame(frameId);
        frameId = null;
        state = "ready";
        resetBoard();
        setOverlay({ icon: "🟡", label: "READY?", title: `LEVEL ${selectedLevel}`, message: "レベルを選んで、また挑戦しよう！", button: "ゲームスタート" });
        elements.saveStatus.textContent = "";
        updateControls();
    }

    function canMove(pos, dir) {
        return Boolean(dir) && isOpen(pos.x + dir.x, pos.y + dir.y);
    }

    function collectDot() {
        const cell = grid[player.y][player.x];
        if (cell !== DOT && cell !== POWER) return;
        score += cell === POWER ? 50 : 10;
        dots--;
        grid[player.y][player.x] = EMPTY;
        if (cell === POWER) {
            frightened = 7;
            ghostCombo = 0;
        }
        updateStatus();
        if (dots === 0) finishGame(true);
    }

    function checkCollisions() {
        if (state !== "playing") return;
        for (const ghost of ghosts) {
            if (ghost.x !== player.x || ghost.y !== player.y || elapsed < ghost.stunUntil) continue;
            if (frightened > 0) {

                // 食べた場所を記録
                const hitX = ghost.x;
                const hitY = ghost.y;

                // 連続で食べると得点アップ
                const points =
                    200 * (
                        2 ** Math.min(ghostCombo, 3)
                    );

                score += points;

                ghostCombo++;

                // 得点ポップアップ
                eatenPopup = {
                    x: hitX,
                    y: hitY,
                    points: points,
                    until: elapsed + 0.9,
                };

                // 敵を初期位置へ戻す
                ghost.x = ghost.home.x;
                ghost.y = ghost.home.y;

                ghost.direction = null;

                // 復活直後は少し動かない
                ghost.stunUntil =
                    elapsed + 1.8;

                updateStatus();

            } else if (invincible <= 0) {
                lives--;
                updateStatus();
                if (lives === 0) {
                    finishGame(false);
                    return;
                }
                player = { x: 1, y: 1 };
                direction = null;
                requestedDirection = null;
                frightened = 0;
                invincible = 1.8;
                playerAccumulator = 0;
                ghostAccumulator = 0;
                ghosts.forEach(g => {
                    g.x = g.home.x;
                    g.y = g.home.y;
                    g.direction = null;
                    g.stunUntil = elapsed + .8;
                });
                return;
            }
        }
    }

    function movePlayer() {
        if (requestedDirection && canMove(player, requestedDirection)) direction = requestedDirection;
        if (!canMove(player, direction)) return;
        player.x += direction.x;
        player.y += direction.y;
        collectDot();
        checkCollisions();
    }

    function distanceMap(targetX, targetY) {
        const distances = Array.from({ length: HEIGHT }, () => Array(WIDTH).fill(Infinity));
        distances[targetY][targetX] = 0;
        const queue = [{ x: targetX, y: targetY }];
        for (let head = 0; head < queue.length; head++) {
            const p = queue[head];
            for (const next of neighbours(p.x, p.y)) {
                if (distances[next.y][next.x] !== Infinity) continue;
                distances[next.y][next.x] = distances[p.y][p.x] + 1;
                queue.push({ x: next.x, y: next.y });
            }
        }
        return distances;
    }

    function moveGhosts() {
        const config = LEVELS[selectedLevel];
        const distances = distanceMap(player.x, player.y);
        for (const ghost of ghosts) {
            if (elapsed < ghost.stunUntil) continue;
            let options = neighbours(ghost.x, ghost.y);
            if (!options.length) continue;
            if (ghost.direction && options.length > 1) {
                const forward = options.filter(option =>
                    option.dir.x !== -ghost.direction.x || option.dir.y !== -ghost.direction.y
                );
                if (forward.length) options = forward;
            }
            let choice;
            if (Math.random() < config.random) {
                choice = options[Math.floor(Math.random() * options.length)];
            } else {
                options.sort((a, b) =>
                    frightened > 0
                        ? distances[b.y][b.x] - distances[a.y][a.x]
                        : distances[a.y][a.x] - distances[b.y][b.x]
                );
                choice = options[0];
            }
            ghost.x = choice.x;
            ghost.y = choice.y;
            ghost.direction = choice.dir;
            checkCollisions();
            if (state !== "playing") break;
        }
    }

    function finishGame(won) {
        if (state !== "playing") return;
        if (won) score += 200 + Math.max(0, 120 - Math.floor(elapsed)) * 5;
        state = "finished";
        updateStatus();
        updateControls();
        setOverlay({
            icon: won ? "🏆" : "👻",
            label: won ? "LEVEL CLEAR!" : "GAME OVER",
            title: won ? "クリア！" : "また挑戦しよう！",
            message: `${selectedLevel} レベル・${score} 点！${won ? " クリアボーナス獲得！" : " 次はもっと集めよう！"}`,
            button: "もう一度遊ぶ",
        });
        saveScore(selectedLevel, score);
    }

    function frame(timestamp) {
        if (state !== "playing" && state !== "paused") {
            frameId = null;
            return;
        }
        const dt = lastFrame ? Math.min((timestamp - lastFrame) / 1000, .06) : 0;
        lastFrame = timestamp;
        if (state === "playing") {
            elapsed += dt;
            frightened = Math.max(0, frightened - dt);
            invincible = Math.max(0, invincible - dt);
            playerAccumulator += dt * 1000;
            ghostAccumulator += dt * 1000;
            const config = LEVELS[selectedLevel];
            while (playerAccumulator >= config.playerMs && state === "playing") {
                playerAccumulator -= config.playerMs;
                movePlayer();
            }
            // パワーアップ中は敵の移動速度を半分にする
            const currentGhostMs =
                frightened > 0
                    ? config.ghostMs * 2
                    : config.ghostMs;

            while (
                ghostAccumulator >= currentGhostMs
                && state === "playing"
            ) {

                ghostAccumulator -= currentGhostMs;

                moveGhosts();

            }
        }
        draw(timestamp);
        if (state === "playing" || state === "paused") {
            frameId = requestAnimationFrame(frame);
        } else {
            frameId = null;
        }
    }

    function draw(timestamp) {
        const size = WIDTH * TILE;
        ctx.clearRect(0, 0, size, size);
        ctx.fillStyle = "#09112e";
        ctx.fillRect(0, 0, size, size);
        const wallColor = LEVELS[selectedLevel].wall;
        for (let y = 0; y < HEIGHT; y++) {
            for (let x = 0; x < WIDTH; x++) {
                const cell = grid[y]?.[x];
                const cx = x * TILE + TILE / 2;
                const cy = y * TILE + TILE / 2;
                if (cell === WALL) {
                    ctx.fillStyle = wallColor;
                    ctx.fillRect(x * TILE + 1, y * TILE + 1, TILE - 2, TILE - 2);
                    ctx.fillStyle = "#ffffff13";
                    ctx.fillRect(x * TILE + 3, y * TILE + 3, TILE - 6, 3);
                } else if (cell === DOT || cell === POWER) {
                    ctx.beginPath();
                    ctx.arc(cx, cy, cell === POWER ? 6 + Math.sin(timestamp / 210) * 1.4 : 2.7, 0, Math.PI * 2);
                    ctx.fillStyle = cell === POWER ? "#ffed91" : "#eac99c";
                    ctx.fill();
                }
            }
        }
        ghosts.forEach(
            ghost => drawGhost(ghost, timestamp)
        );

        drawPlayer(timestamp);


        // 敵を食べた得点を表示
        if (
            eatenPopup
            && elapsed < eatenPopup.until
        ) {

            const remaining =
                eatenPopup.until - elapsed;

            ctx.save();

            ctx.globalAlpha =
                Math.min(1, remaining * 2);

            ctx.fillStyle = "#ffe680";

            ctx.font =
                "bold 19px sans-serif";

            ctx.textAlign = "center";

            ctx.textBaseline = "middle";

            ctx.shadowColor = "#000000";

            ctx.shadowBlur = 8;

            ctx.fillText(
                `+${eatenPopup.points}`,
                eatenPopup.x * TILE + TILE / 2,
                eatenPopup.y * TILE + TILE / 2 - 14,
            );

            ctx.restore();

        }
        if (frightened > 0 && state === "playing") {
            ctx.fillStyle = "#ecf5ff";
            ctx.font = "bold 13px sans-serif";
            ctx.textAlign = "left";
            ctx.fillText(`⚡ ${frightened.toFixed(1)}s`, 10, 18);
        }
    }

    function drawPlayer(timestamp) {
        if (invincible > 0 && Math.floor(timestamp / 110) % 2) return;
        const x = player.x * TILE + TILE / 2;
        const y = player.y * TILE + TILE / 2;
        const mouth = direction ? .12 + .28 * Math.abs(Math.sin(timestamp / 100)) : .12;
        const angle = direction ? direction.angle : 0;
        ctx.beginPath();
        ctx.moveTo(x, y);
        ctx.arc(x, y, TILE * .41, angle + mouth, angle + Math.PI * 2 - mouth);
        ctx.closePath();
        ctx.fillStyle = "#ffdc47";
        ctx.fill();
    }

    function drawGhost(ghost, timestamp) {
        const cx = ghost.x * TILE + TILE / 2;
        const cy = ghost.y * TILE + TILE / 2;
        const radius = TILE * .38;
        const stunned = elapsed < ghost.stunUntil;
        ctx.globalAlpha = stunned ? .38 : 1;
        ctx.beginPath();
        ctx.arc(cx, cy - 2, radius, Math.PI, 0);
        ctx.lineTo(cx + radius, cy + radius);
        for (let i = 3; i >= 0; i--) {
            const px = cx - radius + i * radius * 2 / 4;
            ctx.lineTo(px, cy + radius - ((i % 2) ? 4 : 0));
        }
        ctx.closePath();
        ctx.fillStyle = frightened > 0 && !stunned
            ? (frightened < 2 && Math.floor(timestamp / 180) % 2 ? "#f1f7ff" : "#497cf4")
            : ghost.color;
        ctx.fill();
        for (const eye of [-4, 4]) {
            ctx.beginPath();
            ctx.ellipse(cx + eye, cy - 3, 3.5, 4.8, 0, 0, Math.PI * 2);
            ctx.fillStyle = "#fff";
            ctx.fill();
            ctx.beginPath();
            ctx.arc(cx + eye + (ghost.direction?.x ?? 0), cy - 2 + (ghost.direction?.y ?? 0), 1.6, 0, Math.PI * 2);
            ctx.fillStyle = "#18234a";
            ctx.fill();
        }
        ctx.globalAlpha = 1;
    }

    function setDirection(name) {
        if (state !== "playing") return;
        requestedDirection = DIRECTIONS[name] || null;
    }

    function renderRanking(data, level) {
        elements.rankingLevel.textContent = String(level);
        elements.personalBest.textContent = data.personal_best == null ? "--" : String(data.personal_best);
        elements.rankingList.replaceChildren();
        if (!data.entries?.length) {
            const empty = document.createElement("li");
            empty.className = "maze-ranking-empty";
            empty.textContent = "まだ記録がない";
            elements.rankingList.appendChild(empty);
            return;
        }
        for (const entry of data.entries) {
            const item = document.createElement("li");
            if (entry.is_me) item.classList.add("is-me");
            const rank = document.createElement("span");
            rank.className = "maze-rank-position";
            rank.textContent = String(entry.rank);
            const name = document.createElement("strong");
            name.textContent = entry.name;
            const points = document.createElement("span");
            points.textContent = `${entry.score} 点`;
            item.append(rank, name, points);
            elements.rankingList.appendChild(item);
        }
    }

    async function loadRanking(level) {
        const requestId = ++rankingRequestId;
        elements.rankingLevel.textContent = String(level);
        elements.personalBest.textContent = "--";
        elements.rankingList.replaceChildren();
        const loading = document.createElement("li");
        loading.className = "maze-ranking-empty";
        loading.textContent = "ランキングを読み込み中…";
        elements.rankingList.appendChild(loading);
        try {
            const response = await fetch(`${rankingUrl}?level=${level}`, { credentials: "same-origin" });
            if (!response.ok) throw new Error("Ranking request failed");
            const data = await response.json();
            if (data.ok && selectedLevel === level && requestId === rankingRequestId) renderRanking(data, level);
        } catch (error) {
            if (selectedLevel === level && requestId === rankingRequestId) {
                loading.textContent = "ランキングを読み込めなかった。再読み込みしてね。";
            }
            console.warn("ランキング取得エラー", error);
        }
    }

    async function saveScore(level, finalScore) {
        elements.saveStatus.textContent = "スコアを保存中…";
        try {
            const response = await fetch(scoreUrl, {
                method: "POST",
                credentials: "same-origin",
                headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
                body: JSON.stringify({ game: GAME, level, score: finalScore }),
            });
            if (!response.ok) throw new Error("Score request failed");
            const data = await response.json();
            if (!data.ok) throw new Error(data.error || "Score request failed");
            if (selectedLevel === level) {
                rankingRequestId++; // 先に開始したランキング取得の古い結果を無効にする
                renderRanking(data, level);
                elements.saveStatus.textContent = data.is_new_best ? "🎉 自己ベスト更新！保存したよ。" : "スコアを保存したよ。";
            }
        } catch (error) {
            if (selectedLevel === level) elements.saveStatus.textContent = "スコアを保存できなかった。通信状態を確認してね。";
            console.warn("スコア保存エラー", error);
        }
    }

    function syncFullscreen() {
        const full = document.fullscreenElement === shell || shell.classList.contains("is-pseudo-fullscreen");
        shell.classList.toggle("is-fullscreen", full);
        document.body.classList.toggle("maze-fullscreen-active", full);
        elements.exitFullscreen.hidden = !full;
        elements.fullscreen.hidden = full;
    }

    async function enterFullscreen() {
        if (shell.requestFullscreen) {
            try {
                await shell.requestFullscreen();
                syncFullscreen();
                return;
            } catch (error) {
                // iOSなどは擬似全画面で代替する。
            }
        }
        shell.classList.add("is-pseudo-fullscreen");
        syncFullscreen();
    }

    async function exitFullscreen() {
        shell.classList.remove("is-pseudo-fullscreen");
        if (document.fullscreenElement === shell) {
            try { await document.exitFullscreen(); } catch (error) { /* no-op */ }
        }
        syncFullscreen();
    }

    function resizeCanvas() {
        const ratio = Math.min(window.devicePixelRatio || 1, 2);
        canvas.width = Math.round(WIDTH * TILE * ratio);
        canvas.height = Math.round(HEIGHT * TILE * ratio);
        ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
        if (grid.length) draw(0);
    }

    elements.levels.forEach(button => button.addEventListener("click", () => selectLevel(Number(button.dataset.level))));
    elements.overlayButton.addEventListener("click", () => state === "paused" ? resumeGame() : startGame());
    elements.pause.addEventListener("click", () => state === "paused" ? resumeGame() : pauseGame());
    elements.quit.addEventListener("click", quitGame);
    elements.fullscreen.addEventListener("click", enterFullscreen);
    elements.exitFullscreen.addEventListener("click", exitFullscreen);
    document.addEventListener("fullscreenchange", syncFullscreen);
    window.addEventListener("resize", resizeCanvas);
    window.addEventListener("blur", pauseGame);
    document.addEventListener("visibilitychange", () => { if (document.hidden) pauseGame(); });

    document.querySelectorAll(".maze-direction").forEach(button => {
        button.addEventListener("pointerdown", event => {
            event.preventDefault();
            setDirection(button.dataset.direction);
        });
        button.addEventListener("click", () => setDirection(button.dataset.direction));
    });

    window.addEventListener("keydown", event => {
        const keys = {
            ArrowUp: "up", KeyW: "up",
            ArrowDown: "down", KeyS: "down",
            ArrowLeft: "left", KeyA: "left",
            ArrowRight: "right", KeyD: "right",
        };
        const name = keys[event.code];
        if (name && state === "playing") {
            event.preventDefault();
            setDirection(name);
        } else if ((event.code === "KeyP" || event.code === "Escape") && (state === "playing" || state === "paused")) {
            if (event.code === "Escape" && document.fullscreenElement) return;
            event.preventDefault();
            state === "paused" ? resumeGame() : pauseGame();
        }
    });

    // ========================================
    // Mobile swipe controls
    // ========================================

    canvas.addEventListener(
        "pointerdown",
        event => {

            if (state !== "playing") {
                return;
            }

            swipeStart = {
                x: event.clientX,
                y: event.clientY,
                id: event.pointerId,
            };

            // 指がCanvasの外に出ても
            // 操作を継続できるようにする
            if (canvas.setPointerCapture) {

                canvas.setPointerCapture(
                    event.pointerId
                );

            }

        }
    );


    // 指を動かしている途中で方向転換
    function handleSwipe(event) {

        if (
            !swipeStart
            || swipeStart.id !== event.pointerId
            || state !== "playing"
        ) {
            return;
        }

        const dx =
            event.clientX - swipeStart.x;

        const dy =
            event.clientY - swipeStart.y;

        const distance =
            Math.max(
                Math.abs(dx),
                Math.abs(dy)
            );

        // 小さな動きは無視する
        if (distance < 18) {
            return;
        }

        let newDirection;

        if (Math.abs(dx) > Math.abs(dy)) {

            newDirection =
                dx > 0
                    ? "right"
                    : "left";

        } else {

            newDirection =
                dy > 0
                    ? "down"
                    : "up";

        }

        setDirection(newDirection);

        // 次のスワイプに備えて
        // 基準位置を更新
        swipeStart.x =
            event.clientX;

        swipeStart.y =
            event.clientY;

    }


    // 指を動かしている間に判定
    canvas.addEventListener(
        "pointermove",
        event => {

            if (event.cancelable) {
                event.preventDefault();
            }

            handleSwipe(event);

        }
    );


    // 指を離す直前にも判定
    canvas.addEventListener(
        "pointerup",
        event => {

            handleSwipe(event);

            swipeStart = null;

        }
    );


    // 操作がキャンセルされた場合
    canvas.addEventListener(
        "pointercancel",
        () => {

            swipeStart = null;

        }
    );

    resizeCanvas();
    selectLevel(1);
});