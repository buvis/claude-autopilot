# PRD 00277 — blocking escalation: the "severity emoji anywhere" rule cannot ship as written

Raised: 2026-10-13, review cycle 1 rework (task 7, `[D1] skills/run-autopilot/cli/gate.py`).
Measured in the loop session that implemented the rework findings; the PRD was
stalled to `hold/` rather than guessed through.

## The contradiction

PRD 00277 § "Feature: Severity-content flag (packet 4)" says:

> `_unread_token` also flags any unconsumed line that carries a severity emoji
> (🔴🟠🟡⚪) **anywhere on the line** ...

Review cycle 1 raised four 🟠 findings against task 1's narrower implementation
(ALICE, BLAKE, BOB), all demanding exactly that literal rule, including the
tokenless shapes `- 🔴 crash on empty input` and
`- 🔴 CRITICAL: stale cache survives restart`.

The same PRD's § Success Metrics says:

> The 95 real past reviews walter replayed still pass `gate` exit for exit (a
> measured false-refusal count of 0, or each new refusal listed and accepted).

**These two cannot both hold.** The house review-file format uses severity
emoji in ordinary narrative — severity splits ("57 findings: 3 🔴 Critical,
15 🟠 High, 24 🟡 Medium, 15 ⚪ Low."), dedup narration ("Alice's 🟠 and Bob's
🟡 both say ..."), headings ("## Orchestrator verification of the 🟠 HIGH") and
reviewer lens bullets ("- 🟡 Blake: \"...\""). Those lines are
structurally indistinguishable from the finding rows the PRD wants refused.

## What was measured (not estimated)

The implementation of the literal rule exists and is complete: it turns the
task's own 105 tests green (`test_gate_findings_unread_shapes.py`, committed at
`7a386b5`). Its patch is preserved at the end of this file. Every number below
came from a real run of
`skills/run-autopilot/cli/test_gate_findings_real_fixtures.py` (the 79-review
replay guard) or from a read-only scan of all 114 saved review files.

| Candidate rule | Real reviews that flip to `malformed` |
|---|---|
| emoji anywhere on the line (PRD literal) | **29 of 79**, plus 2 hard-coded assertions on `cli/fixtures/00256-review-1.md` break |
| emoji anywhere **on a pipe-shaped line** (ALICE/BLAKE's wording) | **11 of 79** |
| emoji anywhere, scoped to the **`## Consolidated Findings` section only** | **55 of 114** files carry an emoji on an unconsumed line inside that section |
| today's rule (emoji + pipe + severity word, or + `Found by:`) | **0** (measured by removing just the emoji arm) |

The flipped files include this batch's own neighbours — `00265-review-2`,
`00269-review-1/2`, `00270-review-1/2`, `00271-review-2`, `00276-review-1/2`.
Shipping the literal rule would therefore make the gate refuse review files
written in the format this loop itself produces, i.e. `review-close` would
refuse the next cycle's own review file and the review gate would block.

## Why this is a human decision

It changes what the PRD promises, and it blocks the three queued sibling tasks:
task 8 (test-file split), task 9 (refusal-line cases) and task 10 (the replay
baseline / `_ACCEPTED_FLIPS` content) all depend on which semantics ship. The
options are not equivalent engineering choices — each trades detection against
false refusals on the live review path:

1. **Accept the flips.** Ship the literal rule, list the 29 paths in
   `_ACCEPTED_FLIPS` (`test_gate_findings_real_fixtures.py:173`) and re-pin the
   2 hard assertions. Benefit: every PRD shape is caught. Drawback: the gate
   refuses most real review files from now on, so the review-file format has to
   change in the same breath (no severity emoji in narrative).
2. **Narrow the rule to a pipe-shaped line.** 11 flips instead of 29, catches
   the headline `- 🔴 crash | src/a.py:3` shape. Benefit: fixes the shape the
   consensus reviewers actually quoted. Drawback: still 11 live false refusals,
   and the two tokenless shapes stay unflagged.
3. **Require a stronger row signal** (for example emoji **plus** a `path:line`
   token **plus** a pipe). Unmeasured; likely few flips. Benefit: may reach 0
   while still catching real rows. Drawback: a reviewer who omits the file cell
   still escapes, and it needs its own measurement pass.
4. **Drop packet 4's emoji clause** and keep the other three cycle-1 findings
   (the ref-prefixed marker variant, the marker on a tabular line, the indented
   fenced header). Benefit: zero regression, 5 of the 7 cycle-1 findings fixed.
   Drawback: the PRD's headline escape stays open and the PRD needs rewording.

## State of the work when the PRD stalled

- Committed: `34744e6` (the new test file plus its two registrations) and
  `7a386b5` (the strengthened tests, after the adversarial validator broke the
  first draft with 8 proven exploits). **Those tests are red against `master`
  by design** — 67 of 105 fail, each failure being the absent feature. The
  suite stays red until the decision above lands; that is the loud marker, not
  an oversight.
- Reverted, not committed: the implementation of the literal rule. The patch
  below applies cleanly to `skills/run-autopilot/cli/gate.py` at `7a386b5`.
  Its three independent, 0-flip parts (the `R9 ［2/2］` reference anchor, the
  marker-anywhere-on-a-tabular-line arm, the stripped fenced-header read) and
  its two simplifications (one `_closed_fences` generator shared by `_unfenced`
  and `_fenced_findings_header`; `_is_unread_line` split into named predicates)
  are worth keeping under any option above.
- Not started: tasks 8, 9 and 10 of review cycle 1.

## Resume

Pick an option, reword the PRD's packet-4 feature to match, move
`docs/dev/project-management/prds/hold/00277-catch-critical-rows-in-every-shape-v1.md`
back to `backlog/`, and re-run. The emoji tests in
`test_gate_findings_unread_shapes.py` encode option 1 and must be re-pinned to
whichever option wins — they are the spec, so change them deliberately rather
than letting an implementor weaken them.

## Preserved patch (the literal rule, 105 tests green, 29 corpus flips)

```diff
--- a/skills/run-autopilot/cli/gate.py
+++ b/skills/run-autopilot/cli/gate.py
@@ import argparse
 import json
 import re
 import sys
+from collections.abc import Iterator
 from pathlib import Path
@@ regex block
-# A consensus-marker variant leading the line, after any indent and any bullet,
-# blockquote or ordinal ("1." / "1)") markers, optionally wrapped in one level
-# of emphasis ("**［2/2］**"): spaced or asymmetric brackets, fullwidth or
+# One consensus-marker variant: spaced or asymmetric brackets, fullwidth or
 # lenticular brackets, or parentheses, open and close matched independently.
-# Indent is unbounded, like _CANDIDATE_ROW_RE. Anchored so a count in prose
-# ("(1092/1092)") or a heading ("### Full Consensus (3/3)") stays unread.
+_MARKER = r"[\[(［【]\s*\d+\s*/\s*\d+\s*[\])］】]"
+# The variant leading the line, after any indent, any bullet, blockquote or
+# ordinal ("1." / "1)") markers, an optional finding reference ("R9 ［2/2］")
+# and one level of emphasis ("**［2/2］**"). Indent is unbounded, like
+# _CANDIDATE_ROW_RE. Anchored so a count in prose ("(1092/1092)") or a heading
+# ("### Full Consensus (3/3)") is no row.
 _CONSENSUS_VARIANT_RE = re.compile(
-    r"^[ \t]*(?:(?:[-*+>]|\d+[.)])[ \t]*)*(?:\*{0,2}|_{0,2})"
-    r"[\[(［【]\s*\d+\s*/\s*\d+\s*[\])］】]",
+    r"^[ \t]*(?:(?:[-*+>]|\d+[.)])[ \t]*)*(?:R\d+[ \t]+)?(?:\*{0,2}|_{0,2})" + _MARKER,
 )
-# A severity emoji followed by its severity word ("🔴 CRITICAL"): a reviewer's
-# "[BLAKE] 🟡 issue | File: x" lens bullet names no word and stays unread.
-_SEVERITY_EMOJI_WORD_RE = re.compile(
-    _SEVERITY_EMOJI_ANY_RE.pattern + r"\s*(CRITICAL|HIGH|MEDIUM|LOW)\b(?!-)",
-    re.IGNORECASE,
-)
-# The attribution every finding row ends with (`| Found by: alice`, see
-# _FINDING_ROW_RE): beside a pipe and a severity emoji it marks a wordless
-# finding row, which a reviewer's free-text lens bullet never carries.
-_FOUND_BY = "Found by:"
+# The same variant anywhere on the line, read only beside _ROW_SHAPE_RE: on a
+# line that is already tabular the marker needs no anchor.
+_MARKER_ANY_RE = re.compile(_MARKER)
@@ fence walk
+def _closed_fences(lines: list[str]) -> Iterator[tuple[int, int]]:
+    """Every CLOSED fence in `lines`, as (opener index, closer index) spans, in
+    order. The raw line decides, through `_FENCE_RE`: a fence opens or closes
+    only on a line indented at most 3 spaces, and closes only on a run of its
+    own character at least as long as the opener's (trailing text allowed); one
+    that never closes quotes nothing - and stops the walk right there."""
+    i = 0
+    while i < len(lines):
+        opener = _FENCE_RE.match(lines[i])
+        if opener is not None:
+            run = opener.group(1)
+            for j in range(i + 1, len(lines)):
+                closer = _FENCE_RE.match(lines[j])
+                if closer is not None and closer.group(1).startswith(run):
+                    yield i, j
+                    i = j
+                    break
+            else:
+                return
+        i += 1
+
+
 def _unfenced(text: str) -> str:
     """`text` with every line of a CLOSED fence blanked, opener and closer
-    included, so a quoted example is no heading and no row while line numbers
-    hold. ..."""
+    included, so a quoted example is no heading and no row while line numbers
+    hold."""
     lines = text.splitlines()
     live = list(lines)
-    (the old inline opener/closer walk)
+    for start, end in _closed_fences(lines):
+        live[start : end + 1] = [""] * (end + 1 - start)
     return "\n".join(live)
@@ predicates
+def _is_marker_variant(line: str) -> bool:
+    """A consensus marker, in any spelling: the plain `[m/n]` token anywhere, a
+    bracket variant leading the line, or a variant anywhere on a line that is
+    already tabular - there the row shape is the anchor, so a marker mid-cell
+    (`<td>［2/2］</td>`) counts with no severity signal to help."""
+    return bool(
+        _CONSENSUS_TOKEN_RE.search(line)
+        or _CONSENSUS_VARIANT_RE.match(line)
+        or (_ROW_SHAPE_RE.search(line) and _MARKER_ANY_RE.search(line))
+    )
+
+
+def _is_severity_row(line: str) -> bool:
+    """A severity signal with nothing else to key on: a severity emoji anywhere
+    on the line - position is irrelevant, so a trailing one counts like a
+    leading one - or a severity word with pipes around it, which makes it a
+    cell rather than the prose `the reviewer called the risk high`."""
+    return bool(
+        _SEVERITY_EMOJI_ANY_RE.search(line) or _SEVERITY_WORD_CELL_RE.search(line)
+    )
+
+
+def _is_pipeless_row(line: str) -> bool:
+    """A pipe-less table row: columns separated by runs of whitespace, whose
+    only structural signal is the bare `m/n` leading it, read beside a severity
+    word so a counting line (`ran 1092/1092 green`) is no row."""
+    return bool(_LEADING_RATIO_RE.match(line) and _SEVERITY_WORD_ANY_RE.search(line))
+
+
 def _is_unread_line(line: str) -> bool:
     """Whether `line` carries a [m/n] token or a finding-shaped row that,
     left unconsumed by the findings parser, must be flagged as unread."""
     return bool(
-        (the old 7-arm boolean)
+        # A leading pipe is a table row whatever it carries.
+        _CANDIDATE_ROW_RE.match(line)
+        or _is_marker_variant(line)
+        or _is_severity_row(line)
+        or _is_pipeless_row(line)
     )
@@ fenced header
 def _fenced_findings_header(text: str) -> bool:
     """True when a CLOSED fence (``` or ~~~) in the raw text contains a line
     naming Severity, Issue and File - the findings-table header - anywhere in
-    its body. Walks fence blocks with the same opener/closer rule as
-    `_unfenced` ..."""
+    its body. Walks the same fence spans as `_unfenced`, and reads each body
+    line stripped: a fence that indents its header hides it just as well."""
     lines = text.splitlines()
-    (the old duplicated fence walk)
+    return any(
+        _table_header(body_line.strip()) is not None
+        for start, end in _closed_fences(lines)
+        for body_line in lines[start + 1 : end]
+    )
```

The exact, byte-level patch is recoverable from the task-7 implementor
transcript of this session; the block above is the whole change in reviewable
form, with the unchanged bodies elided.
