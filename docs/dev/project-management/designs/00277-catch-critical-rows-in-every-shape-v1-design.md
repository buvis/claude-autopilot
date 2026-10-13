# Design: Catch CRITICAL rows in every shape

## Architecture fit

All four fixes land in `skills/run-autopilot/cli/`, the gate module the PRD
already names: `gate.py` owns the three content-reading rules
(`_unfenced`, `_unread_token`, the fenced-findings-header check), and
`__main__.py` owns the one-line-refusal `repr()` fix. No new module, no new
layer - this is a backstop that reads review-file text by content before
`review-close` ever applies a findings JSON, per the Component Boundaries
capsule entry ("`skills/run-autopilot/cli/` is the sole `state.json` mutator
surface"; `gate.py` sits beside it as the sole findings-shape reader).

## Module placement

- `skills/run-autopilot/cli/gate.py` - edit three functions/regexes:
  - `_unfenced` (fence-opener/closer matching, line 517-543)
  - `_unread_token` (severity-content flag, line 546-582)
  - a new check inside `_malformed_detail` / `_cross_check_findings` for a
    fenced block containing the findings-table header (packet 17)
- `skills/run-autopilot/cli/__main__.py` - edit `_boundary_refusal_line`
  (line 1028-1039) to `repr()` its two value arguments.
- `skills/run-autopilot/cli/test_gate_findings_shapes.py` - new parametrized
  tests (see Test strategy).
- `skills/run-autopilot/cli/test_gate_findings_real_fixtures.py` - the
  real-review replay guard (new file, if none of the existing fixture-replay
  suites already walks every past review; checked at task time - see Risks).
- `skills/run-autopilot/cli/test_review_stage_paths.py` - one new test for
  the `repr()` refusal line.
- `skills/review-work-completion/references/output-formats.md` - one new
  sentence at/after line 101.
- `CHANGELOG.md` - `[Unreleased] ### Fixed` entries.

No new files beyond tests; every production edit is to an existing function.

## Interfaces & contracts

### `gate._unfenced(text: str) -> str` (fence rule, packet 5)

Replace the opener/closer match target. Today:

```python
_FENCE_RE = re.compile(r"^(`{3,}|~{3,})")
...
opener = _FENCE_RE.match(lines[i].strip())      # matches the STRIPPED line
...
if lines[j].strip().startswith(run):            # closer: also stripped
```

New:

```python
_FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
...
opener = _FENCE_RE.match(lines[i])              # matches the RAW line
...
closer = _FENCE_RE.match(lines[j])              # also the RAW line
if closer is not None and closer.group(1)[0] == run[0] and len(closer.group(1)) >= len(run):
```

`_FENCE_RE` now encodes the CommonMark indentation ceiling itself (`{0,3}`
leading spaces before the fence marker), so both the opener and the closer
read it off the untouched line. A line indented with a tab or 4+ spaces no
longer matches: CommonMark reads 4-space/tab indentation as an indented code
block, not a fence, so the PRD's `tab_fence_opener` and
`four_space_fence_opener` shapes stop opening a fence and the rows after them
are no longer blanked. The closer's character-and-length check moves from
`str.startswith` on `run` (a string) to comparing `closer.group(1)[0]` against
`run[0]` (same fence character) and `len(closer.group(1)) >= len(run)` (at
least as long) - `.startswith` on the stripped text is retired because the
raw-line match already strips at most 3 leading spaces before the marker, so
`closer.group(1)` is just the backtick/tilde run with no leading spaces to
account for.

**Regression guard (PRD 00269's `4ed526e` fix):** the existing
`test_an_indented_fence_still_quotes_its_rows` fixture indents its fence by
exactly 2 spaces (`"  ```\n  {_ALICE_ROW}\n  ```"`) - within the new `{0,3}`
ceiling, so it keeps matching and keeps quoting its row. The new tests use 4
spaces and a tab, strictly above the ceiling.

### `gate._unread_token(live: str) -> str | None` (severity-content flag, packet 4)

**Revised after dispatch-1/dispatch-2 review** (both runs independently
measured real false refusals: plain prose mentioning 🟡/🟠 in a "Review
Summary" line, and `### Full Consensus (3/3)` headings matching a bare
parenthesized count - neither is a hidden finding). The fix gates the new
emoji/word/variant signals on the line ALSO looking like a row - every one
of packet 4's seven shapes (bullet, blockquote table, pipe-less table, HTML
`<table>`, each carrying a consensus-variant) already looks like a row by
construction, so the gate loses no real catch while dropping the measured
false positives (prose and headings are neither bulleted, piped, nor
HTML-tabled).

Add regexes above the function (near `_CONSENSUS_TOKEN_RE`, which **stays
exactly as-is and keeps running unchanged** in the loop below - it is NOT
replaced, so its proven-safe existing bracket-token behavior over the 83/159
real review files that already clear it is untouched):

```python
# A line that looks like a row by shape alone: a bullet/blockquote marker at
# the start, a pipe anywhere, or an HTML table/cell tag anywhere. Gates the
# three signals below so a severity word or count in ordinary prose (a
# "Review Summary" line, a "### Full Consensus (3/3)" heading) is not itself
# read as a hidden finding - only a line already shaped like a row is.
_ROW_SHAPE_RE = re.compile(r"^\s*[-*+>]|\||<t(?:able|d)\b", re.IGNORECASE)
# A severity emoji anywhere on a row-shaped line.
_SEVERITY_EMOJI_ANY_RE = re.compile("[\U0001f534\U0001f7e0\U0001f7e1⚪]")
# A severity WORD only counts when a `|` sits on either side of it - a table
# cell, not the word loose in prose ("the severity is high" must not trip
# this). Case-insensitive so `| High |` and `| HIGH |` both match. (Already
# row-shaped by definition - a `|` is present - so this one needs no extra
# `_ROW_SHAPE_RE` gate; kept ungated for that reason.)
_SEVERITY_WORD_CELL_RE = re.compile(
    r"\|\s*(CRITICAL|HIGH|MEDIUM|LOW)\s*\|", re.IGNORECASE
)
# Consensus-marker variants a model might write instead of the plain bracket:
# spaced (`[2 / 2]`), full-width brackets (`［2/2］`), and parenthesized
# (`(2/2)`). Gated on BOTH `_ROW_SHAPE_RE` and a co-occurring severity signal
# on the same line - every packet-4 test shape pairs its consensus variant
# with the hidden row's own severity emoji/word by construction, so this
# loses no real catch while refusing to match a bare `(3/3)` in a heading or
# narrative sentence that carries no severity marker at all.
_CONSENSUS_VARIANT_RE = re.compile(
    r"\[\s+\d+\s*/\s*\d+\s+\]|［\s*\d+\s*/\s*\d+\s*］|\(\s*\d+\s*/\s*\d+\s*\)"
)
_SEVERITY_SIGNAL_RE = re.compile(
    "[\U0001f534\U0001f7e0\U0001f7e1⚪]"
    r"|\|\s*(?:CRITICAL|HIGH|MEDIUM|LOW)\s*\|",
    re.IGNORECASE,
)
```

In the function's second loop (the one that flags any *unconsumed* line,
today testing `_CONSENSUS_TOKEN_RE.search(line) or _CANDIDATE_ROW_RE.match(line)`):

```python
for i, line in enumerate(lines):
    if i in consumed:
        continue
    row_shaped = _ROW_SHAPE_RE.search(line) is not None
    if (
        _CONSENSUS_TOKEN_RE.search(line)                    # unchanged
        or _CANDIDATE_ROW_RE.match(line)                     # unchanged
        or (row_shaped and _SEVERITY_EMOJI_ANY_RE.search(line))
        or _SEVERITY_WORD_CELL_RE.search(line)
        or (
            row_shaped
            and _CONSENSUS_VARIANT_RE.search(line)
            and _SEVERITY_SIGNAL_RE.search(line)
        )
    ):
        return (
            f"line {i + 1}: a [m/n] token or table row the findings parser "
            f"did not read: {line.strip()[:120]}"
        )
```

**The refusal message text is UNCHANGED** - dispatch-1 review found
`test_gate_findings_shapes.py:384` pins the literal constant
`_UNREAD = "a [m/n] token or table row the findings parser did not read: "`
and roughly a dozen parametrized tests build their expected detail off that
constant, plus `__main__.py`'s and `gate.py`'s own docstrings and
`test_review_verbs_prose.py:107-108` quote the same wording. The original
draft's wording change is dropped entirely; no caller or test needs editing
for this reason. (The earlier claim that "no other code depends on its
exact wording" was wrong; `rg -n "a \[m/n\] token"` finds the pinned
constant and its consumers before any task starts.)

### `gate` - fenced findings-header check (packet 17)

A new private helper, called from `_malformed_detail` (or inline in
`_cross_check_findings` before the `_unfenced` call - the design and the
exit-criteria test name the behavior, not the call site, so plan-tasks may
place it in whichever keeps `_malformed_detail` under its current
line-length):

```python
def _fenced_findings_header(text: str) -> bool:
    """True when a CLOSED fence (``` or ~~~) in the raw text contains a line
    naming Severity, Issue and File - the findings-table header - anywhere in
    its body. Walks fence blocks with the same opener/closer rule as
    `_unfenced` (raw line, <=3 leading spaces) rather than reusing a regex
    that assumes the header is the fence's first line."""
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        opener = _FENCE_RE.match(lines[i])
        if opener is not None:
            run = opener.group(1)
            for j in range(i + 1, len(lines)):
                closer = _FENCE_RE.match(lines[j])
                if (
                    closer is not None
                    and closer.group(1)[0] == run[0]
                    and len(closer.group(1)) >= len(run)
                ):
                    body = lines[i + 1 : j]
                    if any(_table_header(bl) is not None for bl in body):
                        return True
                    i = j
                    break
            else:
                break
        i += 1
    return False
```

Reuses `_table_header` (already defined, line 363) rather than a fresh
regex, so "the findings table header" means exactly the same thing here as
it does when reading a real table: a pipe line naming severity, issue and
file (case-insensitive, any column order, any extra columns) - matching the
PRD's literal example `Ref | ... | Severity | Issue | File` only by virtue
of `_table_header` already accepting that shape.

Wire it into `_malformed_detail`, before the existing checks (it must win
over "no-section" when the only findings heading on the page is itself
inside the fence - `_FINDINGS_HEADING_RE` search is unscoped by fences, so a
fenced heading already gets read as a real heading today; this new check is
needed only for the TABLE inside the fence, which `_unfenced` already blanks
before `_reviewed_keys` runs, so the table rows are correctly invisible -
the problem is that invisibility is exactly the hiding bug packet 17 flags):

```python
def _malformed_detail(live, findings, problem, raw_text=None):
    if len(_FINDINGS_HEADING_RE.findall(live)) > 1:
        return _FINDINGS_PROBLEMS["repeated-section"]
    if raw_text is not None and _fenced_findings_header(raw_text):
        return (
            "a fenced block (``` or ~~~) contains the findings table header "
            "(naming Severity, Issue and File): the header row must never be "
            "fenced, even to show an example"
        )
    unread = _unread_token(live)
    ...
```

`_malformed_detail` gains a fourth parameter, `raw_text` (the pre-`_unfenced`
text), because the check must see the ORIGINAL text including fence markers
- `live` has already had the fence body blanked by the time
`_malformed_detail` runs. `_cross_check_findings` (the sole caller, line
611-656) already holds both `text` (raw) and `live` (`_unfenced(text)`), so
it passes `raw_text=text` at its one call site - no other caller of
`_malformed_detail` exists (`rg -n "_malformed_detail("` shows one
definition and one call).

### `gate._table_header` - example rows without the header stay allowed

No change needed for new tests: `test_fenced_example_rows_without_header_still_pass`
exercises a fence containing data-row-shaped lines (`| [2/3] | ... |`)
but no header line naming Severity/Issue/File. `_fenced_findings_header`
only trips on the header line itself (via `_table_header`), so a fence that
quotes example rows under a *prose* explanation, not a real header, passes
clean - matching the PRD's "Fenced example rows without that header stay
allowed."

**Mandatory revision to an EXISTING test (dispatch-1 review finding):**
`test_a_fenced_example_row_and_heading_are_not_findings`
(`test_gate_findings_shapes.py:519-537`) fences, under `## Alice`, a block
containing the real header (`TABLE_HEADER_REF_6`) plus a data row, and
today asserts `("ok", None, 0)` for the whole file - exactly the packet-17
hiding bug this PRD closes, just located under a reviewer heading rather
than inside `## Consolidated Findings`. `_fenced_findings_header` scans the
whole raw text, not only the Consolidated Findings section, so this
fence now correctly trips it. This is the FIX working as intended, not a
regression, but the task that wires in the check must split this test
rather than leave it red: keep the `in_section` fences (the `~~~~`/`~~~`
bullet-only rows, no header line) asserting `("ok", None, 0)` unchanged,
and change the `alice=example` fence (the one carrying the real header) to
its own assertion of `("malformed", ..., 2)` - or rename/split the test
into two, one per fence, whichever keeps each assertion legible. Per
`rules/testing.md` ("fix the implementation, not the test... unless a test
looks wrong, say so"): this test's old assertion encoded the exact bug
packet 17 reports, so revising it is the PRD's own acceptance criterion,
not a workaround - call this out explicitly in the task report.

### `__main__._boundary_refusal_line` (packet 18)

```python
def _boundary_refusal_line(
    field: str,
    raw: str,
    resolved: Path,
    boundary_desc: str,
    state_path: Path,
) -> str:
    """The one-line refusal for a field that escaped its required boundary."""
    return (
        f"autopilot: review-stage: `{field}` {raw!r} resolves to"
        f" {str(resolved)!r}, outside {boundary_desc!r} ({str(state_path)!r})"
    )
```

Every dynamic value in the line - `raw`, `resolved`, `boundary_desc`, and
`state_path` - goes through `repr()` (`!r`), `resolved` and `state_path`
coerced to `str` first so they read as a plain quoted path rather than
`PosixPath('/abs/path')`. `repr()` on a `str` escapes `\n` and renders
`\x1b` as the literal four characters `\x1b` (never the raw ESC byte) -
Python's `repr` always escapes non-printable characters for `str`, which is
exactly the property that stops a forged `\n`-separated line or a raw ANSI
escape from reaching the terminal unescaped. Only `field` stays bare - it is
one of the two literal strings `"prd"`/`"design_doc"` the call site hardcodes,
never a value read from anywhere external.

**`state_path` is escaped (dispatch-2/codex review finding); `boundary_desc`
is ALSO escaped now (dispatch-3/codex verification finding):** the first
draft escaped only `raw` and `resolved`. Dispatch 2 found `state_path` (the
`--state` CLI argument) still interpolated verbatim and it was fixed.
Dispatch 3's verification pass then found the fix for `state_path` correct
but pointed out that the design's OWN justification for leaving
`boundary_desc` bare - "it is built only from process-resolved paths, not
from attacker-controlled fields" - does not actually make it safe: resolving
a path does not strip control characters FROM the path's own text, so a
repo checked out into a directory whose name itself contains a newline or an
ESC byte (unusual, but not something `Path.resolve()` prevents) would still
forge extra lines through `boundary_desc`, exactly the "always one line"
guarantee the PRD's third Success Metric states as unconditional, not
"unconditional except for repo path content." Rather than add a second
narrower argument, every dynamic value is now escaped uniformly - no
component's safety depends on reasoning about what can and cannot reach it.

**Existing-caller compatibility:** `test_review_stage_paths.py:106` asserts
`` f"`{field}` '{raw}' resolves to" in err `` - a bare single-quoted `raw`
with no `repr()` escaping. That assertion is for a `raw` value with no
quote/backslash content (a plain relative path like `"../outside.md"`),
where `repr()` of a plain string without the above lands on the same
`'../outside.md'` text (Python's `repr()` for a string containing no special
characters wraps it in single quotes with no further escaping) - so the
existing test keeps passing unchanged. The design doc flags this as a thing
to verify rather than assume: plan-tasks' acceptance criterion is "passes at
base" for the new test only, but the existing suite's green-after-change is
load-bearing too (Exit Criteria's full-suite run covers it).

## Data flow

1. `gate --findings` / `review-close` read a review file's raw text.
2. `_cross_check_findings` calls `_unfenced(text)` to get `live` (fence
   bodies blanked) - now using the raw-line, `<=3`-space-indent fence rule.
3. `_reviewed_keys(live)` extracts bullet/table rows from the
   `## Consolidated Findings` section of `live`.
4. `_malformed_detail(live, findings, problem, raw_text=text)` runs, in
   order: repeated-heading check, the new fenced-header check (against
   `raw_text`, before fences are blanked), `_unread_token(live)` (now
   widened to severity emoji/word/consensus-variant), then the existing
   no-section / problem-passthrough branches.
5. Any of these returning non-`None` makes `findings_verdict` return
   `("malformed", detail)`, which `review_close.py` and `autopilot gate`
   both turn into exit 2 and a one-line refusal.
6. `_boundary_refusal_line` is unrelated data flow (CLI arg validation in
   `__main__.py`'s `review-stage` command, not the gate) - it fires when a
   `prd`/`design_doc` path argument resolves outside its required boundary,
   independent of findings parsing.

## Reuse inventory

- `gate._table_header` (line 363) - reused as-is by the new
  `_fenced_findings_header` helper instead of writing a second
  header-detection regex. Greps tried: `rg -n "def _table_header|header.*severity"
  skills/run-autopilot/cli/gate.py` - one definition, already general over
  column order and extra columns.
- `gate._FENCE_RE` / the fence-walk loop shape in `_unfenced` - reused
  structurally (not by call) in `_fenced_findings_header`, since both need
  the same opener/closer walk; a shared private `_fence_spans(text)` helper
  was considered (Alternatives) and rejected as unnecessary indirection for
  two call sites.
- `str.__repr__` / `repr()` builtin - stdlib, no helper needed for packet 18.
- Greps tried for an existing "escape control characters" helper before
  reaching for `repr()`: `rg -n "x1b|ascii\(|repr\(" skills/run-autopilot/cli/*.py`
  - no existing sanitizer function; every other CLI error path in this repo
    either prints a plain f-string or (in a handful of places) already uses
    `repr()` directly on a user-controlled value, confirming `repr()` is the
    established idiom here, not a new one.

## Alternatives considered

1. **Smallest-diff version**: patch only `_unread_token`'s token regex and
   `_boundary_refusal_line`'s `repr()`, and leave the fence/fenced-header
   fixes as a follow-up PRD. Rejected: packets 5 and 17 are HIGH/LOW findings
   from the SAME agoge run with reproducible exploits already in hand; the
   PRD's own Success Metrics name all four packets, and splitting them
   doubles the review/rework overhead for work that is already scoped and
   small (two regex edits plus one new ~20-line helper).
2. **One combined `_content_flagged(line)` predicate** merging severity
   emoji/word/consensus-variant into a single compiled alternation instead
   of three separate regexes tried in sequence. Rejected: the three patterns
   test fundamentally different things (a codepoint set, a pipe-bounded
   word, a numeric-ratio shape); keeping them separate keeps each one
   independently testable and the refusal message generation trivial, at the
   cost of three `.search()` calls per unconsumed line instead of one -  a
   negligible cost since review files are at most a few hundred lines.
3. **Chosen: four narrow, independent edits**, each touching exactly the
   function the PRD's feature list names, each covered by its own
   parametrized test file section. This is the design above. It is larger
   than option 1 only by the fenced-header helper (~20 lines) and buys
   closing all four packets in one PRD cycle, which the PRD's framing
   ("packets 4, 5, 17, 18" as one finding set from one agoge run) already
   treats as one unit of work.

## Risks & edge cases

- **False refusals (packet 4, PRD's own Risk):** prose that happens to
  contain `| High |` or a bare 🔴 next to other text, outside the findings
  section, now refuses. Mitigated by the required real-fixture replay
  (Exit Criteria's `test_gate_findings_real_fixtures.py`): any of the 95
  real past reviews that newly refuses must be listed in the task report,
  not silently absorbed by editing the fixture.
- **Fenced-header false refusal (packet 17's own Risk):** a doc that shows
  the full header literally, inside a fence, as a worked example (exactly
  what `output-formats.md` itself did before this PRD) now refuses too -
  this PRD's own prose fix (line 101+) is the mitigation: never fence the
  header row, only example data rows.
- **Likely next changes after this PRD:**
  1. A fifth shape surfaces from a future agoge run (e.g. a severity word
     written as a Markdown **bold** cell, `**High**`, with no surrounding
     `|`) - the three-regex structure in `_unread_token` is built to grow by
     adding one more `.search()` branch, not by rewriting the function.
  2. The real-fixture replay guard (`test_gate_findings_real_fixtures.py`)
     becomes the permanent backstop every future content-flag widening must
     pass before merge - this PRD is what gives it its first real job.
  3. `_fenced_findings_header`'s walk duplicates `_unfenced`'s fence-walk
     loop; a future PRD may be worth extracting a shared `_fence_spans`
     helper once a third caller needs the same walk (not done here per
     Alternative 2's reasoning: two call sites do not yet justify it).
- **This PRD does not change `review_close.py` or `consolidate_findings.py`**
  - both already call into `gate.findings_verdict`/`gate.check`, so no
    caller-side change is needed; the fix is entirely inside `gate.py` and
    `__main__.py`'s own helper.
- **Residual fence-grammar gaps (codex dispatch-2 non-blocker):** both the
  fence walk in `_unfenced` and the new one in `_fenced_findings_header`
  accept a closer followed by trailing non-whitespace (e.g. `` ``` suffix``)
  and an opener whose info string itself contains backticks - both inherited
  from the existing `_unfenced` behavior (`test_a_closer_with_trailing_text_still_closes_the_fence`
  already pins the first as intentional) and left as-is here; a CommonMark
  fence a 4-space/tab-indented LIST ITEM still legitimately opens (list-item
  content indentation is not page-level indentation) is a known edge this
  PRD's raw-line `<=3`-space rule does not special-case - if the real-fixture
  replay (above) surfaces a false refusal from that shape, it is handled
  through `_ACCEPTED_FLIPS` like any other replay finding, not a design
  change.

## Test strategy outline

All new tests live beside the PRD's named files, parametrized where the PRD
names a shape list, to keep one assertion body per concept:

1. `test_gate_findings_shapes.py`:
   - `test_indented_fence_does_not_blank_rows`, parametrized `tab` /
     `4 spaces`, over a fence with an `_ALICE_ROW` after it (placed, like
     the existing `test_an_unclosed_fence_quotes_nothing` fixture, under
     `## Alice` rather than inside `## Consolidated Findings`): asserts
     **`("malformed", _unread_detail(text, _ALICE_ROW), 2)`** - NOT
     `("ok", None, 0)`. (Dispatch-1 review finding: `_ALICE_ROW` carries a
     bracket consensus token; once the fence no longer opens, that line is
     live, unconsumed, and caught by the UNCHANGED `_CONSENSUS_TOKEN_RE`
     branch of `_unread_token` - exactly like the existing
     `test_an_unclosed_fence_quotes_nothing` fixture two tests below it, not
     like a covered, dispositioned row. The PRD's own metric is that both
     indented-fence shapes make `review-close` *refuse* (exit 2); asserting
     `"ok"` would have passed at base, the opposite of "fails at base,
     passes after the fix.")
   - Re-run `test_an_indented_fence_still_quotes_its_rows` and
     `test_a_closer_with_trailing_text_still_closes_the_fence` unmodified -
     both must stay green (the `4ed526e` guard). Update both this test's and
     `_unfenced`'s own docstring away from "the fence rule reads the
     stripped line" (no longer true) to describe the raw-line, `<=3`-space
     rule instead - a doc-only edit, no assertion changes.
   - Split `test_a_fenced_example_row_and_heading_are_not_findings` per the
     `## Interfaces & contracts` note above: its `alice=example` fence (the
     one carrying the real table header) now asserts `("malformed", ..., 2)`;
     its `in_section` fences (bullet-only rows, no header) keep asserting
     `("ok", None, 0)`.
   - `test_critical_row_in_unparsed_shape_is_malformed`, parametrized over
     the seven shapes: 🔴 bullet with no `[m/n]` token, `[2 / 2]`, `［2/2］`,
     `(2/2)`, a blockquoted table, a pipe-less table, an HTML `<table>`. Each
     constructs a review text whose `## Alice` section buries that shape
     beside the `_COVERED` well-formed rows and asserts
     `("malformed", ..., 2)`.
   - `test_fenced_findings_table_is_malformed`, backtick and tilde variants:
     a fence whose body is a full findings table (header + rows) asserts
     `("malformed", ..., 2)`.
   - `test_fenced_example_rows_without_header_still_pass`: a fence with
     data-row-shaped lines but no header line asserts the existing
     `("ok", None, 0)` behavior is unchanged.
2. `test_gate_findings_real_fixtures.py` (new, or extended if a fixture
   replay harness already exists under another name - verify at task time
   with `rg -ln "docs/dev/project-management/reviews" skills/run-autopilot/cli/test_*.py`).

   **Revised after dispatch-1/dispatch-2 review** (both independently found
   the "assert same tag before/after, print flips" plan unbuildable: a
   single pytest run has no access to the pre-change code's verdicts, and a
   test that only prints cannot fail, which cannot satisfy the PRD's own
   acceptance "passes with every real fixture"):

   - A **committed baseline fixture**,
     `skills/run-autopilot/cli/fixtures/gate_replay_baseline.json`, maps
     `{relpath: {"tag": <verdict tag>, "coverage": true|false}}` for every
     file under `docs/dev/project-management/reviews/*.md` that contains a
     `## Consolidated Findings` heading (the shape `gate.findings_verdict`
     can run against at all - files without one, e.g. blind-only or audit
     reports, are out of scope and excluded by this same filter at both
     generation and test time, so the set is defined by content, not by a
     hand-maintained count). This file is generated ONCE, against the
     pre-this-PRD code (`git stash` the in-progress edit, or generate it as
     the very first sub-step of task 1 before any `gate.py` line changes,
     whichever the task finds simpler), and committed alongside the new
     test.
   - For each file, the findings JSON fed to `gate.findings_verdict` is
     reconstructed as one `fix`-classified row per consolidated-table row:
     ref-backed (`"ref": "R1"`, …) when the file's table has a Ref column,
     ref-less (bare severity/file/issue) otherwise. A file with no Ref
     column calls `findings_verdict(text, findings, require_coverage=False)`
     (the tail-sweep calling convention) instead of the default
     `require_coverage=True`, and the baseline records which `coverage`
     mode applied so the replay test calls it the same way.
   - The test asserts, per file, `current_tag == baseline[relpath]["tag"]`,
     **except** for entries in a short, explicit, comment-justified
     `_ACCEPTED_FLIPS` dict inside the test file itself (`{relpath: "which
     new check caused it"}`) - an uncommented flip fails the test; an
     accepted one is asserted to equal the NEW expected tag (not merely
     skipped), so a future regression that flips it again is still caught.
     `_ACCEPTED_FLIPS` starts empty; the task report names every entry it
     had to add and why, satisfying the PRD's Success Metric ("0, or each
     new refusal listed and accepted") as an enforced test, not a free-text
     claim.
3. `test_review_stage_paths.py`:
   - `test_refusal_line_stays_single_line_with_control_chars`: calls
     `_boundary_refusal_line` with `raw = "../x.md\nautopilot: review-stage: FORGED_OK_MARKER\n\x1b[31mRED_MARKER"`
     and asserts the return value's `"\n"` count is 0 (one line) and that
     the literal substring `"autopilot: review-stage: FORGED_OK_MARKER"`
     does NOT appear unescaped (it must appear only inside the `repr()`
     escaping, e.g. as `\\nautopilot: review-stage: FORGED_OK_MARKER` inside
     quotes) - reproducing the PRD's own Critical Scenario 18 at the unit
     level, one line up from the full CLI reproduction.

## Review log

**Dispatch 1 (claude):** 0 cardinal-sin, 5 blocker, 2 non-blocker, 1
question. All 5 blockers fixed in this doc: (1) emoji-anywhere/paren-token
false positives (fixed with `_ROW_SHAPE_RE` + severity-co-occurrence gating),
(2) indented-fence test asserted the wrong verdict (fixed to `malformed`/
exit 2), (3) refusal-message wording would have broken ~12 pinned tests
(reverted - wording stays unchanged), (4) the real-fixture replay test was
unbuildable as "assert same tag, print flips" (fixed with a committed
baseline JSON + an `_ACCEPTED_FLIPS` allowlist), (5) the fenced-header check
flips an existing green test the draft never mentioned (fixed - the test is
split, one case moving to `malformed` as the PRD's own intended fix).
Non-blockers (dead/orphaned regexes, stale docstrings) and the question
(conflicting `_boundary_refusal_line` snippets, call-site ordering) are also
resolved above (dead `_FENCED_HEADER_RE` dropped before this dispatch ran;
`_CONSENSUS_TOKEN_RE` is no longer orphaned - the revised design keeps it
live and unchanged in the loop; docstring updates added to the test
strategy; the single `_boundary_refusal_line` snippet and its
before-`_unread_token` call order are now unambiguous).

**Dispatch 2 (codex):** 0 cardinal-sin, 1 blocker, 4 non-blocker, 1 question.
Blocker fixed: `state_path` is now `repr()`-escaped alongside `raw` and
`resolved`. Non-blockers recorded: packet-5 test now proves refusal via
`_unread_token`, not mere visibility (addressed by the same fix as
dispatch-1 blocker 2); the parenthesized-token false-positive class is
explicitly called out and mitigated via the severity-co-occurrence gate;
residual fence-grammar gaps (trailing text after a closer, nested-list
4-space indentation) are recorded above as an accepted residual risk routed
through the replay's `_ACCEPTED_FLIPS` mechanism rather than further
special-cased; the replay baseline now has a reproducible, committed form.
Question (sole-caller claim for `_malformed_detail`) stands verified in this
session: `rg -n "_malformed_detail\("` against the live repo shows exactly
one definition and one call site (`_cross_check_findings`), confirming the
design's claim.

**Dispatch 3 (codex, verification pass over dispatch 2's fix):** 0
cardinal-sin, 1 blocker, 0 non-blocker, 0 question. Confirmed `state_path`'s
escaping correct, but found the design's OWN justification for leaving
`boundary_desc` bare insufficient: resolving `wip`/`repo_root_resolved` does
not strip control characters a repo's own on-disk directory name could
contain, so the "always one line" guarantee was not actually unconditional.
Fixed by escaping `boundary_desc` too (`{boundary_desc!r}`) rather than
defending a narrower claim - every dynamic value in the line is now `repr()`
escaped uniformly; `field` stays bare because it is always one of the two
literal strings `"prd"`/`"design_doc"`, never external input. Verified no
existing test pins `boundary_desc`'s literal unquoted text (`rg -n
"boundary_desc|resolves outside the repo" skills/run-autopilot/cli/test_review_stage_paths.py`
shows the one hit, "resolves outside the repo", comes from an unrelated
message in `review_stage.py`'s `stage()`, not from `_boundary_refusal_line`),
so this is safe to add with no test fallout.

dispatch 1 (claude): cardinal-sin 0, blocker 5, non-blocker 2, question 1
dispatch 2 (codex): cardinal-sin 0, blocker 1, non-blocker 4, question 1
dispatch 3 (codex): cardinal-sin 0, blocker 1, non-blocker 0, question 0
