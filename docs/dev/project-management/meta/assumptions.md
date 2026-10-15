# Assumptions ledger — PRD 00310-park-cap-regressions-v1

## 1: Write test_cap_check.py fixture tests and register in release-checks

- The review-file fixture uses YAML frontmatter `---\nhead_sha: <sha>\n---` and a `## Consolidated Findings` pipe table with headers `| Ref | Severity | File | Issue |` and plain uppercase severity words (HIGH, CRITICAL, MEDIUM, LOW).
- The import path is `cli.cap_check`, inferred from `skills/run-autopilot/cli/__init__.py` existing (rootdir-insert import mode).
- The previous review file only needs `head_sha`; its findings table is empty.
- The 8 test names and cases (plus 2 CLI-level tests added after review) are the implementor's own, derived from the design doc's contract rather than the PRD's exact naming.
- `rework_range` is directly unit-tested rather than left to transitive coverage.
- Expected short SHAs are computed with `git log --format=%h -1 <sha>`, matching the design's stated `%h` format.
- The previous review's `head_sha` is not checked against an unknown revision; only the current review's is.
