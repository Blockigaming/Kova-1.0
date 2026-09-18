"""Negative controls for the checked-in current policy's evidence boundary."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from release import current_product_policy as policy


class CurrentPolicyIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.source = json.loads(policy.POLICY_PATH.read_text(encoding='utf-8'))

    def evaluate_bytes(self, data):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'PRIVATE-policy.json'
            path.write_bytes(data)
            with patch.object(policy, 'POLICY_PATH', path):
                return policy.validate()

    def evaluate(self, value):
        return self.evaluate_bytes(json.dumps(value).encode())

    def reject(self, value):
        with self.assertRaisesRegex(policy.CurrentPolicyError, '^current product policy rejected$'):
            self.evaluate(value)

    def test_runtime_readiness_promotion_is_rejected(self):
        self.source['phase_b_ready'] = True
        self.reject(self.source)

    def test_runtime_integration_requirement_cannot_be_disabled(self):
        self.source['runtime_integration_required'] = False
        self.reject(self.source)

    def test_unknown_root_authorization_is_rejected(self):
        self.source['execution_authorized'] = True
        self.reject(self.source)

    def test_boolean_and_float_policy_lookalikes_are_rejected(self):
        for path, value in [(('schema_version',), 2.0),
                            (('chat', 'free', 'selectable'), 0),
                            (('work_usage', 'pro_multiplier'), 5.0),
                            (('chat', 'ultra', 'minimum_agents'), 2.0)]:
            with self.subTest(path=path):
                changed = deepcopy(self.source)
                target = changed
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = value
                self.reject(changed)

    def test_boolean_compute_pass_cannot_stand_in_for_integer(self):
        self.source['work']['efforts']['medium']['passes'][0] = True
        self.reject(self.source)

    def test_missing_fields_have_controlled_failure(self):
        for name in ('chat', 'work', 'work_usage', 'model_slots'):
            with self.subTest(name=name):
                value = deepcopy(self.source)
                del value[name]
                self.reject(value)

    def test_wrong_container_shapes_have_controlled_failure(self):
        for field in ('chat', 'work', 'work_usage', 'model_slots'):
            for bad in (None, [], 'PRIVATE-payload', 12):
                with self.subTest(field=field, bad=bad):
                    value = deepcopy(self.source)
                    value[field] = bad
                    self.reject(value)

    def test_unlisted_work_effort_is_rejected(self):
        self.source['work']['efforts']['unlimited'] = self.source['work']['efforts']['ultra']
        self.reject(self.source)

    def test_family_slot_swaps_are_rejected(self):
        a, b = self.source['work']['families']['cosmo'], self.source['work']['families']['nova']
        a['model_slot'], b['model_slot'] = b['model_slot'], a['model_slot']
        self.reject(self.source)

    def test_unknown_distinct_family_slots_are_rejected(self):
        self.source['work']['families']['cosmo']['model_slot'] = 'caller-chosen'
        self.reject(self.source)

    def test_family_display_name_drift_is_rejected(self):
        self.source['work']['families']['cosmo']['display_name'] = 'PRIVATE-claim'
        self.reject(self.source)

    def test_unknown_nested_fields_are_rejected(self):
        for path in [('chat', 'plus'), ('chat', 'free'), ('work', 'efforts', 'high'),
                     ('work_usage',), ('model_slots', 'chat-shared')]:
            with self.subTest(path=path):
                value = deepcopy(self.source)
                target = value
                for key in path:
                    target = target[key]
                target['runtime_approved'] = True
                self.reject(value)

    def test_duplicate_json_keys_are_not_last_write_wins(self):
        raw = json.dumps(self.source).replace('"schema_version": 2',
                                             '"schema_version": 99, "schema_version": 2', 1)
        with self.assertRaises(policy.CurrentPolicyError):
            self.evaluate_bytes(raw.encode())

    def test_nested_duplicate_keys_are_rejected(self):
        raw = json.dumps(self.source).replace('"default_label": "Lite"',
                       '"default_label": "Wrong", "default_label": "Lite"', 1)
        with self.assertRaises(policy.CurrentPolicyError):
            self.evaluate_bytes(raw.encode())

    def test_nonfinite_and_deep_json_are_controlled(self):
        samples = [b'NaN', b'{"x": Infinity}', b'{"x": 1e999}', b'[' * 2000 + b']' * 2000,
                   b'\xff', b'{', b'null']
        for raw in samples:
            with self.subTest(raw=raw[:40]), self.assertRaisesRegex(
                    policy.CurrentPolicyError, '^current product policy rejected$'):
                self.evaluate_bytes(raw)

    def test_oversized_policy_is_rejected(self):
        raw = b' ' * (64 * 1024 + 1) + json.dumps(self.source).encode()
        with self.assertRaises(policy.CurrentPolicyError):
            self.evaluate_bytes(raw)

    def test_missing_policy_file_has_sanitized_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(policy, 'POLICY_PATH', Path(folder) / 'PRIVATE-missing.json'):
                with self.assertRaisesRegex(policy.CurrentPolicyError,
                                            '^current product policy rejected$'):
                    policy.validate()

    def test_fake_runtime_profile_alignment_is_not_execution_evidence(self):
        chat = deepcopy(policy.CHAT_POLICIES)
        work = deepcopy(policy.WORK_FAMILY_POLICIES)
        for entry in chat.values():
            entry['profile'] = 'chat-shared'
        for family, entry in work.items():
            entry['model_slot'] = 'work-' + family
        with patch.object(policy, 'CHAT_POLICIES', chat), \
             patch.object(policy, 'WORK_FAMILY_POLICIES', work):
            report = policy.validate()
        self.assertIs(report['runtime_chat_model_identity_aligned'], False)
        self.assertIs(report['runtime_work_model_identity_aligned'], False)
        self.assertEqual(report['closed_checklist_ids'], [])
        self.assertIs(report['phase_b_ready'], False)


if __name__ == '__main__':
    unittest.main()
