"""Text normalization pipeline for TTS narration (BuildPlan.md Task 1D,
SPEC.md §6.3).

`normalize_for_speech` turns one chunk of *display* text (already split
into a sentence/section-header segment by `app/text/tokenize.py`) into its
*spoken* counterpart: abbreviation/Latin expansion, statistical/mathematical
notation, Greek letters & symbols, unit expansion, reference-bracket
stripping, and small-integer number-reading, per §6.3's bullet list.

This module is deliberately engine-agnostic (plain text in, plain text
out) — it doesn't know or care whether the result is queued to the Web
Speech API now or a self-hosted neural TTS engine later (§6.7).

Known, explicitly-flagged v1 scope gap (§6.3): gene/protein/species names
are passed through as-is. No biomedical pronunciation dictionary is
attempted here.

Architecture note: rather than adding a new third-party dependency
(e.g. `num2words`) for the small amount of cardinal-number spelling this
needs, `_spell_cardinal` below is a compact, self-contained implementation
covering 0-999,999 — plenty for participant counts / figure numbers /
ages seen in abstracts, and it keeps `pyproject.toml` (a file this task
doesn't own) untouched. Numbers outside that range are left as digits
rather than raising.
"""

from __future__ import annotations

import re

_ONES = [
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
]
_TENS = [
    "",
    "",
    "twenty",
    "thirty",
    "forty",
    "fifty",
    "sixty",
    "seventy",
    "eighty",
    "ninety",
]


def _spell_below_1000(n: int) -> str:
    if n < 20:
        return _ONES[n]
    if n < 100:
        tens, rem = divmod(n, 10)
        return _TENS[tens] + ("-" + _ONES[rem] if rem else "")
    hundreds, rem = divmod(n, 100)
    out = _ONES[hundreds] + " hundred"
    if rem:
        out += " " + _spell_below_1000(rem)
    return out


def _spell_cardinal(n: int) -> str:
    """Spell out a non-negative integer as English words. Falls back to
    the digit string for magnitudes this simple converter doesn't cover
    (v1 scope: abstracts don't need million-scale narration)."""
    if n == 0:
        return "zero"
    if n >= 1_000_000:
        return str(n)
    parts: list[str] = []
    millions, rem = divmod(n, 1_000_000)
    thousands, rem = divmod(rem, 1000)
    if millions:
        parts.append(_spell_below_1000(millions) + " million")
    if thousands:
        parts.append(_spell_below_1000(thousands) + " thousand")
    if rem or not parts:
        parts.append(_spell_below_1000(rem))
    return " ".join(parts)


# --- Latin/citation abbreviation expansion (§6.3) --------------------------
# Order matters: longer/more-specific patterns (e.g. "Figs.") must be tried
# before their shorter prefixes ("Fig.").
_ABBREVIATION_EXPANSIONS: list[tuple[str, str]] = [
    (r"\bet\s+al\.", "and colleagues"),
    (r"\be\.g\.", "for example"),
    (r"\bi\.e\.", "that is"),
    (r"\bvs\.", "versus"),
    (r"\bcf\.", "compare to"),
    (r"\bapprox\.", "approximately"),
    (r"\betc\.", "et cetera"),
    (r"\bFigs\.", "figures"),
    (r"\bFig\.", "figure"),
]

# --- Greek letters & symbols (§6.3) ----------------------------------------
_GREEK_AND_SYMBOLS: list[tuple[str, str]] = [
    ("±", " plus or minus "),
    ("°C", " degrees Celsius"),
    ("°F", " degrees Fahrenheit"),
    ("°", " degrees"),
    ("α", " alpha "),
    ("β", " beta "),
    ("γ", " gamma "),
    ("Δ", " delta "),
    ("δ", " delta "),
    ("μ", " micro "),
    ("σ", " sigma "),
    ("λ", " lambda "),
    ("π", " pi "),
    ("θ", " theta "),
    ("ω", " omega "),
    ("²", " squared"),
    ("³", " cubed"),
]

# --- Units (§6.3) — matched only when directly preceded by a number so we
# don't rewrite the letters "mL" etc. when they appear inside unrelated
# words. -----------------------------------------------------------------
_UNIT_EXPANSIONS: list[tuple[str, str]] = [
    (r"mmHg", "millimeters of mercury"),
    (r"kHz", "kilohertz"),
    (r"Hz", "hertz"),
    (r"mL", "milliliters"),
    (r"ml", "milliliters"),
    (r"[uµ]L", "microliters"),
    (r"mg", "milligrams"),
    (r"kg", "kilograms"),
    (r"nm", "nanometers"),
    (r"cm", "centimeters"),
    (r"mm", "millimeters"),
]
_UNIT_PATTERN = re.compile(
    r"(?<=[0-9])\s?(" + "|".join(p for p, _ in _UNIT_EXPANSIONS) + r")\b"
)


def _expand_units(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        token = match.group(1)
        for pattern, expansion in _UNIT_EXPANSIONS:
            if re.fullmatch(pattern, token):
                return " " + expansion
        return match.group(0)

    return _UNIT_PATTERN.sub(repl, text)


# Reference brackets: "[1]", "[1,2]", "[1-3]" — stripped entirely (§6.3).
_REFERENCE_BRACKET = re.compile(r"\s?\[\d+(?:[,\-]\s?\d+)*\]")

# Curly/smart quotes normalized to straight ones before narration.
_QUOTE_MAP = {
    "“": '"',
    "”": '"',
    "‘": "'",
    "’": "'",
}

# Numbers already handled by an operator/percent expansion (see
# `_expand_math_operators`) are marked with this sentinel so the later
# generic cardinal-spellout pass skips them, matching §6.3's own worked
# examples ("p less than 0.05", "n equals 24", "95 percent confidence
# interval" — the numerals themselves are *not* spelled out in those
# statistical contexts, only the operators are).
_PROTECT_OPEN = "\x00"
_PROTECT_CLOSE = "\x01"


def _expand_math_operators(text: str) -> str:
    # Numbers here may carry a leading minus sign ("r = -0.34") — without
    # allowing it, the operator word ("equals") would only ever attach
    # itself to positive comparisons, a fluency inconsistency next to
    # "p < 0.001" in the same sentence getting "less than" correctly.
    number = r"-?[0-9]+(?:\.[0-9]+)?"

    def _op(pattern: str, words: str, source: str) -> str:
        return re.sub(
            pattern + r"\s*(" + number + r")",
            lambda m: " " + words + " " + _PROTECT_OPEN + m.group(1) + _PROTECT_CLOSE,
            source,
        )

    # "p ≤ 0.05" / "p ≥ 0.05" style — Unicode operators (§6.3's "unknown
    # character -> silence" failure mode also applies to these, same as
    # the Greek-letter case the spec calls out; must be handled before the
    # plain "<"/">" cases below since "≤"/"≥" don't otherwise match them.
    text = _op(r"≤", "less than or equal to", text)
    text = _op(r"≥", "greater than or equal to", text)
    # "p < 0.05" / "n = 24" / "r = -0.34" / "r² = 0.8" style: operator
    # directly followed by a number. Expand the operator to words and
    # protect the number from later spellout.
    text = _op("<", "less than", text)
    text = _op(">", "greater than", text)
    text = _op("=", "equals", text)
    # "95% CI" style: number directly followed by a percent sign.
    text = re.sub(
        r"(" + number + r")\s?%",
        lambda m: _PROTECT_OPEN + m.group(1) + _PROTECT_CLOSE + " percent",
        text,
    )
    # Standalone "CI" abbreviation (confidence interval), word-boundary only
    # so it doesn't clobber unrelated capitalized tokens.
    text = re.sub(r"\bCI\b", "confidence interval", text)
    return text


# An integer (no decimal point — decimals are left as digit speech,
# matching §6.3's "p less than 0.05" style example) that is not already
# wrapped in the protection sentinels above.
_STANDALONE_NUMBER = re.compile(r"(?<![0-9.\x00])\b([0-9]{1,6})\b(?!\.[0-9])")


def _spell_out_numbers(text: str) -> str:
    return _STANDALONE_NUMBER.sub(lambda m: _spell_cardinal(int(m.group(1))), text)


def normalize_for_speech(text: str) -> str:
    """Produce the spoken-text form of one display-text segment (§6.3).

    Order of passes matters:
    1. Reference-bracket stripping and quote/whitespace cleanup (raw
       formatting artifacts, before anything tries to parse the text).
    2. Latin/citation abbreviation expansion (must run before the generic
       number spellout, since e.g. "Fig. 2" -> "figure 2" -> "figure two").
    3. Math operators / percent / CI expansion, protecting the numerals
       those touch from the later generic spellout pass.
    4. Greek letters & symbols.
    5. Units (must run before generic spellout so "40 mg" doesn't first
       become "forty mg" and lose the unit-adjacency check — units are
       matched by *preceding* digits, which spellout would remove).
    6. Generic small-integer spellout for any number not already
       protected by step 3.
    7. Strip the protection sentinels back out.
    """
    for smart, straight in _QUOTE_MAP.items():
        text = text.replace(smart, straight)
    text = _REFERENCE_BRACKET.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()

    for pattern, expansion in _ABBREVIATION_EXPANSIONS:
        text = re.sub(pattern, expansion, text)

    text = _expand_math_operators(text)

    for symbol, expansion in _GREEK_AND_SYMBOLS:
        text = text.replace(symbol, expansion)

    text = _expand_units(text)
    text = _spell_out_numbers(text)

    text = text.replace(_PROTECT_OPEN, "").replace(_PROTECT_CLOSE, "")
    return re.sub(r"\s+", " ", text).strip()
