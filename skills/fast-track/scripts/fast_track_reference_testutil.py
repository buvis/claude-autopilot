"""The two reference documents the fast-track driver sends a reader to.

Split out of test_fast_track_prose.py to keep both files under the file size
limit; the two pins themselves stay there. This module holds the documents, the
parser they are read against, the fence walk that says which of their lines an
operator could paste, and the complaint each assertion raises.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

_TESTUTIL_PATH = Path(__file__).with_name("fast_track_prose_testutil.py")
_TESTUTIL_SPEC = importlib.util.spec_from_file_location(
    "fast_track_prose_testutil",
    _TESTUTIL_PATH,
)
assert _TESTUTIL_SPEC is not None and _TESTUTIL_SPEC.loader is not None
_testutil = importlib.util.module_from_spec(_TESTUTIL_SPEC)
_TESTUTIL_SPEC.loader.exec_module(_testutil)

_Passage = _testutil.Passage
_code_fragments = _testutil.code_fragments

# The two reference documents the driver sends a reader to. Resolved from this
# file, never from the working directory, so the suite says the same thing from
# the repo root and from here. A missing document is a failure, never a skip.
_REFERENCES = Path(__file__).resolve().parent.parent / "references"
SPEC_CARD_MD = _REFERENCES / "spec-card.md"
LANE_DISPATCH_MD = _REFERENCES / "lane-dispatch.md"

# The real parser, loaded from beside this file: these scripts are not an
# installed package, so `card.py` comes in the same way the reader model does.
_CARD_PATH = Path(__file__).with_name("card.py")
_CARD_SPEC = importlib.util.spec_from_file_location("fast_track_card_pins", _CARD_PATH)
assert _CARD_SPEC is not None and _CARD_SPEC.loader is not None
_card = importlib.util.module_from_spec(_CARD_SPEC)
# Registered before exec_module, and under a name of this file's own: a module
# built with `from __future__ import annotations` and @dataclass looks itself up
# in sys.modules while it imports, and test_card.py registers the parser too.
sys.modules[_CARD_SPEC.name] = _card
_CARD_SPEC.loader.exec_module(_card)

Card = _card.Card
CardError = _card.CardError
load_card = _card.load_card

# The vocabulary a reference has to teach, read out of the parser at runtime: a
# list copied into this file is a second contract that drifts on the next field.
VOCABULARY = (*_card._SECTIONS, *_card._MODELS, *_card._SUITES)

# Fences of three backticks or more, so a card wrapped in a longer fence to
# carry its own snippets is read whole instead of cut at the first inner fence.
FENCE = re.compile(
    r"^(?P<ticks>`{3,})[^\n]*\n(?P<body>.*?)^(?P=ticks)[ \t]*$",
    re.MULTILINE | re.DOTALL,
)
# An HTML comment renders nowhere, so a kind or a rule written inside one is
# documented for nobody. Both references are read with the comments gone.
HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_FENCE_LINE = re.compile(r"^ {0,3}(?:```|~~~)")


def copyable_lines(text: str) -> list[str]:
    """The fenced lines an operator could select and paste.

    The testutil's reader model is wired to SKILL.md through its own
    `document()`, so the walk is local and only the pasteable bar is shared.
    """
    found: list[str] = []
    in_code = False
    for line in text.splitlines():
        if _FENCE_LINE.match(line):
            in_code = not in_code
        elif in_code and line.strip():
            found.extend(_code_fragments(_Passage((), line.strip(), True)))
    return found


def lifted_from_fixture(block: str) -> str:
    """The parser fixture this block is a copy of, whitespace ignored."""
    wanted = " ".join(block.split())
    for fixture in sorted(Path(__file__).with_name("fixtures").glob("*.md")):
        if " ".join(fixture.read_text(encoding="utf-8").split()) == wanted:
            return fixture.name
    return ""


# The card is picked out by its own shape - a `---` block on top, `## ` sections
# under it - and never by where it sits on the page, so a paragraph or a command
# line added above the example does not quietly move the pin to another block.
CARD_SHAPE = re.compile(r"---\n.*?^## ", re.MULTILINE | re.DOTALL)
DECLARED_ITEM = re.compile(r"^item:[ \t]*(\S+)[ \t]*$", re.MULTILINE)
# What a reader can learn from, counted in words and in path-shaped names: one
# character satisfies a non-empty string, and the example is copied whole.
MIN_GOAL_WORDS = 12
MIN_EXAMPLE_FILES = 2
REAL_PATH = re.compile(r"\S*[/.]\w+$")

NO_SPEC_CARD = (
    f"{SPEC_CARD_MD} is gone. The card is the lane's only input, and with no "
    "format to copy a reader writes one from memory for a parser that answers "
    "a field name and exit 2."
)
NO_LOADABLE_EXAMPLE = (
    f"{SPEC_CARD_MD}: no fenced block in the document loads as a card "
    "({blocks} fenced block(s) read, refusals: {refusals}). An example the real "
    "parser throws back teaches every reader the one card the lane will not take."
)
EXAMPLE_WITHOUT_ITEM = (
    f"{SPEC_CARD_MD}: the example that parsed declares no `item:` line to read "
    "back, so nothing here shows the parse came from the document rather than "
    "from some other block on the page."
)
ITEM_DRIFTED = (
    f"{SPEC_CARD_MD}: the parsed card carries item {{item!r}} while the example "
    "declares {declared!r}. The block under test is not the one on the page."
)
LIFTED_EXAMPLE = (
    f"{SPEC_CARD_MD}: the worked example is a copy of {{fixture!r}} from the "
    "parser's fixtures, and those are bent into refusals whenever a parser test "
    "needs one. The reference then teaches whatever a test needed last."
)
THIN_EXAMPLE = (
    f"{SPEC_CARD_MD}: the example is a shell, not a worked card ({{words}} "
    "word(s) of goal, {paths} named as files). A reader copies the example "
    "whole, so a one-word goal and a file called `x` shape every card after it."
)
UNTAUGHT = (
    f"{SPEC_CARD_MD}: the prose around the example never names {{untaught}}, "
    "read out of `card.py` as the vocabulary it takes. A page that shows a card "
    "and teaches no field leaves one shape to copy and nothing to change, and "
    "prose that teaches some other model is answered with exit 2."
)

# The eight kinds the lane dispatches under. The reference documents conditional
# lanes too (`fast-track:tess`, `fast-track:alice`), so the pin asks that these
# eight are present and never that the document names only these.
LANE_KINDS = tuple(
    f"fast-track:{lane}"
    for lane in ("ivan", "fanout", "blake", "eve", "bob", "carl", "victor", "delta")
)
# The call that opens the row, matched apart from the flag so the two can be
# written in either order. A kind counts as documented when one pasteable line
# carries both; named anywhere else it is a word on a page.
LEDGER_CALL = "record_dispatch.py"
NO_LANE_REFERENCE = (
    f"{LANE_DISPATCH_MD} is gone, and every lane's command block went with it. "
    "A dispatch assembled from memory goes out with the wrong inputs and no row "
    "to show for it."
)
MISSING_KINDS = (
    f"{LANE_DISPATCH_MD}: no line an operator could paste names {{missing}} "
    "beside `record_dispatch.py`. A kind carried only by prose, or by an HTML "
    "comment that renders nowhere, is a lane dispatched from guesswork and a "
    "ledger row nobody knows to open."
)
KINDS_RETIRED = (
    f"{LANE_DISPATCH_MD}: the reference takes its own kinds back: {{retired}}. "
    "A block called retired, historical or safe to disregard is one nobody runs."
)
