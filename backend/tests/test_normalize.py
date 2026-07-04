"""Unit tests for the SPEC.md §6.3 text-normalization pipeline
(BuildPlan.md Task 1D), one construct at a time — no fixed golden corpus
is pinned for normalization (only the tokenizer has one), so these are
this task's own per-construct coverage of §6.3's bullet list."""

from __future__ import annotations

import pytest

from app.text.normalize import normalize_for_speech


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Smith et al. reported similar findings.", "and colleagues"),
        ("Several comorbidities, e.g. diabetes.", "for example"),
        ("The most common, i.e. diabetes.", "that is"),
        ("Higher vs. placebo.", "versus"),
        ("cf. the control group.", "compare to"),
        ("enrolled approx. 200 participants.", "approximately"),
        ("controlled for age, etc.", "et cetera"),
        ("shown in Fig. 2.", "figure"),
        ("shown in Figs. 2 and 3.", "figures"),
    ],
)
def test_latin_abbreviation_expansion(raw: str, expected: str) -> None:
    assert expected in normalize_for_speech(raw)


def test_statistical_notation_matches_spec_worked_examples() -> None:
    # SPEC.md §6.3's own worked examples keep the numerals as digits and
    # only expand the operators/percent/CI markers.
    assert normalize_for_speech("p < 0.05") == "p less than 0.05"
    assert normalize_for_speech("n = 24") == "n equals 24"
    assert "plus or minus" in normalize_for_speech("effect size ± 1.2")
    assert normalize_for_speech("95% CI") == "95 percent confidence interval"


def test_unicode_less_than_or_equal_and_greater_than_or_equal() -> None:
    # Adversarial review finding: the Unicode "≤"/"≥" glyphs are a TTS
    # "unknown character -> silence" trap identical to the Greek-letter
    # case §6.3 explicitly calls out — left unhandled, a real threshold
    # like "p ≤ 0.05" would narrate as "p 0.05", silently losing the
    # comparison direction of a clinically meaningful value.
    out = normalize_for_speech("p ≤ 0.05 was considered significant.")
    assert out == "p less than or equal to 0.05 was considered significant."
    assert "≤" not in out

    out_ge = normalize_for_speech("p ≥ 0.10 was not significant.")
    assert out_ge == "p greater than or equal to 0.10 was not significant."
    assert "≥" not in out_ge


def test_negative_number_after_equals_still_gets_operator_word() -> None:
    # Adversarial review finding: without allowing a leading minus sign,
    # "r = -0.34" dropped the word "equals" while "p < 0.001" in the same
    # sentence correctly got "less than" — a fluency inconsistency.
    out = normalize_for_speech("r = -0.34 and p < 0.001.")
    assert "r equals -0.34" in out
    assert "p less than 0.001" in out


def test_r_squared_notation() -> None:
    out = normalize_for_speech("r² = 0.8")
    assert "squared" in out
    assert "equals" in out
    assert "0.8" in out


@pytest.mark.parametrize(
    ("raw", "expected_fragment"),
    [
        ("α expression increased", "alpha"),
        ("β blockers were used", "beta"),
        ("Δ change over time", "delta"),
        ("a δ subunit", "delta"),
        ("measured in μg", "micro"),
        ("recorded at 37°C", "degrees Celsius"),
    ],
)
def test_greek_letters_and_symbols(raw: str, expected_fragment: str) -> None:
    assert expected_fragment in normalize_for_speech(raw)


@pytest.mark.parametrize(
    ("raw", "expected_fragment"),
    [
        ("dosed at 5 mg per day", "milligrams"),
        ("a volume of 10 mL", "milliliters"),
        ("measured at 20 kHz", "kilohertz"),
        ("a distance of 5 nm", "nanometers"),
        ("weighed 70 kg", "kilograms"),
    ],
)
def test_unit_expansion(raw: str, expected_fragment: str) -> None:
    assert expected_fragment in normalize_for_speech(raw)


def test_reference_brackets_are_stripped() -> None:
    out = normalize_for_speech("This was shown previously [1] and confirmed [2, 3].")
    assert "[1]" not in out
    assert "[2" not in out
    assert "previously" in out
    assert "confirmed" in out


def test_stray_whitespace_and_smart_quotes_cleaned() -> None:
    out = normalize_for_speech("This  has\n\nextra   whitespace and “smart quotes”.")
    assert "  " not in out
    assert "\n" not in out
    assert '"smart quotes"' in out


def test_number_reading_for_plain_counts() -> None:
    assert "forty" in normalize_for_speech("We enrolled 40 participants.")
    assert "40" not in normalize_for_speech("We enrolled 40 participants.")
    assert normalize_for_speech("Fig. 2") == "figure two"


def test_gene_protein_species_names_pass_through_unchanged() -> None:
    # §6.3: known v1 quality gap, explicitly not attempted here.
    out = normalize_for_speech("BRCA1 mutations were observed in E. coli cultures.")
    assert "BRCA1" in out
    assert "E. coli" in out
