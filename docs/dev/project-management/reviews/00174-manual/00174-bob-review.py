import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile

REPO = Path('/Users/bob/git/src/github.com/buvis/claude-autopilot')
SCRIPT = REPO / 'skills/work/scripts/check_qwen_output.py'

def git(root, *args):
    return subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True, text=True).stdout.strip()

def setup(label, flags=None, bare=False):
    root = Path(tempfile.mkdtemp(prefix=f'00174-bob-{label}-')).resolve()
    git(root, 'init', '-q')
    git(root, 'config', 'user.email', 'review@example.invalid')
    git(root, 'config', 'user.name', 'Review')
    git(root, 'config', 'core.hooksPath', '/dev/null')
    for name, body in [('impl.py', 'answer = 0\n'), ('test_impl.py', 'assert answer == 42\n'), ('foreign.txt', 'original\n')]:
        (root / name).write_text(body)
    git(root, 'add', '.')
    git(root, 'commit', '-qm', 'baseline')
    if flags:
        git(root, 'update-index', flags, 'test_impl.py')
    files = root / '.git/files.txt'
    tests = root / '.git/tests.txt'
    files.write_text(str(root / 'impl.py') + '\n')
    tests.write_text(str(root / 'test_impl.py') + '\n')
    snapshot = root / '.git/qwen.json'
    result = subprocess.run([sys.executable, str(SCRIPT), 'before', '--snapshot', str(snapshot), '--repo-root', str(root), '--test-commit', git(root, 'rev-parse', 'HEAD'), '--files-file', str(files), '--tests-file', str(tests)], capture_output=True, text=True)
    assert result.returncode == 0, (result.stdout, result.stderr)
    return root, snapshot

def after(root, snapshot, restore=False):
    result = subprocess.run([sys.executable, str(SCRIPT), 'after', '--snapshot', str(snapshot), *(['--restore-tests'] if restore else [])], capture_output=True, text=True)
    return {'exit': result.returncode, 'stdout': result.stdout.strip(), 'stderr': result.stderr.strip(), 'test': (root / 'test_impl.py').read_text(), 'staged': git(root, 'diff', '--cached', '--name-only')}

for flag in ('--assume-unchanged', '--skip-worktree'):
    root, snapshot = setup(flag.strip('-'), flag)
    (root / 'impl.py').write_text('answer = 42\n')
    (root / 'test_impl.py').write_text('assert True\n')
    result = after(root, snapshot)
    assert result['exit'] == 0 and result['test'] == 'assert True\n', result
    print(json.dumps({'case': flag, 'root': str(root), 'result': result}))

root, snapshot = setup('foreign-staged-restoration')
(root / 'impl.py').write_text('answer = 42\n')
(root / 'test_impl.py').write_text('assert True\n')
(root / 'foreign.txt').write_text('user staged\n')
git(root, 'add', 'foreign.txt')
result = after(root, snapshot, restore=True)
assert result['exit'] == 1 and result['test'] == 'assert answer == 42\n' and result['staged'] == 'foreign.txt', result
assert (root / 'foreign.txt').read_text() == 'user staged\n'
print(json.dumps({'case': 'foreign-staged-restoration', 'root': str(root), 'result': result}))

spec = importlib.util.spec_from_file_location('work_routing', REPO / 'skills/work/scripts/work_routing.py')
routing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(routing)
task = {'model': 'sonnet', 'qwen_eligible': True}
verdict = routing.route(task, {'_WORK_CODEX_RUNG': 'off'}, {}, {}, file_paths='a.py\nb.py')
assert verdict == {'implementor': 'claude', 'tier': 'sonnet', 'rule': 'row7', 'qwen_excluded_reason': 'files'}
assert task['qwen_eligible'] is True
prose = (REPO / 'skills/work/SKILL.md').read_text()
assert 'if `state.tasks[i].qwen_eligible == true` and you are about to dispatch Claude' in prose
assert 'if it would read `null` or `"healthy"`, you skipped the table; run it now' in prose
print(json.dumps({'case': 'runtime-self-check-conflict', 'persisted_task': task, 'route': verdict, 'required_preflight': None, 'self_check_rejects': True}))

text = (REPO / 'dev/local/reviews/00174-manual/cycle-1.diff').read_text()
added = sum(line.startswith('+') and not line.startswith('+++') for line in text.splitlines())
removed = sum(line.startswith('-') and not line.startswith('---') for line in text.splitlines())
prd = (REPO / 'dev/local/prds/backlog/00174-align-qwen-routing-with-single-file-trust-v1.md').read_text()
import re
acceptance = re.findall(r'Acceptance:(.*?)(?=\n- \[ \]|\n\*\*Exit Criteria)', prd, re.S)
words = sum(len(value.split()) for value in acceptance)
print(json.dumps({'case': 'bloat-ratio', 'added_lines': added, 'removed_lines': removed, 'net_lines': added-removed, 'acceptance_words': words, 'ratio': round((added-removed)/words, 2)}))
