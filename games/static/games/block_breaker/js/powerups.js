export const POWERUP_TYPES = {
    FIREBALL: "fireball",
};


export const POWERUP_CONFIG = {
    width: 34,
    height: 34,
    fallSpeed: 2.4,

    fireballDuration: 8000,
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

    return "?";
}