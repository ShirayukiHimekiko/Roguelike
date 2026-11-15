#!/usr/bin/env python3
"""numspec：把参照里量到的数字变成“可检验的目标”和“可填进引擎的参数”，再拿当前版逐条核。

为什么有这个工具：measure / crops 能量出参照的颜色和尺寸，但从“截图上的数”到“shader 里该填什么”、
再到“当前版这条特征到底达到没有”，中间三步最容易凭感觉：
  1. 截图颜色是光照 + 色调映射之后的显示颜色，不是材质颜色；Unity 线性工程里 Color 属性和 Vector 属性要的值也不一样。
  2. “泡沫宽约画面高 1.5%”是屏幕量，填进 shader 要换成世界单位，和视场角、距离、俯视角都有关。
  3. “接近了”要有容差：用感知色差（CIEDE2000）判断，不用 RGB 差。

子命令（--json 输出 JSON，放在子命令前后都行）：
  extract IMG --regions "近岸=…;中段=…;远处=…" --feature T1 --out SPEC.json [--line x0,y0,x1,y1]
                 从参照取各区域目标色（sRGB、线性、Lab）写进 SPEC.json；同一 SPEC 可多次 extract，追加别的特征
  check   IMG --spec SPEC.json [--regions …]
                 当前版按同名区域逐个算 ΔE2000 → 每个区域 达到/接近/未达 → 每条特征的状态，
                 并给出能直接贴给 wavelog end 的 --status
  steps   IMG --line x0,y0,x1,y1 [--min-de 6]
                 沿一条线（近→远）数可区分的色阶：给 “至少 3 个色阶” 这类特征一个客观数
  engine  --spec SPEC.json [--ramp ramp.png --ramp-steps 3]
                 把目标色换成引擎值：Color 属性用 sRGB、Vector/float 用线性；可输出色带贴图（硬边分段或平滑）
  world   --pct 1.5 --vfov 60 --dist 20 [--grazing 15]
                 屏幕高度百分比 → 世界尺寸（米）；给了掠射角就换算成沿水面的宽度

坐标：≤1 的值按比例，否则按像素。区域写法同 refgrab crops："名=x0,y0,x1,y1;名=…"。
调用：python -X utf8 "<本 Skill 目录>\\scripts\\numspec.py" <子命令> …
退出码：0 正常；2 出错；4 check 有特征未达 / steps 色阶少于 --need。
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

LEVELS = ["未达", "接近", "达到"]


class Fail(Exception):
    pass


# --------------------------------------------------------------------------- 颜色换算（sRGB D65）

def srgb_to_linear(c: float) -> float:
    c /= 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def linear_to_srgb8(v: float) -> int:
    v = min(1.0, max(0.0, v))
    s = v * 12.92 if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055
    return round(s * 255)


def rgb_to_lab(rgb) -> list[float]:
    r, g, b = (srgb_to_linear(c) for c in rgb)
    x = (0.4124564 * r + 0.3575761 * g + 0.1804375 * b) / 0.95047
    y = 0.2126729 * r + 0.7151522 * g + 0.0721750 * b
    z = (0.0193339 * r + 0.1191920 * g + 0.9503041 * b) / 1.08883

    def f(t):
        return t ** (1 / 3) if t > 216 / 24389 else (24389 / 27 * t + 16) / 116
    fx, fy, fz = f(x), f(y), f(z)
    return [round(116 * fy - 16, 3), round(500 * (fx - fy), 3), round(200 * (fy - fz), 3)]


def de2000(lab1, lab2) -> float:
    """CIEDE2000 色差（Sharma 2005 实现）。约 1 = 刚能察觉；2–3 = 仔细并排才看得出；>10 = 明显不同。"""
    L1, a1, b1 = lab1
    L2, a2, b2 = lab2
    C1, C2 = math.hypot(a1, b1), math.hypot(a2, b2)
    Cm = (C1 + C2) / 2
    G = 0.5 * (1 - math.sqrt(Cm ** 7 / (Cm ** 7 + 25 ** 7)))
    a1p, a2p = (1 + G) * a1, (1 + G) * a2
    C1p, C2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p = math.degrees(math.atan2(b1, a1p)) % 360
    h2p = math.degrees(math.atan2(b2, a2p)) % 360
    dLp = L2 - L1
    dCp = C2p - C1p
    if C1p * C2p == 0:
        dhp = 0.0
    elif abs(h2p - h1p) <= 180:
        dhp = h2p - h1p
    elif h2p - h1p > 180:
        dhp = h2p - h1p - 360
    else:
        dhp = h2p - h1p + 360
    dHp = 2 * math.sqrt(C1p * C2p) * math.sin(math.radians(dhp / 2))
    Lpm = (L1 + L2) / 2
    Cpm = (C1p + C2p) / 2
    if C1p * C2p == 0:
        hpm = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        hpm = (h1p + h2p) / 2
    elif h1p + h2p < 360:
        hpm = (h1p + h2p + 360) / 2
    else:
        hpm = (h1p + h2p - 360) / 2
    T = (1 - 0.17 * math.cos(math.radians(hpm - 30)) + 0.24 * math.cos(math.radians(2 * hpm))
         + 0.32 * math.cos(math.radians(3 * hpm + 6)) - 0.20 * math.cos(math.radians(4 * hpm - 63)))
    dtheta = 30 * math.exp(-(((hpm - 275) / 25) ** 2))
    Rc = 2 * math.sqrt(Cpm ** 7 / (Cpm ** 7 + 25 ** 7))
    Sl = 1 + 0.015 * (Lpm - 50) ** 2 / math.sqrt(20 + (Lpm - 50) ** 2)
    Sc = 1 + 0.045 * Cpm
    Sh = 1 + 0.015 * Cpm * T
    Rt = -math.sin(math.radians(2 * dtheta)) * Rc
    return math.sqrt((dLp / Sl) ** 2 + (dCp / Sc) ** 2 + (dHp / Sh) ** 2 + Rt * (dCp / Sc) * (dHp / Sh))


def lch(lab):
    L, a, b = lab
    return L, math.hypot(a, b), math.degrees(math.atan2(b, a)) % 360


def describe_gap(ref_lab, cur_lab) -> str:
    """用白话说当前色相对目标偏在哪：明暗、鲜灰、色相方向。"""
    L1, C1, h1 = lch(ref_lab)
    L2, C2, h2 = lch(cur_lab)
    parts = []
    if abs(L2 - L1) >= 4:
        parts.append(("偏亮" if L2 > L1 else "偏暗") + f" {L2 - L1:+.0f}")
    if abs(C2 - C1) >= 4:
        parts.append(("偏鲜" if C2 > C1 else "偏灰") + f" {C2 - C1:+.0f}")
    if C1 >= 8 and C2 >= 8:
        dh = (h2 - h1 + 180) % 360 - 180
        if abs(dh) >= 8:
            parts.append(f"色相偏 {dh:+.0f}°（{'偏黄绿' if dh < 0 and 150 < h1 < 280 else '偏紫' if dh > 0 and 150 < h1 < 280 else '偏移'}）")
    return "、".join(parts) or "接近"


# --------------------------------------------------------------------------- 取样

def load(path: str):
    from PIL import Image
    p = Path(path)
    if not p.is_file():
        raise Fail(f"找不到图片：{p}")
    return Image.open(p).convert("RGB")


def parse_regions(spec: str) -> list[tuple[str, str]]:
    import refgrab
    return refgrab.parse_regions(spec)


def region_color(im, box_spec: str) -> dict:
    """区域中位色（不被零星高光带偏）。"""
    import refgrab
    from PIL import ImageStat
    box = refgrab._box(box_spec, im.width, im.height)
    crop = im.crop(box)
    crop.thumbnail((256, 256))
    med = [round(v) for v in ImageStat.Stat(crop).median]
    return {"box": box, "srgb": med, "hex": "#%02x%02x%02x" % tuple(med), "lab": rgb_to_lab(med),
            "linear": [round(srgb_to_linear(c), 4) for c in med]}


def line_samples(im, line: str, n: int = 120) -> list[list[int]]:
    """沿线取 n 个点，每点取 5x5 邻域中位色（抗噪点和细碎高光）。"""
    from PIL import ImageStat
    v = [float(t) for t in line.split(",")]
    if len(v) != 4:
        raise Fail(f"--line 要 4 个数 x0,y0,x1,y1：{line}")
    w, h = im.size
    x0, y0, x1, y1 = [(t * (w - 1) if t <= 1 else t) for t, w in zip(v, (w, h, w, h))]
    out = []
    for i in range(n):
        t = i / (n - 1)
        x, y = round(x0 + (x1 - x0) * t), round(y0 + (y1 - y0) * t)
        if not (0 <= x < w and 0 <= y < h):
            raise Fail(f"--line 有点在图外（图 {w}x{h}）：{line}")
        box = (max(0, x - 2), max(0, y - 2), min(w, x + 3), min(h, y + 3))
        out.append([round(c) for c in ImageStat.Stat(im.crop(box)).median])
    return out


def count_steps(samples: list[list[int]], min_de: float, min_frac: float = 0.06) -> list[dict]:
    """按色差把沿线颜色分段：和当前段均色差 ≥ min_de 且新颜色持续 ≥ min_frac 长度才算新的一阶。
    短于 min_frac 的突变（高光、泡沫点）并回所在段。"""
    labs = [rgb_to_lab(s) for s in samples]
    n = len(labs)
    min_len = max(2, round(n * min_frac))
    bands = []
    start = 0
    i = 1
    while i <= n:
        if i == n:
            bands.append((start, n))
            break
        seg = labs[start:i]
        mean = [sum(c[k] for c in seg) / len(seg) for k in range(3)]
        # 往后看 min_len 个点，都和当前段差得多才切
        ahead = labs[i:i + min_len]
        if len(ahead) == min_len and all(de2000(mean, a) >= min_de for a in ahead) and i - start >= min_len:
            bands.append((start, i))
            start = i
        i += 1
    out = []
    for a, b in bands:
        seg = samples[a:b]
        med = [sorted(c[k] for c in seg)[len(seg) // 2] for k in range(3)]
        out.append({"from": round(a / (n - 1), 3), "to": round((b - 1) / (n - 1), 3), "srgb": med,
                    "hex": "#%02x%02x%02x" % tuple(med), "lab": rgb_to_lab(med)})
    # 相邻段若中位色其实很近（渐变被切碎），合并
    merged = []
    for bnd in out:
        if merged and de2000(merged[-1]["lab"], bnd["lab"]) < min_de:
            merged[-1]["to"] = bnd["to"]
        else:
            merged.append(bnd)
    return merged


# --------------------------------------------------------------------------- SPEC 文件

def read_spec(path: Path) -> dict:
    if not path.is_file():
        raise Fail(f"找不到 {path}：先用 extract 从参照生成")
    return json.loads(path.read_text(encoding="utf-8"))


def write_spec(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def level_for(de: float, tol: dict) -> str:
    return "达到" if de <= tol["met"] else "接近" if de <= tol["near"] else "未达"


# --------------------------------------------------------------------------- 子命令

def cmd_extract(args):
    im = load(args.image)
    path = Path(args.out)
    spec = read_spec(path) if path.is_file() else {"regions": {}, "features": {}, "tolerance": {"met": args.met, "near": args.near}}
    regs = parse_regions(args.regions)
    names = []
    for name, box in regs:
        c = region_color(im, box)
        c.update(source=str(Path(args.image)), feature=args.feature, time=time.strftime("%Y-%m-%dT%H:%M:%S"))
        spec["regions"][name] = c
        names.append(name)
    feat = spec["features"].setdefault(args.feature, {"regions": [], "note": args.note or ""})
    feat["regions"] = list(dict.fromkeys(feat["regions"] + names))
    if args.note:
        feat["note"] = args.note
    if args.line:
        bands = count_steps(line_samples(im, args.line), args.min_de)
        feat["steps"] = {"line": args.line, "count": len(bands), "minDe": args.min_de, "need": args.need or len(bands)}
    write_spec(path, spec)
    if args.json:
        print(json.dumps(spec, ensure_ascii=False, indent=1))
        return 0
    for n in names:
        r = spec["regions"][n]
        print(f"{args.feature} {n}：{r['hex']}  sRGB{tuple(r['srgb'])}  线性{tuple(r['linear'])}  Lab{tuple(round(x, 1) for x in r['lab'])}")
    if args.line:
        s = feat["steps"]
        print(f"{args.feature} 沿线色阶：{s['count']} 阶（色差阈值 {s['minDe']}），check 时要求 ≥ {s['need']}")
    print(f"已写入 {path}。注意：这是截图上的显示颜色（含光照和色调映射），是比较目标，不是材质参数；"
          "材质起始值用 engine 子命令换算，最终以同机位截图 check 为准。")
    return 0


def cmd_check(args):
    spec = read_spec(Path(args.spec))
    im = load(args.image)
    tol = spec.get("tolerance", {"met": 3.0, "near": 8.0})
    boxes = dict(parse_regions(args.regions)) if args.regions else {n: ",".join(map(str, r["box"])) for n, r in spec["regions"].items()}
    missing = [n for n in spec["regions"] if n not in boxes]
    if missing and args.regions:
        raise Fail(f"--regions 缺少 SPEC 里的区域：{'、'.join(missing)}（名字要一致）")
    rows = []
    for name, ref in spec["regions"].items():
        cur = region_color(im, boxes[name])
        de = round(de2000(ref["lab"], cur["lab"]), 1)
        rows.append({"region": name, "feature": ref.get("feature"), "target": ref["hex"], "current": cur["hex"], "de": de,
                     "level": level_for(de, tol), "gap": describe_gap(ref["lab"], cur["lab"])})
    feats = {}
    for fid, f in spec["features"].items():
        lv = [r["level"] for r in rows if r["region"] in f["regions"]]
        level = min(lv, key=LEVELS.index) if lv else "达到"
        info = {"level": level, "regions": f["regions"]}
        if "steps" in f:
            line = args.line or f["steps"]["line"]
            got = len(count_steps(line_samples(im, line), f["steps"]["minDe"]))
            info["steps"] = {"count": got, "need": f["steps"]["need"]}
            if got < f["steps"]["need"]:
                level = "未达" if got < f["steps"]["need"] - 1 else min(level, "接近", key=LEVELS.index)
            info["level"] = level
        feats[fid] = info
    status = ",".join(f"{k}={v['level']}" for k, v in feats.items())
    if args.regions is None and spec["regions"]:
        note = "没给 --regions：沿用参照的框。只有当前版和参照同构图时才成立；构图不同请给当前版自己的框（同名）"
    else:
        note = ""
    out = {"regions": rows, "features": feats, "status": status, "tolerance": tol, "note": note}
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        for r in rows:
            print(f"[{r['level']}] {r['feature']} {r['region']}：目标 {r['target']} 当前 {r['current']}  ΔE {r['de']}  {r['gap']}")
        for fid, f in feats.items():
            extra = f"；色阶 {f['steps']['count']}/{f['steps']['need']}" if "steps" in f else ""
            print(f"特征 {fid}：{f['level']}{extra}")
        print(f"容差：ΔE2000 ≤{tol['met']} 达到，≤{tol['near']} 接近。贴给 wavelog：--status {status}")
        if note:
            print("注意：" + note)
        print("数字过关不等于像：最后仍要亲眼看 [参照|当前] 并排图。")
    return 4 if any(f["level"] == "未达" for f in feats.values()) else 0


def cmd_steps(args):
    im = load(args.image)
    bands = count_steps(line_samples(im, args.line), args.min_de)
    if args.json:
        print(json.dumps({"count": len(bands), "bands": bands}, ensure_ascii=False, indent=1))
    else:
        print(f"沿线 {len(bands)} 个可区分色阶（相邻色差 ≥ {args.min_de}，短于 6% 线长的突变不算）：")
        for i, b in enumerate(bands, 1):
            print(f"  {i}. {b['from']:.2f}–{b['to']:.2f}  {b['hex']}  L{b['lab'][0]:.0f}")
        if len(bands) >= 2:
            des = [round(de2000(a["lab"], b["lab"]), 1) for a, b in zip(bands, bands[1:])]
            print("  相邻阶色差：" + " / ".join(map(str, des)))
    return 4 if args.need and len(bands) < args.need else 0


def ramp_image(colors: list[list[int]], out: Path, width: int, steps: int | None):
    """色带贴图：steps 给定 → 等宽硬边分段（风格化色阶）；否则在线性空间平滑插值（避免 sRGB 插值发灰）。"""
    from PIL import Image
    im = Image.new("RGB", (width, 4))
    px = im.load()
    lin = [[srgb_to_linear(c) for c in col] for col in colors]
    for x in range(width):
        t = x / (width - 1)
        if steps:
            k = min(steps - 1, int(t * steps))
            u = k / (steps - 1) if steps > 1 else 0
        else:
            u = t
        pos = u * (len(lin) - 1)
        i = min(len(lin) - 2, int(pos)) if len(lin) > 1 else 0
        f = pos - i if len(lin) > 1 else 0
        c = [linear_to_srgb8(lin[i][k] * (1 - f) + lin[min(i + 1, len(lin) - 1)][k] * f) for k in range(3)]
        for y in range(4):
            px[x, y] = tuple(c)
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out)
    return out


def cmd_engine(args):
    spec = read_spec(Path(args.spec))
    names = [n.strip() for n in args.order.split(",")] if args.order else list(spec["regions"])
    bad = [n for n in names if n not in spec["regions"]]
    if bad:
        raise Fail(f"--order 里 {'、'.join(bad)} 不在 SPEC 里")
    rows = []
    for n in names:
        r = spec["regions"][n]
        s = [c / 255 for c in r["srgb"]]
        rows.append({"region": n, "hex": r["hex"], "srgb01": [round(c, 4) for c in s], "linear": r["linear"],
                     "unityColor": "new Color({:.3f}f, {:.3f}f, {:.3f}f)".format(*s),
                     "unityVectorLinear": "new Vector4({:.4f}f, {:.4f}f, {:.4f}f, 1f)".format(*r["linear"])})
    ramp = None
    if args.ramp:
        ramp = str(ramp_image([spec["regions"][n]["srgb"] for n in names], Path(args.ramp), args.width, args.ramp_steps))
    if args.json:
        print(json.dumps({"values": rows, "ramp": ramp}, ensure_ascii=False, indent=1))
        return 0
    for r in rows:
        print(f"{r['region']}：{r['hex']}")
        print(f"  Color 属性（材质面板 / material.SetColor）：{r['unityColor']}  ← 填 sRGB，线性工程里 Unity 自己转")
        print(f"  Vector / float 属性（不会自动转）：{r['unityVectorLinear']}  ← 已是线性值")
    if ramp:
        mode = f"{args.ramp_steps} 阶硬边" if args.ramp_steps else "线性空间平滑"
        print(f"色带贴图：{ramp}（{mode}，顺序 {' → '.join(names)}）。导入设置：勾 sRGB (Color Texture)，Wrap=Clamp，"
              + ("Filter=Point（保住硬边）" if args.ramp_steps else "Filter=Bilinear"))
    print("这些值来自截图，已经包含光照、雾和色调映射：只能当起始值。填进去后同机位截图，用 check 和参照比，按 ΔE 往回调。")
    return 0


def cmd_world(args):
    if not (0 < args.vfov < 179):
        raise Fail("--vfov 要在 0–179 度之间（Unity 相机的 Field of View 默认是竖直视场角）")
    if args.dist <= 0:
        raise Fail("--dist 要大于 0：相机到被量位置的距离（米）")
    perp = args.pct / 100 * 2 * args.dist * math.tan(math.radians(args.vfov / 2))
    out = {"screenPct": args.pct, "vfov": args.vfov, "dist": args.dist, "perpendicularMeters": round(perp, 4)}
    if args.grazing is not None:
        if not (0 < args.grazing <= 90):
            raise Fail("--grazing 要在 (0, 90] 度：视线和水面的夹角，俯视 90，贴水平看接近 0")
        along = perp / math.sin(math.radians(args.grazing))
        out["alongSurfaceMeters"] = round(along, 4)
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 0
    print(f"画面高 {args.pct}% 在 {args.dist} 米处（竖直视场角 {args.vfov}°）≈ 垂直视线方向 {perp:.3f} 米")
    if "alongSurfaceMeters" in out:
        print(f"视线与水面夹角 {args.grazing}° → 沿水面的实际宽度 ≈ {out['alongSurfaceMeters']:.3f} 米"
              "（夹角越小，同样的屏幕宽度对应的水面越宽）")
        if args.grazing < 10:
            print("注意：夹角 <10° 时结果对角度非常敏感，量两三个距离取中间值。")
    else:
        print("提示：泡沫带、岸线这类贴在水面上的东西，加 --grazing <视线与水面夹角> 才是 shader 里要的宽度。")
    print("参照是别的游戏的截图时，视场角和距离只能估：先估一个起始值，再在自己的主机位截图上量回 --pct 对照。")
    return 0


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name, text, epilog=None):
        return sub.add_parser(name, parents=[common], help=text, description=text, epilog=epilog,
                              formatter_class=argparse.RawDescriptionHelpFormatter)

    p = add("extract", "从参照取各区域目标色写进 SPEC.json（同一 SPEC 可多次追加别的特征）",
            '例：extract R1.png --feature T1 --regions "近岸=0.1,0.75,0.4,0.95;中段=0.3,0.55,0.7,0.65;远处=0.2,0.36,0.8,0.42" '
            '--line 0.5,0.95,0.5,0.36 --out SPEC.json')
    p.add_argument("image"); p.add_argument("--regions", required=True, help='"名=x0,y0,x1,y1;名=…"')
    p.add_argument("--feature", required=True, help="这些区域属于哪条 TARGET 特征，如 T1")
    p.add_argument("--out", default="SPEC.json"); p.add_argument("--note", help="一句话：这条特征看什么")
    p.add_argument("--line", help="近→远的一条线 x0,y0,x1,y1：顺带数参照的色阶，check 时要求不少于它")
    p.add_argument("--need", type=int, help="色阶最少要几阶（默认 = 参照数出来的阶数）")
    p.add_argument("--min-de", type=float, default=6.0, help="相邻两阶至少差多少 ΔE2000 才算可区分，默认 6")
    p.add_argument("--met", type=float, default=3.0, help="ΔE ≤ 此值算达到（新建 SPEC 时生效），默认 3")
    p.add_argument("--near", type=float, default=8.0, help="ΔE ≤ 此值算接近，默认 8")

    p = add("check", "当前版逐区域算 ΔE2000，给出每条特征的 达到/接近/未达 和 wavelog 的 --status",
            '例：check v3_main.png --spec SPEC.json --regions "近岸=…;中段=…;远处=…" --line 0.5,0.95,0.5,0.4')
    p.add_argument("image"); p.add_argument("--spec", default="SPEC.json")
    p.add_argument("--regions", help="当前版自己的框（名字与 SPEC 一致）；不给就沿用参照的框")
    p.add_argument("--line", help="当前版数色阶用的线；不给就沿用参照的线")

    p = add("steps", "沿一条线数可区分的色阶", "例：steps R1.png --line 0.5,0.95,0.5,0.36 --need 3")
    p.add_argument("image"); p.add_argument("--line", required=True)
    p.add_argument("--min-de", type=float, default=6.0); p.add_argument("--need", type=int, help="少于这么多阶退出码 4")

    p = add("engine", "目标色 → 引擎值（Color 用 sRGB，Vector 用线性），可出色带贴图",
            "例：engine --spec SPEC.json --order 近岸,中段,远处 --ramp ramp.png --ramp-steps 3")
    p.add_argument("--spec", default="SPEC.json"); p.add_argument("--order", help="区域顺序（色带从左到右），逗号分隔")
    p.add_argument("--ramp", help="输出色带贴图 PNG"); p.add_argument("--ramp-steps", type=int, help="硬边分几段；不给 = 平滑")
    p.add_argument("--width", type=int, default=256)

    p = add("world", "屏幕高度百分比 → 世界尺寸（米）", "例：world --pct 1.5 --vfov 60 --dist 20 --grazing 15")
    p.add_argument("--pct", type=float, required=True, help="refgrab measure --line 给的“占画面高 %%”")
    p.add_argument("--vfov", type=float, default=60, help="竖直视场角（度），Unity 相机默认 60")
    p.add_argument("--dist", type=float, required=True, help="相机到被量位置的距离（米）")
    p.add_argument("--grazing", type=float, help="视线和水面的夹角（度）：俯视 90，平视接近 0")

    args = ap.parse_args(argv)
    func = {"extract": cmd_extract, "check": cmd_check, "steps": cmd_steps, "engine": cmd_engine, "world": cmd_world}[args.cmd]
    try:
        return func(args) or 0
    except Fail as e:
        print(f"失败：{e}", file=sys.stderr)
        return 2
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as e:
        print(f"失败：{type(e).__name__}: {str(e)[:300]}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
