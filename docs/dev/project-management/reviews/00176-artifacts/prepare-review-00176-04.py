from pathlib import Path
import json
import re
import subprocess

root = Path('/Users/bob/git/src/github.com/buvis/claude-autopilot')
tmp = root / 'dev/local/tmp'
ref = root / 'skills/review-work-completion/references'
cycle = '00176-04'
base = '4f9ca6405081eea7b869883c6b53d301e53f6080'
head = 'fdee7b9b3d147ff12e475cd1dceeb9d4bab86f63'
python = '/Users/bob/.local/share/mise/installs/python/latest/bin/python'
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip() == head
assert not (root / 'dev/local/autopilot/state.json').exists()
personas = {}
for agent in ['alice', 'blake', 'bob', 'carl', 'eve']:
    source = (root / 'agents' / f'{agent}.md').read_text()
    assert source.startswith('---\n')
    front, body = source[4:].split('\n---\n', 1)
    fields = {}
    for line in front.splitlines():
        key, value = line.split(':', 1)
        assert key not in fields and value.strip()
        fields[key] = value.strip()
    assert fields['name'] == agent
    assert 0 < len(fields['description']) <= 120
    assert fields['tools'] and not re.search(r'\b(Edit|Write)\b', fields['tools'])
    assert body.strip()
    personas[agent] = body
prd_path = root / 'dev/local/prds/wip/00176-guard-the-target-reads-in-the-doctor-v1.md'
prd = prd_path.read_text()
tasks = '''# Review task context

Standalone review: no canonical task store or autopilot state exists. Both PRD task checkboxes are complete.

| Task | Description | Commit |
|---|---|---|
| 1 | Guard target reads and stat; directory/read/race regressions. Folded with task 2 in the original commit. Cycle 4 replaces the suppressing existence probe with guarded stat and preserves race coverage at stat/read. | ece9ac34053a17e9629e9af50355e7c84dc32fe2; fdee7b9b3d147ff12e475cd1dceeb9d4bab86f63 |
| 2 | Guard repair write/replace/cleanup; error detail and read-only regressions; changelog. Folded with task 1 in the original commit. Prior rework covers orphan stat/unlink and helper extraction, guarded symlink status, exclusive temporary creation, and unique target rows. | ece9ac34053a17e9629e9af50355e7c84dc32fe2; 31fe06b59973374da818a116ec4b3606845049d6; 6906a89bff8f0cf8067b61628844561d94553a5f |
'''
(tmp / f'review-tasks-{cycle}.md').write_text(tasks)
(tmp / f'review-prd-{cycle}.md').write_text(prd)
subprocess.run(['bash', str(root / 'skills/review-work-completion/scripts/gather-context.sh'), '--since', base, str(tmp / f'review-tasks-{cycle}.md'), str(tmp / f'review-prd-{cycle}.md')], cwd=root, check=True)
changed = subprocess.check_output(['git', 'diff', '--name-only', base, 'HEAD'], cwd=root, text=True).splitlines()
blocks = []
for script in ['compute_mech_facts.py', 'detect_tautological_tests.py']:
    result = subprocess.check_output([python, str(root / 'skills/review-work-completion/scripts' / script), *changed], cwd=root, text=True)
    blocks.append(result)
    (tmp / f'{script[:-3]}-{cycle}.md').write_text(result)
blocks.append((tmp / f'replay-output-{cycle}.md').read_text())
record_path = root / 'dev/local/autopilot/last-verification.json'
record_text = record_path.read_text()
record = json.loads(record_text)
assert record['sha'] == head and record['commands']
assert all(record[key] is not None for key in ('passed', 'failed', 'skipped'))
(tmp / f'review-verification-record-{cycle}.json').write_text(record_text)
context = tmp / f'review-context-{cycle}.md'
context.write_text(context.read_text() + '\n' + '\n'.join(blocks) + '\n## Exact-HEAD recorded verification\n```json\n' + record_text + '\n```\nThe parent ran these checks with source HEAD unchanged; do not duplicate suite, release, doctor-version suites, or worktree replay.\n\n## Architecture context\n' + (root / 'dev/local/meta/project-capsule.md').read_text() + '\nNo repository AGENTS.md, CLAUDE.md, agent_docs directory, or matching PRD design document is present. The PRD is the requirements authority.\n')
subprocess.run(['git', 'rev-parse', '--show-toplevel'], cwd=root, check=True)
pack = subprocess.run(['engram', 'pack', '--cycle', cycle, '--prd', str(prd_path), '--capsule', 'dev/local/meta/project-capsule.md'], cwd=root, capture_output=True, text=True)
(tmp / f'review-pack-{cycle}.txt').write_text(f'exit: {pack.returncode}\n{pack.stdout}{pack.stderr}')
assert pack.returncode != 0, 'Inspect unexpectedly available context pack before assembling prompts'
output = (ref / 'output-formats.md').read_text().split('## Agent Output Format (Single Source of Truth)\n', 1)[1].split('\n## Per-Rule Verdict Format', 1)[0]
prior_text = (root / 'dev/local/reviews/00176-guard-the-target-reads-in-the-doctor-v1-review-03.md').read_text()
prior = prior_text.split('## Consolidated findings\n', 1)[1].split('\n## Verification', 1)[0]
ledger_path = root / 'dev/local/reviews/00176-guard-the-target-reads-in-the-doctor-v1-ledger.json'
ledger = json.loads(ledger_path.read_text())
settled = '\n## Settled decisions — do not re-raise\nThese calls were already made in an earlier cycle of this same review, with the reasons given. Do not re-raise them. Raise a NEW finding only if you can show the settled reason no longer holds.\n'
for entry in ledger:
    settled += '- ' + ' | '.join(f'{key}: {entry[key]}' for key in ('disposition', 'severity', 'issue', 'file', 'reason')) + '\n'
values = {'{CONTEXT_FILE}':str(context), '{DIFF_FILE}':str(tmp / f'review-diff-{cycle}.diff'), '{PACK_FILE}':'(no pack available this cycle)', '{PACK_FINDINGS}':'(no pack available this cycle)', '{REVIEW_CHECKLIST}':(ref / 'review-dimensions.md').read_text(), '{RUBRIC}':(ref / 'rubric.md').read_text(), '{OUTPUT_FORMAT}':output}
for agent in ['alice', 'blake', 'bob', 'carl']:
    prompt = personas[agent]
    if agent == 'blake':
        prompt = prompt.replace('{PRD}', prd).replace('{RUBRIC}', (root / 'skills/review-blindly/references/rubric.md').read_text()).replace('{OUTPUT_FORMAT}', output)
    else:
        if agent == 'bob':
            lenses = personas['eve'].split('## Two lenses, applied to every changed file', 1)[1].split('## Categorize every residual finding', 1)[0]
            rubric = personas['eve'].split('## Rubric verdicts (REQUIRED — emit verbatim, one per line)', 1)[1]
            prompt += '\n## Two lenses, applied to every changed file' + lenses + '\n## Rubric verdicts (REQUIRED — emit verbatim, one per line)' + rubric
            prompt += '\n## Doubt rubric full text\n' + (root / 'skills/run-autopilot/references/doubt-review-rubric.md').read_text()
            prompt += '\nApply D1–D5 using the mandatory BOB issue-line format. Prefix every residual issue description with FIX, VERIFY, or KNOWN. FIX is bounded/in-scope/actionable; VERIFY names an exact runnable check; KNOWN includes a written out-of-scope reason. Do not omit issue lines in favor of buckets. Emit the complete current R and D verdict sets.\n'
        for key, value in values.items():
            prompt = prompt.replace(key, value)
        prompt += '\n## Incremental review\nThis is an incremental review of the rework done since the previous review cycle — the diff is scoped to changes since then. Two jobs: (1) for each prior finding listed below, verify it is now resolved in the code; (2) review the scoped diff for any regression the rework introduced. You need not re-review unchanged code; the previous cycle already reviewed the full implementation.\n' + prior
        prompt += settled
        prompt += '\n## Current replay disposition\nThe parent decision gate dismisses the raw computed baseline-pass observation for test_target_deleted_after_stat_is_verdicted because the existing disappearance test was adapted from exists/stat injection to stat/read when exists was removed. The behavior is intentionally unchanged. Keep the observation visible; check independently whether that reason holds. The genuinely new exists-suppression regression failed against the incremental base.\n'
        prompt += '\n## Host execution constraints\nReview only: no edits, commits, branch changes, or state.json creation. No model diversity is claimed for native cleared-context adapters. Read-only file retrieval via cat/rg/sed is the host equivalent of Read; Bob must remain static-only with no code, tests, linters, or package managers executed. Full-suite/release/doctor-version suites and mechanical worktree replay were already run at the captured HEAD; do not duplicate them. If a needed command is blocked, report the exact command to the coordinator instead of requesting child escalation. Return reviewer text in your final response; do not write reviewer output files.\n'
        if agent == 'bob':
            prompt += '\n## Inlined context\n' + context.read_text() + '\n## Inlined diff\n```diff\n' + (tmp / f'review-diff-{cycle}.diff').read_text() + '\n```\n'
            for path in changed:
                if path.endswith('.py'):
                    prompt += '\n## Source snapshot: ' + path + '\n```python\n' + (root / path).read_text() + '\n```\n'
    assert not re.search(r'\{(?:CONTEXT_FILE|DIFF_FILE|PACK_FILE|PACK_FINDINGS|REVIEW_CHECKLIST|RUBRIC|OUTPUT_FORMAT|PRD)\}', prompt)
    (tmp / f'{agent}-prompt-{cycle}.md').write_text(prompt)
print('All roster frontmatter validated; context, mechanical checks, exact-HEAD verification and independently assembled prompts saved.')
