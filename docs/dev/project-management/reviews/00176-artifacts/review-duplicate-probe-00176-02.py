import json
from pathlib import Path
import tempfile
import types

source = Path('skills/use-codex/scripts/codex_hook_doctor.py')
doctor = types.ModuleType('doctor')
exec(compile(source.read_bytes(), str(source), 'exec'), doctor.__dict__)
with tempfile.TemporaryDirectory(prefix='bob-00176-') as directory:
    root = Path(directory)
    hooks = root / 'hooks'
    hooks.mkdir()
    orphan = hooks / 'a_dangling.py'
    orphan.symlink_to(root / 'absent.py')
    later = hooks / 'z_empty.py'
    later.touch()
    config = root / 'hooks.json'
    config.write_text(json.dumps({'hooks': {}}), encoding='utf-8')
    rows = doctor.repair(config=config, aegis_root=root, autopilot_root=root)
    print(rows)
    duplicates = [row for row in rows if row[1] == str(orphan)]
    print('rows for dangling target:', len(duplicates))
    print('later orphan removed:', not later.exists())
    assert len(duplicates) == 2
    assert not later.exists()

