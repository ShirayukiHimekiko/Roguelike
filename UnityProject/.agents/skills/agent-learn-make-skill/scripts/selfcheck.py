#!/usr/bin/env python3
"""selfcheck：一条命令确认本 Skill 的工具在这台机器上真能用（默认不联网，约 10 秒）。

做法：在临时目录（或 --keep 指定的演示目录）里合成参照图和两版“主机位”，按真实命令行调用走一遍
取参照之后的完整流程：触表 → 登记参照 → 量色 → 看图板 → 分区对比 → 写 TARGET/INTENT → 开波 → 收波 → 停线提示。
每一步用和你平时一样的写法（python -X utf8 脚本 子命令 …）运行，所以编码、路径、依赖问题都会在这里暴露。

用法：
  python -X utf8 "<本 Skill 目录>\\scripts\\selfcheck.py"              离线自检
  python -X utf8 "<本 Skill 目录>\\scripts\\selfcheck.py" --online     另外跑 refgrab doctor 查各来源能不能连
  python -X utf8 "<本 Skill 目录>\\scripts\\selfcheck.py" --keep demo  保留演示工作区，可以打开里面的图看每个工具产出什么

退出码：0 全部通过；1 有步骤失败（看表里的“说明”列）；2 自检本身没法运行。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import random
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REFGRAB = HERE / "refgrab.py"
WAVELOG = HERE / "wavelog.py"
LEARNPACK = HERE / "learnpack.py"
SKILL_FILES = HERE / "skill_files.py"
NUMSPEC = HERE / "numspec.py"
PARAMAP = HERE / "paramap.py"

TARGET = """# 目标：自检用水体
## 参照
R1–R2：示例作品的合成参照图
## 可检验特征
- T1 近岸到远处至少 3 个可区分色阶（R1）
- T2 岸线有成型的白色泡沫带（R2）
"""

INTENT = """# INTENT
- 核心名词：二次元水体；最高级：顶级
- 点名：示例作品（不可替换）
- 判断句：这水像示例作品里的水吗？
- 失望：只交报告、换题、只修 bug 不推主线
- 不是调研报告，而是做出能看的水
- 关键未知：
  1. 泡沫用贴图还是几何
"""


def make_scene(path: Path, sea, seed: int, foam: bool = False, size=(960, 540)):
    """合成一张“水面截图”：天空、远水、近水三段，近水带细碎亮纹；foam=True 时加一条岸线白带。"""
    from PIL import Image, ImageDraw
    rnd = random.Random(seed)
    im = Image.new("RGB", size, sea)
    d = ImageDraw.Draw(im)
    w, h = size
    d.rectangle([0, 0, w, h // 3], fill=(175, 205, 235))
    far = tuple(max(0, c - 40) for c in sea)
    d.rectangle([0, h // 3, w, h // 2], fill=far)
    for _ in range(140):
        x, y = rnd.randrange(w), rnd.randrange(h // 2, h)
        d.line([x, y, x + rnd.randint(8, 30), y], fill=(235, 245, 250), width=2)
    if foam:
        d.rectangle([0, int(h * 0.82), w, int(h * 0.84)], fill=(250, 250, 250))
    im.save(path)
    return path


def run(argv: list[str], cwd: Path, timeout: int = 120) -> tuple[int, str, str, float]:
    started = time.monotonic()
    p = subprocess.run([sys.executable, "-X", "utf8", *map(str, argv)], cwd=cwd, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=timeout)
    return p.returncode, p.stdout, p.stderr, round(time.monotonic() - started, 1)


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--online", action="store_true", help="另外运行 refgrab doctor（联网，约 10 秒）")
    ap.add_argument("--keep", help="把演示工作区保留在这个目录（必须不存在或为空）")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    rows = []

    def step(name, ok, note="", seconds=None):
        rows.append({"step": name, "ok": bool(ok), "note": note.strip().splitlines()[-1][:160] if note.strip() else "",
                     "seconds": seconds})
        return ok

    # 1. 依赖
    deps = [("PIL", "pillow", True), ("jsonschema", "jsonschema", False), ("yaml", "PyYAML", False),
            ("yt_dlp", "yt-dlp", False), ("imageio_ffmpeg", "imageio-ffmpeg", False), ("pypdf", "pypdf", False)]
    missing_required = []
    for mod, pkg, required in deps:
        have = importlib.util.find_spec(mod) is not None
        note = "" if have else (f"缺：python -m pip install {pkg}" + ("（必需）" if required else "（只影响对应功能）"))
        step(f"依赖 {pkg}", have or not required, note)
        if required and not have:
            missing_required.append(pkg)
    if missing_required:
        return report(rows, args, fatal=f"缺少必需依赖 {'、'.join(missing_required)}，后面的步骤跑不了")

    if args.keep:
        root = Path(args.keep).resolve()
        if root.exists() and any(root.iterdir()):
            print(f"失败：--keep 目录 {root} 不是空的", file=sys.stderr)
            return 2
        root.mkdir(parents=True, exist_ok=True)
        cleanup = None
    else:
        cleanup = tempfile.TemporaryDirectory(prefix="skill-selfcheck-")
        root = Path(cleanup.name)
    try:
        refs = root / "refs" / "示例作品"
        refs.mkdir(parents=True)
        r1 = make_scene(refs / "ref_a.png", (30, 160, 200), 1)
        r2 = make_scene(refs / "ref_b.png", (35, 150, 205), 2, foam=True)
        v1 = make_scene(root / "v1_main.png", (110, 125, 125), 3)
        v2 = make_scene(root / "v2_main.png", (50, 150, 190), 4)
        (root / "TARGET.md").write_text(TARGET, encoding="utf-8")
        (root / "INTENT.md").write_text(INTENT, encoding="utf-8")

        def cli(name, script, *a, expect=(0,), check=None):
            rc, out, err, sec = run([script, *a], root)
            ok = rc in expect and (check is None or check(out))
            note = "" if ok else f"退出码 {rc}（期望 {'/'.join(map(str, expect))}）：{(err or out)}"
            return step(name, ok, note, sec), out

        cli("refgrab sheet 触表", REFGRAB, "sheet", refs, "--out", root / "cmp" / "contact.png")
        cli("refgrab pick 登记参照", REFGRAB, "pick", r1, r2, "--subject", "示例作品", "--why", "自检：合成参照",
            "--src", "https://example.invalid/ref", "--out", root / "refs" / "selected",
            check=lambda o: "选入 R1" in o)
        cli("refgrab measure 量色", REFGRAB, "measure", r1, "--roi", "0,0.4,1,1", "--grid", "3x1", "--palette", "4")
        cli("refgrab look 看图板", REFGRAB, "look", r1, v2, v1, "--roi", "0,0.4,1,1", "--out", root / "cmp" / "look.png",
            check=lambda o: "饱和度" in o)
        cli("refgrab crops 分区对比", REFGRAB, "crops", r1, v2, "--labels", "R1|v2", "--out", root / "cmp" / "crops.png",
            "--regions", "近水=0,0.6,1,1;远水=0,0.34,1,0.48", check=lambda o: "[近水]" in o)
        cli("numspec extract 参照取目标色", NUMSPEC, "extract", r1, "--feature", "T1", "--out", root / "SPEC.json",
            "--regions", "近水=0,0.6,1,1;远水=0,0.34,1,0.48", check=lambda o: "近水" in o)
        cli("numspec check 当前版（发灰应未达）", NUMSPEC, "check", v1, "--spec", root / "SPEC.json", expect=(4,),
            check=lambda o: "--status T1=未达" in o)
        cli("numspec engine 引擎值 + 色带", NUMSPEC, "engine", "--spec", root / "SPEC.json", "--order", "近水,远水",
            "--ramp", root / "cmp" / "ramp.png", "--ramp-steps", "2", check=lambda o: "new Vector4(" in o)
        cli("numspec world 屏幕→米", NUMSPEC, "world", "--pct", "1.5", "--dist", "20", "--grazing", "15",
            check=lambda o: "米" in o)
        cli("paramap def 写下以为的含义", PARAMAP, "def", "FoamWidth", "--kind", "float", "--range", "0,1", "--expect", "up",
            "--means", "泡沫带宽度")
        for x, y, rd in (("0", "0", "0"), ("0.5", "1", "0.5"), ("1", "2", "1"), ("1.5", "2", "1")):
            cli(f"paramap obs {x}", PARAMAP, "obs", "FoamWidth", x, "--metric", f"宽={y}", "--read", rd)
        cli("paramap fit（应查出钳制）", PARAMAP, "fit", "FoamWidth", expect=(4,), check=lambda o: "保存值 ≠ 生效值" in o)
        cli("paramap pick 内插", PARAMAP, "pick", "FoamWidth", "--want", "宽=1.5", check=lambda o: "0.75" in o)
        cli("wavelog intent 六项检查", WAVELOG, "intent", check=lambda o: "六项齐全" in o)
        cli("wavelog baseline", WAVELOG, "baseline", check=lambda o: "2 条特征" in o)
        cli("wavelog start 开波", WAVELOG, "start", "1", "--push", "T1")
        cli("wavelog end 第 1 波", WAVELOG, "end", "1", "--main", v1, "--ref", r1)
        cli("wavelog end 第 2 波（应算前进）", WAVELOG, "end", "2", "--main", v2, "--ref", r1, "--status", "T1=接近",
            "--regions", "近水=0,0.6,1,1", check=lambda o: "算前进了一版" in o and "更近" in o)
        cli("wavelog end 第 3 波（没变化）", WAVELOG, "end", "3", "--main", v2, "--no-board", expect=(4,))
        cli("wavelog end 第 4 波（应提示停线）", WAVELOG, "end", "4", "--main", v2, "--no-board", expect=(4,),
            check=lambda o: "停掉当前技术线" in o)
        cli("wavelog try/result", WAVELOG, "try", "远水发灰是反射盖住了水色", "--predict", "关反射后远水变蓝")
        cli("wavelog status", WAVELOG, "status", check=lambda o: "| 2 | " in o)
        if importlib.util.find_spec("jsonschema") is not None:
            cli("skill_files inspect 本 Skill", SKILL_FILES, "inspect", HERE.parent, check=lambda o: '"files_passed": true' in o)
        if args.online:
            rc, out, err, sec = run([REFGRAB, "doctor"], root, timeout=180)
            step("refgrab doctor 联网来源", rc in (0, 1), "部分来源不可用，见 doctor 输出" if rc == 1 else (err or ""), sec)
            if rc == 1:
                rows[-1]["note"] = "部分来源不可用（正常，搜索会跳过它们）：" + "；".join(
                    l.strip() for l in out.splitlines() if "失败" in l or "不可用" in l)[:150]
        return report(rows, args, workspace=root if args.keep else None)
    finally:
        if cleanup:
            cleanup.cleanup()


def report(rows, args, fatal: str | None = None, workspace: Path | None = None) -> int:
    failed = [r for r in rows if not r["ok"]]
    if args.json:
        print(json.dumps({"passed": not failed and not fatal, "steps": rows, "fatal": fatal,
                          "workspace": str(workspace) if workspace else None}, ensure_ascii=False, indent=1))
    else:
        print("| 步骤 | 结果 | 秒 | 说明 |")
        print("|---|---|---|---|")
        for r in rows:
            print(f"| {r['step']} | {'通过' if r['ok'] else '失败'} | {r['seconds'] if r['seconds'] is not None else ''} | {r['note']} |")
        if fatal:
            print("失败：" + fatal)
        elif failed:
            print(f"{len(failed)} 步失败。按“说明”列处理；工具坏了就别用它的输出做判断，告诉用户。")
        else:
            print("全部通过：这台机器上 refgrab / wavelog 的离线功能都能用。")
        if workspace:
            print(f"演示工作区：{workspace}（cmp/ 下是看图板和分区图，waves/ 下是每波对比图，WAVES.json 是波次记录）")
    if fatal:
        return 2
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
