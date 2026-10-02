PRD 00173 consensus review — 2026-09-05

No findings. No severity-rated correctness, regression, contract, or maintainability issues were identified within the PRD scope.

Reviewed the PRD and the diff against HEAD limited to `CHANGELOG.md`, `skills/use-codex/scripts/codex_hook_doctor.py`, and `skills/use-codex/scripts/test_codex_hook_doctor_extra.py`. Other dirty files were excluded. Production and test files were not edited.

- `skills/use-codex/scripts/codex_hook_doctor.py:77`: the guarded canonical read maps `OSError` to `no_canonical` with empty detail. Existing reporting counts that verdict as stale and exits 3 when no target is broken.
- `skills/use-codex/scripts/codex_hook_doctor.py:195`: repair catches the read failure before import validation and dry-run reporting, produces the required `no canonical source (<path>)` detail, and writes the captured bytes at line 212.
- `skills/use-codex/scripts/codex_hook_doctor.py:138` and `:154`: widening to `ValueError` retains Unicode decoding coverage and catches the legacy null-byte parser failure. The earlier `SyntaxError` branches retain their existing markers.
- `skills/use-codex/scripts/codex_hook_doctor.py:204`: the prefix is removed only for a single canonical marker. Real imported identifiers cannot collide with the `_common.py: ` marker, and sibling `_common.py` is excluded from the scan.
- `skills/use-codex/scripts/test_codex_hook_doctor_extra.py:578`, `:604`, and `:635`: the three new parametrized regressions cover check/repair/dry-run directory canonicals, null bytes in both scanner inputs, and exact canonical-only details. Exact TSV/summary assertions and filesystem snapshots cover exits, preservation, and absent temporary writes. The adjusted directory expectation at line 507 follows the PRD's earlier read guard; the existing test still verifies sibling repair continues.

Verification:

- `mise exec -- uv run --no-project --with pytest python -m pytest -q -p no:cacheprovider skills/use-codex/scripts` — 74 passed.
- Isolated scratch fixtures on Python 3.13.13: a chmod-denied canonical produced the required check, repair, and dry-run rows with exit 3; real repair still updated another stale known target.
- Injected `ast.parse` `ValueError` for null-byte input: sibling and canonical paths returned the unreadable marker with exits 1 and 3 respectively, no stderr, and unchanged local `_common.py`. The canonical-only marker omitted the sibling prefix.
- A canonical read probe that raises on a second byte read confirmed `_repair_known` repairs a non-common target from one guarded byte buffer.

Limitations: this reviewer did not run native Python 3.10/3.11; their parser exception shape was exercised by injection. On Python 3.13, the checked-in null-byte tests exercise the existing `SyntaxError` branches and do not independently prove the new `ValueError` catches. The parent separately reports green doctor suites on Python 3.10–3.14 and green release checks (112/5/41/18/27), with inherited session/dispatch environment removed for the stub-only checks; those runs were not duplicated here. Scratch fixtures were removed automatically; no live Codex configuration or autopilot state was touched.
