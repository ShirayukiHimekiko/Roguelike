"""Exercise real gates in isolated workspaces, including mutation during execution."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest

import learnpack


class PackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'module.py'
        self.source.write_text('VALUE = 2\n', encoding='utf-8')
        self.pack = self.root / 'contract.json'
        self.input = self.root / 'input.json'; self.output = self.root / 'output.json'
        self.input.write_text('{"value": 1}', encoding='utf-8')
        self.output.write_text('{"result": 2}', encoding='utf-8')
        (self.root / 'generated.py').write_text('result = 2\n', encoding='utf-8')
        (self.root / 'check.py').write_text('assert 1 + 1 == 2\n', encoding='utf-8')
        self.data = dict(schemaVersion=1, name='sample-capability', version='1.0.0', scope='fixture',
            status='trialed', capability='Test a bounded module adapter', triggers=['adapter task'], exclusions=['other domains'],
            dependencies=['Python'], sources=[dict(path='module.py',sha256=learnpack.sha(self.source),role='module')],
            input_schema=dict(type='object',required=['value'],properties=dict(value=dict(type='integer',minimum=0)),additionalProperties=False),
            output_schema=dict(type='object',required=['result'],properties=dict(result=dict(type='integer')),additionalProperties=False),
            principles=[dict(id='result',kind='hard',authority='validated_invariant',rule='Return the intended result',why='Preserve API',
                when='This fixture',unless='Contract changed',evidence=[dict(source='module.py',locator='VALUE')],check_ids=['unit'])],
            checks=[dict(id='unit',argv=['python','check.py'],timeout_seconds=3)],
            trials=[dict(task='Generate an adapter',changed_condition='New caller',artifact='generated.py',result='passed',evidence='unit execution')],
            limitations=['Does not certify creative quality'])
        self.save()

    def save(self):
        self.pack.write_text(json.dumps(self.data), encoding='utf-8')

    def run_check(self, execute=True, result=None, consumer_root=None):
        return learnpack.check(SimpleNamespace(pack=self.pack,source_root=self.root,workspace=self.root,
            input=self.input,output=self.output,run_checks=execute,result=result,consumer_root=consumer_root))

    def learning_result(self):
        (self.root/'设计机制.md').write_text('Mechanism and conditions\n',encoding='utf-8')
        self.result_path=self.root/'LEARNING-RESULT.json'
        data=dict(scope='Bounded adapter',design_extraction='设计机制.md',capability_pack='pack',
            transfer_trial=dict(request='Use another caller',artifact='generated.py',outcome='passed',evidence='Recorded trial'),
            mechanical_status='passed',effect_status='observed',limitations=['One caller only'])
        # Real packs live in a directory; preserve the existing file-path CLI coverage too.
        directory=self.root/'pack';directory.mkdir()
        self.pack=directory/'contract.json';self.save()
        self.write_result(data)
        return data

    def write_result(self,data):
        self.result_path.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')

    def test_real_execution_and_explicit_not_executed(self):
        self.assertTrue(self.run_check()['mechanical_passed'])
        self.assertFalse(self.run_check(False)['mechanical_passed'])

    def test_schema_mismatch_blocks_execution(self):
        self.input.write_text('{"value": -1}', encoding='utf-8')
        result=self.run_check()
        self.assertFalse(result['mechanical_passed']);self.assertEqual(result['checks'],[])

    def test_stale_source_and_escape_are_rejected(self):
        self.source.write_text('VALUE = 3\n',encoding='utf-8')
        self.assertFalse(self.run_check()['mechanical_passed'])
        self.data['sources'][0]['path']='../outside.py';self.save()
        self.assertTrue(learnpack.validate(self.pack,self.root)[1])

    def test_failed_command_is_not_accepted(self):
        (self.root/'check.py').write_text('raise SystemExit(4)\n',encoding='utf-8')
        result=self.run_check();self.assertFalse(result['mechanical_passed'])
        self.assertEqual(result['checks'][0]['exit_code'],4)

    def test_timeout_kills_grandchild_and_returns(self):
        # 孙进程继承输出句柄且活得比超时长：旧实现会卡在 communicate()，而且孙进程留下来继续写文件
        marker=self.root/'late.txt'
        child="import time;from pathlib import Path;time.sleep(6);Path('late.txt').write_text('x')"
        (self.root/'check.py').write_text(
            'import subprocess,sys,time\nprint("started",flush=True)\n'
            f'subprocess.Popen([sys.executable,"-c",{child!r}])\ntime.sleep(30)\n',encoding='utf-8')
        self.data['checks'][0]['timeout_seconds']=2;self.save()
        started=time.monotonic();result=self.run_check()
        self.assertLess(time.monotonic()-started,15)
        self.assertFalse(result['mechanical_passed'])
        self.assertIn('timeout',result['checks'][0]['outcome'])
        self.assertIn('started',result['checks'][0]['stdout'])
        time.sleep(6)
        self.assertFalse(marker.exists(),'grandchild survived the timeout')

    def test_timeout_kills_grandchild_even_when_taskkill_is_unavailable(self):
        # GPT 沙盒里 taskkill 不起作用：模拟它失败，只靠直接枚举子孙进程也要杀干净
        if os.name != 'nt':
            self.skipTest('Windows only')
        real_run = subprocess.run

        def no_taskkill(argv, *a, **k):
            if argv and str(argv[0]).lower().startswith('taskkill'):
                raise OSError('taskkill blocked')
            return real_run(argv, *a, **k)
        learnpack.subprocess.run = no_taskkill
        self.addCleanup(setattr, learnpack.subprocess, 'run', real_run)
        self.test_timeout_kills_grandchild_and_returns()

    def test_source_changed_during_execution_is_detected(self):
        (self.root/'check.py').write_text("from pathlib import Path\nPath('module.py').write_text('VALUE = 9\\n')\n",encoding='utf-8')
        result=self.run_check();self.assertFalse(result['mechanical_passed'])
        self.assertTrue(any('source-drift' in e for e in result['issues']))

    def test_contract_changed_during_execution_is_detected(self):
        (self.root/'check.py').write_text("import json\nfrom pathlib import Path\np=Path('contract.json');d=json.loads(p.read_text());d['version']='1.0.1';p.write_text(json.dumps(d))\n",encoding='utf-8')
        self.assertFalse(self.run_check()['mechanical_passed'])

    def test_output_changed_during_execution_is_detected(self):
        (self.root/'check.py').write_text("from pathlib import Path\nPath('output.json').write_text('{}')\n",encoding='utf-8')
        result=self.run_check();self.assertFalse(result['mechanical_passed'])
        self.assertTrue(any('output_schema-changed' in e for e in result['issues']))

    def test_observed_implementation_cannot_become_hard_rule(self):
        self.data['principles'][0]['authority']='observed_implementation';self.save()
        self.assertTrue(learnpack.validate(self.pack,self.root)[1])

    def test_network_schema_refs_are_rejected(self):
        self.data['input_schema']={'$ref':'https://invalid.example/schema'};self.save()
        self.assertTrue(learnpack.validate(self.pack,self.root)[1])

    def test_literal_ref_property_and_fragment_schema_remain_valid(self):
        self.data['input_schema']={'type':'object','required':['$ref'],'properties':{
            '$ref':{'$ref':'#/$defs/value'}},'$defs':{'value':{'const':'https://example.invalid/data'}}}
        self.save()
        self.input.write_text('{"$ref":"https://example.invalid/data"}',encoding='utf-8')
        self.assertTrue(self.run_check()['mechanical_passed'])

    def test_weakened_check_and_version_collision_need_review(self):
        newer=self.root/'new.json';data=copy.deepcopy(self.data)
        data['checks'][0]['argv']=['python','-c','pass']
        newer.write_text(json.dumps(data),encoding='utf-8')
        result=learnpack.compare(self.pack,newer)
        self.assertTrue(result['review_required'])
        self.assertTrue(any(x.get('field')=='checks' for x in result['conflicts']))
        self.assertTrue(any(x.get('field')=='version' for x in result['conflicts']))

    def test_result_unicode_paths_and_separate_consumer_root(self):
        data=self.learning_result()
        host=self.root/'host';host.mkdir()
        (host/'入口.md').write_text('Use the capability\n',encoding='utf-8')
        (self.root/'consumer-proof.json').write_text('{"used":true}',encoding='utf-8')
        data['consumer_trial']=dict(consumer='Fixture host',request='Different caller',entry='入口.md',
            artifact='generated.py',outcome='passed',evidence='consumer-proof.json')
        self.write_result(data)
        result=self.run_check(result='LEARNING-RESULT.json',consumer_root=host)
        self.assertTrue(result['mechanical_passed'],result['issues'])
        self.assertEqual(result['learning_result']['consumer_outcome'],'passed')
        self.assertFalse(result['learning_result']['actual_execution_verified'])
        self.assertFalse(result['learning_result']['learning_coverage_verified'])

    def test_auto_result_broken_design_link_blocks_before_command(self):
        data=self.learning_result()
        data['design_extraction']='research/P03-?????????.md';self.write_result(data)
        (self.root/'check.py').write_text("from pathlib import Path\nPath('executed').write_text('yes')\n",encoding='utf-8')
        # The result beside the pack is discovered by the existing check invocation.
        self.result_path.rename(self.pack.parent/'LEARNING-RESULT.json')
        result=self.run_check()
        self.assertFalse(result['mechanical_passed'])
        self.assertEqual(result['checks'],[])
        self.assertFalse((self.root/'executed').exists())
        self.assertTrue(any('design_extraction' in issue for issue in result['issues']))

    def test_result_pack_identity_and_empty_design_are_not_accepted(self):
        data=self.learning_result()
        data['capability_pack']='.';self.write_result(data)
        self.assertFalse(self.run_check(result=self.result_path)['mechanical_passed'])
        data['capability_pack']='pack';self.write_result(data)
        (self.root/'设计机制.md').write_text('',encoding='utf-8')
        self.assertFalse(self.run_check(result=self.result_path)['mechanical_passed'])

    def test_passed_result_must_bind_an_existing_declared_trial(self):
        data=self.learning_result()
        (self.root/'unrelated.py').write_text('pass\n',encoding='utf-8')
        data['transfer_trial']['artifact']='unrelated.py';self.write_result(data)
        result=self.run_check(result=self.result_path)
        self.assertFalse(result['mechanical_passed'])
        self.assertTrue(any('matching passed contract trial' in issue for issue in result['issues']))

    def test_missing_consumer_evidence_and_escape_block(self):
        data=self.learning_result()
        data['consumer_trial']=dict(consumer='Fixture',request='Reuse',entry='check.py',artifact='generated.py',
            outcome='passed',evidence='missing.json')
        self.write_result(data)
        self.assertFalse(self.run_check(result=self.result_path)['mechanical_passed'])
        data['consumer_trial']['evidence']='../outside.json';self.write_result(data)
        self.assertFalse(self.run_check(result=self.result_path)['mechanical_passed'])

    def test_unobserved_consumer_is_preserved_without_fabricated_completion(self):
        data=self.learning_result()
        data['consumer_trial']=dict(consumer='Pending host',request='Reuse',entry='future.py',artifact='future.png',
            outcome='unobserved',evidence='future.json')
        self.write_result(data)
        result=self.run_check(result=self.result_path)
        self.assertTrue(result['mechanical_passed'],result['issues'])
        self.assertEqual(result['learning_result']['consumer_outcome'],'unobserved')

    def test_result_mutation_during_checks_is_detected(self):
        self.learning_result()
        (self.root/'check.py').write_text("import json\nfrom pathlib import Path\np=Path('LEARNING-RESULT.json')\nd=json.loads(p.read_text(encoding='utf-8'));d['scope']='Changed';p.write_text(json.dumps(d),encoding='utf-8')\n",encoding='utf-8')
        result=self.run_check(result=self.result_path)
        self.assertFalse(result['mechanical_passed'])
        self.assertTrue(any('learning-result-changed-during-checks' in issue for issue in result['issues']))

    def cli(self, *arguments, tool=None):
        run = subprocess.run([sys.executable, '-X', 'utf8', '-B', str(tool or Path(learnpack.__file__)),
                              *map(str, arguments)], cwd=self.root, capture_output=True, text=True,
                             encoding='utf-8', timeout=15)
        return run.returncode, json.loads(run.stdout)

    def cli_check(self, report, *extra, tool=None):
        return self.cli('check', self.pack, '--source-root', self.root, '--workspace', self.root,
                        '--input', self.input, '--output', self.output, '--run-checks',
                        '--report', report, *extra, tool=tool)

    def test_compare_boundaries_and_evidence_are_classified(self):
        newer = self.root / 'new.json'
        for field in ('triggers', 'exclusions', 'limitations', 'status', 'trials'):
            with self.subTest(field=field):
                data = copy.deepcopy(self.data)
                if field == 'status':
                    data[field] = 'adopted'
                elif field == 'trials':
                    data[field][0]['evidence'] = 'Withdrawn; earlier execution cannot be verified'
                else:
                    data[field] = ['Different applicable boundary']
                newer.write_text(json.dumps(data), encoding='utf-8')
                result = learnpack.compare(self.pack, newer)
                self.assertTrue(result['review_required'])
                entry = next(item for item in result['conflicts'] if item.get('field') == field)
                self.assertEqual(entry.get('category') == 'evidence_or_adoption', field in ('status', 'trials'))
                self.assertEqual(any(item.get('field') == 'version' for item in result['conflicts']),
                                 field not in ('status', 'trials'))

    def test_compare_identical_and_version_only_do_not_invent_conflicts(self):
        self.assertFalse(learnpack.compare(self.pack, self.pack)['review_required'])
        newer = self.root / 'new.json'
        data = copy.deepcopy(self.data); data['version'] = '1.0.1'
        newer.write_text(json.dumps(data), encoding='utf-8')
        self.assertFalse(learnpack.compare(self.pack, newer)['review_required'])

    def test_compare_refuses_duplicate_ids_that_would_hide_changes(self):
        newer = self.root / 'new.json'
        data = copy.deepcopy(self.data); data['version'] = '1.1.0'
        changed = copy.deepcopy(data['principles'][0]); changed['rule'] = 'Return anything'
        data['principles'] = [changed, copy.deepcopy(self.data['principles'][0])]
        newer.write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaises(ValueError):
            learnpack.compare(self.pack, newer)

    def test_non_finite_and_deeply_nested_json_are_rejected(self):
        bad = self.root / 'bad.json'
        bad.write_text('{"v": 1e400}', encoding='utf-8')
        with self.assertRaises(ValueError):
            learnpack.read_json(bad)
        bad.write_text('[' * 100000 + ']' * 100000, encoding='utf-8')
        command = subprocess.run([sys.executable, '-B', learnpack.__file__, 'validate', str(bad), '--source-root', str(self.root)],
                                 capture_output=True, timeout=30)
        self.assertEqual(command.returncode, 2)
        report = json.loads(command.stdout.decode('ascii'))
        self.assertFalse(report['structure_and_sources_passed'])

    def test_cli_stdout_is_ascii_json_under_any_console_encoding(self):
        env = {k: v for k, v in os.environ.items() if k not in ('PYTHONUTF8', 'PYTHONIOENCODING')}
        command = subprocess.run([sys.executable, '-B', learnpack.__file__, 'validate', str(self.root / '缺失😀.json'),
                                  '--source-root', str(self.root)], capture_output=True, timeout=30, env=env)
        self.assertEqual(command.returncode, 2)
        report = json.loads(command.stdout.decode('ascii'))
        self.assertIn('缺失😀', report['error'])

    def test_workspace_root_pack_reference_and_traversal_controls(self):
        data = self.learning_result()
        self.pack = self.root / 'contract.json'; self.save()
        data['capability_pack'] = '.'; self.write_result(data)
        self.assertTrue(self.run_check(result=self.result_path)['mechanical_passed'])
        for invalid in ('..', '../pack', './pack', str(self.root), 'pack\\child', 'C:/pack'):
            with self.subTest(path=invalid):
                data['capability_pack'] = invalid; self.write_result(data)
                self.assertFalse(self.run_check(result=self.result_path)['mechanical_passed'])
        # Only pack identity permits '.', not arbitrary file references.
        data['capability_pack'] = '.'; data['design_extraction'] = './设计机制.md'; self.write_result(data)
        self.assertFalse(self.run_check(result=self.result_path)['mechanical_passed'])

    def test_report_protects_declared_files_before_checks(self):
        data = self.learning_result()
        host = self.root / 'host'; host.mkdir()
        entry = host / 'entry.py'; entry.write_text('pass\n', encoding='utf-8')
        evidence = self.root / 'consumer.json'; evidence.write_text('{}', encoding='utf-8')
        data['consumer_trial'] = dict(consumer='host', request='Reuse', entry='entry.py',
            artifact='generated.py', outcome='passed', evidence='consumer.json')
        self.write_result(data)
        skill = self.pack.parent / 'SKILL.md'; skill.write_text('Bounded use', encoding='utf-8')
        checker = self.root / 'check.py'
        checker.write_text("from pathlib import Path\nPath('executed').write_text('yes')\n", encoding='utf-8')
        for target in (self.pack, self.source, self.input, self.output, self.result_path,
                       self.root/'设计机制.md', self.root/'generated.py', entry, evidence, skill, checker):
            with self.subTest(target=target.name):
                before = target.read_bytes()
                code, result = self.cli_check(target, '--result', self.result_path, '--consumer-root', host)
                self.assertEqual(code, 2, result)
                self.assertIn('protected', result['error'])
                self.assertEqual(target.read_bytes(), before)
                self.assertFalse((self.root/'executed').exists())

    def test_report_protects_automatic_result(self):
        self.learning_result()
        automatic = self.pack.parent / 'LEARNING-RESULT.json'; self.result_path.rename(automatic)
        before = automatic.read_bytes()
        code, result = self.cli_check(automatic)
        self.assertEqual(code, 2, result); self.assertEqual(automatic.read_bytes(), before)

    def test_report_protects_hardlinks_and_directory_artifacts(self):
        directory = self.root / 'proofs'; directory.mkdir()
        proof = directory / 'proof.txt'; proof.write_text('actual evidence', encoding='utf-8')
        self.data['trials'][0]['artifact'] = 'proofs'; self.save()
        alias = self.root / 'other-name'; os.link(proof, alias)
        for target in (proof, directory/'new-report.json', alias):
            with self.subTest(target=target.name):
                code, result = self.cli_check(target)
                self.assertEqual(code, 2, result)
                self.assertEqual(proof.read_text(encoding='utf-8'), 'actual evidence')
        self.assertFalse((directory/'new-report.json').exists())

    def test_report_symlink_alias_when_supported(self):
        alias = self.root / 'source-link'
        try:
            alias.symlink_to(self.source)
        except OSError as exc:
            self.skipTest('Symlink creation unavailable: ' + str(exc))
        before = self.source.read_bytes()
        code, result = self.cli_check(alias)
        self.assertEqual(code, 2, result); self.assertEqual(self.source.read_bytes(), before)

    def test_report_rechecks_alias_created_by_check(self):
        alias = self.root / 'late-alias.json'
        (self.root/'check.py').write_text("import os\nos.link('module.py', 'late-alias.json')\n", encoding='utf-8')
        before = self.source.read_bytes()
        code, result = self.cli_check(alias)
        self.assertEqual(code, 2, result); self.assertIn('protected', result['error'])
        self.assertEqual(self.source.read_bytes(), before)

    def test_safe_report_can_create_update_and_report_failed_checks(self):
        report = self.root / 'report.json'
        for _ in range(2):
            code, result = self.cli_check(report)
            self.assertEqual(code, 0, result)
            self.assertEqual(json.loads(report.read_text(encoding='utf-8')), result)
        (self.root/'check.py').write_text('raise SystemExit(7)\n', encoding='utf-8')
        code, result = self.cli_check(report)
        self.assertEqual(code, 2); self.assertFalse(result['mechanical_passed'])
        self.assertEqual(json.loads(report.read_text(encoding='utf-8')), result)
        with tempfile.TemporaryDirectory() as other:
            code, result = self.cli_check(Path(other)/'outside-report.json')
            self.assertEqual(code, 2); self.assertEqual(result['checks'][0]['exit_code'], 7)
            self.assertTrue((Path(other)/'outside-report.json').is_file())

    def test_inline_check_code_is_not_treated_as_a_file_path(self):
        self.data['checks'][0]['argv'] = ['python', '-c', 'assert True\n#' + 'x'*1000]
        self.save()
        code, result = self.cli_check(self.root/'report.json')
        self.assertEqual(code, 0, result)

    def test_script_options_do_not_hide_configuration_files(self):
        config = self.root/'check-config.json'
        config.write_text('{"expected":true}', encoding='utf-8')
        (self.root/'reader.py').write_text(
            "import json,sys\nfrom pathlib import Path\n"
            "assert json.loads(Path(sys.argv[-1]).read_text())['expected']\n"
            "Path('reader-executed').write_text('yes')\n", encoding='utf-8')
        for prefix in (['reader.py'], ['-B', '-X', 'utf8', 'reader.py'], ['--', 'reader.py']):
            for option in ('-m', '-c'):
                with self.subTest(prefix=prefix, option=option):
                    self.data['checks'][0]['argv'] = ['python', *prefix, option, 'check-config.json']
                    self.save()
                    before = config.read_bytes()
                    code, result = self.cli_check(config)
                    self.assertEqual(code, 2, result); self.assertIn('protected', result['error'])
                    self.assertEqual(config.read_bytes(), before)
                    self.assertFalse((self.root/'reader-executed').exists())
        code, result = self.cli_check(self.root/'safe-report.json')
        self.assertEqual(code, 0, result)
        self.assertTrue((self.root/'reader-executed').is_file())

    def test_real_interpreter_payload_is_distinct_from_following_file_args(self):
        # 'pass' is Python code even if a file happens to have that name.
        code_file = self.root/'pass'; code_file.write_text('not Python source', encoding='utf-8')
        self.data['checks'][0]['argv'] = ['python', '-B', '-X', 'utf8', '-c', 'pass']
        self.save()
        code, result = self.cli_check(code_file)
        self.assertEqual(code, 0, result)
        config = self.root/'extra.json'; config.write_text('{}', encoding='utf-8')
        self.data['checks'][0]['argv'].append('extra.json'); self.save()
        code, result = self.cli_check(config)
        self.assertEqual(code, 2, result)
        self.assertEqual(config.read_text(encoding='utf-8'), '{}')

    def test_failed_trial_missing_artifact_does_not_block_safe_report(self):
        failed = copy.deepcopy(self.data['trials'][0])
        failed.update(result='failed', artifact='never-created.py')
        self.data['trials'].append(failed); self.save()
        code, result = self.cli_check(self.root/'report.json')
        self.assertEqual(code, 0, result)
        self.assertFalse((self.root/'never-created.py').exists())
        code, result = self.cli_check(self.root/'never-created.py')
        self.assertEqual(code, 2, result)
        self.assertFalse((self.root/'never-created.py').exists())

    def test_report_failure_does_not_overwrite_bad_input(self):
        self.input.write_text('{bad json', encoding='utf-8')
        before = self.input.read_bytes()
        code, result = self.cli_check(self.input)
        self.assertEqual(code, 2, result); self.assertEqual(self.input.read_bytes(), before)
        code, result = self.cli_check(self.root/'safe-error.json')
        self.assertEqual(code, 2, result)
        self.assertFalse(result['mechanical_passed']); self.assertEqual(result['checks'], [])

    def test_report_cannot_overwrite_tool_or_schemas(self):
        toolroot = self.root / 'isolated-tool'
        shutil.copytree(Path(learnpack.__file__).resolve().parents[1], toolroot)
        tool = toolroot / 'scripts' / 'learnpack.py'
        for target in (tool, *(toolroot/'assets').glob('*.json')):
            with self.subTest(target=target.name):
                before = target.read_bytes()
                code, result = self.cli_check(target, tool=tool)
                self.assertEqual(code, 2, result); self.assertEqual(target.read_bytes(), before)

    def test_fingerprint_rejects_source_aliases_but_keeps_safe_output(self):
        alias = self.root / 'source-alias'; os.link(self.source, alias)
        before = self.source.read_bytes()
        for target in (self.source, alias):
            code, result = self.cli('fingerprint', '--source-root', self.root, '--file', 'module.py', '--out', target)
            self.assertEqual(code, 2, result); self.assertEqual(self.source.read_bytes(), before)
        target = self.root / 'sources.json'
        for _ in range(2):
            code, result = self.cli('fingerprint', '--source-root', self.root, '--file', 'module.py', '--out', target)
            self.assertEqual(code, 0, result)
            self.assertEqual(json.loads(target.read_text(encoding='utf-8'))[0]['sha256'], learnpack.sha(self.source))

    def test_fingerprint_cannot_destroy_its_own_tool_or_schemas(self):
        toolroot = self.root/'isolated-tool'
        shutil.copytree(Path(learnpack.__file__).resolve().parents[1], toolroot)
        tool = toolroot/'scripts/learnpack.py'
        alias = self.root/'helper-alias'; os.link(tool, alias)
        for target in (tool, alias, *(toolroot/'assets').glob('*.json')):
            with self.subTest(target=target.name):
                before = target.read_bytes()
                code, result = self.cli('fingerprint', '--source-root', self.root, '--file', 'module.py',
                                        '--out', target, tool=tool)
                self.assertEqual(code, 2, result); self.assertIn('protected', result['error'])
                self.assertEqual(target.read_bytes(), before)
        code, result = self.cli('fingerprint', '--source-root', self.root, '--file', 'module.py',
                                '--out', self.root/'safe.json', tool=tool)
        self.assertEqual(code, 0, result)


if __name__=='__main__':
    unittest.main()
