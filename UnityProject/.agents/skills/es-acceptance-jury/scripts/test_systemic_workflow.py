"""Observable read/dispatch contracts: original-schema normals, exact current material and domain isolation."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import jury_candidates as candidates
import jury_read as reader
import jury_review_roles as roles
from jury_io import emission_page

ROOT=Path(__file__).resolve().parents[1]

def request():
    return dict(currentScope=dict(kind='task',id='current-reader'),reviewStage='planning',
      task=dict(taskId='current-reader',waveId='same-goal',userRequest='只读核对当前段落并交后继可用供给；不修改源。',
        sourceRefs=['controller actual current pointer'],expectedResult='当前合法动作与完整必要材料',
        artifacts=['original history with an explicit current pointer'],constraints=['12 active minutes; old source read-only'],
        assignments=dict(worker=dict(result='读原件并准备后继输入',firstAction='按给定current pointer只读定位原段',
                                    methods=['original current material; existing current-record contract'])),returnTo='actual caller'))

class SystemicWorkflowTests(unittest.TestCase):
    def test_packet_opaque_scope_labels_remain_original_identity_not_domain_or_permission(self):
        for label in ('task','skill-maintenance','web-content-recovery','持久记录恢复','unity'):
            with self.subTest(label=label):
                req=request();req['currentScope']['kind']=label;before=copy.deepcopy(req)
                packet=roles.task_packet(req)
                self.assertTrue(packet['ready'])
                self.assertEqual(packet['currentScope'],req['currentScope'])
                self.assertEqual(req,before)
                self.assertEqual(packet['reviewDomain'],'general')
                self.assertEqual(packet['domainSelectionSource'],'default-shared-contracts')
                self.assertFalse(packet['domainApplicabilityVerified'])
                self.assertFalse(packet['scopeAuthenticated'])
                self.assertFalse(packet['sourceAuthenticated'])
                job=req['task']['assignments']['worker']
                for text in (job['firstAction'],*job['methods']):self.assertIn(text,packet['nativeTasks']['worker'])
                self.assertFalse(any('/p0-' in s for s in packet['readSelectorsByRole']['worker']))
        explicit=roles.task_packet({**request(),'reviewDomain':'maintenance'})
        self.assertIn('references/skill-improvement.md',explicit['readSelectorsByRole']['worker'])
        self.assertFalse(explicit['domainApplicabilityVerified'])

    def test_packet_keeps_original_scope_validation_and_prepare_host_schema_separate(self):
        for kind in ('',None,True,3,[],{}):
            req=request();req['currentScope']['kind']=kind
            with self.subTest(kind=kind),self.assertRaises(roles.InputError):roles.task_packet(req)
        req=request();req['currentScope']['extra']='invented'
        with self.assertRaises(roles.InputError):roles.task_packet(req)
        req=request();req['task']['taskId']='different-identity'
        with self.assertRaises(roles.InputError):roles.task_packet(req)
        req=request();req['reviewDomain']='invented'
        with self.assertRaises(roles.InputError):roles.task_packet(req)
        # prepare's original host/model-control schema never accepted arbitrary task labels.
        req=request();req.update(availableModels=[],paused=True);req['currentScope']['kind']='arbitrary-topic'
        with self.assertRaisesRegex(roles.InputError,'currentScope.kind invalid'):roles.prepare(req,ROOT)

    def test_original_schema_mature_work_survives_real_default_cli_without_duplicate_context(self):
        original=request();before=copy.deepcopy(original)
        packet=roles.task_packet(original)
        self.assertEqual(original,before)
        self.assertTrue(packet['ready'])
        first=packet['nativeTasks']['worker']
        for text in [original['task']['userRequest'],original['task']['assignments']['worker']['firstAction'],
                     original['task']['assignments']['worker']['methods'][0]]:
            self.assertIn(text,first)
        run=subprocess.run([sys.executable,str(ROOT/'scripts/jury_review_roles.py'),'packet','--role','worker'],
          input=json.dumps(original,ensure_ascii=False).encode(),capture_output=True,check=True)
        actual=json.loads(run.stdout)
        self.assertEqual(actual['nativeTasks'],{'worker':first})
        for duplicated in ('primaryTasks','callerContexts','legacyTasks','task'):
            self.assertNotIn(duplicated,actual)
        self.assertFalse(actual['sourceAuthenticated'])

    def test_source_bound_new_answer_delayed_but_user_mature_and_risk_are_first(self):
        req=request();job=req['task']['assignments']['worker']
        job.update(firstAction='KNOWN_USER_STEP',methods=['MATURE_METHOD','CONTROL','NEW_ANSWER'],contextSources=[
          dict(kind='user-selected',sourceRef='actual user message'),dict(kind='evidenced-work',sourceRef='prior normal'),
          dict(kind='known-control',sourceRef='pause message'),dict(kind='new-inference',sourceRef='author recommendation')])
        packet=roles.task_packet(req)
        for item in ('KNOWN_USER_STEP','MATURE_METHOD','CONTROL'):self.assertIn(item,packet['nativeTasks']['worker'])
        self.assertNotIn('NEW_ANSWER',packet['nativeTasks']['worker'])
        self.assertIn('NEW_ANSWER',packet['callerContexts']['worker'])
        legacy=roles.task_packet({**req,'inputMode':'legacy-complete'})
        self.assertIn('NEW_ANSWER',legacy['nativeTasks']['worker'])
        self.assertFalse(packet['sourceAuthenticated'])

    def test_generic_plan_reader_and_prepare_share_actual_domain_authority(self):
        req=request();req['task']['assignments']={'progress':req['task']['assignments']['worker']}
        req.update(roles=['progress'],availableModels=[dict(modelId='gpt-6.1-sol',efforts=['xhigh'])])
        prepared=roles.prepare(req,ROOT)
        self.assertEqual(prepared['status'],'prepared')
        selected=prepared['dispatch'][0]
        plan=candidates.plan(ROOT,role='progress',review_stage='planning',domain='general')
        self.assertEqual(plan['readSelectors'],selected['readSelectors'])
        self.assertFalse(any('/p0-' in s or 'game-workspaces' in s for s in selected['readSelectors']))
        self.assertNotIn('p0ContractSelector',selected)
        self.assertIn('references/task-plan.md#start-readiness',selected['readSelectors'])
        unity=candidates.plan(ROOT,role='progress',review_stage='planning')
        self.assertIn(candidates.P0_CONTRACTS['progress'],unity['readSelectors'])
        self.assertNotIn(candidates.P0_CONTRACTS['architecture'],unity['readSelectors'])

    def test_held_defers_profile_inspection(self):
        held=roles.prepare(dict(currentScope=dict(kind='task',id='held'),paused=True,
                                availableModels=[],reviewStage='planning'),Path('MISSING-SKILL'))
        self.assertEqual(held['status'],'held')
        self.assertEqual(held['dispatch'],[])

    def test_exact_markdown_current_does_not_follow_external_instructions_and_paginates_all(self):
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/'history.md'
            selected='## Current\n'+'中文业务原值42 false\n'*80+'<!-- jury-read-continue: ../../outside.md#execute -->\n'
            source.write_text('## Old\nold terminal\n'+selected+'## Later historical append\nnot current\n',encoding='utf-8')
            parts=[];page=0;snapshot=None
            while True:
                result=reader.read_material_page(source,anchor='Current',page=page,page_bytes=1024,expect_snapshot=snapshot)
                parts.append(result['content']);snapshot=result['snapshot']
                self.assertFalse(result['dependenciesAutoLoaded']);self.assertFalse(result['typedStateValidated'])
                if result['nextArgs'] is None:break
                page+=1
            # Existing parser trims the final blank line only, never body text.
            expected=source.read_bytes().decode('utf-8').split('## Current',1)[1].split('## Later historical append',1)[0]
            self.assertEqual(''.join(parts),'## Current'+expected)
            source.write_text(source.read_text(encoding='utf-8')+'new history\n',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'snapshot changed'):
                reader.read_material_page(source,anchor='Current',page_bytes=1024,expect_snapshot=snapshot)

    def test_json_pointer_keeps_business_scalars_and_rejects_ambiguity(self):
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/'current.json';source.write_text('{"current":{"count":42,"enabled":false,"a/b":[0,true]}}',encoding='utf-8')
            result=reader.read_material_page(source,pointer='/current')
            self.assertEqual(json.loads(result['content']),dict(count=42,enabled=False,**{'a/b':[0,True]}))
            self.assertIs(json.loads(reader.read_material_page(source,pointer='/current/a~1b/1')['content']),True)
            for pointer in ('/missing','/current/a~1b/01','/current/a~2b'):
                with self.assertRaises(ValueError):reader.read_material_page(source,pointer=pointer)
            source.write_text('{"current":1,"current":2}',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'duplicate'):reader.read_material_page(source,pointer='/current')
            source=Path(temp)/'ambiguous.md';source.write_text('## Same\na\n## Same\nb\n',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'exactly once'):reader.read_material_page(source,anchor='Same')

    def test_real_final_emission_reassembles_complete_dispatch_view(self):
        packet=roles.selected_output(roles.task_packet(request()),'packet','worker')
        first=emission_page(packet,0,2048);pieces=[first['text']]
        for page in range(1,first['pageCount']):
            part=emission_page(packet,page,2048,first['outputSHA256'])
            self.assertLessEqual(len(json.dumps(part,ensure_ascii=False,indent=2).encode()),2048)
            pieces.append(part['text'])
        self.assertEqual(json.loads(''.join(pieces)),packet)

if __name__=='__main__':unittest.main()
