Cycle-1 consolidated findings and repairs (PRD 00174):
1. HIGH, all three: Git index flags hide mutated Tess tests. Direct disk hash/type/mode vs committed tree now checks working content independently of index shortcuts. Separate index comparison retained. Flags before/during dispatch and scoped restoration covered by tests.
2. HIGH, Alice/Blake: failed or killed Qwen bypasses test integrity guard. after --tests-only required before every fallback and watchdog verification, preserving original failure classification when tests unchanged.
3. MEDIUM, all three: dispatch self-check contradicts effective file exclusion. Self-check now consumes effective decision and includes prep/test-only/write-set exclusions and direct capability escalations.
4. MEDIUM, Alice: active split example advertises two-file Qwen. Rewritten to independent one-file gates and inseparable two-file export/interface slices above Qwen.
5. MEDIUM, Blake: repo ancestors named tests disable Qwen. Routing consumes explicit task.is_test_only derived from repo-relative classification at caller; guard also validates its own normalized paths.
6. MEDIUM/LOW, Bob/Blake: duplicate schema descriptions conflict. Parent signature updated, repeated exclusion explanation replaced with pointer, output-guard breaker meaning synchronized.
7. MEDIUM, Bob: report drops runtime files. Added dispatch files bucket deduplicated per task; plan and runtime populations remain distinct.
Every executable repair had a failing regression observed before its fix. Cycle-1 rejected solution is preserved in cycle-1.diff and all three reports.
Known validation boundary: no live Qwen/model dispatch or autopilot loop (user bypasses loop under construction). Real Git fixtures exercise guard CLI; routing policy is partly model-followed prose as in the repository architecture.
