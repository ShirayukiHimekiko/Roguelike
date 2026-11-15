import copy
import contextlib
import io
import json
import shlex
import unittest
import jury_review_roles as roles


def task(first_action='先改作者建议的厚肩参数', methods=None):
    return {'currentScope': {'kind': 'maintenance', 'id': 'actual-case'}, 'reviewStage': 'planning', 'reviewDomain': 'maintenance',
            'task': {'taskId': 'actual-case', 'waveId': 'current-wave',
                     'userRequest': '完成整幅设计和真实后继；原图已失败。保留既有合格小修。',
                     'sourceRefs': ['actual original request'], 'expectedResult': '完整结果及原接回',
                     'artifacts': ['complete failed image and editable source'],
                     'constraints': ['known actual original product pause; independent owned research allowed'],
                     'assignments': {'architecture': {'result': '独立核路线及首个可消费结果',
                                                    'firstAction': first_action,
                                                    'methods': methods or ['author proposed local parameter control']}},
                     'returnTo': 'real current caller'}}


class NativePacketConsumptionTests(unittest.TestCase):
    def test_prepare_default_and_selected_view_forward_same_canonical_text(self):
        request=task(); request['currentScope']['kind']='task'
        request['availableModels']=[{'modelId':'gpt-6.1-sol','efforts':['xhigh']}]
        request['roles']=['architecture']
        core=roles.Path(roles.__file__).resolve().parents[1]
        prepared=roles.prepare(request,core)
        self.assertEqual(prepared['status'],'prepared')
        view=roles.selected_output(prepared,'prepare')
        text=view['dispatch'][0]['taskText']
        self.assertIn('--profile maintenance --role architecture --review-stage planning',text)
        self.assertIn('sections[].content',text)
        self.assertIn('nextArgs=null',text)
        self.assertIn('先改作者建议的厚肩参数',text)

    def test_forwarded_text_has_selected_canonical_route_for_each_actual_role(self):
        for domain in ('general', 'maintenance', 'unity'):
            for stage in ('planning', 'review'):
                request=task('使用用户指定读取器完成完整原件读取', ['user chosen tool'])
                request['reviewDomain']=domain; request['reviewStage']=stage
                job=request['task']['assignments']['architecture']
                request['task']['assignments']={role:copy.deepcopy(job) for role in roles.TASK_ROLES}
                packet=roles.task_packet(request)
                for role,text in packet['nativeTasks'].items():
                    self.assertIn('--profile '+domain+' --role '+role+' --review-stage '+stage,text)
                    self.assertIn(str(roles.Path(roles.__file__).resolve().parent/'jury_read.py'),text)
                    self.assertIn('sections[].content',text)
                    self.assertIn('expect-snapshot',text)
                    self.assertIn('nextArgs=null',text)
                    self.assertIn('--material-file',text)
                    self.assertIn('未给则先核原件，不猜current',text)
                    self.assertIn('user chosen tool',text)
                    self.assertFalse(packet['autoExecute'])
                request['inputMode']='legacy-complete'
                legacy=roles.task_packet(request)['nativeTasks']['architecture']
                self.assertIn('--profile '+domain,legacy)
                self.assertIn('使用用户指定读取器完成完整原件读取',legacy)

    def test_actual_native_stage_handoff_command_resolves_for_each_stage_and_input_mode(self):
        # Verify the forwarded material, not an unused prepare metadata field.
        selector='references/review-completion.md#stage-continuation'
        core=roles.Path(roles.__file__).resolve().parents[1]
        for stage in ('planning','review'):
            for mode in ('independent-first','legacy-complete'):
                request=task('使用原已授权作者入口接当前工作', ['original owner source'])
                request['reviewStage']=stage;request['inputMode']=mode
                packet=roles.task_packet(request,core)
                native=packet['nativeTasks']['architecture']
                command=next(line for line in native.splitlines() if ' --section '+selector in line)
                output=io.StringIO()
                with contextlib.redirect_stdout(output):
                    status=roles.reader.main(['--section',*shlex.split(command.split(' --section ',1)[1])])
                self.assertEqual(status,0)
                resolved=json.loads(output.getvalue())
                selected={item['selector'] for item in resolved['sections']}
                self.assertIn(selector,selected)
                self.assertIn('references/must-read-work-priority.md#partial-result-continuation',selected)
                self.assertFalse(packet['autoExecute'])
                request['currentScope']['kind']='task'  # prepare uses the existing host-container contract.
                request['availableModels']=[{'modelId':'gpt-6.1-sol','efforts':['xhigh']}]
                request['roles']=['architecture']
                prepared=roles.prepare(request,core)
                actual=roles.selected_output(prepared,'prepare')['dispatch'][0]['taskText']
                self.assertEqual(actual,packet['nativeTasks']['architecture'])
                self.assertEqual(actual.count(' --section '+selector),1)

    def test_original_schema_retained_and_answer_context_separately_consumable(self):
        request = task(); request['task']['assignments']['architecture']['contextSources'] = [
            {'kind':'new-inference','sourceRef':'actual author proposal'},
            {'kind':'new-inference','sourceRef':'actual author proposal'}]
        original = copy.deepcopy(request)
        packet = roles.task_packet(request)
        self.assertEqual(request, original)
        self.assertTrue(packet['ready'])
        self.assertIn(request['task']['userRequest'], packet['primaryTasks']['architecture'])
        self.assertIn(request['task']['constraints'][0], packet['primaryTasks']['architecture'])
        self.assertNotIn(request['task']['assignments']['architecture']['firstAction'], packet['primaryTasks']['architecture'])
        self.assertIn(request['task']['assignments']['architecture']['firstAction'], packet['callerContexts']['architecture'])
        self.assertNotIn(request['task']['assignments']['architecture']['firstAction'], packet['nativeTasks']['architecture'])
        self.assertIn(request['task']['assignments']['architecture']['firstAction'], packet['legacyTasks']['architecture'])
        self.assertTrue(packet['contextSourceResolved'])
        self.assertFalse(packet['sourceAuthenticated'])
        self.assertFalse(packet['semanticContentVerified'])

    def test_user_explicit_method_and_known_safe_normal_remain_first_input(self):
        request = task('仅修已有成熟基线的绑定，不重学工艺', ['original mature baseline and binding source'])
        request['task']['userRequest'] = '用户明确：先用指定CLI只读核绑定，再修已有成熟基线的绑定；原流程与性能不改。'
        request['task']['expectedResult'] = '原成熟完整流程恢复，保全部接口'
        packet = roles.task_packet(request)
        primary = packet['primaryTasks']['architecture']
        self.assertIn('先用指定CLI只读核绑定', primary)
        self.assertIn(request['task']['expectedResult'], primary)
        self.assertIn(request['task']['assignments']['architecture']['result'], primary)
        self.assertIn('原流程与性能不改', primary)
        # The helper retains source-unresolved work for the real caller; it never blocks a method by origin guess.
        self.assertIn(request['task']['assignments']['architecture']['firstAction'], packet['nativeTasks']['architecture'])
        self.assertFalse(packet['autoExecute'])

    def test_unresolved_stage_still_defers_material_choice_without_new_user_approval(self):
        request = task(); request.pop('reviewStage')
        packet = roles.task_packet(request)
        self.assertFalse(packet['ready'])
        self.assertEqual(packet['status'], 'stage-unresolved')
        self.assertEqual(packet['nativeTasks'], {})


if __name__ == '__main__': unittest.main()
