---
head_sha: c7b8d5efc884c2e3546b7b0f0ded6acd16e66dd9
reviewers: alice,blake,eve
---

# Review: 00284-loop-launch-context-v1

Diff range: `b3ad8cf12c373a775d694530878d4a7c1e7eec96..c7b8d5efc884c2e3546b7b0f0ded6acd16e66dd9`

codex_rung_guard: not fired

## Alice

**00284-loop-launch-context-v1-c1**
[ALICE] ✅ No issues found. R1-R13 all pass.

## Blake

**00284-loop-launch-context-v1-c1**
[BLAKE] 🔴 `write_brief` never passed `project_root` to `render_brief`, so the repo-root fallback the PRD/CHANGELOG claimed as fixed never reached production. Confirmed by Victor's adversarial verify; fixed in the rework (commit 2991b0b) and confirmed resolved by Eve's delta review.
[BLAKE] 🟡 CHANGELOG's Fixed entry for the repo-root fallback was false given the above; it became true once the fix landed.
[BLAKE] ✅ MCP-scoping, collected-message validator, and the live MCP test all matched spec exactly.

## Eve

**00284-loop-launch-context-v1-c1**
FIX (roster round, both resolved by the rework):
- write_brief dead-code gap (same as Blake's finding above).
- Wrong discovery-finding citations (F13 instead of F9 for the repo-root fallback; stray F9 on the MCP-scoping citations) — fixed in commit 2991b0b.

FIX (delta round, both resolved directly in commit c7b8d5e):
- The rework's new regression test's name didn't match the card gate's `-k "repo_root"` filter, so the gate would never run it — renamed.
- The test's fixture pinned only the shallow branch of `custody.project_root`, not the real production depth — rebuilt at the correct path.

VERIFY: run the full `bash dev/bin/release-checks` gate — done, twice (after the rework and after the delta fix-up), both exit 0.

KNOWN (accepted, out of scope): reviewer-subprocess MCP connectors still boot unscoped; a garbage `_AUTOPILOT_MCP_CONFIG` value fails the launch verbatim as the PRD mandates; `~/.claude/settings.json`'s stale `mcp__claude_ai_Context7__*` allowlist entry is non-blocking under `--permission-mode auto`; a relative `--state` path to `write-brief` renders `repo root: .` (production always passes an absolute path).

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

Verdict: converged

Tests: 6545 passed, 0 failed, 34 skipped (fast-track batch suite, `bash dev/bin/release-checks`)
