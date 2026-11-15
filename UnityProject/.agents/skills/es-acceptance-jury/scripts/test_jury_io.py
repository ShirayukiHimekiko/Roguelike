import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import jury_io


class JuryIOTests(unittest.TestCase):
    def test_exact_unicode_required_text_late_items_and_outer_budget(self):
        value = {'text': '必要意见"\\\n🙂' * 1300,
                 'items': [{'id': n, 'value': '后继'} for n in range(70)],
                 'nextArgs': ['--page', '1'], 'verdict': '条件及未闭必须保全'}
        first = jury_io.emission_page(value, 0, 2048)
        pages = [jury_io.emission_page(value, n, 2048, first['outputSHA256']) for n in range(first['pageCount'])]
        for index, page in enumerate(pages):
            self.assertLessEqual(len(json.dumps(page, ensure_ascii=False, indent=2).encode()), 2048)
            self.assertEqual(page['page'], index)
            self.assertFalse(page['consumptionVerified'])
        joined = ''.join(page['text'] for page in pages)
        self.assertEqual(hashlib.sha256(joined.encode()).hexdigest(), first['outputSHA256'])
        self.assertEqual(json.loads(joined), value)
        self.assertEqual(json.loads(joined)['items'][-1]['id'], 69)
        self.assertGreater(len(json.dumps(pages, ensure_ascii=False).encode()), 2048)
        self.assertIsNone(pages[-1]['nextEmissionPage'])

    def test_emission_rejects_changed_source_and_bad_bounds(self):
        old = jury_io.emission_page({'value': 'old'})
        with self.assertRaisesRegex(ValueError, 'changed'):
            jury_io.emission_page({'value': 'new'}, expect_sha=old['outputSHA256'])
        for page, budget in [(-1, 2048), (0, 200), (True, 2048), (0, True), (200, 2048)]:
            with self.assertRaises(ValueError): jury_io.emission_page({'x': 1}, page, budget)

    def test_actual_reader_cli_emission_preserves_legacy_json(self):
        command = [sys.executable, '-X', 'utf8', '-B', str(Path(__file__).with_name('jury_read.py')),
                   '--section', 'references/coordination.md#wave-gain']
        original = subprocess.run(command, check=True, capture_output=True, text=True, encoding='utf-8')
        first = json.loads(subprocess.run(command + ['--emit-page', '0', '--emit-bytes', '2048'], check=True, capture_output=True, text=True, encoding='utf-8').stdout)
        pages = [first]
        for n in range(1, first['pageCount']):
            pages.append(json.loads(subprocess.run(command + ['--emit-page', str(n), '--emit-bytes', '2048', '--expect-emission', first['outputSHA256']], check=True, capture_output=True, text=True, encoding='utf-8').stdout))
        self.assertEqual(json.loads(''.join(p['text'] for p in pages)), json.loads(original.stdout))

    def test_raw_history_normal_reuse_collision_and_recovery(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); current = root/'current.json'; history = root/'history'
            old, new = b'{"old":true}\r\n', b'{"new":true}\n'
            current.write_bytes(old)
            saved = jury_io.preserve_and_replace(current, new, history)
            self.assertEqual(Path(saved['snapshot']).read_bytes(), old)
            self.assertEqual(current.read_bytes(), new)
            current.write_bytes(old)
            reused = jury_io.preserve_and_replace(current, new, history)
            self.assertEqual(reused['snapshot'], saved['snapshot'])
            restored = jury_io.preserve_and_replace(current, old, history)
            self.assertEqual(current.read_bytes(), old)
            self.assertEqual(Path(restored['snapshot']).read_bytes(), new)
            Path(saved['snapshot']).write_bytes(b'occupied-other')
            with self.assertRaises(jury_io.CandidateSaveError) as raised:
                jury_io.preserve_and_replace(current, new, history)
            self.assertEqual(raised.exception.phase, 'before-commit')
            self.assertEqual(current.read_bytes(), old)
            self.assertEqual(Path(saved['snapshot']).read_bytes(), b'occupied-other')

    def test_precommit_stage_failure_preserves_current(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); current = root/'current'; current.write_bytes(b'old')
            actual = Path.read_bytes
            def read(path):
                return b'bad-stage' if '.candidate-' in path.name else actual(path)
            with patch.object(Path, 'read_bytes', read):
                with self.assertRaises(jury_io.CandidateSaveError) as raised:
                    jury_io.preserve_and_replace(current, b'new', root/'history')
            self.assertEqual(raised.exception.phase, 'before-commit')
            self.assertEqual(current.read_bytes(), b'old')
            self.assertFalse(list(root.glob('*.candidate-*')))

    def test_postcommit_failure_is_unknown_and_never_automatically_retried(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); current = root/'current'; current.write_bytes(b'old')
            actual = Path.read_bytes
            def read(path):
                data = actual(path)
                if path == current and data == b'new': raise OSError('postcommit read unavailable')
                return data
            with patch.object(Path, 'read_bytes', read):
                with self.assertRaises(jury_io.CandidateSaveError) as raised:
                    jury_io.preserve_and_replace(current, b'new', root/'history')
            self.assertEqual(raised.exception.phase, 'commit-outcome-unverified')
            self.assertEqual(current.read_bytes(), b'new')
            self.assertEqual(next((root/'history').glob('*.raw')).read_bytes(), b'old')


if __name__ == '__main__': unittest.main()
