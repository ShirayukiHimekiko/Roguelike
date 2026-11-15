"""wavelog 离线回归：TARGET 解析、漂移、主机位变化/停线、实验记录、命令行退出码。"""
import contextlib
import io
import json
import random
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wavelog  # noqa: E402

TARGET = """# 目标：顶级二次元水体

## 参照
refs_sheet.jpg：R1–R3 原神湖面，R4-R6 鸣潮海岸，R7~9 王国之泪。

## 可检验特征
- T1 近岸到远处至少 3 个可区分色阶（R1、R3）。
- T2 岸线泡沫是成型的白色带：内缘硬、外缘碎（R4、R6）。
| T3 | 高光是横向断续的硬边条带 | R1 |
3. T4 近岸能清楚看到水底

```
- T9 代码块里的不算
```
"""


def cli(root, *argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = wavelog.main(["--dir", str(root), *argv])
    return rc, out.getvalue(), err.getvalue()


def frame(path, sea=(40, 120, 190), highlight=None, jitter=0, seed=0, size=(320, 180)):
    """合成主机位：上天下海；highlight=(x0,y0,x1,y1) 画一块高光；jitter 模拟水波逐帧细碎抖动。"""
    from PIL import Image, ImageDraw
    im = Image.new("RGB", size, sea)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, size[0], size[1] // 3], fill=(170, 200, 230))
    if highlight:
        d.rectangle(highlight, fill=(250, 250, 240))
    if jitter:
        rnd = random.Random(seed)
        px = im.load()
        for y in range(size[1] // 3, size[1]):
            for x in range(0, size[0], 2):
                r, g, b = px[x, y]
                k = rnd.randint(-jitter, jitter)
                px[x, y] = (max(0, min(255, r + k)), max(0, min(255, g + k)), max(0, min(255, b + k)))
    im.save(path)
    return path


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.target = self.root / "TARGET.md"
        self.target.write_text(TARGET, encoding="utf-8")

    def run_ok(self, *argv, rc=0):
        code, out, err = cli(self.root, *argv)
        self.assertEqual(code, rc, out + err)
        return out, err


class ParseTests(Base):
    def test_features_from_list_table_and_numbered_lines(self):
        t = wavelog.parse_target(self.target)
        self.assertEqual(list(t["features"]), ["T1", "T2", "T3", "T4"])   # 代码块里的 T9 不算
        self.assertIn("硬边条带", t["features"]["T3"])

    def test_reference_ranges_are_expanded(self):
        t = wavelog.parse_target(self.target)
        self.assertEqual(t["refs"], [f"R{i}" for i in range(1, 10)])

    def test_table_rows_with_ref_ids_count_as_refs_not_features(self):
        self.target.write_text("| R1 | a.png |\n| R12 | b.png |\n- F01 水色\n", encoding="utf-8")
        t = wavelog.parse_target(self.target)
        self.assertEqual(list(t["features"]), ["F01"])
        self.assertEqual(t["refs"], ["R1", "R12"])

    def test_no_features_is_an_error(self):
        self.target.write_text("# 只有标题\n", encoding="utf-8")
        rc, _, err = cli(self.root, "baseline")
        self.assertEqual(rc, 2)
        self.assertIn("T1", err)


class DriftTests(Base):
    def test_removed_rewritten_and_added_are_reported(self):
        self.run_ok("baseline")
        text = TARGET.replace("至少 3 个", "至少 2 个").replace("R7~9 王国之泪", "")
        text = text.replace("3. T4 近岸能清楚看到水底", "- T5 第二条溪流")
        self.target.write_text(text, encoding="utf-8")
        out, _ = self.run_ok("drift", rc=4)
        self.assertIn("参照少了：R7、R8、R9", out)
        self.assertIn("特征删了：T4", out)
        self.assertIn("特征改写了：T1", out)
        self.assertIn("新增特征：T5", out)

    def test_rebaseline_needs_user_approval_when_target_changed(self):
        self.run_ok("baseline")
        self.target.write_text(TARGET.replace("- T2", "- T2x"), encoding="utf-8")   # T2 消失
        _, err = self.run_ok("baseline", rc=2)
        self.assertIn("--approve", err)
        self.run_ok("baseline", "--approve", "用户 18:10：泡沫先不做")
        state = json.loads((self.root / "WAVES.json").read_text(encoding="utf-8"))
        self.assertEqual(state["approvals"][0]["approval"], "用户 18:10：泡沫先不做")
        self.run_ok("drift")

    def test_adding_only_is_not_drift(self):
        self.run_ok("baseline")
        self.target.write_text(TARGET + "- T5 船尾浪（R10）\n", encoding="utf-8")
        out, _ = self.run_ok("drift")
        self.assertIn("新增特征：T5", out)
        self.assertIn("新增参照：R10", out)


class WaveTests(Base):
    def setUp(self):
        super().setUp()
        self.run_ok("baseline")

    def test_push_must_be_target_features(self):
        _, err = self.run_ok("start", "1", "--push", "T1,BUG7", rc=2)
        self.assertIn("BUG7", err)
        out, _ = self.run_ok("start", "1", "--push", "T2", "--why", "泡沫最显眼")
        self.assertIn("T2（未达）", out)

    def test_visible_change_with_feature_upgrade_is_forward(self):
        a = frame(self.root / "v1.png")
        b = frame(self.root / "v2.png", highlight=(40, 100, 140, 115))
        self.run_ok("start", "1", "--push", "T3"); self.run_ok("end", "1", "--main", str(a), "--no-board")
        self.run_ok("start", "2", "--push", "T3")
        out, _ = self.run_ok("end", "2", "--main", str(b), "--status", "T3=接近", "--no-board")
        self.assertIn("有可见变化", out)
        self.assertIn("算前进了一版", out)

    def test_change_without_upgrade_or_fix_is_not_forward(self):
        a = frame(self.root / "v1.png")
        b = frame(self.root / "v2.png", sea=(60, 130, 170))
        self.run_ok("end", "1", "--main", str(a), "--no-board")
        out, _ = self.run_ok("end", "2", "--main", str(b), "--no-board", rc=4)
        self.assertIn("说清这次变化让哪条特征更近", out)
        out, _ = self.run_ok("end", "3", "--main", str(a), "--fixed", "主机位远水灰块", "--no-board")
        self.assertIn("算前进了一版", out)

    def test_two_waves_without_visible_change_trigger_stop_line(self):
        a = frame(self.root / "v1.png")
        self.run_ok("end", "1", "--main", str(a), "--status", "T1=接近", "--no-board")
        out, _ = self.run_ok("end", "2", "--main", str(a), "--fixed", "地形 NaN", "--no-board", rc=4)
        self.assertIn("不算前进", out)                       # 修了 bug 但主机位没变 → 不算
        self.assertNotIn("停掉", out)
        out, _ = self.run_ok("end", "3", "--main", str(a), "--no-board", rc=4)
        self.assertIn("连续 2 波", out)
        self.assertIn("T2、T3、T4", out)                      # 指回差距最大的特征

    def test_water_jitter_alone_is_not_visible_change(self):
        a = frame(self.root / "v1.png", jitter=40, seed=1)
        same_build_later = frame(self.root / "v2.png", jitter=40, seed=2)
        self.run_ok("end", "1", "--main", str(a), "--no-board")
        out, _ = self.run_ok("end", "2", "--main", str(same_build_later), "--no-board", rc=4)
        self.assertIn("没有可见变化", out)

    def test_again_raises_threshold_to_measured_noise(self):
        m = wavelog.change_metrics(frame(self.root / "a.png", jitter=40, seed=1),
                                   frame(self.root / "b.png", jitter=40, seed=2), None)
        noisy = {"mean": 5.0, "cellMax": 9.0}
        _, _ = wavelog.judge_change(dict(m), 2.0, noisy)
        m2 = dict(m)
        wavelog.judge_change(m2, 2.0, noisy)
        self.assertEqual(m2["thresholds"], {"mean": 10.0, "cellMax": 18.0})

    def test_local_highlight_change_is_caught_by_cell(self):
        a = frame(self.root / "a.png")
        b = frame(self.root / "b.png", highlight=(250, 140, 300, 170))
        m = wavelog.change_metrics(a, b, None)
        visible, _ = wavelog.judge_change(m, 2.0)
        self.assertTrue(visible)
        self.assertGreater(m["cellMax"], m["mean"] * 3)

    def test_roi_ignores_changes_outside_water(self):
        from PIL import Image, ImageDraw
        a = frame(self.root / "a.png")
        b = frame(self.root / "b.png")
        im = Image.open(b)
        ImageDraw.Draw(im).rectangle([0, 0, 80, 40], fill=(255, 0, 0))   # 小地图 UI 变了
        im.save(b)
        self.assertTrue(wavelog.judge_change(wavelog.change_metrics(a, b, None), 2.0)[0])
        self.assertFalse(wavelog.judge_change(wavelog.change_metrics(a, b, "0,0.4,1,1"), 2.0)[0])

    def test_camera_move_is_warned(self):
        from PIL import Image
        a = frame(self.root / "a.png", highlight=(40, 100, 140, 115))
        im = Image.open(a)
        moved = im.transform(im.size, Image.AFFINE, (1, 0.35, -20, 0, 1, 25))   # 视角变了：地平线和高光位置都移了
        moved.save(self.root / "moved.png")
        recolor = frame(self.root / "recolor.png", sea=(20, 150, 210), highlight=(40, 100, 140, 115))
        same_cam = wavelog.change_metrics(a, recolor, None)
        self.assertIsNone(wavelog.judge_change(same_cam, 2.0)[1])
        other_cam = wavelog.change_metrics(a, self.root / "moved.png", None)
        self.assertIn("机位", wavelog.judge_change(other_cam, 2.0)[1])

    def test_regression_is_flagged(self):
        a = frame(self.root / "v1.png")
        b = frame(self.root / "v2.png", highlight=(40, 100, 140, 115))
        self.run_ok("end", "1", "--main", str(a), "--status", "T1=达到", "--no-board")
        out, _ = self.run_ok("end", "2", "--main", str(b), "--status", "T1=接近,T3=接近", "--no-board", rc=4)
        self.assertIn("特征退步：T1", out)

    def test_bad_status_level_rejected(self):
        a = frame(self.root / "v1.png")
        _, err = self.run_ok("end", "1", "--main", str(a), "--status", "T1=好多了", "--no-board", rc=2)
        self.assertIn("未达/接近/达到", err)

    def test_compare_board_written(self):
        a = frame(self.root / "v1.png")
        b = frame(self.root / "v2.png", highlight=(40, 100, 140, 115))
        ref = frame(self.root / "ref.png", sea=(30, 150, 200))
        self.run_ok("end", "1", "--main", str(a))
        out, _ = self.run_ok("end", "2", "--main", str(b), "--ref", str(ref), "--status", "T3=接近")
        self.assertTrue((self.root / "waves" / "wave2_compare.png").is_file())
        self.assertIn("亲眼看", out)

    def test_status_table_and_json(self):
        a = frame(self.root / "v1.png")
        self.run_ok("start", "1", "--push", "T1"); self.run_ok("end", "1", "--main", str(a), "--no-board")
        out, _ = self.run_ok("status")
        self.assertIn("| 1 | T1 |", out)
        out, _ = self.run_ok("--json", "status")
        self.assertEqual(json.loads(out)["featureStatus"]["T1"], "未达")


class TryTests(Base):
    def test_prediction_first_then_result(self):
        out, _ = self.run_ok("try", "远水发灰是山体倒影盖住了水色", "--predict", "关反射后远水变蓝", "--wave", "3")
        self.assertIn("E1", out)
        out, _ = self.run_ok("result", "E1", "--outcome", "refuted", "--saw", "关反射后远水仍灰")
        self.assertIn("一起撤回", out)
        _, err = self.run_ok("result", "E1", "--outcome", "confirmed", "--saw", "x", rc=2)
        self.assertIn("已记过", err)

    def test_three_unclear_results_in_a_wave_say_change_question(self):
        for i in range(1, 4):
            self.run_ok("try", f"猜测{i}", "--predict", "会变", "--wave", "2")
        self.run_ok("result", "E1", "--outcome", "unclear", "--saw", "看不出")
        self.run_ok("result", "E2", "--outcome", "unclear", "--saw", "看不出")
        out, _ = self.run_ok("result", "E3", "--outcome", "unclear", "--saw", "看不出", rc=4)
        self.assertIn("没有信息量", out)

    def test_empty_prediction_rejected(self):
        _, err = self.run_ok("try", "x", "--predict", "  ", rc=2)
        self.assertIn("预测", err)


GOOD_INTENT = """# INTENT
- 核心名词：二次元水体；最高级：顶级
- 点名：原神、鸣潮、王国之泪（不可替换；“可自行查找”只能增加）
- 判断句：这水像原神、塞尔达里的水吗？
- 失望：只交报告、换题、只修 bug 不推主线
- 不是调研报告，而是真正做出顶级效果
- 关键未知：
  1. 鸣潮海岸的泡沫是贴图还是几何
  2. 用户要白天还是黄昏
"""


class IntentTests(Base):
    def write_intent(self, text):
        (self.root / "INTENT.md").write_text(text, encoding="utf-8")

    def select(self, *subjects):
        d = self.root / "refs" / "selected"
        d.mkdir(parents=True, exist_ok=True)
        rows = [{"id": f"R{i}", "subject": s, "verdict": "selected"} for i, s in enumerate(subjects, 1)]
        (d / "selected.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")

    def test_complete_intent_with_refs_for_every_named_object_passes(self):
        self.write_intent(GOOD_INTENT)
        self.select("原神", "鸣潮", "王国之泪")
        self.target.write_text(TARGET.replace("R7~9 王国之泪", "R7~9 王国之泪").replace("原神湖面", "原神湖面 鸣潮"), encoding="utf-8")
        out, _ = self.run_ok("intent")
        self.assertIn("六项齐全", out)
        self.assertIn("点名 鸣潮：选入参照 R2", out)

    def test_gpt_style_intent_missing_items_is_flagged(self):
        # 来自 L4 实测的真实写法：有失望、有关键未知，缺核心名词、点名三级、判断句、不是X而是Y
        self.write_intent("本轮是审美判别小测，不是 Unity 制作任务。\n\n用户会失望的情况：按误导标题认游戏。\n\n"
                          "预算：token/费用未知。\n\n关键未知：来源真实性；视觉差距；可运行性。\n")
        out, _ = self.run_ok("intent", "--named", "原神", rc=4)
        for item in ("核心名词", "例子的三级", "用户第一眼的判断句", "不是 X 而是 Y"):
            self.assertIn(f"[缺] {item}", out)
        self.assertIn("[有] 决定成败的未知项（最多 3 条）（3 条）", out)   # 不被“费用未知”误判
        self.assertIn("没有选入的实机参照", out)

    def test_too_many_unknowns_and_label_without_content(self):
        self.write_intent(GOOD_INTENT.replace("- 判断句：这水像原神、塞尔达里的水吗？", "- 判断句：")
                          .replace("  2. 用户要白天还是黄昏\n", "  2. a\n  3. b\n  4. c\n"))
        self.select("原神", "鸣潮", "王国之泪")
        out, _ = self.run_ok("intent", rc=4)
        self.assertIn("只有标签没有内容：用户第一眼的判断句", out)
        self.assertIn("最多 3 条", out)

    def test_named_parsed_from_intent_and_substitute_subject_noted(self):
        self.write_intent(GOOD_INTENT)
        self.select("原神", "鸣潮", "吉卜力")
        out, _ = self.run_ok("intent", rc=4)
        self.assertIn("“王国之泪”还没有选入", out)
        self.assertIn("点名之外的对象：吉卜力", out)

    def test_missing_intent_file(self):
        _, err = self.run_ok("intent", rc=2)
        self.assertIn("10 分钟", err)


class RegionTests(Base):
    def setUp(self):
        super().setUp()
        self.run_ok("baseline")

    def test_regions_report_closer_and_farther_against_reference(self):
        ref = frame(self.root / "ref.png", sea=(30, 160, 200))
        v1 = frame(self.root / "v1.png", sea=(110, 120, 120))      # 发灰
        v2 = frame(self.root / "v2.png", sea=(50, 150, 190))       # 接近参照
        spec = "近水=0,0.6,1,1;天空=0,0,1,0.3"
        self.run_ok("end", "1", "--main", str(v1), "--ref", str(ref), "--regions", spec, "--no-board")
        out, _ = self.run_ok("end", "2", "--main", str(v2), "--ref", str(ref), "--regions", spec,
                             "--status", "T1=接近", "--no-board")
        self.assertIn("近水：本波", out)
        self.assertIn("→ 更近", out)
        self.assertTrue((self.root / "waves" / "wave2_crops.png").is_file())
        v3 = frame(self.root / "v3.png", sea=(140, 140, 140))
        out, _ = self.run_ok("end", "3", "--main", str(v3), "--ref", str(ref), "--regions", spec, "--no-board", rc=4)
        self.assertIn("离参照更远了：近水", out)
        self.assertIn("发灰", out)

    def test_upgrade_claim_without_any_closer_region_is_questioned(self):
        ref = frame(self.root / "ref.png", sea=(30, 160, 200))
        v1 = frame(self.root / "v1.png", sea=(110, 120, 120))
        v2 = frame(self.root / "v2.png", sea=(110, 120, 120), highlight=(10, 10, 60, 30))   # 只改了天空一角
        spec = "近水=0,0.6,1,1"
        self.run_ok("end", "1", "--main", str(v1), "--ref", str(ref), "--regions", spec, "--no-board")
        out, _ = self.run_ok("end", "2", "--main", str(v2), "--ref", str(ref), "--regions", spec,
                             "--status", "T1=接近", "--no-board")
        self.assertIn("没有一个分区", out)

    def test_ref_and_main_can_have_different_boxes(self):
        ref = frame(self.root / "ref.png", sea=(30, 160, 200))
        v1 = frame(self.root / "v1.png", sea=(30, 160, 200))
        v2 = frame(self.root / "v2.png", sea=(30, 160, 200))
        out, _ = self.run_ok("end", "1", "--main", str(v1), "--no-board")
        out, _ = self.run_ok("end", "2", "--main", str(v2), "--ref", str(ref), "--fixed", "x", "--no-board",
                             "--regions", "水=0,0.5,1,1 | 水=0,0.4,1,0.9", rc=4)   # 主机位没变 → rc 4，但分区正常算出
        self.assertIn("颜色和纹理接近", out)

    def test_regions_need_ref(self):
        v1 = frame(self.root / "v1.png")
        _, err = self.run_ok("end", "1", "--main", str(v1), "--regions", "水=0,0.5,1,1", "--no-board", rc=2)
        self.assertIn("--ref", err)


class CliTests(Base):
    def test_commands_before_baseline_fail_clearly(self):
        _, err = self.run_ok("drift", rc=2)
        self.assertIn("baseline", err)

    def test_every_subcommand_has_help(self):
        for cmd in ("baseline", "drift", "start", "end", "try", "result", "status", "intent"):
            with self.subTest(cmd=cmd), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as cm:
                    wavelog.main([cmd, "--help"])
                self.assertEqual(cm.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
