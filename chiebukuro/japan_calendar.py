"""
HOME の上に出す「月の満ち欠け」と「六曜 (大安など)」。

外のサービスを使わず、天文の計算で出す (Jean Meeus『Astronomical Algorithms』の近似式)。
- 新月の時刻: 49章 (誤差は数分)
- 太陽の黄経: 25章の簡易式 (誤差 0.01 度ほど)
旧暦は「新月の日 (日本時間) が1日」「中気 (雨水・春分…) を含む月に月の番号を付け、
含まない月は閏月」の決まりで作り、六曜は (旧暦の月 + 日) を 6 で割った余りで決まる。
"""

import math
from datetime import date, datetime, timedelta, timezone


JST = timezone(timedelta(hours=9))
SYNODIC_MONTH = 29.530588861
ROKUYO = ["大安", "赤口", "先勝", "友引", "先負", "仏滅"]


def _jde_to_datetime(jde):
    """ユリウス日 (力学時。数十秒の差は無視) -> UTC の datetime"""
    return datetime(2000, 1, 1, 12, tzinfo=timezone.utc) + timedelta(days=jde - 2451545.0)


def _datetime_to_jde(moment):
    return 2451545.0 + (moment - datetime(2000, 1, 1, 12, tzinfo=timezone.utc)).total_seconds() / 86400


def new_moon_jde(k):
    """k 番目の新月 (k=0 が 2000年1月6日ごろ) の時刻 (JDE)"""

    t = k / 1236.85
    jde = 2451550.09766 + 29.530588861 * k + 0.00015437 * t ** 2 - 0.000000150 * t ** 3 + 0.00000000073 * t ** 4
    e = 1 - 0.002516 * t - 0.0000074 * t ** 2
    m = math.radians((2.5534 + 29.10535670 * k - 0.0000014 * t ** 2 - 0.00000011 * t ** 3) % 360)
    mp = math.radians((201.5643 + 385.81693528 * k + 0.0107582 * t ** 2 + 0.00001238 * t ** 3) % 360)
    f = math.radians((160.7108 + 390.67050284 * k - 0.0016118 * t ** 2 - 0.00000227 * t ** 3) % 360)
    om = math.radians((124.7746 - 1.56375588 * k + 0.0020672 * t ** 2 + 0.00000215 * t ** 3) % 360)
    jde += (
        -0.40720 * math.sin(mp) + 0.17241 * e * math.sin(m) + 0.01608 * math.sin(2 * mp)
        + 0.01039 * math.sin(2 * f) + 0.00739 * e * math.sin(mp - m) - 0.00514 * e * math.sin(mp + m)
        + 0.00208 * e * e * math.sin(2 * m) - 0.00111 * math.sin(mp - 2 * f) - 0.00057 * math.sin(mp + 2 * f)
        + 0.00056 * e * math.sin(2 * mp + m) - 0.00042 * math.sin(3 * mp) + 0.00042 * e * math.sin(m + 2 * f)
        + 0.00038 * e * math.sin(m - 2 * f) - 0.00024 * e * math.sin(2 * mp - m) - 0.00017 * math.sin(om)
        - 0.00007 * math.sin(mp + 2 * m) + 0.00004 * math.sin(2 * mp - 2 * f) + 0.00004 * math.sin(3 * m)
        + 0.00003 * math.sin(mp + m - 2 * f) + 0.00003 * math.sin(2 * mp + 2 * f) - 0.00003 * math.sin(mp + m + 2 * f)
        + 0.00003 * math.sin(mp - m + 2 * f) - 0.00002 * math.sin(mp - m - 2 * f) - 0.00002 * math.sin(3 * mp + m)
        + 0.00002 * math.sin(4 * mp)
    )
    return jde


def sun_longitude(jde):
    """太陽の見かけの黄経 (度)"""

    t = (jde - 2451545.0) / 36525
    l0 = 280.46646 + 36000.76983 * t + 0.0003032 * t * t
    m = math.radians(357.52911 + 35999.05029 * t - 0.0001537 * t * t)
    c = (1.914602 - 0.004817 * t - 0.000014 * t * t) * math.sin(m) + (0.019993 - 0.000101 * t) * math.sin(2 * m) + 0.000289 * math.sin(3 * m)
    omega = math.radians(125.04 - 1934.136 * t)
    return (l0 + c - 0.00569 - 0.00478 * math.sin(omega)) % 360


def _jst_date(jde):
    return _jde_to_datetime(jde).astimezone(JST).date()


def _new_moon_on_or_before(day):
    """その日 (日本時間) かそれより前の、いちばん近い新月の日と k"""

    noon = datetime(day.year, day.month, day.day, 23, 59, tzinfo=JST)
    k = math.floor((_datetime_to_jde(noon) - 2451550.09766) / SYNODIC_MONTH) + 1
    while _jst_date(new_moon_jde(k)) > day:
        k -= 1
    return k


def _chuki_month(start, end):
    """[start, end) (日本時間の日付) にある中気から、旧暦の月の番号。なければ None (閏月)"""

    jde = _datetime_to_jde(datetime(start.year, start.month, start.day, tzinfo=JST))
    end_jde = _datetime_to_jde(datetime(end.year, end.month, end.day, tzinfo=JST))
    longitude = sun_longitude(jde)
    target = (math.floor(longitude / 30) + 1) * 30 % 360  # 次の中気の黄経 (30 の倍数)
    # 太陽は 1日に約 0.9856 度進む。次の中気の時刻を少しずつ詰めて求める
    for _ in range(6):
        delta = (target - sun_longitude(jde)) % 360
        if delta > 300:
            delta -= 360
        jde += delta / 0.9856
    if start <= _jst_date(jde) < end:
        return (int(target // 30) + 2) % 12 or 12
    if jde >= end_jde:
        return None
    return None


def lunar_date(day):
    """旧暦の (月, 日, 閏月か)"""

    k = _new_moon_on_or_before(day)
    start = _jst_date(new_moon_jde(k))
    month = _chuki_month(start, _jst_date(new_moon_jde(k + 1)))
    leap = month is None
    back = k
    while month is None:
        back -= 1
        month = _chuki_month(_jst_date(new_moon_jde(back)), _jst_date(new_moon_jde(back + 1)))
    return month, (day - start).days + 1, leap


def rokuyo(day):
    month, lunar_day, _ = lunar_date(day)
    return ROKUYO[(month + lunar_day) % 6]


MOON_NAMES = [
    (1.0, "新月", "🌑"), (3.5, "三日月", "🌒"), (6.5, "三日月", "🌒"), (9.0, "上弦の月", "🌓"),
    (12.5, "十三夜", "🌔"), (13.8, "小望月", "🌔"), (15.8, "満月", "🌕"), (17.0, "十六夜", "🌖"),
    (20.5, "寝待月", "🌖"), (23.5, "下弦の月", "🌗"), (27.5, "有明月", "🌘"), (30.0, "新月", "🌑"),
]


def moon(moment=None):
    """
    今の月: 月齢・名前・絵文字・光っている割合 (0-1)・満ちていく途中か。
    「満月」は月齢 14.8〜15.8 ごろ (満月の瞬間の前後 12 時間ほど)。
    """

    moment = moment or datetime.now(timezone.utc)
    jde = _datetime_to_jde(moment)
    k = math.floor((jde - 2451550.09766) / SYNODIC_MONTH) + 1
    while new_moon_jde(k) > jde:
        k -= 1
    age = jde - new_moon_jde(k)
    phase = age / SYNODIC_MONTH
    lit = (1 - math.cos(2 * math.pi * phase)) / 2
    name, emoji = "新月", "🌑"
    for limit, label, icon in MOON_NAMES:
        if age < limit:
            name, emoji = label, icon
            break
    if 14.3 <= age <= 15.8 or lit >= 0.985:
        name, emoji = "満月", "🌕"
    return {"age": round(age, 1), "name": name, "emoji": emoji, "lit": lit, "waxing": phase < 0.5}


def moon_path(cx, cy, r, lit, waxing):
    """月の光っている部分の SVG path (満ち欠けの形)"""

    if lit < 0.02:
        return ""
    if lit > 0.98:
        return f"M{cx - r} {cy} a{r} {r} 0 1 0 {2 * r} 0 a{r} {r} 0 1 0 {-2 * r} 0Z"
    rx = abs(1 - 2 * lit) * r
    outer = 1 if waxing else 0          # 右側 (満ちていく) / 左側 (欠けていく) の半円
    inner = (0 if lit < 0.5 else 1) if waxing else (1 if lit < 0.5 else 0)
    return f"M{cx} {cy - r} A{r} {r} 0 0 {outer} {cx} {cy + r} A{rx:.2f} {r} 0 0 {inner} {cx} {cy - r}Z"


def today_info(day=None, moment=None):
    day = day or datetime.now(JST).date()
    info = moon(moment)
    try:
        info["rokuyo"] = rokuyo(day)
    except Exception:
        info["rokuyo"] = ""
    return info
