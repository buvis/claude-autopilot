---
catchup: skip
design: skip
default_model: sonnet
---

# A synthetic twenty-five path PRD

### Problem Statement

Twenty-five modules need one edit each.

### Repository Structure

```
pkg/
├── m01.py
├── m02.py
├── m03.py
├── m04.py
├── m05.py
├── m06.py
├── m07.py
├── m08.py
├── m09.py
├── m10.py
├── m11.py
├── m12.py
├── m13.py
├── m14.py
├── m15.py
├── m16.py
├── m17.py
├── m18.py
├── m19.py
├── m20.py
├── m21.py
├── m22.py
├── m23.py
├── m24.py
└── m25.py
```

## Implementation Phases

### Phase 0: First half

- [ ] Edit `pkg/m01.py` `pkg/m02.py` `pkg/m03.py` `pkg/m04.py` `pkg/m05.py` `pkg/m06.py` `pkg/m07.py` `pkg/m08.py` `pkg/m09.py` `pkg/m10.py` `pkg/m11.py` `pkg/m12.py` `pkg/m13.py` - Acceptance: `pytest -q pkg` passes

**Exit Criteria**: `pytest -q pkg` green.

### Phase 1: Second half

- [ ] Edit `pkg/m14.py` `pkg/m15.py` `pkg/m16.py` `pkg/m17.py` `pkg/m18.py` `pkg/m19.py` `pkg/m20.py` `pkg/m21.py` `pkg/m22.py` `pkg/m23.py` `pkg/m24.py` `pkg/m25.py` - Acceptance: `pytest -q pkg` passes

**Exit Criteria**: `pytest -q pkg` green.
