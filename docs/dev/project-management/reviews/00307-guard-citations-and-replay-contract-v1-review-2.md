---
prd: docs/dev/project-management/prds/wip/00307-guard-citations-and-replay-contract-v1.md
review: 2
date: 2026-10-15
head_sha: d0a8163ad77add3d9a8961eab5e9dec8df0a888b
codex_thread_id: 01a13de8-b55d-7832-9987-23e6175c57ce
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available (after one retry, inlined)
  carl: available
dispatch_rows:
  bob: d32caddc (lack-of-input), 347c7ec5 (retry, ok)
  carl: 6dd88eff
---

# Review: 00307-guard-citations-and-replay-contract-v1

Diff range: `f7e282223f55f8a891a5733f61f6715f21b06d93..d0a8163ad77add3d9a8961eab5e9dec8df0a888b` (incremental: cycle-1 rework only)

codex_rung_guard: not fired

## Review Summary

Reviewed: 9 completed tasks (cycle-1 rework)
PRDs checked: 00307-guard-citations-and-replay-contract-v1

### Agent Status

- alice: ran (legacy consensus engine)
- blake: ran (blind, PRD-only)
- bob: ran on the retry. The first codex dispatch returned a lack-of-input refusal (the path-referenced context and diff were never opened); the retry inlined the context and the full diff into one prompt file and produced a usable review. Recorded as `after one retry (inlined)`.
- carl: ran on the copilot backend; no issues found.

### Degradations and notes (fail loud)

- engram context pack: `failed (engram pack exit 1: sqlite3.OperationalError: attempt to write a readonly database)`. Every prompt carried `(no pack available this cycle)`. The review is degraded in precedent context, not in lenses.
- One phrase in Alice's R13 finding was reworded when saving her output: the literal per-line linter-suppression marker she quoted is blocked by aegis `block_suppression_markers.py`, so the saved text says "no per-line linter-suppression comment". No finding content changed.
- `Tests:` line reused from `last-verification.json` at `6d963d4`. HEAD is `d0a8163`; the three commits in between (`dd15e1c`, `9462669`, `d0a8163`) are autopilot store-record commits only and touch no code. Carl independently ran `dev/bin/release-checks` at `d0a8163` this cycle with no failure.

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [2/4] | 🟡 | The `[^(\s`]` backtick exclusion in `_CITE_SENTENCE_BOUNDARY` has no test that can fail. Mutating the lexicon to the bare `[^(\s]` left the citations, corpus, structure, linearity and narrowing suites green. The matching multi-backtick citation test was dropped in task 4 with the note that task 7 would handle it; task 7 did not re-add it, and the assumptions ledger does not say the shape was closed. The shape is still a false refusal: a doubled-backtick citation is denied because the field-wide pairing in `_quoted_runs` pairs the doubled backticks with each other. Either pin the regex fix with a prompt where the window change flips the verdict, or record the multi-backtick refusal as an accepted gap. | hooks/guard_phase_delegation_lexicon.py:219 | 4 | ALICE, BOB |
| R2 | [1/4] | 🟠 | Spec names `test_six_corpus_dispatches_are_allowed` (six prompts copied verbatim into one test), but no test has that name. The substitute `test_every_recorded_corpus_dispatch_is_allowed` pins only 2 of the 6 ids (toolu_011UqbqFtUDPuSeCiLLgMvEg, toolu_013ePUKbLDE7DLnbnGmgszzR). The other four are recorded as unrecoverable in the file's comment block; hold stub 00294 carries only ids and quoted spans, not prompts, so "copy verbatim from the stub" could not be done as written. The unrecoverable shapes are covered only by synthetic tests. The deviation is disclosed in the test comment, but the spec's named symbol and its "six ids allowed" must-have are only partly pinned. | hooks/test_guard_phase_delegation_corpus.py:35 | 1 | BLAKE |
| R3 | [1/4] | 🟠 | The own-wrapper branch bypasses validated pairing: `The log says 5"plan-tasks for PRD 00300 and print "ok".` is excused despite the digit-preceded quote being rejected by `_quoted_runs`. Route symmetric wrappers through the validated run map, including openers at `start`, and add this regression. | hooks/guard_phase_delegation.py:566 | 7 | BOB |
| R4 | [1/4] | 🟡 | `test_period_inside_a_dotted_identifier_does_not_end_the_citation_sentence` is tautological: it passes against the pre-rework guard (f7e2822), because its prompt has no strong anchor and `cli/frontmatter.parse` reads as a path, which scopes the field. The test cannot fail if `_CITE_SENTENCE_BOUNDARY` regresses for the dotted-identifier shape. Only the recorded-corpus test pins it. Replacement: drop the `cli/` path and add a strong anchor. | hooks/test_guard_phase_delegation_citations.py:187 | 5 | ALICE |
| R5 | [1/4] | 🟡 | The design mandates a test recording the accepted fail-open as deliberate (`test_a_backtick_citation_followed_by_a_parenthetical_is_allowed`). It is absent, and the residual is real: two backtick-citation-plus-parenthetical shapes flip from refused on master to allowed under the new boundary, and the assumptions ledger's fail-open paragraph does not mention them. Add the pin and name the balanced-run scanner as the tightening path. | hooks/test_guard_phase_delegation_citations.py:197 | 5 | ALICE |
| R6 | [1/4] | 🟡 | The citation rule differs from the spec's wording (clause-scoped in the spec, sentence-bounded plus field-wide pairing in the implementation, wired into `_field_delegation` rather than `_candidates`). Clause scope would fail the spec's own corpus spans, so the sentence window is defensible, but the design-doc amendment recording it was not found. | hooks/guard_phase_delegation.py:550 | 2 | BLAKE |
| R7 | [1/4] | 🟡 | Scope growth beyond the PRD's named symbols: `_quoted_runs`, `_delim_positions`, `_mark_in`, `_mark_before`, `_CITE_SENTENCE_BOUNDARY`, `_SYMMETRIC_DELIMS`, `_WRAP_SCAN_PAIRS`/`_WRAP_SCAN_CHARS`, the new `hooks/guard_phase_delegation_lexicon.py` module, a new corpus test file, count-based linearity tests and two extra CHANGELOG entries. The spec lists only `_cited` and `_AGOGE_PERSONAS` as new symbols and one CHANGELOG entry. | hooks/guard_phase_delegation_lexicon.py:1 | 2 | BLAKE |
| R8 | [1/4] | 🟡 | Accepted fail-open surface, now larger because of the field-wide pairing: a dispatch that wraps a whole order in quotes, backticks or parens is allowed (probed: a parenthesised whole order and a double-quoted whole order both return None), while unclosed and tightly closed tails are still refused. Recorded as accepted in e6b44e3. | hooks/guard_phase_delegation.py:550 | general | BLAKE |
| R9 | [1/4] | 🟡 | The multi-backtick regression deferred from task 4 remains unresolved: pairing individual backticks creates empty pairs around double-backtick citations, leaving the enclosed phase uncited. Pair backtick runs by delimiter width and restore the deferred test. | hooks/guard_phase_delegation.py:329 | 7 | BOB |
| R10 | [1/4] | 🟡 | R13 remains unpinned: the replacement fixture still closes its backtick after `next task`, whereas the recorded span closes immediately after `/autopilot:work`. Preserve that known delimiter placement in the narrative regression and retain the standalone-label denial control. | hooks/test_guard_phase_delegation_citations.py:89 | 9 | BOB |
| R11 | [1/4] | 🟡 | Simplify the corpus test: `_find` rebuilds the complete `tool_input` dictionary already held by each fixture. Remove this single-caller adapter and pass the fixture dictionary directly to `find_phase_delegation`. | hooks/test_guard_phase_delegation_corpus.py:19 | 5 | BOB |
| R12 | [1/4] | ⚪ | `_field_delegation` is now exactly 50 lines, at the limit; the two window lookups could move into a small helper over `cite_sentences`. | hooks/guard_phase_delegation.py:594 | 4 | ALICE |
| R13 | [1/4] | ⚪ | `_AGOGE_PREFIX`, `_MASKED_IN_SPAN` and several other names are re-imported into `guard_phase_delegation.py` only so tests and the replay can reach them as `guard_phase_delegation.<name>`. A linter reports them as unused imports (F401); the module comment explains the intent, but there is no `__all__` and no per-line linter-suppression comment. | hooks/guard_phase_delegation.py:39 | 7 | ALICE |
| R14 | [1/4] | ⚪ | `bucket()` in the replay script still classifies any `agoge:`-prefixed type as "agoge" via `_AGOGE_PREFIX`, while the guard now exempts only the 7-name roster. An unlisted `agoge:` persona is refused by the guard and reported as an agoge-bucket refusal, which fails the replay. Fails closed, consistent with the PRD's "visible failure". | dev/bin/replay_delegation_guard.py:58 | 3 | BLAKE |
| R15 | [1/4] | ⚪ | The accepted cross-script lookalike comment block is present and correct at `hooks/guard_phase_delegation.py:84-89`, but the spec's homoglyph literal is spelled as an escape rather than the spec's exact spelling. Cosmetic. | hooks/guard_phase_delegation.py:84 | 2 | BLAKE |
| R16 | [1/4] | ⚪ | Cannot statically verify: release checks and live replay on the reviewed revision. Run `dev/bin/release-checks` and `python3 dev/bin/replay_delegation_guard.py`; require both exit 0, `per-task ... refused 1`, and no pinned ID allowed. | N/A | general | BOB |
| R17 | [1/4] | 🟡 | 126 touched test(s) pass against the pre-change code: test_backtick_run_opening_before_the_name_is_a_citation, test_double_quote_run_is_a_citation, test_paren_aside_is_a_citation, test_a_run_closing_at_the_sentence_tail_cites_the_name_inside_it, test_wrapper_closing_right_after_the_name_still_counts +120 more. Expected for an incremental cycle: the "pre-change code" here is cycle-1's HEAD, where these cycle-1 tests already existed and passed. | hooks/test_guard_phase_delegation_citations.py | general | mech-check |

### Auto-dismissed (ledger)

No Blake finding matched a settled ledger entry this cycle.

Note on merging: `consolidate_findings.py` merged Bob's single-quote re-raise (`hooks/guard_phase_delegation_lexicon.py:40`) into R1 after suffix stripping. That re-raise is a cycle-1 REJECTED decision (single-quote citations deliberately excluded: contractions and possessives) and is not re-litigated; the surviving R1 text is Alice's distinct multi-backtick test-gap finding.

### Carried-forward checks

Cycle 1's queued check (`python3 dev/bin/replay_delegation_guard.py`) recorded `exit 0` at the settled HEAD, so nothing carried forward as a finding.

## Alice

Five findings (R1, R4, R5, R12, R13 above). Prior-cycle verification: R1, R4, R8 (replay exit and `refused 1`) resolved — `total 1186`, `per-task 756 refused 1` (only pinned `01Ku4T`), `reviewer 170 refused 0`, `agoge 49 refused 0`, `other 211 refused 6`, no failure reported. R2/R16 resolved with the recorded-payload caveat (2 recoverable payloads verbatim, 4 documented unrecoverable). R3, R6, R7, R13, R14 resolved; R12 deliberately not applied; R9/R10/R11 stand as accepted or documented. Adversarial probes all produced the correct verdict. 778 passed across the guard suites; functions at or under 50 lines; files 728/663/354/240, all under 800.

R1: fail
R2: fail
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: pass
R10: pass
R11: pass
R12: pass
R13: pass

## Blake

Six findings (R2, R6, R7, R8, R14, R15 above). Verified: 718 passed across the guard and replay test files; replay exits 0 with `per-task 756 refused 1`; the replay exit contract and its pinned-id exemption are covered; `_ordered_to_follow` uses `bisect_left` with no `next(`; `_AGOGE_PERSONAS` holds exactly the 7 names and near-misses are refused; the scratch-corpus test can now fail; the new citations test file is registered once in `dev/bin/release-checks:145` and the CHANGELOG entry sits once under `[Unreleased]`/Fixed.

B1: fail
B2: pass
B3: pass
B4: pass
B5: pass
B6: fail
B7: pass
B8: pass
B9: pass
B10: pass
B11: pass
B12: pass
B13: pass
B14: pass
B15: pass
B16: pass
B17: pass
B18: pass
B19: pass

## Bob

Doubt lens + de-slop, codex, after one retry (inlined). Five FIX findings (R3, R1-merged single-quote re-raise, R9, R10, R11) and one VERIFY (R16); KNOWN: none.

R1: fail
R2: fail
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: fail
R10: pass
R11: pass
R12: pass
R13: pass

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

No issues found. Ran the citations/corpus suites, the full guard and replay suites, `dev/bin/release-checks` and `python3 dev/bin/replay_delegation_guard.py`, and checked file sizes and debug markers.

R1: pass
R2: pass
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: pass
R10: pass
R11: pass
R12: pass
R13: pass

Verdict: 17 findings
Tests: 6827 passed, 0 failed, 34 skipped (reused from last-verification.json at 6d963d4)
