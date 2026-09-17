# A36/A37: unapproved product-decision preparation

This prepares the remaining decisions for review; **A36 and A37 remain open**.
No Free Thinking mapping, Work permission, response target, active-work duration
or Extra High semantic reconciliation was approved by this implementation.
The fixed Phase A checklist remains forty items. Test growth, a populated form,
and a structurally valid proposal never close an item or make Phase B ready.

## Authoritative facts versus this proposed representation

The original fixed rubric is Models issue #10, comment 5704782775. The recovered
September 17 Models handoff leaves the custom Free Thinking mapping, complete
Work tier matrix, numeric response/active-work requirements and Extra High
conceptual-pass interpretation unresolved. That history is not replaced here.

The checked-in `config/product-decisions.v1.json` records only null decisions.
Its protected source snapshot is PR #24 commit
`38a1a020029c9c007652a554592f0a197e7b8dfb`; four original JSON files are SHA-256
bound and unchanged. This identifies model-side recorded source, **not current
live app entitlement or deployed model evidence**. The current Chat entitlements,
Pro prerequisite for Ultra, Core/Ultra names and policies remain controlling.

The new proposal schema is an engineering review format, **not additional owner
requirements**. There are 54 Work permission cells (three tiers by eighteen
combinations), 25 cold/warm completed-answer target entries, 25 active-execution
entries and two unresolved interpretation fields. Its 131 initially blank leaf
fields are not 131 checklist items, product decisions, or separate questions the
owner must answer. One explicit owner decision may cover several entries; an
assistant must not fill others by analogy. This source adds no requirements to
the forty-item rubric and does not declare any proposed value approved.

## Preserved boundaries

- Legacy Free Thinking remains on the existing application path. A proposal can
  describe retaining that path or selecting an existing custom Chat route, but
  does not change `CHAT_ALLOWED`, the app bridge, or `ExecutionGrant.authorize`.
  A proposed custom route above Instant therefore remains blocked by current
  Free execution permissions. Auto/Work/unknown IDs are not Chat mappings.
- Pro is necessary for Ultra; it is not automatic proof of a Work entitlement.
  All 54 checked-in Work cells stay unknown. Null is not denial or permission;
  a proposed explicit false is different from a missing decision. Non-Pro Ultra
  grants contradict the preserved prerequisite and are rejected.
- The recovered Cosmo warm first-visible-answer-token goal is ideally 1–3 seconds
  or faster. It remains a non-measured goal, not a hard deadline, completed-answer
  average or minimum wait. Nothing sleeps, estimates latency, loads a model, or
  extrapolates this goal to other routes.
- Genuine acknowledgement, first visible answer token, completed answer and
  maximum active execution remain distinct clocks. Cold and warm completed-answer
  proposals are separate. A numeric target names its statistic. An explicitly
  proposed `no_fixed_target` is also representable; it is not selected by default
  and must not be inferred from an absent number.
- Proposed active limits require positive integer milliseconds and an explicit
  measurement definition. Zero, booleans, strings and infinity cannot mean
  unlimited runtime. Definition prose is for review, not executable policy. This
  does not implement an active-time meter or select queue/pause/restart semantics;
  the existing wall-clock expiry in `ExecutionLimits` is unchanged.
- Extra High's current Chat 2/2/2/2 policy and historical conceptual description
  are retained separately. A proposed explanation does not mutate the planner
  or claim that reasoning passes equal answer passes.

There is no approval, apply, deploy, execute, grant, self-review or close-checklist
interface. Even a completely populated valid proposal reports owner approval,
runtime-policy changes and Phase B readiness as false, with no closed checklist
IDs. Reports omit free-text rationales/definitions. No auth, job API, tool runner,
public listener, browser code or cloud client is installed or bypassed.

## Reproduction

`python3 -m unittest release.test_product_decisions -v` runs synthetic checks.
Fixture choices are not product recommendations or approvals.

`npm run validate:product-decisions` validates the unchanged source snapshot and
pending record. Exit zero means **valid unresolved source**, not product readiness.
It is appended to existing preflight; all previous gates remain in place.

`npm run check:product-ready` prints the same unresolved evidence and exits **78**.
It is intentionally separate from source preflight so that blocked product policy
cannot be confused with broken unit tests. It checks this A36/A37 preparation
boundary only, not overall forty-item readiness.

For a separately prepared, public-safe proposal file:

```
python3 -m release.product_decisions --proposal PROPOSAL.json
```

Only the `decisions` object is editable in a proposal. All known facts/source pins
and the forty-item rubric must match exactly. JSON is size/node/depth bounded,
strictly typed and rejects duplicate keys, invalid Unicode, nonfinite values and
floating-point representations. No input file is written. Invalid CLI input
produces a sanitized error without echoing file paths or document content.

A valid proposal still needs explicit owner confirmation/recovery, reviewed
source-policy changes, actual entitlement/active-time integration and applicable
tests. These are remaining work, not approval obtained by this validator. The
historical archive and A22/A26 publication restrictions remain independent
blockers. This preparation neither recovers that archive nor reimplements those
blocked payloads. Independent review is also still required.

Sources checked September 17, 2026:
- https://github.com/Blockigaming/Kova-1.0/issues/10#issuecomment-5704782775
- https://github.com/Blockigaming/Kova-1.0/issues/10#issuecomment-5716271030
- Attached `KovaGPT_Models_Full_Handoff_2026-09-17(1).md`, sections 5–8 and 12.
