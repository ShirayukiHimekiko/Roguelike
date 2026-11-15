"""Real isolated video controls; never capture the user's screen or run a game."""
import hashlib
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import jury_media as media


class CapturePlanningTests(unittest.TestCase):
    def test_installed_wrapper_without_binary_still_returns_install_recommendations(self):
        with patch('jury_media.shutil.which', return_value=None), \
             patch.dict(os.environ, {'IMAGEIO_FFMPEG_EXE': ''}), \
             patch('jury_media.sys.prefix', 'no-such-conda-prefix'), \
             patch('jury_media.importlib.util.find_spec', return_value=SimpleNamespace(submodule_search_locations=[])), \
             patch('jury_media.importlib.import_module', side_effect=ImportError('unsupported metadata')):
            report = media.doctor()
        self.assertIsNone(report['ffmpeg'])
        self.assertEqual(report['status'], 'failed')
        self.assertIn('unsupported metadata', report['error'])
        self.assertTrue(any(item['source']=='https://ffmpeg.org/download.html' for item in report['recommendations']))

    def test_capture_requires_an_explicit_valid_target_and_preserves_argument_boundaries(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'review space'
            args = media.capture_command('ffmpeg', output, 2, 60, hwnd=12345)
            self.assertEqual(args[args.index('-i')+1], 'hwnd=12345')
            self.assertEqual(args[-1], str(output / 'capture.mkv'))
            self.assertIn('-an', args)
            self.assertFalse(output.exists())
            for kwargs in ({}, {'hwnd': 0}, {'hwnd': 1, 'region': '0,0,40,40'}, {'region': '0,0,0,20'}):
                with self.assertRaises(ValueError):media.capture_command('ffmpeg', output, 2, 60, **kwargs)
            for duration in (0, -1, float('nan'), float('inf')):
                with self.assertRaises(ValueError):media.capture_command('ffmpeg', output, duration, 60, hwnd=1)


class DeadlineTests(unittest.TestCase):
    def test_real_timeout_reaps_child_and_keeps_diagnostics_inputs_and_partial_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            original, partial, log = root/'input.txt', root/'partial.txt', root/'stderr.log'
            original.write_bytes(b'original evidence')
            normal = media.run([sys.executable, '-c', "print('normal return')"], timeout=5)
            self.assertIn('normal return', normal.stdout)
            children, real_popen = [], subprocess.Popen
            def remember(*args, **kwargs):
                child = real_popen(*args, **kwargs)
                children.append(child)
                return child
            code = ("import pathlib,sys,time;pathlib.Path(sys.argv[1]).write_bytes(b'partial evidence');"
                    "print('progress stdout',flush=True);print('progress stderr',file=sys.stderr,flush=True);time.sleep(60)")
            started = time.monotonic()
            with patch('jury_media.subprocess.Popen', side_effect=remember), \
                 self.assertRaisesRegex(ValueError, 'timed out after 2 seconds') as caught:
                media.run([sys.executable, '-c', code, str(partial)], log, timeout=2)
            self.assertLess(time.monotonic()-started, 15)
            self.assertEqual(len(children), 1)
            self.assertIsNotNone(children[0].poll())
            self.assertIn('progress stdout', str(caught.exception))
            self.assertIn('progress stderr', log.read_text(encoding='utf-8'))
            self.assertEqual(original.read_bytes(), b'original evidence')
            self.assertEqual(partial.read_bytes(), b'partial evidence')

    def test_default_is_finite_and_invalid_deadlines_never_launch(self):
        with patch('jury_media._execute', return_value=SimpleNamespace(returncode=0, stdout='', stderr='')) as child:
            media.run(['fake'])
            self.assertEqual(child.call_args.kwargs['timeout'], 600)
            child.reset_mock()
            for deadline in (0, -1, float('nan'), float('inf')):
                with self.subTest(deadline=deadline), self.assertRaises(ValueError):
                    media.run(['fake'], timeout=deadline)
            child.assert_not_called()

    def test_provider_discovery_does_not_execute_and_explicit_environment_is_not_replaced(self):
        with tempfile.TemporaryDirectory() as folder:
            binary = Path(folder)/'binaries'/'local-ffmpeg.exe'
            binary.parent.mkdir()
            binary.write_bytes(b'local executable fixture; never executed')
            metadata = SimpleNamespace(FNAME_PER_PLATFORM={'fixture':binary.name}, get_platform=lambda:'fixture')
            with patch('jury_media.shutil.which', return_value=None), \
                 patch.dict(os.environ, {'IMAGEIO_FFMPEG_EXE': ''}), \
                 patch('jury_media.importlib.util.find_spec', return_value=SimpleNamespace(submodule_search_locations=[folder])), \
                 patch('jury_media.subprocess.Popen', side_effect=AssertionError('Discovery must not launch')), \
                 patch('jury_media.importlib.import_module', return_value=metadata) as load:
                self.assertEqual(media.ffmpeg_path(), str(binary.resolve()))
                load.assert_called_once_with('imageio_ffmpeg._definitions')
                with patch.dict(os.environ, {'IMAGEIO_FFMPEG_EXE':str(binary)}):
                    self.assertEqual(media.ffmpeg_path(), str(binary.resolve()))
                with patch.dict(os.environ, {'IMAGEIO_FFMPEG_EXE':str(binary.parent/'missing.exe')}), \
                     self.assertRaisesRegex(ValueError, 'Configured IMAGEIO_FFMPEG_EXE'):
                    media.ffmpeg_path()

    def test_doctor_timeouts_preserve_phase_context_and_cli_failure(self):
        for fail_at in (0, 1, None):
            calls = []
            def execute(argv, **kwargs):
                self.assertEqual(kwargs['timeout'], 7)
                calls.append(argv)
                if len(calls)-1 == fail_at:
                    raise subprocess.TimeoutExpired(argv, kwargs['timeout'], output=b'version progress', stderr=b'device progress')
                return SimpleNamespace(returncode=0, stdout='ffmpeg test\n' if '-version' in argv else 'gdigrab', stderr='')
            stdout = io.StringIO()
            with self.subTest(fail_at=fail_at), patch('jury_media.ffmpeg_path', return_value='fake'), \
                 patch('jury_media._execute', side_effect=execute), contextlib.redirect_stdout(stdout):
                exit_code = media.main(['--timeout', '7', 'doctor'])
            report = json.loads(stdout.getvalue())
            self.assertEqual(exit_code, 0 if fail_at is None else 2)
            self.assertEqual(report['status'], 'checked' if fail_at is None else 'failed')
            self.assertEqual(report['ffmpeg'], 'fake')
            if fail_at is not None:
                self.assertIn('version progress', report['error'])
                self.assertIn('device progress', report['error'])
                self.assertEqual(report['failedPhase'], 'version-query' if fail_at == 0 else 'device-query')
            if fail_at != 0:
                self.assertEqual(report['version'], 'ffmpeg test')
        with patch('jury_media.ffmpeg_path', return_value='fake'), \
             patch('jury_media._execute', return_value=SimpleNamespace(returncode=0, stdout='ffmpeg\ngdigrab', stderr='')) as child:
            self.assertEqual(media.doctor()['status'], 'checked')
            self.assertEqual([c.kwargs['timeout'] for c in child.call_args_list], [30,30])

    def test_capture_deadlines_failures_and_dry_run_without_recording(self):
        with tempfile.TemporaryDirectory() as folder:
            for override in (None, 9):
                for fail_at in (0, 1, None):
                    out = Path(folder)/f'capture-{override}-{fail_at}'
                    calls = []
                    def execute(argv, **kwargs):
                        index = len(calls)
                        calls.append(argv)
                        self.assertEqual(kwargs['timeout'], override or (30 if index == 0 else 120))
                        if index:
                            Path(argv[-1]).write_bytes(b'partial fixture video')
                        if index == fail_at:
                            raise subprocess.TimeoutExpired(argv, kwargs['timeout'], stderr=b'capture progress')
                        return SimpleNamespace(returncode=0, stdout='gdigrab', stderr='capture diagnostics')
                    with self.subTest(override=override, fail_at=fail_at), \
                         patch('jury_media.sys.platform', 'win32'), patch('jury_media.ffmpeg_path', return_value='fake'), \
                         patch('jury_media._execute', side_effect=execute):
                        if fail_at is None:
                            self.assertEqual(media.capture(out,90,30,hwnd=1,timeout=override)['status'], 'recorded-not-observed')
                        else:
                            with self.assertRaisesRegex(ValueError, 'timed out'):
                                media.capture(out,90,30,hwnd=1,timeout=override)
                            self.assertFalse((out/'capture.json').exists())
                            if fail_at == 0:
                                self.assertFalse(out.exists())
                            else:
                                self.assertEqual((out/'capture.mkv').read_bytes(), b'partial fixture video')
                                self.assertIn('capture progress', (out/'capture.log').read_text(encoding='utf-8'))
            dry = Path(folder)/'dry'
            with patch('jury_media.ffmpeg_path', return_value='fake'), \
                 patch('jury_media._execute', side_effect=AssertionError('dry-run must not launch')):
                self.assertEqual(media.capture(dry,1,30,hwnd=1,dry_run=True)['status'], 'planned-only')
            self.assertFalse(dry.exists())


@unittest.skipUnless(os.name == 'nt', 'Windows owned-job behavior')
class WindowsJobTests(unittest.TestCase):
    @staticmethod
    def active(pid):
        import ctypes as C
        from ctypes import wintypes as W
        kernel = C.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.argtypes = (W.DWORD, W.BOOL, W.DWORD)
        kernel.OpenProcess.restype = W.HANDLE
        kernel.GetExitCodeProcess.argtypes = (W.HANDLE, C.POINTER(W.DWORD))
        kernel.GetExitCodeProcess.restype = W.BOOL
        kernel.CloseHandle.argtypes = (W.HANDLE,)
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            error = C.get_last_error()
            if error == 87:  # Already gone; access-denied must not count as exit.
                return False
            raise C.WinError(error)
        try:
            code = W.DWORD()
            if not kernel.GetExitCodeProcess(handle, C.byref(code)):
                raise C.WinError(C.get_last_error())
            return code.value == 259
        finally:
            kernel.CloseHandle(handle)

    def test_accepted_cmd_timeout_stops_owned_descendant_and_preserves_other_process(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            pidfile, worker, wrapper = root/'worker.pid', root/'worker.py', root/'ffmpeg front.cmd'
            worker.write_text("import os,sys,time\nfrom pathlib import Path\n"
                              + f"Path({str(pidfile)!r}).write_text(str(os.getpid()))\n"
                              + "print('owned progress',flush=True)\nprint('owned stderr',file=sys.stderr,flush=True)\ntime.sleep(5)\n", encoding='utf-8')
            wrapper.write_bytes(('@echo off\r\n' + subprocess.list2cmdline([sys.executable, '-u', str(worker)])
                                 + ' %*\r\n').encode('utf-8'))
            outside = subprocess.Popen([sys.executable, '-c', "import time;time.sleep(3);print('outside preserved')"],
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                selected = media.ffmpeg_path(str(wrapper))
                started = time.monotonic()
                with self.assertRaisesRegex(ValueError, 'timed out') as caught:
                    media.run([selected, '-version'], root/'timeout.log', timeout=1.5)
                self.assertLess(time.monotonic()-started, 4)
                self.assertIn('owned progress', str(caught.exception))
                self.assertIn('owned stderr', (root/'timeout.log').read_text(encoding='utf-8'))
                self.assertFalse(self.active(int(pidfile.read_text())))
                self.assertIsNone(outside.poll())
                output, _ = outside.communicate(timeout=5)
                self.assertIn(b'outside preserved', output)
            finally:
                if outside.poll() is None:
                    outside.kill()
                    outside.communicate(timeout=5)

    def test_frontend_exit_does_not_truncate_late_descendant_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            front = root/'front.py'
            child = "import sys,time;time.sleep(.4);print('late stdout',flush=True);print('late stderr',file=sys.stderr,flush=True)"
            front.write_text("import subprocess,sys\nsubprocess.Popen([sys.executable,'-c',"
                             + repr(child) + "],stdout=sys.stdout,stderr=sys.stderr,creationflags=subprocess.CREATE_NO_WINDOW)\n", encoding='utf-8')
            result = media.run([sys.executable, str(front)], timeout=5)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout.strip(), 'late stdout')
            self.assertEqual(result.stderr.strip(), 'late stderr')

    def test_original_arguments_exit_code_and_inherited_utf8_input(self):
        values = ['space value', '中文', 'a"b', 'a&b', '(value)', '%PATH%', 'tail\\']
        code = "import json,sys;print(json.dumps(sys.argv[1:],ensure_ascii=False));print('错误诊断',file=sys.stderr);sys.exit(7)"
        argv = [sys.executable, '-X', 'utf8', '-c', code, *values]
        result = media._execute(argv, timeout=5)
        self.assertEqual(result.args, argv)
        self.assertEqual(result.returncode, 7)
        self.assertEqual(json.loads(result.stdout), values)
        self.assertIn('错误诊断', result.stderr)
        # Feed the run API through its original inherited-stdin contract.
        caller = ("import sys;sys.path.insert(0," + repr(str(Path(media.__file__).parent)) + ");import jury_media;"
                  "r=jury_media.run([sys.executable,'-X','utf8','-c','import sys;sys.stdout.write(sys.stdin.read())'],timeout=5);"
                  "sys.stdout.write(r.stdout)")
        payload = '原始输入 空格 & %PATH%\n第二行\n'
        result = subprocess.run([sys.executable, '-X', 'utf8', '-B', '-c', caller], input=payload,
                                capture_output=True, encoding='utf-8', timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, payload)

    def test_job_setup_failure_never_launches_target(self):
        with tempfile.TemporaryDirectory() as folder:
            marker = Path(folder)/'must-not-exist.txt'
            argv = [sys.executable, '-c', "from pathlib import Path;Path(" + repr(str(marker)) + ").write_text('launched')"]
            # Isolated API-failure injection, not a claim of actual host denial.
            deny = ("import ctypes\ndef denied(*args,**kwargs):raise OSError('隔离受拒')\nctypes.WinDLL=denied\n")
            with patch('jury_media._WINDOWS_LAUNCHER', deny + media._WINDOWS_LAUNCHER), \
                 self.assertRaisesRegex(ValueError, 'Unable to establish owned media job') as caught:
                media.run(argv, timeout=5)
            self.assertIn('隔离受拒', str(caught.exception))
            self.assertFalse(marker.exists())

    def test_job_query_failure_fails_and_stops_created_descendant(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            pidfile, worker, front = root/'child.pid', root/'worker.py', root/'front.py'
            worker.write_text("import os,time\nfrom pathlib import Path\n"
                              + f"Path({str(pidfile)!r}).write_text(str(os.getpid()))\ntime.sleep(5)\n", encoding='utf-8')
            front.write_text("import subprocess,sys,time\nfrom pathlib import Path\n"
                             + f"p=Path({str(pidfile)!r})\n"
                             + f"subprocess.Popen([sys.executable,{str(worker)!r}],stdout=sys.stdout,stderr=sys.stderr,creationflags=subprocess.CREATE_NO_WINDOW)\n"
                             + "end=time.monotonic()+2\nwhile not p.exists() and time.monotonic()<end:time.sleep(.01)\n", encoding='utf-8')
            # Keep real create/assign behavior; inject only QueryInformation failure.
            deny = """import ctypes
original_factory=ctypes.WinDLL
def denied_query(*args):
    ctypes.set_last_error(5)
    return False
class QueryDenied:
    def __init__(self,real):
        self.real=real
        self.QueryInformationJobObject=denied_query
    def __getattr__(self,name):return getattr(self.real,name)
ctypes.WinDLL=lambda *args,**kwargs:QueryDenied(original_factory(*args,**kwargs))
"""
            with patch('jury_media._WINDOWS_LAUNCHER', deny + media._WINDOWS_LAUNCHER), \
                 self.assertRaisesRegex(ValueError, 'Unable to inspect owned media job'):
                media.run([sys.executable, str(front)], timeout=5)
            self.assertFalse(self.active(int(pidfile.read_text())))


class RealVideoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from PIL import Image, ImageDraw
            cls.exe = media.ffmpeg_path()
        except (ImportError, OSError, ValueError) as exc:
            raise unittest.SkipTest('Optional media dependencies unavailable: ' + str(exc))
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        images = cls.root / 'images'
        images.mkdir()
        for index in range(12):
            image = Image.new('RGB', (160, 90), '#203030')
            draw = ImageDraw.Draw(image)
            draw.rectangle((index*4, 30, index*4+15, 50), fill='#ee6040')
            if index == 5:draw.rectangle((0, 0, 159, 12), fill='white')
            image.save(images / f'frame-{index:03d}.png')
        cls.source = cls.root / 'test media 空间.mkv'
        media.run([cls.exe, '-hide_banner', '-nostdin', '-n', '-framerate', '10',
                   '-i', str(images/'frame-%03d.png'), '-c:v', 'ffv1', str(cls.source)])
        cls.source_hash = hashlib.sha256(cls.source.read_bytes()).hexdigest()

    def test_each_decode_timeout_retains_original_logs_and_partial_without_success(self):
        real_execute = media._execute
        for override in (None, 12):
            for fail_at in (0, 1):
                out = self.root/f'timeout-{override}-{fail_at}'
                calls = []
                def execute(argv, **kwargs):
                    self.assertEqual(kwargs['timeout'], override or 600)
                    self.assertEqual(argv[argv.index('-t')+1], '1.1')
                    index = len(calls)
                    calls.append(argv)
                    if index == fail_at:
                        if index:
                            (out/'frames/frame-000001.png').write_bytes(b'partial frame')
                        raise subprocess.TimeoutExpired(argv, kwargs['timeout'], stderr=b'decode progress')
                    return real_execute(argv, **kwargs)
                with self.subTest(override=override, fail_at=fail_at), \
                     patch('jury_media._execute', side_effect=execute), self.assertRaisesRegex(ValueError,'timed out'):
                    media.sample(self.source,out,1,1.1,executable=self.exe,timeout=override)
                log = out/('source-frames.log' if fail_at == 0 else 'extract.log')
                self.assertIn('decode progress', log.read_text(encoding='utf-8'))
                self.assertFalse((out/'frames.json').exists())
                if fail_at:
                    self.assertEqual((out/'frames/frame-000001.png').read_bytes(), b'partial frame')
                self.assertEqual(media.file_sha256(self.source), self.source_hash)

    def test_native_frames_keep_short_event_timestamps_originals_and_visible_sheets(self):
        from PIL import Image
        out = self.root / 'all frames'
        result = media.sample(self.source, out, .2, .9, executable=self.exe)
        record = json.loads((out/'frames.json').read_text(encoding='utf-8'))
        self.assertEqual(result['frames'], 7)
        for frame, expected in zip(record['frames'], [.2,.3,.4,.5,.6,.7,.8]):
            self.assertAlmostEqual(frame['timeSeconds'], expected, places=5)
            self.assertEqual(frame['size'], [160,90])
        with Image.open(out/record['frames'][3]['file']) as event:
            self.assertGreater(sum(event.convert('RGB').getpixel((80,5))), 700)
        self.assertTrue((out/record['contactSheets'][0]).is_file())
        self.assertFalse(record['continuousObserved'])
        self.assertFalse(record['audioObserved'])
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(), self.source_hash)

    def test_coarse_sampling_and_roi_preserve_actual_time_and_full_size(self):
        out = self.root / 'coarse'
        media.sample(self.source, out, .2, .9, every=.3, roi='0,0,160,15', executable=self.exe)
        record = json.loads((out/'frames.json').read_text(encoding='utf-8'))
        self.assertEqual(len(record['frames']), 3)
        for frame, expected in zip(record['frames'], [.2,.5,.8]):
            self.assertAlmostEqual(frame['timeSeconds'], expected, places=5)
            self.assertEqual(frame['size'], [160,90])
        self.assertGreater(record['frames'][1]['meanAbsoluteRgbDifference'], 100)
        self.assertEqual(record['roi'], [0,0,160,15])

    def test_variable_frame_times_are_read_from_video_not_frame_number(self):
        listing = self.root / 'vfr.txt'
        lines = []
        for index, duration in enumerate([.04,.12,.08,.20]):
            lines += [f"file 'images/frame-{index:03d}.png'", f'duration {duration}']
        lines.append("file 'images/frame-004.png'")
        listing.write_text('\n'.join(lines)+'\n', encoding='utf-8')
        source = self.root / 'variable.mkv'
        media.run([self.exe, '-hide_banner', '-nostdin', '-n', '-f', 'concat', '-safe', '0',
                   '-i', str(listing), '-vsync', 'vfr', '-c:v', 'ffv1', str(source)])
        out = self.root / 'vfr-output'
        media.sample(source, out, 0, 1, executable=self.exe)
        frames = json.loads((out/'frames.json').read_text(encoding='utf-8'))['frames']
        self.assertEqual(len(frames), 5)
        for frame, expected in zip(frames, [0,.04,.16,.24,.44]):
            self.assertAlmostEqual(frame['timeSeconds'], expected, places=5)

    def test_changing_resolution_is_rejected_even_for_an_interval_after_the_change(self):
        from PIL import Image
        for name, size in [('small',(160,90)),('large',(320,180))]:
            image = self.root / (name+'.png')
            Image.new('RGB',size,'#335577').save(image)
            media.run([self.exe,'-hide_banner','-nostdin','-n','-loop','1','-framerate','10',
                       '-i',str(image),'-frames:v','4','-c:v','libx264','-preset','ultrafast',
                       '-g','1','-pix_fmt','yuv420p','-f','mpegts',str(self.root/(name+'.ts'))])
        listing = self.root/'changing.txt'
        listing.write_text("file 'small.ts'\nfile 'large.ts'\n",encoding='utf-8')
        source = self.root/'changing.ts'
        media.run([self.exe,'-hide_banner','-nostdin','-n','-f','concat','-safe','0',
                   '-i',str(listing),'-c','copy',str(source)])
        source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        for name,start in [('all',0),('late',.4)]:
            out = self.root/('changing-'+name)
            with self.assertRaisesRegex(ValueError,'changing frame size/format'):
                media.sample(source,out,start,.8,executable=self.exe)
            self.assertTrue((out/'source-frames.log').is_file())
            self.assertFalse((out/'frames.json').exists())
            self.assertEqual(list((out/'frames').glob('*.png')),[])
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),source_hash)

    def test_existing_output_and_invalid_interval_do_not_overwrite_source_or_evidence(self):
        out = self.root / 'existing'
        out.mkdir()
        marker = out / 'keep.txt'
        marker.write_text('old evidence', encoding='utf-8')
        with self.assertRaises(FileExistsError):media.sample(self.source, out, 0, 1, executable=self.exe)
        self.assertEqual(marker.read_text(encoding='utf-8'), 'old evidence')
        invalid = self.root / 'invalid'
        with self.assertRaises(ValueError):media.sample(self.source, invalid, 1, 1, executable=self.exe)
        self.assertFalse(invalid.exists())
        dry = self.root / 'capture-dry'
        result = media.capture(dry, 1, 30, hwnd=12345, executable=self.exe, dry_run=True)
        self.assertEqual(result['status'], 'planned-only')
        self.assertFalse(dry.exists())
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(), self.source_hash)

    def test_cli_reuses_complete_evidence_without_decoding_or_new_outputs(self):
        out = self.root / 'reusable'
        first = media.sample(self.source, out, .2, .9, executable=self.exe, reuse=True)
        self.assertFalse(first['reused'])
        before = {p.relative_to(out).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns)
                  for p in out.rglob('*') if p.is_file()}
        stdout = io.StringIO()
        with patch('jury_media.run', side_effect=AssertionError('Cache hit must not decode')), \
             contextlib.redirect_stdout(stdout):
            code = media.main(['--ffmpeg', self.exe, 'sample', str(self.source),
                               '--output', str(out), '--start', '.2', '--end', '.9',
                               '--every', '0', '--reuse'])
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(stdout.getvalue())['reused'])
        after = {p.relative_to(out).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns)
                 for p in out.rglob('*') if p.is_file()}
        self.assertEqual(after, before)
        self.assertFalse(json.loads((out / 'frames.json').read_text(encoding='utf-8'))['continuousObserved'])
        missing = self.root / 'missing-explicit-sampling'
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as failure:
            media.main(['sample', str(self.source), '--output', str(missing),
                        '--start', '0', '--end', '1'])
        self.assertEqual(failure.exception.code, 2)
        self.assertFalse(missing.exists())

    def test_reuse_rejects_stale_inputs_even_when_source_size_and_mtime_match(self):
        source = self.root / 'mutable-source.mkv'
        source.write_bytes(self.source.read_bytes())
        out = self.root / 'stale-inputs'
        media.sample(source, out, .2, .9, executable=self.exe)
        before = {p.relative_to(out).as_posix(): p.read_bytes()
                  for p in out.rglob('*') if p.is_file()}
        with self.assertRaises(ValueError):
            media.sample(source, out, .2, .9, every=.3, executable=self.exe, reuse=True)
        tool = self.root / 'different-decoder.exe'
        tool.write_bytes(b'changed decoder identity; never executed')
        with self.assertRaises(ValueError):
            media.sample(source, out, .2, .9, executable=str(tool), reuse=True)
        state = source.stat()
        content = source.read_bytes()
        source.write_bytes(content[:-1] + bytes([content[-1] ^ 1]))
        os.utime(source, ns=(state.st_atime_ns, state.st_mtime_ns))
        with self.assertRaises(ValueError):
            media.sample(source, out, .2, .9, executable=self.exe, reuse=True)
        self.assertEqual({p.relative_to(out).as_posix(): p.read_bytes()
                          for p in out.rglob('*') if p.is_file()}, before)

    def test_reuse_rejects_missing_modified_or_untrusted_artifacts_without_repair(self):
        out = self.root / 'damaged-output'
        media.sample(self.source, out, .2, .9, executable=self.exe)
        manifest = out / 'frames.json'
        original = manifest.read_bytes()
        record = json.loads(original)
        frame = out / record['frames'][0]['file']
        content = frame.read_bytes()
        frame.write_bytes(content[:-1] + bytes([content[-1] ^ 1]))
        damaged = frame.read_bytes()
        with self.assertRaises(ValueError):
            media.sample(self.source, out, .2, .9, executable=self.exe, reuse=True)
        self.assertEqual(frame.read_bytes(), damaged)
        frame.unlink()
        with self.assertRaises(ValueError):
            media.sample(self.source, out, .2, .9, executable=self.exe, reuse=True)
        self.assertFalse(frame.exists())
        frame.write_bytes(content)
        extra = out / 'unrelated.txt'
        extra.write_text('Do not delete or adopt this unrelated content', encoding='utf-8')
        with self.assertRaises(ValueError):
            media.sample(self.source, out, .2, .9, executable=self.exe, reuse=True)
        self.assertTrue(extra.exists())
        extra.unlink()
        record['frames'][0]['file'] = '../outside.png'
        record['manifestSha256'] = media.manifest_sha256(record)
        manifest.write_text(json.dumps(record), encoding='utf-8')
        with self.assertRaises(ValueError):
            media.sample(self.source, out, .2, .9, executable=self.exe, reuse=True)
        record = json.loads(original)
        record.pop('cacheSignature')
        record['manifestSha256'] = media.manifest_sha256(record)
        manifest.write_text(json.dumps(record), encoding='utf-8')
        with self.assertRaises(ValueError):
            media.sample(self.source, out, .2, .9, executable=self.exe, reuse=True)
        self.assertNotEqual(manifest.read_bytes(), original)
        manifest.write_text('[]', encoding='utf-8')
        with self.assertRaises(ValueError):
            media.sample(self.source, out, .2, .9, executable=self.exe, reuse=True)
        self.assertEqual(manifest.read_text(encoding='utf-8'), '[]')

    def test_source_change_during_extraction_never_publishes_reusable_success(self):
        for preserve_metadata in (False, True):
            with self.subTest(preserve_metadata=preserve_metadata):
                source = self.root / f'changing-source-{preserve_metadata}.mkv'
                source.write_bytes(self.source.read_bytes())
                out = self.root / f'changing-during-extract-{preserve_metadata}'
                real_run = media.run
                calls = []
                def run_then_change(argv, *args, **kwargs):
                    result = real_run(argv, *args, **kwargs)
                    calls.append(argv)
                    if len(calls) == 2:
                        state = source.stat()
                        content = source.read_bytes()
                        source.write_bytes(content[:-1] + bytes([content[-1] ^ 1])
                                           if preserve_metadata else content + b'changed while extracting')
                        if preserve_metadata:
                            os.utime(source, ns=(state.st_atime_ns, state.st_mtime_ns))
                    return result
                with patch('jury_media.run', side_effect=run_then_change), self.assertRaises(ValueError):
                    media.sample(source, out, .2, .9, executable=self.exe)
                self.assertTrue((out / 'extract.log').exists())
                self.assertFalse((out / 'frames.json').exists())

    def test_source_change_during_reuse_preserving_metadata_is_refused(self):
        source = self.root / 'changing-during-reuse.mkv'
        source.write_bytes(self.source.read_bytes())
        out = self.root / 'reuse-tail-change'
        media.sample(source, out, .2, .9, executable=self.exe)
        before = {p.relative_to(out).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns)
                  for p in out.rglob('*') if p.is_file()}
        real_sha = media.file_sha256
        changed = []
        def hash_then_change(path):
            digest = real_sha(path)
            if Path(path) == out / 'review.html':
                state = source.stat()
                content = source.read_bytes()
                source.write_bytes(content[:-1] + bytes([content[-1] ^ 1]))
                os.utime(source, ns=(state.st_atime_ns, state.st_mtime_ns))
                changed.append(True)
            return digest
        with patch('jury_media.file_sha256', side_effect=hash_then_change), \
             patch('jury_media.run', side_effect=AssertionError('Reuse must not decode')), \
             self.assertRaises(ValueError):
            media.sample(source, out, .2, .9, executable=self.exe, reuse=True)
        self.assertEqual(changed, [True])
        self.assertEqual({p.relative_to(out).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns)
                          for p in out.rglob('*') if p.is_file()}, before)

    def test_frame_numbers_beyond_six_digits_keep_pts_order_and_reuse(self):
        out = self.root / 'wide-frame-numbers'
        real_run = media.run
        calls = []
        def run_then_rename(argv, *args, **kwargs):
            result = real_run(argv, *args, **kwargs)
            calls.append(argv)
            if len(calls) == 2:
                (out / 'frames/frame-000002.png').rename(out / 'frames/frame-999999.png')
                (out / 'frames/frame-000003.png').rename(out / 'frames/frame-1000000.png')
            return result
        with patch('jury_media.run', side_effect=run_then_rename):
            media.sample(self.source, out, .2, .9, every=.3, executable=self.exe)
        record = json.loads((out / 'frames.json').read_text(encoding='utf-8'))
        self.assertEqual([entry['file'] for entry in record['frames']],
                         ['frames/frame-000001.png', 'frames/frame-999999.png',
                          'frames/frame-1000000.png'])
        for frame, expected in zip(record['frames'], [.2, .5, .8]):
            self.assertAlmostEqual(frame['timeSeconds'], expected, places=5)
        with patch('jury_media.run', side_effect=AssertionError('Reuse must not decode')):
            self.assertTrue(media.sample(self.source, out, .2, .9, every=.3,
                                         executable=self.exe, reuse=True)['reused'])

    def test_readthrough_source_is_supported_but_linked_output_is_refused(self):
        holder = self.root / 'source-holder'
        holder.mkdir()
        source = holder / 'video.mkv'
        source.write_bytes(self.source.read_bytes())
        def link_directory(alias, target):
            if os.name == 'nt':
                result = subprocess.run(['cmd.exe', '/c', 'mklink', '/J', str(alias), str(target)],
                                        capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
                if result.returncode:
                    self.skipTest('Directory junction creation unavailable')
                self.addCleanup(alias.rmdir)
            else:
                alias.symlink_to(target, target_is_directory=True)
                self.addCleanup(alias.unlink)
        source_alias = self.root / 'source-alias'
        link_directory(source_alias, holder)
        out = self.root / 'link-controls'
        media.sample(source_alias / 'video.mkv', out, .2, .9, executable=self.exe)
        self.assertTrue(media.sample(source, out, .2, .9, executable=self.exe, reuse=True)['reused'])
        output_alias = self.root / 'output-alias'
        link_directory(output_alias, out)
        with self.assertRaises(ValueError):
            media.sample(source, output_alias, .2, .9, executable=self.exe, reuse=True)


if __name__ == '__main__':
    unittest.main()
