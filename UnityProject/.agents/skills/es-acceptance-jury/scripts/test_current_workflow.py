"""Current failure/normal controls; withdrawn session replay is intentionally absent."""
import copy,json,hashlib,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
import jury_candidates as candidate
import jury_review_roles as roles
import jury_session as relay
import validate_package as package
ROOT=Path(__file__).resolve().parents[1]

def work_task(identity):
    return dict(taskId=identity,waveId='test-wave',userRequest='Test fixture actual requested result',sourceRefs=['original fixture request'],expectedResult='consume the fixture result',artifacts=['fixture primary artifact'],constraints=['preserve unrelated state'],returnTo='fixture caller',assignments={role:dict(result='obtain the real '+role+' result',firstAction='inspect the primary fixture artifact',methods=['role contract']) for role in ('progress','architecture','worker','dialogue')})

class CurrentWorkflowTests(unittest.TestCase):
    def observation(self):
        return dict(reviewDomain='unity',currentScope={'kind':'task','id':'test-current'},reviewStage='review',task=work_task('test-current'),availableModels=[dict(modelId='gpt-6.1-sol',efforts=['xhigh']),dict(modelId='custom-current',efforts=['high']),dict(modelId='no-effort',efforts=[],supportsEffort=False)])
    def choice(self,model,**extra):
        return dict(modelId=model,sourceKind='direct-user',messageRef='actual-ref-declared',rawText='user choice declaration',responseKind='model-choice',scope={'kind':'task','id':'test-current'},revoked=False,**extra)
    def clone(self,folder):
        root=Path(folder)/'es-acceptance-jury';shutil.copytree(ROOT,root);return root

    def test_planning_consumers_share_route_material_and_preserve_role_boundaries(self):
        prepared=roles.prepare({**self.observation(),'reviewStage':'planning'},ROOT)
        self.assertEqual(prepared['status'],'prepared')
        self.assertEqual(prepared['stageSelectionSource'],'explicit')
        for call in prepared['dispatch']:
            role=call['role'];other='architecture' if role=='progress' else 'progress'
            planned=candidate.plan(ROOT,role=role,review_stage='planning')
            self.assertEqual(planned['readSelectors'],call['readSelectors'])
            self.assertIn('references/reading-guide.md#planning-round',call['readSelectors'])
            self.assertIn('references/task-plan.md#plan-evaluation',call['readSelectors'])
            self.assertIn('references/task-plan.md#start-readiness',call['readSelectors'])
            self.assertIn(candidate.P0_CONTRACTS[role],call['readSelectors'])
            self.assertNotIn(candidate.P0_CONTRACTS[other],call['readSelectors'])
            self.assertIn(candidate.P0_SHARED_CONTRACT,call['readSelectors'])
            self.assertIn(candidate.PROJECT_CONTEXT,call['readSelectors'])
            self.assertFalse(any(c['type']=='shared-check' for c in planned['candidates']))
            self.assertTrue(call['firstReviewTask'])
            self.assertFalse(call['initialInputIndependenceVerified'])
        self.assertFalse(prepared['autoExecute'])
        self.assertFalse(prepared['sourceAuthenticated'])

    def test_unknown_stage_is_unresolved_and_explicit_mature_review_is_preserved(self):
        observation=self.observation();observation.pop('reviewStage')
        default=roles.prepare(observation,ROOT)
        self.assertEqual(default['status'],'stage-unresolved');self.assertEqual(default['dispatch'],[])
        explicit=roles.prepare(self.observation(),ROOT)
        self.assertEqual(explicit['stageSelectionSource'],'explicit')
        for call in explicit['dispatch']:
            self.assertNotIn('firstReviewTask',call)
            self.assertIn('references/candidate-mechanism.md#selection',call['readSelectors'])
            self.assertIn('Test fixture actual requested result',call['taskText'])
        self.assertEqual(candidate.plan(ROOT,role='progress')['status'],'stage-unresolved')
        review=candidate.plan(ROOT,role='progress',review_stage='review')
        self.assertTrue(review['readSelectors']);self.assertEqual(review['stageSelectionSource'],'explicit')

    def test_invalid_stage_never_silently_changes_material_purpose(self):
        for stage in ('', 'production', None, True, 1, [], {}):
            with self.subTest(stage=stage):
                with self.assertRaises(ValueError):
                    candidate.plan(ROOT,review_stage=stage)
                with self.assertRaises(ValueError):
                    roles.prepare({**self.observation(),'reviewStage':stage},ROOT)

    def test_planning_explicit_risk_methods_are_still_consumed(self):
        index=candidate.load_index(ROOT)
        for role in candidate.ROLES:
            check=index['roles'][role]['productChecks'][0]
            planned=candidate.plan(ROOT,role=role,blocks=('architecture',),
                                   product_ids=(check['id'],),review_stage='planning')
            self.assertIn(check['methodSelector'],planned['readSelectors'])
            self.assertIn('references/review-standard.md#failure-continuation',planned['readSelectors'])
            self.assertTrue(planned['declaredBlocks'])
            other='architecture' if role=='progress' else 'progress'
            foreign=index['roles'][other]['productChecks'][0]['id']
            with self.assertRaises(candidate.UnregisteredSelection):
                candidate.plan(ROOT,role=role,product_ids=(foreign,),review_stage='planning')

    def test_missing_planning_contract_refuses_only_its_material_path_and_recovers(self):
        with tempfile.TemporaryDirectory() as folder:
            root=self.clone(folder);path=root/'references/reading-guide.md';original=path.read_bytes()
            text=original.decode('utf-8').replace('\r\n','\n')
            start=text.index('<a id="unity-planning"></a>');end=text.index('<a id="unity-round"></a>',start)
            path.write_text(text[:start]+'<a id="unity-planning"></a>\n## Empty planning\n'+text[end:],encoding='utf-8')
            failed=roles.prepare({**self.observation(),'reviewStage':'planning'},root)
            self.assertFalse(failed['ready']);self.assertEqual(failed['dispatch'],[])
            with self.assertRaises(candidate.CandidateError):
                candidate.plan(root,role='progress',review_stage='planning')
            self.assertEqual(roles.prepare(self.observation(),root)['status'],'prepared')
            path.write_bytes(original)
            self.assertEqual(roles.prepare({**self.observation(),'reviewStage':'planning'},root)['status'],'prepared')

    def test_planning_keeps_pause_model_identity_and_actual_reader_guards(self):
        missing=ROOT/'not-a-real-package'
        held=roles.prepare({**self.observation(),'reviewStage':'planning','paused':True},missing)
        self.assertEqual(held['status'],'held');self.assertEqual(held['dispatch'],[])
        unavailable=roles.prepare({**self.observation(),'reviewStage':'planning','availableModels':[]},ROOT)
        self.assertEqual(unavailable['status'],'model-unavailable');self.assertEqual(unavailable['dispatch'],[])
        with self.assertRaises(roles.InputError):
            roles.prepare({**self.observation(),'reviewStage':'planning','dispatchContext':'same-host',
                           'existingAgents':{'progress':'one','architecture':'one'}},ROOT)
        observation={**self.observation(),'reviewStage':'planning','roles':['progress']}
        prepared=roles.prepare(observation,ROOT)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'prepared.json';path.write_text(json.dumps(prepared),encoding='utf-8')
            page=candidate.reader.read_plan_page(path,ROOT,role='progress')
            self.assertEqual(page['sections'][0]['selector'],'references/reading-guide.md#planning-round')
            self.assertTrue(page['sections'][0]['content'].strip())
            path.write_text(json.dumps(roles.prepare({**observation,'reviewStage':'review'},ROOT)),encoding='utf-8')
            with self.assertRaises(ValueError):
                candidate.reader.read_plan_page(path,ROOT,role='progress',page=1,expect_snapshot=page['snapshot'])

    def test_default_direction_continuations_reach_consumers_and_restore(self):
        # Source authority remains default; disputed route leadership is a real conditional operation.
        conditional=['references/source-authority.md#delegated-direction',
                     'references/must-read-work-priority.md#route-leadership']
        for role in candidate.ROLES:
            planned=candidate.plan(ROOT,role=role,blocks=('tools',),review_stage='review')
            prepared=roles.prepare({**self.observation(),'roles':[role]},ROOT)
            for selected in (planned['readSelectors'],prepared['dispatch'][0]['readSelectors']):
                self.assertIn('references/source-authority.md#current-mainline',selected)
                self.assertFalse(any(s in selected for s in conditional))
        with tempfile.TemporaryDirectory() as folder:
            root=self.clone(folder)
            for selector in conditional:
                path=root/selector.split('#')[0];raw=path.read_bytes()
                text=raw.decode('utf-8').replace('\r\n','\n')
                body=candidate.reader.read_section(selector,root)['content'].replace('\r\n','\n')
                for replacement in ('','<a id="'+selector.split('#')[1]+'"></a>\n## Empty\n'):
                    path.write_text(text.replace(body,replacement,1),encoding='utf-8')
                    with self.assertRaises(ValueError):candidate.expanded_reads([selector],root)
                    self.assertTrue(roles.prepare({**self.observation(),'roles':['progress']},root)['ready'])
                path.write_bytes(raw)
                self.assertTrue(candidate.expanded_reads([selector],root))

    def test_grounded_consideration_reaches_real_consumers_and_empty_body_refuses(self):
        selector='references/source-authority.md#grounded-consideration'
        section=candidate.reader.read_section(selector,ROOT)
        self.assertEqual(section['continuationSelectors'],[])
        for role in candidate.ROLES:
            self.assertEqual(candidate.plan(ROOT,role=role,blocks=('tools',), review_stage='review')['readSelectors'].count(selector),1)
            prepared=roles.prepare({**self.observation(),'roles':[role]},ROOT)
            self.assertEqual([c['role'] for c in prepared['dispatch']],[role])
            self.assertEqual(prepared['dispatch'][0]['readSelectors'].count(selector),1)
        with tempfile.TemporaryDirectory() as folder:
            root=self.clone(folder);path=root/'references/source-authority.md';raw=path.read_bytes()
            text=raw.decode('utf-8').replace('\r\n','\n')
            body=section['content'].replace('\r\n','\n')
            for replacement in ('','<a id="grounded-consideration"></a>\n## Grounding\n<!-- empty -->\n'):
                path.write_text(text.replace(body,replacement,1),encoding='utf-8')
                with self.assertRaises(ValueError):candidate.plan(root,role='progress', review_stage='review')
                self.assertEqual(roles.prepare({**self.observation(),'roles':['progress']},root)['dispatch'],[])
            path.write_bytes(raw)
            self.assertEqual(len(roles.prepare({**self.observation(),'roles':['architecture']},root)['dispatch']),1)

    def test_required_quality_completion_and_guidance_contracts_cannot_be_omitted(self):
        selectors = (
            'references/review-standard.md#quality-blocking',
            'references/review-completion.md#completion-coverage',
            'references/candidate-collision.md#advancement-guidance',
        )
        self.assertTrue(roles.prepare(self.observation(), ROOT)['ready'])
        with tempfile.TemporaryDirectory() as folder:
            root = self.clone(folder)
            for selector in selectors:
                path = root / selector.split('#')[0]
                original = path.read_bytes()
                text = original.decode('utf-8').replace('\r\n', '\n')
                selected = candidate.reader.read_section(selector, root)['content'].replace('\r\n', '\n')
                anchor = selector.split('#')[1]
                for replacement in ('', '<a id="' + anchor + '"></a>\n### Required contract\n<!-- empty -->\n'):
                    path.write_text(text.replace(selected, replacement, 1), encoding='utf-8')
                    result = roles.prepare(self.observation(), root)
                    self.assertFalse(result['ready'])
                    self.assertEqual(result['dispatch'], [])
                path.write_bytes(original)
                restored = roles.prepare(self.observation(), root)
                self.assertTrue(restored['ready'])
                self.assertEqual(len(restored['dispatch']), 2)

    def test_selected_roles_preserve_order_and_actual_host_boundaries(self):
        for selected in (['progress'],['architecture'],['architecture','progress']):
            result=roles.prepare({**self.observation(),'roles':selected},ROOT)
            self.assertEqual(result['status'],'prepared')
            self.assertEqual([c['role'] for c in result['dispatch']],selected)
            self.assertFalse(result['autoExecute'])
            for call in result['dispatch']:
                self.assertEqual(call['readSelectors'].count('references/coordination.md#wave-review'),1)
                self.assertEqual(call['factContractVersion'],1)
                self.assertEqual(call['presentationOwner'],'dialogue')
                self.assertNotIn('displayLayout',call)
                self.assertNotIn('displayBoundary',call)
        current={**self.observation(),'roles':['architecture'],'dispatchContext':'same-host','existingAgents':{'architecture':'real-host-ref'}}
        call=roles.prepare(current,ROOT)['dispatch'][0]
        self.assertEqual((call['action'],call['target']),('followup','real-host-ref'))
        cross=roles.prepare({**current,'dispatchContext':'cross-window'},ROOT)
        self.assertEqual([c['action'] for c in cross['dispatch']],['spawn'])
        self.assertNotIn('target',cross['dispatch'][0])
        self.assertEqual(roles.prepare({**current,'paused':True},ROOT)['dispatch'],[])
        self.assertEqual([c['role'] for c in roles.prepare(self.observation(),ROOT)['dispatch']],['progress','architecture'])

    def test_invalid_roles_and_missing_wave_contract_do_not_prepare_dispatch(self):
        for selected in ([],['progress','progress'],['both'],['other'],['progress',3],'progress',None,{'progress':True}):
            with self.assertRaises(roles.InputError):
                roles.prepare({**self.observation(),'roles':selected},ROOT)
        with tempfile.TemporaryDirectory() as folder:
            root=self.clone(folder);path=root/'references/coordination.md';raw=path.read_bytes()
            text=raw.decode('utf-8').replace('\r\n','\n')
            section=candidate.reader.read_section('references/coordination.md#wave-review',ROOT)['content'].replace('\r\n','\n')
            for body in ('','<a id="wave-review"></a>\n## Wave\n<!-- empty -->\n'):
                path.write_text(text.replace(section,body,1),encoding='utf-8')
                with self.assertRaises(ValueError):candidate.plan(root,role='progress', review_stage='review')
                result=roles.prepare({**self.observation(),'roles':['architecture']},root)
                self.assertEqual(result['dispatch'],[])
            path.write_bytes(raw)
            self.assertEqual(len(roles.prepare({**self.observation(),'roles':['architecture']},root)['dispatch']),1)

    def test_consolidated_entrypoints_reach_common_contract_without_other_role(self):
        for role,card in [('progress','progress-correctness'),('architecture','architecture-ecology-playability')]:
            contract=candidate.P0_CONTRACTS[role]
            summary=candidate.P0_REFERENCES[role]+'#products-'+role
            primary='references/'+card+'.md#products-'+role
            legacy='references/'+card+'.md#product-methods-'+role
            heading='references/'+card+'.md#P0 方法导航'
            slug='references/'+card+'.md#p0-方法导航'
            self.assertIn(candidate.P0_SHARED_CONTRACT,candidate.reader.read_section(contract,ROOT)['continuationSelectors'])
            self.assertIn(contract,candidate.reader.read_section(summary,ROOT)['continuationSelectors'])
            records=[candidate.reader.read_section(selector,ROOT) for selector in (primary,legacy,heading,slug)]
            def from_heading(record):
                lines=record['content'].splitlines()
                return lines[next(i for i,line in enumerate(lines) if line.startswith('#')):]
            for record in records[1:]:self.assertEqual(from_heading(records[0]),from_heading(record))
            other='architecture' if role=='progress' else 'progress'
            for entry in (contract,summary,primary,legacy,heading,slug):
                reads=candidate.expanded_reads([entry],ROOT)
                self.assertIn(candidate.P0_SHARED_CONTRACT,reads)
                self.assertEqual(len(reads),len(set(reads)))
                self.assertFalse(any(x.startswith(candidate.P0_REFERENCES[other]+'#') for x in reads))
        self.assertIn(candidate.P0_SHARED_CONTRACT,candidate.expanded_reads([candidate.WORKSPACE_GUIDE],ROOT))
        with tempfile.TemporaryDirectory() as folder:
            root=self.clone(folder)
            (root/'references/p0-review.md').unlink()
            for contract in candidate.P0_CONTRACTS.values():
                with self.assertRaises(FileNotFoundError):candidate.expanded_reads([contract],root)

    def test_consolidated_visual_methods_keep_full_visual_continuation(self):
        visual='references/review-standard.md#visual-review'
        for role,products in [('progress',('F-P0-01','F-P0-06')),('architecture',('A-P0-03','A-P0-04'))]:
            for product in products:
                selector=candidate.P0_REFERENCES[role]+'#method-'+product.lower()
                record=candidate.reader.read_section(selector,ROOT)
                self.assertIn(visual,record['continuationSelectors'])
                planned=candidate.plan(ROOT,role=role,product_ids=(product,), review_stage='review')
                self.assertEqual(planned['readSelectors'].count(visual),1)
                self.assertIn('references/constraints/04-visual.md#target-and-change',planned['readSelectors'])

    def test_ai_tooling_is_selected_for_tools_without_preloading_every_action(self):
        guide='references/ai-tooling.md#scope'
        leaves=['references/ai-tooling.md#'+key for key in ('mcp','cli','permissions','recovery','results','configuration','installation','delegation')]
        for role in candidate.ROLES:
            tool_plan=candidate.plan(ROOT,role=role,blocks=('tools',), review_stage='review')
            self.assertEqual(tool_plan['readSelectors'].count(guide),1)
            self.assertIn('references/project-understanding.md#capability-fit',tool_plan['readSelectors'])
            self.assertFalse(any(leaf in tool_plan['readSelectors'] for leaf in leaves))
            self.assertNotIn(guide,candidate.plan(ROOT,role=role,blocks=('rules',), review_stage='review')['readSelectors'])
        for dispatch in roles.prepare(self.observation(),ROOT)['dispatch']:
            self.assertNotIn(guide,dispatch['readSelectors'])
        for leaf in leaves:
            self.assertEqual(candidate.expanded_reads([leaf],ROOT),[leaf])
            self.assertTrue(candidate.reader.read_section(leaf,ROOT)['content'].strip())

    def test_missing_ai_tooling_guide_limits_affected_plan_and_empty_scope_refuses(self):
        with tempfile.TemporaryDirectory() as folder:
            root=self.clone(folder);path=root/'references/ai-tooling.md';raw=path.read_bytes()
            path.unlink()
            with self.assertRaises(FileNotFoundError):candidate.plan(root,role='progress',blocks=('tools',), review_stage='review')
            self.assertEqual(candidate.plan(root,role='progress',blocks=('rules',), review_stage='review')['status'],'planned')
            path.write_bytes(raw)
            body=path.read_text(encoding='utf-8')
            section=candidate.reader.read_section('references/ai-tooling.md#scope',root)['content'].replace('\r\n','\n')
            path.write_text(body.replace(section,'<a id="scope"></a>\n## AI tools\n<!-- no method routing -->\n'),encoding='utf-8')
            with self.assertRaises(candidate.CandidateError):candidate.plan(root,role='architecture',blocks=('tools',), review_stage='review')
            self.assertEqual(candidate.plan(root,role='architecture',blocks=('rules',), review_stage='review')['status'],'planned')
            path.write_bytes(raw)
            self.assertEqual(candidate.plan(root,role='architecture',blocks=('tools',), review_stage='review')['status'],'planned')

    def test_project_context_is_in_both_dispatches_and_invalid_material_refuses(self):
        with tempfile.TemporaryDirectory() as folder:
            root=self.clone(folder)
            planned=candidate.plan(root,role='both',blocks=('rules',), review_stage='review')
            self.assertEqual(planned['readSelectors'].count(candidate.PROJECT_CONTEXT),1)
            prepared=roles.prepare(self.observation(),root)
            self.assertEqual(prepared['status'],'prepared')
            for call in prepared['dispatch']:
                self.assertEqual(call['readSelectors'].count(candidate.PROJECT_CONTEXT),1)
                self.assertEqual(call['projectDecisionSelectors'],list(candidate.PROJECT_DECISIONS))
                self.assertFalse(any(x in candidate.PROJECT_DECISIONS for x in call['readSelectors']))
                other='architecture' if call['role']=='progress' else 'progress'
                self.assertFalse(any(x.startswith(candidate.P0_REFERENCES[other]) for x in call['readSelectors']))
            path=root/'references/project-understanding.md'; original=path.read_bytes()
            section=candidate.reader.read_section(candidate.PROJECT_CONTEXT,root)['content'].encode('utf-8')
            for body in (None,b'<a id="project-fit"></a>\n## Context\n<!-- no body -->\n',
                         original.replace(b'id="project-fit"',b'id="project-fitt"'),
                         original.replace(section,section+b'\n<!-- jury-read-continue: references/p0-review.md#review-contract -->\n'),
                         original.replace(section,section+b'\n<!-- jury-read-continue: references/no-project.md#absent -->\n')):
                if body is None:path.unlink()
                else:path.write_bytes(body)
                result=roles.prepare(self.observation(),root)
                self.assertFalse(result['ready']);self.assertEqual(result['dispatch'],[])
                path.write_bytes(original)
            decision=candidate.reader.read_section(candidate.PROJECT_DECISIONS[0],root)['content']
            path.write_text(path.read_text(encoding='utf-8').replace(decision,'<a id="stage-fit"></a>\n## Decisions\n<!-- no body -->\n'),encoding='utf-8')
            self.assertFalse(roles.prepare(self.observation(),root)['ready'])
            path.write_bytes(original)
            self.assertEqual(roles.prepare(self.observation(),root)['status'],'prepared')
            self.assertEqual(roles.prepare({**self.observation(),'paused':True},root)['status'],'held')

    def test_default_current_plan_keeps_required_visual_guidance_without_unrelated_library(self):
        with tempfile.TemporaryDirectory() as folder:
            root=self.clone(folder)
            for path in (root/'references/constraints').glob('*.md'):
                if path.name not in ('04-visual.md','11-methods.md'):path.unlink()
            (root/'references/constraint-index.md').unlink()
            planned=candidate.plan(root,role='both',blocks=('delivery','art'), review_stage='review')
            self.assertEqual(len([x for x in planned['candidates'] if x['type']=='product-check']),10)
            self.assertFalse(any(x['type']=='P0' for x in planned['candidates']))
            self.assertEqual(roles.prepare(self.observation(),root)['status'],'prepared')
            with self.assertRaises(candidate.RetiredInterface):candidate.plan(root,legacy_ids=('01/01',), review_stage='review')
            (root/'references/constraints/04-visual.md').unlink()
            with self.assertRaises(FileNotFoundError):candidate.plan(root,role='both',blocks=('delivery','art'), review_stage='review')

    def test_coverage_reconciliation_is_read_and_missing_body_refuses_preparation(self):
        selector='references/review-perspectives.md#coverage-reconciliation'
        for role in candidate.ROLES:
            reads=candidate.plan(ROOT,role=role,blocks=('rules',), review_stage='review')['readSelectors']
            self.assertEqual(reads.count(selector),1)
            self.assertEqual({s for s in reads if s.startswith('references/recognition.md')}, {'references/recognition.md#unit-state'})
        for call in roles.prepare(self.observation(),ROOT)['dispatch']:
            self.assertEqual(call['readSelectors'].count(selector),1)
        with tempfile.TemporaryDirectory() as folder:
            root=self.clone(folder);path=root/'references/review-perspectives.md'
            raw=path.read_bytes()
            path.unlink()
            with self.assertRaises(FileNotFoundError):candidate.plan(root,role='progress', review_stage='review')
            self.assertEqual(roles.prepare(self.observation(),root)['dispatch'],[])
            body=raw.decode('utf-8').replace('\r\n','\n')
            section=candidate.reader.read_section(selector,ROOT)['content'].replace('\r\n','\n')
            self.assertIn(section,body)
            path.write_text(body.replace(section,'<a id="coverage-reconciliation"></a>\n## Coverage\n<!-- empty body -->\n'),encoding='utf-8')
            with self.assertRaises(candidate.CandidateError):candidate.plan(root,role='architecture', review_stage='review')
            self.assertEqual(roles.prepare(self.observation(),root)['dispatch'],[])
            path.write_bytes(raw)
            self.assertEqual(candidate.plan(root,role='both', review_stage='review')['status'],'planned')
            self.assertEqual(roles.prepare(self.observation(),root)['status'],'prepared')

    def test_knowledge_absence_does_not_supply_or_block_execution_contracts(self):
        with tempfile.TemporaryDirectory() as folder:
            root=self.clone(folder)
            knowledge=(root/'knowledge').resolve()
            self.assertTrue(knowledge.is_relative_to(root.resolve()))
            for path in knowledge.rglob('*'):
                if path.is_file():path.unlink()
            index=candidate.load_index(root)
            for role in candidate.ROLES:
                products=tuple(item['id'] for item in index['roles'][role]['productChecks'])
                plan=candidate.plan(root,role=role,blocks=index['blockKeys'],templates=tuple(index['templates']),product_ids=products, review_stage='review')
                self.assertTrue(all(s.startswith('references/') for s in plan['readSelectors']))
            prepared=roles.prepare(self.observation(),root)
            self.assertEqual(prepared['status'],'prepared')
            self.assertEqual(prepared['schemaVersion'],3)
            for call in prepared['dispatch']:
                self.assertIn('references',Path(call['roleCardPath']).parts)
                self.assertNotIn('knowledgePath',call)
            path=root/candidate.INDEX
            index['roles']['progress']['card']='knowledge/cases/responsibility-identity.md'
            path.write_text(json.dumps(index),encoding='utf-8')
            material=root/'knowledge/cases/responsibility-identity.md'
            material.parent.mkdir(parents=True,exist_ok=True)
            material.write_text('# Archive\nReadable historical facts.\n',encoding='utf-8')
            self.assertEqual(roles.prepare(self.observation(),root)['dispatch'],[])

    def test_knowledge_contract_reaches_plan_and_dispatch_and_empty_contract_refuses(self):
        for role in candidate.ROLES:
            plan=candidate.plan(ROOT,role=role, review_stage='review')
            self.assertIn(candidate.KNOWLEDGE_GUIDE,plan['readSelectors'])
            self.assertEqual(plan['knowledgeIndexSelector'],'knowledge/index.md#issues')
            self.assertEqual(plan['knowledgeLookupRequiredWhen'],['blockage','high-risk','high-requirement'])
            self.assertNotIn(plan['knowledgeIndexSelector'],plan['readSelectors'])
        for call in roles.prepare(self.observation(),ROOT)['dispatch']:
            self.assertIn(candidate.KNOWLEDGE_GUIDE,call['readSelectors'])
            self.assertEqual(call['knowledgeLookupGuideSelector'],candidate.KNOWLEDGE_GUIDE)
            self.assertEqual(call['knowledgeLookupRequiredWhen'],list(candidate.KNOWLEDGE_TRIGGERS))
        with tempfile.TemporaryDirectory() as folder:
            root=self.clone(folder);path=root/'references/reading-guide.md'
            body=path.read_text(encoding='utf-8')
            section=candidate.reader.read_section(candidate.KNOWLEDGE_GUIDE,root)['content'].replace('\r\n','\n')
            self.assertEqual(body.count(section),1)
            changed=body.replace(section,'<a id="knowledge-use"></a>\n## Knowledge\n<!-- no contract -->\n')
            self.assertNotEqual(changed,body)
            for newline in ('\n','\r\n'):
                path.write_bytes(changed.replace('\n',newline).encode('utf-8'))
                result=roles.prepare(self.observation(),root)
                self.assertFalse(result['ready'])
                self.assertEqual(result['dispatch'],[])

    def test_mechanism_titles_match_same_section_but_neighbours_missing_and_empty_refuse(self):
        with tempfile.TemporaryDirectory() as folder:
            root=self.clone(folder);path=root/candidate.INDEX;original=path.read_text(encoding='utf-8')
            self.assertEqual(roles.prepare(self.observation(),root)['status'],'prepared')
            index=json.loads(original)
            selectors=[]
            for selector in index['mechanismSections']:
                record=candidate.reader.read_section(selector,root)
                heading=next(line.lstrip('#').strip() for line in record['content'].splitlines() if line.startswith('#'))
                selectors.append(selector.partition('#')[0]+'#'+heading)
            index['mechanism']=selectors[0];index['mechanismSections']=selectors
            path.write_text(json.dumps(index,ensure_ascii=False),encoding='utf-8')
            self.assertEqual(candidate.plan(root,role='both', review_stage='review')['status'],'planned')
            self.assertTrue(roles.inspect_installation(root)['ready'])
            self.assertEqual(roles.prepare(self.observation(),root)['status'],'prepared')
            for invalid in [dict(mechanism=selectors[1],mechanismSections=selectors),
                            dict(mechanism=selectors[0],mechanismSections=[selectors[0],selectors[1]]),
                            dict(mechanism=selectors[0],mechanismSections=[selectors[0],selectors[2]]),
                            dict(mechanism=selectors[0],mechanismSections=[selectors[0],selectors[2],selectors[2]])]:
                changed={**index,**invalid};path.write_text(json.dumps(changed,ensure_ascii=False),encoding='utf-8')
                with self.assertRaises(candidate.CandidateError):candidate.load_index(root)
                result=roles.prepare(self.observation(),root)
                self.assertFalse(result['ready']);self.assertEqual(result['dispatch'],[])
            path.write_text(json.dumps(index,ensure_ascii=False),encoding='utf-8')
            body_path=root/'references/candidate-mechanism.md';body=body_path.read_text(encoding='utf-8')
            selection=candidate.reader.read_section(selectors[0],root)['content']
            heading=selection.splitlines()[0]
            body_path.write_text(body.replace(selection,heading+'\n<!-- invisible body -->\n'),encoding='utf-8')
            with self.assertRaises(candidate.CandidateError):candidate.load_index(root)
            result=roles.prepare(self.observation(),root)
            self.assertFalse(result['ready']);self.assertEqual(result['dispatch'],[])

    def test_missing_empty_and_wrong_role_material_never_dispatch(self):
        with tempfile.TemporaryDirectory() as folder:
            root=self.clone(folder)
            material=root/'references/progress-correctness.md'; original=material.read_bytes()
            for body in (None,b' ',b'# title\n<!-- no body -->\n'):
                if body is None:material.unlink()
                else:material.write_bytes(body)
                result=roles.prepare(self.observation(),root)
                self.assertFalse(result['ready']);self.assertEqual(result['dispatch'],[])
                material.write_bytes(original)
            index_path=root/candidate.INDEX;index=json.loads(index_path.read_text(encoding='utf-8'))
            index['roles']['progress']['card']='references/architecture-ecology-playability.md';index_path.write_text(json.dumps(index),encoding='utf-8')
            self.assertFalse(roles.prepare(self.observation(),root)['ready'])

    def test_wrong_block_binding_and_missing_product_member_refuse(self):
        with tempfile.TemporaryDirectory() as folder:
            root=self.clone(folder);path=root/candidate.INDEX;original=path.read_text(encoding='utf-8');index=json.loads(original)
            index['roles']['progress']['blocks']['delivery'],index['roles']['progress']['blocks']['rules']=index['roles']['progress']['blocks']['rules'],index['roles']['progress']['blocks']['delivery']
            path.write_text(json.dumps(index),encoding='utf-8')
            with self.assertRaises(candidate.CandidateError):candidate.plan(root, review_stage='review')
            index=json.loads(original);index['roles']['architecture']['productChecks'].pop();path.write_text(json.dumps(index),encoding='utf-8')
            self.assertEqual(roles.prepare(self.observation(),root)['dispatch'],[])

    def test_bounded_verification_reaches_both_roles_and_general_dispatch_once(self):
        selector=candidate.BOUNDED_INSPECTION
        for role in candidate.ROLES:
            for blocks in ((),('tools',),('delivery',)):
                reads=candidate.plan(ROOT,role=role,blocks=blocks, review_stage='review')['readSelectors']
                self.assertEqual(reads.count(selector),1)
                self.assertNotIn('references/coordination.md#opinion-records',reads)
                self.assertNotIn('references/evidence-recovery.md#test-capabilities',reads)
        prepared=roles.prepare(self.observation(),ROOT)
        self.assertEqual(prepared['status'],'prepared')
        for call in prepared['dispatch']:
            self.assertEqual(call['readSelectors'].count(selector),1)
            self.assertIn('evidenceReminder',call);self.assertIn('evidenceStopReminder',call)
        generic=candidate.expanded_reads(['references/juror-prompt.md#planning-dispatch'],ROOT)
        self.assertEqual(generic.count(selector),1)
        self.assertFalse(any(s.startswith('references/p0-') for s in generic))

    def test_missing_empty_and_restored_bounded_contract_controls_real_preparation(self):
        with tempfile.TemporaryDirectory() as folder:
            root=self.clone(folder);path=root/candidate.BOUNDED_INSPECTION.partition('#')[0];raw=path.read_bytes()
            body=path.read_text(encoding='utf-8')
            section=candidate.reader.read_section(candidate.BOUNDED_INSPECTION,root)['content'].replace('\r\n','\n')
            self.assertEqual(body.count(section),1)
            for replacement in ('<a id="bounded-withdrawn"></a>\n## Missing\nActual other text.\n',
                                '<a id="'+candidate.BOUNDED_INSPECTION.partition('#')[2]+'"></a>\n## Bounds\n<!-- no body -->\n'):
                path.write_text(body.replace(section,replacement),encoding='utf-8')
                with self.assertRaises(ValueError):candidate.plan(root,role='architecture',blocks=('tools',), review_stage='review')
                refused=roles.prepare(self.observation(),root)
                self.assertFalse(refused['ready']);self.assertEqual(refused['dispatch'],[])
                path.write_bytes(raw)
                self.assertEqual(roles.prepare(self.observation(),root)['status'],'prepared')

    def test_usability_method_reaches_real_plan_dispatch_and_direct_crosscut(self):
        selector=candidate.USABILITY_METHOD
        for role in candidate.ROLES:
            for blocks in ((),('tools',),('architecture',),('rules',)):
                planned=candidate.plan(ROOT,role=role,blocks=blocks, review_stage='review')
                self.assertEqual(planned['usabilityMethodSelector'],selector)
                self.assertEqual(planned['readSelectors'].count(selector),1)
                self.assertIn(candidate.CROSS_CUTTING_WORKSPACES['playability'],planned['readSelectors'])
        prepared=roles.prepare(self.observation(),ROOT)
        self.assertFalse(prepared['autoExecute'])
        for call in prepared['dispatch']:
            self.assertEqual(call['usabilityMethodSelector'],selector)
            self.assertEqual(call['readSelectors'].count(selector),1)
        self.assertIn(selector,candidate.expanded_reads([candidate.CROSS_CUTTING_WORKSPACES['playability']],ROOT))

    def test_usability_missing_empty_and_restored_material_controls_readiness(self):
        with tempfile.TemporaryDirectory() as folder:
            root=self.clone(folder);path=root/'references/constraints/11-methods.md';raw=path.read_bytes()
            self.assertEqual(roles.prepare(self.observation(),root)['status'],'prepared')
            section=candidate.reader.read_section(candidate.USABILITY_METHOD,root)['content'].replace('\r\n','\n')
            text=path.read_text(encoding='utf-8');self.assertEqual(text.count(section),1)
            empty=text.replace(section,'<a id="early-value-check"></a>\n## Usability\n<!-- no body -->\n')
            for content in (None,empty.encode('utf-8')):
                if content is None:path.unlink()
                else:path.write_bytes(content)
                with self.assertRaises((OSError,ValueError)):candidate.plan(root,role='progress',blocks=('tools',), review_stage='review')
                refused=roles.prepare(self.observation(),root)
                self.assertFalse(refused['ready']);self.assertEqual(refused['dispatch'],[])
                path.write_bytes(raw)
                self.assertEqual(roles.prepare(self.observation(),root)['status'],'prepared')

    def test_game_workspaces_expand_shared_methods_without_duplicate_identity_or_lost_triggers(self):
        index=candidate.load_index(ROOT)
        self.assertEqual(index['blockKeys'],list(candidate.GAME_BLOCKS))
        for role,prefix in [('progress','F'),('architecture','A')]:
            self.assertEqual({x['id'] for x in index['roles'][role]['checks']},{f'{prefix}1-{i:02}' for i in range(1,17)})
            for blocks in [(),*((block,) for block in candidate.GAME_BLOCKS)]:
                result=candidate.plan(ROOT,role=role,blocks=blocks, review_stage='review')
                self.assertTrue(all(selector in result['readSelectors'] for selector in candidate.CROSS_CUTTING_WORKSPACES.values()))
            planned=candidate.plan(ROOT,role=role,blocks=('flow','playability'), review_stage='review')
            for selector in [candidate.WORKSPACE_GUIDE,*candidate.CROSS_CUTTING_WORKSPACES.values(),
                             'references/game-workspaces.md#flow','references/game-workspaces.md#playability']:
                self.assertIn(selector,planned['readSelectors'])
                self.assertTrue(candidate.reader.read_section(selector,ROOT)['content'].strip())
            checks=[x for x in planned['candidates'] if x['type'] in ('shared-check','work-block')]
            self.assertEqual(len(checks),len({x['id'] for x in checks}))
            shared=next(x for x in checks if x['id']==prefix+'1-10')
            self.assertEqual(shared['activatedBy'],['flow','playability'])
            self.assertIn(shared['selector'],planned['readSelectors'])
            self.assertIn(prefix+'1-15',{x['id'] for x in checks})
        for call in roles.prepare(self.observation(),ROOT)['dispatch']:
            self.assertEqual(set(call['workBlockSelectors']),set(candidate.GAME_BLOCKS))
            self.assertIn(candidate.WORKSPACE_GUIDE,call['readSelectors'])
            self.assertTrue(all(x in call['readSelectors'] for x in candidate.CROSS_CUTTING_WORKSPACES.values()))
            self.assertIn('gameQualityReminder',call)

    def test_no_simulation_contract_reaches_real_plans_and_dispatch_without_eager_topics(self):
        required=('references/coordination.md#no-simulation',)
        for role in candidate.ROLES:
            for blocks in [(),*((block,) for block in candidate.GAME_BLOCKS)]:
                planned=candidate.plan(ROOT,role=role,blocks=blocks, review_stage='review')
                for selector in required:self.assertEqual(planned['readSelectors'].count(selector),1)
                self.assertEqual({s for s in planned['readSelectors'] if s.startswith('references/recognition.md')}, {'references/recognition.md#unit-state'})
                self.assertNotIn(candidate.KNOWLEDGE_INDEX,planned['readSelectors'])
        prepared=roles.prepare(self.observation(),ROOT)
        self.assertTrue(prepared['ready'])
        for call in prepared['dispatch']:
            for selector in required:self.assertEqual(call['readSelectors'].count(selector),1)
            self.assertEqual({s for s in call['readSelectors'] if s.startswith('references/recognition.md')}, {'references/recognition.md#unit-state'})
        with tempfile.TemporaryDirectory() as folder:
            root=self.clone(folder);path=root/'references/coordination.md'
            original=path.read_text(encoding='utf-8')
            for selector in required:
                section=candidate.reader.read_section(selector,ROOT)['content'].replace('\r\n','\n')
                self.assertEqual(original.count(section),1)
                anchor=selector.split('#')[1]
                for replacement in ('',f'<a id="{anchor}"></a>\n## Contract\n<!-- no visible contract -->\n'):
                    path.write_text(original.replace(section,replacement,1),encoding='utf-8')
                    with self.assertRaises(ValueError):candidate.plan(root, review_stage='review')
                    result=roles.prepare(self.observation(),root)
                    self.assertFalse(result['ready']);self.assertEqual(result['dispatch'],[])
            path.write_text(original,encoding='utf-8')
            self.assertTrue(roles.prepare(self.observation(),root)['ready'])

    def test_symptom_selection_maps_to_blocks_cards_and_static_chain(self):
        index=candidate.load_index(ROOT)
        self.assertIn('spawn-appear',index['symptoms'])
        planned=candidate.plan(ROOT,role='both',symptom_ids=('spawn-appear',), review_stage='review')
        self.assertEqual(planned['status'],'planned')
        self.assertIn('rules',planned['declaredBlocks'])
        self.assertEqual({t['id'] for t in planned['investigationTemplates']},{'U5','U9'})
        self.assertEqual({m['id'] for m in planned['investigationMethods']},{'F-P0-03','A-P0-01','A-P0-03','A-P0-04'})
        ref=planned['symptomRefs'][0]
        self.assertTrue(ref['staticChain']);self.assertTrue(ref['legalContrast']);self.assertTrue(ref['cannotConclude'])
        # the routing must carry the prose that says routing is not a conclusion
        self.assertIn('references/recognition.md#symptom-trace',planned['readSelectors'])
        self.assertNotIn('references/recognition.md#symptom-trace',candidate.plan(ROOT,role='both', review_stage='review')['readSelectors'])
        # a symptom never certifies investigation or a finding
        self.assertFalse(planned['autoExecute'])
        self.assertNotIn('verified',planned)
        with self.assertRaises(candidate.UnregisteredSelection):
            candidate.plan(ROOT,role='both',symptom_ids=('not-a-symptom',), review_stage='review')
        # every registered symptom must route without error and keep its trace
        for key in index['symptoms']:
            routed=candidate.plan(ROOT,role='both',symptom_ids=(key,), review_stage='review')
            self.assertEqual(routed['status'],'planned',key)
            self.assertTrue(routed['symptomRefs'][0]['staticChain'],key)
            self.assertTrue(routed['symptomRefs'][0]['legalContrast'],key)
            self.assertTrue(routed['investigationTemplates'],key)
        # a check-style symptom id must land in candidates, never in product methods
        frozen=candidate.plan(ROOT,role='both',symptom_ids=('frozen',), review_stage='review')
        ids={c['id'] for c in frozen['candidates']}
        self.assertIn('A1-06',ids)
        self.assertNotIn('A1-06',{m['id'] for m in frozen['investigationMethods']})
        with tempfile.TemporaryDirectory() as folder:
            root=self.clone(folder);path=root/candidate.INDEX
            original=json.loads(path.read_text(encoding='utf-8'))
            for mutate in (
                lambda i: i['symptoms']['spawn-appear']['progress'].append('F1-99'),
                lambda i: i['symptoms']['spawn-appear']['progress'].append('A-P0-01'),
                lambda i: i['symptoms']['spawn-appear']['architecture'].append('F-P0-03'),
                lambda i: i['symptoms']['spawn-appear'].__setitem__('blocks',['no-such-block']),
                lambda i: i['symptoms']['spawn-appear'].__setitem__('templates',['U99']),
                lambda i: i['symptoms']['spawn-appear'].__setitem__('staticChain',[]),
                lambda i: i['symptoms']['spawn-appear'].pop('cannotConclude'),
            ):
                item=copy.deepcopy(original);mutate(item)
                path.write_text(json.dumps(item,ensure_ascii=False),encoding='utf-8')
                with self.assertRaises(candidate.CandidateError):
                    candidate.plan(root,role='both',symptom_ids=('spawn-appear',), review_stage='review')

    def test_invalid_game_workspace_or_check_reference_never_dispatches(self):
        with tempfile.TemporaryDirectory() as folder:
            root=self.clone(folder);path=root/candidate.INDEX
            original=json.loads(path.read_text(encoding='utf-8'))
            invalid=[]
            item=copy.deepcopy(original);item['roles']['progress']['checks'].append(item['roles']['progress']['checks'][0]);invalid.append(item)
            item=copy.deepcopy(original);item['roles']['progress']['crossCuttingChecks']['flow'].append('F1-99');invalid.append(item)
            item=copy.deepcopy(original);item['roles']['progress']['checks'][0]['selector']=item['roles']['progress']['checks'][2]['selector'];invalid.append(item)
            item=copy.deepcopy(original);item['crossCuttingWorkspaces']['flow']=item['crossCuttingWorkspaces']['playability'];invalid.append(item)
            for item in invalid:
                path.write_text(json.dumps(item),encoding='utf-8')
                result=roles.prepare(self.observation(),root)
                self.assertFalse(result['ready']);self.assertEqual(result['dispatch'],[])
            path.write_text(json.dumps(original),encoding='utf-8')
            guide=root/'references/game-workspaces.md';body=guide.read_text(encoding='utf-8')
            section=candidate.reader.read_section(candidate.WORKSPACE_GUIDE,root)['content'].replace('\r\n','\n')
            self.assertEqual(body.count(section),1)
            guide.write_text(body.replace(section,'<a id="approach"></a>\n## Approach\n<!-- empty -->\n'),encoding='utf-8')
            result=roles.prepare(self.observation(),root)
            self.assertFalse(result['ready']);self.assertEqual(result['dispatch'],[])

    def test_selected_production_methods_are_read_without_forcing_unrelated_tasks(self):
        selector='references/project-understanding.md#capability-fit'
        for role in candidate.ROLES:
            self.assertIn(selector,candidate.plan(ROOT,role=role,blocks=('tools',), review_stage='review')['readSelectors'])
            self.assertNotIn(selector,candidate.plan(ROOT,role=role,blocks=('rules',), review_stage='review')['readSelectors'])
            wiring='references/constraints/01-architecture.md#strong-wiring'
            self.assertIn(wiring,candidate.plan(ROOT,role=role,blocks=('architecture',), review_stage='review')['readSelectors'])
            self.assertNotIn(wiring,candidate.plan(ROOT,role=role,blocks=('rules',), review_stage='review')['readSelectors'])
        with tempfile.TemporaryDirectory() as folder:
            root=self.clone(folder);path=root/'references/project-understanding.md'
            body=path.read_text(encoding='utf-8')
            section=candidate.reader.read_section(selector,root)['content'].replace('\r\n','\n')
            self.assertEqual(body.count(section),1)
            changed=body.replace(section,'<a id="capability-fit"></a>\n## Adoption\n<!-- empty -->\n')
            self.assertNotEqual(changed,body)
            path.write_text(changed,encoding='utf-8')
            with self.assertRaises(candidate.CandidateError):candidate.plan(root,role='progress',blocks=('tools',), review_stage='review')
            self.assertEqual(candidate.plan(root,role='progress',blocks=('rules',), review_stage='review')['status'],'planned')

    def test_role_owned_result_methods_are_read_only_when_selected(self):
        planned=candidate.plan(ROOT,role='both', review_stage='review')
        checks=[x for x in planned['candidates'] if x['type']=='product-check']
        progress={x['id'] for x in checks if x['role']=='progress'}
        architecture={x['id'] for x in checks if x['role']=='architecture'}
        self.assertEqual(progress,{'F-P0-01','F-P0-02','F-P0-03','F-P0-04','F-P0-06'})
        self.assertEqual(architecture,{'A-P0-01','A-P0-02','A-P0-03','A-P0-04','A-P0-05'})
        self.assertEqual(planned['investigationMethods'],[])
        self.assertIn(candidate.P0_SHARED_CONTRACT,planned['readSelectors'])
        self.assertTrue(all(candidate.P0_CONTRACTS[role] in planned['readSelectors'] for role in candidate.ROLES))
        self.assertTrue(all(x['selector'].startswith(candidate.P0_REFERENCES[x['role']]+'#') and x['methodSelector'].startswith(candidate.P0_REFERENCES[x['role']]+'#') for x in checks))
        self.assertTrue(all(x['methodSelector'] not in planned['readSelectors'] for x in checks))
        selected=candidate.plan(ROOT,role='progress',product_ids=('F-P0-06',), review_stage='review')
        self.assertEqual([x['id'] for x in selected['investigationMethods']],['F-P0-06'])
        self.assertIn(selected['investigationMethods'][0]['selector'],selected['readSelectors'])
        self.assertIn('references/review-standard.md#failure-continuation',selected['readSelectors'])
        self.assertTrue(all(x['methodSelector'] not in selected['readSelectors'] for x in checks if x['id']!='F-P0-06'))
        with self.assertRaises(candidate.UnregisteredSelection):candidate.plan(ROOT,role='progress',product_ids=('A-P0-03',), review_stage='review')
        prepared=roles.prepare(self.observation(),ROOT)
        for call in prepared['dispatch']:
            owned={x['id'] for x in call['primaryProductChecks']}
            self.assertEqual(owned,progress if call['role']=='progress' else architecture)
            self.assertEqual(set(call['productMethodSelectors']),owned)
            self.assertIn(candidate.P0_CONTRACTS[call['role']],call['readSelectors'])
            self.assertIn(candidate.P0_SHARED_CONTRACT,call['readSelectors'])
            self.assertTrue(all(selector not in call['readSelectors'] for selector in call['productMethodSelectors'].values()))
            self.assertTrue(all(x['primaryRole']==call['role'] for x in call['primaryProductChecks']))

    def test_wrong_or_empty_complete_method_and_wrong_primary_role_refuse_dispatch(self):
        with tempfile.TemporaryDirectory() as folder:
            root=self.clone(folder);path=root/candidate.INDEX;original=path.read_text(encoding='utf-8')
            for kind in ('neighbour-method','cross-role-method','wrong-primary-role','cross-role-result','wrong-object'):
                index=json.loads(original);entry=index['roles']['progress']['productChecks'][0]
                if kind=='neighbour-method':entry['methodSelector']=index['roles']['progress']['productChecks'][1]['methodSelector']
                elif kind=='cross-role-method':entry['methodSelector']=index['roles']['architecture']['productChecks'][0]['methodSelector']
                elif kind=='wrong-primary-role':entry['primaryRole']='architecture'
                elif kind=='cross-role-result':entry['id']='A-P0-01'
                else:entry['object']='other readable but wrong result'
                path.write_text(json.dumps(index,ensure_ascii=False),encoding='utf-8')
                with self.assertRaises(candidate.CandidateError):candidate.load_index(root)
                self.assertEqual(roles.prepare(self.observation(),root)['dispatch'],[])
            path.write_text(original,encoding='utf-8')
            index=json.loads(original);selector=index['roles']['architecture']['productChecks'][0]['methodSelector']
            material=root/selector.partition('#')[0];body=material.read_text(encoding='utf-8')
            section=candidate.reader.read_section(selector,root)['content'];heading=next(x for x in section.splitlines() if x.startswith('#'))
            material.write_text(body.replace(section,section.splitlines()[0]+'\n'+heading+'\n<!-- no visible method -->\n'),encoding='utf-8')
            self.assertEqual(roles.prepare(self.observation(),root)['dispatch'],[])
            material.write_text(body,encoding='utf-8')
            common=root/'references/review-standard.md';body=common.read_text(encoding='utf-8')
            section=candidate.reader.read_section('references/review-standard.md#failure-continuation',root)['content']
            common.write_text(body.replace(section,''),encoding='utf-8')
            self.assertEqual(roles.prepare(self.observation(),root)['dispatch'],[])

    def test_missing_empty_or_role_card_bound_p0_authority_never_dispatches(self):
        with tempfile.TemporaryDirectory() as folder:
            root=self.clone(folder)
            for selector in [*candidate.P0_CONTRACTS.values(),candidate.P0_SHARED_CONTRACT]:
                authority=root/selector.partition('#')[0];original=authority.read_bytes()
                authority.unlink()
                self.assertEqual(roles.prepare(self.observation(),root)['dispatch'],[])
                authority.write_bytes(original)
                body=authority.read_text(encoding='utf-8')
                section=candidate.reader.read_section(selector,root)['content']
                authority.write_text(body.replace(section,'<a id="review-contract"></a>\n## P0\n<!-- no visible contract -->\n'),encoding='utf-8')
                self.assertEqual(roles.prepare(self.observation(),root)['dispatch'],[])
                authority.write_bytes(original)
            index_path=root/candidate.INDEX;index=json.loads(index_path.read_text(encoding='utf-8'))
            entry=index['roles']['progress']['productChecks'][0]
            entry['methodSelector']=index['roles']['progress']['card']+'#method-f-p0-01'
            with (root/index['roles']['progress']['card']).open('a',encoding='utf-8') as stream:
                stream.write('\n<a id="method-f-p0-01"></a>\n### Old method\nReadable old method body.\n')
            index_path.write_text(json.dumps(index,ensure_ascii=False),encoding='utf-8')
            with self.assertRaises(candidate.CandidateError):candidate.load_index(root)
            self.assertEqual(roles.prepare(self.observation(),root)['dispatch'],[])

    def test_single_role_plan_and_dispatch_read_only_own_p0_reference(self):
        prepared=roles.prepare(self.observation(),ROOT)
        for role in candidate.ROLES:
            other=next(name for name in candidate.ROLES if name!=role)
            index=candidate.load_index(ROOT)
            product=index['roles'][role]['productChecks'][0]['id']
            planned=candidate.plan(ROOT,role=role,product_ids=(product,), review_stage='review')
            self.assertEqual(set(planned['reviewContractSelectors']),{role})
            self.assertIn(candidate.P0_CONTRACTS[role],planned['readSelectors'])
            self.assertFalse(any(selector.startswith(candidate.P0_REFERENCES[other]+'#') for selector in planned['readSelectors']))
            call=next(item for item in prepared['dispatch'] if item['role']==role)
            self.assertEqual(call['p0ContractSelector'],candidate.P0_CONTRACTS[role])
            self.assertTrue(call['p0AuthorityPath'].endswith(Path(candidate.P0_REFERENCES[role]).name))
            self.assertFalse(any(selector.startswith(candidate.P0_REFERENCES[other]+'#') for selector in call['readSelectors']))
            self.assertTrue(all(selector.startswith(candidate.P0_REFERENCES[role]+'#') for selector in call['productMethodSelectors'].values()))

    def test_architecture_tracking_is_consumed_without_expanding_progress_scope(self):
        architecture=candidate.plan(ROOT,role='architecture', review_stage='review')
        progress=candidate.plan(ROOT,role='progress', review_stage='review')
        self.assertIn(candidate.P0_ARCHITECTURE_TRACKING,architecture['readSelectors'])
        self.assertNotIn(candidate.P0_ARCHITECTURE_TRACKING,progress['readSelectors'])
        dispatch=roles.prepare(self.observation(),ROOT)['dispatch']
        for call in dispatch:
            if call['role']=='architecture':
                self.assertIn(candidate.P0_ARCHITECTURE_TRACKING,call['readSelectors'])
                self.assertEqual(call['projectTrackingSelector'],candidate.P0_ARCHITECTURE_TRACKING)
            else:self.assertNotIn(candidate.P0_ARCHITECTURE_TRACKING,call['readSelectors'])
        with tempfile.TemporaryDirectory() as folder:
            root=self.clone(folder);path=root/candidate.P0_REFERENCES['architecture'];body=path.read_text(encoding='utf-8')
            section=candidate.reader.read_section(candidate.P0_ARCHITECTURE_TRACKING,root)['content']
            path.write_text(body.replace(section,'<a id="project-tracking"></a>\n## Tracking\n<!-- empty -->\n'),encoding='utf-8')
            self.assertEqual(roles.prepare(self.observation(),root)['dispatch'],[])

    def test_independent_input_contract_reaches_each_role_and_empty_contract_refuses(self):
        for role in candidate.ROLES:
            planned=candidate.plan(ROOT,role=role, review_stage='review')
            self.assertIn(candidate.INDEPENDENT_INPUT_CONTRACT,planned['readSelectors'])
        for stage in ('planning','review'):
            for selected in (['progress'],['architecture'],['architecture','progress']):
                prepared=roles.prepare({**self.observation(),'reviewStage':stage,'roles':selected},ROOT)
                self.assertEqual([c['role'] for c in prepared['dispatch']],selected)
                self.assertFalse(prepared['autoExecute'])
                self.assertFalse(prepared['sourceAuthenticated'])
                for call in prepared['dispatch']:
                    self.assertIn(candidate.INDEPENDENT_INPUT_CONTRACT,call['readSelectors'])
                    self.assertFalse(call['initialInputIndependenceVerified'])
                    reminder=call['initialReviewInputReminder']
                    self.assertEqual(reminder.count('本人及其它AI首次形成的需求解释、方案、判断和产物，均是不可信候选'),1)
                    self.assertIn('not automatic rejection',reminder)
        with tempfile.TemporaryDirectory() as folder:
            root=self.clone(folder);path=root/'references/coordination.md';body=path.read_bytes()
            section=candidate.reader.read_section(candidate.INDEPENDENT_INPUT_CONTRACT,root)['content']
            original=section.encode('utf-8')
            self.assertEqual(body.count(original),1,'The negative fixture must actually replace its selected contract')
            path.write_bytes(body.replace(original,b'<a id="independent-input"></a>\n## Input\n<!-- empty -->\n'))
            self.assertEqual(roles.prepare(self.observation(),root)['dispatch'],[])

    def test_empty_message_and_judgement_contracts_refuse(self):
        with tempfile.TemporaryDirectory() as folder:
            root=self.clone(folder)
            for filename,anchor in [('coordination.md','activation'),('coordination.md','message-delivery'),('review-standard.md','decision-order')]:
                path=root/'references'/filename;original=path.read_bytes()
                for suffix in ['<!-- invisible -->','```\nnot a visible obligation\n```']:
                    path.write_text('<a id="'+anchor+'"></a>\n## Title\n'+suffix,encoding='utf-8')
                    result=roles.prepare(self.observation(),root);self.assertFalse(result['ready']);self.assertEqual(result['dispatch'],[])
                path.write_bytes(original)

    def test_user_choice_precedes_default_and_no_effort_is_explicit(self):
        observation=self.observation();observation['selection']=self.choice('custom-current',effort='high')
        result=roles.prepare(observation,ROOT);self.assertEqual(result['model'],'custom-current')
        self.assertTrue(all(x['reasoning_effort']=='high' for x in result['dispatch']))
        observation['selection']=self.choice('no-effort');result=roles.prepare(observation,ROOT)
        self.assertEqual(result['status'],'model-unavailable');self.assertEqual(result['dispatch'],[])
        observation['selection']['effort']=None;result=roles.prepare(observation,ROOT)
        self.assertEqual(result['status'],'prepared');self.assertTrue(all('reasoning_effort' not in x for x in result['dispatch']))
        observation['selection']['effort']='high';self.assertEqual(roles.prepare(observation,ROOT)['dispatch'],[])
        observation['selection']=self.choice('custom-current',effort='xhigh');self.assertEqual(roles.prepare(observation,ROOT)['dispatch'],[])
        observation['selection']['scope']={'kind':'task','id':'wrong'};self.assertEqual(roles.prepare(observation,ROOT)['status'],'model-unresolved')

    def test_current_model_defaults_and_unsupported_effort_never_downgrade(self):
        observation=self.observation()
        observation['availableModels'].extend([
            dict(modelId='gpt-6-astra',efforts=['low','high','xhigh']),
            dict(modelId='test-sol',family='sol',efforts=['high','xhigh']),
            dict(modelId='test-luna',family='luna',efforts=['high','xhigh']),
            dict(modelId='test-other',efforts=['high','xhigh'])])
        for model,expected in [('gpt-6.1-sol','xhigh'),('gpt-6-astra','high'),('test-sol','xhigh'),('test-luna','xhigh'),('test-other','xhigh')]:
            observation['selection']=self.choice(model)
            result=roles.prepare(observation,ROOT)
            self.assertEqual(result['status'],'prepared')
            self.assertEqual(result['reasoning_effort'],expected)
            self.assertTrue(all(call['reasoning_effort']==expected for call in result['dispatch']))
        observation['selection']=self.choice('custom-current')
        self.assertEqual(roles.prepare(observation,ROOT)['status'],'model-unavailable')
        observation['selection']=self.choice('gpt-6-astra')
        next(item for item in observation['availableModels'] if item['modelId']=='gpt-6-astra')['efforts']=['low']
        self.assertEqual(roles.prepare(observation,ROOT)['dispatch'],[])

    def test_pause_and_independence(self):
        observation=self.observation();observation['paused']=True
        result=roles.prepare(observation,ROOT);self.assertEqual(result['status'],'held');self.assertEqual(result['dispatch'],[])
        observation['paused']=False;observation['dispatchContext']='same-host';observation['existingAgents']={'progress':'same','architecture':'same'}
        with self.assertRaises(roles.InputError):roles.prepare(observation,ROOT)
        observation['existingAgents']={'progress':'real-progress'}
        result=roles.prepare(observation,ROOT);self.assertEqual(result['dispatch'][0]['target'],'real-progress');self.assertEqual(result['dispatch'][1]['action'],'spawn')

    def test_known_model_family_cannot_silently_change_default_effort(self):
        for model,family,expected in [('gpt-6-astra','astra','high'),('gpt-6.1-sol','sol','xhigh')]:
            for declared in (None,family):
                with self.subTest(model=model,family=declared):
                    observation=self.observation()
                    observation['availableModels']=[dict(modelId=model,family=declared,efforts=['high','xhigh'])]
                    observation['selection']=self.choice(model)
                    result=roles.prepare(observation,ROOT)
                    self.assertEqual(result['status'],'prepared')
                    self.assertEqual(result['reasoning_effort'],expected)
                    observation['selection']['effort']='xhigh' if expected=='high' else 'high'
                    explicit=roles.prepare(observation,ROOT)
                    self.assertEqual(explicit['reasoning_effort'],observation['selection']['effort'])
            observation['availableModels'][0]['family']='sol' if family=='astra' else 'astra'
            with self.assertRaises(roles.InputError):
                roles.prepare(observation,ROOT)
        observation=self.observation()
        observation['availableModels']=[dict(modelId='private-astra-alias',family='astra',efforts=['high','xhigh'])]
        observation['selection']=self.choice('private-astra-alias')
        self.assertEqual(roles.prepare(observation,ROOT)['reasoning_effort'],'high')

    def test_route_shapes_return_cli_diagnostics_and_optional_symptoms_keep_cards(self):
        with tempfile.TemporaryDirectory() as folder:
            root=self.clone(folder);path=root/candidate.INDEX
            original=json.loads(path.read_text(encoding='utf-8'))
            values=[[]]
            for key in ('roles','templates','crossCuttingWorkspaces'):
                value=json.loads(json.dumps(original));value[key]=[];values.append(value)
            value=json.loads(json.dumps(original));value['roles']['progress']=[];values.append(value)
            for value in values:
                path.write_text(json.dumps(value),encoding='utf-8')
                with self.assertRaises(candidate.CandidateError): candidate.load_index(root)
            # Real CLI must emit the established structured error rather than traceback.
            result=subprocess.run([sys.executable,'-X','utf8','-B',str(root/'scripts/jury_candidates.py'),'inspect'],
                                  capture_output=True,text=True,encoding='utf-8',timeout=15)
            self.assertEqual(result.returncode,2,result.stderr)
            self.assertEqual(json.loads(result.stdout)['status'],'invalid-candidate-material')
            self.assertNotIn('Traceback',result.stderr)
            original.pop('symptoms',None)
            path.write_text(json.dumps(original),encoding='utf-8')
            self.assertEqual(set(candidate.load_index(root)['templates']),{f'U{i}' for i in range(1,10)})
            for cards in ({},{'U1':original['templates']['U1']}):
                value={**original,'templates':cards};path.write_text(json.dumps(value),encoding='utf-8')
                with self.assertRaises(candidate.CandidateError):candidate.load_index(root)

    def test_pause_and_cancellation_hold_before_reading_unavailable_material(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/'SKILL.md').write_bytes(b'\xff')
            for control in ('paused','cancelled'):
                observation=self.observation();observation[control]=True
                with patch.object(roles,'inspect_installation',side_effect=AssertionError('must not inspect while held')):
                    result=roles.prepare(observation,root)
                self.assertEqual(result['status'],'held')
                self.assertEqual(result['dispatch'],[])
                self.assertFalse(result['ready'])
                self.assertFalse(result['autoExecute'])
                observation[control]=False
                with self.assertRaises(UnicodeError):
                    roles.prepare(observation,root)

    def test_window_handoff_preserves_same_window_and_never_targets_history(self):
        observation=self.observation();old={'progress':'old-progress','architecture':'old-architecture'}
        observation['existingAgents']=old
        unresolved=roles.prepare(observation,ROOT)
        self.assertEqual(unresolved['status'],'dispatch-context-unresolved')
        self.assertEqual(unresolved['dispatch'],[])
        self.assertEqual(unresolved['unclassifiedAgentRefs'],old)
        self.assertFalse(unresolved['hostContextAuthenticated'])
        for references in (None,{}):
            fresh=self.observation()
            if references is not None:fresh['existingAgents']=references
            self.assertTrue(all(call['action']=='spawn' for call in roles.prepare(fresh,ROOT)['dispatch']))
        observation['dispatchContext']='same-host'
        result=roles.prepare(observation,ROOT)
        self.assertEqual(result['status'],'prepared')
        self.assertFalse(result['hostContextAuthenticated'])
        self.assertTrue(all(call['action']=='followup' and call['target']==old[call['role']] for call in result['dispatch']))
        observation['dispatchContext']='cross-window'
        for history in (old,{'progress':'old-progress'},{'progress':'old-reference','architecture':'old-reference'}):
            observation['existingAgents']=history
            result=roles.prepare(observation,ROOT)
            self.assertEqual(result['historicalAgentRefs'],history)
            self.assertFalse(result['hostContextAuthenticated'])
            self.assertFalse(result['sourceAuthenticated'])
            self.assertTrue(all(call['action']=='spawn' and 'target' not in call for call in result['dispatch']))
            self.assertTrue(all(call['reasoning_effort']=='xhigh' for call in result['dispatch']))
        for flag in ('paused','cancelled'):
            for context in (None,'unknown','cross-window'):
                held={**observation,flag:True}
                if context is None:held.pop('dispatchContext',None)
                else:held['dispatchContext']=context
                result=roles.prepare(held,ROOT)
                self.assertEqual(result['status'],'held')
                self.assertEqual(result['dispatch'],[])
        successor={'progress':'current-progress','architecture':'current-architecture'}
        continued=roles.prepare({**observation,'dispatchContext':'same-host','existingAgents':successor},ROOT)
        self.assertTrue(all(call['action']=='followup' and call['target']==successor[call['role']] for call in continued['dispatch']))
        self.assertFalse(continued['hostContextAuthenticated'])
        for context in ('unknown','',None,True,{}):
            with self.assertRaises(roles.InputError):roles.prepare({**observation,'dispatchContext':context},ROOT)

    def test_inheritance_contract_reaches_existing_plan_and_dispatch(self):
        selector='references/coordination.md#activation'
        for role in candidate.ROLES:
            self.assertIn(selector,candidate.plan(ROOT,role=role, review_stage='review')['readSelectors'])
        prepared=roles.prepare(self.observation(),ROOT)
        self.assertTrue(prepared['continuityContractReadable'])
        for call in prepared['dispatch']:
            self.assertIn(selector,call['readSelectors'])
            self.assertEqual(call['continuityContractSelector'],selector)
        self.assertEqual(candidate.reader.read_section('SKILL.md',ROOT)['continuationSelectors'],[])
        self.assertIn(selector,candidate.read_profile(ROOT,'worker','review','general')['readSelectors'])

    def test_role_blocks_require_declared_receipt(self):
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder);draft=folder/'draft.md';receipt=folder/'receipt.md'
            marker='**🟦进度／功能｜独立初判**\n【📈 本波推进增益：+12】\n主事件：示例\n'
            draft.write_text(marker,encoding='utf-8')
            bare=relay.check_roles(draft.read_text(encoding='utf-8'),[])
            self.assertFalse(bare['passed']);self.assertEqual(bare['verdict'],'receipt-required')
            self.assertNotIn('single-source',bare['action'])
            self.assertEqual(bare['blocks'],1)
            receipt.write_text('真实来源原文\n',encoding='utf-8')
            supplied=relay.check_roles(draft.read_text(encoding='utf-8'),[receipt])
            self.assertTrue(supplied['passed']);self.assertEqual(supplied['receipts'],1)
            self.assertFalse(supplied['receiptAuthenticated']);self.assertFalse(supplied['semanticContentVerified'])
            for provable in ('receiptAuthenticated','receiptCoverageVerified','semanticContentVerified','userVisible','autoExecute'):
                self.assertFalse(bare[provable])
                self.assertFalse(supplied[provable])
            empty=relay.check_roles('工作端记录：本轮只整理已有材料。\n',[])
            self.assertTrue(empty['passed']);self.assertEqual(empty['blocks'],0);self.assertEqual(empty['verdict'],'no-role-blocks')
            mixed=relay.check_roles('工作端说明\n'+marker+'🔶架构｜初判\n本波推进增益：-3\n主事件：x\n',[])
            self.assertFalse(mixed['passed']);self.assertGreaterEqual(mixed['blocks'],2)
            receipt.write_text('   \n',encoding='utf-8')
            with self.assertRaises(ValueError):relay.check_roles(marker,[receipt])

    def test_receipt_data_formatting_does_not_change_acceptance(self):
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder);receipt=folder/'receipt.json'
            draft='🟦进度／功能\n本波推进增益：+1\n主事件：已亲查\n'
            original={'source':'native-progress','originalRaw':draft,'result':{'passed':False,'count':0}}
            for indent in (None,2,4):
                for newline in ('\n','\r\n'):
                    raw=json.dumps(original,ensure_ascii=False,indent=indent).replace('\n',newline).encode('utf-8')
                    for bom in (b'',b'\xef\xbb\xbf'):
                        receipt.write_bytes(bom+raw)
                        result=relay.check_roles(draft,[receipt])
                        self.assertTrue(result['passed'])
                        self.assertEqual(result['receiptFiles'][0]['sha256'],hashlib.sha256(bom+raw).hexdigest())
                        self.assertFalse(result['receiptAuthenticated'])
                        self.assertFalse(result['receiptCoverageVerified'])
            for value in (0,False):
                receipt.write_text(json.dumps(value),encoding='utf-8')
                self.assertTrue(relay.check_roles(draft,[receipt])['passed'])
            receipt=folder/'receipt.md'
            for text in ('    原始缩进回执\n','```text\n原始回执\n```\n','<pre>原始回执</pre>'):
                receipt.write_text(text,encoding='utf-8')
                self.assertTrue(relay.check_roles(draft,[receipt])['passed'])
                self.assertFalse(relay.check_message(text)['passed'])
            receipt.write_text(draft+'🔶架构\n本波推进增益：+2\n主事件：原始意见\n',encoding='utf-8')
            result=relay.check_roles(receipt.read_text(encoding='utf-8'),[receipt])
            self.assertTrue(result['passed']);self.assertEqual(result['receipts'],1)
            self.assertEqual(result['blocks'],2);self.assertFalse(result['receiptCoverageVerified'])

    def test_receipt_invalid_data_keeps_encoding_capacity_and_path_guards(self):
        with tempfile.TemporaryDirectory() as folder:
            receipt=Path(folder)/'receipt.json';draft='🟦进度／功能\n'
            for text in ('','  \n','{}','[]','null','""','"  "','{','NaN','Infinity','-Infinity'):
                with self.subTest(text=text):
                    receipt.write_text(text,encoding='utf-8')
                    with self.assertRaises(ValueError):relay.check_roles(draft,[receipt])
            receipt.write_bytes(b'\xff')
            with self.assertRaises(UnicodeError):relay.check_roles(draft,[receipt])
            receipt.write_bytes(b'x'*(relay.MAX_RECORD+1))
            with self.assertRaises(ValueError):relay.check_roles(draft,[receipt])
            with self.assertRaises(ValueError):relay.check_roles(draft,['relative-receipt.md'])
            with self.assertRaises(FileNotFoundError):relay.check_roles(draft,[Path(folder)/'missing.md'])

    def test_relay_rejects_lost_gain_event_condition_source_or_added_ack(self):
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder);one=folder/'one.md';two=folder/'two.md';draft=folder/'draft.md'
            one.write_text('增益：-20\n主事件：需要返工\n条件：未验Player，不能通过。\n',encoding='utf-8')
            two.write_text('增益：-10\n主事件：架构缺证\n否决：未闭。\n',encoding='utf-8')
            result=relay.relay_message([one,two],['progress','architecture']);full=result['messageText']
            draft.write_text(full,encoding='utf-8');self.assertTrue(relay.relay_message([one,two],['progress','architecture'],draft)['passed'])
            for modified in [full.replace('增益：-20',''),full.replace('增益：-10',''),full.replace('主事件：需要返工',''),full.replace('条件：未验Player，不能通过。',''),full.split('转发来源：architecture')[0],'已收到。\n'+full]:
                draft.write_text(modified,encoding='utf-8');self.assertFalse(relay.relay_message([one,two],['progress','architecture'],draft)['passed'])
            for flag in ['sourceAuthenticated','sourceSetCompletenessVerified','semanticContentVerified','userVisible','autoExecute']:
                self.assertFalse(result[flag])

    def test_relay_literal_and_capacity_includes_generated_crlf_bom(self):
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder);source=folder/'source.md';draft=folder/'draft.md'
            source.write_text('意见与条件必须保留\n<!--\n```\n'+('~\n'*1400000),encoding='utf-8',newline='\n')
            result=relay.relay_message([source],['progress']);message=result['messageText']
            self.assertIn(r'\<\!--',message);self.assertIn(r'\`\`\`',message)
            encoded=b'\xef\xbb\xbf'+message.replace('\n','\r\n').encode('utf-8')
            self.assertGreater(len(encoded),relay.MAX_RECORD);self.assertLessEqual(len(encoded),result['draftLimitBytes'])
            draft.write_bytes(encoded);self.assertTrue(relay.relay_message([source],['progress'],draft)['passed'])

    def test_general_first_round_reaches_common_guards_without_other_role(self):
        entry='references/reading-guide.md#first-round'
        record=candidate.reader.read_section(entry,ROOT)
        self.assertEqual(record['continuationSelectors'],[])
        self.assertTrue(candidate.reader.read_section('references/reading-guide.md#reader-contract',ROOT)['content'])
        for role,card in [('progress','progress-correctness'),('architecture','architecture-ecology-playability')]:
            reads=candidate.read_profile(ROOT,role,'review','general')['readSelectors']
            self.assertTrue(set(candidate.SOURCE_MODE_CONTRACTS)<=set(reads))
            other='architecture' if role=='progress' else 'progress'
            self.assertFalse(any(item.startswith(candidate.P0_REFERENCES[other]+'#') for item in reads))
            self.assertFalse(any(item.startswith('references/'+('architecture-ecology-playability' if other=='architecture' else 'progress-correctness')+'.md#') for item in reads))
            planned=candidate.plan(ROOT,role=role,blocks=('rules',), review_stage='review')
            self.assertTrue(set(candidate.SOURCE_MODE_CONTRACTS)<=set(planned['readSelectors']))
        self.assertEqual(candidate.expanded_reads(['references/ai-tooling.md#results'],ROOT),
                         ['references/ai-tooling.md#results'])

    def test_general_first_round_missing_guard_fails_actual_reading(self):
        with tempfile.TemporaryDirectory() as folder:
            root=self.clone(folder);path=root/'references/coordination.md';raw=path.read_bytes()
            for selector in candidate.SOURCE_MODE_CONTRACTS:
                with self.subTest(selector=selector):
                    anchor=selector.split('#',1)[1]
                    body=raw.decode('utf-8').replace('<a id="'+anchor+'"></a>','<a id="fixture-unavailable-'+anchor+'"></a>')
                    path.write_text(body,encoding='utf-8')
                    with self.assertRaises(ValueError):
                        candidate.read_profile(root,'worker','review','general')['readSelectors']
                    path.write_bytes(raw)
            self.assertTrue(set(candidate.SOURCE_MODE_CONTRACTS)<=set(candidate.read_profile(root,'worker','review','general')['readSelectors']))

    def test_live_method_navigation_links_resolve_to_readable_rules(self):
        for card,ids in [('progress-correctness',('F1-15',)),
                         ('architecture-ecology-playability',('A1-07','A1-15','A1-16'))]:
            relative='references/'+card+'.md'
            content=(ROOT/relative).read_text(encoding='utf-8-sig')
            for method in ids:
                with self.subTest(method=method):
                    row=next(line for line in content.splitlines() if line.startswith('| '+method+' |'))
                    self.assertNotRegex(row,r'[、\s]14[、。]')
                    links=package._targets(row)
                    self.assertTrue(links,method+' must link its current rule')
                    for target in links:
                        parts=package.urlsplit(target)
                        selector=(Path(relative).parent/package.unquote(parts.path)).as_posix()
                        if parts.fragment:selector+='#'+package.unquote(parts.fragment)
                        self.assertTrue(candidate.reader.read_section(selector,ROOT)['content'].strip())

    def test_integrity_missing_modified_and_added_payload_never_pass(self):
        with tempfile.TemporaryDirectory() as folder:
            root=self.clone(folder)
            self.assertTrue(package.inspect_structure(root,require_full_integrity=True)['passed'])
            path=root/'references/first-principles.md';original=path.read_bytes();path.write_bytes(original+b'changed')
            self.assertFalse(package.inspect_structure(root,require_full_integrity=True)['passed']);path.write_bytes(original)
            path.unlink();self.assertFalse(package.inspect_structure(root,require_full_integrity=True)['passed']);path.write_bytes(original)
            (root/'unexpected.txt').write_text('extra',encoding='utf-8');self.assertFalse(package.inspect_structure(root,require_full_integrity=True)['passed'])

if __name__=='__main__':unittest.main()
