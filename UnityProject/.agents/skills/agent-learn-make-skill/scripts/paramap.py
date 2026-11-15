#!/usr/bin/env python3
"""paramap：参数含义映射。任何“改一个值 → 结果变了没有、怎么变”的问题都用它，不限水、颜色或引擎。

适用：shader 参数、组件字段、配置表的列、命令行选项、开关、枚举……值的种类只分四种语义：
  float（连续）  int（整数/档位）  bool（开关）  enum（选项）
不需要知道它在程序里的真实类型；你只要能“设一个值、看一个结果”。

为什么有这个工具：看参数名猜含义最容易错。常见的坑——
  · 改了没反应：没接线、被别处覆盖、或者在有效范围外（保存的值 ≠ 实际生效的值）；
  · 方向和以为的相反、到某个值就饱和、中间有一个阈值突跳；
  · 枚举里有几个选项其实效果一样；开关打开后几乎没区别；
  · 用一个点的观察就外推出“填多少能达到目标”。
本工具把“设了什么值、实际读回什么、结果量到多少”记下来，再机械地分析映射关系。

子命令（状态存在 <--dir>/PARAMS.json；--json 输出 JSON，放在子命令前后都行）：
  def NAME --kind float|int|bool|enum [--options a,b,c] [--range lo,hi] [--expect up|down|any]
           --means "以为它控制什么" [--where "在哪被读取，如 Water.shader:42 / Cfg.xlsx 列 G"]
                 先写下你以为它是什么意思（可推翻的预测），再去试
  obs  NAME VALUE --metric 名=数 [--metric …] [--read 读回值] [--img 截图 [--roi x0,y0,x1,y1]] [--note …]
                 记一次观察：设了 VALUE，结果量到这些数；--read 是保存/运行后实际读回的值；
                 --img 会自动量截图的 亮度/饱和度/边缘锐度，并和本参数第一张截图比变化量
  fit  NAME [--metric 名] [--noise 数]
                 分析映射：有没有作用、方向、线性还是阈值/饱和、哪些选项没区别、保存值和生效值是否一致、
                 和 def 里写的预期是否矛盾
  pick NAME --want 名=数
                 在已观察的范围里反推“填多少能得到这个结果”（只内插，不外推）
  table          所有参数的含义表（Markdown），可直接写进 Skill 的“做法和参数”

调用：python -X utf8 "<本 Skill 目录>\\scripts\\paramap.py" [--dir 工作区] <子命令> …
退出码：0 正常；2 出错；4 fit 发现问题（没作用、与预期矛盾、保存值≠生效值）或 pick 超出观察范围。
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

KINDS = ("float", "int", "bool", "enum")
TRUE_WORDS = {"1", "true", "on", "yes", "开", "是", "真"}
FALSE_WORDS = {"0", "false", "off", "no", "关", "否", "假"}


class Fail(Exception):
    pass


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


class Store:
    def __init__(self, root: Path):
        self.path = root / "PARAMS.json"
        self.data = json.loads(self.path.read_text(encoding="utf-8")) if self.path.is_file() else {"params": {}}

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(self.path)

    def param(self, name: str) -> dict:
        p = self.data["params"].get(name)
        if p is None:
            raise Fail(f"没有参数 {name}：先用 def 写下它以为的含义")
        return p


def coerce(kind: str, raw: str, options: list[str] | None = None):
    """把命令行上的值按语义类型解析。enum 必须是声明过的选项之一（防止拼错的选项被当成新选项）。"""
    s = str(raw).strip()
    if kind == "bool":
        low = s.lower()
        if low in TRUE_WORDS:
            return True
        if low in FALSE_WORDS:
            return False
        raise Fail(f"开关值只认 true/false/1/0/on/off/开/关：{raw}")
    if kind == "enum":
        if options and s not in options:
            raise Fail(f"{raw} 不在声明的选项 {options} 里；新选项先用 def --options 补上")
        return s
    try:
        v = float(s)
    except ValueError:
        raise Fail(f"{kind} 值要是数字：{raw}") from None
    if not math.isfinite(v):
        raise Fail(f"值不能是无穷或 NaN：{raw}")
    if kind == "int":
        if v != int(v):
            raise Fail(f"int 参数的值要是整数：{raw}")
        return int(v)
    return v


def parse_metrics(items: list[str] | None) -> dict:
    out = {}
    for tok in items or []:
        name, sep, val = tok.partition("=")
        if not sep or not name.strip():
            raise Fail(f"--metric 写成 名=数：{tok}")
        try:
            v = float(val)
        except ValueError:
            raise Fail(f"--metric {name} 的值要是数字：{val}（定性结论写 --note）") from None
        if not math.isfinite(v):
            raise Fail(f"--metric {name} 不能是无穷或 NaN")
        out[name.strip()] = v
    return out


def image_metrics(path: Path, roi: str | None, first: str | None) -> dict:
    import refgrab
    from PIL import Image
    im = Image.open(path).convert("RGB")
    if roi:
        im = im.crop(refgrab._box(roi, im.width, im.height))
    st = refgrab.look_stats(im)
    gray = im.convert("L")
    gray.thumbnail((256, 256))
    lum = list(gray.tobytes())
    out = {"img.luma": round(sum(lum) / len(lum), 2), "img.saturation": st["saturationMean"],
           "img.edge": st["edgeSharpness"]}
    if not first or Path(first).resolve() == path.resolve():
        out["img.changeFromFirst"] = 0.0
    elif Path(first).is_file():
        import wavelog
        out["img.changeFromFirst"] = wavelog.change_metrics(Path(first), path, roi)["mean"]
    return out


# --------------------------------------------------------------------------- 分析

def series(param: dict, metric: str) -> list[tuple]:
    """(生效值, 结果) 列表；有 --read 时用读回值，不用设定值。"""
    pts = []
    for o in param["obs"]:
        if metric in o["metrics"]:
            x = o["read"] if o.get("read") is not None else o["value"]
            pts.append((x, o["metrics"][metric]))
    return pts


def estimate_noise(pts: list[tuple], given: float | None) -> float:
    if given is not None:
        return given
    groups: dict = {}
    for x, y in pts:
        groups.setdefault(x, []).append(y)
    spreads = [statistics.pstdev(v) for v in groups.values() if len(v) >= 2]
    ys = [y for _, y in pts]
    span = (max(ys) - min(ys)) if ys else 0
    base = max(spreads) * 2 if spreads else 0.0
    # 相对下限：结果本身是 5、只变了 0.0001，不算有作用（量不准的尾数）；真有这么细的作用用 --noise 指定
    level = sum(abs(y) for y in ys) / len(ys) if ys else 0
    return max(base, span * 0.02, level * 0.001, 1e-9)


def mean_by_x(pts: list[tuple]) -> list[tuple]:
    groups: dict = {}
    for x, y in pts:
        groups.setdefault(x, []).append(y)
    return sorted((x, sum(v) / len(v)) for x, v in groups.items())


def fit_numeric(pts: list[tuple], noise: float, expect: str) -> dict:
    m = mean_by_x(pts)
    res = {"points": [[x, round(y, 4)] for x, y in m], "noise": round(noise, 4)}
    if len(m) < 2:
        res["shape"] = "只有一个取值，还看不出映射"
        res["problems"] = ["至少要 2 个不同取值；看形状（阈值、饱和）至少 4–5 个，跨过你关心的范围"]
        return res
    xs, ys = [p[0] for p in m], [p[1] for p in m]
    span = max(ys) - min(ys)
    problems, notes = [], []
    if span <= noise:
        res["shape"] = "没有作用"
        problems.append(f"在 {xs[0]}–{xs[-1]} 范围内结果几乎不变（变化 {span:.4g} ≤ 噪声 {noise:.4g}）："
                        "查是不是没接线、被别处覆盖、值被钳在有效范围外，或这个结果量不出它的作用")
        res["problems"] = problems
        return res
    steps = [b - a for a, b in zip(ys, ys[1:])]
    sig = [0 if abs(d) <= noise else (1 if d > 0 else -1) for d in steps]
    ups, downs = sig.count(1), sig.count(-1)
    if downs == 0:
        direction = "up"
    elif ups == 0:
        direction = "down"
    else:
        direction = "mixed"
    res["direction"] = {"up": "值越大结果越大", "down": "值越大结果越小", "mixed": "先升后降或来回变"}[direction]
    if direction == "mixed":
        k = max(range(len(ys)), key=lambda i: ys[i]) if ys[0] < max(ys) else min(range(len(ys)), key=lambda i: ys[i])
        notes.append(f"不单调：极值在 {xs[k]} 附近，两侧方向相反")
    if expect in ("up", "down") and direction != "mixed" and direction != expect:
        problems.append(f"方向和预期相反：预期“{'值越大结果越大' if expect == 'up' else '值越大结果越小'}”，"
                        f"实际“{res['direction']}”。先确认含义理解，再决定往哪边调")
    # 线性度
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx if sxx else 0
    ss_tot = sum((y - my) ** 2 for y in ys)
    ss_res = sum((y - (my + slope * (x - mx))) ** 2 for x, y in zip(xs, ys))
    r2 = 1 - ss_res / ss_tot if ss_tot else 0
    res["slope"] = round(slope, 6)
    res["r2"] = round(r2, 4)
    # 平台（前段没反应 / 后段饱和）与阈值突跳
    flat_head = 0
    while flat_head < len(sig) and sig[flat_head] == 0:
        flat_head += 1
    flat_tail = 0
    while flat_tail < len(sig) and sig[len(sig) - 1 - flat_tail] == 0:
        flat_tail += 1
    biggest = max(range(len(steps)), key=lambda i: abs(steps[i]))
    share = abs(steps[biggest]) / span if span else 0
    if n >= 4 and share >= 0.6:
        res["shape"] = f"阈值：在 {xs[biggest]}–{xs[biggest + 1]} 之间突变（占总变化 {share:.0%}）"
        notes.append("阈值附近再补 2–3 个点，定准突变位置；两侧大范围调都没用")
    elif r2 >= 0.97:
        res["shape"] = f"近似线性：每 +1 结果约 {slope:+.4g}"
    else:
        res["shape"] = "单调但非线性" if direction != "mixed" else "非单调"
    if 0 < flat_head < len(sig) and n >= 3:
        notes.append(f"{xs[0]}–{xs[flat_head]} 之间没反应：有效作用从 {xs[flat_head]} 附近才开始")
    if 0 < flat_tail < len(sig) and n >= 3:
        notes.append(f"{xs[-1 - flat_tail]} 以上不再变化：已饱和，再往上加没用")
    res["problems"], res["notes"] = problems, notes
    return res


def fit_bool(pts: list[tuple], noise: float) -> dict:
    on = [y for x, y in pts if x is True]
    off = [y for x, y in pts if x is False]
    if not on or not off:
        return {"shape": "只观察了一边", "problems": ["开和关都要至少观察一次"]}
    a, b = sum(off) / len(off), sum(on) / len(on)
    eff = b - a
    res = {"off": round(a, 4), "on": round(b, 4), "effect": round(eff, 4), "noise": round(noise, 4)}
    if abs(eff) <= noise:
        res["shape"] = "开关没有作用"
        res["problems"] = [f"开/关结果只差 {eff:.4g}（噪声 {noise:.4g}）：查是否没接线、被覆盖，或要配合别的参数才生效"]
    else:
        res["shape"] = f"打开后结果 {'增加' if eff > 0 else '减少'} {abs(eff):.4g}"
        res["problems"] = []
    return res


def fit_enum(pts: list[tuple], noise: float, options: list[str]) -> dict:
    groups: dict = {}
    for x, y in pts:
        groups.setdefault(x, []).append(y)
    means = {k: sum(v) / len(v) for k, v in groups.items()}
    res = {"byOption": {k: round(v, 4) for k, v in means.items()}, "noise": round(noise, 4), "problems": [], "notes": []}
    unseen = [o for o in options if o not in means]
    if unseen:
        res["notes"].append(f"还没观察的选项：{'、'.join(unseen)}")
    order = sorted(means, key=means.get)
    same, cur = [], [order[0]] if order else []
    for a, b in zip(order, order[1:]):
        if means[b] - means[a] <= noise:
            cur.append(b)
        else:
            if len(cur) > 1:
                same.append(cur)
            cur = [b]
    if len(cur) > 1:
        same.append(cur)
    if len(means) >= 2 and len(same) == 1 and len(same[0]) == len(means):
        res["shape"] = "所有选项效果一样"
        res["problems"].append("各选项结果都在噪声内：查是否没接线或被覆盖，或这个结果量不出它的作用")
    else:
        res["shape"] = "从小到大：" + " < ".join(order)
        for g in same:
            res["notes"].append(f"这几个选项结果分不开：{'、'.join(g)}（可能是同一实现或回退到默认）")
    return res


def readback_issues(param: dict) -> list[str]:
    out = []
    for o in param["obs"]:
        if o.get("read") is not None and o["read"] != o["value"]:
            out.append(f"设 {o['value']} 读回 {o['read']}")
    if not out:
        return []
    return [f"保存值 ≠ 生效值（{len(out)} 次）：{'；'.join(out[:4])}——被钳制、取整、被覆盖或没保存成功；"
            "分析已按读回值算，但先查清是谁改了它"]


def range_issues(param: dict) -> list[str]:
    rng = param.get("range")
    if not rng or param["kind"] not in ("float", "int"):
        return []
    xs = [o["value"] for o in param["obs"]]
    if not xs:
        return []
    lo, hi = rng
    out = []
    covered = (max(xs) - min(xs)) / (hi - lo) if hi > lo else 1
    if covered < 0.3:
        out.append(f"只试了有效范围 {lo}–{hi} 的 {covered:.0%}：范围外的结论不能推")
    outside = [x for x in xs if x < lo or x > hi]
    if outside:
        out.append(f"试了范围外的值 {outside[:4]}：看读回值确认有没有被钳制")
    return out


def fit_param(param: dict, metric: str | None, noise: float | None) -> dict:
    metrics = sorted({k for o in param["obs"] for k in o["metrics"]})
    if not metrics:
        raise Fail("还没有带 --metric 或 --img 的观察")
    chosen = [metric] if metric else metrics
    for m in chosen:
        if m not in metrics:
            raise Fail(f"没有结果量 {m}；已有：{'、'.join(metrics)}")
    out = {"name": param["name"], "kind": param["kind"], "means": param["means"], "metrics": {}}
    for m in chosen:
        pts = series(param, m)
        nz = estimate_noise(pts, noise)
        if param["kind"] == "bool":
            r = fit_bool(pts, nz)
        elif param["kind"] == "enum":
            r = fit_enum(pts, nz, param.get("options") or [])
        else:
            r = fit_numeric(pts, nz, param.get("expect", "any"))
        out["metrics"][m] = r
    out["problems"] = [f"{m}：{p}" for m, r in out["metrics"].items() for p in r.get("problems", [])] + readback_issues(param)
    out["notes"] = [f"{m}：{p}" for m, r in out["metrics"].items() for p in r.get("notes", [])] + range_issues(param)
    if len(chosen) > 1 and all(r.get("shape", "").startswith(("没有作用", "开关没有作用", "所有选项效果一样")) for r in out["metrics"].values()):
        out["problems"].append("所有结果量都看不出作用：先确认参数真的被读到了（改成极端值看一次）")
    return out


# --------------------------------------------------------------------------- 子命令

def cmd_def(args, st: Store):
    kind = args.kind
    options = [o.strip() for o in (args.options or "").split(",") if o.strip()]
    if kind == "enum" and len(options) < 2:
        raise Fail("enum 要用 --options 列出至少 2 个选项")
    rng = None
    if args.range:
        if kind not in ("float", "int"):
            raise Fail("--range 只用于 float/int")
        lo, _, hi = args.range.partition(",")
        rng = [float(lo), float(hi)]
        if rng[0] >= rng[1]:
            raise Fail("--range 要写成 lo,hi 且 lo < hi")
    old = st.data["params"].get(args.name)
    if old and old["kind"] != kind and old["obs"]:
        raise Fail(f"{args.name} 已按 {old['kind']} 记了 {len(old['obs'])} 次观察，不能改成 {kind}；换个名字")
    p = old or {"name": args.name, "obs": []}
    p.update(kind=kind, means=args.means, where=args.where or p.get("where", ""), options=options or p.get("options"),
             range=rng or p.get("range"), expect=args.expect, defined=now())
    st.data["params"][args.name] = p
    st.save()
    if args.json:
        print(json.dumps(p, ensure_ascii=False, indent=1))
    else:
        print(f"已定义 {args.name}（{kind}）：以为它“{args.means}”" + (f"；在 {p['where']}" if p["where"] else ""))
        print("下一步：每设一个值就 obs 一次（同一个值重复测一两次，工具才能估出噪声）。")
    return 0


def cmd_obs(args, st: Store):
    p = st.param(args.name)
    value = coerce(p["kind"], args.value, p.get("options"))
    read = coerce(p["kind"], args.read, p.get("options")) if args.read is not None else None
    metrics = parse_metrics(args.metric)
    if args.img:
        img = Path(args.img)
        if not img.is_file():
            raise Fail(f"找不到截图：{img}")
        p.setdefault("firstImg", str(img.resolve()))
        metrics.update(image_metrics(img, args.roi or p.get("roi"), p["firstImg"]))
        if args.roi:
            p["roi"] = args.roi
    if not metrics and not args.note:
        raise Fail("至少给一个 --metric 名=数、--img 截图或 --note 说明看到了什么")
    o = {"value": value, "read": read, "metrics": metrics, "note": args.note or "", "img": args.img, "time": now()}
    p["obs"].append(o)
    st.save()
    if args.json:
        print(json.dumps(o, ensure_ascii=False, indent=1))
    else:
        shown = "，".join(f"{k}={v}" for k, v in metrics.items())
        print(f"{args.name}={value}" + (f"（读回 {read}）" if read is not None else "") + f"：{shown or args.note}")
        if read is not None and read != value:
            print("注意：读回值和设定值不同——被钳制、取整或覆盖；分析会按读回值算。")
    return 0


def cmd_fit(args, st: Store):
    p = st.param(args.name)
    r = fit_param(p, args.metric, args.noise)
    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    else:
        print(f"{p['name']}（{p['kind']}）以为：{p['means']}")
        for m, res in r["metrics"].items():
            line = f"  [{m}] {res.get('shape', '')}"
            if "direction" in res:
                line += f"；{res['direction']}"
            if "r2" in res:
                line += f"；线性拟合 R²={res['r2']}"
            print(line)
        for x in r["problems"]:
            print("问题：" + x)
        for x in r["notes"]:
            print("注意：" + x)
        if not r["problems"]:
            print("映射清楚。把“含义 / 方向 / 有效范围 / 饱和或阈值”写进 Skill 的参数说明（table 子命令可直接出表）。")
    return 4 if r["problems"] else 0


def cmd_pick(args, st: Store):
    p = st.param(args.name)
    if p["kind"] not in ("float", "int"):
        raise Fail("pick 只用于 float/int；bool/enum 直接看 fit 里每个选项的结果")
    name, sep, val = args.want.partition("=")
    if not sep:
        raise Fail("--want 写成 结果名=目标值")
    target = float(val)
    m = mean_by_x(series(p, name.strip()))
    if len(m) < 2:
        raise Fail(f"{name} 至少要 2 个不同取值的观察")
    hits = []
    for (x0, y0), (x1, y1) in zip(m, m[1:]):
        if min(y0, y1) <= target <= max(y0, y1) and y0 != y1:
            x = x0 + (target - y0) * (x1 - x0) / (y1 - y0)
            hits.append(round(x) if p["kind"] == "int" else round(x, 4))
    ys = [y for _, y in m]
    out = {"want": target, "candidates": hits, "observed": [min(ys), max(ys)]}
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    elif hits:
        print(f"要让 {name}={target}：在已观察的点之间内插，{p['name']} ≈ {'，或 '.join(map(str, hits))}")
        if len(hits) > 1:
            print("注意：有多个解，说明映射不单调；按你要的另一侧效果选。")
        print("这是内插估计：填进去再 obs 一次核实。")
    else:
        print(f"{target} 不在已观察的结果范围 {min(ys):.4g}–{max(ys):.4g} 内：不外推。往那一侧再试几个值，或者这个参数本来就到不了")
    return 0 if hits else 4


def cmd_table(args, st: Store):
    rows = ["| 参数 | 类型 | 以为的含义 | 在哪读取 | 实测映射 | 问题 |", "|---|---|---|---|---|---|"]
    for name, p in st.data["params"].items():
        try:
            r = fit_param(p, None, None)
            shape = "；".join(f"{m}: {res.get('shape', '')}" + (f"，{res['direction']}" if "direction" in res else "")
                             for m, res in r["metrics"].items())
            probs = "；".join(r["problems"]) or "—"
        except Fail as e:
            shape, probs = "—", str(e)
        cells = [name, p["kind"], p["means"], p.get("where") or "—", shape, probs]
        rows.append("| " + " | ".join(str(c).replace("|", "\\|").replace("\n", " ") for c in cells) + " |")
    text = "\n".join(rows)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--dir", default=".", help="工作区（PARAMS.json 放这里），默认当前目录")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name, text, epilog=None):
        return sub.add_parser(name, parents=[common], help=text, description=text, epilog=epilog,
                              formatter_class=argparse.RawDescriptionHelpFormatter)

    p = add("def", "定义参数并写下你以为的含义（可推翻的预测）",
            '例：def _FoamWidth --kind float --range 0,1 --expect up --means "岸边泡沫带宽度" --where "Water.shader:88"\n'
            '    def UseFlowMap --kind bool --means "打开后水面沿流向图流动"\n'
            '    def Quality --kind enum --options Low,Medium,High --means "反射质量档位"')
    p.add_argument("name"); p.add_argument("--kind", required=True, choices=KINDS)
    p.add_argument("--means", required=True, help="一句话：你以为它控制什么")
    p.add_argument("--where", help="在哪被读取（文件:行、配置表列…）"); p.add_argument("--options", help="enum 的选项，逗号分隔")
    p.add_argument("--range", help="float/int 的有效范围 lo,hi（文档或滑条上写的）")
    p.add_argument("--expect", default="any", choices=["up", "down", "any"], help="预期方向：值变大结果变大(up)/变小(down)")

    p = add("obs", "记一次观察：设了什么值、实际读回什么、结果量到多少",
            '例：obs _FoamWidth 0.2 --metric 泡沫占画面高=0.8 --read 0.2\n'
            '    obs _FoamWidth 0.4 --img shots/foam_04.png --roi 0,0.6,1,1\n'
            '    obs UseFlowMap on --metric 帧间变化=3.1')
    p.add_argument("name"); p.add_argument("value")
    p.add_argument("--metric", action="append", help="结果量 名=数，可写多个")
    p.add_argument("--read", help="保存/运行后实际读回的值（检验保存值 = 生效值）")
    p.add_argument("--img", help="结果截图：自动量 亮度/饱和度/边缘锐度 和相对第一张的变化")
    p.add_argument("--roi", help="截图只量这个框 x0,y0,x1,y1（≤1 为比例）"); p.add_argument("--note")

    p = add("fit", "分析映射：有没有作用、方向、线性/阈值/饱和、选项是否可分、保存值是否生效")
    p.add_argument("name"); p.add_argument("--metric", help="只看这一个结果量"); p.add_argument("--noise", type=float, help="手动指定噪声幅度")

    p = add("pick", "在已观察范围内反推填多少能得到目标结果（只内插）", "例：pick _FoamWidth --want 泡沫占画面高=1.5")
    p.add_argument("name"); p.add_argument("--want", required=True)

    p = add("table", "所有参数的含义表（Markdown）"); p.add_argument("--out", help="同时写到文件")

    args = ap.parse_args(argv)
    st = Store(Path(args.dir))
    func = {"def": cmd_def, "obs": cmd_obs, "fit": cmd_fit, "pick": cmd_pick, "table": cmd_table}[args.cmd]
    try:
        return func(args, st) or 0
    except Fail as e:
        print(f"失败：{e}", file=sys.stderr)
        return 2
    except (OSError, ValueError, json.JSONDecodeError) as e:
        print(f"失败：{type(e).__name__}: {str(e)[:300]}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
