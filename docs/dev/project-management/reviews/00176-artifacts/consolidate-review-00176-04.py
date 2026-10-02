from pathlib import Path
import json
import re
import subprocess

root = Path('/Users/bob/git/src/github.com/buvis/claude-autopilot')
tmp = root / 'dev/local/tmp'
cycle = '00176-04'
python = '/Users/bob/.local/share/mise/installs/python/latest/bin/python'
ref = root / 'skills/review-work-completion/references'
expected_r = re.findall(r'^R\d+(?=:)', (ref / 'rubric.md').read_text(), re.M)
expected_b = re.findall(r'^B\d+(?=:)', (root / 'skills/review-blindly/references/rubric.md').read_text(), re.M)
expected_d = re.findall(r'^D\d+(?=:)', (root / 'skills/run-autopilot/references/doubt-review-rubric.md').read_text(), re.M)
for name, expected in [('alice', expected_r), ('blake', expected_b), ('bob', expected_r + expected_d)]:
    content = (tmp / f'{name}-output-{cycle}.txt').read_text()
    verdicts = re.findall(r'^([RBD]\d+): (pass|fail)$', content, re.M)
    assert sorted(rule for rule, _ in verdicts) == sorted(expected), (name, verdicts, expected)
    issue_lines = [line for line in content.splitlines() if line.startswith('[')]
    assert issue_lines
    for line in issue_lines:
        assert line == f'[{name.upper()}] ✅ No issues found' or re.fullmatch(r'\[' + name.upper() + r'\] [🔴🟠🟡⚪] .+ \| File: .+ \| Task: .+', line), line
    print(f'{name}: complete output format and {len(expected)} current rubric verdicts verified')
ledger_path = root / 'dev/local/reviews/00176-guard-the-target-reads-in-the-doctor-v1-ledger.json'
ledger = json.loads(ledger_path.read_text())
issue = '1 touched test(s) pass against the pre-change code: test_target_deleted_after_stat_is_verdicted'
assert not any(entry.get('cycle') == 4 for entry in ledger)
ledger.append({
    'cycle': 4,
    'disposition': 'discarded',
    'severity': 'Medium',
    'issue': issue,
    'file': 'skills/use-codex/scripts/test_codex_hook_doctor_parse_errors.py',
    'reason': 'The pre-existing disappearance regression moved its fault injection from exists/stat to stat/read because this rework removes exists(). It preserves the same disappearance and error-detail behavior. Passing the incremental base is expected for this behavior-preserving test maintenance; the genuinely new permission-suppression regression fails there. Alice and Bob independently verified this rationale, and the parent decision gate explicitly accepted the dismissal. Raw mechanical evidence remains in review-04.'
})
ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + '\n')
result = subprocess.run([python, str(root / 'skills/review-work-completion/scripts/consolidate_findings.py'), *[name.upper() + ':' + str(tmp / f'{name}-output-{cycle}.txt') for name in ('alice', 'blake', 'bob')], '--ledger', str(ledger_path), '--ledger-dismiss', 'BLAKE'], cwd=root, capture_output=True, text=True)
assert result.returncode == 0, result.stderr
(tmp / f'review-consolidated-{cycle}.md').write_text(result.stdout)
print(result.stdout)
assert 'Auto-dismissed' not in result.stdout
