"""Pin the reviewer citation format (PRD 00198) in every persona.

`consolidate_findings.py` merges two findings only when their `File:`
citations name one file. Review 00186 cycle 1 lost four real agreements
because Alice cited absolute paths with a `(lines a-b)` suffix while Bob
cited `path:line`. The sentence below stops that drift at the source.
"""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]

CITATION_SENTENCE = (
    "Cite files repo-relative as path:line (for example skills/work/SKILL.md:166), "
    'never absolute and never with a "(lines a-b)" suffix.'
)

PERSONAS = [
    "agents/alice.md",
    "agents/blake.md",
    "agents/carl.md",
    "skills/review-work-completion/references/agent-invocation.md",
]


@pytest.mark.parametrize("relative", PERSONAS)
def test_persona_carries_the_citation_sentence_verbatim(relative: str) -> None:
    text = (ROOT / relative).read_text(encoding="utf-8")
    assert CITATION_SENTENCE in text
    assert "path:line" in text
    assert "never absolute" in text


def test_bob_section_owns_the_citation_line_and_forbids_the_na_shape() -> None:
    invocation = (ROOT / PERSONAS[3]).read_text(encoding="utf-8")
    bob = invocation.split("## Bob (Codex)", 1)[1].split("\n## ", 1)[0]
    assert CITATION_SENTENCE in bob
    assert "never `N/A (a.py:77, b.py:91)`" in bob
    assert "cites the first file as its `File:` value" in bob
