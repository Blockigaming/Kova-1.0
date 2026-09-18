"""Check the complete current source policy without asserting runtime readiness.

Metadata pins are not weight verification or an execution grant. No model,
provider, quota, reset time, paid replenishment or runtime is activated here.
"""
import json
from pathlib import Path
import sys

from release.model_revisions import MODEL_SOURCE_REFERENCES, ROUTE_MODEL_SLOTS
from router.policy import CHAT_POLICIES, WORK_EFFORTS, WORK_FAMILY_POLICIES

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / 'config/current-product-policy.v2.json'
MAX_POLICY_BYTES = 64 * 1024


class CurrentPolicyError(ValueError):
    pass


def need(condition):
    if not condition:
        raise CurrentPolicyError('current product policy rejected')


def exact(actual, expected):
    """Require exact shapes and scalar types; False/0 and 2/2.0 differ."""
    need(type(actual) is type(expected))
    if type(expected) is dict:
        need(set(actual) == set(expected))
        for key, value in expected.items():
            exact(actual[key], value)
    elif type(expected) is list:
        need(len(actual) == len(expected))
        for value, sample in zip(actual, expected):
            exact(value, sample)
    else:
        need(actual == expected)


def expected_policy():
    # These are existing approved source values, not executable account grants.
    efforts = {
        'light': ('Lite', [0, 1, 0, 0], 2048),
        'medium': ('Medium', [1, 1, 0, 1], 4096),
        'high': ('High', [1, 2, 1, 1], 8192),
        'extra-high': ('Extra High', [2, 3, 2, 2], 16384),
        'max': ('Max', [2, 4, 2, 3], 24576),
    }
    work_efforts = {
        key: {'label': label, 'passes': passes, 'maximum_output_tokens': ceiling,
              'engine': 'kova-core'}
        for key, (label, passes, ceiling) in efforts.items()
    }
    work_efforts['ultra'] = {
        'label': 'Ultra', 'passes': None, 'maximum_output_tokens': 32768,
        'engine': 'kova-ultra', 'minimum_agents': 2, 'maximum_agents': 5,
        'uses_same_family_model_slot': True,
    }
    return {
        'schema_version': 2,
        'status': 'owner_approved_source_policy_not_runtime_integrated',
        'provenance': {
            'repository': 'Blockigaming/KovaGPT_Models', 'issue': 10,
            'comment_id': 5734534302, 'approved_on': '2026-09-18',
        },
        'chat': {
            'default_route_id': 'instant', 'default_label': 'Lite',
            'shared_model_slot': 'chat-shared',
            'same_underlying_model_across_efforts': True,
            'free': {'selectable': False, 'routes': ['instant']},
            'plus': {
                'routes': ['instant', 'medium', 'high'],
                'labels': {'instant': 'Lite', 'medium': 'Medium', 'high': 'Thinking'},
            },
            'pro': {
                'routes': ['instant', 'medium', 'high', 'extra-high', 'max', 'ultra'],
                'labels': {'instant': 'Lite', 'medium': 'Medium', 'high': 'High',
                           'extra-high': 'Extra High', 'max': 'Max', 'ultra': 'Ultra'},
            },
            'ultra': {'engine': 'kova-ultra', 'minimum_agents': 2,
                      'maximum_agents': 5, 'uses_same_model_slot': True},
            'paid_chat_uses_work_weekly_allowance': False,
        },
        'work': {
            'default_effort_id': 'light', 'default_label': 'Lite',
            'families': {family: {'display_name': 'Kova 5.6 ' + family.title(),
                                  'model_slot': 'work-' + family}
                         for family in ('cosmo', 'orion', 'nova')},
            'family_model_slots_must_be_distinct': True,
            'same_family_model_across_efforts': True,
            'efforts': work_efforts,
            'entitlements': {'free': [], 'plus': 'all_18', 'pro': 'all_18'},
        },
        'work_usage': {
            'period': 'weekly', 'plus_base_units': None, 'reset_anchor': None,
            'pro_multiplier': 5, 'paid_replenishment_allowed': True,
            'replenishment_units': None, 'replenishment_price_usd': None,
            'chat_remains_available_when_exhausted': True,
        },
        'model_slots': {
            slot: {'upstream_model': ref.model, 'upstream_revision': ref.revision,
                   'license': 'Apache-2.0',
                   'role': 'chat' if slot == 'chat-shared' else 'work',
                   'runtime_verified': False}
            for slot, ref in MODEL_SOURCE_REFERENCES.items()
        },
        'runtime_integration_required': True, 'phase_b_ready': False,
    }


def _unique(pairs):
    value = {}
    for key, item in pairs:
        need(key not in value)
        value[key] = item
    return value


def _reject_number(_value):
    # This policy has only integer counters; no floating numeric field exists.
    raise CurrentPolicyError('current product policy rejected')


def load_policy():
    try:
        with POLICY_PATH.open('rb') as stream:
            encoded = stream.read(MAX_POLICY_BYTES + 1)
        need(0 < len(encoded) <= MAX_POLICY_BYTES)
        value = json.loads(encoded.decode('utf-8'), object_pairs_hook=_unique,
                           parse_float=_reject_number, parse_constant=_reject_number)
        exact(value, expected_policy())
        return value
    except (OSError, ValueError, TypeError, UnicodeError, RecursionError, KeyError):
        raise CurrentPolicyError('current product policy rejected') from None


def _work_compute_matches(work):
    names = {'light': 'Light', 'medium': 'Medium', 'high': 'High',
             'extra-high': 'Extra High', 'max': 'Max', 'ultra': 'Ultra'}
    try:
        need(type(WORK_EFFORTS) is dict and set(WORK_EFFORTS) == set(names.values()))
        for effort, source_name in names.items():
            current = WORK_EFFORTS[source_name]
            declared = work['efforts'][effort]
            exact(current['maximum_output_tokens'], declared['maximum_output_tokens'])
            if effort == 'ultra':
                exact(current['dynamic_agents'], (2, 5))
                need(all(type(n) is int for n in current['dynamic_agents']))
            else:
                need(type(current['passes']) is tuple)
                exact(list(current['passes']), declared['passes'])
        return True
    except (CurrentPolicyError, KeyError, TypeError):
        return False


def validate():
    value = load_policy()
    slots = value['model_slots']
    return {
        'schema_version': 2,
        'status': 'current_policy_valid_runtime_integration_pending',
        'owner_comment_id': 5734534302,
        'chat_shared_model_policy_valid': True,
        'work_three_distinct_model_slots_policy_valid': True,
        'work_effort_contracts_match_current_compute': _work_compute_matches(value['work']),
        # Profile names or a model_slot string in source are not authenticated
        # observations of loaded weights. This checker has no runtime evidence.
        'runtime_chat_model_identity_aligned': False,
        'runtime_work_model_identity_aligned': False,
        'selected_upstream_models': {name: item['upstream_model'] for name, item in slots.items()},
        'selected_upstream_revisions': {name: item['upstream_revision'] for name, item in slots.items()},
        'missing_upstream_revision_slots': [],
        'source_route_model_slots': dict(ROUTE_MODEL_SLOTS),
        'auto_requires_resolved_chat_route': True,
        'revision_pin_scope': 'upstream_source_only',
        'verified_weight_artifact_slots': [],
        'quantized_serving_artifact_slots': [],
        'missing_plus_weekly_units': value['work_usage']['plus_base_units'] is None,
        'missing_reset_anchor': value['work_usage']['reset_anchor'] is None,
        'missing_replenishment_terms': (
            value['work_usage']['replenishment_units'] is None or
            value['work_usage']['replenishment_price_usd'] is None),
        'closed_checklist_ids': [],
        'phase_b_ready': False,
    }


def main():
    try:
        print(json.dumps(validate(), sort_keys=True))
    except CurrentPolicyError:
        print('current product policy rejected', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
