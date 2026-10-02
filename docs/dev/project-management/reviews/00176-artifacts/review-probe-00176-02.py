import contextlib
import errno
import io
import os
from pathlib import Path
import tempfile
import types
from unittest.mock import patch

source = Path('skills/use-codex/scripts/codex_hook_doctor.py')
doctor = types.ModuleType('doctor')
exec(compile(source.read_bytes(), str(source), 'exec'), doctor.__dict__)
root = Path('/virtual-review')
config = root / 'hooks.json'
first = root / 'hooks/protect_config.py'
second = root / 'hooks/validate_commit_msg.py'
hooks = {'PreToolUse': [{'hooks': [
    {'type': 'command', 'command': f'python3 {first}'},
    {'type': 'command', 'command': f'python3 {second}'},
]}]}
error = PermissionError(errno.EACCES, 'Permission denied', str(first))
stdout, stderr = io.StringIO(), io.StringIO()
with patch.object(doctor, '_resolve_roots', return_value=(config, root / 'aegis', root / 'autopilot')), patch.object(doctor, 'check', return_value=[('stale', str(first), ''), ('stale', str(second), '')]), patch.object(doctor, '_load_hooks', return_value=hooks), patch.object(Path, 'lstat', side_effect=error), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
    exit_code = doctor.main(['repair'])
print('is_symlink OSError:')
print({'exit_code': exit_code, 'stdout': stdout.getvalue(), 'stderr': stderr.getvalue()})
assert exit_code == 2 and stdout.getvalue() == ''

if os.geteuid() == 0:
    raise SystemExit('Run as a non-root user; root bypasses permission bits.')
with tempfile.TemporaryDirectory(prefix='blake-00176-') as directory:
    root = Path(directory)
    target = root / 'protect_config.py'
    target.write_bytes(b'X = 1\n')
    temp = root / 'protect_config.py.tmp'
    temp.write_bytes(b'pre-existing operator data\n')
    temp.chmod(0o444)
    try:
        print('before:', temp.exists(), repr(temp.read_bytes()))
        row = doctor._write_repair(target, root / 'canonical.py', b'X = 2\n')
        print('verdict:', row[0])
        print('detail:', row[2])
        print('temp exists after:', temp.exists())
        print('target bytes after:', repr(target.read_bytes()))
        assert row[0] == 'unrepairable'
        assert target.read_bytes() == b'X = 1\n'
        assert not temp.exists(), 'Pre-existing temp was preserved.'
    finally:
        if temp.exists():
            temp.chmod(0o600)

