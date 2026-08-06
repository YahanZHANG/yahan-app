export const BRICK_TYPES = {
    EMPTY: 0,
    NORMAL: 1,
    STRONG: 2,
    UNBREAKABLE: 3,
    POWERUP: 4,
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
        movingBricks: false,

        layout: [
            [0, 0, 0, 1, 1, 0, 0, 0],
            [0, 0, 1, 4, 4, 1, 0, 0],
            [0, 1, 1, 2, 2, 1, 1, 0],
            [1, 1, 1, 1, 1, 1, 1, 1],
            [0, 1, 1, 1, 1, 1, 1, 0],
            [0, 0, 1, 1, 1, 1, 0, 0],
        ],

        powerups: {
            "1-3": "fireball",
            "1-4": "wide-paddle",
        },
    },

    {
        number: 3,
        name: "鋼鉄の迷路",
        ballSpeed: 5.4,
        powerupAccess: POWERUP_ACCESS.ALL,
        movingBricks: false,

        layout: [
            [2, 2, 2, 2, 2, 2, 2, 2],
            [1, 3, 1, 4, 4, 1, 3, 1],
            [1, 0, 1, 0, 0, 1, 0, 1],
            [1, 3, 1, 1, 1, 1, 3, 1],
            [0, 1, 2, 1, 1, 2, 1, 0],
        ],

        powerups: {
            "1-3": "fireball",
            "1-4": "wide-paddle",
        },
    },

    {
        number: 4,
        name: "高速要塞",
        ballSpeed: 6.1,
        powerupAccess: POWERUP_ACCESS.ALL,
        movingBricks: false,

        layout: [
            [2, 1, 2, 1, 1, 2, 1, 2],
            [1, 4, 1, 3, 3, 1, 4, 1],
            [2, 1, 2, 1, 1, 2, 1, 2],
            [1, 3, 1, 2, 2, 1, 3, 1],
            [4, 1, 1, 1, 1, 1, 1, 4],
            [1, 2, 1, 2, 2, 1, 2, 1],
        ],

        powerups: {
            "1-1": "fireball",
            "1-6": "wide-paddle",
            "4-0": "wide-paddle",
            "4-7": "fireball",
        },
    },

    {
        number: 5,
        name: "カオス・ブレイカー",
        ballSpeed: 7.2,
        powerupAccess: POWERUP_ACCESS.ALL,
        movingBricks: true,
        brickMovementSpeed: 1.25,
        brickMovementRange: 85,

        layout: [
            [2, 4, 2, 3, 3, 2, 4, 2],
            [1, 2, 1, 2, 2, 1, 2, 1],
            [3, 1, 4, 1, 1, 4, 1, 3],
            [1, 2, 1, 3, 3, 1, 2, 1],
            [2, 1, 2, 1, 1, 2, 1, 2],
            [4, 3, 1, 2, 2, 1, 3, 4],
        ],

        powerups: {
            "0-1": "fireball",
            "0-6": "wide-paddle",
            "2-2": "wide-paddle",
            "2-5": "fireball",
            "5-0": "fireball",
            "5-7": "wide-paddle",
        },
    },
];