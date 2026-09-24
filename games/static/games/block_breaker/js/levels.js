export const BRICK_TYPES = {
    EMPTY: 0,
    NORMAL: 1,
    STRONG: 2,
    UNBREAKABLE: 3,
    POWERUP: 4,
    BOMB: 5,
};


export const POWERUP_ACCESS = {
    BEGINNER: "beginner",
    ALL: "all",
};


export const LEVELS = [

    // ========================================
    // LEVEL 1
    // 元ステージ3：鋼鉄の迷路
    // ========================================

    {
        number: 1,

        name: "鋼鉄の迷路",

        difficulty: "やさしい",

        ballSpeed: 5.4,

        powerupAccess: POWERUP_ACCESS.ALL,

        comboEnabled: true,

        movingBricks: false,

        layout: [
            [2, 2, 5, 2, 2, 5, 2, 2],
            [1, 3, 1, 4, 4, 1, 3, 1],
            [1, 0, 1, 0, 0, 1, 0, 1],
            [1, 3, 1, 5, 1, 1, 3, 1],
            [0, 1, 2, 1, 4, 2, 1, 0],
        ],

        powerups: {
            "1-3": "fireball",
            "1-4": "wide-paddle",
            "4-4": "laser",
        },
    },


    // ========================================
    // LEVEL 2
    // 元ステージ6：ツインタワー
    // ========================================

    {
        number: 2,

        name: "ツインタワー",

        difficulty: "ふつう",

        ballSpeed: 7.0,

        powerupAccess: POWERUP_ACCESS.ALL,

        comboEnabled: true,

        movingBricks: true,

        brickMovementSpeed: 1.2,

        brickMovementRange: 20,

        layout: [
            [2, 2, 0, 3, 3, 0, 2, 2],
            [2, 4, 0, 1, 1, 0, 4, 2],
            [5, 2, 0, 2, 2, 0, 2, 5],
            [2, 1, 0, 3, 3, 0, 1, 2],
            [4, 2, 0, 1, 1, 0, 2, 4],
            [2, 5, 0, 2, 2, 0, 5, 2],
        ],

        powerups: {
            "1-1": "fireball",
            "1-6": "wide-paddle",
            "4-0": "laser",
            "4-7": "fireball",
        },
    },


    // ========================================
    // LEVEL 3
    // 元ステージ8：スネークライン
    // ========================================

    {
        number: 3,

        name: "スネークライン",

        difficulty: "むずかしい",

        ballSpeed: 7.4,

        powerupAccess: POWERUP_ACCESS.ALL,

        comboEnabled: true,

        movingBricks: true,

        brickMovementSpeed: 1.45,

        brickMovementRange: 18,

        layout: [
            [2, 2, 2, 4, 5, 2, 2, 2],
            [0, 0, 0, 0, 1, 0, 0, 0],
            [2, 2, 5, 4, 2, 2, 2, 0],
            [1, 0, 0, 0, 0, 0, 0, 0],
            [2, 2, 2, 2, 4, 5, 2, 2],
            [0, 0, 0, 0, 0, 0, 0, 1],
            [0, 2, 2, 5, 4, 2, 2, 2],
        ],

        powerups: {
            "0-3": "fireball",
            "2-3": "laser",
            "4-4": "wide-paddle",
            "6-4": "fireball",
        },
    },


    // ========================================
    // LEVEL 4
    // 元ステージ9：ブラックホール
    // ========================================

    {
        number: 4,

        name: "ブラックホール",

        difficulty: "激ムズ",

        ballSpeed: 7.6,

        powerupAccess: POWERUP_ACCESS.ALL,

        comboEnabled: true,

        movingBricks: true,

        brickMovementSpeed: 1.5,

        brickMovementRange: 22,

        layout: [
            [2, 2, 2, 5, 5, 2, 2, 2],
            [2, 4, 1, 3, 3, 1, 4, 2],
            [2, 1, 3, 0, 0, 3, 1, 2],
            [5, 3, 0, 0, 0, 0, 3, 5],
            [5, 3, 0, 0, 0, 0, 3, 5],
            [2, 1, 3, 0, 0, 3, 1, 2],
            [2, 4, 1, 3, 3, 1, 4, 2],
            [2, 2, 2, 5, 5, 2, 2, 2],
        ],

        powerups: {
            "1-1": "laser",
            "1-6": "wide-paddle",
            "6-1": "fireball",
            "6-6": "laser",
        },
    },


    // ========================================
    // LEVEL 5
    // 元ステージ10：ラスト・カオス
    // ========================================

    {
        number: 5,

        name: "ラスト・カオス",

        difficulty: "鬼",

        ballSpeed: 7.9,

        powerupAccess: POWERUP_ACCESS.ALL,

        comboEnabled: true,

        movingBricks: true,

        brickMovementSpeed: 1.65,

        brickMovementRange: 26,

        layout: [
            [5, 2, 4, 3, 3, 4, 2, 5],
            [2, 5, 2, 1, 1, 2, 5, 2],
            [4, 2, 3, 5, 5, 3, 2, 4],
            [3, 1, 5, 2, 2, 5, 1, 3],
            [3, 1, 5, 2, 2, 5, 1, 3],
            [4, 2, 3, 5, 5, 3, 2, 4],
            [2, 5, 2, 1, 1, 2, 5, 2],
            [5, 2, 4, 3, 3, 4, 2, 5],
        ],

        powerups: {
            "0-2": "fireball",
            "0-5": "laser",
            "2-0": "wide-paddle",
            "2-7": "fireball",
            "5-0": "laser",
            "5-7": "wide-paddle",
        },
    },

];