# Split note: 00265-close-the-critical-row-escapes-v1.md
planned=9 prd_tasks=9 expansion=1.00 reasons=module_drift

## skills/review-work-completion/references (UNLISTED)

- 5 phase-review prose: stamp carry_refs/carry_cycle at re-queue, two sites: skills/review-work-completion/references/output-formats.md

## skills/review-work-completion/scripts (UNLISTED)

- 5 phase-review prose: stamp carry_refs/carry_cycle at re-queue, two sites: skills/review-work-completion/scripts/test_review_verbs_prose.py
- 9 help text: gate.py and __main__.py docstrings describe the two-way check (#10): skills/review-work-completion/scripts/test_review_verbs_prose.py

## skills/run-autopilot/references (UNLISTED)

- 5 phase-review prose: stamp carry_refs/carry_cycle at re-queue, two sites: skills/run-autopilot/references/phase-review.md, skills/run-autopilot/references/recovery.md
- 8 CHANGELOG Unreleased + phase-review.md:280 final carry/coverage prose (#15, #29, #30): skills/run-autopilot/references/phase-review.md

## skills/work/scripts (UNLISTED)

- 6 low-severity review-verb corrections (#12, #13, #14, #17, #20, #24): skills/work/scripts/record_dispatch.py

## . (listed)

- 8 CHANGELOG Unreleased + phase-review.md:280 final carry/coverage prose (#15, #29, #30): CHANGELOG.md

## dev/bin (listed)

- 7 release-checks: list the five review-verb test modules, add self-guard (#32): dev/bin/release-checks

## skills/run-autopilot/cli (listed)

- 1 gate: findings_verdict shared parser, fail-closed on off-shape rows: skills/run-autopilot/cli/gate.py, skills/run-autopilot/cli/test_gate_findings_table.py, skills/run-autopilot/cli/test_gate.py
- 2 review_close: findings_verdict, unreadable-table refusal, unmatched-carry pre-lock check: skills/run-autopilot/cli/review_close.py, skills/run-autopilot/cli/__main__.py, skills/run-autopilot/cli/test_review_close.py, skills/run-autopilot/cli/test_main_review_close_validation.py
- 3 review_close: tail sweep carve-outs (before gate, above medium, not empty, no carry): skills/run-autopilot/cli/review_close.py, skills/run-autopilot/cli/__main__.py, skills/run-autopilot/cli/test_review_close.py
- 4 gate: per-row classification validation shared between gate and review-close: skills/run-autopilot/cli/__main__.py, skills/run-autopilot/cli/test_gate_findings_table.py
- 6 low-severity review-verb corrections (#12, #13, #14, #17, #20, #24): skills/run-autopilot/cli/review_close.py, skills/run-autopilot/cli/gate.py, skills/run-autopilot/cli/__main__.py, skills/run-autopilot/cli/test_review_close.py, skills/run-autopilot/cli/test_gate_findings_table.py
- 9 help text: gate.py and __main__.py docstrings describe the two-way check (#10): skills/run-autopilot/cli/gate.py, skills/run-autopilot/cli/__main__.py
