import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import jury_session as session


class ProbeTests(unittest.TestCase):
    def state(self):
        return {'schemaVersion':1,'taskId':'probe-task','waveId':'probe-wave','participants':['progress'],'scope':'本轮局部首版','events':['planning-start'],
          'progress':{'done':['已核原输入'],'active':['制作隔离候选'],'todo':['真实消费者核回'],
            'next':{'owner':'worker','result':'交当前候选'},'blocked':[]},'risks':[],
          'opinions':[{'role':'progress','state':'初判','gain':-6,'scope':'本波缺证',
            'event':'真实原事件','judgment':'未批准正式采用',
            'basis':{'userNeed':{'source':'fixture user input','evidence':'只让用户看展示，事实仍保留','disposition':'保原范围','action':'交实际消费者'},'actualUse':{'source':'fixture actual use','evidence':'真实调用未运行不冒完成','disposition':'仅保已有证据','action':'取得必要观察'}},
            'open':['正式实物未核'],'conditions':['不能据此停修'],'losses':['已证返工'],
            'limits':['限制正式交付'],'closureOwner':'F本人','next':'交真实消费','decision':'pending'}]}

    def save(self,root,value,markdown=False):
        value.setdefault('taskId','probe-task');value.setdefault('waveId','probe-wave')
        if 'opinions' not in value:value['opinions']=self.state()['opinions']
        value['participants']=[x['role'] for x in value['opinions']]
        current=[]
        for original in value['opinions']:
            op={k:v for k,v in original.items() if k not in ('sourceRef','sourceSelection','responseSelection')}
            op.setdefault('id','fixture-'+op['role']);op.setdefault('actor','fixture-actor-'+op['role'])
            op.setdefault('taskId',value['taskId']);op.setdefault('waveId',value['waveId'])
            source=Path(root)/('source-'+op['role']+'.json');body=json.dumps(op,ensure_ascii=False,indent=2)+'\n';source.write_bytes(body.encode('utf-8'))
            current.append(dict(op,sourceRef=str(source),sourceSelection={'path':str(source),'id':op['id'],'blockSha256':hashlib.sha256(body.encode('utf-8')).hexdigest()}))
        value['opinions']=current
        p=Path(root)/('PLAN.md' if markdown else 'state.json')
        body=json.dumps(value,ensure_ascii=False,indent=2)
        if markdown:body='# Original task record\n\n```jury-state\n'+body+'\n```\n'
        p.write_text(body,encoding='utf-8');return p

    def probe(self,*args,**kwargs):
        if (len(args)>1 and args[1]=='user') or kwargs.get('audience')=='user':
            kwargs.setdefault('expected_task','probe-task');kwargs.setdefault('expected_wave','probe-wave')
        return session.probe_record(*args,**kwargs)

    def test_target_role_uses_same_opinion_skeleton(self):
        with tempfile.TemporaryDirectory() as root:
            value=self.state();value['opinions'][0]['role']='target';value['opinions'][0]['closureOwner']='T本人'
            path=self.save(root,value,True)
            text=self.probe(path,'user','planning-start')['messageText']
            self.assertIn('**🟪T 目标／美术／初判',text);self.assertIn('【📈 本波推进增益：-6】',text)
            self.assertIn('主事件：真实原事件',text);self.assertIn('【🧭开始评估方案】',text)
            self.assertEqual(session.role_blocks(text)['markedBlocks'],1)
            for label in ('🟦F 进度／功能','🔶A 架构／技术生态／可玩性'):self.assertIn(label,session.USER_ROLES.values())

    def test_internal_facts_and_user_view_preserve_same_original(self):
        with tempfile.TemporaryDirectory() as root:
            value=self.state();path=self.save(root,value,True);before=path.read_bytes()
            internal=self.probe(path,event='planning-start')
            user=self.probe(path,'user','planning-start')
            self.assertEqual(internal['facts'],value);self.assertEqual(user['facts'],value)
            self.assertNotIn('messageText',internal);self.assertEqual(path.read_bytes(),before)
            self.assertEqual(internal['sourceSha256'],hashlib.sha256(before).hexdigest())
            for key in ('sourceAuthenticated','semanticContentVerified','readinessCertified','autoExecute','wrote','userVisible'):
                self.assertFalse(user[key])
            self.assertEqual(user['facts']['opinions'][0]['event'],'真实原事件')
            self.assertIn('主事件：真实原事件',user['messageText'])
            for text in ('正式实物未核','不能据此停修','已证返工','限制正式交付','F本人','-6','初判'):
                self.assertIn(text,user['messageText'])
            self.assertIn('【🧭开始评估方案】',user['messageText'])

    def test_unstructured_original_is_unknown_and_cannot_supply_fake_phase(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'old.md';path.write_text('申请停止，等待另一职责核回。',encoding='utf-8')
            result=self.probe(path)
            self.assertEqual(result['status'],'record-unstructured');self.assertIsNone(result['facts'])
            self.assertFalse(result['progressParsed']);self.assertEqual(result['riskStatus'],'unknown')
            self.assertNotIn('messageText',result)
            with self.assertRaises(ValueError):self.probe(path,'user')
            with self.assertRaises(ValueError):self.probe(path,'user','accepted')

    def test_user_projection_resolves_responsibility_without_scrubbing_business_evidence(self):
        with tempfile.TemporaryDirectory() as root:
            value=self.state();base=value['opinions'][0]
            actors={'worker':'/root/production-019','progress':'/root/progress-017','architecture':'/root/architecture-035','dialogue':'/root'}
            value['opinions']=[]
            for role,actor in actors.items():
                op=json.loads(json.dumps(base));op.update(role=role,actor=actor,event='opaque-machine-event-936',wave=value['waveId'],details=str(Path(root)/('source-'+role+'.json')),closureOwner=actors['architecture'])
                op['basis']['actualUse']['source']='/root/Assets/LICENSE-17.md；产品版本2.8.0'
                value['opinions'].append(op)
            value['progress']['next']['owner']=actors['worker']
            recovery=dict(state='review-needed',proposition='实际前提',question='哪种观察区分？',affectedAction='有限采用',evidenceOwner=actors['worker'],evidenceAction='读业务许可证',reviewOwner=actors['architecture'],challengeRef='受控请求',evidenceRef='/root/Assets/LICENSE-17.md',reviewRef='',decision='')
            value['risks']=[dict(id='business-risk-17',source='/root/Assets/LICENSE-17.md',status='unknown',impact='许可范围待核',limitedActions=['有限采用'],next=dict(owner=actors['worker'],action='核业务许可'),resume='原审查结果',urgent=False,closureOwner=actors['architecture'],recovery=recovery)]
            value['propositions']=[dict(id='business-premise-17',claim='业务许可可用',status='unknown',evidenceRefs=['/root/Assets/LICENSE-17.md'],conditions='核许可条目',affectedActions=['有限采用'],owner=actors['architecture'],nextAction='核适用范围')]
            value['adoptions']=[dict(action='有限采用',owner=actors['worker'],propositionIds=['business-premise-17'],state='held')]
            value['considerations']=[dict(id='business-question-17',name='保许可证来源',kind='request',sourceRef='/root/Assets/LICENSE-17.md',owner=actors['progress'],request='核许可而不重设计',state='open',nextAction='回原职责',limitedActions=['有限采用'])]
            path=self.save(root,value);before=path.read_bytes();result=self.probe(path,'user','progress');text=result['messageText']
            self.assertEqual(result['facts'],value);self.assertEqual(path.read_bytes(),before)
            for op in result['facts']['opinions']:
                self.assertEqual(op['event'],'opaque-machine-event-936');self.assertEqual(op['gain'],-6)
            for token in (value['waveId'],str(path),actors['worker'],actors['progress'],actors['architecture']):self.assertNotIn(token,text)
            for label in ('下一结果：'+session.USER_ROLES['worker'],'原责重核：'+session.USER_ROLES['architecture'],'关闭责任：'+session.USER_ROLES['architecture'],'实际收件职责：'+session.USER_ROLES['progress']):self.assertIn(label,text)
            self.assertIn('主事件：opaque-machine-event-936',text)
            for useful in ('/root/Assets/LICENSE-17.md','business-risk-17','产品版本2.8.0','许可范围待核','有限采用','【📈 本波推进增益：-6】'):self.assertIn(useful,text)

    def test_meaningful_legacy_scope_and_substantive_details_are_not_misclassified_as_metadata(self):
        with tempfile.TemporaryDirectory() as root:
            value=self.state();op=value['opinions'][0]
            op.update(wave='只签本次技术核对，不含美术重设计',details='必须保留产品/root/Assets/LICENSE-17.md的许可引用，不能借去调度名删掉本条限制。')
            path=self.save(root,value);text=self.probe(path,'user')['messageText']
            self.assertIn(op['wave'],text);self.assertIn(op['details'],text)

    def test_single_reviewer_can_show_real_unselected_writer_responsibility_without_an_extra_vote(self):
        with tempfile.TemporaryDirectory() as root:
            value=self.state();writer='/root/actual_native_writer';value['progress']['next']['owner']=writer
            path=self.save(root,value)
            with self.assertRaisesRegex(ValueError,'role binding'):self.probe(path,'user')
            value['responsibilityRoles']={writer:'worker'};path=self.save(root,value)
            result=self.probe(path,'user');self.assertIn('下一结果：'+session.USER_ROLES['worker'],result['messageText']);self.assertNotIn(writer,result['messageText'])
            self.assertEqual(result['facts']['opinions'],value['opinions']);self.assertEqual(result['facts']['participants'],['progress'])
            value['responsibilityRoles'][value['opinions'][0]['actor']]='worker';path=self.save(root,value)
            with self.assertRaisesRegex(ValueError,'conflicts'):self.probe(path,'user')

    def test_consideration_container_pointer_is_projected_but_business_reference_is_preserved(self):
        with tempfile.TemporaryDirectory() as root:
            value=self.state();path=self.save(root,value);op=value['opinions'][0];pointer=op['sourceRef']+'#'+op['id']
            item=dict(id='business-request',name='保护原有配方',kind='request',sourceRef=pointer,owner='worker',request='不得覆盖用户已有配方',state='open',nextAction='核范围')
            value['considerations']=[item];path=self.save(root,value);result=self.probe(path,'user')
            self.assertNotIn(session._user_plain(pointer),result['messageText']);self.assertIn(session.USER_ROLES['progress']+'原始意见',result['messageText']);self.assertIn('不得覆盖用户已有配方',result['messageText'])
            self.assertEqual(result['facts']['considerations'][0]['sourceRef'],pointer)
            item['sourceRef']='/root/Assets/LICENSE-17.md#redistribution';path=self.save(root,value)
            self.assertIn(session._user_plain(item['sourceRef']),self.probe(path,'user')['messageText'])

    def test_missing_unsupported_or_conflicting_event_never_renders_approval(self):
        with tempfile.TemporaryDirectory() as root:
            value=self.state();path=self.save(root,value)
            with self.assertRaises(ValueError):self.probe(path,'user','accepted')
            value['events'].append('accepted');path=self.save(root,value)
            with self.assertRaises(ValueError):self.probe(path,'user','accepted')
            value['progress'].update(active=[],todo=[],blocked=[])
            value['opinions'][0].update(open=[],conditions=[],limits=[],decision='allow')
            value['requiredRoles']=['progress','architecture'];path=self.save(root,value)
            with self.assertRaises(ValueError):self.probe(path,'user','accepted')
            value['requiredRoles']=['progress'];path=self.save(root,value)
            result=self.probe(path,'user','accepted')
            self.assertIn('原记录声明允许收尾',result['messageText']);self.assertFalse(result['readinessCertified'])
            value['opinions'][0]['limits']=['只签本轮范围，不签无人值守'];path=self.save(root,value)
            self.assertIn('只签本轮范围',self.probe(path,'user','accepted')['messageText'])

    def test_declared_urgent_risk_not_status_words_causes_notice(self):
        with tempfile.TemporaryDirectory() as root:
            value=self.state();value['progress']['active']=['running 旧mtime 正常长工具，未声称推进']
            path=self.save(root,value);self.assertEqual(self.probe(path)['alerts'],[])
            risk={'id':'supply','source':'原件:12','status':'unknown','impact':'目标供给未核',
              'limitedActions':['依赖扩量'],'next':{'owner':'worker','action':'定点核供给'},
              'resume':'原职责核回当前供给','urgent':True}
            value['risks']=[risk];path=self.save(root,value)
            result=self.probe(path,'user')
            self.assertEqual(result['alerts'][0]['status'],'unknown');self.assertIn('risk-warning',result['declaredEvents'])
            for text in ('原件:12','unknown','目标供给未核','依赖扩量','定点核供给','原职责核回当前供给'):
                self.assertIn(text,result['messageText'])
            value['risks'][0]['status']='closed';path=self.save(root,value)
            self.assertEqual(self.probe(path)['alerts'],[])

    def test_current_risk_blocks_green_but_explicit_parent_risk_keeps_local_scope(self):
        with tempfile.TemporaryDirectory() as root:
            value=self.state();value['events']=['accepted'];value['requiredRoles']=['progress']
            value['progress'].update(active=[],todo=[],blocked=[])
            value['opinions'][0].update(open=[],conditions=[],limits=[],decision='allow')
            value['risks']=[{'id':'downstream','source':'真实原件','status':'proven','impact':'本轮必要下游未验',
              'limitedActions':['不得整体交付'],'next':{'owner':'worker','action':'核下游'},'resume':'本责核回','urgent':True}]
            path=self.save(root,value)
            with self.assertRaisesRegex(ValueError,'current unresolved risk'):self.probe(path,'user','accepted')
            value['risks'][0].update(appliesTo='parent',impact='父目标后继未验，当前仅局部首版',limitedActions=['父目标整体交付']);path=self.save(root,value)
            user=self.probe(path,'user','accepted')
            self.assertIn('原记录声明允许收尾',user['messageText']);self.assertIn('不随本次当前许可关闭',user['messageText'])
            self.assertIn('当前记录范围：本轮局部首版',user['messageText'].splitlines()[0])
            self.assertEqual(user['alerts'][0]['riskId'],'downstream');self.assertFalse(user['readinessCertified'])

    def test_hidden_history_and_outer_samples_are_not_current_state(self):
        with tempfile.TemporaryDirectory() as root:
            body='```jury-state\n'+json.dumps(self.state(),ensure_ascii=False)+'\n```'
            samples=['<!-- 历史样例\n'+body+'\n-->\n当前仍待必要票。',
              '````text\n'+body+'\n````\n当前仍未核回。',
              '\n'.join('> '+line for line in body.splitlines()),'<pre>\n'+body+'\n</pre>']
            path=Path(root)/'history.md'
            for text in samples:
                path.write_text(text,encoding='utf-8');result=self.probe(path)
                self.assertEqual(result['status'],'record-unstructured');self.assertIsNone(result['facts'])
                with self.assertRaises(ValueError):self.probe(path,'user','accepted')
            path.write_text(samples[0]+'\n\n'+body+'\n',encoding='utf-8')
            self.assertEqual(self.probe(path)['facts'],self.state())

    def test_frontend_adds_basis_brackets_and_exact_feature_labels(self):
        with tempfile.TemporaryDirectory() as root:
            value=self.state();value['features']={'basic':['后台只交事实'],'advanced':['前台主动探查风险']}
            value['opinions'][0]['basis']['userNeed']={'source':'只需要用户看',
              'evidence':'当前调用已核','disposition':'按原需迁移','action':'前台呈现'}
            path=self.save(root,value);internal=self.probe(path)
            self.assertNotIn('messageText',internal)
            user=self.probe(path,'user')['messageText']
            self.assertIn('[只需要用户看]',user);self.assertIn('依据：当前调用已核',user)
            self.assertIn('依据：真实调用未运行不冒完成',user)
            self.assertIn('【基础功能】\n后台只交事实',user)
            self.assertIn('【细节／进阶功能】\n前台主动探查风险',user)

    def test_missing_score_records_rule_minus_one_without_forging_original(self):
        with tempfile.TemporaryDirectory() as root:
            value=self.state();value['opinions'][0].pop('gain');path=self.save(root,value)
            result=self.probe(path,'user')
            self.assertNotIn('gain',result['facts']['opinions'][0])
            self.assertIn('本波推进增益：-1',result['messageText'])
            self.assertIn('非原角色评价',result['messageText'])
            value['opinions'][0].update(gain=0,scoreStatus='unverifiable');path=self.save(root,value)
            with self.assertRaises(ValueError):self.probe(path,'user')
            value['opinions'][0]['gain']=-3;path=self.save(root,value)
            self.assertIn('unverifiable',self.probe(path,'user')['messageText'])

    def test_plain_roles_need_receipts_but_letters_and_quoted_examples_do_not(self):
        for draft in ('role: architecture\nstate: pending\n','角色：F\n判断：需补证\n',
                      json.dumps({'role':'progress','gain':-3}),json.dumps({'opinions':[{'role':'architecture'}]}),
                      json.dumps([{'role':'architecture'}])):
            self.assertEqual(session.check_roles(draft,[])['verdict'],'receipt-required')
        for draft in ('A | B 是普通表达\n','> role: progress\n> 主事件：历史引用\n',
                      '```json\n{"role":"progress"}\n```\n','<!-- role: progress -->\n普通文字',
                      json.dumps({'example':{'role':'progress'}},indent=2)):
            self.assertEqual(session.check_roles(draft,[])['verdict'],'no-role-blocks')

    def test_duplicate_blocks_bad_json_fields_and_stale_record_are_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            path=self.save(root,self.state());old=hashlib.sha256(path.read_bytes()).hexdigest()
            path.write_text(path.read_text(encoding='utf-8')+' ',encoding='utf-8')
            with self.assertRaises(ValueError):self.probe(path,expected_sha256=old)
            for text in ('{"schemaVersion":1,"schemaVersion":1,"risks":[]}',
              '{"schemaVersion":1,"risks":NaN}','```jury-state\n{}\n```\n```jury-state\n{}\n```\n'):
                path.write_text(text,encoding='utf-8')
                with self.assertRaises(ValueError):self.probe(path)
            bad=self.state();bad['progress']['next'].pop('owner');path=self.save(root,bad)
            with self.assertRaises(ValueError):self.probe(path)

    def test_real_cli_does_not_mutate_record_and_exposes_actual_profile(self):
        with tempfile.TemporaryDirectory() as root:
            path=self.save(root,self.state(),True);before=path.read_bytes()
            cmd=[sys.executable,'-X','utf8','-B',str(Path(session.__file__)),'probe','--record-file',str(path)]
            process=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8',timeout=15)
            self.assertEqual(process.returncode,0,process.stderr)
            self.assertNotIn('messageText',json.loads(process.stdout));self.assertEqual(path.read_bytes(),before)
            process=subprocess.run(cmd+['--audience','user','--expect-task','probe-task','--expect-wave','probe-wave','--event','accepted'],capture_output=True,text=True,encoding='utf-8',timeout=15)
            self.assertEqual(process.returncode,2);self.assertFalse(json.loads(process.stdout)['passed'])


    def model(self):
        return {'sourceRef':'project/MODEL.md#current；修订r3；观察2026-11-03T04:30Z',
          'scope':'本场景守卫与灯具','declaration':'世界允许短距传送；守卫依据已知目标护送，灯具按触发工作。合计并发成本待原预算核，尚不签整体合格。'}

    def model_risk(self,scope='current'):
        return {'id':'combined-cost','source':'budget.json及当前并发记录','status':'unknown',
          'impact':'单件成本正常，合计峰值仍待核','limitedActions':['依赖该负载的整体采用'],
          'next':{'owner':'worker','action':'对回并发与共享成本'},'resume':'原职责核回整体预算',
          'urgent':False,'appliesTo':scope}

    def test_model_projection_uses_original_facts_without_certifying_or_writing(self):
        with tempfile.TemporaryDirectory() as root:
            value=self.state();value['events']=['element-modeling','element-question','element-open','element-reposition','element-declaration']
            value['risks']=[self.model_risk()];value['elementModel']=self.model()
            value['elementModel'].update(questions=['当前守卫只知告警，凭什么直接锁定未被发现的目标？'],
              reposition=['原以为灯具自主巡逻；据触发配置纠正为无自主主体，守卫目标未降级。'],openRisks=['combined-cost'])
            path=self.save(root,value,True);before=path.read_bytes()
            for event in value['events']:
                result=self.probe(path,'user',event)
                self.assertEqual(result['facts'],value);self.assertEqual(path.read_bytes(),before)
                for text in ('【📐 元素建模声明】','修订r3','世界允许短距传送','当前守卫只知告警','守卫目标未降级','combined-cost','整体预算'):
                    self.assertIn(text,result['messageText'])
                for key in ('sourceAuthenticated','semanticContentVerified','readinessCertified','noLossRelayVerified','autoExecute','wrote','userVisible'):
                    self.assertFalse(result[key])
            user=self.probe(path,'user','element-modeling')['messageText']
            for event in value['events']:
                self.assertEqual(user.count(session.USER_EVENTS[event]),1)
            self.assertNotIn('messageText',self.probe(path))

    def test_model_stage_cannot_be_faked_by_labels_or_empty_detail(self):
        with tempfile.TemporaryDirectory() as root:
            value=self.state();events=['element-modeling','element-question','element-open','element-reposition','element-declaration']
            value['events']=events;path=self.save(root,value)
            for event in events:
                with self.assertRaisesRegex(ValueError,'not supported'):self.probe(path,'user',event)
            value['elementModel']=self.model();path=self.save(root,value)
            for event in ('element-question','element-open','element-reposition'):
                with self.assertRaisesRegex(ValueError,'not supported'):self.probe(path,'user',event)
            # A declaration itself supplies only this optional rendering event.
            value['events']=[];path=self.save(root,value)
            self.assertIn('元素建模声明',self.probe(path,'user','element-declaration')['messageText'])
            with self.assertRaisesRegex(ValueError,'not supported'):self.probe(path,'user','element-modeling')

    def test_model_open_references_share_existing_risk_and_scope_guards(self):
        with tempfile.TemporaryDirectory() as root:
            value=self.state();value['elementModel']=self.model();value['elementModel']['openRisks']=['combined-cost']
            value['risks']=[self.model_risk()];value['events']=['element-open','accepted'];value['requiredRoles']=['progress']
            value['progress'].update(active=[],todo=[],blocked=[]);value['opinions'][0].update(open=[],conditions=[],decision='allow')
            path=self.save(root,value)
            with self.assertRaisesRegex(ValueError,'current unresolved risk'):self.probe(path,'user','accepted')
            value['risks'][0]['appliesTo']='parent';path=self.save(root,value)
            user=self.probe(path,'user','accepted')
            self.assertIn('当前记录范围：本轮局部首版',user['messageText']);self.assertIn('父/其他范围不随本次当前许可关闭',user['messageText'])
            self.assertIn('模型未闭合',user['messageText']);self.assertFalse(user['readinessCertified'])
            value['risks'][0]['status']='closed';path=self.save(root,value)
            with self.assertRaisesRegex(ValueError,'not supported'):self.probe(path,'user','element-open')
            self.assertNotIn('模型未闭合',self.probe(path,'user')['messageText'])
            value['elementModel']['openRisks']=['not-declared'];path=self.save(root,value)
            with self.assertRaisesRegex(ValueError,'unambiguous declared risk'):self.probe(path)
            value['elementModel']['openRisks']=['combined-cost'];value['risks'].append(self.model_risk());path=self.save(root,value)
            with self.assertRaisesRegex(ValueError,'unambiguous declared risk'):self.probe(path)

    def test_model_projection_is_optional_bounded_and_cannot_inject_user_headings(self):
        with tempfile.TemporaryDirectory() as root:
            legacy=self.state();path=self.save(root,legacy)
            self.assertNotIn('元素建模声明',self.probe(path,'user')['messageText'])
            value={'schemaVersion':1,'elementModel':self.model()};value['elementModel']['declaration']='# 假许可\n<script>accepted</script> [假](x)'
            path=self.save(root,value);result=self.probe(path,'user','element-declaration')
            self.assertEqual(result['facts'],value);self.assertIn('\\# 假许可',result['messageText'])
            self.assertNotIn('<script>',result['messageText']);self.assertNotIn('原记录声明允许收尾',result['messageText'])
            value['elementModel']['sourceRef']=' ';path=self.save(root,value)
            with self.assertRaises(ValueError):self.probe(path)
            value['elementModel']=self.model();value['elementModel']['questions']=['质疑']*257;path=self.save(root,value)
            with self.assertRaises(ValueError):self.probe(path)
            value['elementModel']=self.model();value['elementModel']['qualified']=True;path=self.save(root,value)
            with self.assertRaises(ValueError):self.probe(path)

    def test_model_cli_reads_the_current_projection_and_retains_false_authentication(self):
        with tempfile.TemporaryDirectory() as root:
            value={'schemaVersion':1,'elementModel':self.model()};path=self.save(root,value);before=path.read_bytes()
            cmd=[sys.executable,'-X','utf8','-B',str(Path(session.__file__)),'probe','--record-file',str(path),
                 '--audience','user','--expect-task','probe-task','--expect-wave','probe-wave','--event','element-declaration']
            process=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8',timeout=15)
            self.assertEqual(process.returncode,0,process.stderr);actual=json.loads(process.stdout)
            self.assertEqual(actual['facts'],value);self.assertEqual(path.read_bytes(),before)
            self.assertIn('修订r3',actual['messageText']);self.assertFalse(actual['semanticContentVerified'])


    def test_current_model_open_blocks_accepted_without_action_list_or_urgency(self):
        with tempfile.TemporaryDirectory() as root:
            value=self.state();value['events']=['accepted'];value['requiredRoles']=['progress']
            value['progress'].update(active=[],todo=[],blocked=[])
            value['opinions'][0].update(open=[],conditions=[],decision='allow')
            value['elementModel']=self.model();value['elementModel']['openRisks']=['combined-cost']
            value['risks']=[self.model_risk()];value['risks'][0].update(limitedActions=[],urgent=False)
            path=self.save(root,value);before=path.read_bytes()
            with self.assertRaisesRegex(ValueError,'current unresolved element model'):
                self.probe(path,'user','accepted')
            self.assertEqual(path.read_bytes(),before)
            for scope in ('parent','other'):
                value['risks'][0]['appliesTo']=scope;path=self.save(root,value)
                result=self.probe(path,'user','accepted')
                self.assertIn('原记录声明允许收尾',result['messageText'])
                self.assertIn('模型未闭合',result['messageText'])
                self.assertIn('不随本次当前许可关闭',result['messageText'])
                self.assertFalse(result['readinessCertified'])


if __name__=='__main__':unittest.main()
