# 着せかえの日本の模様 (chiebukuro.css の [data-cb-pattern="..."] の SVG) を作るスクリプト。
# 2026-11-18 Taro: 着せかえの色とは掛け合わせず、その模様本来の和の色で。
# 使い方: python chiebukuro/pattern_svgs.py /tmp/patterns.css → 中身を chiebukuro.css の模様の行と入れかえる
import math
import sys
import urllib.parse

R3 = math.sqrt(3)

# 和の色
BENI = "#c0395a"        # 紅
TOKI = "#f4b3c2"        # 鴇色
AI = "#1f4e8c"          # 藍
ASAGI = "#5ba3c9"       # 浅葱
KURO = "#23272b"        # 墨
TOKIWA = "#2e7d5b"      # 常磐色
KIN = "#c39a2b"         # 金茶
YAMABUKI = "#e7b53c"    # 山吹
MURASAKI = "#6b3f8f"    # 江戸紫
FUJI = "#b9a2d6"        # 藤色
ROKUSHO = "#3f8a78"     # 緑青
SHU = "#d0573c"         # 朱
TORINOKO = "#f3e3c3"    # 鳥の子色
AINEZU = "#3f5d7d"      # 藍鼠
ENJI = "#9b2d4a"        # 臙脂
SAKURA = "#f2a7bd"      # 桜色


def f(x):
    return f"{x:.2f}".rstrip("0").rstrip(".")


def svg(w, h, body):
    return (w, h, f"<svg xmlns='http://www.w3.org/2000/svg' width='{f(w)}' height='{f(h)}' viewBox='0 0 {f(w)} {f(h)}'>{body}</svg>")


def line(a, b):
    return f"<path d='M{f(a[0])} {f(a[1])}L{f(b[0])} {f(b[1])}'/>"


def poly(points, attrs=""):
    return "<path d='M" + "L".join(f"{f(x)} {f(y)}" for x, y in points) + f"Z'{attrs}/>"


def asanoha(a=36):
    # 麻の葉: 紅の線。三角形の格子と、各三角形の頂点から重心への線
    h = a * R3 / 2
    out = []
    for j in range(-2, 6):
        for i in range(-2, 4):
            x0 = i * a + (j % 2) * a / 2
            y = j * h
            for t in ([(x0, y), (x0 + a, y), (x0 + a / 2, y + h)], [(x0 + a / 2, y + h), (x0 - a / 2, y + h), (x0, y)]):
                c = (sum(p[0] for p in t) / 3, sum(p[1] for p in t) / 3)
                for k in range(3):
                    out.append(line(t[k], t[(k + 1) % 3]))
                    out.append(line(t[k], c))
    return svg(a, 2 * h, f"<g stroke='{BENI}' stroke-width='1.2' fill='none'>{''.join(out)}</g>")


def seigaiha(r=24):
    # 青海波: 藍と浅葱の波を交互に
    w, h = 2 * r, r
    centers = sorted([(0, h), (2 * r, h), (r, h / 2), (r, h * 1.5), (0, 0), (2 * r, 0), (r, -h / 2), (0, 2 * h), (2 * r, 2 * h)], key=lambda c: c[1])
    out = []
    for cx, cy in centers:
        for k, rr in enumerate((r, r * 0.8, r * 0.6, r * 0.4, r * 0.2)):
            out.append(f"<circle cx='{f(cx)}' cy='{f(cy)}' r='{f(rr)}' fill='{AI if k % 2 == 0 else ASAGI}'/>")
    return svg(w, h, "".join(out))


def ichimatsu(s=20):
    # 市松: 墨と常磐色
    w = 2 * s
    return svg(w, w, f"<rect width='{w}' height='{w}' fill='{TOKIWA}'/><rect width='{s}' height='{s}' fill='{KURO}'/><rect x='{s}' y='{s}' width='{s}' height='{s}' fill='{KURO}'/>")


def shippo(r=20):
    # 七宝: 金茶の輪、重なりの中に山吹の花菱
    w = 2 * r
    out = [f"<g fill='none' stroke='{KIN}' stroke-width='1.5'>"]
    for cx, cy in ((0, 0), (w, 0), (0, w), (w, w), (r, r)):
        out.append(f"<circle cx='{cx}' cy='{cy}' r='{r}'/>")
    out.append("</g>")
    for cx, cy in ((r, 0), (0, r), (w, r), (r, w)):
        d = r * 0.16
        out.append(poly([(cx, cy - d), (cx + d, cy), (cx, cy + d), (cx - d, cy)], f" fill='{YAMABUKI}'"))
    return svg(w, w, "".join(out))


def yagasuri(w=24, h=40):
    # 矢絣: 江戸紫と藤色の矢羽根を交互の列に
    out = [f"<rect width='{w}' height='{h}' fill='{FUJI}'/>"]
    for col, dx in enumerate((0, w / 2)):
        for dy in (-h, 0, h):
            y = dy + (h / 2 if col else 0)
            x0, x1 = dx, dx + w / 2
            if col == 0:
                pts = [(x0, y), (x1, y + h * 0.3), (x1, y + h * 0.8), (x0, y + h * 0.5)]
            else:
                pts = [(x1, y), (x0, y + h * 0.3), (x0, y + h * 0.8), (x1, y + h * 0.5)]
            out.append(poly(pts, f" fill='{MURASAKI}'"))
    return svg(w, h, "".join(out))


def kikko(r=18):
    # 亀甲: 緑青の二重の六角形と、中に小さな花
    w, h = 3 * r, R3 * r
    out = []
    for cx, cy in ((0, 0), (w, 0), (0, h), (w, h), (1.5 * r, h / 2), (1.5 * r, -h / 2), (1.5 * r, 1.5 * h)):
        for k, sw in ((1, 1.4), (0.78, 0.8)):
            pts = [(cx + k * r * math.cos(math.pi / 3 * i), cy + k * r * math.sin(math.pi / 3 * i)) for i in range(6)]
            out.append(poly(pts, f" fill='none' stroke='{ROKUSHO}' stroke-width='{sw}'"))
        out.append(f"<circle cx='{f(cx)}' cy='{f(cy)}' r='{f(r * 0.14)}' fill='{ROKUSHO}'/>")
    return svg(w, h, "".join(out))


def uroko(s=22):
    # 鱗: 朱と鳥の子色の三角
    h = s * 0.9
    out = [f"<rect width='{s}' height='{f(2 * h)}' fill='{TORINOKO}'/>"]
    for row in range(-1, 3):
        off = (row % 2) * s / 2
        for i in range(-1, 3):
            x, y = i * s + off, row * h
            out.append(poly([(x, y + h), (x + s / 2, y), (x + s, y + h)], f" fill='{SHU}'"))
    return svg(s, 2 * h, "".join(out))


def kagome(a=34):
    # 籠目: 藍鼠の線を3方向に編む
    h = a * R3 / 2
    big = 6 * a
    out = []
    for k in range(-8, 10):
        y = k * h + h / 2
        out.append(line((-a, y), (2 * a, y)))
        x = k * a
        out.append(line((x - 0.5 * big, -R3 / 2 * big), (x + 0.5 * big, R3 / 2 * big)))
        out.append(line((x + 0.5 * big, -R3 / 2 * big), (x - 0.5 * big, R3 / 2 * big)))
    return svg(a, 2 * h, f"<g stroke='{AINEZU}' stroke-width='1.6' fill='none'>{''.join(out)}</g>")


def hishi(w=30, h=44):
    # 菱: 臙脂の菱と、中に小さな菱
    out = []
    for dx in (-w, 0, w):
        for dy in (-h, 0, h):
            for cx, cy in ((dx + w / 2, dy + h / 2), (dx, dy), (dx + w, dy + h)):
                out.append(poly([(cx, cy - h / 2 * 0.9), (cx + w / 2 * 0.9, cy), (cx, cy + h / 2 * 0.9), (cx - w / 2 * 0.9, cy)], f" fill='none' stroke='{ENJI}' stroke-width='1.2'"))
                out.append(poly([(cx, cy - h * 0.12), (cx + w * 0.12, cy), (cx, cy + h * 0.12), (cx - w * 0.12, cy)], f" fill='{ENJI}'"))
    return svg(w, h, "".join(out))


def sakura(s=64):
    # 桜: 桜色の花びらと紅のしべ
    def flower(cx, cy, r, rot, color):
        out = []
        for k in range(5):
            out.append(f"<ellipse cx='{f(cx)}' cy='{f(cy - r * 0.55)}' rx='{f(r * 0.38)}' ry='{f(r * 0.56)}' transform='rotate({rot + 72 * k} {f(cx)} {f(cy)})' fill='{color}'/>")
        out.append(f"<circle cx='{f(cx)}' cy='{f(cy)}' r='{f(r * 0.17)}' fill='{BENI}'/>")
        return "".join(out)

    body = flower(s * 0.25, s * 0.28, 10, 10, SAKURA) + flower(s * 0.75, s * 0.72, 8, 40, TOKI) + flower(s * 0.8, s * 0.18, 5, 0, SAKURA) + flower(s * 0.2, s * 0.82, 5.5, 25, TOKI)
    return svg(s, s, body)


PATTERNS = [
    ("asanoha", asanoha), ("seigaiha", seigaiha), ("ichimatsu", ichimatsu), ("shippo", shippo), ("yagasuri", yagasuri),
    ("kikko", kikko), ("uroko", uroko), ("kagome", kagome), ("hishi", hishi), ("sakura", sakura),
]


def main(path):
    rows = []
    for key, build in PATTERNS:
        w, h, text = build()
        uri = "data:image/svg+xml," + urllib.parse.quote(text, safe=":/=' ,.-()")
        rows.append(f'[data-cb-pattern="{key}"] {{ --cb-pattern: url("{uri}"); --cb-pattern-size: {f(w)}px {f(h)}px; }}')
    with open(path, "w") as out:
        out.write("\n".join(rows) + "\n")


if __name__ == "__main__":
    main(sys.argv[1])
