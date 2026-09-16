from dataclasses import replace
import json
import unittest

from execution.contracts import (
    ExecutionBlocked, ExecutionError, ExecutionGrant, ExecutionLimits, ExecutionSpec, canonical,
)
from execution.test_support import IDENTITY, grant_for, make_plan, make_spec


class ExecutionContractTests(unittest.TestCase):
    def test_all_24_explicit_routes_keep_names_and_original_budgets(self):
        from execution.contracts import ALL_ROUTES
        self.assertEqual(len(ALL_ROUTES), 24)
        for route in sorted(ALL_ROUTES):
            with self.subTest(route=route):
                spec = make_spec(route)
                self.assertEqual(spec.plan["route_id"], route)
                self.assertEqual(spec.limits.token_limit, sum(s.token_reservation for s in spec.stages))
                self.assertEqual(len([s for s in spec.stages if s.public]), 1)
                self.assertTrue(spec.stages[-1].public)

    def test_explicit_limits_reject_nonfinite_missing_boolean_and_invalid_values(self):
        baseline = make_spec().limits
        for name in ("deadline_unix_ms", "token_limit", "cost_limit_microusd", "max_parallel", "stage_timeout_seconds"):
            for value in (None, True, False, 0, -1, float("inf"), float("nan"), "10"):
                with self.subTest(name=name, value=value), self.assertRaises(ExecutionError):
                    replace(baseline, **{name: value})
        for value in (240, 600):
            with self.assertRaises(ExecutionError):
                replace(baseline, stage_timeout_seconds=value)
        with self.assertRaises(ExecutionError):
            replace(baseline, max_parallel=6)

    def test_source_and_budget_snapshots_are_defensive(self):
        plan = make_plan()
        expected = make_spec()
        caps = {s.id: 100 for s in expected.stages}
        spec = ExecutionSpec.from_plan(plan, limits=expected.limits, runtime_identity=IDENTITY,
                                       stage_cost_caps=caps)
        fingerprint = spec.fingerprint
        plan["display_name"] = "changed"
        caps.clear()
        copy = spec.plan
        copy["display_name"] = "changed again"
        self.assertEqual(spec.fingerprint, fingerprint)
        self.assertEqual(spec.plan["display_name"], "Kova 5.6 Nova")
        self.assertNotIn("PRIVATE", repr(spec))

    def test_every_stage_needs_explicit_cost_bounds_and_total_admission(self):
        original = make_spec()
        caps = {s.id: 100 for s in original.stages}
        for changed in ({}, {**caps, "unknown": 1}, {**caps, original.stages[0].id: None}):
            with self.assertRaises(ExecutionError):
                ExecutionSpec.from_plan(original.plan, limits=original.limits, runtime_identity=IDENTITY,
                                        stage_cost_caps=changed)
        for field in ("token_limit", "cost_limit_microusd"):
            with self.subTest(field=field), self.assertRaises(ExecutionError):
                ExecutionSpec.from_plan(original.plan, limits=replace(original.limits, **{field: 1}),
                                        runtime_identity=IDENTITY, stage_cost_caps=caps)

    def test_snapshot_rejects_tampered_dependencies_budgets_visibility_and_pins(self):
        for mutate in (
            lambda v: v["stages"][0].update(dependencies=["verification-1"]),
            lambda v: v["stages"][0].update(id="forged"),
            lambda v: v["stages"][0].update(public=True),
            lambda v: v["stages"][0].update(maximum_output_tokens=999),
            lambda v: v["stages"][0].update(condition="always"),
            lambda v: v["runtime_identity"].update(model_revision="unpinned"),
            lambda v: v["runtime_identity"].update(context_tokens=1),
            lambda v: v["plan"].update(production_ready=True),
            lambda v: v["plan"].update(route_id="thinking"),
        ):
            value = make_spec().snapshot()
            mutate(value)
            with self.assertRaises(ExecutionError):
                ExecutionSpec(canonical(value))

    def test_chat_plan_caps_cannot_be_widened_by_allowed_route_list(self):
        for tier, denied in (("free", ["medium", "high", "ultra"]), ("plus", ["extra-high", "max", "ultra"])):
            for route in denied:
                spec = make_spec(route)
                with self.subTest(tier=tier, route=route), self.assertRaises(ExecutionBlocked):
                    grant_for(spec, tier=tier).authorize("fixture-owner", route)

    def test_work_permissions_and_ultra_pro_are_explicit(self):
        spec = make_spec("work:nova:high")
        grant = grant_for(spec)
        grant.authorize(grant.owner_id, spec.plan["route_id"])
        with self.assertRaises(ExecutionBlocked):
            replace(grant, allowed_routes=frozenset()).authorize(grant.owner_id, spec.plan["route_id"])
        for tier in ("free", "plus"):
            spec = make_spec("work:nova:ultra")
            with self.assertRaises(ExecutionBlocked):
                grant_for(spec, tier=tier).authorize(grant.owner_id, spec.plan["route_id"])

    def test_unrecovered_free_thinking_and_auto_are_not_direct_execution_routes(self):
        for route in ("thinking", "kova-auto", "auto", "extra_high"):
            with self.subTest(route=route), self.assertRaises(ExecutionError):
                ExecutionGrant("fixture", "pro", frozenset((route,)), True)

    def test_grants_disabled_by_default_and_bound_to_the_owner(self):
        spec = make_spec()
        grant = ExecutionGrant("fixture-owner", "pro", frozenset(("high",)))
        with self.assertRaises(ExecutionBlocked):
            grant.authorize(grant.owner_id, "high")
        with self.assertRaises(ExecutionBlocked):
            grant_for(spec).authorize("different-owner", "high")


if __name__ == "__main__":
    unittest.main()
