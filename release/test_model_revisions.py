"""Offline source-reference tests; never a model download or execution grant."""
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from dataclasses import FrozenInstanceError
import io
import json
from pathlib import Path
import socket
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from release import current_product_policy as policy
from release.model_revisions import (
    CHAT_SOURCE_ROUTES, MODEL_SOURCE_REFERENCES, ROUTE_MODEL_SLOTS,
    WORK_SOURCE_EFFORTS, source_reference_for_route,
)

EXPECTED = {
    'chat-shared': ('Qwen/Qwen3-8B', 'b968826d9c46dd6066d109eabc6255188de91218'),
    'work-cosmo': ('Qwen/Qwen3-0.6B', 'c1899de289a04d12100db370d81485cdf75e47ca'),
    'work-orion': ('Qwen/Qwen3-1.7B', '70d244cc86ccca08cf5af4e1e306ecf908b1ad5e'),
    'work-nova': ('Qwen/Qwen3-4B', '1cfa9a7208912126459214e8b04321603b3df60c'),
}


class ModelRevisionTests(unittest.TestCase):
    def reject_policy(self, mutate):
        value = policy.load_policy()
        mutate(value)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'PRIVATE-policy.json'
            path.write_text(json.dumps(value), encoding='utf-8')
            with patch.object(policy, 'POLICY_PATH', path):
                with self.assertRaisesRegex(policy.CurrentPolicyError,
                                            '^current product policy rejected$'):
                    policy.validate()

    def test_exact_official_source_pins_match_the_checked_policy(self):
        value = policy.load_policy()
        self.assertEqual(set(MODEL_SOURCE_REFERENCES), set(EXPECTED))
        for slot, pair in EXPECTED.items():
            with self.subTest(slot=slot):
                ref = MODEL_SOURCE_REFERENCES[slot]
                self.assertEqual((ref.model, ref.revision), pair)
                self.assertEqual(ref.slot, slot)
                self.assertEqual(value['model_slots'][slot]['upstream_model'], pair[0])
                self.assertEqual(value['model_slots'][slot]['upstream_revision'], pair[1])
                self.assertRegex(ref.revision, r'^[a-f0-9]{40}$')

    def test_commit_urls_are_official_immutable_source_urls_not_weight_downloads(self):
        for slot, (model, revision) in EXPECTED.items():
            self.assertEqual(MODEL_SOURCE_REFERENCES[slot].source_url,
                             f'https://huggingface.co/{model}/commit/{revision}')

    def test_every_chat_effort_including_ultra_keeps_the_same_source_identity(self):
        self.assertEqual(CHAT_SOURCE_ROUTES,
                         ('instant', 'medium', 'high', 'extra-high', 'max', 'ultra'))
        for route in CHAT_SOURCE_ROUTES:
            with self.subTest(route=route):
                self.assertIs(source_reference_for_route(route),
                              MODEL_SOURCE_REFERENCES['chat-shared'])

    def test_each_work_family_has_six_efforts_on_its_own_exact_source(self):
        self.assertEqual(WORK_SOURCE_EFFORTS,
                         ('light', 'medium', 'high', 'extra-high', 'max', 'ultra'))
        for family in ('cosmo', 'orion', 'nova'):
            for effort in WORK_SOURCE_EFFORTS:
                with self.subTest(family=family, effort=effort):
                    ref = source_reference_for_route(f'work:{family}:{effort}')
                    self.assertIs(ref, MODEL_SOURCE_REFERENCES['work-' + family])
                    self.assertEqual((ref.model, ref.revision), EXPECTED['work-' + family])
        self.assertEqual(len({MODEL_SOURCE_REFERENCES['work-' + name].model
                              for name in ('cosmo', 'orion', 'nova')}), 3)

    def test_source_lookup_contains_exactly_the_24_canonical_execution_routes(self):
        expected = set(CHAT_SOURCE_ROUTES) | {
            f'work:{family}:{effort}' for family in ('cosmo', 'orion', 'nova')
            for effort in WORK_SOURCE_EFFORTS}
        self.assertEqual(set(ROUTE_MODEL_SLOTS), expected)
        self.assertEqual(len(ROUTE_MODEL_SLOTS), 24)

    def test_auto_must_resolve_via_the_existing_trusted_routing_boundary(self):
        with self.assertRaisesRegex(ValueError, '^model source route rejected$'):
            source_reference_for_route('auto')
        self.assertIs(policy.validate()['auto_requires_resolved_chat_route'], True)

    def test_aliases_unknown_and_provider_override_inputs_are_not_model_identities(self):
        for value in (None, True, 0, [], {}, {'route_id': 'instant', 'model': 'caller'},
                      'thinking', 'Lite', 'lite', 'extra_high', 'work:cosmo:lite',
                      'work:cosmo:instant', 'work:nova:deep', 'work:unknown:light',
                      ' instant', 'instant\n', 'work:*', 'https://caller.example/model'):
            with self.subTest(value=value), self.assertRaisesRegex(
                    ValueError, '^model source route rejected$'):
                source_reference_for_route(value)

    def test_source_catalog_and_returned_records_cannot_be_edited_normally(self):
        with self.assertRaises(TypeError):
            ROUTE_MODEL_SLOTS['instant'] = 'work-cosmo'
        with self.assertRaises(TypeError):
            MODEL_SOURCE_REFERENCES['work-nova'] = MODEL_SOURCE_REFERENCES['work-cosmo']
        with self.assertRaises(FrozenInstanceError):
            source_reference_for_route('instant').revision = 'main'

    def test_unpinned_or_different_revision_cannot_silently_replace_a_source(self):
        for slot in EXPECTED:
            for bad in (None, 'main', 'latest', 'v1.0', EXPECTED[slot][1][:8],
                        EXPECTED[slot][1].upper(), 'f' * 40, True):
                with self.subTest(slot=slot, revision=bad):
                    self.reject_policy(lambda value: value['model_slots'][slot].update(
                        upstream_revision=bad))

    def test_swapping_model_revisions_or_names_between_families_is_rejected(self):
        for field in ('upstream_model', 'upstream_revision'):
            self.reject_policy(lambda value: value['model_slots']['work-cosmo'].update(
                {field: value['model_slots']['work-nova'][field]}))

    def test_pin_never_self_promotes_to_weight_or_runtime_verification(self):
        for slot in EXPECTED:
            self.reject_policy(lambda value: value['model_slots'][slot].update(runtime_verified=True))
        report = policy.validate()
        self.assertEqual(report['revision_pin_scope'], 'upstream_source_only')
        self.assertEqual(report['verified_weight_artifact_slots'], [])
        self.assertEqual(report['quantized_serving_artifact_slots'], [])
        self.assertIs(report['phase_b_ready'], False)
        self.assertEqual(report['closed_checklist_ids'], [])

    def test_reports_are_fresh_copies_and_do_not_modify_future_source_selection(self):
        report = policy.validate()
        report['source_route_model_slots']['instant'] = 'work-cosmo'
        report['selected_upstream_revisions']['chat-shared'] = 'main'
        fresh = policy.validate()
        self.assertEqual(fresh['source_route_model_slots']['instant'], 'chat-shared')
        self.assertEqual(fresh['selected_upstream_revisions']['chat-shared'], EXPECTED['chat-shared'][1])

    def test_introspection_uses_no_network_model_process_or_cloud_api(self):
        with patch.object(socket, 'socket', side_effect=AssertionError('unexpected network')), \
             patch.object(subprocess, 'Popen', side_effect=AssertionError('unexpected process')):
            policy.validate()
            for route in ROUTE_MODEL_SLOTS:
                source_reference_for_route(route)

    def test_work_compute_metadata_drift_is_reported_without_rewriting_policy(self):
        original = deepcopy(policy.WORK_EFFORTS)
        for bad in (True, 1.0, 99):
            with self.subTest(value=bad):
                changed = deepcopy(original)
                changed['Medium']['passes'] = (bad, 1, 0, 1)
                with patch.object(policy, 'WORK_EFFORTS', changed):
                    report = policy.validate()
                self.assertIs(report['work_effort_contracts_match_current_compute'], False)
                self.assertIs(report['phase_b_ready'], False)
        self.assertEqual(policy.WORK_EFFORTS, original)

    def test_ultra_agent_range_and_extra_efforts_do_not_evade_compute_comparison(self):
        for mutate in (lambda work: work['Ultra'].update(dynamic_agents=(2, 99)),
                       lambda work: work.update({'Unbounded': work['Ultra']})):
            changed = deepcopy(policy.WORK_EFFORTS)
            mutate(changed)
            with patch.object(policy, 'WORK_EFFORTS', changed):
                self.assertIs(policy.validate()['work_effort_contracts_match_current_compute'], False)

    def test_cli_failure_is_nonzero_and_does_not_leak_path_or_payload(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'PRIVATE-config.json'
            path.write_text('{"PRIVATE-payload":true}', encoding='utf-8')
            output, error = io.StringIO(), io.StringIO()
            with patch.object(policy, 'POLICY_PATH', path), redirect_stdout(output), redirect_stderr(error):
                status = policy.main()
            self.assertEqual(status, 1)
            self.assertEqual(output.getvalue(), '')
            self.assertEqual(error.getvalue(), 'current product policy rejected\n')

    def test_cli_success_is_source_only_and_does_not_set_ready(self):
        output, error = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(error):
            status = policy.main()
        self.assertEqual(status, 0)
        self.assertEqual(error.getvalue(), '')
        self.assertIs(json.loads(output.getvalue())['phase_b_ready'], False)


if __name__ == '__main__':
    unittest.main()
