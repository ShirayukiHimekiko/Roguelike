"""paramap 离线回归：四种语义类型的映射分析、保存值≠生效值、阈值/饱和/方向、内插反推、截图结果量。"""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paramap  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def cli(self, *argv, rc=0):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = paramap.main(["--dir", str(self.root), *argv])
        self.assertEqual(code, rc, out.getvalue() + err.getvalue())
        return out.getvalue(), err.getvalue()

    def fit(self, name, rc=0):
        out, _ = self.cli("--json", "fit", name, rc=rc)
        return json.loads(out)

    def sweep(self, name, pairs, metric="y"):
        for x, y in pairs:
            self.cli("obs", name, str(x), "--metric", f"{metric}={y}")


class NumericTests(Base):
    def test_linear_mapping_and_pick_interpolates(self):
        self.cli("def", "W", "--kind", "float", "--expect", "up", "--means", "宽度")
        self.sweep("W", [(0, 0), (0.25, 1), (0.5, 2), (1, 4)])
        r = self.fit("W")
        self.assertIn("近似线性", r["metrics"]["y"]["shape"])
        self.assertAlmostEqual(r["metrics"]["y"]["slope"], 4, places=3)
        out, _ = self.cli("pick", "W", "--want", "y=3")
        self.assertIn("0.75", out)
        self.cli("pick", "W", "--want", "y=9", rc=4)

    def test_threshold_saturation_and_dead_head_found(self):
        self.cli("def", "T", "--kind", "float", "--means", "阈值")
        self.sweep("T", [(0, 0), (0.2, 0), (0.4, 0), (0.5, 10), (0.6, 10), (0.8, 10)])
        r = self.fit("T")
        m = r["metrics"]["y"]
        self.assertIn("阈值", m["shape"])
        self.assertIn("0.4–0.5", m["shape"])
        self.assertTrue(any("没反应" in n for n in r["notes"]))
        self.assertTrue(any("饱和" in n for n in r["notes"]))

    def test_no_effect_is_a_problem(self):
        self.cli("def", "D", "--kind", "float", "--means", "以为有用")
        self.sweep("D", [(0, 5), (1, 5), (10, 5.0001)])
        r = self.fit("D", rc=4)
        self.assertEqual(r["metrics"]["y"]["shape"], "没有作用")
        self.assertIn("没接线", r["problems"][0])

    def test_direction_contradicting_expectation(self):
        self.cli("def", "R", "--kind", "float", "--expect", "up", "--means", "越大越亮")
        self.sweep("R", [(0, 9), (1, 6), (2, 3)])
        r = self.fit("R", rc=4)
        self.assertTrue(any("方向和预期相反" in p for p in r["problems"]))

    def test_non_monotonic_peak(self):
        self.cli("def", "P", "--kind", "float", "--means", "x")
        self.sweep("P", [(0, 0), (1, 5), (2, 8), (3, 5), (4, 0)])
        r = self.fit("P")
        self.assertIn("先升后降", r["metrics"]["y"]["direction"])
        self.assertTrue(any("极值在 2" in n for n in r["notes"]))
        out, _ = self.cli("pick", "P", "--want", "y=5")
        self.assertIn("多个解", out)

    def test_readback_mismatch_and_clamp_uses_effective_value(self):
        self.cli("def", "C", "--kind", "float", "--range", "0,1", "--means", "x")
        self.cli("obs", "C", "0", "--metric", "y=0", "--read", "0")
        self.cli("obs", "C", "1", "--metric", "y=10", "--read", "1")
        self.cli("obs", "C", "2", "--metric", "y=10", "--read", "1")
        r = self.fit("C", rc=4)
        self.assertTrue(any("保存值 ≠ 生效值" in p and "设 2.0 读回 1.0" in p for p in r["problems"]))
        self.assertEqual([p[0] for p in r["metrics"]["y"]["points"]], [0.0, 1.0])
        self.assertTrue(any("范围外" in n for n in r["notes"]))

    def test_repeats_raise_noise_floor(self):
        self.cli("def", "N", "--kind", "float", "--means", "x")
        self.sweep("N", [(0, 1.0), (0, 1.4), (1, 1.2), (1, 0.9), (2, 1.3)])
        self.assertEqual(self.fit("N", rc=4)["metrics"]["y"]["shape"], "没有作用")

    def test_int_rejects_fractions_and_rounds_pick(self):
        self.cli("def", "S", "--kind", "int", "--means", "档位")
        _, err = self.cli("obs", "S", "1.5", "--metric", "y=1", rc=2)
        self.assertIn("整数", err)
        self.sweep("S", [(1, 10), (3, 30)])
        out, _ = self.cli("pick", "S", "--want", "y=24")
        self.assertIn("≈ 2", out)


class BoolEnumTests(Base):
    def test_bool_effect_and_no_effect(self):
        self.cli("def", "B", "--kind", "bool", "--means", "开流动")
        self.sweep("B", [("off", 1), ("开", 4)])
        self.assertIn("增加 3", self.fit("B")["metrics"]["y"]["shape"])
        self.cli("def", "Z", "--kind", "bool", "--means", "没接线的开关")
        self.sweep("Z", [("false", 2), ("true", 2), ("1", 2.0)])
        self.assertEqual(self.fit("Z", rc=4)["metrics"]["y"]["shape"], "开关没有作用")
        _, err = self.cli("obs", "Z", "maybe", "--metric", "y=1", rc=2)
        self.assertIn("开关值", err)

    def test_bool_needs_both_sides_and_pick_refused(self):
        self.cli("def", "B", "--kind", "bool", "--means", "x")
        self.sweep("B", [("on", 1)])
        self.assertTrue(self.fit("B", rc=4)["problems"])
        _, err = self.cli("pick", "B", "--want", "y=1", rc=2)
        self.assertIn("float/int", err)

    def test_enum_groups_indistinguishable_options(self):
        self.cli("def", "Q", "--kind", "enum", "--options", "Low,Med,High,Ultra", "--means", "质量档")
        self.sweep("Q", [("Low", 2), ("Med", 5), ("High", 5.01), ("High", 4.99)])
        r = self.fit("Q")
        self.assertTrue(any("Med、High" in n for n in r["notes"]))
        self.assertTrue(any("Ultra" in n for n in r["notes"]))
        _, err = self.cli("obs", "Q", "Hgh", "--metric", "y=1", rc=2)
        self.assertIn("不在声明的选项", err)

    def test_enum_all_same_is_problem_and_needs_options(self):
        _, err = self.cli("def", "E", "--kind", "enum", "--means", "x", rc=2)
        self.assertIn("--options", err)
        self.cli("def", "E", "--kind", "enum", "--options", "A,B", "--means", "x")
        self.sweep("E", [("A", 3), ("B", 3)])
        self.assertEqual(self.fit("E", rc=4)["metrics"]["y"]["shape"], "所有选项效果一样")


class MiscTests(Base):
    def test_image_metrics_and_change_from_first(self):
        from PIL import Image
        a, b = self.root / "a.png", self.root / "b.png"
        Image.new("RGB", (64, 64), (40, 40, 40)).save(a)
        Image.new("RGB", (64, 64), (200, 200, 200)).save(b)
        self.cli("def", "L", "--kind", "float", "--means", "亮度")
        self.cli("obs", "L", "0", "--img", str(a))
        self.cli("obs", "L", "1", "--img", str(b))
        p = json.loads((self.root / "PARAMS.json").read_text(encoding="utf-8"))["params"]["L"]
        self.assertEqual(p["obs"][0]["metrics"]["img.changeFromFirst"], 0.0)
        self.assertGreater(p["obs"][1]["metrics"]["img.changeFromFirst"], 100)
        self.assertGreater(p["obs"][1]["metrics"]["img.luma"], p["obs"][0]["metrics"]["img.luma"])

    def test_errors_and_table(self):
        _, err = self.cli("obs", "Nope", "1", "--metric", "y=1", rc=2)
        self.assertIn("先用 def", err)
        self.cli("def", "K", "--kind", "float", "--means", "x")
        _, err = self.cli("obs", "K", "1", rc=2)
        self.assertIn("--metric", err)
        self.cli("obs", "K", "inf", "--metric", "y=1", rc=2)
        self.cli("obs", "K", "1", "--metric", "y=1")
        self.cli("obs", "K", "2", "--metric", "y=2")
        _, err = self.cli("def", "K", "--kind", "bool", "--means", "x", rc=2)
        self.assertIn("不能改成", err)
        out, _ = self.cli("table", "--out", str(self.root / "PARAMS.md"))
        self.assertIn("| K | float |", out)
        self.assertTrue((self.root / "PARAMS.md").is_file())

    def test_every_subcommand_has_help(self):
        for cmd in ("def", "obs", "fit", "pick", "table"):
            with self.subTest(cmd=cmd), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as cm:
                    paramap.main([cmd, "--help"])
                self.assertEqual(cm.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
