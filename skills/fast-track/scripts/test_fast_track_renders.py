"""Render pins for the fast-track driver skill (skills/fast-track/SKILL.md).

The prose pins next door ask whether the document tells a reader to do the right
thing. These ask whether the thing works when they do it. Every prompt this lane
sends is rendered by `render_prompt.py` from a fenced `bash` block, and that
script opens each path the block hands it: a flag pointed at a file no earlier
step wrote exits 4 in the operator's terminal, after the item has already spent
a dispatch and a commit, and a `cat` pointed at a file the item is about to
create fails the same way for the same reason. None of that shows up in a
reading of the document; all of it shows up in the flags.

So none of these pins greps. The blocks are parsed - flags, keys, values, and
the line each one sits on - by fast_track_render_testutil.py, which carries the
reasoning behind every vocabulary it uses. A document that rewords the sentences
around a broken flag still fails here, and one that deletes a pinned string
while keeping the defect fails harder.

What is pinned: every staged file a render opens is written by a step above it
and every placeholder its persona demands is filled, the implementor is handed
the card's constraints and AGENTS.md, the interface read opens only files that
are there and the item's planned targets are named apart from it, and the rework
dispatches the prompt its own render wrote, spec and all.

Each pin asks the persona what the block owes it, so deleting a flag fails
rather than passes, and reads every flag value the way the prose pins read a
sentence - a value written as English can name a thing in order to say it is
withheld, and a value the renderer drops (a `--require-file` guard, a key no
placeholder matches) never reaches the dispatch at all.

These pins live here rather than in test_fast_track_prose.py because that file
is at the project's file size limit. Same split as the vocabularies beside it.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _sibling(name: str) -> ModuleType:
    """A helper module read from beside this file, never from an install path.

    These scripts are not an installed package, so the reader model and the
    render parser come in by path, the way `card.py` does.
    """
    spec = importlib.util.spec_from_file_location(
        name,
        Path(__file__).with_name(f"{name}.py"),
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_testutil = _sibling("fast_track_prose_testutil")
_render = _sibling("fast_track_render_testutil")

_SKILL_MD = _testutil.SKILL_MD
_section = _testutil.section

_NO_RENDERS = (
    f"{_SKILL_MD}: no fenced `bash` block calls `render_prompt.py`. Every "
    "prompt this lane sends is rendered from a persona file, so a document "
    "with no render block dispatches nothing - and every pin below it passes "
    "by having nothing to read."
)


def test_every_render_block_has_every_input_it_needs_to_run() -> None:
    # `render_prompt.py` opens its `--set-file` paths and runs its `--set-cmd`
    # commands the moment the operator pastes the block, and exits 4 when one of
    # them is not there. Under `dev/local/tmp/` that is this document's own
    # doing: the lane stages those files itself, so a render reading one the
    # document never writes - or writes two sections down, which to a reader
    # working top to bottom is the same thing - cannot run. The placeholder is
    # the other half of that failure: the renderer exits 1 on the first
    # `{PLACEHOLDER}` no flag fills, so dropping a flag stops the dispatch
    # instead of quietening this pin. Read flags and personas, never prose.
    assert _render.renders(), _NO_RENDERS

    staged = [
        path for block in _render.renders() for _, path in _render.read_paths(block)
    ]
    personas = [
        block for block in _render.renders() if _render.persona_file(block) is not None
    ]

    assert staged, (
        f"{_SKILL_MD}: no render block reads anything the lane staged under "
        "`dev/local/tmp/`. The prompts are assembled from files this document "
        "writes, so a lane staging nothing sends its dispatches nothing - and a "
        "pin about writing before reading passes by having no read to check."
    )
    assert personas, (
        f"{_SKILL_MD}: every render block writes its persona as a placeholder "
        "for the operator to fill in, so which prompt a dispatch sends is "
        "nobody's decision on the page and no block owes a fixed set of keys."
    )

    unwritten = _render.unwritten_inputs()
    unfilled = _render.unfilled_placeholders()

    assert not unwritten, (
        f"{_SKILL_MD}: {len(unwritten)} render input(s) read before anything "
        f"writes them: {unwritten}. The operator pastes the block, "
        "`render_prompt.py` exits 4 on the missing file, and the item stalls "
        "with its earlier dispatches already paid for. Every path a block reads "
        "under `dev/local/tmp/` needs a step above it that puts the file there: "
        "a Write-tool staging line, or an earlier block's `--out`."
    )
    assert not unfilled, (
        f"{_SKILL_MD}: {len(unfilled)} render block(s) cannot fill the persona "
        f"they render: {unfilled}. The renderer exits 1 on the first "
        "placeholder no flag fills - the document says as much about the blind "
        "lane's three - so a dropped flag stops the dispatch in the operator's "
        "terminal rather than sending a thinner prompt. Every `{PLACEHOLDER}` "
        "the persona carries needs a `--set*` flag in the block rendering it."
    )


def test_the_implementor_render_hands_over_the_constraints_and_agents_md() -> None:
    # The implementor gets no acceptance criteria and nothing from the driver's
    # reading of the fix, so `ARCHITECTURE_CONTEXT` is the whole of what it
    # knows about the house it is building in. The card's `## Constraints` is
    # this item's half of that - standard library only, no new dependencies -
    # and `AGENTS.md` is the repo's half, which no card repeats. Handed only the
    # constraints, a fresh implementor writes code that passes the tests and
    # breaks every convention the repo has, and the review lanes spend the one
    # rework on it.
    blocks = [
        block for block in _render.renders() if _render.IVAN.search(block.persona)
    ]

    assert blocks, (
        f"{_SKILL_MD}: no render block fills `agents/ivan.md`. The implementor "
        "is the one dispatch that writes code, and a lane that never renders "
        "its prompt has nothing to send it."
    )

    starved = [
        f"line {block.line + 1} (`## {block.section}`): {complaint}"
        for block in blocks
        if (complaint := _render.context_complaint(block))
    ]

    assert not starved, (
        f"{_SKILL_MD}: the implementor's `ARCHITECTURE_CONTEXT` does not hand "
        f"over both the card's `## Constraints` and `AGENTS.md`: {starved}. One "
        "without the other sends a fresh implementor in knowing either the "
        "item's constraints or the repo's conventions, never both, and nothing "
        "else in its prompt carries the missing half. It has to arrive as file "
        "content the render reads, in one flag that names both: a second flag "
        "for the same key is a value the renderer throws away without saying "
        "which, and a `--set` literal hands the implementor a sentence about "
        "the constraints - which is a sentence that can name them in order to "
        "say they are withheld."
    )


def test_the_interface_read_opens_only_files_that_exist_today() -> None:
    # `PUBLIC_INTERFACES` is a shell command, and the shell it runs in has no
    # opinion about which of the card's `## Files` entries exist yet. Half that
    # list is usually the item's own output - the module it is about to write -
    # so a `cat` over the whole list exits non-zero on the first missing path
    # and takes the render down with it, before the test author is ever
    # dispatched. The block already knows the distinction: its own
    # `--require-file` asks for the entries that exist today, and the read has
    # to ask for the same half. Matched on what the operand names rather than on
    # its wording, so any phrasing that still hands over the whole list fails.
    blocks = [
        block for block in _render.renders() if _render.TESS.search(block.persona)
    ]

    assert blocks, (
        f"{_SKILL_MD}: no render block fills the test author's prompt. A card "
        "with an empty `## Tests` section has no spec until that dispatch runs, "
        "so the lane has nothing to hand the implementor."
    )

    reading = [block for block in blocks if _render.fills(block, "PUBLIC_INTERFACES")]

    assert reading, (
        f"{_SKILL_MD}: no flag of the test author's render fills "
        "`PUBLIC_INTERFACES`. The author is then asked to write tests against "
        "an interface it was never shown, and a read that opens nothing is not "
        "a read that opens only what exists."
    )

    unsafe = [
        f"line {block.line + 1}: PUBLIC_INTERFACES reads {unqualified!r}"
        for block in reading
        if (unqualified := _render.unqualified_read(block))
    ]

    assert not unsafe, (
        f"{_SKILL_MD}: the interface read opens paths nothing says are on "
        f"disk: {unsafe}. `cat` on a path the item has not created yet exits "
        "non-zero, the render dies with it, and the failure lands on the one "
        "step whose whole job is to describe the code as it stands. Point the "
        "read at the entries that exist today, the way the block's own "
        "`--require-file` already does - and at those alone, because an operand "
        "that says `present or absent` names the existing half while asking for "
        "both."
    )


def test_the_tests_render_names_the_paths_the_item_will_create() -> None:
    # The other half of the same rule, and the half that keeps the fix honest.
    # Narrowing the read to the files that exist is not enough on its own: the
    # test author is writing tests for a module that does not exist yet, and the
    # paths it will live at are the one thing reading the files that do exist
    # cannot supply. Dropped rather than moved, the entries the card creates
    # simply vanish from the prompt, and the tests come back written against
    # paths the author invented.
    blocks = [
        block for block in _render.renders() if _render.TESS.search(block.persona)
    ]

    assert blocks, (
        f"{_SKILL_MD}: no render block fills the test author's prompt, so "
        "nothing here can name the paths the item is about to create."
    )

    named = [
        f"line {block.line + 1}: `{flag.name} {flag.key}`"
        for block in blocks
        for flag in _render.planned_flags(block)
    ]
    named += _render.sentences_asserting(_section("Tests"), _render.PLANNED)

    assert named, (
        f"{_SKILL_MD}: nothing in the test author's render or in the `Tests` "
        "section names the `## Files` entries the card creates. Once the "
        "interface read is restricted to the files that exist, those paths are "
        "in no input the dispatch receives, and the author writes tests against "
        "paths of its own invention that the implementor's allowlist then "
        "refuses. Naming them in a `--require-file` guard is not naming them to "
        "the author: the renderer checks that path and drops it, so the prompt "
        "never carries the wording. Nor is naming them in order to say they are "
        "withheld."
    )


def test_the_rework_dispatch_sends_the_prompt_its_own_render_wrote() -> None:
    # The rework's ledger row names a prompt file, and the Agent call sends the
    # contents of that file. Reusing the implement block writes a different
    # path, so the row points at a file nothing rendered: the operator finds it
    # empty and either re-sends round one's prompt - which asks for work already
    # done and never mentions the findings - or types one by hand, the one thing
    # a zero-context lane cannot allow. The render carries its own spec too.
    renders = [
        block for block in _render.renders() if _render.REWORK.search(block.section)
    ]
    sends = [
        call for call in _render.dispatches() if _render.REWORK.search(call.section)
    ]

    assert renders, (
        f"{_SKILL_MD}: the `Rework` section opens a ledger row but renders no "
        "prompt of its own. A section that borrows another block's render "
        "borrows its `--out` too, and nothing then writes the file the row names."
    )
    assert sends, (
        f"{_SKILL_MD}: the `Rework` section renders a prompt and dispatches "
        "nothing. An unsent rework prompt leaves the confirmed findings "
        "unaddressed and the item at the exit rule with everything standing."
    )

    written = {_render.bare(block.out) for block in renders}
    sent = {_render.bare(call.prompt_file) for call in sends}

    assert written == sent, (
        f"{_SKILL_MD}: the rework renders {sorted(written)} and dispatches "
        f"{sorted(sent)}. The prompt file the ledger row names has to be the "
        "one the render wrote; anything else sends the operator to an empty "
        "path with a rework to run and nothing to run it with."
    )

    borrowed = [
        f"line {block.line + 1}: {complaint}"
        for block in renders
        if (complaint := _render.unspecced_rework(block))
    ]

    assert not borrowed, (
        f"{_SKILL_MD}: the rework render does not hand the implementor the "
        f"confirmed findings: {borrowed}. Rework runs once, and an implementor "
        "handed round one's failing tests is handed a spec it already satisfied "
        "- it reads nothing the reviewers confirmed, and the findings survive to "
        "park the item. The flag names the findings file itself, and a step "
        "above the block writes that file: the word `findings` in a shell "
        "comment reaches no implementor, and an unwritten path renders exit 4."
    )
