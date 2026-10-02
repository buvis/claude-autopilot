# Review task context

Standalone review: no canonical task store or autopilot state exists. Both PRD task checkboxes are complete.

| Task | Description | Commit |
|---|---|---|
| 1 | Guard target reads and stat; directory/read/race regressions. Folded with task 2. | ece9ac34053a17e9629e9af50355e7c84dc32fe2 |
| 2 | Guard repair write/replace/cleanup; error detail and read-only regressions; changelog. Folded with task 1. Rework covers orphan stat/unlink and helper extraction, guarded symlink status, exclusive temporary creation, and unique target rows. | ece9ac34053a17e9629e9af50355e7c84dc32fe2; 31fe06b59973374da818a116ec4b3606845049d6; 6906a89bff8f0cf8067b61628844561d94553a5f |
