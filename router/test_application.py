from copy import deepcopy
import json
from pathlib import Path
import subprocess
import unittest

from execution.contracts import ALL_ROUTES, ExecutionBlocked, ExecutionError, ExecutionGrant
from router.application import LegacySelectionRequired, SELECTION_SCHEMA, resolve_application_selection
from router.policy import CHAT_POLICIES, WORK_EFFORTS, WORK_FAMILIES


ROOT = Path(__file__).resolve().parents[1]


def grant(tier="pro", routes=ALL_ROUTES, enabled=True):
    return ExecutionGrant("application-fixture-owner", tier, frozenset(routes), enabled)


def selection(mode="instant", **changes):
    return {"schema_version": SELECTION_SCHEMA, "surface": "chat", "mode_id": mode, **changes}


BUDGET = {"ultra_authorized": True, "remaining_usd": 1, "estimated_ultra_usd": 0.5}


class ApplicationBridgeTests(unittest.TestCase):
    def resolve(self, value, **kwargs):
        return resolve_application_selection(value, grant=kwargs.pop("grant", grant()), **kwargs)

    def test_all_six_chat_profiles_and_extra_high_aliases_keep_names_and_policies(self):
        for route, policy in CHAT_POLICIES.items():
            for mode in (("extra_high", "extra-high") if route == "extra-high" else (route,)):
                with self.subTest(mode=mode):
                    resolved = self.resolve(selection(mode))
                    self.assertEqual(resolved.route_id, route)
                    self.assertEqual(resolved.policy()["display_name"], policy["display_name"])
                    self.assertEqual(resolved.policy().get("passes"), policy.get("passes"))
                    self.assertFalse(resolved.selected_by_auto)
                    self.assertEqual(resolved.application_mode_id, "extra_high" if route == "extra-high" else route)
                    self.assertFalse(resolved.metadata()["production_routing_enabled"])

    def test_all_eighteen_work_combinations_preserve_family_and_effort_policy(self):
        count = 0
        for family in sorted(WORK_FAMILIES):
            for effort, policy in WORK_EFFORTS.items():
                aliases = (effort, effort.lower().replace(" ", "-"))
                if effort == "Extra High":
                    aliases += ("extra_high",)
                for alias in aliases:
                    with self.subTest(family=family, effort=alias):
                        value = {"schema_version": SELECTION_SCHEMA, "surface": "work", "family": family, "effort": alias}
                        resolved = self.resolve(value)
                        self.assertEqual(resolved.route_id, f"work:{family}:{effort.lower().replace(' ', '-')}")
                        self.assertEqual(resolved.policy()["maximum_output_tokens"], policy["maximum_output_tokens"])
                        self.assertEqual(resolved.policy().get("passes"), policy.get("passes"))
                        self.assertIsNone(resolved.application_mode_id)
                count += 1
        self.assertEqual(count, 18)

    def test_versioned_auto_routes_through_classifier_not_legacy_instant_alias(self):
        prompt = "Research competitors and prepare a comprehensive full report."
        for alias in ("auto", "kova-auto"):
            result = self.resolve(selection(alias), prompt=prompt, auto_budget=BUDGET, auto_enabled=True)
            self.assertEqual(result.route_id, "ultra")
            self.assertTrue(result.selected_by_auto)
            self.assertIn("ultra_budget_admitted", result.feature_ids)
            with self.assertRaises(LegacySelectionRequired):
                self.resolve({"surface": "chat", "mode_id": alias}, prompt=prompt, auto_budget=BUDGET, auto_enabled=True)

    def test_free_thinking_maps_to_orion_only_as_the_free_alias(self):
        resolved = self.resolve(selection("thinking"), grant=grant("free"))
        self.assertEqual(resolved.route_id, "medium")
        self.assertEqual(resolved.application_mode_id, "thinking")
        self.assertEqual(resolved.policy()["display_name"], "Kova 5.6 Orion")
        self.assertFalse(resolved.selected_by_auto)
        with self.assertRaises(ExecutionBlocked):
            self.resolve(selection("medium"), grant=grant("free"))
        with self.assertRaises(ExecutionBlocked):
            self.resolve(selection("thinking"), grant=grant("free", routes={"instant"}))
        for tier in ("plus", "pro"):
            with self.subTest(tier=tier), self.assertRaises(ExecutionBlocked):
                self.resolve(selection("thinking"), grant=grant(tier))
        for mode in ("creative", "precise", "code", "study", "default", "pro", "research", "kova_5_5", "UNKNOWN"):
            with self.subTest(mode=mode), self.assertRaises(ExecutionError):
                self.resolve(selection(mode))

    def test_exact_application_entitlements_match_the_pinned_executable_fixture(self):
        command = ["node", "--input-type=module", "-e",
                   'import {MODE_IDS_BY_TIER} from "./tests/fixtures/app-mode-entitlements.mjs"; console.log(JSON.stringify(MODE_IDS_BY_TIER))']
        app = json.loads(subprocess.check_output(command, cwd=ROOT, text=True, timeout=5))
        contract = json.loads((ROOT / "config/application-bridge.v1.json").read_text())
        self.assertEqual(app, contract["application_chat_modes"])
        self.assertEqual(self.resolve(selection("thinking"), grant=grant("free")).route_id, "medium")
        for tier, modes in app.items():
            for route in CHAT_POLICIES:
                app_id = "extra_high" if route == "extra-high" else route
                if app_id in modes:
                    self.assertEqual(self.resolve(selection(app_id), grant=grant(tier)).route_id, route)
                else:
                    with self.assertRaises(ExecutionBlocked):
                        self.resolve(selection(app_id), grant=grant(tier))

    def test_auto_remains_within_tier_exact_allowlist_and_runtime_budget(self):
        prompts = ("What is 8 + 7?", "Debug this React error", "Analyze security",
                   "Analyze architecture " + "context " * 145,
                   "Research competitors and create a comprehensive full report.")
        allowed = {"free": {"instant"}, "plus": {"instant", "medium", "high"}, "pro": set(CHAT_POLICIES)}
        for tier, routes in allowed.items():
            for prompt in prompts:
                for enabled in (False, True):
                    for remaining in (0, 1):
                        result = self.resolve(selection("auto"), grant=grant(tier), prompt=prompt, auto_enabled=True,
                                              auto_budget={**BUDGET, "ultra_authorized": enabled, "remaining_usd": remaining})
                        self.assertIn(result.route_id, routes)
                        if result.route_id == "ultra":
                            self.assertEqual(tier, "pro")
                            self.assertTrue(enabled)
                            self.assertEqual(remaining, 1)
        with self.assertRaises(ExecutionBlocked):
            self.resolve(selection("auto"), grant=grant(routes={"instant"}), prompt="Analyze architecture",
                         auto_enabled=True, auto_budget=BUDGET)

    def test_auto_disabled_by_default_and_client_cannot_enable_it(self):
        with self.assertRaises(ExecutionBlocked):
            self.resolve(selection("auto"), prompt="hello", auto_budget=BUDGET)
        for key in ("auto_enabled", "tier", "allowed_routes", "budget", "remaining_usd", "owner_id", "execution_authorized"):
            with self.subTest(key=key), self.assertRaises(ExecutionError):
                self.resolve(selection("auto", **{key: True}), auto_enabled=True, prompt="hello", auto_budget=BUDGET)
        for flag in (1, None, "true"):
            with self.assertRaises(ExecutionError):
                self.resolve(selection("auto"), auto_enabled=flag)

    def test_complete_work_entitlement_matrix_is_plan_bounded_and_exact_route_bounded(self):
        for tier in ("free", "plus", "pro"):
            for family in sorted(WORK_FAMILIES):
                for effort in WORK_EFFORTS:
                    value = {"schema_version": SELECTION_SCHEMA, "surface": "work", "family": family, "effort": effort}
                    route = f"work:{family}:{effort.lower().replace(' ', '-')}"
                    expected = tier == "pro" or (tier == "plus" and effort in ("Light", "Medium", "High"))
                    with self.subTest(tier=tier, route=route):
                        if expected:
                            self.assertEqual(self.resolve(value, grant=grant(tier)).route_id, route)
                            with self.assertRaises(ExecutionBlocked):
                                self.resolve(value, grant=grant(tier, routes={"instant"}))
                        else:
                            with self.assertRaises(ExecutionBlocked):
                                self.resolve(value, grant=grant(tier))

    def test_disabled_grant_and_untrusted_grant_types_fail_before_selection(self):
        with self.assertRaises(ExecutionBlocked):
            self.resolve(selection(), grant=grant(enabled=False))
        for bad in ({"tier": "pro"}, None, "pro", True):
            with self.assertRaises(ExecutionError):
                self.resolve(selection(), grant=bad)

    def test_unknown_payload_fields_cannot_override_model_or_behavior(self):
        for field in ("model", "provider", "engine", "messages", "system_prompt", "reasoning_effort", "passes", "max_tokens", "headers", "destination"):
            with self.subTest(field=field), self.assertRaises(ExecutionError):
                self.resolve(selection("high", **{field: "untrusted"}))

    def test_invalid_shapes_and_schema_versions_fail_closed(self):
        for value in (None, [], "high", 1, selection(schema_version=2), selection(schema_version=True),
                      selection(schema_version="kova-models.v2"), selection(surface=[]), selection(surface="Work"),
                      selection(mode_id=[]), selection(mode_id=None), selection(mode_id="HIGH")):
            with self.subTest(value=value), self.assertRaises(ExecutionError):
                self.resolve(value)
        work = {"schema_version": SELECTION_SCHEMA, "surface": "work", "family": "nova", "effort": "High"}
        for changes in ({"family": []}, {"family": "Nova"}, {"effort": []}, {"effort": "highest"}, {"mode_id": "high"}):
            with self.assertRaises(ExecutionError):
                self.resolve(work | changes)

    def test_payload_policies_and_metadata_are_defensive(self):
        original = selection("high")
        saved = deepcopy(original)
        resolved = self.resolve(original)
        self.assertEqual(original, saved)
        policy = resolved.policy()
        policy["passes"] = (100, 100, 100, 100)
        original["mode_id"] = "instant"
        self.assertEqual(resolved.policy()["passes"], (1, 1, 1, 1))
        metadata = resolved.metadata()
        metadata["feature_ids"].append("forged")
        self.assertEqual(resolved.metadata()["feature_ids"], [])
        self.assertNotIn("behavior_instruction", metadata)
        self.assertNotIn("system_prompt", metadata)


if __name__ == "__main__":
    unittest.main()
