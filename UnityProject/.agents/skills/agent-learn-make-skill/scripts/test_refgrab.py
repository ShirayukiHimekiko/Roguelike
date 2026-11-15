"""refgrab 离线回归：不联网，只测解析、图像处理、命令行合同和退出码。"""
import base64
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import refgrab  # noqa: E402


def make_img(path: Path, size=(1200, 600), color=(30, 140, 140), stripe=None):
    from PIL import Image, ImageDraw
    im = Image.new("RGB", size, color)
    if stripe:
        ImageDraw.Draw(im).rectangle([0, 0, size[0] - 1, size[1] // 2 - 1], fill=stripe)  # 含端点
    im.save(path)
    return path


def run_cli(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = refgrab.main(list(argv))
    return rc, out.getvalue(), err.getvalue()


class ParseTests(unittest.TestCase):
    def test_bing_redirect_is_decoded(self):
        real = "https://genshin.hoyoverse.com/en/"
        enc = base64.urlsafe_b64encode(real.encode()).decode().rstrip("=")
        href = f"https://www.bing.com/ck/a?!&&p=abc&u=a1{enc}&ntb=1"
        self.assertEqual(refgrab.bing_real_url(href), real)

    def test_bing_non_redirect_and_garbage_kept(self):
        self.assertEqual(refgrab.bing_real_url("https://example.com/x"), "https://example.com/x")
        bad = "https://www.bing.com/ck/a?u=a1@@@"
        self.assertEqual(refgrab.bing_real_url(bad), bad)

    def test_subtitles_dedupe_and_timestamps(self):
        vtt = ("WEBVTT\nKind: captions\n\n00:00:01.000 --> 00:00:02.000\n<c>Hello</c> world\n\n"
               "00:00:02.000 --> 00:00:03.000\nHello world\n\n00:00:03.500 --> 00:00:04.000\nfoam &amp; depth\n")
        self.assertEqual(refgrab.subs_to_text(vtt), "[00:00:01] Hello world\n[00:00:03] foam & depth")

    def test_page_parser_skips_scripts_and_resolves_images(self):
        html = ('<html><head><title>T</title><meta property="og:image" content="/og.png"></head><body>'
                '<script>var x=1</script><p>正文一</p><img data-src="a.jpg" alt="A"><a href="/n">下一页</a></body></html>')
        page = refgrab.parse_page(html, "https://site.test/dir/page")
        self.assertEqual(page["title"], "T")
        self.assertIn("正文一", page["text"])
        self.assertNotIn("var x", page["text"])
        self.assertEqual([i["src"] for i in page["images"]], ["https://site.test/og.png", "https://site.test/dir/a.jpg"])
        self.assertEqual(page["links"][0]["href"], "https://site.test/n")

    def test_rank_by_topic_puts_water_first_without_dropping(self):
        items = [{"title": "character art"}, {"title": "Lake at dusk"}, {"title": "海边"}]
        ranked = refgrab.rank_by_topic(items, "water", "水面")
        self.assertEqual(len(ranked), 3)
        self.assertEqual(ranked[-1]["title"], "character art")

    def test_dedupe_ignores_fragment_and_trailing_slash(self):
        items = [{"url": "https://a.test/x/"}, {"url": "https://a.test/x#top"}, {"url": "https://a.test/y"}]
        self.assertEqual(len(refgrab.dedupe(items, "url")), 2)


class ImageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_filter_moves_small_and_duplicate_images(self):
        a = make_img(self.d / "a.png", stripe=(250, 250, 250))
        b = make_img(self.d / "b.png", stripe=(250, 250, 250))  # 与 a 相同
        c = make_img(self.d / "c.png", size=(400, 300))           # 太小
        e = make_img(self.d / "e.png", color=(200, 60, 20))
        from PIL import Image, ImageDraw
        im = Image.open(e)
        ImageDraw.Draw(im).rectangle([0, 0, 600, 600], fill=(10, 10, 10))
        im.save(e)
        kept, notes = refgrab.filter_images(self.d, [a, b, c, e], 800)
        self.assertEqual([p.name for p in kept], ["a.png", "e.png"])
        self.assertTrue((self.d / "_rejected" / "b.png").exists())
        self.assertTrue((self.d / "_rejected" / "c.png").exists())
        self.assertEqual(len(notes), 2)

    def test_measure_grid_points_palette(self):
        p = make_img(self.d / "m.png", size=(100, 100), color=(0, 0, 255), stripe=(255, 0, 0))
        res = refgrab.measure(p, "0.5,0.1;0.5,0.9", None, 2, "2x1")
        self.assertEqual(res["points"][0]["hex"], "#ff0000")
        self.assertEqual(res["points"][1]["hex"], "#0000ff")
        self.assertEqual(res["grid"], [["#ff0000"], ["#0000ff"]])
        self.assertEqual({c["hex"] for c in res["palette"]}, {"#ff0000", "#0000ff"})

    def test_compare_and_sheet_produce_images(self):
        a = make_img(self.d / "a.png", size=(800, 400))
        b = make_img(self.d / "b.png", size=(400, 400))
        out = refgrab.compare([a, b], ["参照", "当前版"], self.d / "cmp.png", 200)
        from PIL import Image
        with Image.open(out) as im:
            self.assertEqual(im.height, 240)          # 200 + 标签栏
            self.assertEqual(im.width, 400 + 8 + 200)
        sheet = refgrab.contact_sheet([a, b], self.d / "s.png", 2, 100)
        self.assertTrue(sheet.exists())


class MeasureAndMotionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_roi_restricts_grid_and_missing_roi_warns(self):
        p = make_img(self.d / "ui.png", size=(100, 100), color=(0, 0, 255), stripe=(255, 0, 0))
        warned = refgrab.measure(p, None, None, 0, "1x1")
        self.assertTrue(warned["warnings"])
        res = refgrab.measure(p, None, None, 0, "1x1", roi="0,0.6,1,1")
        self.assertEqual(res["grid"], [["#0000ff"]])
        self.assertFalse(res["warnings"])

    def test_line_profile_measures_foam_band(self):
        from PIL import Image, ImageDraw
        im = Image.new("RGB", (200, 400), (20, 60, 80))
        ImageDraw.Draw(im).rectangle([0, 200, 199, 207], fill=(250, 250, 250))  # 8px 白带
        p = self.d / "foam.png"
        im.save(p)
        ln = refgrab.line_profile(p, "100,100,100,300")
        self.assertAlmostEqual(ln["bandWidthPx"], 8, delta=1.5)
        self.assertAlmostEqual(ln["bandPctOfHeight"], 2.0, delta=0.4)

    def test_annotated_image_written(self):
        p = make_img(self.d / "a.png")
        res = refgrab.measure(p, "0.5,0.5", "0.1,0.1,0.4,0.4", 0, None, roi="0,0.5,1,1")
        out = refgrab.annotate_measure(p, res, self.d / "a_measure.png")
        self.assertTrue(out.exists())

    def test_motion_recovers_speed_direction_and_period(self):
        """波长 40px 的条纹每帧右移 4px（60px/s @15fps）；定点看到的周期 = 波长/速度 = 10 帧 ≈ 0.67s。"""
        import math
        from PIL import Image
        frames = []
        for t in range(60):
            im = Image.new("RGB", (320, 80))
            px = im.load()
            for x in range(320):
                v = int(120 + 80 * math.sin(2 * math.pi * (x - 4 * t) / 40))
                for y in range(80):
                    px[x, y] = (v, v, v)
            frames.append(im)
        stats, slit = refgrab.analyze_motion(frames, 15, [0, 0, 320, 80], "h0.5")
        self.assertEqual(slit.size, (320, 60))
        self.assertEqual(stats["slitDirection"], "向右")
        self.assertAlmostEqual(stats["slitSpeedPxPerSec"], 60, delta=8)
        self.assertGreater(stats["slitTrackConfidence"], 0.8)
        self.assertAlmostEqual(stats["dominantPeriod"]["periodSec"], 0.667, delta=0.08)

    def test_motion_static_scene_reports_no_motion(self):
        from PIL import Image
        frames = [make_img(Path(self.tmp.name) / f"s{i}.png", size=(160, 60), stripe=(200, 200, 200)) for i in range(20)]
        frames = [Image.open(p).convert("RGB") for p in frames]
        stats, _ = refgrab.analyze_motion(frames, 10, [0, 0, 160, 60], "v0.5")
        self.assertEqual(stats["meanChangePerFrame"], 0)

    def test_motion_vertical_line_direction_and_subpixel_speed(self):
        """亮条每帧向下 3px（10fps → 30px/s）。竖切片线要报“向下”；亚像素插值后速度误差 < 10%。"""
        from PIL import Image, ImageDraw
        frames = []
        for i in range(30):
            im = Image.new("RGB", (100, 200))
            d = ImageDraw.Draw(im)
            for k in range(0, 200, 40):
                y = (k + 3 * i) % 200
                d.rectangle([0, y, 99, y + 8], fill=(255, 255, 255))
            frames.append(im)
        stats, _ = refgrab.analyze_motion(frames, 10, [0, 0, 100, 200], "v0.5")
        self.assertEqual(stats["slitDirection"], "向下")
        self.assertAlmostEqual(stats["slitSpeedPxPerSec"], 30, delta=3)
        up, _ = refgrab.analyze_motion(frames[::-1], 10, [0, 0, 100, 200], "v0.5")
        self.assertEqual(up["slitDirection"], "向上")

    def test_measure_rejects_point_outside_image(self):
        p = make_img(self.d / "small.png", size=(50, 50))
        with self.assertRaises(ValueError):
            refgrab.measure(p, "60,10", None, 0, None)
        rc, _, err = run_cli("measure", str(p), "--points", "60,10", "--no-annot")
        self.assertEqual(rc, 2)
        self.assertIn("图外", err)

    def test_line_profile_flat_line_has_no_band(self):
        p = make_img(self.d / "flat.png", size=(200, 200))
        ln = refgrab.line_profile(p, "0,0.5,1,0.5")
        self.assertTrue(ln["flat"])
        self.assertEqual(ln["bandWidthPx"], 0)


class LookTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def bands(self, name, values, color=lambda v: (v, v, v)):
        """横向色带图，每段一个明度。"""
        from PIL import Image, ImageDraw
        im = Image.new("RGB", (300, 300))
        dr = ImageDraw.Draw(im)
        step = 300 // len(values)
        for i, v in enumerate(values):
            dr.rectangle([0, i * step, 299, (i + 1) * step - 1], fill=color(v))
        p = self.d / name
        im.save(p)
        return p

    def test_stats_count_value_levels_and_saturation(self):
        from PIL import Image
        gray3 = refgrab.look_stats(Image.open(self.bands("g3.png", [30, 128, 230])).convert("RGB"))
        self.assertEqual(gray3["valueLevels"], 3)
        self.assertEqual(gray3["saturationMean"], 0)
        flat = refgrab.look_stats(Image.open(self.bands("g1.png", [120])).convert("RGB"))
        self.assertEqual(flat["valueLevels"], 1)
        blue = refgrab.look_stats(Image.open(self.bands("b.png", [200], color=lambda v: (0, 0, v))).convert("RGB"))
        self.assertGreater(blue["saturationMean"], 90)
        self.assertAlmostEqual(sum(blue["lumaHistogram"]), 100, delta=0.5)

    def test_edge_sharpness_hard_vs_soft(self):
        from PIL import Image, ImageFilter
        hard = Image.open(self.bands("h.png", [20, 230])).convert("RGB")
        soft = hard.filter(ImageFilter.GaussianBlur(12))
        h, s = refgrab.look_stats(hard)["edgeSharpness"], refgrab.look_stats(soft)["edgeSharpness"]
        self.assertGreater(h, 50)
        self.assertLess(s, 30)

    def test_roi_restricts_stats(self):
        p = self.bands("two.png", [30, 230])  # 上暗下亮
        _, stats = refgrab.look_board([p], ["x"], self.d / "b.png", "0,0.6,1,1")
        self.assertEqual(stats[0]["valueLevels"], 1)
        self.assertGreater(stats[0]["valueRange"][0], 200)

    def test_board_has_one_row_per_image_and_cli_prints_diff(self):
        a = self.bands("a.png", [40, 140, 240])
        b = self.bands("b.png", [100, 140])
        out = self.d / "board.png"
        rc, text, _ = run_cli("look", str(a), str(b), "--out", str(out), "--row-height", "120")
        self.assertEqual(rc, 0)
        self.assertIn("差异（当前 相对 参照）", text)
        self.assertIn("明度阶数 -1", text)
        from PIL import Image
        with Image.open(out) as im:
            self.assertEqual(im.height, 2 * (120 + 24) + 8)


class RobustnessTests(unittest.TestCase):
    def test_short_reason_strips_urls_and_names_cause(self):
        self.assertIn("SSL", refgrab.short_reason("x https://raw.githubusercontent.com/a SSLEOFError UNEXPECTED_EOF"))
        self.assertEqual(refgrab.short_reason("urllib=URLError(TimeoutError('timed out'))"), "超时")
        self.assertEqual(refgrab.short_reason("HTTP Error 403: Forbidden"), "HTTP 403")
        self.assertNotIn("http", refgrab.short_reason("weird failure at https://a.test/x?y=1"))

    def test_safe_name_removes_powershell_wildcards(self):
        name = refgrab.safe_name("标题 [BV1nYHN6rE91]")
        self.assertNotIn("[", name)
        self.assertNotIn("]", name)

    def test_gh_file_falls_back_to_raw(self):
        calls = []

        def fake_fetch(url, **kw):
            calls.append(url)
            if "api.github.com" in url:
                raise RuntimeError("SSL handshake")
            return b"ok"
        saved = refgrab.fetch
        refgrab.fetch = fake_fetch
        try:
            data, used = refgrab.gh_file("o/r", "a b.shader", "HEAD")
        finally:
            refgrab.fetch = saved
        self.assertEqual(data, b"ok")
        self.assertIn("api.github.com/repos/o/r/contents/a%20b.shader", calls[0])
        self.assertIn("raw.githubusercontent.com", used)

    def test_youtube_falls_back_to_ytdlp(self):
        saved = (refgrab.vid_youtube, refgrab.vid_youtube_ytdlp)
        refgrab.vid_youtube = lambda q, n: (_ for _ in ()).throw(RuntimeError("URLError"))
        refgrab.vid_youtube_ytdlp = lambda q, n: [{"title": "t", "url": "https://www.youtube.com/watch?v=x"}]
        try:
            self.assertEqual(len(refgrab.vid_youtube_any("q", 3)), 1)
        finally:
            refgrab.vid_youtube, refgrab.vid_youtube_ytdlp = saved

    def test_pdf_uses_pypdf_and_reports_pages_without_text(self):
        try:
            from pypdf import PdfWriter
        except ImportError:
            self.skipTest("pypdf 未安装")
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "blank.pdf"
            w = PdfWriter()
            w.add_blank_page(200, 200)
            w.add_blank_page(200, 200)
            with open(src, "wb") as fh:
                w.write(fh)
            rc, out, _ = run_cli("pdf", str(src), "--out", str(Path(td) / "x.md"))
            self.assertEqual(rc, 0)
            self.assertIn("2 页没有文字层", out)
            self.assertIn("## 第 2 页", (Path(td) / "x.md").read_text(encoding="utf-8"))


@unittest.skipUnless(__import__("os").environ.get("REFGRAB_ONLINE") == "1", "联网冒烟测试：设 REFGRAB_ONLINE=1 才跑")
class OnlineSmokeTests(unittest.TestCase):
    def test_core_sources_return_results(self):
        for name, fn in (("ddg", refgrab.web_ddg), ("bing-img", refgrab.img_bing), ("bilibili", refgrab.vid_bilibili),
                         ("youtube", refgrab.vid_youtube_any)):
            with self.subTest(source=name):
                self.assertTrue(fn("genshin impact water", 3))

    def test_gh_file_reads_readme(self):
        data, _ = refgrab.gh_file("Unity-Technologies/BoatAttack", "README.md", "HEAD")
        self.assertIn(b"Boat", data)


class CliTests(unittest.TestCase):
    def setUp(self):
        self.saved = dict(refgrab.WEB_ENGINES)

    def tearDown(self):
        refgrab.WEB_ENGINES.clear()
        refgrab.WEB_ENGINES.update(self.saved)

    def fake_engines(self, items):
        refgrab.WEB_ENGINES.clear()
        refgrab.WEB_ENGINES.update({"bing": lambda q, n: [dict(i) for i in items]})

    def test_json_flag_works_before_and_after_subcommand(self):
        self.fake_engines([{"title": "t", "url": "https://x.test/"}])
        for argv in (["--json", "web", "q", "--src", "bing"], ["web", "q", "--src", "bing", "--json"]):
            rc, out, _ = run_cli(*argv)
            self.assertEqual(rc, 0, argv)
            self.assertEqual(json.loads(out)["items"][0]["url"], "https://x.test/")

    def test_no_results_exit_3(self):
        self.fake_engines([])
        rc, out, _ = run_cli("web", "q", "--src", "bing")
        self.assertEqual(rc, 3)
        self.assertIn("无结果", out)

    def test_engine_error_is_reported_not_raised(self):
        def boom(q, n):
            raise RuntimeError("blocked")
        refgrab.WEB_ENGINES.clear()
        refgrab.WEB_ENGINES.update({"bing": boom})
        rc, out, _ = run_cli("web", "q", "--src", "bing")
        self.assertEqual(rc, 3)
        self.assertIn("失败", out)

    def test_unexpected_error_exit_2_with_message(self):
        rc, _, err = run_cli("measure", str(Path(tempfile.gettempdir()) / "no-such-image-refgrab.png"))
        self.assertEqual(rc, 2)
        self.assertIn("失败：", err)

    def test_site_filter_is_added_to_query(self):
        seen = []
        refgrab.WEB_ENGINES.clear()
        refgrab.WEB_ENGINES.update({"bing": lambda q, n: seen.append(q) or [{"title": "t", "url": "https://z.test"}]})
        run_cli("web", "原神 水面", "--src", "bing", "--site", "zhuanlan.zhihu.com")
        self.assertEqual(seen, ["原神 水面 site:zhuanlan.zhihu.com"])

    def test_doctor_dependency_table_runs_offline(self):
        saved = (dict(refgrab.WEB_ENGINES), dict(refgrab.IMG_ENGINES), dict(refgrab.VID_ENGINES), refgrab.gh_file)
        for table in (refgrab.WEB_ENGINES, refgrab.IMG_ENGINES, refgrab.VID_ENGINES):
            table.clear()
        refgrab.WEB_ENGINES["fake"] = lambda q, n: [{"url": "u"}]
        refgrab.gh_file = lambda *a: (b"x", "u")
        try:
            rc, out, err = run_cli("doctor")
        finally:
            refgrab.WEB_ENGINES.clear(); refgrab.WEB_ENGINES.update(saved[0])
            refgrab.IMG_ENGINES.update(saved[1]); refgrab.VID_ENGINES.update(saved[2]); refgrab.gh_file = saved[3]
        self.assertEqual(err, "")
        self.assertIn("AGPL", out)
        self.assertIn(rc, (0, 1))

    def test_http_404_fails_without_curl_but_403_tries_curl(self):
        import http.server
        import threading

        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(404 if "missing" in self.path else 403)
                self.end_headers()
                self.wfile.write(b'{"message": "Not Found"}')

            def log_message(self, *a):
                pass
        srv = http.server.HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        calls = []
        saved = refgrab._curl
        refgrab._curl = lambda url, *a, **k: calls.append(url) or (_ for _ in ()).throw(RuntimeError("curl 失败(22)"))
        try:
            with self.assertRaises(RuntimeError) as cm:
                refgrab.fetch(base + "/missing", retries=0)
            self.assertEqual(refgrab.short_reason(cm.exception), "HTTP 404")
            self.assertEqual(calls, [])  # 404 是确定结果，不再白等 curl
            with self.assertRaises(RuntimeError):
                refgrab.fetch(base + "/blocked", retries=0)
            self.assertEqual(calls, [base + "/blocked"])  # 403 可能只拦 Python，交给 curl
        finally:
            refgrab._curl = saved
            srv.shutdown()
        self.assertEqual(refgrab.short_reason("curl: (22) The requested URL returned error: 404"), "HTTP 404")

    def test_search_engines_run_with_fast_fail_defaults(self):
        seen = {}

        def engine(q, n):
            seen["timeout"] = getattr(refgrab._FETCH_DEFAULTS, "timeout", None)
            return [{"url": "u"}]
        items, status = refgrab.run_parallel({"e": engine}, "q", 1)
        self.assertEqual(seen["timeout"], refgrab.SEARCH_TIMEOUT)
        self.assertEqual(status["e"], 1)
        self.assertFalse(hasattr(refgrab._FETCH_DEFAULTS, "timeout"))  # 主线程不受影响

    def test_parallel_downloads_with_same_name_do_not_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            payloads = [bytes([i]) * 500 for i in range(8)]
            saved = refgrab.fetch
            refgrab.fetch = lambda url, **kw: payloads[int(url.rsplit("/", 1)[1])]
            try:
                import concurrent.futures as cf
                with cf.ThreadPoolExecutor(8) as ex:
                    entries = list(ex.map(lambda i: refgrab.download(f"https://x.test/{i}", Path(td), "same"), range(8)))
            finally:
                refgrab.fetch = saved
            self.assertEqual(len({e["file"] for e in entries}), 8)
            self.assertEqual(sorted(Path(td, e["file"]).read_bytes() for e in entries), sorted(payloads))

    def test_generated_images_are_not_counted_as_references(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            for name in ("bing-en_00.jpg", "a.JPEG", "_contact.png", "bing-en_00_measure.png", "x_slit.png", "notes.txt"):
                (d / name).write_bytes(b"x")
            self.assertEqual([p.name for p in refgrab.reference_images(d)], ["a.JPEG", "bing-en_00.jpg"])

    def test_decode_os_falls_back_to_locale(self):
        self.assertEqual(refgrab.decode_os("失败".encode("utf-8")), "失败")
        self.assertIsInstance(refgrab.decode_os("握手失败".encode("gbk")), str)

    def test_guess_ext_checks_webp_fourcc(self):
        self.assertEqual(refgrab.guess_ext("u", b"RIFF\0\0\0\0WEBPVP8 "), ".webp")
        self.assertEqual(refgrab.guess_ext("https://a/x.wav", b"RIFF\0\0\0\0WAVEfmt "), ".wav")

    def test_gh_tree_ext_filter(self):
        saved = refgrab.fetch_json
        refgrab.fetch_json = lambda *a, **k: {"tree": [{"path": p, "type": "blob"} for p in
                                                       ("README.md", "Water.shader", "lib/Noise.HLSL", "Readme Resources/a.jpg")]}
        try:
            rc, out, _ = run_cli("gh-tree", "o/r", "--ext", "shader,.hlsl")
        finally:
            refgrab.fetch_json = saved
        self.assertEqual(out.splitlines()[:2], ["Water.shader", "lib/Noise.HLSL"])
        self.assertIn("2 个文件", out)

    def test_subcommand_help_has_description(self):
        for cmd in ("frames", "sheet", "vdl", "images", "doctor"):
            buf = io.StringIO()
            with self.subTest(cmd=cmd), contextlib.redirect_stdout(buf), self.assertRaises(SystemExit):
                refgrab.main([cmd, "--help"])
            self.assertRegex(buf.getvalue().split("positional arguments")[0].split("options:")[0], r"[一-鿿]{4}")

    def test_every_subcommand_has_help(self):
        for cmd in ("doctor", "web", "images", "refs", "video", "get", "page", "shot", "vdl", "frames", "sheet", "compare",
                    "wiki", "gh", "gh-dl", "gh-tree", "gh-cat", "expand", "research", "subs", "pdf", "measure", "wayback",
                    "motion", "look", "crops", "pick"):
            with self.subTest(cmd=cmd), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as cm:
                    refgrab.main([cmd, "--help"])
                self.assertEqual(cm.exception.code, 0)


class CropsPickTests(unittest.TestCase):
    """crops：各图同名部位并排量色；pick：参照登记可审计、可改判、不重复。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(self.tmp.name)

    def two_tone(self, name, top, bottom, size=(400, 200)):
        return make_img(self.d / name, size=size, color=bottom, stripe=top)

    def test_crops_aligns_named_regions_and_reports_diff(self):
        ref = self.two_tone("ref.png", (20, 60, 160), (40, 200, 200))   # 上深蓝 下浅青
        cur = self.two_tone("cur.png", (90, 90, 90), (40, 200, 200))     # 远水发灰
        out = self.d / "crops.png"
        rc, text, _ = run_cli("crops", str(ref), str(cur), "--labels", "参照|v3", "--out", str(out),
                              "--regions", "远水=0,0,1,0.45;近岸=0,0.55,1,1")
        self.assertEqual(rc, 0, text)
        self.assertTrue(out.is_file())
        self.assertIn("[远水]", text)
        far = text.split("[远水]")[1].split("[近岸]")[0]
        self.assertRegex(far, r"饱和-\d+")           # 远水饱和度掉了
        near = text.split("[近岸]")[1]
        self.assertIn("饱和+0 明度+0", near)          # 近岸一致

    def test_crops_per_image_regions_and_name_mismatch(self):
        a = self.two_tone("a.png", (20, 60, 160), (40, 200, 200))
        b = self.two_tone("b.png", (40, 200, 200), (20, 60, 160))      # 构图上下颠倒
        _, rows = refgrab.crops_board([a, b], ["a", "b"], ["深=0,0,1,0.45", "深=0,0.55,1,1"], self.d / "x.png")
        self.assertEqual(rows[0]["images"][0]["hex"], rows[0]["images"][1]["hex"])
        rc, _, err = run_cli("crops", str(a), str(b), "--out", str(self.d / "y.png"), "--regions", "深=0,0,1,0.4 | 浅=0,0.6,1,1")
        self.assertEqual(rc, 2)
        self.assertIn("不一致", err)
        rc, _, err = run_cli("crops", str(a), str(b), "--out", str(self.d / "y.png"), "--regions", "a=0,0,1,1|b=0,0,1,1|c=0,0,1,1")
        self.assertEqual(rc, 2)
        self.assertIn("3 段", err)

    def test_crops_warns_when_box_lands_on_black_margin(self):
        from PIL import Image, ImageDraw
        sheet = Image.new("RGB", (400, 200), (24, 24, 24))          # 拼图：上面一条黑色标签行
        ImageDraw.Draw(sheet).rectangle([0, 60, 399, 199], fill=(40, 160, 190))
        sheet.save(self.d / "sheet.png")
        cur = self.two_tone("cur.png", (40, 160, 190), (40, 160, 190))
        rc, out, _ = run_cli("crops", str(self.d / "sheet.png"), str(cur), "--out", str(self.d / "c.png"),
                             "--regions", "水=0,0,1,0.2")
        self.assertEqual(rc, 1)
        self.assertIn("框到了拼图边距", out)
        rc, out, _ = run_cli("crops", str(self.d / "sheet.png"), str(cur), "--out", str(self.d / "c.png"),
                             "--regions", "水=0,0.5,1,1")
        self.assertEqual(rc, 0)
        self.assertNotIn("框到了", out)

    def test_hue_delta_wraps(self):
        self.assertEqual(refgrab.hue_delta(350, 10), 20)
        self.assertEqual(refgrab.hue_delta(10, 350), -20)

    def test_look_accepts_one_roi_per_image(self):
        a = self.two_tone("a.png", (30, 30, 30), (230, 230, 230))
        b = self.two_tone("b.png", (230, 230, 230), (30, 30, 30))
        _, stats = refgrab.look_board([a, b], ["a", "b"], self.d / "l.png", "0,0.6,1,1|0,0,1,0.4")
        self.assertEqual([s["roi"] for s in stats], [[0, 120, 400, 200], [0, 0, 400, 80]])
        self.assertGreater(stats[1]["valueRange"][0], 200)

    def pick(self, *argv):
        return run_cli("pick", *argv, "--out", str(self.d / "sel"))

    def test_pick_records_provenance_ids_and_rejections(self):
        src = self.d / "refs"
        src.mkdir()
        g1 = make_img(src / "bing_01.jpg", color=(10, 120, 200))
        g2 = make_img(src / "bing_02.jpg", color=(200, 120, 10))
        bad = make_img(src / "fan.jpg", color=(90, 10, 90))
        refgrab.record(src, {"file": "bing_01.jpg", "url": "https://img.example/1.jpg", "page": "https://site.example/a"})
        rc, text, _ = self.pick(str(g1), str(g2), "--subject", "原神", "--why", "实机，水面占六成")
        self.assertEqual(rc, 0)
        self.assertIn("选入 R1", text)
        self.assertIn("选入 R2", text)
        self.assertIn("找不到出处", text)              # bing_02 没有下载记录
        self.assertTrue((self.d / "sel" / "R1.jpg").is_file())
        rc, text, _ = self.pick(str(bad), "--subject", "原神", "--reject", "--why", "同人图")
        md = (self.d / "sel" / "SELECTED.md").read_text(encoding="utf-8")
        self.assertIn("https://site.example/a", md)
        self.assertIn("## 剔除", md)
        self.assertIn("同人图", md)
        self.assertIn("**未知，需补**", md)
        # 改判：同一张图再 pick 成剔除 → 不重复登记，复制件删除，编号不复用
        self.pick(str(g2), "--subject", "原神", "--reject", "--why", "复核发现是滤镜图")
        db = json.loads((self.d / "sel" / "selected.json").read_text(encoding="utf-8"))
        self.assertEqual(len(db), 3)
        self.assertFalse((self.d / "sel" / "R2.jpg").exists())
        g3 = make_img(src / "bing_03.jpg", color=(0, 200, 120))
        _, text, _ = self.pick(str(g3), "--subject", "鸣潮", "--why", "实机", "--src", "https://x.example/3")
        self.assertIn("选入 R2", text)

    def test_one_sheet_can_be_registered_for_several_subjects(self):
        sheet = make_img(self.d / "sheet.jpg", color=(20, 120, 180))
        for subject in ("原神", "鸣潮", "王国之泪"):
            rc, _, _ = self.pick(str(sheet), "--subject", subject, "--why", "三作拼图中的一格", "--src", "https://x.example/s")
            self.assertEqual(rc, 0)
        db = json.loads((self.d / "sel" / "selected.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(e["subject"] for e in db), ["原神", "王国之泪", "鸣潮"])
        self.assertEqual(len({e["id"] for e in db}), 3)
        rc, text, _ = self.pick(str(sheet), "--subject", "鸣潮", "--reject", "--why", "这一格其实是技能特效")
        self.assertIn("已改判", text)
        db = json.loads((self.d / "sel" / "selected.json").read_text(encoding="utf-8"))
        self.assertEqual(len(db), 3)
        self.assertEqual(sum(e["verdict"] == "selected" for e in db), 2)

    def test_pick_requires_reason_and_rejects_id_collision(self):
        a = make_img(self.d / "a.png")
        b = make_img(self.d / "b.png", color=(1, 2, 3))
        rc, _, err = self.pick(str(a), "--subject", "x", "--why", "  ")
        self.assertEqual(rc, 2)
        self.assertIn("--why", err)
        self.assertEqual(self.pick(str(a), "--subject", "x", "--why", "ok", "--ids", "T1")[0], 0)
        rc, _, err = self.pick(str(b), "--subject", "x", "--why", "ok", "--ids", "T1")
        self.assertEqual(rc, 2)
        self.assertIn("已被别的图占用", err)


class MustTests(unittest.TestCase):
    def test_off_topic_marked_and_sorted_last(self):
        items = [{"title": "和平精英 海岛"}, {"title": "【王国之泪】水上快艇"}, {"title": "Zelda TOTK boat", "author": "x"}]
        got = refgrab.apply_must(items, "王国之泪,Zelda")
        self.assertEqual([i["offTopic"] for i in got], [False, False, True])
        self.assertTrue(got[-1]["title"].startswith("[疑似跑题]"))
        self.assertEqual(refgrab.apply_must([{"title": "a"}], None), [{"title": "a"}])

    def test_video_cli_warns_when_everything_off_topic(self):
        saved = dict(refgrab.VID_ENGINES)
        refgrab.VID_ENGINES["bilibili"] = lambda q, n: [{"title": "和平精英", "url": "https://b/1"}]
        try:
            rc, out, err = run_cli("video", "王国之泪 水面", "--src", "bilibili", "--must", "王国之泪")
        finally:
            refgrab.VID_ENGINES.clear()
            refgrab.VID_ENGINES.update(saved)
        self.assertEqual(rc, 0)
        self.assertIn("[疑似跑题]", out)
        self.assertIn("多半跑题", err)


class RefsOfflineTests(unittest.TestCase):
    """refs 全流程（搜索和下载打桩）：够数即停、过滤小图、疑似跑题标出来、缺参照退出码 4。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(self.tmp.name)
        self.saved = (refgrab.REF_ROUTES, refgrab.download)
        self.addCleanup(self.restore)
        colors = iter([(i * 37 % 255, i * 91 % 255, i * 53 % 255) for i in range(1, 200)])

        def fake_download(url, out, name=None, meta=None, timeout=40, retries=2):
            out.mkdir(parents=True, exist_ok=True)
            size = (300, 200) if "small" in url else (1400, 800)
            import random
            from PIL import Image
            rnd = random.Random(next(colors)[0] * 1000 + len(url))
            small = Image.new("L", (9, 8))
            small.putdata([rnd.randint(0, 255) for _ in range(72)])      # 每张图明暗格局都不同 → 不会被判近重复
            im = small.resize(size, Image.NEAREST).convert("RGB")
            path = out / f"{name}.png"
            im.save(path)
            entry = {"file": path.name, "url": url, **(meta or {})}
            refgrab.record(out, entry)
            return entry
        refgrab.download = fake_download

    def restore(self):
        refgrab.REF_ROUTES, refgrab.download = self.saved

    def test_refs_marks_images_not_mentioning_the_subject(self):
        def route(en, zh, n):
            return [{"url": "https://a/genshin_lake.jpg", "title": "Genshin Impact lake screenshot", "page": ""},
                    {"url": "https://a/2.jpg", "title": "原神 湖面 截图", "page": ""},
                    {"url": "https://a/3.jpg", "title": "PUBG beach", "page": "https://pubg.example"},
                    {"url": "https://a/small.jpg", "title": "Genshin small", "page": ""}]
        refgrab.REF_ROUTES = [("fake", "假来源", route)]
        rc, out, _ = run_cli("refs", "Genshin Impact=原神", "--need", "3", "--out", str(self.d / "refs"))
        self.assertEqual(rc, 0, out)
        self.assertIn("疑似不是原神", out)
        line = [l for l in out.splitlines() if "疑似不是原神" in l][0]
        self.assertIn("fake_", line)
        self.assertEqual(line.count("fake_"), 1)           # 只有 PUBG 那张
        self.assertTrue((self.d / "refs" / "原神" / "_contact.png").is_file())

    def test_refs_short_of_need_exits_4_and_says_not_to_substitute(self):
        refgrab.REF_ROUTES = [("fake", "假来源", lambda en, zh, n: [{"url": "https://a/small.jpg", "title": "鸣潮"}])]
        rc, out, _ = run_cli("refs", "Wuthering Waves=鸣潮", "--need", "2", "--out", str(self.d / "refs"))
        self.assertEqual(rc, 4)
        self.assertIn("不要换成别的对象", out)

    def test_subject_words_and_matching(self):
        w = refgrab.subject_words("Zelda Tears of the Kingdom", "王国之泪")
        self.assertIn("zelda", w)
        self.assertNotIn("the", w)
        self.assertTrue(refgrab.mentions_subject({"title": "【王国之泪】水上快艇"}, w))
        self.assertFalse(refgrab.mentions_subject({"title": "和平精英 海岛"}, w))
        g = refgrab.subject_words("Genshin Impact", "原神")
        self.assertTrue(refgrab.mentions_subject({"url": "https://i.example/genshin-impact-lake.jpg"}, g))


if __name__ == "__main__":
    unittest.main()
