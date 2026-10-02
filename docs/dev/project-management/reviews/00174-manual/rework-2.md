Second-cycle repairs:
- Bob C1 (Medium): raw disk differences could normalize away at staging. Implementation no-edit detection now uses Git commit semantics (working diff + untracked candidate); Tess tests continue direct disk blob/type/mode comparison plus index comparison. LF-to-CRLF and core.filemode=false chmod fixtures were observed failing then fixed. Removed the now-unused index option from the immutable-content helper.
- Blake: the attempt payload example still excluded runtime files. Updated the enum and added a focused prose regression.
Cycle-2 Alice found no remaining PRD defects; all seven first-cycle repairs were independently verified. Baseline-only MECH finding and old test_work_routing.py file size are preserved as existing debt, not expanded into this PRD.
