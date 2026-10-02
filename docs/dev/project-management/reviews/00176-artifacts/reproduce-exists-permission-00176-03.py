import importlib.util
from pathlib import Path
import tempfile

source = Path('/Users/bob/git/src/github.com/buvis/claude-autopilot/skills/use-codex/scripts/codex_hook_doctor.py')
spec = importlib.util.spec_from_file_location('doctor', source)
doctor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(doctor)
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    hooks = root / 'hooks'
    hooks.mkdir()
    target = hooks / 'protect_config.py'
    target.write_text('X = 1\n')
    hooks.chmod(0)
    try:
        print('target.exists:', target.exists())
        try:
            target.stat()
        except OSError as exc:
            print('target.stat:', type(exc).__name__, exc.errno)
        print('verdict:', doctor._verdict_for(target, root, root))
    finally:
        hooks.chmod(0o700)
