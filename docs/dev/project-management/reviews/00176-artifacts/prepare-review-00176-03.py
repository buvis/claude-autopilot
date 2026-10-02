from pathlib import Path
import re
import subprocess

root = Path('/Users/bob/git/src/github.com/buvis/claude-autopilot')
tmp = root / 'dev/local/tmp'
ref = root / 'skills/review-work-completion/references'
cycle = '00176-03'
prd = (root / 'dev/local/prds/wip/00176-guard-the-target-reads-in-the-doctor-v1.md').read_text()
tasks = (tmp / 'review-tasks-00176-02.md').read_text().replace('Rework covers orphan stat/unlink and helper extraction.', 'Rework covers orphan stat/unlink and helper extraction, guarded symlink status, exclusive temporary creation, and unique target rows.').replace('31fe06b59973374da818a116ec4b3606845049d6 |', '31fe06b59973374da818a116ec4b3606845049d6; 6906a89bff8f0cf8067b61628844561d94553a5f |')
(tmp / f'review-tasks-{cycle}.md').write_text(tasks)
(tmp / f'review-prd-{cycle}.md').write_text(prd)
subprocess.run(['bash', str(root / 'skills/review-work-completion/scripts/gather-context.sh'), '--since', '31fe06b59973374da818a116ec4b3606845049d6', str(tmp / f'review-tasks-{cycle}.md'), str(tmp / f'review-prd-{cycle}.md')], cwd=root, check=True)
changed = subprocess.check_output(['git', 'diff', '--name-only', '31fe06b59973374da818a116ec4b3606845049d6', 'HEAD'], cwd=root, text=True).splitlines()
blocks = []
for script in ['compute_mech_facts.py', 'detect_tautological_tests.py']:
    result = subprocess.check_output(['/Users/bob/.local/share/mise/installs/python/latest/bin/python', str(root / 'skills/review-work-completion/scripts' / script), *changed], cwd=root, text=True)
    blocks.append(result)
    (tmp / f'{script[:-3]}-{cycle}.md').write_text(result)
context = tmp / f'review-context-{cycle}.md'
context.write_text(context.read_text() + '\n' + '\n'.join(blocks) + '\n## Mechanical fail-first replay\nPending parent-run exact incremental replay; supplementary evidence will follow.\n')
output = (ref / 'output-formats.md').read_text().split('## Agent Output Format (Single Source of Truth)\n', 1)[1].split('\n## Per-Rule Verdict Format', 1)[0]
prior = (root / 'dev/local/reviews/00176-guard-the-target-reads-in-the-doctor-v1-review-02.md').read_text().split('## Consolidated findings\n', 1)[1].split('\n## Verification', 1)[0]
values = {'{CONTEXT_FILE}':str(context), '{DIFF_FILE}':str(tmp / f'review-diff-{cycle}.diff'), '{PACK_FILE}':'(no pack available this cycle)', '{PACK_FINDINGS}':'(no pack available this cycle)', '{REVIEW_CHECKLIST}':(ref / 'review-dimensions.md').read_text(), '{RUBRIC}':(ref / 'rubric.md').read_text(), '{OUTPUT_FORMAT}':output}
for agent in ['alice', 'blake', 'bob', 'carl', 'eve']:
    source = (root / 'agents' / f'{agent}.md').read_text()
    front, body = source[4:].split('\n---\n', 1)
    assert re.search(r'^name: '+agent+r'$', front, re.M)
    assert re.search(r'^description: .+', front, re.M)
    if agent == 'eve':
        continue
    if agent == 'blake':
        prompt = body.replace('{PRD}', prd).replace('{RUBRIC}', (root / 'skills/review-blindly/references/rubric.md').read_text()).replace('{OUTPUT_FORMAT}', output)
    else:
        prompt = body
        if agent == 'bob':
            eve = (root / 'agents/eve.md').read_text()
            lenses = eve.split('## Two lenses, applied to every changed file',1)[1].split('## Categorize every residual finding',1)[0]
            rubric = eve.split('## Rubric verdicts (REQUIRED — emit verbatim, one per line)',1)[1]
            prompt += '\n## Two lenses, applied to every changed file' + lenses + '\n## Rubric verdicts (REQUIRED — emit verbatim, one per line)' + rubric
            prompt += '\nUse the BOB issue-line contract for residual findings; prefix each description with FIX, VERIFY, or KNOWN to apply D1-D5 without losing findings in consolidation.\n'
        for key, value in values.items():
            prompt = prompt.replace(key, value)
        prompt += '\n## Incremental review\nThis is an incremental review of the rework done since the previous review cycle — the diff is scoped to changes since then. Two jobs: (1) for each prior finding listed below, verify it is now resolved in the code; (2) review the scoped diff for any regression the rework introduced. You need not re-review unchanged code; the previous cycle already reviewed the full implementation.\n' + prior
        prompt += '\n## Execution constraints\nThis is a review only. Source stays immutable: no edits, commits, or branch changes. Native cleared-context reviewer is the host adapter. Read-only shell calls provide file-read access where a Read tool is absent; Bob remains static-only and must not execute code, tests, or package managers. The coordinator is obtaining exact-HEAD full-suite, release, and replay evidence; do not duplicate full-suite/release runs. No design doc or ledger is available.\n'
    assert not re.search(r'\{(?:CONTEXT_FILE|DIFF_FILE|PACK_FILE|PACK_FINDINGS|REVIEW_CHECKLIST|RUBRIC|OUTPUT_FORMAT|PRD)\}', prompt)
    (tmp / f'{agent}-prompt-{cycle}.md').write_text(prompt)
print('Prepared staged context, diff, mechanical facts, shape scan, and validated registry prompts.')
