# Completed tasks

Standalone manual review: no state.json or canonical task store exists. The two checked PRD tasks and commit scope supply the table below; they do not substitute for independent verification.

| Task | Description | Commit |
|---|---|---|
| 1 | Guard target read_bytes calls and stat in _verdict_for; map OSError to syntax_error and cover directory targets with fail-first tests. Shared commit with task 2. | ece9ac34053a17e9629e9af50355e7c84dc32fe2 |
| 2 | Guard write_bytes and replace in _repair_known, clean partial temp files, preserve later rows; add regression tests and Fixed changelog entry. Shared commit with task 1. | ece9ac34053a17e9629e9af50355e7c84dc32fe2 |
