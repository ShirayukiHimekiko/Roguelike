import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import shutil
from unittest import mock
import jury_read
from jury_read import read_section


class JuryReadTests(unittest.TestCase):
    def test_priority_is_bounded_but_retained_in_common_decision(self):
        root=Path(__file__).resolve().parent.parent
        priority=read_section('references/review-standard.md#obligation-priority',root)
        failure=read_section('references/review-standard.md#failure-continuation',root)
        common=read_section('references/review-standard.md#decision-order',root)
        self.assertLess(priority['endLine'],failure['startLine'])
        self.assertNotIn('F05',priority['content'])
        self.assertIn('兑现完整有效用户目标及真实消费者结果',priority['content'])
        self.assertIn('source-authority.md#current-mainline',priority['content'])
        self.assertIn(priority['content'],common['content'])
        self.assertNotIn(failure['content'],common['content'])

    def test_default_progress_section_ends_before_delegated_route_section(self):
        root = Path(__file__).resolve().parent.parent
        default = read_section('references/must-read-work-priority.md#core-loop-progress', root)
        delegated = read_section('references/must-read-work-priority.md#route-leadership', root)
        self.assertLess(default['endLine'], delegated['startLine'])
        self.assertNotIn(delegated['content'], default['content'])

    def test_explicit_continuation_is_reported_without_reading_the_target(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'nav.md').write_text('## Entry\nUse the full rule.\n<!-- jury-read-continue: missing.md#rule -->\n', encoding='utf-8')
            result = read_section('nav.md#Entry', root)
            self.assertEqual(result['continuationSelectors'], ['missing.md#rule'])
            self.assertTrue(result['continuationRequired'])
            self.assertFalse((root / 'missing.md').exists())
            (root / 'nav.md').write_text('## Entry\n```text\n<!-- jury-read-continue: ../outside.md -->\n```\n', encoding='utf-8')
            self.assertFalse(read_section('nav.md#Entry', root)['continuationRequired'])
            (root / 'nav.md').write_text('## Entry\n<!-- jury-read-continue: ../outside.md -->\n', encoding='utf-8')
            with self.assertRaises(ValueError):
                read_section('nav.md#Entry', root)

    def test_round_cli_returns_current_entry_without_loading_unrelated_references(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'scripts').mkdir()
            (root / 'references').mkdir()
            shutil.copyfile(Path(__file__).with_name('jury_read.py'), root / 'scripts/jury_read.py')
            entry = root / 'SKILL.md'
            entry.write_text('# 当前核心\n必要义务与例外\n', encoding='utf-8')
            for label in ('continuity', 'work-priority', 'review-delivery'):
                path = root / 'references' / ('must-read-' + label + '.md')
                path.write_bytes(b'\xffUNRELATED_BODY_MUST_NOT_BE_READ')
            command = [sys.executable, '-X', 'utf8', '-B', str(root / 'scripts/jury_read.py'), '--round-context']
            for updated in (False, True):
                if updated:
                    entry.write_text('恢复后新标准，不能沿用旧正文\n', encoding='utf-8')
                result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(entry.read_text(encoding='utf-8'), result.stdout)
                self.assertIn(str(entry), result.stdout)
                self.assertNotIn('UNRELATED_BODY_MUST_NOT_BE_READ', result.stdout)
                self.assertFalse((root / 'references/reading-guide.md').exists())

    def test_round_failure_does_not_emit_partial_body(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'scripts').mkdir()
            (root / 'references').mkdir()
            shutil.copyfile(Path(__file__).with_name('jury_read.py'), root / 'scripts/jury_read.py')
            last = root / 'SKILL.md'
            for content in (None, b'\xff', b' \n', b'x' * (24 * 1024 + 1)):
                if content is not None:
                    last.write_bytes(content)
                result = subprocess.run([sys.executable, '-X', 'utf8', '-B', str(root / 'scripts/jury_read.py'),
                                         '--round-context'], capture_output=True, text=True, encoding='utf-8', timeout=10)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(json.loads(result.stdout)['status'], 'invalid-input')
                self.assertNotIn('MUST READ', result.stdout)

    def test_supplementary_body_is_available_only_when_explicitly_selected(self):
        root = Path(__file__).resolve().parent.parent
        command = [sys.executable, '-X', 'utf8', '-B', str(root / 'scripts/jury_read.py'),
                   '--section', 'references/must-read-continuity.md#runtime-evidence-boundary']
        result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        section = json.loads(result.stdout)['sections'][0]
        self.assertIn('游戏 JSON', section['content'])
        self.assertNotIn('## 记录降温', section['content'])

    def test_sections_keep_nested_obligations_and_exclude_next_anchor(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = '# Main\n\n<a id="a"></a>\n## First\n必须保留\n### Nested\n条件\n\n<a id="b"></a>\n## Next\n后文\n'
            (root/'doc.md').write_bytes(source.encode('utf-8'))
            got = read_section('doc.md#a', root)
            self.assertIn('### Nested\n条件', got['content'])
            self.assertNotIn('id="b"', got['content'])
            self.assertNotIn('后文', got['content'])
            self.assertEqual(got['characters'], len(got['content']))
            self.assertEqual(got['utf8Bytes'], len(got['content'].encode('utf-8')))
            self.assertEqual(read_section('doc.md#Next', root)['content'], '## Next\n后文\n')

    def test_code_fences_are_not_section_boundaries(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)/'doc.md'
            p.write_bytes(b'## First\n```text\n## Second\n```\nkeep\n## Second\nend\n')
            self.assertIn('keep', read_section('doc.md#First', folder)['content'])
            self.assertEqual(read_section('doc.md#Second', folder)['content'], '## Second\nend\n')

    def test_html_comments_do_not_select_anchors_or_truncate_visible_sections(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = ('<!--\n<a id="live"></a>\n## Visible\nOld hidden body.\n-->\n'
                      '<a id="live"></a>\n## Visible\nBEFORE\n<!--\n'
                      '<a id="hidden"></a>\n## Disabled\n```\n-->\n'
                      'REQUIRED_AFTER_COMMENT\n## Next\nEnd.\n')
            (root/'doc.md').write_bytes(source.encode('utf-8'))
            got = read_section('doc.md#live', root)
            self.assertIn('REQUIRED_AFTER_COMMENT', got['content'])
            self.assertNotIn('Old hidden body.', got['content'])
            self.assertNotIn('End.', got['content'])
            self.assertEqual(got['startLine'], 6)
            self.assertEqual(read_section('doc.md#Visible', root)['content'], got['content'].split('\n', 1)[1])
            with self.assertRaises(ValueError):
                read_section('doc.md#hidden', root)

    def test_comment_literals_and_real_continuation_metadata_remain_distinct(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = ('## Live\nLiteral `<!--` is code.\n'
                      '<!--\n<!-- jury-read-continue: ../hidden.md -->\n'
                      '<!-- jury-read-continue: next.md#more -->\n'
                      '```text\n<!--\n<!-- jury-read-continue: ../code.md -->\n```\n'
                      'KEEP\n## Next\nEnd.\n')
            (root/'doc.md').write_bytes(source.encode('utf-8'))
            got = read_section('doc.md#Live', root)
            self.assertEqual(got['continuationSelectors'], ['next.md#more'])
            self.assertIn('KEEP', got['content'])
            self.assertEqual(read_section('doc.md#Next', root)['content'], '## Next\nEnd.\n')

    def test_missing_duplicate_empty_and_escape_fail(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)/'doc.md'
            p.write_text('## A\na\n## A\nb\n', encoding='utf-8')
            for selector in ('doc.md#A', 'doc.md#missing', 'doc.md#', '../outside.md', 'doc.py'):
                with self.subTest(selector=selector), self.assertRaises(ValueError):
                    read_section(selector, folder)

    def test_indented_examples_cannot_activate_sections_or_dependencies(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)/'doc.md'
            source = ('   ## Live\nKEEP\n'
                      '    <!-- jury-read-continue: ../outside.md -->\n'
                      '\t<a id="ghost"></a>\n'
                      '    ## Ghost\n'
                      '   ```text\n## Fenced\n   ```\n'
                      '    <a id="example"></a>\n'
                      '## Next\nEND\n')
            p.write_bytes(source.encode('utf-8'))
            got = read_section('doc.md#Live', folder)
            self.assertFalse(got['continuationRequired'])
            self.assertIn('id="example"', got['content'])
            self.assertNotIn('END', got['content'])
            for anchor in ('ghost', 'Ghost', 'example', 'Fenced'):
                with self.subTest(anchor=anchor), self.assertRaises(ValueError):
                    read_section('doc.md#'+anchor, folder)

    def test_fence_with_info_is_not_a_close_and_cannot_hide_following_rules(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)/'doc.md'
            for fence in ('```', '~~~'):
                source = ('## First\n' + fence + 'text\n' + fence + 'not-a-close\n'
                          '## Example heading still inside code\n' + fence + '\n'
                          'MUST_KEEP_REAL_RULE\n## Next\noutside\n')
                p.write_bytes(source.encode('utf-8'))
                actual = read_section('doc.md#First', folder)['content']
                self.assertIn('MUST_KEEP_REAL_RULE', actual)
                self.assertNotIn('outside', actual)

    def test_invalid_encoding_and_oversize_fail_without_partial_success(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)/'doc.md'
            for data in (b'\xff', b'x'*(1024*1024+1)):
                p.write_bytes(data)
                with self.assertRaises((ValueError, UnicodeError)):
                    read_section('doc.md', folder)

    def test_cli_measure_is_not_consumption_and_duplicate_selector_is_once(self):
        command = [sys.executable, '-B', str(Path(__file__).with_name('jury_read.py')),
                   '--section', 'SKILL.md', '--section', 'SKILL.md', '--measure']
        got = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', timeout=10)
        self.assertEqual(got.returncode, 0, got.stderr)
        result = json.loads(got.stdout)
        self.assertEqual(result['status'], 'measured')
        self.assertEqual(len(result['sections']), 1)
        self.assertNotIn('content', result['sections'][0])
        self.assertFalse(result['tokensMeasured'])

    def test_conditional_routes_preserve_experience_and_write_obligations(self):
        specialist = read_section('references/review-standard.md#specialist-quality')['content']
        for anchor in ('player-experience', 'evidence-gaps', 'method-selection', 'content-review'):
            self.assertIn('](#' + anchor + ')', specialist)
            self.assertTrue(read_section('references/review-standard.md#' + anchor)['content'])
        write = read_section('references/source-authority.md#rule-write')['content']
        self.assertIn('](#write-consumption)', write)
        actual = read_section('references/source-authority.md#write-consumption')['content']
        self.assertIn('真实用户原话', actual)
        self.assertIn('授权争议', actual)


class JuryReadFollowTests(unittest.TestCase):
    def test_real_maintenance_follow_reaches_required_contracts_and_common_guards(self):
        root = Path(__file__).resolve().parent.parent
        result = jury_read.read_section_page(['references/source-authority.md#rule-write'], root)
        selectors = [x['selector'] for x in result['sections']]
        self.assertEqual(selectors, ['references/source-authority.md#rule-write',
                                     'references/source-authority.md#write-consumption',
                                     'references/rule-maintenance.md'])
        self.assertIn('真实用户原话', ''.join(x['content'] for x in result['sections']))
        shared = [x['selector'] for x in jury_read.expanded_sections(['SKILL.md'], root)]
        self.assertEqual(shared,['SKILL.md'])
        import jury_candidates
        selected=jury_candidates.read_profile(root,'worker','review','general')['readSelectors']
        self.assertIn('references/coordination.md#no-simulation',selected)

    def tree(self, folder):
        root = Path(folder)
        (root / 'a.md').write_text('## A\nREQUIRED_A\n<!-- jury-read-continue: b.md#B -->\n'
                                 '<!-- jury-read-continue: c.md#C -->\n[optional](unused.md)\n', encoding='utf-8')
        (root / 'b.md').write_text('## B\nREQUIRED_B\n<!-- jury-read-continue: c.md#C -->\n', encoding='utf-8')
        (root / 'c.md').write_text('## C\nREQUIRED_C\n', encoding='utf-8')
        (root / 'unused.md').write_bytes(b'\xffOPTIONAL_NOT_READ')
        return root

    def test_follow_expands_diamond_once_and_leaves_normal_link_unread(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self.tree(folder)
            result = jury_read.read_section_page(['a.md#A', 'a.md#A'], root)
            self.assertEqual([x['selector'] for x in result['sections']], ['a.md#A', 'b.md#B', 'c.md#C'])
            self.assertTrue(result['dependenciesAutoLoaded'])
            self.assertFalse(result['allPagesConsumptionVerified'])
            self.assertFalse(result['sourceAuthenticated'])
            for text in ('REQUIRED_A', 'REQUIRED_B', 'REQUIRED_C'):
                self.assertIn(text, ''.join(x['content'] for x in result['sections']))
            self.assertEqual(read_section('a.md#A', root)['continuationSelectors'], ['b.md#B', 'c.md#C'])

    def test_cli_next_args_really_read_every_page_without_a_plan(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self.tree(folder)
            (root / 'scripts').mkdir()
            for name in ('jury_read.py', 'jury_session.py'):
                shutil.copyfile(Path(__file__).with_name(name), root / 'scripts' / name)
            command = [sys.executable, '-B', str(root / 'scripts' / 'jury_read.py')]
            args = ['--section', 'a.md#A', '--follow', '--page-bytes', '150']
            found, calls = [], 0
            while args is not None:
                calls += 1
                self.assertLessEqual(calls, 3)
                actual = subprocess.run(command + args, capture_output=True, text=True, encoding='utf-8', timeout=10)
                self.assertEqual(actual.returncode, 0, actual.stdout + actual.stderr)
                result = json.loads(actual.stdout)
                found.extend(x['selector'] for x in result['sections'])
                args = result['nextArgs']
                if args:
                    self.assertIn('--follow', args)
                    self.assertNotIn('--from-plan', args)
                    self.assertIn('--expect-snapshot', args)
            self.assertGreater(calls, 1)
            self.assertEqual(found, ['a.md#A', 'b.md#B', 'c.md#C'])

    def test_measure_continuation_can_be_read_but_is_not_claimed_consumed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self.tree(folder)
            measured = jury_read.read_section_page(['a.md#A'], root, page_bytes=150, measure=True)
            self.assertTrue(all('content' not in x for x in measured['sections']))
            self.assertIn('--measure', measured['nextArgs'])
            read = jury_read.read_section_page(['a.md#A'], root, page=1, page_bytes=150,
                                               expect_snapshot=measured['snapshot'])
            self.assertTrue(all('content' in x for x in read['sections']))
            self.assertFalse(read['allPagesConsumptionVerified'])

    def test_follow_snapshot_rejects_changed_selection_source_root_and_target(self):
        with tempfile.TemporaryDirectory() as folder, tempfile.TemporaryDirectory() as other:
            root = self.tree(folder)
            other_root = self.tree(other)
            original = jury_read.read_section_page(['a.md#A', 'c.md#C'], root, page_bytes=150)
            for selectors, selected_root, target in [(['c.md#C', 'a.md#A'], root, 150),
                                                     (['a.md#A', 'c.md#C'], other_root, 150),
                                                     (['a.md#A', 'c.md#C'], root, 151)]:
                with self.assertRaisesRegex(ValueError, 'reading-snapshot-changed'):
                    jury_read.read_section_page(selectors, selected_root, page_bytes=target,
                                                expect_snapshot=original['snapshot'])
            with mock.patch.object(jury_read, '_IMPLEMENTATION_SHA256', '0' * 64):
                with self.assertRaisesRegex(ValueError, 'reading-snapshot-changed'):
                    jury_read.read_section_page(['a.md#A', 'c.md#C'], root, page_bytes=150,
                                                expect_snapshot=original['snapshot'])
            (root / 'c.md').write_text('## C\nCHANGED_REQUIRED_C\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'reading-snapshot-changed'):
                jury_read.read_section_page(['a.md#A', 'c.md#C'], root, page_bytes=150,
                                            expect_snapshot=original['snapshot'])

    def test_follow_rejects_bad_dependency_and_never_truncates_large_section(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for dependency in ('missing.md', 'a.md#A', '../outside.md'):
                (root / 'a.md').write_text('## A\nKEEP\n<!-- jury-read-continue: ' + dependency + ' -->\n', encoding='utf-8')
                with self.subTest(dependency=dependency), self.assertRaises((ValueError, OSError)):
                    jury_read.read_section_page(['a.md#A'], root)
            (root / 'a.md').write_text('## A\n' + 'x' * 200, encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'section exceeds page target'):
                jury_read.read_section_page(['a.md#A'], root, page_bytes=150)

    def test_follow_rechecks_source_before_returning_a_page(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self.tree(folder)
            verify = jury_read._ReadSession.verify
            def change_then_verify(session):
                (root / 'c.md').write_text('## C\nSOURCE_CHANGED_BEFORE_RETURN\n', encoding='utf-8')
                verify(session)
            with mock.patch.object(jury_read._ReadSession, 'verify', change_then_verify):
                with self.assertRaisesRegex(ValueError, 'reading-input-changed'):
                    jury_read.read_section_page(['a.md#A'], root)

    def test_follow_cli_rejects_incompatible_modes_and_preserves_raw_selection(self):
        command = [sys.executable, '-B', str(Path(__file__).with_name('jury_read.py'))]
        for args in (['--round-context', '--follow'], ['--section', 'SKILL.md', '--follow', '--role', 'progress']):
            result = subprocess.run(command + args, capture_output=True, text=True, encoding='utf-8', timeout=10)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(json.loads(result.stdout)['status'], 'invalid-input')
        result = subprocess.run(command + ['--section', 'SKILL.md'], capture_output=True, text=True, encoding='utf-8', timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = json.loads(result.stdout)
        self.assertFalse(result['dependenciesAutoLoaded'])
        self.assertEqual(len(result['sections']), 1)




class ExplicitFinalBudgetCLITests(unittest.TestCase):
    def call_reader(self, args, root=None):
        script=(root or Path(__file__).resolve().parent.parent)/'scripts/jury_read.py'
        return subprocess.run([sys.executable,'-X','utf8','-B',str(script),*args],capture_output=True,text=True,encoding='utf-8')

    def test_explicit_budget_without_page_rejects_before_read_even_default_and_invalid(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'scripts').mkdir()
            shutil.copyfile(Path(__file__).with_name('jury_read.py'),root/'scripts/jury_read.py')
            # No SKILL/material/helper exists: argument rejection must precede all body reads/imports.
            for budget in ('2048','6144','0','-1'):
                for selection in (['--section','missing.md#never-read'],['--from-plan',str(root/'missing.json')],['--round-context'],['--round-context','--measure']):
                    with self.subTest(budget=budget,selection=selection):
                        result=self.call_reader(selection+['--emit-bytes='+budget],root)
                        self.assertEqual(result.returncode,2,result.stderr)
                        value=json.loads(result.stdout)
                        self.assertEqual(value['status'],'invalid-input')
                        self.assertIn('--emit-page 0',value['reason'])
                        self.assertLess(len(result.stdout.encode('utf-8')),2048)
                        self.assertNotIn('sections',value)
                        self.assertEqual(result.stderr,'')

    def test_no_flag_legacy_and_paired_default_complete_unicode_tail(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'scripts').mkdir()
            shutil.copyfile(Path(__file__).with_name('jury_read.py'),root/'scripts/jury_read.py')
            shutil.copyfile(Path(__file__).with_name('jury_io.py'),root/'scripts/jury_io.py')
            body='# Whole\n'+('必要正文"\\🙂微调\n'*800)+'尾部条件不可丢\n'
            (root/'body.md').write_text(body,encoding='utf-8')
            args=['--section','body.md#Whole']
            plain=self.call_reader(args,root);self.assertEqual(plain.returncode,0,plain.stderr)
            expected=json.loads(plain.stdout);self.assertEqual(expected['status'],'read')
            first=self.call_reader(args+['--emit-page','0'],root)
            page=json.loads(first.stdout);self.assertEqual(page['maxSerializedUtf8Bytes'],6144)
            self.assertLessEqual(len(first.stdout.encode('utf-8')),6144)
            pieces=[page['text']]
            for index in range(1,page['pageCount']):
                result=self.call_reader(args+['--emit-page',str(index),'--expect-emission',page['outputSHA256']],root)
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertLessEqual(len(result.stdout.encode('utf-8')),6144)
                pieces.append(json.loads(result.stdout)['text'])
            self.assertEqual(json.loads(''.join(pieces)),expected)
            self.assertIn('尾部条件不可丢',json.loads(''.join(pieces))['sections'][0]['content'])

    def test_paired_invalid_range_and_round_context_still_reject(self):
        for budget in ('0','-1','2047','1048577'):
            result=self.call_reader(['--section','references/coordination.md#wave-gain','--emit-page','0','--emit-bytes',budget])
            self.assertEqual(result.returncode,2,result.stderr)
            self.assertNotIn('sections',json.loads(result.stdout))
        result=self.call_reader(['--round-context','--emit-page','0','--emit-bytes','2048'])
        self.assertEqual(result.returncode,2,result.stderr)


if __name__ == '__main__':
    unittest.main()
