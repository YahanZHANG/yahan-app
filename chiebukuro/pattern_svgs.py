# 着せかえの日本の模様 (chiebukuro.css の [data-cb-pattern="..."] の SVG) を作るスクリプト。
# 使い方: python chiebukuro/pattern_svgs.py /tmp/patterns.css → 中身を chiebukuro.css の模様の行と入れかえる
import math, urllib.parse
R3=math.sqrt(3)
def f(x): return f"{x:.2f}".rstrip("0").rstrip(".")
def svg(w,h,body,sw=1.4,size=None):
    # 白=見える線、黒=見えない。SVG内のマスクで重なりを処理し、結果は透明度だけ (CSS の mask-image に使う)
    s=(f"<svg xmlns='http://www.w3.org/2000/svg' width='{f(w)}' height='{f(h)}' viewBox='0 0 {f(w)} {f(h)}'>"
       f"<mask id='m'><rect width='{f(w)}' height='{f(h)}' fill='black'/><g fill='none' stroke='white' stroke-width='{sw}'>{body}</g></mask>"
       f"<rect width='{f(w)}' height='{f(h)}' fill='black' mask='url(#m)'/></svg>")
    return s, (size or (w,h))
def line(a,b): return f"<path d='M{f(a[0])} {f(a[1])}L{f(b[0])} {f(b[1])}'/>"

def asanoha(a=36):
    h=a*R3/2; out=[]
    for j in range(-2,6):
        for i in range(-2,4):
            x0=i*a+(j%2)*a/2; y=j*h
            up=[(x0,y),(x0+a,y),(x0+a/2,y+h)]          # 下向き三角形 (上辺が水平)
            dn=[(x0+a/2,y+h),(x0-a/2,y+h),(x0,y)]
            for t in (up,dn):
                c=(sum(p[0] for p in t)/3,sum(p[1] for p in t)/3)
                for k in range(3):
                    out.append(line(t[k],t[(k+1)%3])); out.append(line(t[k],c))
    return svg(a,2*h,"".join(out),1.1)
def kagome(a=32):
    h=a*R3/2; out=[]; L=6*a
    for k in range(-8,10):
        y=k*h+h/2; out.append(line((-a,y),(2*a,y)))
        x=k*a
        out.append(line((x-0.5*L,-R3/2*L),(x+0.5*L,R3/2*L)))
        out.append(line((x+0.5*L,-R3/2*L),(x-0.5*L,R3/2*L)))
    return svg(a,2*h,"".join(out),1.2)
def seigaiha(r=22):
    w,h=2*r,r; out=[]
    rows=[(0,h),(2*r,h),(r,h/2),(r,h*1.5),(0,0),(2*r,0),(r,-h/2)]
    order=sorted(rows,key=lambda c:c[1])
    for cx,cy in order:
        for k,rr in enumerate((r, r*0.72, r*0.44, r*0.16)):
            fill="black" if k==0 else "none"
            out.append(f"<circle cx='{f(cx)}' cy='{f(cy)}' r='{f(rr)}' fill='{fill}'/>")
    return svg(w,h,"".join(out),1.3)
def ichimatsu(s=18):
    w=2*s
    body=f"<rect x='0' y='0' width='{s}' height='{s}' fill='white' stroke='none'/><rect x='{s}' y='{s}' width='{s}' height='{s}' fill='white' stroke='none'/>"
    return svg(w,w,body)
def shippo(r=18):
    w=2*r; out=[]
    for cx,cy in ((0,0),(w,0),(0,w),(w,w),(r,r)):
        out.append(f"<circle cx='{cx}' cy='{cy}' r='{r}'/>")
    return svg(w,w,"".join(out),1.2)
def kikko(r=16):
    w=3*r; h=R3*r; out=[]
    for cx,cy in ((0,0),(w,0),(0,h),(w,h),(1.5*r,h/2),(1.5*r,-h/2),(1.5*r,1.5*h)):
        pts=[(cx+r*math.cos(math.pi/3*k),cy+r*math.sin(math.pi/3*k)) for k in range(6)]
        inner=[(cx+0.72*r*math.cos(math.pi/3*k),cy+0.72*r*math.sin(math.pi/3*k)) for k in range(6)]
        for P in (pts,inner):
            out.append("<path d='M"+"L".join(f"{f(x)} {f(y)}" for x,y in P)+"Z'/>")
    return svg(w,h,"".join(out),1.1)
def uroko(s=20):
    h=s*0.9; w=s; out=[]
    # 三角形を互い違いに塗る (鱗)
    for row in range(-1,3):
        off=(row%2)*w/2
        for i in range(-1,3):
            x=i*w+off; y=row*h
            out.append(f"<path d='M{f(x)} {f(y+h)}L{f(x+w/2)} {f(y)}L{f(x+w)} {f(y+h)}Z' fill='white' stroke='none'/>")
    return svg(w,2*h,"".join(out))
def hishi(w=28,h=40):
    out=[]
    for dx in (-w,0,w):
        for dy in (-h,0,h):
            cx,cy=dx+w/2,dy+h/2
            for k in (1,0.55):
                out.append(f"<path d='M{f(cx)} {f(cy-h/2*k)}L{f(cx+w/2*k)} {f(cy)}L{f(cx)} {f(cy+h/2*k)}L{f(cx-w/2*k)} {f(cy)}Z'/>")
    return svg(w,h,"".join(out),1.1)
def yagasuri(w=24,h=36):
    out=[]
    # 矢羽根: 縦の列ごとに上下さかさま、半分ずらす
    for col,(dx,flip) in enumerate(((0,1),(w/2,-1))):
        for dy in (-h,0,h):
            y=dy+(h/2 if col else 0)
            x0,x1=dx,dx+w/2
            if flip==1:
                pts=[(x0,y),(x1,y+h*0.3),(x1,y+h*0.8),(x0,y+h*0.5)]
            else:
                pts=[(x1,y),(x0,y+h*0.3),(x0,y+h*0.8),(x1,y+h*0.5)]
            out.append("<path d='M"+"L".join(f"{f(a)} {f(b)}" for a,b in pts)+"Z' fill='white' stroke='none'/>")
    return svg(w,h,"".join(out))
def sakura(s=60):
    def flower(cx,cy,r,rot):
        ps=[]
        for k in range(5):
            ang=rot+72*k
            ps.append(f"<ellipse cx='{f(cx)}' cy='{f(cy-r*0.55)}' rx='{f(r*0.36)}' ry='{f(r*0.55)}' transform='rotate({ang} {f(cx)} {f(cy)})' fill='white' stroke='none'/>")
        ps.append(f"<circle cx='{f(cx)}' cy='{f(cy)}' r='{f(r*0.16)}' fill='black' stroke='none'/>")
        return "".join(ps)
    body=flower(s*0.25,s*0.28,9,10)+flower(s*0.75,s*0.72,7,40)+flower(s*0.78,s*0.18,4.5,0)+flower(s*0.2,s*0.82,5,25)
    return svg(s,s,body)
PATTERNS=[("asanoha","麻の葉",asanoha),("seigaiha","青海波",seigaiha),("ichimatsu","市松",ichimatsu),("shippo","七宝",shippo),
          ("yagasuri","矢絣",yagasuri),("kikko","亀甲",kikko),("uroko","鱗",uroko),("kagome","籠目",kagome),("hishi","菱",hishi),("sakura","桜",sakura)]
css=[]
for key,label,fn in PATTERNS:
    s,(w,h)=fn()
    uri="data:image/svg+xml,"+urllib.parse.quote(s,safe=":/=' ,.-()")
    css.append(f'[data-cb-pattern="{key}"] {{ --cb-pattern: url("{uri}"); --cb-pattern-size: {f(w)}px {f(h)}px; }}')
open(__import__("sys").argv[1],"w").write("\n".join(css)+"\n")
print(len("".join(css)))
