"""Abbreviation-aware sentence tokenizer and segmented-abstract builder
(BuildPlan.md Task 1D; SPEC.md §6.4's pause logic, §6.5's tokenizer,
§13.3's language check; CONTRACTS.md §1 "Segmented-abstract response").

This is the **only** place sentence segmentation, abbreviation handling,
and pause-class assignment live in this project — the frontend playback
engine (Task 2D) only ever renders the `AbstractSegment` list this module
produces, it never recomputes any of this (see BuildPlan.md's note under
Task 2D).

Two public entry points:

- `tokenize_sentences(text)` — the pure abbreviation-aware sentence
  splitter, tested directly against `fixtures/tokenizer/
  abbreviation_corpus.json`.
- `build_segmented_abstract(...)` — assembles the full pinned
  `SegmentedAbstractResponse` shape (section headers + sentences, pause
  classes, language-mismatch flag) from structured section input.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel

from app.text.normalize import normalize_for_speech

# --------------------------------------------------------------------------
# Abbreviation-aware sentence splitting (§6.5)
# --------------------------------------------------------------------------

# Title abbreviations: per the task's flagged hard case, these are *always*
# followed by a capitalized proper name and must NEVER be treated as a
# sentence boundary — they are exempted from the capitalization check
# entirely (unlike the "et al." citation class below, which does use it).
_TITLE_ABBREVIATIONS = {
    "dr",
    "mr",
    "mrs",
    "ms",
    "prof",
    "st",
    "rev",
    "sr",
    "jr",
    "hon",
    "gen",
    "col",
    "capt",
    "lt",
    "sgt",
}

# Generic abbreviations: never a sentence boundary regardless of what
# follows (measurement qualifiers, citation/example markers, figure
# references, genus-species shorthand's second half, etc.).
_GENERIC_ABBREVIATIONS = {
    "e.g",
    "i.e",
    "vs",
    "cf",
    "approx",
    "etc",
    "fig",
    "figs",
    "no",
    "vol",
    "eq",
    "eqs",
    "al",  # fallback if "al." ever appears without a preceding "et"
    "resp",
    "ca",
    "viz",
}

# A candidate sentence-terminator: one of . ! ? optionally followed by
# closing quote/paren/bracket characters, itself followed by whitespace or
# end-of-string. (An internal abbreviation period like the first "." in
# "e.g." is *not* followed by whitespace, so it never matches here at
# all — only the final period of a multi-dot abbreviation is a candidate.)
_TERMINATOR = re.compile(r"[.!?]+[\'\")\]]*(?=\s|$)")

_WRAP_CHARS = "()[]{}\"'“”‘’"


@dataclass(frozen=True)
class SentenceSpan:
    """One sentence, as a slice of the original (display) text: `text ==
    source[start:end]` always holds (0-indexed, end-exclusive)."""

    text: str
    start: int
    end: int


def _preceding_token(text: str, before: int) -> tuple[str, int]:
    """Returns (token, token_start) for the run of non-whitespace
    characters ending immediately before index `before`."""
    i = before
    while i > 0 and not text[i - 1].isspace():
        i -= 1
    return text[i:before], i


def _next_char_info(text: str, after: int) -> tuple[bool, bool]:
    """Looks at what follows index `after` (skipping whitespace and any
    leading quote/paren characters). Returns (at_end_of_text,
    next_starts_upper_or_digit)."""
    i = after
    n = len(text)
    while i < n and text[i].isspace():
        i += 1
    if i >= n:
        return True, False
    while i < n and text[i] in _WRAP_CHARS:
        i += 1
    if i >= n:
        return True, False
    ch = text[i]
    if ch.isdigit():
        return False, True
    if ch.isalpha():
        return False, ch.isupper()
    return False, False


def _is_sentence_boundary(text: str, match: re.Match[str]) -> bool:
    punct_start = match.start()
    stem, stem_start = _preceding_token(text, punct_start)
    stem = stem.strip(_WRAP_CHARS)
    stem_lower = stem.lower()

    at_end, next_upper = _next_char_info(text, match.end())
    if at_end:
        # The last sentence in the text always closes here, regardless of
        # what precedes it.
        return True

    second_token = ""
    if stem_start > 0:
        j = stem_start
        while j > 0 and text[j - 1].isspace():
            j -= 1
        if j > 0:
            second_token, _ = _preceding_token(text, j)
            second_token = second_token.strip(_WRAP_CHARS)

    is_et_al = stem_lower == "al" and second_token.lower() == "et"

    if is_et_al:
        # "et al." — the hard case: split only when genuinely followed by
        # a new capitalized sentence, never when it's mid-clause.
        return next_upper
    if re.fullmatch(r"[A-Za-z]", stem):
        # Single-letter genus/initial abbreviation (e.g. "E. coli") — never
        # a boundary.
        return False
    if stem_lower in _TITLE_ABBREVIATIONS:
        # Title abbreviations are exempted from the capitalization check
        # entirely — always followed by a capitalized name, never a split.
        return False
    if stem_lower in _GENERIC_ABBREVIATIONS:
        return False
    if re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", stem):
        # A number's trailing period (e.g. the "2." in "Fig. 2.") — treat
        # like a normal word boundary, decided by capitalization of what
        # follows.
        return next_upper
    # Default: an ordinary word ending in terminal punctuation.
    return next_upper


def tokenize_sentences(text: str) -> list[SentenceSpan]:
    """Splits `text` into abbreviation-aware sentence spans (§6.5).

    Unlike a naive `". ".split()`, this does not cut mid-sentence on
    `Fig. 2`, `vs.`, `approx.`, `Dr.`, `et al.` (mid-clause), `E. coli`,
    decimal numbers, or statistical notation — see
    `fixtures/tokenizer/abbreviation_corpus.json` for the full corpus this
    is validated against.
    """
    spans: list[SentenceSpan] = []
    sentence_start = 0
    n = len(text)

    for match in _TERMINATOR.finditer(text):
        if match.end() <= sentence_start:
            continue
        if not _is_sentence_boundary(text, match):
            continue
        start = sentence_start
        while start < n and text[start].isspace():
            start += 1
        end = match.end()
        if start < end:
            spans.append(SentenceSpan(text=text[start:end], start=start, end=end))
        sentence_start = end

    # Trailing content with no terminal punctuation at all (or content
    # after the final matched boundary) still forms one last sentence.
    if sentence_start < n:
        start = sentence_start
        while start < n and text[start].isspace():
            start += 1
        end = n
        while end > start and text[end - 1].isspace():
            end -= 1
        if start < end:
            spans.append(SentenceSpan(text=text[start:end], start=start, end=end))

    return spans


# --------------------------------------------------------------------------
# Segmented-abstract assembly (§6.4 pause logic, §7.5 structured sections,
# §13.3 language check) — CONTRACTS.md §1 shape.
# --------------------------------------------------------------------------


class SegmentKind(StrEnum):
    section_header = "section_header"
    sentence = "sentence"


class PauseClass(StrEnum):
    structural = "structural"
    sentence = "sentence"


class AbstractSegment(BaseModel):
    index: int
    kind: SegmentKind
    section_label: str | None
    display_text: str
    spoken_text: str
    char_start: int
    char_end: int
    pause_class: PauseClass


class SegmentedAbstractResponse(BaseModel):
    pmid: str
    narration_unavailable: bool
    segments: list[AbstractSegment]


@dataclass(frozen=True)
class AbstractSection:
    """One `<AbstractText Label="...">` element from EFetch (§7.5), or the
    single unlabeled section of an unstructured abstract (`label=None`)."""

    label: str | None
    text: str


# PubMed/MEDLINE `Language` field values are 3-letter codes (e.g. "eng",
# "fre") — not BCP-47 (§13.3 doesn't spell this out explicitly, but this is
# the real MEDLINE record format; flagged here since it's the kind of
# real-API-vs-spec-prose gap this project's process asks to call out
# rather than silently code around). Mapped to the 2-letter language
# subtag used to compare against an active narration voice's locale
# (e.g. "en-US" -> "en").
_MEDLINE_LANGUAGE_TO_SUBTAG = {
    "eng": "en",
    "fre": "fr",
    "fra": "fr",
    "ger": "de",
    "deu": "de",
    "spa": "es",
    "ita": "it",
    "por": "pt",
    "rus": "ru",
    "jpn": "ja",
    "chi": "zh",
    "zho": "zh",
    "kor": "ko",
    "dut": "nl",
    "nld": "nl",
    "pol": "pl",
    "swe": "sv",
    "dan": "da",
    "nor": "no",
    "fin": "fi",
    "gre": "el",
    "ell": "el",
    "tur": "tr",
    "ara": "ar",
    "heb": "he",
    "hin": "hi",
}


def is_narration_unavailable(language: str | None, narration_locale: str) -> bool:
    """§13.3: true when the record's captured `Language` field doesn't
    match the active narration voice's locale. An absent `Language` field
    (common — it's optional on MEDLINE records, and 1B may not have it
    wired in yet) is treated permissively (`False`) rather than blocking
    narration on unknown data."""
    if not language:
        return False
    code = language.strip().lower()
    subtag = _MEDLINE_LANGUAGE_TO_SUBTAG.get(code, code[:2])
    target = narration_locale.strip().lower().split("-")[0]
    return subtag != target


def build_segmented_abstract(
    pmid: str,
    sections: list[AbstractSection],
    *,
    language: str | None,
    narration_locale: str = "en",
) -> tuple[str, str, SegmentedAbstractResponse]:
    """Builds `display_abstract` and `spoken_abstract` (both flattened, for
    `Paper.display_abstract`/`Paper.spoken_abstract` per CONTRACTS.md §1's
    note that segments' `spoken_text` is "sourced from `Paper.
    spoken_abstract`") plus the pinned `SegmentedAbstractResponse`, from
    structured section input (§7.5's `AbstractText`/`Label` pairs, or a
    single unlabeled section for a plain abstract).

    Returns `(display_abstract, spoken_abstract, response)`. The two
    flattened strings follow the same section/sentence-join convention (so
    Task 3A can persist both onto a `Paper` row directly rather than
    re-deriving this join logic itself) — only `display_abstract`'s join
    is char-offset-exact against `response.segments[].char_start/char_end`
    (`spoken_abstract` has no equivalent offset contract, since nothing
    needs to slice back into it).
    """
    display_parts: list[str] = []
    spoken_parts: list[str] = []
    segments: list[AbstractSegment] = []
    cursor = 0
    index = 0

    for section_idx, section in enumerate(sections):
        if section_idx > 0:
            display_parts.append("\n\n")
            spoken_parts.append("\n\n")
            cursor += 2

        if section.label:
            header_display = section.label.strip().capitalize()
            header_spoken = normalize_for_speech(header_display) + "."
            header_start = cursor
            header_end = header_start + len(header_display)
            segments.append(
                AbstractSegment(
                    index=index,
                    kind=SegmentKind.section_header,
                    section_label=section.label,
                    display_text=header_display,
                    spoken_text=header_spoken,
                    char_start=header_start,
                    char_end=header_end,
                    pause_class=PauseClass.structural,
                )
            )
            display_parts.append(header_display)
            spoken_parts.append(header_spoken)
            cursor = header_end
            index += 1
            display_parts.append("\n")
            spoken_parts.append("\n")
            cursor += 1

        for sentence in tokenize_sentences(section.text):
            sentence_start = cursor
            sentence_end = sentence_start + len(sentence.text)
            spoken_text = normalize_for_speech(sentence.text)
            is_first_overall = index == 0
            pause_class = (
                PauseClass.structural if is_first_overall else PauseClass.sentence
            )
            segments.append(
                AbstractSegment(
                    index=index,
                    kind=SegmentKind.sentence,
                    section_label=section.label,
                    display_text=sentence.text,
                    spoken_text=spoken_text,
                    char_start=sentence_start,
                    char_end=sentence_end,
                    pause_class=pause_class,
                )
            )
            display_parts.append(sentence.text)
            spoken_parts.append(spoken_text)
            cursor = sentence_end
            index += 1
            # Single space between consecutive sentences within a section.
            display_parts.append(" ")
            spoken_parts.append(" ")
            cursor += 1

        # Drop the trailing single-space separator added after the last
        # sentence of this section (avoids a stray space before the next
        # section's "\n\n").
        if display_parts and display_parts[-1] == " ":
            display_parts.pop()
            cursor -= 1
        if spoken_parts and spoken_parts[-1] == " ":
            spoken_parts.pop()

    display_abstract = "".join(display_parts)
    spoken_abstract = "".join(spoken_parts)

    narration_unavailable = is_narration_unavailable(language, narration_locale)

    return (
        display_abstract,
        spoken_abstract,
        SegmentedAbstractResponse(
            pmid=pmid,
            narration_unavailable=narration_unavailable,
            segments=segments,
        ),
    )
