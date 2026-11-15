"""numspec 离线回归：色彩换算、CIEDE2000、色阶计数、SPEC 取样与核对、引擎值、屏幕→世界换算。"""
import contextlib
import io
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numspec  # noqa: E402


def cli(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = numspec.main(list(argv))
    return rc, out.getvalue(), err.getvalue()


def bands_img(path, colors, size=(300, 300), noise=0):
    """从下到上（近→远）等高色带；noise>0 时加稀疏亮点模拟高光。"""
    from PIL import Image, ImageDraw
    im = Image.new("RGB", size)
    d = ImageDraw.Draw(im)
    h = size[1] // len(colors)
    for i, c in enumerate(colors):
        y1 = size[1] - i * h
        d.rectangle([0, y1 - h, size[0], y1], fill=c)
    if noise:
        for k in range(0, size[1], 37):
            d.point((size[0] // 2, k), fill=(255, 255, 255))
    im.save(path)
    return path


class ColorTests(unittest.TestCase):
    def test_de2000_matches_sharma_reference_pairs(self):
        pairs = [((50, 2.6772, -79.7751), (50, 0, -82.7485), 2.0425),
                 ((50, 0, 0), (50, -1, 2), 2.3669),
                 ((50, 2.5, 0), (73, 25, -18), 27.1492),
                 ((60.2574, -34.0099, 36.2677), (60.4626, -34.1751, 39.4387), 1.2644),
                 ((2.0776, 0.0795, -1.1350), (0.9033, -0.0636, -0.5514), 0.9082)]
        for a, b, expected in pairs:
            with self.subTest(a=a, b=b):
                self.assertAlmostEqual(numspec.de2000(a, b), expected, places=3)
                self.assertAlmostEqual(numspec.de2000(b, a), expected, places=3)

    def test_srgb_linear_round_trip_and_lab_white(self):
        for c in (0, 10, 60, 128, 200, 255):
            self.assertEqual(numspec.linear_to_srgb8(numspec.srgb_to_linear(c)), c)
        self.assertAlmostEqual(numspec.srgb_to_linear(128), 0.2158, places=3)
        L, a, b = numspec.rgb_to_lab((255, 255, 255))
        self.assertAlmostEqual(L, 100, places=1)
        self.assertAlmostEqual(a, 0, places=1)

    def test_gap_description_names_direction(self):
        target = numspec.rgb_to_lab((60, 151, 173))
        grey = numspec.rgb_to_lab((135, 148, 140))
        self.assertIn("偏灰", numspec.describe_gap(target, grey))
        self.assertIn("偏暗", numspec.describe_gap(target, numspec.rgb_to_lab((20, 80, 95))))
        self.assertEqual(numspec.describe_gap(target, target), "接近")


class StepsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(self.tmp.name)

    def test_three_distinct_bands_counted_and_highlights_ignored(self):
        p = bands_img(self.d / "a.png", [(120, 210, 200), (30, 150, 200), (20, 60, 140)], noise=1)
        rc, out, _ = cli("--json", "steps", str(p), "--line", "0.5,0.99,0.5,0.01", "--need", "3")
        self.assertEqual(rc, 0)
        data = json.loads(out)
        self.assertEqual(data["count"], 3)
        self.assertLess(data["bands"][0]["lab"][0], 100)

    def test_smooth_gradient_is_not_many_steps_and_need_fails(self):
        from PIL import Image
        im = Image.new("RGB", (100, 300))
        for y in range(300):
            v = 110 + y // 10        # 很缓的渐变：没有可区分的色阶
            for x in range(100):
                im.putpixel((x, y), (40, v, v + 30))
        p = self.d / "g.png"
        im.save(p)
        rc, out, _ = cli("steps", str(p), "--line", "0.5,0.99,0.5,0.01", "--need", "3")
        self.assertEqual(rc, 4)
        self.assertRegex(out, r"沿线 [12] 个")

    def test_line_outside_image_is_an_error(self):
        p = bands_img(self.d / "a.png", [(0, 0, 0)])
        rc, _, err = cli("steps", str(p), "--line", "10,10,5000,10")
        self.assertEqual(rc, 2)
        self.assertIn("图外", err)


class SpecTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(self.tmp.name)
        self.spec = self.d / "SPEC.json"
        self.ref = bands_img(self.d / "ref.png", [(120, 210, 200), (30, 150, 200), (20, 60, 140)])
        self.regions = "近岸=0,0.7,1,0.98;中段=0,0.4,1,0.6;远处=0,0.02,1,0.3"
        rc, _, err = cli("extract", str(self.ref), "--feature", "T1", "--regions", self.regions,
                         "--line", "0.5,0.99,0.5,0.01", "--out", str(self.spec))
        self.assertEqual(rc, 0, err)

    def test_reference_checks_against_itself_as_met(self):
        rc, out, _ = cli("check", str(self.ref), "--spec", str(self.spec))
        self.assertEqual(rc, 0, out)
        self.assertIn("--status T1=达到", out)
        self.assertIn("沿用参照的框", out)

    def test_grey_far_water_fails_and_status_is_pasteable(self):
        cur = bands_img(self.d / "cur.png", [(120, 210, 200), (30, 150, 200), (90, 100, 110)])
        rc, out, _ = cli("check", str(cur), "--spec", str(self.spec), "--regions", self.regions)
        self.assertEqual(rc, 4)
        self.assertIn("[未达] T1 远处", out)
        self.assertIn("[达到] T1 近岸", out)
        self.assertIn("偏灰", out)
        self.assertIn("--status T1=未达", out)

    def test_slightly_off_is_near(self):
        cur = bands_img(self.d / "cur.png", [(125, 205, 200), (40, 150, 195), (25, 70, 145)])
        rc, out, _ = cli("--json", "check", str(cur), "--spec", str(self.spec))
        data = json.loads(out)
        self.assertEqual(data["features"]["T1"]["level"], "接近")
        self.assertEqual(rc, 0)

    def test_missing_steps_downgrades_even_if_colours_match(self):
        two = bands_img(self.d / "two.png", [(120, 210, 200), (30, 150, 200), (30, 150, 200)])
        rc, out, _ = cli("--json", "check", str(two), "--spec", str(self.spec),
                         "--regions", "近岸=0,0.7,1,0.98;中段=0,0.4,1,0.6;远处=0,0.4,1,0.6")
        data = json.loads(out)
        self.assertEqual(data["features"]["T1"]["steps"], {"count": 2, "need": 3})
        self.assertNotEqual(data["features"]["T1"]["level"], "达到")

    def test_second_feature_appends_and_region_names_must_match(self):
        rc, _, _ = cli("extract", str(self.ref), "--feature", "T4", "--regions", "倒影=0.2,0.3,0.8,0.5", "--out", str(self.spec))
        self.assertEqual(rc, 0)
        spec = json.loads(self.spec.read_text(encoding="utf-8"))
        self.assertEqual(sorted(spec["features"]), ["T1", "T4"])
        self.assertEqual(len(spec["regions"]), 4)
        rc, _, err = cli("check", str(self.ref), "--spec", str(self.spec), "--regions", "近岸=0,0.7,1,0.98")
        self.assertEqual(rc, 2)
        self.assertIn("缺少", err)

    def test_engine_values_and_hard_ramp(self):
        ramp = self.d / "ramp.png"
        rc, out, _ = cli("--json", "engine", "--spec", str(self.spec), "--order", "近岸,中段,远处",
                         "--ramp", str(ramp), "--ramp-steps", "3", "--width", "90")
        self.assertEqual(rc, 0)
        data = json.loads(out)
        near = data["values"][0]
        self.assertEqual(near["region"], "近岸")
        self.assertIn("new Color(0.471f", near["unityColor"])       # 120/255，sRGB
        self.assertIn("new Vector4(0.1878f", near["unityVectorLinear"])   # 线性
        from PIL import Image
        with Image.open(ramp) as im:
            cols = [im.getpixel((x, 1)) for x in (5, 45, 85)]
        self.assertEqual(cols[0], (120, 210, 200))
        self.assertEqual(cols[2], (20, 60, 140))
        self.assertEqual(len(set(cols)), 3)

    def test_engine_order_must_exist(self):
        rc, _, err = cli("engine", "--spec", str(self.spec), "--order", "近岸,深海")
        self.assertEqual(rc, 2)
        self.assertIn("深海", err)


class WorldTests(unittest.TestCase):
    def test_screen_percent_to_meters(self):
        rc, out, _ = cli("--json", "world", "--pct", "1.5", "--vfov", "60", "--dist", "20", "--grazing", "30")
        data = json.loads(out)
        perp = 0.015 * 2 * 20 * math.tan(math.radians(30))
        self.assertAlmostEqual(data["perpendicularMeters"], perp, places=3)
        self.assertAlmostEqual(data["alongSurfaceMeters"], perp / 0.5, places=3)

    def test_bad_inputs_rejected(self):
        self.assertEqual(cli("world", "--pct", "1", "--dist", "0")[0], 2)
        self.assertEqual(cli("world", "--pct", "1", "--dist", "5", "--grazing", "0")[0], 2)
        rc, out, _ = cli("world", "--pct", "1", "--dist", "5", "--grazing", "5")
        self.assertIn("非常敏感", out)

    def test_every_subcommand_has_help(self):
        for cmd in ("extract", "check", "steps", "engine", "world"):
            with self.subTest(cmd=cmd), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as cm:
                    numspec.main([cmd, "--help"])
                self.assertEqual(cm.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
