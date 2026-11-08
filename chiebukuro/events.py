"""
HOME の上に出す「きょうは何の日」: スイスと日本の祝日・行事。
ふつうの日 (平日や、ただの土日) は何も出さない。両方あるときは両方出す。
"""

from datetime import date, datetime, timedelta

from .japan_calendar import JST, _datetime_to_jde, japan_holidays, sun_longitude


def easter(year):
    """復活祭 (イースター) の日曜日。グレゴリオ暦の計算 (Anonymous Gregorian algorithm)"""

    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


def _nth_weekday(year, month, weekday, nth):
    """その月の n 回目の ○曜日 (weekday: 月=0 … 日=6)"""

    first = date(year, month, 1)
    return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (nth - 1))


def setsubun(year):
    """節分 = 立春 (太陽の黄経が315度になる日、日本時間) の前の日"""

    for offset in range(0, 8):
        day = date(year, 2, 1) + timedelta(days=offset)
        end = datetime(day.year, day.month, day.day, tzinfo=JST) + timedelta(days=1)
        if 315 <= sun_longitude(_datetime_to_jde(end)) < 330:
            return day - timedelta(days=1)
    return date(year, 2, 3)


def swiss_days(year):
    """スイスの祝日 (全国か、多くの州で休み) {date: 名前}"""

    sunday = easter(year)
    return {
        date(year, 1, 1): "新年",
        date(year, 1, 2): "ベルヒトルトの日",
        sunday - timedelta(days=2): "聖金曜日",
        sunday: "イースター",
        sunday + timedelta(days=1): "イースターマンデー",
        sunday + timedelta(days=39): "キリスト昇天祭",
        sunday + timedelta(days=49): "聖霊降臨祭",
        sunday + timedelta(days=50): "聖霊降臨祭の月曜日",
        date(year, 8, 1): "建国記念日",
        _nth_weekday(year, 9, 6, 3): "連邦感謝祭",
        date(year, 12, 6): "サミクラウス（聖ニコラウスの日）",
        date(year, 12, 26): "聖シュテファンの日",
    }


def japan_events(year):
    """日本の行事 (祝日ではないもの) {date: 名前}"""

    return {
        setsubun(year): "節分",
        date(year, 3, 3): "ひなまつり",
        date(year, 7, 7): "七夕",
        date(year, 11, 15): "七五三",
        date(year, 12, 31): "大晦日",
    }


# スイスも日本も同じ日の行事 (旗をつけない)
def common_events(year):
    return {
        date(year, 2, 14): "💝 バレンタインデー",
        _nth_weekday(year, 5, 6, 2): "💐 母の日",
        date(year, 10, 31): "🎃 ハロウィン",
        date(year, 12, 24): "🎄 クリスマスイブ",
        date(year, 12, 25): "🎄 クリスマス",
    }


def day_events(day):
    """その日の祝日・行事のラベル (なければ空のリスト)。例: ["🇯🇵 春分の日", "🇨🇭 イースターマンデー"]"""

    try:
        labels = []
        common = common_events(day.year).get(day)
        if common:
            labels.append(common)
        japan = japan_holidays(day.year).get(day) or japan_events(day.year).get(day)
        if japan:
            labels.append(f"🇯🇵 {japan}")
        swiss = swiss_days(day.year).get(day)
        if swiss:
            labels.append(f"🇨🇭 {swiss}")
        return labels
    except Exception:
        return []
