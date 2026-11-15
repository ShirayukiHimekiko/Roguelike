"""Consumer/negative controls for bounded diagnostics and command-local reuse."""
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import jury_candidates as candidates
import jury_read as reader
import jury_review_roles as roles
from test_current_workflow import work_task
import jury_session as session
import validate_package as package

ROOT = Path(__file__).resolve().parents[1]


class OptimizationTests(unittest.TestCase):
    def observation(self):
        return dict(currentScope=dict(kind='task', id='optimization'),reviewStage='review',task=work_task('optimization'),
                    availableModels=[dict(modelId='gpt-6.1-sol', efforts=['xhigh'])],
                    roles=['architecture'])

    def save(self, root, record):
        path = root / 'plan.json'
        path.write_bytes(json.dumps(record, ensure_ascii=False).encode('utf-8'))
        return path

    def small_plan(self, root):
        (root / 'rules.md').write_bytes(('## One\n' + 'a' * 70 + '\n## Two\n' +
                                        'b' * 70 + '\n## Three\n' + 'c' * 70 + '\n').encode('utf-8'))
        return self.save(root, dict(schemaVersion=3, status='planned', autoExecute=False,
                                   roles=['progress'], readSelectors=['rules.md#One', 'rules.md#Two', 'rules.md#Three']))

    def test_real_plan_pages_preserve_every_section_and_role_selection(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.save(Path(folder), candidates.plan(ROOT, role='progress', blocks=['rules'], review_stage='review'))
            first = reader.read_plan_page(path, ROOT)
            records, current = [], first
            while True:
                records.extend(current['sections'])
                if current['nextArgs'] is None:
                    break
                current = reader.read_plan_page(path, ROOT, role='progress', page=current['page'] + 1,
                                                page_bytes=first['pageBodyTargetUtf8'], expect_snapshot=first['snapshot'])
            expected = reader.expanded_sections(candidates.plan(ROOT, role='progress', blocks=['rules'], review_stage='review')['readSelectors'], ROOT)
            self.assertGreater(len(expected), 32)
            self.assertEqual(records, expected)
            self.assertFalse(first['allPagesConsumptionVerified'])
            prepared = roles.prepare({**self.observation(), 'roles': ['architecture', 'progress']}, ROOT)
            path = self.save(Path(folder), prepared)
            with self.assertRaisesRegex(ValueError, 'select --role'):
                reader.read_plan_page(path, ROOT)
            own = reader.read_plan_page(path, ROOT, role='progress')
            self.assertEqual(own['selectedRole'], 'progress')

    def test_cross_page_content_and_page_parameters_cannot_reuse_old_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = self.small_plan(root)
            first = reader.read_plan_page(path, root, page_bytes=100)
            self.assertIsNotNone(first['nextArgs'])
            for options in [dict(page_bytes=200), dict(role='architecture', page_bytes=100)]:
                with self.assertRaises(ValueError):
                    reader.read_plan_page(path, root, page=1, expect_snapshot=first['snapshot'], **options)
            target = root / 'rules.md'
            before = target.stat()
            target.write_bytes(target.read_bytes().replace(b'a' * 70, b'z' * 70))
            os.utime(target, ns=(before.st_atime_ns, before.st_mtime_ns))
            with self.assertRaisesRegex(ValueError, 'snapshot-changed'):
                reader.read_plan_page(path, root, page=1, page_bytes=100, expect_snapshot=first['snapshot'])
            self.assertNotEqual(reader.read_plan_page(path, root, page_bytes=100)['snapshot'], first['snapshot'])
            with self.assertRaisesRegex(ValueError, 'needs'):
                reader.read_plan_page(path, root, page_bytes=10)

    def test_plan_rejects_held_bad_json_missing_empty_cycle_and_escape(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = self.small_plan(root)
            valid = path.read_bytes()
            for raw in [b'{"schemaVersion":3,"schemaVersion":3}', b'{"x":NaN}', b'[]', b'\xff',
                        json.dumps(dict(schemaVersion=3, autoExecute=False, status='held', dispatch=[])).encode()]:
                path.write_bytes(raw)
                with self.assertRaises((ValueError, UnicodeError)):
                    reader.read_plan_page(path, root)
            path.write_bytes(valid)
            original = (root / 'rules.md').read_bytes()
            for raw in [b'## One\n<!-- empty -->\n## Two\nbody\n## Three\nbody',
                        b'## One\nbody\n<!-- jury-read-continue: rules.md#One -->\n',
                        b'## One\nbody\n<!-- jury-read-continue: ../outside.md#Two -->\n']:
                (root / 'rules.md').write_bytes(raw)
                with self.assertRaises(ValueError):
                    reader.read_plan_page(path, root)
            (root / 'rules.md').unlink()
            with self.assertRaises(OSError):
                reader.read_plan_page(path, root)
            (root / 'rules.md').write_bytes(original)
            self.assertEqual(reader.read_plan_page(path, root)['status'], 'read-page')

    def test_measure_and_returned_record_mutation_do_not_poison_cached_body(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = self.small_plan(root)
            with reader.reading_session(root):
                measured = reader.read_plan_page(path, root, measure=True)
                self.assertNotIn('content', measured['sections'][0])
                record = reader.read_section('rules.md#One', root)
                record.pop('content')
                record['continuationSelectors'].append('bad.md')
                current = reader.read_section('rules.md#One', root)
                self.assertIn('content', current)
                self.assertEqual(current['continuationSelectors'], [])

    def test_core_and_index_changes_at_return_refuse_mixed_generation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'es-acceptance-jury'
            shutil.copytree(ROOT, root)
            original_read = reader.read_section
            def changing_core(selector, package_root=reader.ROOT):
                result = original_read(selector, package_root)
                if selector == 'SKILL.md':
                    (root / 'SKILL.md').write_bytes((root / 'SKILL.md').read_bytes() + b'\nchanged\n')
                return result
            with mock.patch.object(reader, 'read_section', side_effect=changing_core):
                with self.assertRaisesRegex(ValueError, 'input-changed'):
                    reader.round_context(root)
            self.assertIn('changed', reader.round_context(root))
            original_verify = reader._ReadSession.verify
            index = root / candidates.INDEX
            raw = index.read_bytes()
            def changing_index(state):
                index.write_bytes(raw + b' ')
                return original_verify(state)
            with mock.patch.object(reader._ReadSession, 'verify', changing_index):
                with self.assertRaisesRegex(ValueError, 'input-changed'):
                    candidates.plan(root, role='progress', review_stage='review')
            index.write_bytes(raw)
            self.assertEqual(candidates.plan(root, role='progress', review_stage='review')['status'], 'planned')
            held = roles.prepare({**self.observation(), 'paused': True}, root / 'missing')
            self.assertEqual(held['status'], 'held')

    def test_reader_actual_cli_consumes_plan_and_next_args(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.save(Path(folder), candidates.plan(ROOT, role='progress', blocks=['rules'], review_stage='review'))
            argv = [sys.executable, '-X', 'utf8', '-B', str(ROOT / 'scripts/jury_read.py')]
            first = subprocess.run(argv + ['--from-plan', str(path)], capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(first.returncode, 0, first.stdout)
            record = json.loads(first.stdout)
            following = subprocess.run(argv + record['nextArgs'], capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(following.returncode, 0, following.stdout)
            self.assertEqual(json.loads(following.stdout)['snapshot'], record['snapshot'])

    def test_receipt_precheck_reuses_same_raw_and_preserves_format_guards(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'message.txt'
            source.write_bytes('🟦 **F**\n原事件和条件\n'.encode('utf-8'))
            with mock.patch.object(session, '_read', wraps=session._read) as calls:
                result = session.relay_message([str(source), str(source)], ['F', 'F'], check_receipts=True)
            self.assertEqual(calls.call_count, 1)
            check = result['receiptCheck']
            self.assertEqual(check['receiptFiles'][0]['sha256'], hashlib.sha256(source.read_bytes()).hexdigest())
            self.assertFalse(check['receiptAuthenticated'])
            self.assertFalse(check['receiptCoverageVerified'])
            data = root / 'receipt.json'
            for raw in [b'0', b'false']:
                data.write_bytes(raw)
                self.assertTrue(session.relay_message([str(data)], ['F'], check_receipts=True)['receiptCheck']['passed'])
            for raw in [b'null', b'[]', b'{}', b'NaN', b'"   "', b'bad']:
                data.write_bytes(raw)
                with self.assertRaises(ValueError):
                    session.relay_message([str(data)], ['F'], check_receipts=True)
            source.write_bytes(b'```\nhidden\n```')
            with self.assertRaisesRegex(ValueError, 'visible-body'):
                session.relay_message([str(source)], ['F'], check_receipts=True)

    def test_literal_draft_stays_exact_and_difference_context_is_bounded(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, draft = root / 'source.txt', root / 'draft.txt'
            source.write_bytes(('🟦 **F**\n' + 'a' * 100000 + '\ncondition\n').encode())
            literal = session.relay_message([str(source)], ['F'])['messageText']
            draft.write_bytes(literal.encode())
            self.assertTrue(session.relay_message([str(source)], ['F'], str(draft), True)['passed'])
            draft.write_bytes(literal.replace('condition', '').encode())
            result = session.relay_message([str(source)], ['F'], str(draft), True)
            self.assertFalse(result['passed'])
            self.assertTrue(result['receiptCheck']['passed'])
            self.assertLessEqual(len(result['difference']['expectedContext']), 240)
            self.assertLessEqual(len(result['difference']['actualContext']), 240)
            self.assertIn('\\*\\*F\\*\\*', literal)

    def test_timeout_keeps_bounded_stdout_stderr_and_failure_without_retry(self):
        for stdout, stderr in [(b'checkpoint\n', b'stderr'), ('checkpoint\n', 'stderr'), (None, None),
                               (b'x' * 70000, b'end\xff')]:
            exc = subprocess.TimeoutExpired(['probe'], 1, output=stdout, stderr=stderr)
            with mock.patch.object(package.subprocess, 'run', side_effect=exc) as calls:
                result = package.run_tests(ROOT, timeout=1)
            self.assertEqual(calls.call_count, 1)
            self.assertFalse(result['passed'])
            self.assertEqual(result['timeoutSeconds'], 1)
            self.assertLessEqual(len(result['diagnostics']), 65536)
            if stdout and len(stdout) < 1000:
                self.assertIn('checkpoint', result['diagnostics'])
                self.assertIn('stderr', result['diagnostics'])
            if stdout and len(stdout) > 65536:
                self.assertTrue(result['diagnosticsTruncated'])

    def test_real_timeout_retains_checkpoint_and_normal_control(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            scripts = root / 'scripts'
            scripts.mkdir()
            target = scripts / 'test_probe.py'
            for delay, expected in [(0, True), (2, False)]:
                target.write_text('import time,unittest\nclass Probe(unittest.TestCase):\n def test_go(self):\n'
                                  '  print("checkpoint",flush=True)\n  time.sleep(' + str(delay) + ')\n', encoding='utf-8')
                result = package.run_tests(root, timeout=0.5)
                self.assertEqual(result['passed'], expected)
                self.assertIn('checkpoint', result['diagnostics'])


if __name__ == '__main__':
    unittest.main()
