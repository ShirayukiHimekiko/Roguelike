import copy
import json
from pathlib import Path
import tempfile
import unittest

import jury_candidates as candidates
import jury_review_roles as roles
import jury_session as session


class MechanismTests(unittest.TestCase):
    def ground(self,label):
        return dict(source='actual '+label+' source',evidence='observed '+label+' with limits',disposition='keep only supported '+label,action='perform the next '+label+' action')

    def opinion(self,role='progress'):
        return dict(id='current-'+role,taskId='task',waveId='wave',role=role,actor='actor-'+role,
          state='real current feedback',scope='legitimate '+role+' scope',gain=-7,event='original event',
          judgment='This result is supported only under the stated conditions.',
          basis=dict(userNeed=self.ground('need'),actualUse=self.ground('use')),
          open=[],conditions=[],limits=['keep this necessary limitation'],next='actual next action',decision='allow')

    def source(self,root,role='progress'):
        path=root/(role+'.md');op=self.opinion(role)
        path.write_text('# history\n\n```jury-opinion\n'+json.dumps(op,ensure_ascii=False,indent=2)+'\n```\n',encoding='utf-8')
        return path,session.select_opinion(str(path),op['id'],'task','wave')

    def record(self,root,opinions):
        state=dict(schemaVersion=1,taskId='task',waveId='wave',participants=[x['role'] for x in opinions],scope='current bounded result',
          events=['accepted','progress'],requiredRoles=['progress'],opinions=opinions,
          progress=dict(done=['actual result'],active=[],todo=[],blocked=[],next=dict(owner='worker',result='consume the real result')))
        path=root/'state.json';path.write_text(json.dumps(state,ensure_ascii=False),encoding='utf-8')
        return path,state

    def test_stage_and_real_work_are_not_silently_guessed(self):
        self.assertEqual(candidates.plan()['status'],'stage-unresolved')
        self.assertEqual(roles.prepare(dict(currentScope=dict(kind='task',id='task'),availableModels=[]),Path('missing'))['status'],'stage-unresolved')
        task=dict(taskId='task',waveId='wave',userRequest='Real requested outcome',sourceRefs=['original message'],expectedResult='consumer result',
          artifacts=['real artifact'],constraints=['preserve existing work'],returnTo='actual owner',
          assignments=dict(progress=dict(result='use the real object',firstAction='inspect its actual consumer',methods=['role method'])))
        observation=dict(currentScope=dict(kind='task',id='task'),reviewStage='review',task=task)
        result=roles.task_packet(observation)
        self.assertEqual(result['reviewStage'],'review')
        self.assertIn('Real requested outcome',result['nativeTasks']['progress'])
        self.assertIn('inspect its actual consumer',result['nativeTasks']['progress'])
        self.assertFalse(result['sourceAuthenticated'])
        observation.pop('reviewStage');self.assertEqual(roles.task_packet(observation)['status'],'stage-unresolved')

    def test_current_selection_preserves_optional_limits_and_tolerates_history_append(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source,op=self.source(root);path,state=self.record(root,[op])
            initial=session.probe_record(path,'user','accepted',expected_task='task',expected_wave='wave')
            self.assertIn('原记录声明允许收尾',initial['messageText'])
            with source.open('a',encoding='utf-8') as stream:stream.write('\nUnrelated preserved history append.\n')
            self.assertTrue(session.probe_record(path,'user',expected_task='task',expected_wave='wave')['passed'])
            for key in ('open','conditions','limits','next'):
                modified=copy.deepcopy(state);modified['opinions'][0].pop(key)
                path.write_text(json.dumps(modified),encoding='utf-8')
                with self.assertRaisesRegex(ValueError,'rewritten'):session.probe_record(path,'user',expected_task='task',expected_wave='wave')

    def test_hidden_nested_duplicate_and_wrong_wave_cannot_supply_current_opinion(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source,op=self.source(root);original=source.read_text(encoding='utf-8')
            for wrapped in ('<!--\n'+original+'\n-->','<pre>\n'+original+'\n</pre>','````text\n'+original+'\n````','\n'.join('> '+x for x in original.splitlines())):
                source.write_text(wrapped,encoding='utf-8')
                with self.assertRaises(ValueError):session.select_opinion(source,'current-progress','task','wave')
            source.write_text(original+original,encoding='utf-8')
            with self.assertRaises(ValueError):session.select_opinion(source,'current-progress','task','wave')
            source.write_text(original,encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'task-wave'):session.select_opinion(source,'current-progress','task','other-wave')

    def test_pointer_only_basis_is_not_a_current_personal_response(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'source.json';op=self.opinion();op['basis']['actualUse']={'source':'pointer only'}
            path.write_text(json.dumps(op),encoding='utf-8')
            with self.assertRaises(ValueError):session.select_opinion(path,op['id'],'task','wave')

    def test_known_owner_revision_requires_explicit_current_head_not_last_timestamp(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'owner.md';first=self.opinion();second=dict(self.opinion(),id='owner-next-result',judgment='a real revised result')
            def block(marker,value):return '```'+marker+'\n'+json.dumps(value)+'\n```\n'
            body=block('jury-opinion',first)+block('jury-opinion',second);path.write_text(body,encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'explicit'):session.select_opinion(path,first['id'],'task','wave')
            head=dict(taskId='task',waveId='wave',role='progress',actor=first['actor'],currentOpinionId=second['id'],supersedes=[first['id']])
            path.write_text(body+block('jury-current',head),encoding='utf-8')
            self.assertEqual(session.select_opinion(path,second['id'],'task','wave')['judgment'],second['judgment'])
            with self.assertRaisesRegex(ValueError,'superseded'):session.select_opinion(path,first['id'],'task','wave')
            self.assertEqual(session.select_opinion(path,first['id'],'task','wave',historical=True)['judgment'],first['judgment'])

    def test_all_four_sources_visible_but_worker_and_dialogue_are_not_review_quorum(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);ops=[self.source(root,role)[1] for role in ('worker','progress','architecture','dialogue')];path,state=self.record(root,ops)
            result=session.probe_record(path,'user','progress',expected_task='task',expected_wave='wave')
            self.assertEqual(result['messageText'].count('🔎考虑到｜用户需求偏移'),4)
            self.assertEqual(result['messageText'].count('🔎考虑到｜真实的视觉理解'),4)
            for role in ('worker','dialogue'):
                with self.assertRaises(ValueError):session._validate_probe({**state,'requiredRoles':[role]})
            state['opinions'].pop();path.write_text(json.dumps(state),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'missing'):session.probe_record(path,'user',expected_task='task',expected_wave='wave')

    def test_draft_requires_full_visible_body_not_metadata_titles_or_hidden_copy(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);_,op=self.source(root);path,_=self.record(root,[op]);draft=root/'draft.md'
            projected=session.probe_record(path,'user','progress',expected_task='task',expected_wave='wave')['messageText']
            for bad in ('passed=true sources=1','用户需求偏移 / 真实的视觉理解','```text\n'+projected+'\n```','<!--\n'+projected+'\n-->',projected.replace('keep this necessary limitation','')):
                draft.write_text(bad,encoding='utf-8')
                self.assertFalse(session.check_user_view(path,draft,'task','wave','progress')['passed'])
            draft.write_text('Actual user introduction.\n\n'+projected+'\nActual next step.',encoding='utf-8')
            self.assertTrue(session.check_user_view(path,draft,'task','wave','progress')['passed'])

    def test_unknown_or_refuted_claim_cannot_support_allowed_action(self):
        prop=dict(id='p',claim='tool declaration proves actual effect',status='unknown',evidenceRefs=[],conditions='unobserved',affectedActions=['publish'],owner='worker',nextAction='obtain actual consumer evidence')
        state=dict(schemaVersion=1,propositions=[prop],adoptions=[dict(action='publish',owner='root',propositionIds=['p'],state='allowed')])
        with self.assertRaises(ValueError):session._validate_probe(state)
        state['adoptions'][0]['state']='held';session._validate_probe(state)
        prop.update(status='observed',evidenceRefs=['actual evidence']);state['adoptions'][0]['state']='allowed';session._validate_probe(state)

    def test_dialogue_response_binds_both_real_source_blocks_and_survives_compose(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);fpath,fop=self.source(root);dpath,dop=self.source(root,'dialogue')
            raw=self.opinion('dialogue');raw['responses']=[dict(to=fop['id'],blockSha256=fop['sourceSelection']['blockSha256'],**self.ground('root adopts this exact source'))]
            dpath.write_text(json.dumps(raw),encoding='utf-8');dop=session.select_opinion(dpath,raw['id'],'task','wave')
            path,state=self.record(root,[fop,dop]);selections=[(fpath,fop['id']),(dpath,dop['id'])]
            direct=session.probe_record(path,'user','progress',expected_task='task',expected_wave='wave')
            self.assertIn('主交流对本来源的处置',direct['messageText'])
            result=session.compose_record(path,selections,'task','wave','progress')
            self.assertEqual(result['facts']['opinions'][0]['response']['disposition'],raw['responses'][0]['disposition'])
            self.assertIn('主交流对本来源的处置',result['messageText'])
            path.write_text(json.dumps(result['facts']),encoding='utf-8')
            self.assertIn('主交流对本来源的处置',session.probe_record(path,'user',expected_task='task',expected_wave='wave')['messageText'])
            with fpath.open('a',encoding='utf-8') as stream:stream.write('\nUnrelated history append.\n')
            self.assertTrue(session.compose_record(path,selections,'task','wave')['passed'])
            changed=self.opinion();changed['limits']=['a new necessary restriction'];fpath.write_text(json.dumps(changed),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'target changed'):session.compose_record(path,selections,'task','wave')

    def test_expected_identity_rejects_stale_current_scope_even_with_same_event(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);_,op=self.source(root);path,state=self.record(root,[op])
            with self.assertRaisesRegex(ValueError,'task-wave'):session.probe_record(path,'user','progress',expected_task='task',expected_wave='new-wave')
            with self.assertRaisesRegex(ValueError,'expected taskId'):session.probe_record(path,'user','progress')
            legacy=root/'legacy.json';legacy.write_text(json.dumps(dict(schemaVersion=1,events=['planning-start'])),encoding='utf-8')
            self.assertTrue(session.probe_record(legacy)['passed'])
            with self.assertRaises(ValueError):session.probe_record(legacy,'user','planning-start',expected_task='task',expected_wave='wave')

    def test_consideration_names_and_reply_are_not_replaced_by_two_basis_titles(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);_,op=self.source(root);path,state=self.record(root,[op])
            item=dict(id='request',name='preserve real source limits',kind='request',sourceRef='actual request',owner='actual reviewer',request='check this explicit concern',state='open',nextAction='send and obtain the real answer',limitedActions=['adopt'])
            state['considerations']=[item];path.write_text(json.dumps(state),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'unanswered'):session.probe_record(path,'user','accepted',expected_task='task',expected_wave='wave')
            item.update(state='answered',response=self.ground('same-name actual reply'));path.write_text(json.dumps(state),encoding='utf-8')
            text=session.probe_record(path,'user','accepted',expected_task='task',expected_wave='wave')['messageText']
            self.assertIn('🧩请考虑｜preserve real source limits',text);self.assertIn('同名实答｜preserve real source limits',text)

    def test_original_review_result_releases_only_wrong_veto_and_preserves_true_one(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);evidence=root/'evidence.txt';evidence.write_text('Actual distinguishing observation.',encoding='utf-8')
            risks=[dict(id=name,source='controlled case',status='proven',impact=name,limitedActions=[name+'-action'],next=dict(owner='worker',action='investigate'),resume='original reviewer result',urgent=False,closureOwner='actor-architecture') for name in ('wrong','true')]
            state=dict(schemaVersion=1,taskId='task',waveId='wave',risks=risks,events=[])
            for name in ('wrong','true'):
                state=session.review_transition(state,dict(action='challenge',riskId=name,actor='worker',sourceRef='explicit controlled premise',proposition=name,question='distinguish premise',affectedAction=name+'-action',evidenceOwner='worker',evidenceAction='perform observation'),'task','wave')['facts']
                state=session.review_transition(state,dict(action='evidence',riskId=name,actor='worker',sourceRef=str(evidence)),'task','wave')['facts']
            source,_=self.source(root,'architecture');op=self.opinion('architecture')
            op['reviews']=[dict(riskId='wrong',decision='withdraw',evidenceRef=str(evidence),reason='premise refuted'),dict(riskId='true',decision='retain',evidenceRef=str(evidence),reason='other necessary protection still holds')]
            source.write_text(json.dumps(op),encoding='utf-8')
            for name in ('wrong','true'):
                result=session.review_transition(state,dict(action='review',riskId=name,actor='actor-architecture',sourceRef=str(source),opinionId=op['id']),'task','wave');state=result['facts']
                self.assertEqual(result['restoredActions'],['wrong-action'] if name=='wrong' else [])
            self.assertEqual(state['risks'][0]['status'],'closed');self.assertEqual(state['risks'][1]['limitedActions'],['true-action'])
            bad=copy.deepcopy(state);bad['risks'][1]['status']='closed'
            with self.assertRaises(ValueError):session._validate_probe(bad)

    def test_later_sourced_recheck_preserves_true_hold_and_history_until_original_review_returns(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source,_=self.source(root,'architecture');evidence=root/'evidence';evidence.write_text('first observation',encoding='utf-8')
            risk=dict(id='hold',source='real scoped hold declaration',status='unknown',impact='adoption not yet established',limitedActions=['adopt'],next=dict(owner='worker',action='obtain evidence'),resume='original review',urgent=False,closureOwner='actor-architecture')
            state=dict(schemaVersion=1,taskId='task',waveId='wave',risks=[risk],events=[])
            request_file=root/'actual-request';request_file.write_text('the first actual missing-evidence request',encoding='utf-8')
            request=dict(action='challenge',riskId='hold',actor='worker',sourceRef=str(request_file),proposition='adoption readiness',question='has the necessary evidence arrived?',affectedAction='adopt',evidenceOwner='worker',evidenceAction='obtain the missing result')
            state=session.review_transition(state,request,'task','wave')['facts']
            state=session.review_transition(state,dict(action='evidence',riskId='hold',actor='worker',sourceRef=str(evidence)),'task','wave')['facts']
            op=self.opinion('architecture');op['reviews']=[dict(riskId='hold',decision='retain',evidenceRef=str(evidence),reason='the actual result still leaves the prerequisite unknown')];source.write_text(json.dumps(op),encoding='utf-8')
            review=dict(action='review',riskId='hold',actor='actor-architecture',sourceRef=str(source),opinionId=op['id'])
            state=session.review_transition(state,review,'task','wave')['facts'];prior=copy.deepcopy(state['risks'][0]['recovery'])
            with self.assertRaises(ValueError):session.review_transition(state,request,'task','wave')
            for ref in (str(request_file),str(evidence),prior['reviewRef']):
                with self.assertRaisesRegex(ValueError,'replay'):session.review_transition(state,dict(request,action='recheck',sourceRef=ref,changeReason='later claim requiring actual changed evidence'),'task','wave')
            renamed=root/'renamed-request';renamed.write_bytes(request_file.read_bytes())
            with self.assertRaisesRegex(ValueError,'replay'):session.review_transition(state,dict(request,action='recheck',sourceRef=str(renamed),changeReason='a new filename does not establish a changed request'),'task','wave')
            request_file.write_text('later request: the previously missing result has now arrived; original reviewer must inspect it',encoding='utf-8')
            with self.assertRaises(ValueError):session.review_transition(state,dict(request,action='recheck'),'task','wave')
            result=session.review_transition(state,dict(request,action='recheck',changeReason='the missing result arrived after the retained hold; inspect its current evidence'),'task','wave');pending=result['facts']
            self.assertEqual(result['restoredActions'],[]);self.assertEqual(pending['risks'][0]['status'],'unknown');self.assertEqual(pending['risks'][0]['limitedActions'],['adopt'])
            self.assertEqual(pending['risks'][0]['recovery']['history'],[prior]);self.assertEqual(pending['risks'][0]['recovery']['reviewOwner'],'actor-architecture')
            view=session._render_probe(pending,[]);self.assertIn('上一裁定：retain',view);self.assertIn(pending['risks'][0]['recovery']['changeReason'],view)
            self.assertNotIn(session._user_plain(prior['reviewRef']),view)
            with self.assertRaises(ValueError):session.review_transition(pending,dict(request,action='recheck',sourceRef='another request during work'),'task','wave')
            later=root/'later-evidence';later.write_text('new completed distinguishing observation',encoding='utf-8')
            pending=session.review_transition(pending,dict(action='evidence',riskId='hold',actor='worker',sourceRef=str(later)),'task','wave')['facts']
            op['reviews']=[dict(riskId='hold',decision='withdraw',evidenceRef=str(later),reason='the new result establishes the remaining prerequisite')];source.write_text(json.dumps(op),encoding='utf-8')
            result=session.review_transition(pending,review,'task','wave')
            self.assertEqual(result['restoredActions'],['adopt']);self.assertEqual(result['facts']['risks'][0]['recovery']['history'],[prior])
            with self.assertRaisesRegex(ValueError,'closed'):session.review_transition(result['facts'],dict(request,action='recheck',sourceRef='new request after closure'),'task','wave')

    def test_revision_reports_only_removed_actions_and_respects_other_current_holds(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source,_=self.source(root,'architecture');evidence=root/'evidence';evidence.write_text('controlled distinguishing evidence',encoding='utf-8')
            risk=dict(id='revise',source='controlled case',status='proven',impact='overbroad restriction',limitedActions=['A','B'],next=dict(owner='worker',action='investigate'),resume='review',urgent=False,closureOwner='actor-architecture')
            base=dict(schemaVersion=1,taskId='task',waveId='wave',risks=[risk],events=[])
            base=session.review_transition(base,dict(action='challenge',riskId='revise',actor='worker',sourceRef='controlled premise',proposition='overbreadth',question='which action remains limited?',affectedAction='A',evidenceOwner='worker',evidenceAction='read evidence'),'task','wave')['facts']
            base=session.review_transition(base,dict(action='evidence',riskId='revise',actor='worker',sourceRef=str(evidence)),'task','wave')['facts']
            for revised,held,released,restored in [(['B'],False,['A'],['A']),(['B'],True,['A'],[]),(['A','B'],False,[],[]),(['A','B','C'],False,[],[])]:
                state=copy.deepcopy(base)
                if held:state['risks'].append(dict(risk,id='other',limitedActions=['A'],closureOwner='other-reviewer'))
                op=self.opinion('architecture');op['reviews']=[dict(riskId='revise',decision='revise',evidenceRef=str(evidence),reason='actual reviewer narrows or retains the declared restriction',limitedActions=revised)];source.write_text(json.dumps(op),encoding='utf-8')
                result=session.review_transition(state,dict(action='review',riskId='revise',actor='actor-architecture',sourceRef=str(source),opinionId=op['id']),'task','wave')
                self.assertEqual(result['releasedActions'],released);self.assertEqual(result['restoredActions'],restored)
                self.assertEqual(result['facts']['risks'][0]['limitedActions'],revised)
                self.assertEqual(bool(result['stillHeld']),held)

    def test_shared_restrictions_are_not_removed_by_one_local_withdrawal(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source,_=self.source(root,'architecture');evidence=root/'evidence';evidence.write_text('distinguishing source',encoding='utf-8')
            risk=dict(id='wrong',source='controlled premise',status='proven',impact='one wrong restriction',limitedActions=['shared-action'],next=dict(owner='worker',action='investigate'),resume='review',urgent=False,closureOwner='actor-architecture')
            op=self.opinion('architecture');op['reviews']=[dict(riskId='wrong',decision='withdraw',evidenceRef=str(evidence),reason='this one premise is refuted')];source.write_text(json.dumps(op),encoding='utf-8')
            base=dict(schemaVersion=1,taskId='task',waveId='wave',risks=[risk],events=[])
            base=session.review_transition(base,dict(action='challenge',riskId='wrong',actor='worker',sourceRef='case',proposition='wrong',question='distinguish',affectedAction='shared-action',evidenceOwner='worker',evidenceAction='read source'),'task','wave')['facts']
            base=session.review_transition(base,dict(action='evidence',riskId='wrong',actor='worker',sourceRef=str(evidence)),'task','wave')['facts']
            counterparts=[dict(risks=[dict(risk,id='true',status='unknown',closureOwner='other-reviewer')]),dict(propositions=[dict(id='p',claim='separate prerequisite',status='unknown',evidenceRefs=[],conditions='not yet established',affectedActions=['shared-action'],owner='worker',nextAction='obtain evidence')]),dict(considerations=[dict(id='c',name='actual pending concern',kind='request',sourceRef='request',owner='reviewer',request='check the remaining condition',state='open',nextAction='get real response',limitedActions=['shared-action'])])]
            for extra in counterparts:
                state=copy.deepcopy(base)
                for key,values in extra.items():state[key]=state.get(key,[])+values
                result=session.review_transition(state,dict(action='review',riskId='wrong',actor='actor-architecture',sourceRef=str(source),opinionId=op['id']),'task','wave')
                self.assertEqual(result['releasedActions'],['shared-action']);self.assertEqual(result['restoredActions'],[]);self.assertTrue(result['stillHeld'])
                result['facts']['propositions']=[dict(id='supported',claim='local positive evidence',status='observed',evidenceRefs=['actual source'],conditions='same input',affectedActions=[],owner='worker',nextAction='continue')]+result['facts'].get('propositions',[])
                result['facts']['adoptions']=[dict(action='shared-action',owner='worker',propositionIds=['supported'],state='allowed')]
                with self.assertRaises(ValueError):session._validate_probe(result['facts'])


if __name__=='__main__':unittest.main()
