"""selfcheck 回归：离线全流程能跑通；演示目录不空时拒绝覆盖；坏掉的步骤会被报出来。"""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import selfcheck  # noqa: E402


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = selfcheck.main(list(argv))
    return rc, out.getvalue(), err.getvalue()


class SelfcheckTests(unittest.TestCase):
    def test_offline_flow_passes_and_keeps_demo(self):
        with tempfile.TemporaryDirectory() as d:
            demo = Path(d) / "demo"
            rc, out, _ = run("--json", "--keep", str(demo))
            data = json.loads(out)
            self.assertEqual(rc, 0, [s for s in data["steps"] if not s["ok"]])
            self.assertTrue(data["passed"])
            self.assertTrue((demo / "WAVES.json").is_file())
            self.assertTrue((demo / "refs" / "selected" / "SELECTED.md").is_file())
            self.assertTrue((demo / "waves" / "wave2_crops.png").is_file())

    def test_keep_refuses_non_empty_directory(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "x.txt").write_text("x", encoding="utf-8")
            rc, _, err = run("--keep", d)
            self.assertEqual(rc, 2)
            self.assertIn("不是空的", err)

    def test_broken_step_is_reported_not_hidden(self):
        saved = selfcheck.WAVELOG
        with tempfile.TemporaryDirectory() as d:
            broken = Path(d) / "wavelog.py"
            broken.write_text("import sys\nsys.exit(2)\n", encoding="utf-8")
            selfcheck.WAVELOG = broken
            try:
                rc, out, _ = run()
            finally:
                selfcheck.WAVELOG = saved
        self.assertEqual(rc, 1)
        self.assertIn("| wavelog baseline | 失败 |", out)
        self.assertIn("步失败", out)


if __name__ == "__main__":
    unittest.main()
