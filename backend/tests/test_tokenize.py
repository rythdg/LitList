"""Tests for BuildPlan.md Task 1D's abbreviation-aware sentence tokenizer
and segmented-abstract builder (SPEC.md §6.4, §6.5, §13.3; §15.1/§15.9).

The golden-file corpus (`fixtures/tokenizer/abbreviation_corpus.json`) is
shared verbatim with the frontend's Task 2D tests per BuildPlan.md Task
0.3 — this file is the *only* place that corpus is exercised on the
backend side.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.text.tokenize import (
    AbstractSection,
    PauseClass,
    SegmentKind,
    build_segmented_abstract,
    is_narration_unavailable,
    tokenize_sentences,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CORPUS_PATH = _REPO_ROOT / "fixtures" / "tokenizer" / "abbreviation_corpus.json"


def _load_corpus() -> list[dict]:
    with _CORPUS_PATH.open() as f:
        return json.load(f)["cases"]


_CASES = _load_corpus()


@pytest.mark.parametrize("case", _CASES, ids=[c["id"] for c in _CASES])
def test_golden_corpus(case: dict) -> None:
    spans = tokenize_sentences(case["raw_text"])
    actual = [s.text for s in spans]
    assert actual == case["expected_sentences"], case["note"]


@pytest.mark.parametrize("case", _CASES, ids=[c["id"] for c in _CASES])
def test_golden_corpus_spans_are_exact_slices(case: dict) -> None:
    """Every span must be an exact, verbatim slice of the source text
    (0-indexed, end-exclusive) — not just text-equal after the fact."""
    text = case["raw_text"]
    for span in tokenize_sentences(text):
        assert text[span.start : span.end] == span.text


def test_no_mid_sentence_split_on_every_known_abbreviation_class() -> None:
    """Explicit named coverage of the hard disambiguation the task calls
    out: 'et al.' splits at a true sentence end but title abbreviations
    ('Dr.') never split despite always being followed by a capitalized
    proper name."""
    et_al_end = next(c for c in _CASES if c["id"] == "abbreviation_at_true_sentence_end")
    et_al_mid = next(c for c in _CASES if c["id"] == "et_al_citation")
    titles = next(c for c in _CASES if c["id"] == "titles_and_approx")

    assert len(tokenize_sentences(et_al_end["raw_text"])) == 2
    assert len(tokenize_sentences(et_al_mid["raw_text"])) == 2
    assert len(tokenize_sentences(titles["raw_text"])) == 2
    # "Dr. Alvarez" must remain glued to the same sentence as what follows.
    first_sentence = tokenize_sentences(titles["raw_text"])[0].text
    assert "Dr. Alvarez" in first_sentence


def test_baseline_no_under_split() -> None:
    case = next(c for c in _CASES if c["id"] == "baseline_no_abbreviations")
    assert len(tokenize_sentences(case["raw_text"])) == 3


# --------------------------------------------------------------------------
# Segmented-abstract assembly (CONTRACTS.md §1)
# --------------------------------------------------------------------------


def test_unstructured_abstract_first_segment_is_structural_rest_are_sentence() -> None:
    text = (
        "Twenty-two patients completed the full protocol. "
        "Three withdrew due to unrelated scheduling conflicts."
    )
    display_abstract, spoken_abstract, response = build_segmented_abstract(
        pmid="123",
        sections=[AbstractSection(label=None, text=text)],
        language=None,
    )
    assert spoken_abstract  # non-empty, parallel flattened spoken form
    assert response.pmid == "123"
    assert len(response.segments) == 2
    assert response.segments[0].pause_class == PauseClass.structural
    assert response.segments[1].pause_class == PauseClass.sentence
    for segment in response.segments:
        assert segment.kind == SegmentKind.sentence
        assert segment.section_label is None
        assert (
            display_abstract[segment.char_start : segment.char_end]
            == segment.display_text
        )


def test_structured_abstract_headers_are_structural_and_sentences_denormalized() -> None:
    display_abstract, spoken_abstract, response = build_segmented_abstract(
        pmid="456",
        sections=[
            AbstractSection(
                label="BACKGROUND",
                text="Prior work has shown mixed results. A gap remains.",
            ),
            AbstractSection(
                label="METHODS",
                text="We enrolled 40 participants across two sites.",
            ),
        ],
        language=None,
    )
    kinds = [(s.kind, s.pause_class, s.section_label) for s in response.segments]
    assert kinds == [
        (SegmentKind.section_header, PauseClass.structural, "BACKGROUND"),
        (SegmentKind.sentence, PauseClass.sentence, "BACKGROUND"),
        (SegmentKind.sentence, PauseClass.sentence, "BACKGROUND"),
        (SegmentKind.section_header, PauseClass.structural, "METHODS"),
        (SegmentKind.sentence, PauseClass.sentence, "METHODS"),
    ]
    # index matches TTS queue order (0-based, contiguous).
    assert [s.index for s in response.segments] == [0, 1, 2, 3, 4]
    # Every char range must be an exact slice of the flattened display text.
    for segment in response.segments:
        assert (
            display_abstract[segment.char_start : segment.char_end]
            == segment.display_text
        )
    # Number-reading applied in the spoken form, not the display form.
    methods_sentence = response.segments[4]
    assert methods_sentence.display_text == "We enrolled 40 participants across two sites."
    assert "forty" in methods_sentence.spoken_text
    assert "40" not in methods_sentence.spoken_text
    # The flattened spoken_abstract carries the same headers/sentences in
    # their normalized (spoken) form, e.g. "forty" rather than "40".
    assert "Background." in spoken_abstract
    assert "Methods." in spoken_abstract
    assert "forty" in spoken_abstract


def test_very_first_segment_is_always_structural_even_with_no_header() -> None:
    _display, _spoken, response = build_segmented_abstract(
        pmid="789",
        sections=[AbstractSection(label=None, text="Only one sentence here.")],
        language=None,
    )
    assert response.segments[0].pause_class == PauseClass.structural


# --------------------------------------------------------------------------
# §13.3 language-mismatch flag
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("language", "locale", "expected"),
    [
        ("eng", "en", False),
        ("eng", "en-US", False),
        ("fre", "en", True),
        ("ger", "en-GB", True),
        (None, "en", False),  # unknown language: permissive, don't block
        ("en", "en", False),  # already a bare 2-letter subtag
        ("ENG", "en", False),  # case-insensitive
    ],
)
def test_is_narration_unavailable(language: str | None, locale: str, expected: bool) -> None:
    assert is_narration_unavailable(language, locale) is expected


def test_build_segmented_abstract_sets_narration_unavailable_flag() -> None:
    _display, _spoken, response = build_segmented_abstract(
        pmid="999",
        sections=[AbstractSection(label=None, text="Un texte en francais complet.")],
        language="fre",
        narration_locale="en",
    )
    assert response.narration_unavailable is True

    _display, _spoken, response_match = build_segmented_abstract(
        pmid="999",
        sections=[AbstractSection(label=None, text="An English sentence here.")],
        language="eng",
        narration_locale="en",
    )
    assert response_match.narration_unavailable is False
