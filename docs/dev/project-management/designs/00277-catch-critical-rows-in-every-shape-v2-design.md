# Design: catch critical rows in every shape (v2)

## Architecture fit

`skills/run-autopilot/cli/gate.py` is the deterministic review-file shape
gate (`autopilot gate`), consulted by `review-close`/`review-stage` before a
batch of findings is applied to state. Its unread-line detector
(`_is_unread_line`/`_unread_token`) is the trust boundary that decides
whether a CRITICAL/HIGH row survives into `findings_malformed` refusal or
silently passes. This PRD edits only that detector and the CommonMark fence
reader it shares with `_fenced_findings_header` — no new module, no new
CLI flag, no change to `findings_verdict()`'s public signature. The emoji
table itself (`_SEVERITY_EMOJI`) already lives in `cli/findings_section.py`
and is reused, not duplicated.

## Module placement

Four existing files, no new files:

- `skills/run-autopilot/cli/gate.py` — replace the bullet-lead arm of
  `_is_unread_line`, add `_strip_lead`/`_LEAD_RE`/`_is_emoji_row`, change
  `_unread_token`'s detail for an emoji row, and replace `_FENCE_RE`'s single
  regex with `_fence_open`/`_fence_close` helpers used by `_unfenced` and
  `_fenced_findings_header`.
- `skills/run-autopilot/cli/test_gate_findings_unread_shapes.py` — re-pin
  `test_a_severity_emoji_alone_makes_an_unread_line_a_finding` (below) plus
  the one the PRD names, add the eleven new tests the PRD names.
- `skills/run-autopilot/cli/test_gate_findings_shapes.py` — fix the shared
  `_unread_detail` test helper so every existing caller keeps working, and
  re-pin `test_a_closer_with_trailing_text_still_closes_the_fence` (below).
  This file is NOT a no-touch regression backstop, contrary to an earlier
  draft of this doc — it shares the `_unread_detail` helper and one fence
  test with the behavior this PRD changes; see "Existing-test impact" below.
- `skills/run-autopilot/cli/test_gate_findings_real_fixtures.py` — re-baseline
  `_ACCEPTED_FLIPS`.
- `CHANGELOG.md` — reword line 31, add the Fixed entry.

### Existing-test impact (found by the cross-model review; corrects an
earlier draft's wrong claim that these two files needed no changes)

1. **`test_gate_findings_shapes.py:618`,
   `test_a_closer_with_trailing_text_still_closes_the_fence`** asserts
   `` ```\n{row}\n``` trailing text `` is `("ok", None, 0)` — the OLD,
   incorrect closer rule. Under `_fence_close` this closer no longer closes
   (trailing non-whitespace after the run), so the fence stays open, the
   row inside stays live, and the verdict becomes `("malformed",
   _unread_detail(text, _ALICE_ROW), 2)`. Re-pin the test to assert the
   malformed verdict (rename to `test_a_closer_with_trailing_text_does_not_
   close_the_fence`, or merge it with the PRD-named
   `test_closer_with_trailing_text_does_not_close` so there is one test, not
   two making opposite claims).
2. **`test_gate_findings_unread_shapes.py:67`,
   `test_a_severity_emoji_alone_makes_an_unread_line_a_finding`** calls
   `gate._is_unread_line(row) is True` directly for `_EMOJI_SHAPES` rows
   (e.g. `- 🔴 crash on empty input`) and checks the OLD generic `_UNREAD`
   wording. `_is_unread_line` no longer has an emoji arm (that logic moved
   into `_is_emoji_row`, checked separately in `_unread_token`), so this
   direct-predicate assertion breaks regardless of wording. Re-pin it
   alongside the PRD-named rename: assert `gate._is_emoji_row(row) is True`
   (not `_is_unread_line`) and expect the emoji wording via `_unread_detail`
   (below). This is a second test needing the PRD's rename treatment,
   missed by the first review pass; the PRD's Module section names only
   `test_every_severity_emoji_counts_wherever_it_sits_on_the_line` for
   re-pinning, but this one needs the same treatment for the same reason.
3. **`_unread_detail`, the shared test helper in
   `test_gate_findings_shapes.py:421`** (`f"line {n}: {_UNREAD}{line...}"`)
   is called by roughly twenty assertions across both test files, several
   of which feed it an emoji-led row with no consensus token (e.g.
   `- {CRIT} crash on empty input | src/a.py:3`, the near-variant rows at
   `test_gate_findings_shapes.py:956-957`, the templates at
   `test_gate_findings_unread_shapes.py:291/325/341` — NOT line 101: that
   site serves the mid-line/trailing-position templates, which under the
   new rule match no arm at all and return `ok`, not `malformed`; they are
   covered by the PRD-named re-pin of
   `test_every_severity_emoji_counts_wherever_it_sits_on_the_line`
   expecting `ok`, not by this helper). Under the new
   precedence rule those rows now refuse with the emoji wording, not
   `_UNREAD`, so every one of those call sites would otherwise need its own
   edit. **Fix `_unread_detail` itself instead of each call site**: branch
   on whether `line`, after lead-stripping, starts with a severity emoji,
   and emit the matching wording —
   ```python
   _EMOJI_UNREAD = "a severity emoji row the findings parser did not read: "

   def _unread_detail(text: str, line: str) -> str:
       from cli import gate
       n = text.splitlines().index(line) + 1
       prefix = _EMOJI_UNREAD if gate._is_emoji_row(line) else _UNREAD
       return f"line {n}: {prefix}{line.strip()[:120]}"
   ```
   This is a one-site fix: every existing call site keeps calling
   `_unread_detail(text, row)` unchanged and gets the right wording for
   whichever shape `row` is, including `_ALICE_ROW`
   (`- [1/3] 🔴 crash on empty input | ...`), which still gets the
   generic wording because its first remaining character after
   `_strip_lead` is `[`, not an emoji — the consensus-token arm of
   `_is_unread_line` still fires for it, unaffected by this change.

## Interfaces & contracts

### `cli/gate.py` — lead-normalised emoji rule

```python
import unicodedata

# Single-character lead tokens this rule strips, besides ASCII space/tab:
# ASCII bullets (-, *, +), blockquote (>), emphasis markers (*, _), and the
# typographic bullets below. Ordinals ("1.", "23)") are stripped by
# _ORDINAL_LEAD_RE, not this set, because they are multi-character.
_LEAD_MARK_RE = re.compile(r"[-*+_>•◦‣–—－]")
# No `^`: re's `^` anchors to the real string start even with `.match(line,
# i)`'s `pos` argument, which would silently stop this ever matching past
# index 0 (`re.compile(r"^\d+[.)]").match("  1. x", 2)` is None, checked) —
# an unanchored pattern plus `.match(line, i)` is what actually anchors the
# match at `i`.
_ORDINAL_LEAD_RE = re.compile(r"\d+[.)]")
_EMOJI_ROW_DETAIL = "a severity emoji row the findings parser did not read:"


def _strip_lead(line: str) -> str:
    """Strip `line`'s lead, repeatedly, in any combination: ASCII space/tab,
    every other Unicode category Zs or Cf code point (this is what covers a
    no-break space (Zs), a zero-width space (Cf), and a BOM/bidi-control
    character (also Cf, stripped on purpose — a reviewer's editor can leave
    one behind invisibly) with no per-character allowlist beyond the two
    ASCII whitespace bytes, since `unicodedata.category("\\t")` is `Cc`, not
    Zs/Cf, and must be checked explicitly), ASCII bullets (-, *, +),
    blockquote (>), ordinals (\\d+[.)]), typographic bullets (•, ◦, ‣, –, —,
    －), and emphasis markers (*, _). Stops at the first character none of
    these consume. Returns the remainder, which may be empty."""
    i, n = 0, len(line)
    while i < n:
        ch = line[i]
        if ch in " \t" or unicodedata.category(ch) in ("Zs", "Cf"):
            i += 1
            continue
        if _LEAD_MARK_RE.match(ch):
            i += 1
            continue
        m = _ORDINAL_LEAD_RE.match(line, i)
        if m:
            i = m.end()
            continue
        break
    return line[i:]


def _is_emoji_row(line: str) -> bool:
    """True when the first character remaining after `_strip_lead` is a
    severity emoji — a finding row regardless of what the lead looked
    like. An emoji that is not the first remaining character (prose that
    mentions one after other text) is never a row."""
    stripped = _strip_lead(line)
    return bool(stripped) and stripped[0] in _SEVERITY_EMOJI
```

`_SEVERITY_EMOJI` is the existing import from `findings_section.py`
(`{"🔴": "critical", "🟠": "high", "🟡": "medium", "⚪": "low"}`); no change to
that table.

`_is_unread_line`'s bullet-lead arm —

```python
(_BULLET_LEAD_RE.match(line) and _SEVERITY_EMOJI_ANY_RE.search(line))
```

— is **deleted** (not deprecated-but-kept): `_is_emoji_row` fully replaces its
job and is checked separately in `_unread_token` (below), not folded back
into `_is_unread_line`, because it needs its own detail wording.
`_BULLET_LEAD_RE` and `_SEVERITY_EMOJI_ANY_RE` stay defined — both are still
used elsewhere (`_SEVERITY_EMOJI_WORD_RE` is built from
`_SEVERITY_EMOJI_ANY_RE.pattern`; grep both names before deleting either to
confirm no other caller breaks).

`_unread_token`'s per-line loop gains an emoji-row check ahead of the
existing `_is_unread_line` check, so the two detail wordings stay distinct
test-pinned strings (`[m/n] or table row ...` vs `severity emoji row ...`):

```python
for i, line in enumerate(lines):
    if i in consumed:
        continue
    if _is_emoji_row(line):
        return f"line {i + 1}: {_EMOJI_ROW_DETAIL} {line.strip()[:120]}"
    if _is_unread_line(line):
        return (
            f"line {i + 1}: a [m/n] token or table row the findings parser "
            f"did not read: {line.strip()[:120]}"
        )
return None
```

The `consumed` set (rows the table/bullet parser already read) is computed
exactly as today — an emoji inside a `- [2/3] 🔴 ...` consumed finding row is
never re-flagged, because that line index is already in `consumed` and the
loop `continue`s past it before either check runs.

**Precedence rule, pinned explicitly**: for any *unconsumed* line, the
emoji-row check always wins when it matches, even if the same line would
also match `_is_unread_line`'s other arms (e.g. a line that is both
emoji-led and happens to contain a `[m/n]` token elsewhere). The emoji
detail is reported in that case, never the generic `[m/n]` detail. Add
`test_refusal_names_the_matched_emoji` against a line built to trigger both,
asserting the literal expected string directly (not by calling
`_unread_detail`/`gate._is_emoji_row` to build the expectation) — the
dispatch-3 verification pass flagged that deriving the expected wording
from the same code path under test would make the assertion circular.

### `cli/gate.py` — CommonMark fence rule

Replace the single `_FENCE_RE` regex with two matchers, same names (`run`)
and same call sites (`_unfenced`, `_fenced_findings_header`):

```python
_FENCE_RUN_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_FENCE_CLOSE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})[ \t]*$")


def _fence_open(line: str) -> str | None:
    """The fence run (e.g. "```" or "~~~~") that opens on `line`, or None.
    A backtick run's info string must not itself contain a backtick
    (CommonMark); a tilde run's info string is unrestricted — it may
    contain backticks or tildes."""
    m = _FENCE_RUN_RE.match(line)
    if m is None:
        return None
    run, info = m.group(1), m.group(2)
    if run[0] == "`" and "`" in info:
        return None
    return run


def _fence_close(line: str, run: str) -> bool:
    """True when `line` closes a fence opened with `run`: the same
    character, a run at least as long, and nothing but trailing
    whitespace after it (a closer followed by non-whitespace does not
    close, for both backtick and tilde fences)."""
    m = _FENCE_CLOSE_RE.match(line)
    return m is not None and m.group(1)[0] == run[0] and len(m.group(1)) >= len(run)
```

`_unfenced` and `_fenced_findings_header` call `_fence_open(lines[i])` where
they currently call `_FENCE_RE.match(lines[i])` (using the returned `run`
string directly instead of `opener.group(1)`), and `_fence_close(lines[j],
run)` where they currently call `_FENCE_RE.match(lines[j])` plus their own ad
hoc comparison (`closer.group(1).startswith(run)` in `_unfenced`;
`closer.group(1)[0] == run[0] and len(...) >= len(run)` in
`_fenced_findings_header`). For a single-character run these two existing
comparisons already agree (a 4-backtick closer's group starts with any
shorter all-backtick run, same as same-char-and-longer), so neither call
site had a closer-matching bug; the real, and only, change at both call
sites is the two new CommonMark rules `_fence_open`/`_fence_close` add — the
backtick info-string check and the closer's trailing-whitespace-only check,
neither of which the old `_FENCE_RE` (a bare opener-run regex with no
info-string or closer-content check at all) could express. `_FENCE_RE`
itself is deleted; both call sites move to the new names.

Two stale-comment sites a task implementor must also update, named by the
cross-model review: `_unfenced`'s own docstring (`gate.py:402-404`, "through
`_FENCE_RE`" and "a closer is a run ... (trailing text allowed)") and the
old `_FENCE_RE` comment itself (`gate.py:205`, trailing-text-allowed note) —
both describe the rule this PRD reverses and must not survive as dead
documentation beside the new functions.

## Data flow

`findings_verdict()` → `_cross_check_findings()` → `_unfenced(text)` (blanks
closed-fence bodies using `_fence_open`/`_fence_close`) → `_reviewed_keys(live)`
reads the table/bullet rows from the fence-blanked text → `_malformed_detail`
calls `_fenced_findings_header(text)` (raw, unblanked text — it must see the
fence markers to find a hidden header) then `_unread_token(live)` (the
fence-blanked text — a pseudo-fence that fails to open per the new rule is
therefore NOT blanked, so its guarded row surfaces to `_unread_token` as an
ordinary unread line and the whole call refuses `findings_malformed`, closing
packet 6). No change to the function signatures or the call graph; only the
fence-matching primitive underneath `_unfenced`/`_fenced_findings_header`
changes, and the one new per-line check inside `_unread_token`.

## Reuse inventory

- `_SEVERITY_EMOJI` (`cli/findings_section.py:38`) — reused as-is for the
  emoji-row first-character test; no new emoji table.
- `_FENCE_RE`'s two call sites (`_unfenced`, `_fenced_findings_header`) —
  reused as the integration points for `_fence_open`/`_fence_close`; no new
  fence-walking loop structure (both already walk `i`/`j` over
  `lines`/`text.splitlines()`, which does not change).
- Greps tried before concluding no existing lead-stripping helper exists:
  `rg -n "def _strip" skills/run-autopilot/cli/`,
  `rg -n "lstrip|strip_lead|strip_bullet" skills/run-autopilot/cli/gate.py
  skills/run-autopilot/cli/findings_section.py`,
  `rg -n "unicodedata" skills/run-autopilot/cli/` — all empty; confirmed the
  search itself works by re-running `rg -n "_BULLET_LEAD_RE"
  skills/run-autopilot/cli/gate.py`, which does hit. Nothing found: this is
  new code.

## Alternatives considered

1. **Extend `_BULLET_LEAD_RE` with more lead alternatives** (add
   `•|◦|‣|–|—|－` and invisible-space characters to the existing anchored
   regex, keep `_SEVERITY_EMOJI_ANY_RE.search` unanchored). Smallest diff.
   Rejected: `_SEVERITY_EMOJI_ANY_RE.search` is unanchored by design (`.search`,
   not `.match`), so it still matches an emoji anywhere on the line —
   including after real prose following the bullet (`- some **bold 🔴 word**
   note`), which is exactly packet 5's false-refusal shape with a bullet
   added. A regex-only fix cannot express "first character after an
   arbitrary, possibly-invisible lead" without effectively building the
   strip loop anyway, so this alternative does not actually solve packet 5.
2. **A single compiled regex covering all lead shapes plus the emoji**
   (`^[ \t​ ...]*(?:[-*+>]|\d+[.)]|[•◦‣–—－]|[*_])*[🔴🟠🟡⚪]`,
   repeated via `*` instead of a Python loop). Rejected as the chosen
   design's riskier twin: Python's `re` has no `\p{Zs}`/`\p{Cf}` classes, so
   covering "every Unicode Cf code point and every Zs space" in one pattern
   means hand-enumerating code points instead of asking `unicodedata` for
   the category — hand-enumerating is what the PRD's "every ... code point"
   wording is written to rule out. (`unicodedata.category` is tied to the
   interpreter's own Unicode database version, so the gain over a hand list
   is real but not unlimited; nothing here depends on it tracking a future
   Unicode version precisely.) One side effect worth naming rather than
   hiding: a blanket Cf strip also consumes a BOM (U+FEFF) and bidi-control
   characters, not just the zero-width space the PRD names — intended,
   since any of them could hide a lead invisibly, but a task implementor
   should know it's deliberate, not an accident of the category choice.
3. **Chosen: `_strip_lead` as an explicit per-character strip loop**, tested
   directly as its own function (so the eleven new tests can assert on the
   stripped remainder as well as on `_is_emoji_row`'s boolean), plus
   `_fence_open`/`_fence_close` replacing the single fence regex. This is
   larger than alternative 1 by about 30 lines, which buys: correct
   "first-character-only" emoji semantics (closes packet 5 for real), a
   `unicodedata`-driven Zs/Cf match that needs no enumeration (closes packet
   4's invisible-space cases without a hardcoded character list), and a
   CommonMark-correct fence pair — the gain there is the backtick
   info-string check and the closer's trailing-whitespace-only check, not a
   closer-length fix (both existing call sites already agreed on closer
   length/char; see the CommonMark fence rule section above).

## Risks & edge cases

- **Likely next change 1**: a reviewer format that puts a severity emoji
  inside a table cell's free-text comment column rather than a bullet lead
  (e.g. `| ... | Comment: saw a 🔴 once | ...`). The new rule only looks at
  the start of a *line*, not inside an already-consumed table data row's
  cells, so this stays correctly unread as a prose cell — no change needed,
  but worth naming because a future PRD may ask the gate to inspect cell
  content too.
- **Likely next change 2**: a reviewer indenting a finding row inside a
  blockquote used as a callout (`> - 🔴 crash`, blockquote-wrapping an
  otherwise normal bullet row). `_strip_lead` already strips `>` then the
  ASCII bullet `-` in the same pass (both are in the stripped set), so this
  shape is already caught by this PRD's rule; flagged here only so a future
  reader does not assume it needs separate handling.
- **Likely next change 3**: nested fences (a fenced block containing its own
  fenced block using a different character/longer run). `_fence_open`/
  `_fence_close` keep the existing single-open/single-close walk (no stack);
  CommonMark itself does not nest same-style fences either, so this is
  consistent with upstream behavior, not a gap this PRD introduces.
- **Edge case, new under this rule**: a backtick opener whose info string
  contains a backtick no longer opens at all (by design), so the scan moves
  past it looking for the NEXT line that opens. If a later line opens an
  honest fence (say a bare ` ``` `) and only after that comes the ` ``` `
  that would have closed the pseudo-fence, the span between that later
  opener and its own closer is blanked exactly as any real fenced block
  would be — this can blank MORE of the file than the old single-regex
  fence did in the same input, not less. This is the intended effect for
  packet 6 (the row the pseudo-fence hid becomes visible, because it now
  sits before any real opener), but a task implementor should add one test
  where a real row sits between a non-opening pseudo-fence line and a real
  fence pair further down, confirming that row stays visible and nothing
  past the real fence pair is wrongly blanked.
- **Edge case**: a lead that is *only* whitespace/markers with nothing after
  it (a line that is just `- ` or just `>`) — `_strip_lead` returns `""`;
  `_is_emoji_row` returns `False` via its `bool(stripped)` guard, so an
  empty remainder is never mistaken for "starts with nothing, therefore
  matches". Pin this as a boundary case in the new tests if `rg` on the real
  fixtures ever surfaces one (it does not need its own named test per the
  PRD's task list, but the guard must stay).
- **Accepted narrowing, flagged by the cross-model review**: the OLD arm
  (`_BULLET_LEAD_RE.match and _SEVERITY_EMOJI_ANY_RE.search`, unanchored)
  caught `- [BLAKE] 🔴 crash`, `- R1 🔴 crash`, and `- **Bob:** 🔴 crash` —
  any ASCII-bulleted line containing an emoji ANYWHERE — which is exactly
  the over-broad behavior packet 5 says must stop. Under the new rule none
  of these three is a row: after `_strip_lead` removes the bullet and
  space, the next character is `[`, `R`, or `*`, not the emoji, so each is
  prose by the PRD's own "first remaining character" rule. This is a
  deliberate consequence of the PRD's stated fix, not a bug in this design
  — but it is a real narrowing of what the gate catches relative to today,
  in a PRD titled "catch critical rows in every shape", so it is named here
  rather than discovered later. No task should "fix" this by special-casing
  `[...]`/`R\d+`/`**Name:**` leads; that would reopen packet 5.
- **Edge case**: `_ORDINAL_LEAD_RE` eating a 4-digit year (`2026.`) as if it
  were an ordinal list marker. This is deliberate, not a bug: after
  stripping `2026.` the next character is whatever follows (a space, then a
  letter for real prose), so the row only becomes a finding when an emoji
  is *literally the next character after the stripped year* — a shape no
  real review file produces. The PRD's `test_ordinal_year_prose_is_read`
  pins exactly this.

## Test strategy outline

- `test_gate_findings_unread_shapes.py`: re-pin
  `test_every_severity_emoji_counts_wherever_it_sits_on_the_line` to
  `test_every_severity_emoji_counts_as_the_first_character_after_the_lead`
  (mid-line/trailing-position templates move to the new prose tests, since
  under the new rule an emoji NOT at the first position is prose by
  definition). Add the eleven tests the PRD's Module section names,
  parametrizing the typographic-bullet test over `•`, `◦`, `‣`, `–`, `—`,
  `－` and the invisible-lead test over zero-width space (`​`) and
  no-break space (` `). Each fence test (`test_backtick_in_info_string_
  is_not_a_fence`, `test_closer_with_trailing_text_does_not_close`) asserts
  through `_unfenced`'s observable behavior (a line inside the would-be
  fence stays live/is blanked) rather than calling the private matchers
  directly, matching the file's existing style of testing `_unfenced`
  end-to-end.
- `test_gate_findings_real_fixtures.py`: re-run the full replay over every
  real review file under the new rule (the harness this file already runs),
  diff the new flip set against `_ACCEPTED_FLIPS`, and for every path that
  newly joins, read the `_unread_token`/`_fenced_findings_header` refusal
  the gate now produces for it and confirm the named line starts with a
  severity emoji after `_strip_lead` — quoting that line in a comment beside
  the entry, per the PRD's join rule. The four bold-lead paths named in the
  Problem section (00188 review-2, 00207 review-01, 00244 review-1, 00256
  review-2) must come OUT of the list (they now read as prose, exit 0).
  `_ACCEPTED_FLIPS`' own header comment (`test_gate_findings_real_fixtures.py:
  173-178`) still describes the OLD rule being deleted ("widened to flag a
  bullet- or ordinal-led line carrying a bare severity emoji anywhere on
  it") — rewrite it to describe the lead-normalised rule as part of this
  same re-baseline task, not left stale beside the new list.
- `test_gate_findings_shapes.py` needs the two fixes in "Existing-test
  impact" above (the `_unread_detail` helper, the closer re-pin); apply both
  there rather than editing each affected assertion. `test_gate.py` runs
  unchanged as a regression backstop — no test deleted, per the Phase 1
  acceptance line.

## Review log

dispatch 1 (claude): cardinal-sin 0, blocker 2, non-blocker 3, question 1
- Blocker fixed: `_ORDINAL_LEAD_RE` was anchored with `^`, which (per Python's
  `re` semantics) never matches past index 0 even via `.match(line, i)`'s
  `pos` argument — an indented ordinal (`  1. 🔴 x`) would never be stripped.
  Removed the anchor.
- Blocker fixed: tabs (`unicodedata.category("\t") == "Cc"`, not Zs/Cf) were
  never stripped by the lead loop, regressing the existing `\t- 🔴 x` case
  `_BULLET_LEAD_RE`'s `[ \t]*` covers today. Added an explicit `ch in " \t"`
  check.
- Non-blocker: the `_unfenced`/`_fenced_findings_header` prose wrongly
  described the existing `startswith` closer comparison as buggy; corrected
  to say the real (and only) change is the new info-string/trailing-text
  rules, not a closer-length fix.
- Non-blocker: a pseudo-opener that fails to open now lets the scan reach a
  later real fence pair, which can blank a wider span than the old
  single-regex fence did on the same input (intended for packet 6, but
  worth a named test); added as a Risks bullet.
- Non-blocker: softened the Unicode-proofing claim in Alternative 2 and
  named the BOM/bidi-control side effect of a blanket Cf strip explicitly.
- Question answered: pinned the precedence rule for a line that could match
  both the emoji-row check and `_is_unread_line`'s other arms — the emoji
  detail always wins — as its own paragraph plus a named test.

dispatch 2 (claude-fallback): cardinal-sin 0, blocker 3, non-blocker 4, question 1
- codex-run.sh completed (exit 0) but its sandboxed session was blocked by
  its own repo-local fact-forcing hook before it ever read a file and never
  produced a findings summary line — unparseable per the skill's codex
  fallback rule. Degraded to a fresh Claude reviewer subagent for this
  dispatch.
- Blocker fixed: `test_gate_findings_shapes.py:618`'s
  `test_a_closer_with_trailing_text_still_closes_the_fence` pins the OLD
  closer rule (trailing text still closes); under the new rule it does not,
  so the row inside stays live and the verdict flips to malformed. Added to
  Module placement's re-pin list with the exact fix.
- Blocker fixed: `test_gate_findings_unread_shapes.py:67`'s
  `test_a_severity_emoji_alone_makes_an_unread_line_a_finding` asserts
  `_is_unread_line(row) is True` directly for emoji rows — an arm this PRD
  deletes from `_is_unread_line` entirely. The PRD's Module section named
  only the OTHER test for re-pinning; this second one needed the same
  treatment and was missing from both the PRD's list and this doc. Added.
- Blocker fixed: roughly twenty assertions across both test files route
  through the shared `_unread_detail` test helper, which hard-codes the
  generic `_UNREAD` wording; several feed it an emoji-led row with no
  consensus token, which now refuses with the emoji wording instead. Fixed
  at the single helper definition (branches on `gate._is_emoji_row`) rather
  than naming all twenty call sites individually — every existing call site
  keeps working unedited.
- Non-blocker: named the accepted narrowing where a bracket/attribution/
  bold-name-prefixed emoji row (`- [BLAKE] 🔴 crash`, `- R1 🔴 crash`,
  `- **Bob:** 🔴 crash`) that the OLD unanchored-search arm caught now reads
  as prose, per the PRD's own "first remaining character" rule — added as a
  Risks bullet, explicitly not to be "fixed" by a task (that would reopen
  packet 5).
- Non-blocker: Alternative 3's closing sentence still described the fence
  gain as fixing a closer-length bug that dispatch 1 had already shown does
  not exist; reworded to match the corrected Interfaces text.
- Non-blocker: "two existing files" in Module placement undercounted;
  corrected to name all four files actually touched.
- Non-blocker: two in-code comments (`_unfenced`'s docstring, the old
  `_FENCE_RE` comment) describe the rule this PRD reverses and would go
  stale; named as an implementor note beside the fence contract.
- Question: whether an emoji-led summary/label line with no bullet at all
  (e.g. a bare `🔴 Critical (0)` heading-less line) should be named
  separately in Risks beyond the existing `_ACCEPTED_FLIPS` join-rule
  coverage — left as-is: the join rule (a flip is accepted only when the
  named refusal line starts with a severity emoji after lead-normalisation)
  already covers this exact shape with no special-casing needed, so no doc
  change.

dispatch 3 (claude-fallback): cardinal-sin 0, blocker 0, non-blocker 2, question 1
- Verification dispatch (runs because dispatch 2 found blockers).
- codex-run.sh completed (exit 0) again but hit the identical sandbox-init
  failure as dispatch 2 (its own PreToolUse fact-forcing hook blocked its
  first command, then every shell read failed) — a persistent environmental
  outage in this run, not content-specific. Degraded to a fresh Claude
  verification subagent per the skill's codex fallback rule.
- Verified all three dispatch-2 fixes hold: the `_unread_detail` one-site
  fix produces the right wording at every one of 21 checked call sites
  (rows starting with `[`, `(`, `［`, `<`, `|`, or a bare ratio keep the
  generic wording; rows starting with an emoji get the emoji wording); the
  closer re-pin lands on the correct new verdict; the emoji-alone re-pin
  works against the real `_EMOJI_SHAPES` values. Confirmed `_is_unread_line`
  has exactly one non-test call site (`gate.py:487`, inside `_unread_token`
  itself, already replaced by the new loop) and no other test file
  references `_BULLET_LEAD_RE`/`_FENCE_RE`.
- Non-blocker fixed: line 101 of the unread-shapes file was wrongly listed
  as a site the `_unread_detail` fix covers — it serves mid-line/trailing
  templates that return `ok` under the new rule, not `malformed`; removed
  from that list and attributed to the PRD-named re-pin instead.
- Non-blocker fixed: `test_refusal_names_the_matched_emoji` (added by
  dispatch 1) is now specified to assert the literal expected string rather
  than deriving it from `_unread_detail`/`_is_emoji_row`, avoiding a
  circular assertion.
- Question answered, fixed: `_ACCEPTED_FLIPS`' header comment in
  `test_gate_findings_real_fixtures.py` describes the old rule; added to
  the re-baseline task's scope in Test strategy outline.

result: ok
