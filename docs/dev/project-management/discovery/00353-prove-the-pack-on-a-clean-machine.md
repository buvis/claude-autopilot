# Discovery: Prove the pack on a clean machine

## Classification
Depth: comprehensive | Date: 2026-10-18 | Status: pre-elicitation (written from the release-readiness review, no questions asked yet)

## Problem
Nothing proves the pack works outside the author's Mac. The repo has no CI
(`.github/` absent, 0 workflow runs per the project capsule), the gate takes
15 to 25 minutes and 7,176 tests, and every batch ever run went through the
author's seatbelt, hooks and credentials. The shipped prose assumes that
environment:

| Dependency | Where the pack assumes it | What a stranger gets |
|---|---|---|
| codex CLI with the author's config | Bob (`agents/bob.md`, `use-codex`) | no Bob; the lane logs `error` and the item still converges on four lenses |
| gemini or copilot CLI with a personal PAT | Carl (`agents/carl.md`, `use-gemini`) | no Carl |
| engram | catchup and the review context pack | `(no pack available this cycle)` sentinel, catchup timeouts |
| warden, aegis, loupe, ponytail | named in `skills/run-autopilot/SKILL.md` (19 mentions), `skills/run-autopilot/scripts/README.md` (14), `review-work-completion/SKILL.md` (5), `review-blindly/SKILL.md` (5) and 20 more files | prose that names hooks the user does not have |
| `run-agent` seatbelt, `caffeinate`, macOS `ps` semantics | the `autoclaude` wrapper, `cli/loop.py` orphan sweep | Linux users have no wrapper |
| the fast-track skill | its frontmatter: "Requires Bob personal Claude/autoclaude environment or equivalent host adapters" | a skill that declares itself author-only |
| README | no requirements section; "What intentionally stays out" still says the `autoclaude` wrapper lives in the author's dotfiles although the loop driver moved into `cli/__main__.py loop` | an install path that stops at `/plugin install` |

The README promises "three independent review lenses" and the fast-track
roster is five; in batch 202610161547 Bob was missing on every fast-track
card, so the promise was not met even here. This is gate 2 of the
public-release bar.

## Requirements (candidate, to be elicited)

### Must have
- F1: a CI workflow on a plain Linux runner that runs `dev/bin/release-checks`
  on every push to master and on pull requests, with the skip ceiling
  honoured; a red gate blocks `dev/bin/release` (the shim already refuses on a
  critical stub; a failed CI run is the same shape).
- F2: a documented Claude-only roster: with no codex, gemini or engram
  installed, a PRD still converges through Alice, Blake, Eve and Victor, and
  the review file names the missing lanes as absent by configuration, not as
  failures.
- F3: a README requirements section: Claude Code version, Python 3.11, `uv`,
  `rg`, `jq`, optional codex, gemini, engram, the loop driver command for
  macOS and Linux, and what degrades without each optional piece.
- F4: the shipped prose stops naming the author's personal hooks and tools;
  where a behaviour depends on them it is phrased as "when a hook blocks X"
  and the fast-track frontmatter drops the author-only compatibility line or
  states the real requirement.

### Nice to have
- A one-PRD smoke batch in CI on a toy repo, Claude-only, asserting the
  review file and the done move.

### Out of scope
- Supporting Windows; replacing the seatbelt (a user choice, not the pack's).

## Constraints
- CI needs an Anthropic API key or OAuth in secrets only for the smoke
  batch; the gate itself runs without network (the two live tests skip).
- The gate's duration (15 to 25 min) sets the CI budget; parallel blocks
  already exist (`-n auto`).

## Codebase Context
- `dev/bin/release-checks` (the gate), `dev/bin/release` (the shim that
  refuses on a critical stub).
- `skills/review-work-completion/SKILL.md` step 5 Bob fallback (exit 3
  dispatches a Claude subagent with Bob's prompt) and
  `references/retry-policy.md`: the Claude-only roster partly exists for Bob;
  Carl has no fallback.
- `skills/fast-track/SKILL.md` frontmatter and roster section.
- `README.md` sections "What's inside", "What intentionally stays out",
  "Install".

## Approach (candidate)
CI first (it is the cheapest proof and the one that exists nowhere), then the
roster semantics, then the prose sweep.

## Success Criteria (candidate)
- A green CI run on a runner that has no codex, gemini, engram, warden, aegis
  or loupe.
- A PRD run with those tools absent converges with a review file whose roster
  line reads `bob: absent (not installed)`, `carl: absent (not installed)`.
- `rg -c "warden|aegis|loupe|ponytail|run-agent" skills/*/SKILL.md` prints 0.

## Risks
- The gate has one three-minute-a-day flaky test (PRD 00349) and a root-only
  skip; CI will find more environment-bound tests.
- Removing tool names from prose can delete real guidance; each mention
  needs a reader to decide.

## Open Questions
- Is a Claude-only convergence acceptable as a product promise, or must the
  README say "three lenses need codex and gemini"?
- Which CI provider, and does the smoke batch justify an API secret in CI?
- Does the loop driver need a Linux wrapper, or is `python3 cli/__main__.py
  loop` the documented entry point everywhere?

## Discovery Log

### Inferred (not asked)
- Counts from `rg -c "warden|aegis|run-agent|engram|ponytail|loupe|autoclaude"
  skills/ README.md --glob '*.md'` on 2026-10-18 at commit 016796b.
