import json
import re
import subprocess
from pathlib import Path

root = Path('/Users/bob/git/src/github.com/buvis/claude-autopilot')
tmp = root / 'dev/local/tmp'
reviews = root / 'dev/local/reviews'
stem = '00176-guard-the-target-reads-in-the-doctor-v1'
sha = '4f9ca6405081eea7b869883c6b53d301e53f6080'
outputs = {agent: (tmp / f'{agent}-output-00176-03.txt').read_text() for agent in ('alice', 'blake', 'bob')}
expected = {'alice': [f'R{i}' for i in (1, 2, 3, 4, 6, 7, 8, 9, 10, 11, 12, 13)], 'blake': [f'B{i}' for i in range(1, 20)]}
expected['bob'] = expected['alice'] + [f'D{i}' for i in range(1, 6)]
for agent, body in outputs.items():
    for rule in expected[agent]:
        assert re.search(r'^' + rule + r': (pass|fail)$', body, re.M), (agent, rule)
    for line in body.splitlines():
        if line.startswith('[' + agent.upper() + ']'):
            assert re.match(r'^\[' + agent.upper() + r'\] [🔴🟠🟡⚪] .+ \| File: .+ \| Task: .+$', line), (agent, line)
record = json.loads((root / 'dev/local/autopilot/last-verification.json').read_text())
assert record['sha'] == sha and record['commands']
assert all(record[k] is not None for k in ('passed', 'failed', 'skipped'))
(tmp / 'review-verification-record-00176-03.json').write_text(json.dumps(record, indent=2) + '\n')
consolidated = subprocess.check_output(['/Users/bob/.local/share/mise/installs/python/latest/bin/python', str(root / 'skills/review-work-completion/scripts/consolidate_findings.py'), *[a.upper() + ':' + str(tmp / f'{a}-output-00176-03.txt') for a in outputs]], cwd=root, text=True)
(tmp / 'review-consolidated-00176-03.md').write_text(consolidated)
replay = (tmp / 'replay-output-00176-03.md').read_text()
mech = next(line for line in replay.splitlines() if line.startswith('[MECH]'))
reason = ('Partial-write and failed-replace behavior is intentionally unchanged. The existing regression test moved its I/O injection from Path.write_bytes to Path.open/stream.write because exclusive creation must retain one handle. Both cases retain the original error-path assertions; all five actual new behavior cases fail against the incremental base. Passing the rework base is expected behavior-preserving regression maintenance, not unpinned new behavior. Parent decision gate accepted this dismissal.')
issues = [line.split('] ', 1)[1].split(' | File:', 1)[0][2:] for agent in ('alice', 'bob') for line in outputs[agent].splitlines() if 'partial-write/replace' in line]
issues.append(mech.split('] ', 1)[1].split(' | File:', 1)[0][2:])
ledger_path = reviews / f'{stem}-ledger.json'
ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else []
for issue in issues:
    entry = {'cycle': 3, 'disposition': 'discarded', 'severity': 'Medium', 'issue': issue, 'file': 'skills/use-codex/scripts/test_codex_hook_doctor_parse_errors.py', 'reason': reason}
    if entry not in ledger:
        ledger.append(entry)
ledger_path.write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + '\n')
report = '''---
prd: dev/local/prds/wip/00176-guard-the-target-reads-in-the-doctor-v1.md
review: 3
date: 2026-09-05
head_sha: 4f9ca6405081eea7b869883c6b53d301e53f6080
reviewers: alice,blake,bob
agents:
  alice: available
  blake: available
  bob: available
  carl: unavailable
  eve: disabled
---

# Review: 00176-guard-the-target-reads-in-the-doctor-v1

Diff range: `31fe06b59973374da818a116ec4b3606845049d6..4f9ca6405081eea7b869883c6b53d301e53f6080`

codex_rung_guard: not fired

One actionable Medium finding remains: Python 3.14 suppresses a target permission error inside `Path.exists()`, returning `missing` without the required error detail. All three cycle-2 findings are resolved. Four raw consolidated rows are preserved below: the source finding, two descriptions of the same mechanical replay observation (discarded with evidence), and a runtime verification note (resolved by the matching exact-HEAD record).

This is a standalone incremental review of the explicitly supplied PRD. No canonical task store or autopilot state exists or was created. The two completed PRD task rows remain separate in `dev/local/tmp/review-tasks-00176-03.md`, including shared and rework commit provenance. Original PRD base is `9336ab507525e13a685957a41b338561e74032fd`. There is no repository AGENTS.md/CLAUDE.md, matching design document, or pre-existing settled-decisions ledger. Consensus resolves to legacy; doubt reviewer resolves to codex. Eve is not opted in. The state-based Codex implementor guard cannot fire on this standalone path.

An external release-stamp revert changed HEAD from the handoff's `6906a89` to the captured `4f9ca64` during setup. The incremental net diff was gathered after that change, before Alice and Bob dispatch, and contains only CHANGELOG.md, the doctor, and its parse-error tests. The parent reran verification with the captured SHA checked before and after the suite. The source review ended before the parent began task-1 rework; later uncommitted test edits are not part of this snapshot.

## Prior findings

Alice and Bob independently verified each prior finding:

- `_repair_known` guards `is_symlink()` metadata errors and returns an `unrepairable` row while later targets continue.
- `_write_repair` reserves the predictable temporary path with exclusive `xb` creation, retains the open handle, and cleans up only after creation succeeded. Pre-existing regular files and symlinks survive. Partial-write, replace, and cleanup errors retain the existing reporting behavior.
- Orphan cleanup excludes both registered targets and targets already emitted by repair, preventing duplicate rows for a dangling orphan while still processing later empty orphans.

The changed functions remain below 50 lines and the changed Python files are 475 and 459 lines, below 800.

## Execution and limitations

Every roster prompt was assembled independently from validated current registry frontmatter and body. Alice and Blake ran in fresh native subagents with `fork_turns=none`; Bob followed in another fresh subagent when Alice released a slot. Parent plus review coordinator consume two of this host's four slots. Native Codex subagents are the available host adapter for the documented Claude Task reviewers and Bob fallback. Contexts are isolated, but there is no model diversity and the documented Claude model pins cannot be fulfilled by this host.

Blake received only persona, verbatim PRD, blind rubric B1–B19, and output contract, with no implementation context, history, findings, diff, pack, or design. Alice received the complete current R rubric, checklist, scoped diff, mechanical facts, and previous findings. Bob received the same inputs plus the current doubt/de-slop appendix and D1–D5 rubric; his review was static-only. All issue lines and all current R/B/D verdict lines passed format validation without a retry.

Bob later read the coordinator's verification artifact and explicitly reported the permission-error issue as supplied evidence. He is a confirming reviewer, not a second independent discoverer of that issue; the script's [2/3] row counts two reporting reviewers, while independent discovery is Blake's and the coordinator separately reproduced it. This exposure occurred after Bob independently confirmed the prior fixes.

Real Bob and Carl wrapper dispatches each returned exit 3, `refusing nested dispatch (already inside a CLI agent)`, on initial attempt and one retry: `[RETRY] Bob attempt 1/1`, `[RETRY] Carl attempt 1/1`. No live backend launched and no guard was bypassed. Bob's required doubt lens completed in the fresh fallback. Carl is unavailable this cycle, not permanently unavailable, and has no output to consolidate. No stale CLI result or thread ID was reused.

Pack: unavailable. Engram exited 1 because this checkout is not registered. Implementation-aware prompts used `(no pack available this cycle)`; no external configuration changed. Mechanical replay was appended verbatim when the parent supplied it. The lack of a filesystem Write tool was handled through structured apply_patch for textual artifacts and a standard-library assembly script; no shell interpolation of prompt contents was used.

## Consolidated findings

`consolidate_findings.py` exited 0. Its four raw rows are preserved verbatim. The script did not merge the two differing descriptions of the same replay observation; the decision records below group them explicitly. There was no ledger to filter at dispatch or initial consolidation. No finding contradicts the computed mechanical facts.

{CONSOLIDATED}

The `[MECH]` line names the same test as both replay rows; `mech-check` is added as a finder to both of those rows for the final finding record. It creates no fifth finding. The raw computed evidence is retained verbatim:

{MECH}

## Decisions and actionable follow-up

1. **Accepted, Medium, task 1:** Replace the suppressing existence probe with guarded stat classification. Preserve `missing` for a nonexistent target and return `syntax_error` plus the OSError text for permission failures. Add a real parent-directory permission regression that fails at this reviewed HEAD and checks later rows continue. Root owns this source fix.
2. **Discarded, both replay rows plus mech-check:** {REASON} The three verbatim issue texts and reason are recorded in `dev/local/reviews/{STEM}-ledger.json`. Alice's and Bob's raw R2 failures remain visible; this disposition does not rewrite reviewer verdicts.
3. **Resolved, Bob runtime VERIFY:** The matching recorded suite and release commands both exited 0 at the reviewed HEAD. Counts and command provenance appear below. No standalone verification queue or tasks were created.

The formal `Verdict:` counts the four raw consolidated rows; the decision gate leaves exactly one source issue requiring rework. Findings are reported rather than written as tasks because this is standalone.

## Verification

- Full suite: **2615 passed, 0 failed, 1 skipped**, plus **459 subtests passed** and 4 existing warnings. Reused from `last-verification.json` at the captured HEAD; parent checked HEAD before and after the mandatory foreground run. The immutable copy is `dev/local/tmp/review-verification-record-00176-03.json`.
- Release checks: **224 passed**, exit 0, recorded at the same HEAD. Only the hermetic stub-test invocation removed inherited runner markers; the real reviewer attempts retained their recursion guards.
- Doctor scripts: **90 passed**, independently run by Blake. He also independently ran release checks successfully after correcting the inherited guard variables in the stub-test environment.
- Mechanical replay: **7 touched cases ran, 5 failed against the incremental base, 2 passed, zero collection failures**. The five new behavior cases fail as intended; the two passing existing error-path cases are explicitly dispositioned above. Full raw output: `dev/local/tmp/replay-output-00176-03.md`.
- Tautology shape scan: **12 test functions checked, no findings**. AST function counts and changed-file sizes meet the rubric. `git diff --check 31fe06b59973374da818a116ec4b3606845049d6 HEAD` passed against the captured source.

The one skip and four warnings are the same existing baseline skip and legacy schema warnings observed in prior cycles. Verification was not inferred from a stale SHA; the old cycle-2 record was ignored until the matching record arrived. No duplicate coordinator full-suite, release, or worktree replay was run.

Blake's CLI reproduction on Python 3.14.6 creates a registered readable target inside a directory and a later readable target, then changes the first parent to mode 000. Its direct stat raises PermissionError (errno 13); check emits `missing` with empty detail, later `ok`, and summary `1 ok, 0 stale, 1 broken`, exit 1. The coordinator independently reproduced the underlying result with real filesystem permissions:

```text
target.exists: False
target.stat: PermissionError 13
verdict: ('missing', '')
```

Both reproductions restore directory permissions in `finally`. Coordinator script and dispatch evidence are in `dev/local/tmp/reproduce-exists-permission-00176-03.py` and `dev/local/tmp/review-verification-00176-03.md`.

## Alice

{ALICE}

## Blake

{BLAKE}

## Bob

{BOB}

## Handoff

The coordinator made no tracked source edits, commits, branch changes, state.json, or verification queue. Root owns the accepted source fix and cycle 4 must run in another fresh review session with fresh reviewer contexts. Review evidence remains under dev/local; the cycle contract card records the transition.

Verdict: 4 findings
Tests: 2615 passed, 0 failed, 1 skipped (reused from last-verification.json at 4f9ca6405081eea7b869883c6b53d301e53f6080; 459 additional subtests passed)
'''
for key, value in {'CONSOLIDATED': consolidated.strip(), 'MECH': mech, 'REASON': reason, 'STEM': stem, **{agent.upper(): body.strip() for agent, body in outputs.items()}}.items():
    report = report.replace('{' + key + '}', value)
(reviews / f'{stem}-review-03.md').write_text(report)
(root / 'dev/local/autopilot/contract-card.md').write_text('''# Contract card

Current step: standalone PRD 00176 cycle-3 review completed at 4f9ca6405081eea7b869883c6b53d301e53f6080; four raw findings, one actionable source finding after recorded decisions.

Active invariants: no autopilot execution/state fabrication while modifying autopilot; each review session and reviewer context is fresh; all consensus, blind, and doubt/de-slop lenses run every cycle; source review snapshots remain immutable; preserve verdict strings and per-target continuation.

Next gate: root fixes the accepted Python 3.14 permission-error classification, verifies fail-first coverage and exact-HEAD suite/release, then hands off cycle 4 to another fresh review coordinator. Two replay observation rows were discarded with evidence in the settled-decisions ledger; Bob's runtime note is resolved by the matching verification record.
''')
print('Saved outputs, validated all current R/B/D verdicts, preserved raw consolidation, recorded dismissals, and wrote review plus contract card.')
