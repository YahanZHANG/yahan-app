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
    {
        number: 1,
        name: "はじめの壁",
        ballSpeed: 4.2,
        powerupAccess: POWERUP_ACCESS.BEGINNER,
        comboEnabled: false,
        movingBricks: false,

        layout: [
            [1, 1, 1, 4, 4, 1, 1, 1],
            [1, 1, 1, 1, 1, 1, 1, 1],
            [1, 1, 4, 1, 1, 4, 1, 1],
            [0, 1, 1, 1, 1, 1, 1, 0],
        ],

        powerups: {
            "0-3": "fireball",
            "0-4": "wide-paddle",
            "2-2": "fireball",
            "2-5": "wide-paddle",
        },
    },

    {
        number: 2,
        name: "ダイヤモンド",
        ballSpeed: 4.8,
        powerupAccess: POWERUP_ACCESS.ALL,
        comboEnabled: true,
        movingBricks: false,

        layout: [
            [0, 0, 0, 1, 1, 0, 0, 0],
            [0, 0, 1, 4, 4, 1, 0, 0],
            [0, 1, 5, 2, 2, 5, 1, 0],
            [1, 1, 1, 4, 1, 1, 1, 1],
            [0, 1, 1, 1, 1, 1, 1, 0],
            [0, 0, 1, 1, 1, 1, 0, 0],
        ],

        powerups: {
            "1-3": "fireball",
            "1-4": "wide-paddle",
            "3-3": "laser",
        },
    },

    {
        number: 3,
        name: "鋼鉄の迷路",
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

    {
        number: 4,
        name: "高速要塞",
        ballSpeed: 6.1,
        powerupAccess: POWERUP_ACCESS.ALL,
        comboEnabled: true,
        movingBricks: false,

        layout: [
            [2, 1, 5, 1, 1, 5, 1, 2],
            [1, 4, 1, 3, 3, 1, 4, 1],
            [2, 1, 2, 5, 1, 2, 1, 2],
            [1, 3, 1, 2, 2, 1, 3, 1],
            [4, 1, 1, 1, 1, 1, 1, 4],
            [1, 2, 1, 4, 2, 1, 2, 1],
        ],

        powerups: {
            "1-1": "fireball",
            "1-6": "wide-paddle",
            "4-0": "wide-paddle",
            "4-7": "fireball",
            "5-3": "laser",
        },
    },

    {
        number: 5,
        name: "カオス・ブレイカー",
        ballSpeed: 7.2,
        powerupAccess: POWERUP_ACCESS.ALL,
        comboEnabled: true,
        movingBricks: true,
        brickMovementSpeed: 1.4,
        brickMovementRange: 28,

        layout: [
            [2, 4, 5, 3, 3, 5, 4, 2],
            [1, 2, 1, 2, 2, 1, 2, 1],
            [3, 1, 4, 5, 1, 4, 1, 3],
            [1, 2, 1, 3, 3, 1, 2, 1],
            [2, 5, 2, 1, 1, 2, 5, 2],
            [4, 3, 1, 4, 2, 1, 3, 4],
        ],

        powerups: {
            "0-1": "fireball",
            "0-6": "wide-paddle",
            "2-2": "wide-paddle",
            "2-5": "fireball",
            "5-0": "fireball",
            "5-3": "laser",
            "5-7": "wide-paddle",
        },
    },
        
    {
        number: 6,
        name: "ツインタワー",
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

    {
        number: 7,
        name: "クロスファイア",
        ballSpeed: 7.3,
        powerupAccess: POWERUP_ACCESS.ALL,
        comboEnabled: true,
        movingBricks: true,
        brickMovementSpeed: 1.35,
        brickMovementRange: 24,

        layout: [
            [2, 0, 0, 5, 5, 0, 0, 2],
            [0, 2, 4, 1, 1, 4, 2, 0],
            [0, 4, 3, 2, 2, 3, 4, 0],
            [5, 1, 2, 3, 3, 2, 1, 5],
            [0, 4, 3, 2, 2, 3, 4, 0],
            [0, 2, 4, 1, 1, 4, 2, 0],
            [2, 0, 0, 5, 5, 0, 0, 2],
        ],

        powerups: {
            "1-2": "laser",
            "1-5": "fireball",
            "4-1": "wide-paddle",
            "4-6": "laser",
            "5-2": "fireball",
            "5-5": "wide-paddle",
        },
    },

    {
        number: 8,
        name: "スネークライン",
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

    {
        number: 9,
        name: "ブラックホール",
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

    {
        number: 10,
        name: "ラスト・カオス",
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
