export const POWERUP_TYPES = {
    FIREBALL: "fireball",
    WIDE_PADDLE: "wide-paddle",
    LASER: "laser",
};

export const POWERUP_CONFIG = {
    width: 34,
    height: 34,
    fallSpeed: 2.4,

    fireballDuration: 8000,

    widePaddleDuration: 10000,
    widePaddleMultiplier: 1.6,

    laserDuration: 10000,
    laserSpeed: 9,
    laserWidth: 5,
    laserHeight: 18,
    laserCooldown: 260,
};

export function createPowerup(type, x, y) {
    return {
        type,
        x,
        y,
        width: POWERUP_CONFIG.width,
        height: POWERUP_CONFIG.height,
        speed: POWERUP_CONFIG.fallSpeed,
        collected: false,
    };
}

export function getPowerupSymbol(type) {
    if (type === POWERUP_TYPES.FIREBALL) {
        return "🔥";
    }

    if (type === POWERUP_TYPES.WIDE_PADDLE) {
        return "↔️";
    }

    if (type === POWERUP_TYPES.LASER) {
        return "⚡";
    }

    return "?";
}
