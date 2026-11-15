"""Exercise real Skill payloads, references and maintenance differences."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import skill_files


class SkillFilesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.skill = self.root / 'local-method'
        self.skill.mkdir()
        self.text = ('---\nname: local-method\ndescription: Use a local method for a specific request\n'
                     'metadata:\n  version: "1.0.0"\n  retained: true\n---\n'
                     '# Method\n\nIf the source changed, read [details](references/details.md).\n')
        (self.skill / 'references').mkdir()
        (self.skill / 'references/details.md').write_text('Use the source, then check the result.\n', encoding='utf-8')
        self.write()

    def write(self, text=None):
        (self.skill / 'SKILL.md').write_text(self.text if text is None else text, encoding='utf-8')

    def copied(self):
        destination = self.root / 'snapshot'
        shutil.copytree(self.skill, destination)
        return destination

    def test_method_only_skill_and_optional_resources(self):
        self.assertTrue(skill_files.inspect(self.skill)['files_passed'])
        (self.skill / 'references/details.md').unlink()
        (self.skill / 'references').rmdir()
        self.write(self.text.replace('[details](references/details.md)', 'the actual source'))
        result = skill_files.inspect(self.skill)
        self.assertTrue(result['files_passed'])
        self.assertEqual(list(result['files']), ['SKILL.md'])

    def test_missing_skill_cannot_be_a_deliverable(self):
        (self.skill / 'SKILL.md').unlink()
        (self.skill / 'contract.json').write_text('{}', encoding='utf-8')
        with self.assertRaises(OSError):
            skill_files.inspect(self.skill)

    def test_frontmatter_identity_and_body(self):
        for text in ('Plain report', '---\nname: local-method\n---\nBody',
                     '---\nname: Bad Name\ndescription: Method\n---\nBody',
                     '---\nname: local-method\ndescription: ""\n---\nBody',
                     '---\nname: local-method\ndescription: Method\n---\n',
                     '---\n- local-method\n---\nBody'):
            with self.subTest(text=text):
                self.write(text)
                with self.assertRaises(ValueError):
                    skill_files.inspect(self.skill)
        self.write(self.text.replace('name: local-method', 'name: other-method'))
        self.assertFalse(skill_files.inspect(self.skill)['files_passed'])

    def test_multiline_yaml_utf8_and_crlf(self):
        self.write(self.text.replace('description: Use a local method for a specific request',
                                    'description: >-\n  读取真实原件，\n  按条件使用方法。').replace('\n', '\r\n'))
        self.assertTrue(skill_files.inspect(self.skill)['files_passed'])

    def test_missing_resource_is_reported_at_its_real_reference(self):
        (self.skill / 'references/details.md').unlink()
        result = skill_files.inspect(self.skill)
        self.assertFalse(result['files_passed'])
        self.assertIn('references/details.md', result['issues'][0])

    def test_titled_links_and_angle_bracket_paths_are_checked(self):
        for link in ('[reference](missing.md "title")', "[reference](missing.md 'title')",
                     '[reference](<missing file.md> "title")', '![image](assets/missing.png)'):
            with self.subTest(link=link):
                self.write(self.text + link + '\n')
                self.assertFalse(skill_files.inspect(self.skill)['files_passed'])
        (self.skill / 'references/space name.md').write_text('Actual reference', encoding='utf-8')
        self.write(self.text + '[real](<references/space name.md> "details")\n')
        self.assertTrue(skill_files.inspect(self.skill)['files_passed'])

    def test_nested_links_use_the_referring_document_directory(self):
        (self.skill / 'assets').mkdir()
        (self.skill / 'assets/中文 sample.txt').write_text('material', encoding='utf-8')
        (self.skill / 'references/details.md').write_text(
            '[material](../assets/%E4%B8%AD%E6%96%87%20sample.txt)\n[entry](../SKILL.md#method)\n', encoding='utf-8')
        result = skill_files.inspect(self.skill)
        self.assertTrue(result['files_passed'], result['issues'])
        self.assertEqual(len(result['checked_local_links']), 3)

    def test_examples_external_urls_and_anchors_are_not_missing_dependencies(self):
        self.write(self.text + '\n```markdown\n[example](not-a-file.md)\n```\n'
                   '~~~\n[another](another-file.md)\n~~~\n'
                   '`[inline](not-present.md)`\n[web](https://example.invalid/a)\n'
                   '[mail](mailto:author@example.invalid)\n[section](#method)\n')
        self.assertTrue(skill_files.inspect(self.skill)['files_passed'])

    def test_outside_reference_is_not_portable(self):
        (self.root / 'outside.md').write_text('not payload', encoding='utf-8')
        self.write(self.text + '[outside](../outside.md)\n')
        self.assertFalse(skill_files.inspect(self.skill)['files_passed'])

    def test_windows_drive_unc_and_file_links_are_local_not_web_schemes(self):
        for target in ('C:/materials/source.md', 'C:%5Cmaterials%5Csource.md',
                       '//server/share/source.md', 'file:///C:/materials/source.md',
                       '\\\\server\\share\\source.md'):
            with self.subTest(target=target):
                self.write(self.text + '[outside](' + target + ')\n')
                result = skill_files.inspect(self.skill)
                self.assertFalse(result['files_passed'])
                self.assertIn('Absolute local links', result['issues'][0])

    def test_payload_comparison_finds_changes_outside_contract(self):
        snapshot = self.copied()
        (self.skill / 'contract.json').write_text('{}', encoding='utf-8')
        (snapshot / 'contract.json').write_text('{}', encoding='utf-8')
        (snapshot / 'references/details.md').write_text('Changed decision and recovery.\n', encoding='utf-8')
        (snapshot / 'assets').mkdir()
        (snapshot / 'assets/material.txt').write_text('new material', encoding='utf-8')
        result = skill_files.compare(self.skill, snapshot)
        self.assertTrue(result['review_required'])
        self.assertEqual(result['changed'], ['references/details.md'])
        self.assertEqual(result['added'], ['assets/material.txt'])
        self.assertEqual(result['old_version'], result['new_version'])
        self.assertFalse(result['applied'])
        self.assertEqual((self.skill / 'references/details.md').read_text(encoding='utf-8'),
                         'Use the source, then check the result.\n')

    def test_removals_metadata_and_same_payload(self):
        snapshot = self.copied()
        self.assertFalse(skill_files.compare(self.skill, snapshot)['review_required'])
        (snapshot / 'references/details.md').unlink()
        (snapshot / 'agents').mkdir()
        (snapshot / 'agents/openai.yaml').write_text('policy:\n  allow_implicit_invocation: false\n', encoding='utf-8')
        result = skill_files.compare(self.skill, snapshot)
        self.assertEqual(result['removed'], ['references/details.md'])
        self.assertEqual(result['added'], ['agents/openai.yaml'])
        (snapshot / 'SKILL.md').write_text(self.text.replace('1.0.0', '1.1.0'), encoding='utf-8')
        self.assertIn('SKILL.md', skill_files.compare(self.skill, snapshot)['changed'])

    def test_generated_directories_do_not_create_false_changes(self):
        snapshot = self.copied()
        for name in skill_files.IGNORED_DIRS:
            directory = snapshot / name
            directory.mkdir()
            (directory / 'generated').write_text('incidental', encoding='utf-8')
        (snapshot / 'incidental.pyc').write_bytes(b'cache')
        self.assertFalse(skill_files.compare(self.skill, snapshot)['review_required'])

    def test_unreadable_enumeration_is_not_reported_as_unchanged(self):
        error = PermissionError('cannot enumerate payload')
        def failed_walk(root, **kwargs):
            kwargs['onerror'](error)
            return iter(())
        with patch.object(skill_files.os, 'walk', failed_walk):
            with self.assertRaises(PermissionError):
                skill_files.compare(self.skill, self.skill)

    def test_external_linked_file_is_rejected(self):
        outside = self.root / 'outside.txt'
        outside.write_text('external material', encoding='utf-8')
        try:
            (self.skill / 'linked.txt').symlink_to(outside)
        except OSError as error:
            self.skipTest('Symlink creation unavailable: ' + str(error))
        with self.assertRaises(ValueError):
            skill_files.inspect(self.skill)

    def test_cli_exit_codes_are_usable_without_running_skill_commands(self):
        script = Path(skill_files.__file__)
        (self.skill / 'scripts').mkdir()
        (self.skill / 'scripts/do-not-run.py').write_text('raise RuntimeError("not a check")\n', encoding='utf-8')
        def run(*args):
            command = subprocess.run([sys.executable, '-B', str(script), *map(str, args)],
                                     capture_output=True, text=True, encoding='utf-8', timeout=15)
            return command.returncode, json.loads(command.stdout)
        self.assertEqual(run('inspect', self.skill)[0], 0)
        snapshot = self.copied()
        self.assertEqual(run('compare', self.skill, snapshot)[0], 0)
        (snapshot / 'scripts/do-not-run.py').write_text('different payload\n', encoding='utf-8')
        self.assertEqual(run('compare', self.skill, snapshot)[0], 3)
        (self.skill / 'references/details.md').unlink()
        self.assertEqual(run('inspect', self.skill)[0], 2)


    def test_links_must_match_payload_path_exactly(self):
        (self.skill / '__pycache__').mkdir()
        (self.skill / '__pycache__/x.md').write_text('generated', encoding='utf-8')
        for link in ('references\\details.md', 'REFERENCES/Details.MD', '__pycache__/x.md'):
            with self.subTest(link=link):
                self.write(self.text.replace('references/details.md', link))
                result = skill_files.inspect(self.skill)
                self.assertFalse(result['files_passed'], link)
        self.write(self.text.replace('references/details.md', 'references'))
        self.assertTrue(skill_files.inspect(self.skill)['files_passed'])

    def test_cli_output_survives_gbk_console(self):
        env = {k: v for k, v in os.environ.items() if k not in ('PYTHONUTF8', 'PYTHONIOENCODING')}
        self.write(self.text.replace('references/details.md', 'missing-😀.md'))
        command = subprocess.run([sys.executable, '-B', skill_files.__file__, 'inspect', str(self.skill)],
                                 capture_output=True, timeout=15, env=env)
        self.assertEqual(command.returncode, 2)
        report = json.loads(command.stdout.decode('ascii'))
        self.assertIn('missing-😀.md', json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    unittest.main()
