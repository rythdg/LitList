# Shared test fixture corpus

Created by `BuildPlan.md` Task 0.3 so backend and frontend tests aren't
independently guessing at the same edge cases. Every later task that
needs one of these payload shapes should point at these files rather
than inventing a private copy — that duplication is exactly what this
task exists to prevent.

- `tokenizer/abbreviation_corpus.json` — the abbreviation-heavy sentence
  corpus (`Fig. 2`, `vs.`, `et al.`, `e.g.`, `i.e.`, `Dr.`, `approx.`,
  species abbreviations, decimal numbers) used as a golden-file test by
  **both** Task 1D's backend tokenizer tests (SPEC.md §15.1, §6.5) and
  Task 2D's frontend playback-engine tests (§15.9). Each case pairs
  `raw_text` with the correct `expected_sentences` split, so it doubles
  as an assertion fixture, not just prose to eyeball.
- `pubmed/esearch_response.json` / `esearch_zero_results.json` —
  ESearch-shaped payloads (§7.3) for Task 1B's respx-mocked tests: a
  normal 3-result page and the zero-result edge case (§7.9/§4.3).
- `pubmed/esummary_response.json` — ESummary-shaped payload (§7.4) for
  the same 3 PMIDs, including one record with a missing DOI (§13.4).
- `pubmed/efetch_response.xml` — EFetch `retmode=xml` payload (§7.5) for
  the same 3 PMIDs: one normal structured abstract (deliberately reusing
  the tokenizer corpus's `Fig.`/`vs.`/`et al.` sentences), one marked
  `Retracted Publication` (§13.4's badge case), and one non-English
  (`Language=fre`) record with no English translation (§13.3's
  language-mismatch case).
- `pubmed/icite_response.json` — iCite batch response (§7.6), including
  a PMID absent from `data` to exercise the nullable-citation-count case.
- `zotero/collections_response.json` — pyzotero-shaped `collections()`
  response (§8.4) for Task 1C's mocked client tests and Task 2C's MSW
  handlers.
- `zotero/item_creation_response.json` — pyzotero-shaped
  `create_items()` response (§8.6) with one successful and one failed
  item, for exercising the partial-batch-failure path (§8.7) that
  `CONTRACTS.md`'s `ZoteroPushResult` shape exists to report cleanly.

All PMIDs across the PubMed fixtures are cross-consistent (`38279812`,
`38279813`, `37000001`) so a test can chain ESearch → ESummary → EFetch
against the same fake queue without PMID mismatches.
