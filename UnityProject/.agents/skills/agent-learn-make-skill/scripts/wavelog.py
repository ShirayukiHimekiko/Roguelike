#!/usr/bin/env python3
"""wavelog：波次记录。把“本波推进哪条特征 / 主机位有没有可见变化 / 目标有没有悄悄变”变成可执行的检查。

为什么有这个工具：作者最常见的跑偏是连续几波都在修小 bug，主机位画面没变，自己却觉得在推进；
或者参照、特征在讨论中被悄悄删弱，没人发现。本工具只做机械检查，不判断好不好看——那是作者亲眼看和陪审的事。

子命令（状态存在 <目录>/WAVES.json；加 --json 输出 JSON，放在子命令前后都行）：
  baseline --target TARGET.md [--approve "用户原话"]
                       记下 TARGET 里的特征（T1…）和参照（R1…）作为基线；目标变更经用户批准后带 --approve 重记
  drift                对照基线查：参照少了/换了、特征删了/改写了、新增了特征（可能扩范围）
  start N --push T1,T3 [--why "…"]
                       开第 N 波：写明本波推进哪几条特征，同时自动跑 drift
  end N --main 主机位.png [--ref R1.png] [--roi x0,y0,x1,y1] [--status T1=接近,T3=达到] [--fixed "…"]
                       收第 N 波：和上一波主机位比可见变化，出 [参照|本波|上一波] 对比图，判断算不算“前进了一版”；
                       连续两波主机位没有可见变化 → 提示停掉当前技术线
  try "要验证的判断" --predict "改了会看到什么" [--wave N]
                       做实验前先写可推翻的预测（防止改完再编解释）
  result ID --outcome confirmed|refuted|unclear --saw "实际看到什么"
                       记实验结果；同一波里连续 3 次 unclear → 提示这条路没有信息量，换问法或换路线
  status               各波一览：推进了什么、主机位变化、特征状态、未结实验
  intent [--named 原神,鸣潮]
                       查 INTENT.md 六项写没写全；每个点名对象有没有选入的实机参照（refgrab pick 登记）

特征状态只用三级：未达 < 接近 < 达到。

调用方式：python -X utf8 "<本 Skill 目录>\\scripts\\wavelog.py" [--dir 工作区] <子命令> …
退出码：0 正常；2 出错；4 需要处理（有漂移、不算前进、该停线、该换路线），看输出里的“下一步”。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path

LEVELS = ["未达", "接近", "达到"]
STATE_NAME = "WAVES.json"
ID_LINE = re.compile(r"^\s*(?:[-*+]\s*|\|\s*|\d+[.)]\s*)?\*{0,2}`?([A-Z]{1,2}\d{1,3})`?\*{0,2}(?![\w.])\s*[:：|]?\s*(.*)$")
REF_RANGE = r"(?<![A-Za-z0-9]){p}(\d{{1,3}})\s*[-–—~～至到]\s*(?:{p})?(\d{{1,3}})(?!\d)"


def ref_ids(text: str, prefix: str) -> set[str]:
    """R3、R1–R9、R1-R3、R4~6 都识别；范围展开成每个编号。"""
    p = re.escape(prefix)
    found = set(re.findall(rf"(?<![A-Za-z0-9]){p}\d{{1,3}}(?!\d)", text))
    for a, b in re.findall(REF_RANGE.format(p=p), text):
        a, b = int(a), int(b)
        if a < b <= a + 60:
            found.update(f"{prefix}{i}" for i in range(a, b + 1))
    return found


class Fail(Exception):
    pass


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[`*|]", " ", text)).strip()


def parse_target(path: Path, ref_prefix: str = "R") -> dict:
    """从 TARGET.md 取特征和参照。特征：行首（列表项、表格首列、编号项）是 T1/F01 这类 ID 的行；
    以参照前缀（默认 R）开头的 ID 算参照。全文出现过的 R 编号都算参照集合。"""
    if not path.is_file():
        raise Fail(f"找不到 {path}；先写 TARGET.md（特征用 T1、T2… 编号，参照用 R1、R2…）")
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    features: dict[str, str] = {}
    refs = ref_ids(text, ref_prefix)
    in_code = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        m = ID_LINE.match(line)
        if not m:
            continue
        fid, rest = m.group(1), norm(m.group(2))
        if fid.startswith(ref_prefix):
            refs.add(fid)
            continue
        if fid not in features:
            features[fid] = rest
    if not features:
        raise Fail(f"{path} 里没找到编号特征。每条特征单起一行，以 T1、T2…（或 F01…）开头，例：\"- T1 近岸到远处至少 3 个色阶\"")
    return {"features": features, "refs": sorted(refs, key=lambda r: int(re.sub(r"\D", "", r) or 0)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


class Ledger:
    def __init__(self, root: Path):
        self.root = root
        self.path = root / STATE_NAME
        self.data = json.loads(self.path.read_text(encoding="utf-8")) if self.path.is_file() else {
            "baseline": None, "approvals": [], "waves": {}, "tries": [], "featureStatus": {}}

    def save(self):
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(self.path)

    def need_baseline(self) -> dict:
        if not self.data["baseline"]:
            raise Fail("还没有基线：先运行 baseline --target TARGET.md")
        return self.data["baseline"]

    def wave(self, n: int) -> dict:
        return self.data["waves"].setdefault(str(n), {"n": n})

    def ordered_waves(self) -> list[dict]:
        return [self.data["waves"][k] for k in sorted(self.data["waves"], key=int)]


# --------------------------------------------------------------------------- 漂移

def drift_report(ledger: Ledger, target: Path, ref_prefix: str) -> dict:
    base = ledger.need_baseline()
    cur = parse_target(target, ref_prefix)
    removed_refs = [r for r in base["refs"] if r not in cur["refs"]]
    added_refs = [r for r in cur["refs"] if r not in base["refs"]]
    removed = [f for f in base["features"] if f not in cur["features"]]
    added = [f for f in cur["features"] if f not in base["features"]]
    rewritten = [f for f in base["features"] if f in cur["features"] and cur["features"][f] != base["features"][f]]
    issues = []
    if removed_refs:
        issues.append(f"参照少了：{'、'.join(removed_refs)}（用户给的参照只能加不能换、不能删）")
    if removed:
        issues.append(f"特征删了：{'、'.join(removed)}")
    for f in rewritten:
        issues.append(f"特征改写了：{f}\n      原：{base['features'][f][:120]}\n      现：{cur['features'][f][:120]}\n"
                      "      看清是补充细节，还是把要求放宽了（放宽 = 弱化 = 目标变更）")
    notes = []
    if added:
        notes.append(f"新增特征：{'、'.join(added)}——确认是同一主体的细化，不是扩大范围（新场景、第二条溪流…算扩范围）")
    if added_refs:
        notes.append(f"新增参照：{'、'.join(added_refs)}——只能是同类补充，不能替代原参照")
    return {"drift": bool(issues), "issues": issues, "notes": notes, "removedRefs": removed_refs, "removedFeatures": removed,
            "rewrittenFeatures": rewritten, "addedFeatures": added, "addedRefs": added_refs, "current": cur}


def print_drift(rep: dict) -> None:
    if rep["drift"]:
        print("【目标变更嫌疑】")
        for i in rep["issues"]:
            print("  - " + i)
        print("下一步：写进下一条给用户的消息，说清改了什么、为什么；用户确认前按原目标做。"
              "用户确认后运行 baseline --approve \"用户原话\" 重记基线。作者、统筹、陪审都不能批准目标变更。")
    else:
        print("漂移检查：参照和特征与基线一致。")
    for n in rep["notes"]:
        print("  注意：" + n)
    print("还要自己看一眼：主体还是 INTENT 核心名词说的那种风格吗？拿别的风格的现成工程当主体 = 换题。")


# --------------------------------------------------------------------------- 主机位变化

def change_metrics(a_path: Path, b_path: Path, roi: str | None) -> dict:
    """两张主机位截图的可见差异（0–255）。b 先缩放到 a 的尺寸。
    都在缩到 32 宽的图上算：水面波纹、TAA 抖动这类逐帧细碎变化被平均掉，留下色块、明暗、高光位置这类看得见的变化。
    mean：整体平均差；cellMax：4x4 格里差异最大的一格（抓局部改动，如一处高光）；squint：缩到 16 宽的平均差（只剩大关系）。"""
    from PIL import Image, ImageChops, ImageStat
    a = Image.open(a_path).convert("RGB")
    b = Image.open(b_path).convert("RGB").resize(a.size, Image.LANCZOS)
    if roi:
        v = [float(t) for t in roi.split(",")]
        if len(v) != 4:
            raise Fail(f"--roi 要 4 个数 x0,y0,x1,y1：{roi}")
        w, h = a.size
        box = [round(x * (w if i % 2 == 0 else h)) if x <= 1 else int(x) for i, x in enumerate(v)]
        box = [min(box[0], box[2]), min(box[1], box[3]), max(box[0], box[2]), max(box[1], box[3])]
        if box[2] - box[0] < 4 or box[3] - box[1] < 4:
            raise Fail(f"--roi 太小：{roi}")
        a, b = a.crop(box), b.crop(box)

    def scaled(im, width):
        return im.resize((width, max(1, round(im.height * width / im.width))), Image.LANCZOS)

    def mean_diff(x, y):
        return sum(ImageStat.Stat(ImageChops.difference(x, y)).mean) / 3

    a2, b2 = scaled(a, 32), scaled(b, 32)
    cells = []
    gw, gh = a2.width // 4, a2.height // 4
    for gy in range(4):
        for gx in range(4):
            box = (gx * gw, gy * gh, (gx + 1) * gw, (gy + 1) * gh)
            cells.append(round(mean_diff(a2.crop(box), b2.crop(box)), 2))
    return {"mean": round(mean_diff(a2, b2), 2), "squint": round(mean_diff(scaled(a, 16), scaled(b, 16)), 2),
            "cellMax": max(cells), "cells": cells, "structure": structure_similarity(a, b)}


def structure_similarity(a, b) -> float:
    """两张图边缘结构（地平线、岛、岸线的位置）的相关度，−1–1。颜色、明暗改了它基本不变，机位动了它会掉。
    实测：同机位不同版本 0.92–0.96，主机位 vs 俯视 0.83，不同场景 0.75。"""
    from PIL import Image, ImageFilter

    def edges(im):
        g = im.convert("L").resize((96, max(2, round(im.height * 96 / im.width))), Image.LANCZOS)
        return list(g.filter(ImageFilter.GaussianBlur(1)).filter(ImageFilter.FIND_EDGES).tobytes())
    x, y = edges(a), edges(b)
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    cov = sum((p - mx) * (q - my) for p, q in zip(x, y))
    vx = sum((p - mx) ** 2 for p in x) ** 0.5
    vy = sum((q - my) ** 2 for q in y) ** 0.5
    if vx < 1e-6 or vy < 1e-6:
        return 1.0 if vx < 1e-6 and vy < 1e-6 else 0.0
    return round(cov / (vx * vy), 3)


def judge_change(m: dict, min_change: float, noise: dict | None = None) -> tuple[bool, str | None]:
    """noise：同一版本连拍两张的差（量出画面本身在动的幅度）；阈值取 min_change 和 2 倍噪声中较大者。"""
    mean_t = max(min_change, 2 * noise["mean"]) if noise else min_change
    cell_t = max(min_change * 2.5, 2 * noise["cellMax"]) if noise else min_change * 2.5
    m["thresholds"] = {"mean": round(mean_t, 2), "cellMax": round(cell_t, 2)}
    visible = m["mean"] >= mean_t or m["cellMax"] >= cell_t
    warn = None
    if m.get("structure", 1.0) < 0.88:
        warn = (f"画面结构相关度只有 {m['structure']}（同机位通常 >0.9）：机位、视角或场景可能变了，"
                "这个比较不成立；回到固定主机位重截")
    return visible, warn


# --------------------------------------------------------------------------- 子命令

def target_path(args, ledger: Ledger) -> Path:
    """--target 给了按当前目录解析；没给就用基线记下的路径，再没有就用 <工作区>/TARGET.md。"""
    if getattr(args, "target", None):
        return Path(args.target).resolve()
    base = ledger.data.get("baseline")
    return Path(base["target"]) if base else (ledger.root / "TARGET.md").resolve()


def cmd_baseline(args, ledger: Ledger):
    target = target_path(args, ledger)
    cur = parse_target(target, args.ref_prefix)
    old = ledger.data["baseline"]
    if old and not args.approve:
        rep = drift_report(ledger, target, args.ref_prefix)
        if rep["drift"]:
            print_drift(rep)
            raise Fail("已有基线且目标有变化：只有用户批准后才能重记，带上 --approve \"用户原话或消息时间\"")
    ledger.data["baseline"] = {"time": now(), "target": str(target), **cur}
    if args.approve:
        ledger.data["approvals"].append({"time": now(), "approval": args.approve, "previousSha256": (old or {}).get("sha256")})
    for f in cur["features"]:
        ledger.data["featureStatus"].setdefault(f, "未达")
    ledger.save()
    out = {"features": list(cur["features"]), "refs": cur["refs"], "state": str(ledger.path)}
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        print(f"基线：{len(cur['features'])} 条特征（{'、'.join(cur['features'])}），参照 {len(cur['refs'])} 个（{'、'.join(cur['refs']) or '无'}）")
        if not cur["refs"]:
            print("注意：TARGET 里没有 R 编号的参照。点名对象要有实机参照（refgrab pick 登记后引用 R 编号）。")
        print(f"状态文件：{ledger.path}")
    return 0


def cmd_drift(args, ledger: Ledger):
    ledger.need_baseline()
    rep = drift_report(ledger, target_path(args, ledger), args.ref_prefix)
    if args.json:
        rep = {k: v for k, v in rep.items() if k != "current"}
        print(json.dumps(rep, ensure_ascii=False, indent=1))
    else:
        print_drift(rep)
    return 4 if rep["drift"] else 0


def cmd_start(args, ledger: Ledger):
    ledger.need_baseline()
    rep = drift_report(ledger, target_path(args, ledger), args.ref_prefix)
    push = [p.strip() for p in args.push.split(",") if p.strip()]
    if not push:
        raise Fail("--push 至少写一条本波要推进的特征编号")
    unknown = [p for p in push if p not in rep["current"]["features"]]
    if unknown:
        raise Fail(f"--push 里 {'、'.join(unknown)} 不是 TARGET 里的特征。本波推进的必须是 TARGET 特征；"
                   "修 bug 不是推进项，修完在 end 用 --fixed 记")
    status = ledger.data["featureStatus"]
    done = [p for p in push if status.get(p) == "达到"]
    w = ledger.wave(args.n)
    w.update(push=push, why=args.why or "", startTime=now(), drift=rep["issues"])
    ledger.save()
    worst = [f for f in rep["current"]["features"] if status.get(f, "未达") == "未达"]
    if args.json:
        print(json.dumps({"wave": args.n, "push": push, "drift": rep["drift"], "issues": rep["issues"],
                          "alreadyMet": done, "unmet": worst}, ensure_ascii=False, indent=1))
    else:
        print(f"第 {args.n} 波推进：{'、'.join(f'{p}（{status.get(p, "未达")}）' for p in push)}")
        for p in push:
            print(f"  {p}：{rep['current']['features'][p][:100]}")
        if done:
            print(f"注意：{'、'.join(done)} 已记为达到，本波还推它要说明理由（陪审指出退化？）")
        if worst and not any(p in worst for p in push):
            print(f"注意：本波没推任何“未达”特征；未达的还有 {'、'.join(worst)}。确认这是差距最大的方向。")
        print_drift(rep)
    return 4 if rep["drift"] else 0


def last_main(ledger: Ledger, before: int) -> tuple[int, str] | None:
    for w in reversed(ledger.ordered_waves()):
        if w["n"] < before and w.get("main"):
            return w["n"], w["main"]
    return None


def parse_status(spec: str | None, known: dict) -> dict:
    out = {}
    for tok in (spec or "").replace("，", ",").split(","):
        if not tok.strip():
            continue
        fid, sep, level = tok.partition("=")
        fid, level = fid.strip(), level.strip()
        if not sep or level not in LEVELS:
            raise Fail(f"--status 写成 T1=接近，级别只能是 {'/'.join(LEVELS)}：{tok}")
        if fid not in known:
            raise Fail(f"--status 里 {fid} 不是基线特征")
        out[fid] = level
    return out


def region_gap(ref: dict, cur: dict) -> float:
    """同名分区离参照多远：中位色的 RGB 距离 + 纹理（明度离散）差的一半。只说“差多少”，不说“好不好看”。"""
    color = sum((a - b) ** 2 for a, b in zip(ref["rgb"], cur["rgb"])) ** 0.5
    return round(color + 0.5 * abs(ref["lumaStd"] - cur["lumaStd"]), 1)


def gap_hint(ref: dict, cur: dict) -> str:
    sat = cur["hsv"][1] - ref["hsv"][1]
    val = cur["hsv"][2] - ref["hsv"][2]
    tex = cur["lumaStd"] - ref["lumaStd"]
    parts = []
    if abs(sat) >= 8:
        parts.append("饱和度" + ("偏高" if sat > 0 else "偏低（发灰）") + f" {sat:+d}")
    if abs(val) >= 8:
        parts.append("明度" + ("偏亮" if val > 0 else "偏暗") + f" {val:+d}")
    if ref["hsv"][1] >= 8 and cur["hsv"][1] >= 8:
        dh = (cur["hsv"][0] - ref["hsv"][0] + 180) % 360 - 180
        if abs(dh) >= 12:
            parts.append(f"色相偏 {dh:+d}°")
    if abs(tex) >= 4:
        parts.append("纹理" + ("偏多/偏碎" if tex > 0 else "偏少/偏平") + f" {tex:+.1f}")
    return "、".join(parts) or "颜色和纹理接近"


def region_gaps(ref: Path, main: Path, prev: Path | None, spec: str, out: Path, n: int, prev_n: int | None):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import refgrab  # noqa: E402
    imgs = [ref, main] + ([prev] if prev else [])
    labels = ["参照", f"第{n}波"] + ([f"第{prev_n}波"] if prev else [])
    parts = [s.strip() for s in spec.split("|")]
    if len(parts) == 2 and len(imgs) == 3:
        parts.append(parts[1])          # 本波和上一波同机位，共用主机位的框
    specs = refgrab.split_per_image("|".join(parts), len(imgs), "--regions")
    path, rows = refgrab.crops_board(imgs, labels, specs, out)
    result = []
    for row in rows:
        r, c = row["images"][0], row["images"][1]
        gap = region_gap(r, c)
        prev_gap = region_gap(r, row["images"][2]) if prev else None
        if prev_gap is None:
            trend = "—"
        elif gap <= prev_gap - 3:
            trend = "更近"
        elif gap >= prev_gap + 3:
            trend = "更远"
        else:
            trend = "没变"
        result.append({"region": row["region"], "gap": gap, "prevGap": prev_gap, "trend": trend, "hint": gap_hint(r, c)})
    return result, path


def cmd_end(args, ledger: Ledger):
    base = ledger.need_baseline()
    main = Path(args.main)
    if not main.is_file():
        raise Fail(f"找不到主机位截图：{main}")
    w = ledger.wave(args.n)
    if not w.get("push"):
        print(f"注意：第 {args.n} 波没有用 start 写明推进哪条特征。", file=sys.stderr)
    known = base["features"]
    new_status = parse_status(args.status, known)
    old_status = dict(ledger.data["featureStatus"])
    improved = [f for f, lv in new_status.items() if LEVELS.index(lv) > LEVELS.index(old_status.get(f, "未达"))]
    regressed = [f for f, lv in new_status.items() if LEVELS.index(lv) < LEVELS.index(old_status.get(f, "未达"))]
    prev = last_main(ledger, args.n)
    metrics, visible, warn = None, None, None
    noise = None
    if args.again:
        noise = change_metrics(main, Path(args.again), args.roi)
        noise.pop("cells", None)
        w["noise"] = noise
    noise = noise or (ledger.data["waves"].get(str(prev[0])) or {}).get("noise") if prev else noise
    if prev:
        metrics = change_metrics(Path(prev[1]), main, args.roi)
        visible, warn = judge_change(metrics, args.min_change, noise)
    board = None
    if args.board is not False:
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            import refgrab  # noqa: E402
            imgs, labels = [], []
            if args.ref:
                imgs.append(Path(args.ref)); labels.append("参照")
            imgs.append(main); labels.append(f"第{args.n}波")
            if prev:
                imgs.append(Path(prev[1])); labels.append(f"第{prev[0]}波")
            if len(imgs) >= 2:
                board = refgrab.compare(imgs, labels, Path(args.board or (ledger.root / "waves" / f"wave{args.n}_compare.png")), 540)
        except Exception as e:  # noqa: BLE001 - 对比图失败不影响记账
            print(f"对比图没生成：{e}", file=sys.stderr)
    regions = None
    if args.regions:
        if not args.ref:
            raise Fail("--regions 要和 --ref 一起用：分区比的是“本波离参照近了没有”")
        regions, crops_path = region_gaps(Path(args.ref), main, Path(prev[1]) if prev else None, args.regions,
                                          ledger.root / "waves" / f"wave{args.n}_crops.png", args.n, prev[0] if prev else None)
        w["regions"] = regions
        w["cropsBoard"] = str(crops_path)
    # 连续无变化计数（从上一波往前数）
    streak = 0
    if visible is False:
        streak = 1
        for pw in reversed([x for x in ledger.ordered_waves() if x["n"] < args.n]):
            if pw.get("visible") is False:
                streak += 1
            else:
                break
    forward = None if visible is None else bool(visible and (improved or args.fixed))
    w.update(main=str(main.resolve()), endTime=now(), change=metrics, visible=visible, improved=improved,
             regressed=regressed, fixed=args.fixed or "", forward=forward, board=str(board) if board else None)
    ledger.data["featureStatus"].update(new_status)
    ledger.save()
    pushed = w.get("push") or []
    unmoved = [p for p in pushed if p not in improved]
    status = ledger.data["featureStatus"]
    gaps = [f for f in known if status.get(f, "未达") == "未达"] or [f for f in known if status.get(f) == "接近"]
    nexts = []
    if streak >= 2:
        nexts.append(f"连续 {streak} 波主机位没有可见变化：停掉当前技术线，回到差距最大的特征"
                     f"（{'、'.join(gaps[:3]) or '无'}）；当前做法推不动就换做法，不在原路线上继续打磨")
    elif visible is False:
        nexts.append("本波主机位没有可见变化，不算前进了一版。修的若是诊断视角/边界机位的问题，放进待办")
    elif visible and not (improved or args.fixed):
        nexts.append("主机位有变化，但没有特征升级、也没写 --fixed：说清这次变化让哪条特征更近了；说不清就不算前进")
    if regressed:
        nexts.append(f"特征退步：{'、'.join(regressed)}——先查是哪次改动造成的")
    if warn:
        nexts.append(warn)
    if pushed and unmoved and visible is not None:
        nexts.append(f"本波计划推进但没升级：{'、'.join(unmoved)}——下一波继续推还是换做法，写理由")
    if regions:
        farther = [r["region"] for r in regions if r["trend"] == "更远"]
        if farther:
            nexts.append(f"这些部位离参照更远了：{'、'.join(farther)}——先看分区图确认，是本波改动的副作用就先收回")
        if improved and regions and not any(r["trend"] == "更近" for r in regions):
            nexts.append("自评有特征升级，但没有一个分区在颜色/纹理上离参照更近：对照分区图再确认一次升级是否成立")
    out = {"wave": args.n, "comparedWith": prev[0] if prev else None, "change": metrics, "visible": visible,
           "improved": improved, "regressed": regressed, "fixed": args.fixed or "", "forward": forward,
           "noChangeStreak": streak, "board": str(board) if board else None, "regions": regions,
           "cropsBoard": w.get("cropsBoard") if regions else None, "next": nexts}
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        if prev:
            print(f"主机位对比第 {prev[0]} 波：平均差 {metrics['mean']}，眯眼差 {metrics['squint']}，"
                  f"最大局部差 {metrics['cellMax']} → {'有可见变化' if visible else '没有可见变化'}"
                  f"（阈值 平均 {metrics['thresholds']['mean']} / 局部 {metrics['thresholds']['cellMax']}"
                  f"{'，已按连拍噪声抬高' if noise else ''}）")
            if not noise:
                print("提示：画面本身在动（水波、粒子）时，同一版本再截一张用 --again 传入，阈值会按实际抖动抬高。")
        else:
            print("这是第一张主机位截图，下一波开始比较。")
        if improved:
            print(f"特征升级：{'、'.join(f'{f}→{new_status[f]}' for f in improved)}")
        if args.fixed:
            print(f"修掉的主机位缺陷：{args.fixed}")
        if forward is not None:
            print("结论：" + ("算前进了一版" if forward else "不算前进了一版"))
        if board:
            print(f"对比图：{board}（数字只说明有没有变；变得像不像参照，要亲眼看这张图）")
        if regions:
            print("分区离参照的距离（颜色 + 纹理，越小越像）：")
            for r in regions:
                was = f"，上一波 {r['prevGap']} → {r['trend']}" if r["prevGap"] is not None else ""
                print(f"  {r['region']}：本波 {r['gap']}{was}；{r['hint']}")
            print(f"分区对齐图：{w['cropsBoard']}")
        for n in nexts:
            print("下一步：" + n)
    return 4 if (streak >= 2 or forward is False or regressed) else 0


def cmd_try(args, ledger: Ledger):
    if not args.predict.strip() or not args.claim.strip():
        raise Fail("判断和预测都要写：改完之前先写清会看到什么，不然改完什么结果都能解释")
    tid = f"E{len(ledger.data['tries']) + 1}"
    ledger.data["tries"].append({"id": tid, "wave": args.wave, "claim": args.claim.strip(), "predict": args.predict.strip(),
                                 "time": now(), "outcome": None, "saw": ""})
    ledger.save()
    if args.json:
        print(json.dumps({"id": tid}, ensure_ascii=False))
    else:
        print(f"{tid} 已记：{args.claim.strip()}\n  预测：{args.predict.strip()}\n"
              f"做完运行：result {tid} --outcome confirmed|refuted|unclear --saw \"实际看到什么\"")
    return 0


def cmd_result(args, ledger: Ledger):
    t = next((x for x in ledger.data["tries"] if x["id"] == args.id), None)
    if t is None:
        raise Fail(f"没有实验 {args.id}")
    if t["outcome"]:
        raise Fail(f"{args.id} 已记过结果（{t['outcome']}）；要再验证就新开一个 try")
    if not args.saw.strip():
        raise Fail("--saw 要写实际看到了什么（图、数字、日志），不是结论")
    t.update(outcome=args.outcome, saw=args.saw.strip(), resultTime=now())
    ledger.save()
    same = [x for x in ledger.data["tries"] if x["wave"] == t["wave"] and x["outcome"]]
    tail = 0
    for x in reversed(same):
        if x["outcome"] == "unclear":
            tail += 1
        else:
            break
    nexts = []
    if args.outcome == "refuted":
        nexts.append("预测被推翻：依赖这个判断的后续做法一起撤回，回到原因重新想；不要换个说法继续同一条路")
    if tail >= 3:
        nexts.append(f"连续 {tail} 个实验结果不清：这条路没有信息量。换一个能把两种解释分开的实验（只改一个量、"
                     "做反向对照、找参照里的同类现象），或者换路线")
    if args.json:
        print(json.dumps({"id": args.id, "outcome": args.outcome, "unclearStreak": tail, "next": nexts}, ensure_ascii=False, indent=1))
    else:
        print(f"{args.id}：{args.outcome}（预测：{t['predict'][:80]}）")
        for n in nexts:
            print("下一步：" + n)
    return 4 if tail >= 3 else 0


def cmd_status(args, ledger: Ledger):
    base = ledger.need_baseline()
    st = ledger.data["featureStatus"]
    waves = ledger.ordered_waves()
    open_tries = [t for t in ledger.data["tries"] if not t["outcome"]]
    if args.json:
        print(json.dumps({"featureStatus": st, "waves": waves, "openTries": open_tries,
                          "approvals": ledger.data["approvals"]}, ensure_ascii=False, indent=1))
        return 0
    print("特征：" + "  ".join(f"{f}={st.get(f, '未达')}" for f in base["features"]))
    print("| 波 | 推进 | 主机位变化 | 升级 | 修掉 | 前进 |")
    print("|---|---|---|---|---|---|")
    for w in waves:
        vis = {True: "有", False: "无", None: "—"}[w.get("visible")]
        fwd = {True: "是", False: "否", None: "—"}[w.get("forward")]
        print(f"| {w['n']} | {'、'.join(w.get('push') or []) or '（没写）'} | {vis} | {'、'.join(w.get('improved') or []) or '—'} "
              f"| {(w.get('fixed') or '—')[:30]} | {fwd} |")
    if open_tries:
        print("未记结果的实验：" + "；".join(f"{t['id']} {t['claim'][:40]}" for t in open_tries))
    if ledger.data["approvals"]:
        print("用户批准过的目标变更：" + "；".join(f"{a['time']} {a['approval'][:60]}" for a in ledger.data["approvals"]))
    return 0


# --------------------------------------------------------------------------- INTENT.md 检查

# (名称, 识别这一项的标签/句式, 缺了会怎样)
INTENT_ITEMS = [
    ("核心名词和最高级形容词", r"核心名词|最高级|核心词", "成功的定义没钉住，后面容易被拆成“能运行、能看”这类条款"),
    ("例子的三级处理（点名不可替换）", r"点名|不可替换|可替换", "参照取不到时会被悄悄换掉"),
    ("用户第一眼的判断句", r"判断句|第一眼", "出图时没有一句话可以自测“像不像”"),
    ("什么会让用户失望", r"失望", "容易交出报告、最小实现或只修 bug"),
    ("不是 X 而是 Y", r"不是[^。\n]{1,60}?而是|不是[^。\n]{0,60}?[，,；;]\s*是", "底线没写出来"),
    ("决定成败的未知项（最多 3 条）", r"未知项|关键未知|决定成败|(?<![费用间度])未知\s*[：:]", "回读时没有要问用户的问题"),
]


def section_text(text: str, start: int) -> str:
    """这一项的内容：命中所在行的剩余部分，加上紧跟的缩进续行（如编号子项）；
    命中的是 ## 标题时取到下一个标题为止。用来判断是不是只有标签没有内容。"""
    line_start = text.rfind("\n", 0, start) + 1
    lines = text[line_start:].split("\n")
    first = lines[0]
    if first.lstrip().startswith("#"):
        body = []
        for l in lines[1:]:
            if l.lstrip().startswith("#"):
                break
            body.append(l)
        return text[start:line_start + len(first)] + "\n" + "\n".join(body)
    block = [text[start:line_start + len(first)]]
    for l in lines[1:]:
        if l[:1] in (" ", "\t") and l.strip():
            block.append(l)
        else:
            break
    return "\n".join(block)


def count_items(block: str) -> int:
    lines = [l for l in block.splitlines()[1:] if re.match(r"\s*(?:[-*+]|\d+[.)、])\s+\S", l)]
    if lines:
        return len(lines)
    head, _, body = block.partition("：") if "：" in block else block.partition(":")
    return len([x for x in re.split(r"[；;]", body) if x.strip()]) if body else 0


def find_selected(root: Path, given: str | None) -> Path | None:
    if given:
        return Path(given)
    for c in (root / "refs" / "selected" / "selected.json", root / "selected" / "selected.json"):
        if c.is_file():
            return c
    hits = sorted(root.glob("**/selected.json"))
    return hits[0] if hits else None


def cmd_intent(args, ledger: Ledger):
    path = Path(args.intent) if args.intent else ledger.root / "INTENT.md"
    if not path.is_file():
        raise Fail(f"找不到 {path}。开工 10 分钟内先写一屏 INTENT.md（六项见 intent-and-drift 第 1 节）")
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    items = []
    for name, pattern, risk in INTENT_ITEMS:
        m = re.search(pattern, text)
        entry = {"item": name, "present": bool(m), "risk": risk}
        if m:
            block = section_text(text, m.start())
            body = re.sub(pattern, "", block)
            body = re.sub(r"[#*`|：:\-\s]", "", body)
            entry["thin"] = len(body) < 6
            if name.startswith("决定成败"):
                n = count_items(block)
                entry["count"] = n
                entry["tooMany"] = n > 3
        items.append(entry)
    named = [x.strip() for x in re.split(r"[,，、]", args.named or "") if x.strip()]
    if not named:
        m = re.search(r"点名[^：:\n]*[：:]\s*([^\n]+)", text)
        if m:
            line = re.sub(r"（[^）]*）|\([^)]*\)", "", m.group(1))   # 括号里是说明，不是对象
            named = [x.strip(" 《》“”\"'。.") for x in re.split(r"[,，、/；;]|\s+和\s*|\s+及\s*", line) if x.strip()]
            named = [x for x in named if 0 < len(x) <= 20]
    sel_path = find_selected(ledger.root, args.selected)
    selected = json.loads(sel_path.read_text(encoding="utf-8")) if sel_path and sel_path.is_file() else []
    picked = {}
    for e in selected:
        if e.get("verdict") == "selected":
            picked.setdefault(e.get("subject", ""), []).append(e.get("id", ""))
    target = ledger.root / "TARGET.md"
    target_text = target.read_text(encoding="utf-8-sig", errors="replace") if target.is_file() else ""
    coverage = []
    for n in named:
        refs = picked.get(n, [])
        coverage.append({"named": n, "selected": refs, "inTarget": n in target_text})
    extra = [s for s in picked if named and s not in named]
    problems = [f"缺：{i['item']}——{i['risk']}" for i in items if not i["present"]]
    problems += [f"只有标签没有内容：{i['item']}" for i in items if i.get("thin")]
    problems += [f"未知项写了 {i['count']} 条，最多 3 条：只留会改变结果的" for i in items if i.get("tooMany")]
    problems += [f"点名对象“{c['named']}”还没有选入的实机参照（refgrab pick --subject {c['named']} …）" for c in coverage if not c["selected"]]
    problems += [f"点名对象“{c['named']}”没出现在 TARGET.md 里" for c in coverage if target_text and not c["inTarget"]]
    notes = []
    if not named:
        notes.append("没认出点名对象：在 INTENT 里写一行“点名：原神、鸣潮、…”，或用 --named 传入")
    if extra:
        notes.append(f"参照里还有点名之外的对象：{'、'.join(extra)}——只能是同类补充，不能替代点名对象")
    if not sel_path:
        notes.append("没找到 selected.json：参照选完用 refgrab pick 登记，这里才能核对覆盖")
    out = {"intent": str(path), "items": items, "named": coverage, "extraSubjects": extra,
           "selected": str(sel_path) if sel_path else None, "problems": problems, "notes": notes}
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        for i in items:
            mark = "缺" if not i["present"] else ("薄" if i.get("thin") or i.get("tooMany") else "有")
            print(f"[{mark}] {i['item']}" + (f"（{i['count']} 条）" if "count" in i else ""))
        for c in coverage:
            print(f"点名 {c['named']}：选入参照 {'、'.join(c['selected']) or '无'}" + ("" if c["inTarget"] or not target_text else "；TARGET 里没提到"))
        for p in problems:
            print("问题：" + p)
        for n in notes:
            print("注意：" + n)
        if not problems:
            print("INTENT 六项齐全，点名对象都有参照。理解得对不对仍要回读给用户确认，这个检查替代不了。")
    return 4 if problems else 0


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--dir", default=".", help="工作区（WAVES.json 放这里），默认当前目录")
    ap.add_argument("--ref-prefix", default="R", help="参照编号前缀，默认 R")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name, help_text):
        return sub.add_parser(name, parents=[common], help=help_text, description=help_text)

    p = add("baseline", "记下 TARGET 的特征和参照作为基线；目标变更经用户批准后带 --approve 重记")
    p.add_argument("--target", help="默认 <工作区>/TARGET.md"); p.add_argument("--approve", help="用户批准目标变更的原话或消息时间")
    p = add("drift", "对照基线查参照/特征有没有被删、改写或扩范围")
    p.add_argument("--target", help="默认用基线记下的 TARGET 路径")
    p = add("start", "开一波：写明本波推进哪几条 TARGET 特征，并自动查漂移")
    p.add_argument("n", type=int); p.add_argument("--push", required=True, help="特征编号，逗号分隔，如 T1,T3")
    p.add_argument("--why", help="为什么选它们（一句话）"); p.add_argument("--target")
    p = add("end", "收一波：主机位和上一波比可见变化，出对比图，判断算不算前进（没先 start 也会记下，但本波没有推进项可核）")
    p.add_argument("n", type=int); p.add_argument("--main", required=True, help="本波主机位截图（同机位、同时间、同光照）")
    p.add_argument("--ref", help="参照图（进对比图第一列）"); p.add_argument("--roi", help="只比这个框（如水面）：x0,y0,x1,y1，≤1 为比例")
    p.add_argument("--status", help="特征当前状态，如 T1=接近,T3=达到（三级：未达/接近/达到）")
    p.add_argument("--fixed", help="本波修掉的主机位可见缺陷（一句话）")
    p.add_argument("--again", help="同一版本、同机位再截一张（隔几秒）：量出画面本身的抖动，作为变化阈值的底")
    p.add_argument("--min-change", type=float, default=2.0, help="平均差阈值（0–255，32 宽下），默认 2；局部格阈值为它的 2.5 倍")
    p.add_argument("--board", nargs="?", const=None, default=None, help="对比图路径，默认 waves/waveN_compare.png")
    p.add_argument("--no-board", dest="board", action="store_const", const=False)
    p.add_argument("--regions", help='分区比离参照的远近（要 --ref）："近岸=x0,y0,x1,y1;远水=…"。参照构图不同：先把参照的全部区域写完，'
                   '再写一个 |，再按同样的名字和顺序写主机位的全部区域，如 "近岸=0.05,0.7,0.3,0.9;远水=0.1,0.3,0.6,0.4 | 近岸=0.1,0.75,0.4,0.95;远水=0.3,0.35,0.8,0.45"')
    p = add("try", "实验前先写可推翻的预测")
    p.add_argument("claim", help="要验证的判断，如：远水发灰是山体倒影盖住了水色"); p.add_argument("--predict", required=True)
    p.add_argument("--wave", type=int)
    p = add("result", "记实验结果")
    p.add_argument("id"); p.add_argument("--outcome", required=True, choices=["confirmed", "refuted", "unclear"])
    p.add_argument("--saw", required=True)
    add("status", "各波一览")
    p = add("intent", "查 INTENT.md 六项写没写全、每个点名对象有没有选入的实机参照")
    p.add_argument("--intent", help="默认 <工作区>/INTENT.md"); p.add_argument("--named", help="点名对象，逗号分隔；不给就读 INTENT 里“点名：…”那一行")
    p.add_argument("--selected", help="refgrab pick 生成的 selected.json；默认在工作区里找")

    args = ap.parse_args(argv)
    ledger = Ledger(Path(args.dir))
    func = {"baseline": cmd_baseline, "drift": cmd_drift, "start": cmd_start, "end": cmd_end, "try": cmd_try,
            "result": cmd_result, "status": cmd_status, "intent": cmd_intent}[args.cmd]
    try:
        return func(args, ledger) or 0
    except Fail as e:
        print(f"失败：{e}", file=sys.stderr)
        return 2
    except (OSError, ValueError, json.JSONDecodeError) as e:
        print(f"失败：{type(e).__name__}: {str(e)[:300]}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
