import json
from pathlib import Path
import shutil
import tempfile
import unittest

import jury_candidates as candidate
import jury_read as reader
import jury_review_roles as roles
from test_current_workflow import work_task

ROOT = Path(__file__).resolve().parent.parent


class RemediationRoutingTests(unittest.TestCase):
    def observation(self, selected):
        return dict(currentScope=dict(kind='task', id='relevance-routing'),reviewDomain='unity',reviewStage='review',task=work_task('relevance-routing'),
                    availableModels=[dict(modelId='gpt-6.1-sol', efforts=['xhigh'])],
                    roles=selected)

    def test_front_probe_entry_reads_complete_contract_without_injecting_backend_views(self):
        selected = reader.read_section('references/message-style.md#user-facing', ROOT)
        for required in ('--record-file', '--audience user', 'accepted', 'appliesTo', 'features', 'jury-state'):
            self.assertIn(required, selected['content'])
        for role in ('progress', 'architecture'):
            prepared = roles.prepare(self.observation([role]), ROOT)
            self.assertNotIn('references/message-style.md#user-facing', prepared['dispatch'][0]['readSelectors'])
            self.assertNotIn('displayBoundary', prepared['dispatch'][0])

    def test_completion_and_correction_legacy_routes_preserve_stage_boundaries(self):
        common = reader.read_section('references/review-standard.md#decision-order', ROOT)
        priority = reader.read_section('references/review-standard.md#obligation-priority', ROOT)
        self.assertIn(priority['content'], common['content'])
        for anchor, leaf in [('completion-coverage', 'review-completion.md'),
                             ('workflow-correction', 'review-correction.md')]:
            old = 'references/review-standard.md#' + anchor
            new = 'references/' + leaf + '#' + anchor
            old_section = reader.read_section(old, ROOT)
            new_section = reader.read_section(new, ROOT)
            self.assertEqual(old_section['continuationSelectors'], [new])
            expected = [old, new]
            if anchor == 'completion-coverage':
                expected.append('references/review-completion.md#stop-request')
            self.assertEqual(candidate.expanded_reads([old], ROOT), expected)
            self.assertNotIn(new_section['content'], common['content'])
        self.assertNotIn('references/review-completion.md#stop-request',
                         candidate.expanded_reads(['references/review-standard.md#decision-order'], ROOT))

    def test_selected_preparation_catalogue_preserves_order_and_inspection(self):
        inspected = roles.inspect_installation(ROOT)
        self.assertEqual([r['role'] for r in inspected['roles']], ['progress', 'architecture'])
        catalogue = {r['role']: r for r in inspected['roles']}
        for selected in [['progress'], ['architecture'], ['architecture', 'progress']]:
            prepared = roles.prepare(self.observation(selected), ROOT)
            self.assertEqual(prepared['status'], 'prepared')
            self.assertEqual([r['role'] for r in prepared['roles']], selected)
            self.assertEqual([r['role'] for r in prepared['dispatch']], selected)
            self.assertEqual(prepared['roles'], [catalogue[r] for r in selected])
            self.assertFalse(prepared['autoExecute'])
            for call in prepared['dispatch']:
                self.assertFalse(call['initialInputIndependenceVerified'])
                self.assertEqual(len([k for k in call if k.endswith('Reminder')]), 9)

    def test_selected_catalogue_semantics_cover_legal_unavailable_and_unresolved_results(self):
        no_model = self.observation(['architecture'])
        no_model['availableModels'] = []
        unavailable = roles.prepare(no_model, ROOT)
        self.assertEqual(unavailable['status'], 'model-unavailable')
        self.assertEqual(unavailable['dispatch'], [])
        self.assertEqual([r['role'] for r in unavailable['roles']], ['architecture'])
        unresolved_input = self.observation(['architecture'])
        unresolved_input['existingAgents'] = {'architecture': 'declared-current-role'}
        unresolved = roles.prepare(unresolved_input, ROOT)
        self.assertEqual(unresolved['status'], 'dispatch-context-unresolved')
        self.assertEqual(unresolved['dispatch'], [])
        self.assertEqual([r['role'] for r in unresolved['roles']], ['architecture'])
        for flag in ['paused', 'cancelled']:
            held_input = self.observation(['architecture'])
            held_input[flag] = True
            held = roles.prepare(held_input, ROOT / 'does-not-exist')
            self.assertEqual(held['status'], 'held')
            self.assertEqual(held['dispatch'], [])
            self.assertNotIn('roles', held)

    def test_default_relevance_is_consumed_without_preloading_idle_or_closeout_details(self):
        for role in candidate.ROLES:
            planned = candidate.plan(ROOT, role=role, review_stage='review')
            prepared = roles.prepare(self.observation([role]), ROOT)['dispatch'][0]
            for selectors in [planned['readSelectors'], prepared['readSelectors']]:
                self.assertEqual(selectors.count(candidate.BOUNDED_INSPECTION), 1)
                self.assertIn('references/verification-scope.md#selection', selectors)
                self.assertNotIn('references/coordination.md#bounded-inspection', selectors)
                self.assertFalse(any(s.startswith('references/evidence-lifecycle.md#') for s in selectors))
                self.assertNotIn('references/review-completion.md#completion-coverage', selectors)
                self.assertNotIn('references/review-correction.md#workflow-correction', selectors)
            self.assertIn('references/review-completion.md#completion-coverage',
                          roles.prepare(self.observation([role]), ROOT)['requiredReviewContracts'])

    def test_missing_empty_and_restored_relevance_or_selection_controls_real_dispatch(self):
        with tempfile.TemporaryDirectory() as folder:
            owner = Path(folder).resolve()
            root = owner / 'jury'
            self.assertTrue(root.resolve().is_relative_to(owner))
            shutil.copytree(ROOT, root)
            path = root / 'references/verification-scope.md'
            original = path.read_bytes()
            self.assertTrue(roles.prepare(self.observation(['progress']), root)['ready'])
            path.unlink()
            self.assertEqual(roles.prepare(self.observation(['progress']), root)['dispatch'], [])
            path.write_bytes(original)
            for anchor in ['relevance', 'selection']:
                selector = 'references/verification-scope.md#' + anchor
                section = reader.read_section(selector, root)['content']
                text = original.decode('utf-8')
                empty = '<a id="' + anchor + '"></a>\n## Empty\n<!-- no visible contract -->\n'
                self.assertEqual(text.count(section), 1)
                path.write_bytes(text.replace(section, empty, 1).encode('utf-8'))
                with self.assertRaises(ValueError):
                    candidate.plan(root, role='progress', review_stage='review')
                self.assertEqual(roles.prepare(self.observation(['progress']), root)['dispatch'], [])
                path.write_bytes(original)
                self.assertTrue(roles.prepare(self.observation(['progress']), root)['ready'])


if __name__ == '__main__':
    unittest.main()
