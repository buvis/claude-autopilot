# Split note: 00256-finish-the-review-verbs-before-release-v1.md
planned=7 prd_tasks=7 expansion=1.00 reasons=module_drift

## docs/dev/project-management/prds/hold (UNLISTED)

- 7 triage: delete the superseded hold stub for the diff-base resolver finding: docs/dev/project-management/prds/hold/00255-triage-resolve-base-is-a-second-diff-base-resol-v1.md

## skills/review-work-completion (UNLISTED)

- 6 skill prose sync: ledger flags, all five lenses, dispatch_rows format, word severity: skills/review-work-completion/SKILL.md

## skills/review-work-completion/references (UNLISTED)

- 6 skill prose sync: ledger flags, all five lenses, dispatch_rows format, word severity: skills/review-work-completion/references/output-formats.md

## dev/bin (listed)

- 2 verification + release-checks: real counts, bounded streaming run_gate, rename-safe reuse_verdict: dev/bin/release-checks

## skills/run-autopilot/cli (listed)

- 1 triage: emoji severities qualify as critical/high: skills/run-autopilot/cli/triage.py
- 2 verification + release-checks: real counts, bounded streaming run_gate, rename-safe reuse_verdict: skills/run-autopilot/cli/verification.py
- 3 review_close: error outcome for unavailable reviewers, close every lens: skills/run-autopilot/cli/review_close.py, skills/run-autopilot/cli/test_review_close.py
- 4 review_stage: Eve PRD-only, Bob appendix unconditional, one diff-base resolver: skills/run-autopilot/cli/review_stage.py, skills/run-autopilot/cli/test_review_stage.py
- 5 gate: findings JSON cross-check, wired into review-close's state mutation: skills/run-autopilot/cli/gate.py, skills/run-autopilot/cli/review_close.py, skills/run-autopilot/cli/__main__.py, skills/run-autopilot/cli/test_gate.py, skills/run-autopilot/cli/test_review_close.py

## skills/run-autopilot/references (listed)

- 6 skill prose sync: ledger flags, all five lenses, dispatch_rows format, word severity: skills/run-autopilot/references/phase-review.md
