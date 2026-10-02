from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path('/Users/bob/git/src/github.com/buvis/claude-autopilot')
head = 'fdee7b9b3d147ff12e475cd1dceeb9d4bab86f63'
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip() == head
assert sys.version_info[:2] == (3, 14)
assert os.geteuid() != 0
source = root / 'skills/use-codex/scripts/codex_hook_doctor.py'
spec = importlib.util.spec_from_file_location('doctor', source)
doctor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(doctor)
print('Python:', sys.version.split()[0])
print('HEAD:', head)
with tempfile.TemporaryDirectory(prefix='review-parent-permission-00176-04-', dir=root / 'dev/local/tmp') as directory:
    fixture = Path(directory)
    hooks = fixture / 'hooks'
    denied = hooks / 'denied'
    denied.mkdir(parents=True)
    target = denied / 'protect_config.py'
    later = hooks / 'validate_commit_msg.py'
    canonical = fixture / 'aegis' / 'hooks'
    canonical.mkdir(parents=True)
    for path in (target, later, canonical / target.name, canonical / later.name):
        path.write_text('X = 1\n')
    config = fixture / 'hooks.json'
    config.write_text(json.dumps({'hooks': {'PreToolUse': [{'hooks': [
        {'type': 'command', 'command': f'python3 {target}'},
        {'type': 'command', 'command': f'python3 {later}'},
    ]}]}}))
    denied.chmod(0)
    try:
        print('target.exists():', target.exists())
        try:
            target.stat()
        except OSError as exc:
            print('target.stat():', type(exc).__name__, exc.errno)
        else:
            raise AssertionError('chmod parent fixture failed to deny stat')
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = doctor.main(['check', '--config', str(config), '--aegis-root', str(canonical.parent), '--autopilot-root', str(fixture)])
        rows = [line.split('\t') for line in out.getvalue().splitlines()]
        assert code == 1, (code, out.getvalue(), err.getvalue())
        assert len(rows) == 3, rows
        assert rows[0][0:2] == ['syntax_error', str(target)], rows
        assert '[Errno 13]' in rows[0][2] and 'Permission denied' in rows[0][2], rows
        assert rows[1] == ['ok', str(later), ''], rows
        assert rows[2] == ['summary', '1 ok, 0 stale, 1 broken'], rows
        assert not err.getvalue(), err.getvalue()
        print('exit:', code)
        print(out.getvalue(), end='')
        print('stderr: empty')
    finally:
        denied.chmod(0o700)
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip() == head
print('PASS: real parent permissions retain error detail and later rows; modes restored and fixture removed.')
