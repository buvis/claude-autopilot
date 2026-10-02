PRD: /Users/bob/git/src/github.com/buvis/claude-autopilot/dev/local/prds/backlog/00174-align-qwen-routing-with-single-file-trust-v1.md
Base: ad1b20721ec2f5e0b724008fc7a15175a54a8ada
Diff: uncommitted tracked changes plus new files, in cycle-1.diff.
Scope excludes three pre-existing routing-tuner/ledger edits.

Changed files:
CHANGELOG.md
skills/plan-tasks/SKILL.md
skills/plan-tasks/scripts/test_plan_tasks_prose.py
skills/run-autopilot/references/model-ladder.md
skills/run-autopilot/references/state-schema.md
skills/work/SKILL.md
skills/work/references/attempt-logging.md
skills/work/references/gate-failure.md
skills/work/references/qwen-integration.md
skills/work/scripts/test_work_routing.py
skills/work/scripts/work_routing.py
skills/work/scripts/check_qwen_output.py
skills/work/scripts/test_check_qwen_output.py
skills/work/scripts/test_qwen_trust.py
skills/work/scripts/test_qwen_trust_prose.py

Validation: full suite 2540 passed, 32 pre-existing skipped, 459 subtests passed (pytest + rich + pyyaml through uv). Focused new tests were observed failing before implementation. Release checks pending environment-isolated harness run.
