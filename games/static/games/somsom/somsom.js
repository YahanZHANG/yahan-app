
document.addEventListener("DOMContentLoaded", function () {

    "use strict";

    // =========================================================
    // Configuration
    // =========================================================

    const BOARD_SIZE = 7;
    const TOTAL_PIECES = BOARD_SIZE * BOARD_SIZE;

    const MAX_SCORE = 1_000_000;

    const COLORS = [
        "red",
        "blue",
        "green",
        "yellow",
        "purple",
    ];

    const SOM_LABELS = {
        red: "赤の丸ソム・にっこり顔",
        blue: "青の四角ソム・まじめ顔",
        green: "緑の三角ソム・びっくり顔",
        yellow: "黄色の星ソム・ウインク顔",
        purple: "紫のひし形ソム・ねむねむ顔",
    };

    const LEVELS = {
        1: {
            name: "やさしい",
            duration: 60,
            minChain: 3,
            neighborChance: 0.72,
        },
        2: {
            name: "ふつう",
            duration: 60,
            minChain: 3,
            neighborChance: 0.48,
        },
        3: {
            name: "むずかしい",
            duration: 50,
            minChain: 3,
            neighborChance: 0.30,
        },
        4: {
            name: "激ムズ",
            duration: 45,
            minChain: 3,
            neighborChance: 0.15,
        },
        5: {
            name: "鬼",
            duration: 40,
            minChain: 4,
            neighborChance: 0.08,
        },
    };

    const PENDING_SCORE_KEY =
        "yapp:somsom:pending_score";

    const PENDING_SCORE_MAX_AGE =
        30 * 60 * 1000;

    const CLEAR_DELAY = 190;
    const REFILL_DELAY = 100;

    // =========================================================
    // Elements
    // =========================================================

    const page = document.querySelector(
        ".somsom-page"
    );

    if (!page) {
        return;
    }

    const get = function (id) {
        return document.getElementById(id);
    };

    const elements = {
        gameArea: get("somsom-game-area"),
        board: get("somsom-board"),

        chainLine: get("somsom-chain-line"),
        effects: get("somsom-effects"),

        score: get("somsom-score"),
        time: get("somsom-time"),
        currentLevel: get("somsom-current-level"),
        selectedLevel: get("somsom-selected-level"),

        ready: get("somsom-ready"),
        result: get("somsom-result"),
        pauseOverlay: get("somsom-pause-overlay"),

        start: get("somsom-start-button"),
        restart: get("somsom-restart-button"),
        pause: get("somsom-pause-button"),
        quit: get("somsom-quit-button"),
        controls: get("somsom-game-controls"),

        finalScore: get("somsom-final-score"),
        resultLevel: get("somsom-result-level"),
        resultMessage: get("somsom-result-message"),

        rankingList: get("somsom-ranking-list"),
        rankingLevel: get("somsom-ranking-level"),
        personalBest: get("somsom-personal-best"),
        saveStatus: get("somsom-save-status"),

        loginButton: get("somsom-login-score-button"),
    };

    const levelButtons = [
        ...document.querySelectorAll(
            ".somsom-level-button"
        ),
    ];

    // =========================================================
    // Authentication / URLs
    // =========================================================

    const scoreSaveUrl = page.dataset.scoreUrl;
    const rankingUrl = page.dataset.rankingUrl;
    const csrfToken = page.dataset.csrfToken;

    const isAuthenticated =
        page.dataset.isAuthenticated === "true";

    const loginUrl = page.dataset.loginUrl;

    // =========================================================
    // Game State
    // =========================================================

    let selectedLevel = 1;

    let board = [];

    let score = 0;
    let remainingTime = LEVELS[1].duration;

    let gameRunning = false;
    let isPaused = false;
    let isResolving = false;

    let timerId = null;
    let endTime = 0;

    let gameSessionId = 0;
    let rankingRequestId = 0;

    let lastFinishedResult = null;

    let selectedChain = [];
    let activePointerId = null;
    let dragging = false;

    // =========================================================
    // Helpers
    // =========================================================

    function sleep(milliseconds) {
        return new Promise(function (resolve) {
            window.setTimeout(resolve, milliseconds);
        });
    }

    function randomInt(maximum) {
        return Math.floor(Math.random() * maximum);
    }

    function randomColor() {
        return COLORS[randomInt(COLORS.length)];
    }

    function isValidLevel(level) {
        return Number.isInteger(level)
            && Object.prototype.hasOwnProperty.call(
                LEVELS,
                level
            );
    }

    function positionToIndex(row, col) {
        return row * BOARD_SIZE + col;
    }

    function indexToPosition(index) {
        return {
            row: Math.floor(index / BOARD_SIZE),
            col: index % BOARD_SIZE,
        };
    }

    function isValidPosition(row, col) {
        return row >= 0
            && row < BOARD_SIZE
            && col >= 0
            && col < BOARD_SIZE;
    }

    function isAdjacent(first, second) {
        const a = indexToPosition(first);
        const b = indexToPosition(second);

        const rowDistance = Math.abs(a.row - b.row);
        const colDistance = Math.abs(a.col - b.col);

        return rowDistance <= 1
            && colDistance <= 1
            && (rowDistance + colDistance > 0);
    }

    function setSaveStatus(message) {
        elements.saveStatus.textContent = message;
    }

    function formatScore(value) {
        return Number(value).toLocaleString("ja-JP");
    }

    function updateScoreDisplay() {
        elements.score.textContent = formatScore(score);
    }

    function updateTimeDisplay() {
        elements.time.textContent =
            String(Math.max(0, remainingTime));
    }

    function clearChainLine() {
        elements.chainLine.setAttribute("points", "");
    }

    function clearEffects() {
        elements.effects.replaceChildren();
    }

    function resetChain() {
        selectedChain = [];
        dragging = false;
        activePointerId = null;

        clearChainLine();

        elements.board
            .querySelectorAll(".is-selected")
            .forEach(function (piece) {
                piece.classList.remove("is-selected");
            });
    }

    function canInteract() {
        return gameRunning
            && !isPaused
            && !isResolving;
    }

    // =========================================================
    // Level Selection
    // =========================================================

    function selectLevel(level) {
        if (!isValidLevel(level) || gameRunning) {
            return;
        }

        selectedLevel = level;
        remainingTime = LEVELS[level].duration;

        elements.selectedLevel.textContent =
            String(level);

        elements.currentLevel.textContent =
            String(level);

        updateTimeDisplay();

        levelButtons.forEach(function (button) {
            const active =
                Number(button.dataset.level) === level;

            button.classList.toggle(
                "is-active",
                active
            );

            button.setAttribute(
                "aria-pressed",
                String(active)
            );
        });

        void loadRanking(level);
    }

    function setLevelButtonsDisabled(disabled) {
        levelButtons.forEach(function (button) {
            button.disabled = disabled;
        });
    }

    // =========================================================
    // Board Generation
    // =========================================================

    function chooseNewColor(row, col, result) {
        const settings = LEVELS[selectedLevel];

        const neighbors = [];

        if (col > 0) {
            const left = result[
                positionToIndex(row, col - 1)
            ];

            if (left) {
                neighbors.push(left);
            }
        }

        if (row > 0) {
            const above = result[
                positionToIndex(row - 1, col)
            ];

            if (above) {
                neighbors.push(above);
            }
        }

        if (
            neighbors.length > 0
            && Math.random() < settings.neighborChance
        ) {
            return neighbors[randomInt(neighbors.length)];
        }

        return randomColor();
    }

    function generateBoard() {
        const result = [];

        for (let row = 0; row < BOARD_SIZE; row++) {
            for (let col = 0; col < BOARD_SIZE; col++) {
                result.push(
                    chooseNewColor(row, col, result)
                );
            }
        }

        return result;
    }

    function hasValidMove() {
        const required = LEVELS[selectedLevel].minChain;
        const visited = new Set();

        for (let start = 0; start < TOTAL_PIECES; start++) {
            if (visited.has(start) || !board[start]) {
                continue;
            }

            const color = board[start];
            const queue = [start];

            visited.add(start);

            let count = 0;

            while (queue.length > 0) {
                const current = queue.pop();

                count += 1;

                if (count >= required) {
                    return true;
                }

                const center = indexToPosition(current);

                for (let dr = -1; dr <= 1; dr++) {
                    for (let dc = -1; dc <= 1; dc++) {
                        if (dr === 0 && dc === 0) {
                            continue;
                        }

                        const row = center.row + dr;
                        const col = center.col + dc;

                        if (!isValidPosition(row, col)) {
                            continue;
                        }

                        const next = positionToIndex(row, col);

                        if (
                            !visited.has(next)
                            && board[next] === color
                        ) {
                            visited.add(next);
                            queue.push(next);
                        }
                    }
                }
            }
        }

        return false;
    }

    function ensureValidBoard() {
        for (let attempt = 0; attempt < 100; attempt++) {
            if (hasValidMove()) {
                return;
            }

            board = generateBoard();
        }

        // Guarantee at least one playable chain.
        const required = LEVELS[selectedLevel].minChain;
        const color = randomColor();

        for (let index = 0; index < required; index++) {
            board[index] = color;
        }
    }

    function createInitialBoard() {
        board = generateBoard();

        ensureValidBoard();

        renderBoard();
    }

    // =========================================================
    // Board Rendering
    // =========================================================

    function renderBoard() {
        const fragment = document.createDocumentFragment();

        const cellPercentage = 100 / BOARD_SIZE;
        const piecePercentage = cellPercentage * 0.91;

        const boardWidth = elements.board.clientWidth;
        const piecePixels =
            boardWidth * piecePercentage / 100;

        for (let index = 0; index < TOTAL_PIECES; index++) {
            const color = board[index];

            if (!color) {
                continue;
            }

            const position = indexToPosition(index);

            const piece = document.createElement("button");

            piece.type = "button";

            piece.className =
                `somsom-piece is-${color}`;

            piece.dataset.index = String(index);

            piece.setAttribute(
                "aria-label",
                SOM_LABELS[color]
            );

            piece.style.left =
                `${(position.col + 0.5) * cellPercentage}%`;

            piece.style.top =
                `${(position.row + 0.5) * cellPercentage}%`;

            piece.style.setProperty(
                "--piece-size",
                `${piecePercentage}%`
            );

            piece.style.setProperty(
                "--eye-gap",
                `${piecePixels * 0.36}px`
            );

            piece.style.setProperty(
                "--som-piece-font-size",
                `${piecePixels}px`
            );

            if (selectedChain.includes(index)) {
                piece.classList.add("is-selected");
            }

            fragment.appendChild(piece);
        }

        elements.board.replaceChildren(fragment);

        updateChainLine();
    }

    // =========================================================
    // Chain Line
    // =========================================================

    function getPieceCenter(index) {
        const position = indexToPosition(index);

        const boardRect =
            elements.board.getBoundingClientRect();

        const areaRect =
            elements.gameArea.getBoundingClientRect();

        const cellWidth = boardRect.width / BOARD_SIZE;
        const cellHeight = boardRect.height / BOARD_SIZE;

        return {
            x:
                boardRect.left - areaRect.left
                + (position.col + 0.5) * cellWidth,

            y:
                boardRect.top - areaRect.top
                + (position.row + 0.5) * cellHeight,
        };
    }

    function updateChainLine() {
        if (selectedChain.length === 0) {
            clearChainLine();
            return;
        }

        const points = selectedChain.map(function (index) {
            const center = getPieceCenter(index);
            return `${center.x},${center.y}`;
        });

        elements.chainLine.setAttribute(
            "points",
            points.join(" ")
        );
    }

    // =========================================================
    // Pointer / Drag Handling
    // =========================================================

    function getIndexFromPointer(event) {
        const rect =
            elements.board.getBoundingClientRect();

        const x = event.clientX - rect.left;
        const y = event.clientY - rect.top;

        if (
            x < 0
            || y < 0
            || x >= rect.width
            || y >= rect.height
        ) {
            return null;
        }

        const cellWidth = rect.width / BOARD_SIZE;
        const cellHeight = rect.height / BOARD_SIZE;

        const col = Math.floor(x / cellWidth);
        const row = Math.floor(y / cellHeight);

        // Prevent selecting a cell too far from its center.
        const localX = x / cellWidth - col - 0.5;
        const localY = y / cellHeight - row - 0.5;

        if (Math.hypot(localX, localY) > 0.66) {
            return null;
        }

        return positionToIndex(row, col);
    }

    function addToChain(index) {
        if (index === null || !board[index]) {
            return;
        }

        if (selectedChain.length === 0) {
            selectedChain.push(index);
            renderSelection();
            return;
        }

        const lastIndex =
            selectedChain[selectedChain.length - 1];

        if (index === lastIndex) {
            return;
        }

        // Drag backwards to undo the previous piece.
        if (
            selectedChain.length >= 2
            && index === selectedChain[selectedChain.length - 2]
        ) {
            selectedChain.pop();
            renderSelection();
            return;
        }

        if (selectedChain.includes(index)) {
            return;
        }

        if (!isAdjacent(lastIndex, index)) {
            return;
        }

        if (board[index] !== board[selectedChain[0]]) {
            return;
        }

        selectedChain.push(index);

        renderSelection();
    }

    function renderSelection() {
        const selected = new Set(selectedChain);

        elements.board
            .querySelectorAll(".somsom-piece")
            .forEach(function (piece) {
                const index = Number(piece.dataset.index);

                piece.classList.toggle(
                    "is-selected",
                    selected.has(index)
                );
            });

        updateChainLine();
    }

    function handlePointerDown(event) {
        if (!canInteract()) {
            return;
        }

        if (event.pointerType === "mouse" && event.button !== 0) {
            return;
        }

        const index = getIndexFromPointer(event);

        if (index === null || !board[index]) {
            return;
        }

        event.preventDefault();

        resetChain();

        dragging = true;
        activePointerId = event.pointerId;

        try {
            elements.board.setPointerCapture(event.pointerId);
        } catch (error) {
            // Pointer capture is optional.
        }

        addToChain(index);
    }

    function handlePointerMove(event) {
        if (
            !dragging
            || !canInteract()
            || event.pointerId !== activePointerId
        ) {
            return;
        }

        event.preventDefault();

        const index = getIndexFromPointer(event);

        addToChain(index);
    }

    function handlePointerUp(event) {
        if (
            !dragging
            || event.pointerId !== activePointerId
        ) {
            return;
        }

        const chain = [...selectedChain];

        resetChain();

        if (!canInteract()) {
            return;
        }

        if (
            chain.length >= LEVELS[selectedLevel].minChain
        ) {
            void resolveChain(chain);
        }
    }

    function handlePointerCancel(event) {
        if (event.pointerId === activePointerId) {
            resetChain();
        }
    }

    // =========================================================
    // Effects
    // =========================================================

    function showFloatingText(index, text, className) {
        const center = getPieceCenter(index);

        const effect = document.createElement("span");

        effect.className = className;
        effect.textContent = text;

        effect.style.left = `${center.x}px`;
        effect.style.top = `${center.y}px`;

        elements.effects.appendChild(effect);

        window.setTimeout(function () {
            effect.remove();
        }, 1200);
    }

    function markClearingPieces(indices) {
        const clearing = new Set(indices);

        elements.board
            .querySelectorAll(".somsom-piece")
            .forEach(function (piece) {
                if (clearing.has(Number(piece.dataset.index))) {
                    piece.classList.add("is-clearing");
                }
            });
    }

    // =========================================================
    // Special Abilities
    // =========================================================

    function collectRedBomb(indices, lastIndex) {
        const result = new Set(indices);
        const center = indexToPosition(lastIndex);

        for (let dr = -1; dr <= 1; dr++) {
            for (let dc = -1; dc <= 1; dc++) {
                const row = center.row + dr;
                const col = center.col + dc;

                if (isValidPosition(row, col)) {
                    result.add(positionToIndex(row, col));
                }
            }
        }

        return result;
    }

    function collectPurpleLine(indices, lastIndex) {
        const result = new Set(indices);
        const row = indexToPosition(lastIndex).row;

        for (let col = 0; col < BOARD_SIZE; col++) {
            result.add(positionToIndex(row, col));
        }

        return result;
    }

    function applyGreenTransformation() {
        const candidates = [];

        for (let index = 0; index < TOTAL_PIECES; index++) {
            if (board[index] !== "green") {
                candidates.push(index);
            }
        }

        for (let count = 0; count < 2; count++) {
            if (candidates.length === 0) {
                break;
            }

            const randomPosition = randomInt(candidates.length);

            const index = candidates.splice(
                randomPosition,
                1
            )[0];

            board[index] = "green";
        }
    }

    // =========================================================
    // Scoring / Clearing
    // =========================================================

    function calculatePoints(chain, cleared, color) {
        const base = chain.length * chain.length * 10;

        const extraCount = Math.max(
            0,
            cleared.size - chain.length
        );

        const extraPoints = extraCount * 25;

        let points = base + extraPoints;

        if (color === "yellow") {
            points = Math.round(points * 1.5);
        }

        return points;
    }

    function collapseBoard(indicesToClear) {
        const cleared = new Set(indicesToClear);

        const nextBoard = new Array(TOTAL_PIECES).fill(null);

        for (let col = 0; col < BOARD_SIZE; col++) {
            const survivors = [];

            for (
                let row = BOARD_SIZE - 1;
                row >= 0;
                row--
            ) {
                const index = positionToIndex(row, col);

                if (!cleared.has(index) && board[index]) {
                    survivors.push(board[index]);
                }
            }

            let targetRow = BOARD_SIZE - 1;

            for (const color of survivors) {
                nextBoard[
                    positionToIndex(targetRow, col)
                ] = color;

                targetRow -= 1;
            }

            while (targetRow >= 0) {
                nextBoard[
                    positionToIndex(targetRow, col)
                ] = randomColor();

                targetRow -= 1;
            }
        }

        board = nextBoard;
    }

    async function resolveChain(chain) {
        if (!canInteract()) {
            return;
        }

        const session = gameSessionId;

        isResolving = true;

        const color = board[chain[0]];
        const lastIndex = chain[chain.length - 1];

        let cleared = new Set(chain);
        let abilityMessage = "";

        if (color === "red" && chain.length >= 6) {
            cleared = collectRedBomb(
                cleared,
                lastIndex
            );

            abilityMessage = "💥 ボム！";
        }

        if (color === "purple" && chain.length >= 7) {
            cleared = collectPurpleLine(
                cleared,
                lastIndex
            );

            abilityMessage = "✨ ライン消去！";
        }

        if (color === "blue" && chain.length >= 6) {
            endTime += 1000;

            remainingTime = Math.max(
                0,
                Math.ceil((endTime - Date.now()) / 1000)
            );

            updateTimeDisplay();

            abilityMessage = "⏱ +1秒！";
        }

        if (color === "green" && chain.length >= 6) {
            abilityMessage = "🍀 変身！";
        }

        if (color === "yellow") {
            abilityMessage = "⭐ 1.5倍！";
        }

        const points = calculatePoints(
            chain,
            cleared,
            color
        );

        score = Math.min(MAX_SCORE, score + points);

        updateScoreDisplay();

        markClearingPieces(cleared);

        showFloatingText(
            lastIndex,
            `+${formatScore(points)}`,
            "somsom-floating-score"
        );

        if (abilityMessage) {
            showFloatingText(
                lastIndex,
                abilityMessage,
                "somsom-ability-effect"
            );
        }

        await sleep(CLEAR_DELAY);

        if (session !== gameSessionId || !gameRunning) {
            return;
        }

        collapseBoard(cleared);

        if (color === "green" && chain.length >= 6) {
            applyGreenTransformation();
        }

        ensureValidBoard();

        renderBoard();

        await sleep(REFILL_DELAY);

        if (session !== gameSessionId || !gameRunning) {
            return;
        }

        isResolving = false;

        if (!isPaused && endTime <= Date.now()) {
            endGame();
        }
    }

    // =========================================================
    // Timer
    // =========================================================

    function clearGameTimer() {
        if (timerId !== null) {
            clearInterval(timerId);
            timerId = null;
        }
    }

    function startTimer() {
        clearGameTimer();

        endTime = Date.now() + remainingTime * 1000;

        timerId = window.setInterval(function () {
            if (!gameRunning || isPaused) {
                return;
            }

            remainingTime = Math.max(
                0,
                Math.ceil((endTime - Date.now()) / 1000)
            );

            updateTimeDisplay();

            if (remainingTime <= 0 && !isResolving) {
                endGame();
            }
        }, 100);
    }

    // =========================================================
    // Start Game
    // =========================================================

    function startGame() {
        clearGameTimer();

        gameSessionId += 1;

        gameRunning = true;
        isPaused = false;
        isResolving = false;

        score = 0;
        remainingTime = LEVELS[selectedLevel].duration;

        resetChain();
        clearEffects();

        updateScoreDisplay();
        updateTimeDisplay();

        elements.currentLevel.textContent =
            String(selectedLevel);

        elements.ready.hidden = true;
        elements.result.hidden = true;
        elements.pauseOverlay.hidden = true;

        elements.board.hidden = false;
        elements.controls.hidden = false;

        elements.pause.textContent = "⏸ 一時停止";

        elements.loginButton.hidden = true;

        setSaveStatus("");
        setLevelButtonsDisabled(true);

        createInitialBoard();

        startTimer();
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
        if (!gameRunning || isPaused) {
            return;
        }

        remainingTime = Math.max(
            0,
            (endTime - Date.now()) / 1000
        );

        isPaused = true;

        clearGameTimer();
        resetChain();

        elements.pauseOverlay.hidden = false;
        elements.pause.textContent = "▶ 再開";
    }

    function resumeGame() {
        if (!gameRunning || !isPaused) {
            return;
        }

        isPaused = false;

        elements.pauseOverlay.hidden = true;
        elements.pause.textContent = "⏸ 一時停止";

        startTimer();
    }

    // =========================================================
    // Quit Game
    // =========================================================

    function quitGame() {
        gameSessionId += 1;

        clearGameTimer();

        gameRunning = false;
        isPaused = false;
        isResolving = false;

        resetChain();
        clearEffects();

        score = 0;
        remainingTime = LEVELS[selectedLevel].duration;

        board = [];

        elements.board.replaceChildren();
        elements.board.hidden = true;

        elements.result.hidden = true;
        elements.ready.hidden = false;
        elements.pauseOverlay.hidden = true;

        elements.controls.hidden = true;
        elements.loginButton.hidden = true;

        elements.pause.textContent = "⏸ 一時停止";

        updateScoreDisplay();
        updateTimeDisplay();

        setSaveStatus("");
        setLevelButtonsDisabled(false);
    }

    // =========================================================
    // Result
    // =========================================================

    function getResultMessage(currentScore) {
        if (currentScore >= 30000) {
            return "すごすぎる！ソムソムマスター！";
        }

        if (currentScore >= 15000) {
            return "大連鎖！かなりいい記録！";
        }

        if (currentScore >= 7000) {
            return "いい感じ！ソムをつなぐのが上手！";
        }

        if (currentScore >= 2500) {
            return "ナイスチャレンジ！";
        }

        return "次はもっとつなげてみよう！";
    }

    function endGame() {
        if (!gameRunning) {
            return;
        }

        const finishedLevel = selectedLevel;
        const finishedScore = score;
        const finishedSession = gameSessionId;

        gameRunning = false;
        isPaused = false;
        isResolving = false;

        clearGameTimer();
        resetChain();
        clearEffects();

        remainingTime = 0;
        updateTimeDisplay();

        elements.board.hidden = true;
        elements.controls.hidden = true;
        elements.pauseOverlay.hidden = true;

        elements.finalScore.textContent =
            formatScore(score);

        elements.resultLevel.textContent =
            String(selectedLevel);

        elements.resultMessage.textContent =
            getResultMessage(score);

        elements.result.hidden = false;

        elements.loginButton.hidden = isAuthenticated;

        setLevelButtonsDisabled(false);

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
    // Ranking Rendering
    // =========================================================

    function renderRanking(data, level) {
        if (!data || !Array.isArray(data.entries)) {
            return;
        }

        elements.rankingLevel.textContent = String(level);

        elements.rankingList.replaceChildren();

        if (data.entries.length === 0) {
            const item = document.createElement("li");

            item.className = "somsom-ranking-empty";
            item.textContent = "まだ記録がない";

            elements.rankingList.appendChild(item);
        } else {
            data.entries.forEach(function (entry) {
                const item = document.createElement("li");

                if (entry.is_me) {
                    item.classList.add("is-me");
                }

                const position =
                    document.createElement("span");

                position.className =
                    "somsom-ranking-position";

                position.textContent = String(entry.rank);

                const name =
                    document.createElement("strong");

                name.textContent = String(entry.name);

                const points =
                    document.createElement("span");

                points.textContent =
                    `${formatScore(entry.score)} 点`;

                item.append(position, name, points);

                elements.rankingList.appendChild(item);
            });
        }

        elements.personalBest.textContent =
            data.personal_best == null
                ? "--"
                : formatScore(data.personal_best);
    }

    // =========================================================
    // Ranking API
    // =========================================================

    async function loadRanking(level) {
        const requestId = ++rankingRequestId;

        elements.rankingLevel.textContent = String(level);
        elements.personalBest.textContent = "--";

        elements.rankingList.replaceChildren();

        const loading = document.createElement("li");

        loading.className = "somsom-ranking-empty";
        loading.textContent = "ランキングを読み込み中…";

        elements.rankingList.appendChild(loading);

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
                "ソムソム ランキング取得エラー:",
                error
            );
        }
    }

    // =========================================================
    // Save Score API
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
                    game: "somsom",
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

    async function saveScore(level, currentScore, session) {
        if (!isAuthenticated) {
            setSaveStatus(
                "今回のスコアは未保存。ログインすると記録できる。"
            );
            return;
        }

        setSaveStatus("スコアを保存中…");

        try {
            const data = await postGameScore(
                level,
                currentScore
            );

            if (
                gameSessionId === session
                && selectedLevel === level
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
                gameSessionId === session
                && selectedLevel === level
            ) {
                setSaveStatus(
                    "スコアを保存できませんでした。"
                );
            }

            console.warn(
                "ソムソム スコア保存エラー:",
                error
            );
        }
    }

    // =========================================================
    // Guest Pending Score
    // =========================================================

    function clearPendingScore() {
        try {
            sessionStorage.removeItem(
                PENDING_SCORE_KEY
            );
        } catch (error) {
            console.warn(error);
        }
    }

    function readPendingScore() {
        let raw;

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

            const valid =
                pending !== null
                && typeof pending === "object"
                && pending.game === "somsom"
                && isValidLevel(pending.level)
                && Number.isInteger(pending.score)
                && pending.score >= 0
                && pending.score <= MAX_SCORE
                && Number.isFinite(pending.createdAt)
                && pending.createdAt <= now
                && now - pending.createdAt
                    <= PENDING_SCORE_MAX_AGE;

            if (!valid) {
                clearPendingScore();
                return null;
            }

            return pending;
        } catch (error) {
            clearPendingScore();
            return null;
        }
    }

    function savePendingScore() {
        if (!lastFinishedResult) {
            return false;
        }

        const pending = {
            game: "somsom",
            level: lastFinishedResult.level,
            score: lastFinishedResult.score,
            createdAt: Date.now(),
        };

        try {
            sessionStorage.setItem(
                PENDING_SCORE_KEY,
                JSON.stringify(pending)
            );

            return true;
        } catch (error) {
            console.warn(error);
            return false;
        }
    }

    function goToLoginWithScore(event) {
        event.preventDefault();

        if (isAuthenticated || !loginUrl) {
            return;
        }

        if (!savePendingScore()) {
            setSaveStatus(
                "スコアを一時保存できませんでした。"
            );
            return;
        }

        const url = new URL(
            loginUrl,
            window.location.origin
        );

        url.searchParams.set(
            "next",
            window.location.pathname
                + window.location.search
        );

        window.location.assign(url.toString());
    }

    async function restorePendingScoreAfterLogin() {
        if (!isAuthenticated) {
            return;
        }

        const pending = readPendingScore();

        if (!pending) {
            return;
        }

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
                renderRanking(data, pending.level);
            } else {
                await loadRanking(selectedLevel);
            }

            setSaveStatus(
                data.is_new_best
                    ? `🎉 LEVEL ${pending.level} の自己ベスト更新！`
                    : `LEVEL ${pending.level} のスコアを記録したよ。`
            );
        } catch (error) {
            try {
                sessionStorage.setItem(
                    PENDING_SCORE_KEY,
                    JSON.stringify(pending)
                );
            } catch (storageError) {
                console.warn(storageError);
            }

            setSaveStatus(
                "スコアを保存できませんでした。再読み込みしてね。"
            );

            console.warn(error);
        }
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

    elements.start.addEventListener(
        "click",
        startGame
    );

    elements.restart.addEventListener(
        "click",
        startGame
    );

    elements.pause.addEventListener(
        "click",
        togglePause
    );

    elements.quit.addEventListener(
        "click",
        quitGame
    );

    elements.board.addEventListener(
        "pointerdown",
        handlePointerDown
    );

    elements.board.addEventListener(
        "pointermove",
        handlePointerMove
    );

    elements.board.addEventListener(
        "pointerup",
        handlePointerUp
    );

    elements.board.addEventListener(
        "pointercancel",
        handlePointerCancel
    );

    elements.board.addEventListener(
        "lostpointercapture",
        function () {
            if (dragging) {
                resetChain();
            }
        }
    );

    elements.board.addEventListener(
        "dragstart",
        function (event) {
            event.preventDefault();
        }
    );

    elements.loginButton.addEventListener(
        "click",
        goToLoginWithScore
    );

    window.addEventListener(
        "resize",
        function () {
            if (gameRunning) {
                renderBoard();
            }
        }
    );

    document.addEventListener(
        "visibilitychange",
        function () {
            if (document.hidden && gameRunning && !isPaused) {
                pauseGame();
            }
        }
    );

    // =========================================================
    // Initial State
    // =========================================================

    elements.board.hidden = true;
    elements.controls.hidden = true;
    elements.result.hidden = true;
    elements.pauseOverlay.hidden = true;
    elements.loginButton.hidden = true;

    selectLevel(1);

    void restorePendingScoreAfterLogin();

});
