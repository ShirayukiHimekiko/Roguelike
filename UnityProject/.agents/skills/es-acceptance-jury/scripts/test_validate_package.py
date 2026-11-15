"""Real validator diagnostics with isolated, explicitly fingerprinted fixtures."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import validate_package as package

ROOT = Path(__file__).resolve().parents[1]


class PackageValidationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / package.NAME
        shutil.copytree(ROOT, self.root)
        self.metadata = self.read_metadata()
        self.assertTrue(self.inspect()['passed'])

    def inspect(self, *, full=True):
        return package.inspect_structure(self.root, require_full_integrity=full)

    def read_metadata(self):
        return json.loads((self.root / package.MANIFEST_FILE).read_text(encoding='utf-8-sig'))

    def write_metadata(self, value):
        (self.root / package.MANIFEST_FILE).write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    def write_payload(self, relative, raw):
        """Record only this intentional fixture edit, never refresh the real package."""
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        metadata = self.read_metadata()
        metadata['payloadFiles'][relative] = hashlib.sha256(raw).hexdigest()
        self.write_metadata(metadata)

    def assert_issue(self, code, *, full=True):
        result = self.inspect(full=full)
        self.assertFalse(result['passed'])
        codes = {item['code'] for item in result['issues']}
        self.assertIn(code, codes, result['issues'])
        self.assertFalse({'core-source-mismatch', 'payload-source-mismatch'} & codes,
                         'An unrelated fingerprint failure must not mask this diagnostic.')
        return result

    def test_utf8_bom_crlf_and_chinese_keep_original_byte_fingerprints(self):
        for relative in ('README.md', 'SKILL.md', 'agents/openai.yaml', 'package-info.json'):
            with self.subTest(relative=relative):
                path = self.root / relative
                raw = b'\xef\xbb\xbf' + path.read_bytes().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
                if relative == package.MANIFEST_FILE:
                    path.write_bytes(raw)
                else:
                    self.write_payload(relative, raw)
                    self.assertEqual(self.read_metadata()['payloadFiles'][relative],
                                     hashlib.sha256(raw).hexdigest())
                result = self.inspect()
                self.assertTrue(result['passed'], result['issues'])
                self.assertTrue(result['integrity']['fullCoverage'])
                self.assertEqual(path.read_bytes(), raw)

    def test_legal_links_chinese_paths_and_fenced_examples(self):
        self.write_payload('references/夹具 (示例).md',
                           '<a id="fixture"></a>\n## 中文夹具\n正文。\n'.encode('utf-8'))
        raw = (self.root / 'README.md').read_bytes()
        fence = chr(96) * 3
        addition = ('\n[当前](SKILL.md#terms)\n'
                    '[中文](<references/夹具 (示例).md#fixture>)\n'
                    '[引用][current]\n[current]: SKILL.md#terms\n'
                    + fence + '\n[示例不执行](missing-example.md)\n' + fence + '\n')
        self.write_payload('README.md', raw + addition.encode('utf-8'))
        self.assertTrue(self.inspect()['passed'])

    def test_invalid_link_diagnostics_reach_the_intended_branch(self):
        baseline = (self.root / 'README.md').read_bytes()
        for target, code in (
                ('not-present.md', 'broken-link'),
                ('SKILL.md#fixture-missing-anchor', 'missing-anchor'),
                ('../outside.md', 'outside-package-link'),
                ('%2e%2e/outside.md', 'outside-package-link'),
                ('C:/outside.md', 'nonportable-link'),
                ('/outside.md', 'nonportable-link'),
                ('https://[', 'invalid-link')):
            with self.subTest(target=target):
                self.write_payload('README.md', baseline + ('\n[坏例](' + target + ')\n').encode('utf-8'))
                self.assert_issue(code)

    def test_hidden_markdown_links_and_anchors_do_not_enter_link_contract(self):
        self.write_payload('references/comment-fixture.md',
                           b'## Live\nLiteral `<!--`\n<!--\n<a id="hidden"></a>\n'
                           b'[disabled](absent.md)\n-->\n'
                           b'    [example](absent.md)\n'
                           b'   ```text\n[example](absent.md)\n   ```\n'
                           b'<a id="visible"></a>\n## Next\nBody\n')
        raw=(self.root/'README.md').read_bytes()
        self.write_payload('README.md',raw+b'\n[good](references/comment-fixture.md#visible)\n')
        self.assertTrue(self.inspect()['passed'])
        self.write_payload('README.md',raw+b'\n[bad](references/comment-fixture.md#hidden)\n')
        self.assert_issue('missing-anchor')
        # A new call must observe new bytes at the same target path.
        self.write_payload('references/comment-fixture.md',b'<a id="hidden"></a>\n## Now active\nBody\n')
        self.assertTrue(self.inspect()['passed'])
        self.write_payload('references/comment-fixture.md',b'## Removed\nBody\n')
        self.assert_issue('missing-anchor')

    def test_all_json_payloads_share_emitter_strict_json_contract(self):
        for raw in (b'{"value":NaN}',b'{"value":Infinity}',b'{"value":-Infinity}',b'{"value":1,"value":2}'):
            with self.subTest(raw=raw):
                self.write_payload('other-data.json',raw)
                self.assert_issue('invalid-json')
                emitted=package.emit_payload_files(self.root)
                self.assertEqual(emitted['status'],'failed')
                self.assertIn('invalid-json',{i['code'] for i in emitted['issues']})
        self.write_payload('other-data.json',b'{"value":1}')
        self.assertTrue(self.inspect()['passed'])
        self.assertEqual(package.emit_payload_files(self.root)['status'],'candidate-generated')

    def test_missing_frontmatter_is_diagnosed(self):
        body = (self.root / 'SKILL.md').read_text(encoding='utf-8').split('---', 2)[-1]
        self.write_payload('SKILL.md', body.encode('utf-8'))
        self.assert_issue('invalid-frontmatter')

    def test_frontmatter_name_description_and_scalar_contract(self):
        baseline = (self.root / 'SKILL.md').read_text(encoding='utf-8')
        lines = baseline.splitlines()
        description = next(line for line in lines if line.startswith('description:'))
        for changed in (
                baseline.replace('name: ' + package.NAME, 'name: different-skill', 1),
                baseline.replace(description, '', 1),
                baseline.replace(description, 'description: "unclosed', 1)):
            with self.subTest(changed=changed[:100]):
                self.write_payload('SKILL.md', changed.encode('utf-8'))
                self.assert_issue('frontmatter-mismatch')

    def test_agent_metadata_required_fields_are_checked(self):
        baseline = (self.root / 'agents/openai.yaml').read_text(encoding='utf-8')
        prompt = next(line for line in baseline.splitlines() if line.startswith('  default_prompt:'))
        for changed in (baseline.replace('interface:', 'other:', 1),
                        baseline.replace(prompt, '', 1),
                        baseline.replace(prompt, '  default_prompt: "unclosed', 1)):
            with self.subTest(changed=changed[:100]):
                self.write_payload('agents/openai.yaml', changed.encode('utf-8'))
                self.assert_issue('invalid-agent-metadata')

    def test_agent_prompt_must_invoke_the_actual_skill(self):
        baseline = (self.root / 'agents/openai.yaml').read_text(encoding='utf-8')
        self.write_payload('agents/openai.yaml', baseline.replace('$' + package.NAME, '$another-skill').encode('utf-8'))
        self.assert_issue('agent-skill-mismatch')

    def metadata_value(self, relative, value):
        source = (ROOT / relative).read_text(encoding='utf-8-sig')
        prefix = 'description:' if relative == 'SKILL.md' else '  default_prompt:'
        original = next(line for line in source.splitlines() if line.startswith(prefix))
        self.write_payload(relative, source.replace(original, prefix + ' ' + value, 1).encode('utf-8'))

    def test_single_quoted_frontmatter_rejects_unclosed_values(self):
        for value in ("'fixture metadata", "'fixture metadata''", "'fixture' tail'", "'"):
            with self.subTest(value=value):
                self.metadata_value('SKILL.md', value)
                self.assert_issue('frontmatter-mismatch')

    def test_single_quoted_agent_prompt_rejects_unclosed_values(self):
        for value in ("'Use $es-acceptance-jury fixture", "'Use $es-acceptance-jury fixture''",
                      "'Use $es-acceptance-jury' tail'", "'"):
            with self.subTest(value=value):
                self.metadata_value('agents/openai.yaml', value)
                self.assert_issue('invalid-agent-metadata')

    def test_valid_metadata_quotes_plain_apostrophes_and_escapes_remain_accepted(self):
        values = (
            'Use $es-acceptance-jury fixture',
            "'Use $es-acceptance-jury fixture'",
            '"Use $es-acceptance-jury fixture"',
            "'Use $es-acceptance-jury it''s valid'",
            "Use $es-acceptance-jury user's text",
            "'Use $es-acceptance-jury 中文 '''",
            "'Use $es-acceptance-jury fixture' # metadata comment",
            "'Use $es-acceptance-jury fixture'#metadata comment",
        )
        for relative in ('SKILL.md', 'agents/openai.yaml'):
            for value in values:
                with self.subTest(relative=relative, value=value):
                    self.metadata_value(relative, value)
                    result = self.inspect()
                    self.assertTrue(result['passed'], result['issues'])

    def test_metadata_malformed_duplicate_keys_and_nonfinite_json(self):
        for raw in ('{', '{"schemaVersion": 2, "schemaVersion": 2}', '{"schemaVersion": NaN}'):
            with self.subTest(raw=raw):
                (self.root / package.MANIFEST_FILE).write_text(raw, encoding='utf-8')
                self.assert_issue('invalid-package-metadata')

    def test_metadata_rejects_unsupported_schema_types_and_values(self):
        for schema in (True, 0, 3, '2'):
            with self.subTest(schema=schema):
                metadata = copy.deepcopy(self.metadata)
                metadata['schemaVersion'] = schema
                self.write_metadata(metadata)
                self.assert_issue('invalid-package-metadata')

    def test_schema1_is_legacy_only_and_cannot_claim_full_integrity(self):
        metadata = copy.deepcopy(self.metadata)
        metadata['schemaVersion'] = 1
        metadata.pop('payloadFiles')
        self.write_metadata(metadata)
        legacy = self.inspect(full=False)
        self.assertTrue(legacy['passed'], legacy['issues'])
        self.assertEqual(legacy['integrity']['status'], 'legacy-core-only')
        self.assertFalse(legacy['integrity']['fullCoverage'])
        self.assert_issue('payload-integrity-required')

    def test_metadata_identity_requirements_and_unknown_fields(self):
        for key, value, code in (
                ('name', 'different-skill', 'package-metadata-mismatch'),
                ('version', 'unversioned', 'package-metadata-mismatch'),
                ('python', '>=2.7', 'package-requirements-mismatch'),
                ('extra-fixture-field', True, 'unknown-package-metadata')):
            with self.subTest(key=key):
                metadata = copy.deepcopy(self.metadata)
                metadata[key] = value
                self.write_metadata(metadata)
                self.assert_issue(code)

    def test_manifest_paths_are_checked_before_any_resolution(self):
        for relative in ('../escape.md', 'C:/escape.md', 'a\\escape.md', 'aux.txt',
                         'tail./entry.md', '/absolute.md', 'a/' * 17 + 'entry.md'):
            with self.subTest(relative=relative):
                metadata = copy.deepcopy(self.metadata)
                metadata['payloadFiles'][relative] = '0' * 64
                self.write_metadata(metadata)
                self.assert_issue('invalid-fingerprint-path')

    def test_case_and_unicode_manifest_aliases_are_rejected(self):
        for keys in (('README.md', 'readme.md'), ('extra/e\u0301.txt', 'extra/é.txt')):
            with self.subTest(keys=keys):
                metadata = copy.deepcopy(self.metadata)
                for key in keys:
                    metadata['payloadFiles'][key] = metadata['payloadFiles']['README.md']
                self.write_metadata(metadata)
                self.assert_issue('fingerprint-path-collision')

    def test_manifest_self_reference_and_invalid_hash_are_diagnosed(self):
        for key, value, code in (
                ('package-info.json', '0' * 64, 'manifest-self-reference'),
                ('README.md', 'not-a-sha256', 'invalid-fingerprint-hash')):
            with self.subTest(code=code):
                metadata = copy.deepcopy(self.metadata)
                metadata['payloadFiles'][key] = value
                self.write_metadata(metadata)
                self.assert_issue(code)

    def test_inventory_addition_and_phantom_manifest_entries_are_distinct(self):
        path = self.root / 'fixture-extra.txt'
        path.write_text('fixture', encoding='utf-8')
        self.assert_issue('missing-payload-fingerprint')
        self.write_payload('fixture-extra.txt', path.read_bytes())
        self.assertTrue(self.inspect()['passed'])
        metadata = self.read_metadata()
        metadata['payloadFiles']['fixture-absent.txt'] = '0' * 64
        self.write_metadata(metadata)
        self.assert_issue('unexpected-payload-fingerprint')

    def test_private_or_generated_entries_are_not_distributable(self):
        for relative in ('.env', 'fixture.pyc', '__pycache__'):
            with self.subTest(relative=relative):
                path = self.root / relative
                if relative == '__pycache__':
                    path.mkdir()
                else:
                    path.write_bytes(b'fixture')
                self.assert_issue('private-or-generated-content')
                if path.is_dir():
                    path.rmdir()
                else:
                    path.unlink()
        self.assertTrue(self.inspect()['passed'])

    def test_private_preference_records_are_rejected_even_when_fingerprinted(self):
        raw = json.dumps({'environment': 'fixture', 'selection': {}, 'frozenAtUtc': 'fixture'}).encode('utf-8')
        self.write_payload('fixture-preference.json', raw)
        self.assert_issue('private-preference-record')

    def test_other_json_and_python_syntax_have_explicit_diagnostics(self):
        for relative, raw, code in (
                ('fixture-invalid.json', b'{', 'invalid-json'),
                ('fixture-invalid.py', b'def broken(\n', 'invalid-python')):
            with self.subTest(relative=relative):
                self.write_payload(relative, raw)
                self.assert_issue(code)
                (self.root / relative).unlink()
                metadata = self.read_metadata()
                metadata['payloadFiles'].pop(relative)
                self.write_metadata(metadata)
                self.assertTrue(self.inspect()['passed'])

    def test_invalid_utf8_nul_and_replacement_characters_remain_rejected(self):
        for raw in (b'\xff', b'\xff\xfeS\x00', b'contains\x00nul', '\ufffd'.encode('utf-8')):
            with self.subTest(raw=raw):
                self.write_payload('README.md', raw)
                self.assert_issue('invalid-utf8-text')

    def test_file_byte_capacity_boundary_uses_the_original_input(self):
        relative = 'fixture-capacity.bin'
        raw = b'x' * package.MAX_FILE_BYTES
        self.write_payload(relative, raw)
        self.assertTrue(self.inspect()['passed'])
        self.write_payload(relative, raw + b'x')
        self.assert_issue('file-size-limit')

    def test_file_count_capacity_accepts_limit_and_rejects_next_file(self):
        metadata = self.read_metadata()
        count = sum(path.is_file() for path in self.root.rglob('*'))
        extra = self.root / 'fixture-count'
        extra.mkdir()
        for index in range(package.MAX_FILES - count):
            relative = 'fixture-count/' + str(index) + '.bin'
            (self.root / relative).write_bytes(b'x')
            metadata['payloadFiles'][relative] = hashlib.sha256(b'x').hexdigest()
        self.write_metadata(metadata)
        normal = self.inspect()
        self.assertTrue(normal['passed'], normal['issues'])
        self.assertEqual(normal['filesChecked'], package.MAX_FILES)
        self.write_payload('fixture-count/overflow.bin', b'x')
        self.assert_issue('package-limit')

    def test_total_byte_budget_checks_original_bytes_at_the_boundary(self):
        observed = sum(path.stat().st_size for path in self.root.rglob('*') if path.is_file())
        with mock.patch.object(package, 'MAX_TOTAL_BYTES', observed):
            self.assertTrue(self.inspect()['passed'])
        with mock.patch.object(package, 'MAX_TOTAL_BYTES', observed - 1):
            self.assert_issue('package-limit')

    def test_cli_returns_diagnostics_and_exit_two_for_a_broken_link(self):
        command = [sys.executable, '-X', 'utf8', '-B', str(ROOT / 'scripts/validate_package.py'),
                   '--skill-root', str(self.root), '--structure-only', '--require-full-integrity']
        options = dict(capture_output=True, text=True, encoding='utf-8', timeout=30,
                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        normal = subprocess.run(command, **options)
        self.assertEqual(normal.returncode, 0, normal.stderr)
        self.assertTrue(json.loads(normal.stdout)['passed'])
        raw = (self.root / 'README.md').read_bytes() + b'\n[fixture](not-present.md)\n'
        self.write_payload('README.md', raw)
        failed = subprocess.run(command, **options)
        self.assertEqual(failed.returncode, 2, failed.stderr)
        record = json.loads(failed.stdout)
        self.assertFalse(record['passed'])
        self.assertIn('broken-link', {item['code'] for item in record['issues']})


if __name__ == '__main__':
    unittest.main()
