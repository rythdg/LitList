"""Task 3C tests, SPEC.md §8.8 (CSV export column spec, CSV/formula-
injection neutralization) and §13.4 (missing-DOI handling), per §15.1.

Builds a minimal app (`SessionIdentityMiddleware` + the export router)
the same way `tests/test_session_middleware.py` does for Task 1A, rather
than importing the full `app.main.app` (which doesn't have the session
middleware wired in yet — that's Task 3D's job).
"""

from __future__ import annotations

import csv
import io

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlmodel import Session as DBSession
from sqlmodel import SQLModel

from app.middleware.session import SessionIdentityMiddleware
from app.models.entities import DecisionState, Paper, QueueDecision
from app.routes.export import _neutralize_formula_injection
from app.routes.export import router as export_router

# U+202E RIGHT-TO-LEFT OVERRIDE — a Unicode "format" (Cf) category
# character that renders invisibly but can flip the visual order of
# following text; used here as the "invisible character before a
# formula trigger" adversarial case.
_RTL_OVERRIDE = "‮"


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(SessionIdentityMiddleware)
    app.include_router(export_router)
    return app


def _client(db_engine: Engine) -> TestClient:
    SQLModel.metadata.create_all(db_engine)
    return TestClient(_make_app(), base_url="https://testserver")


def _establish_session(client: TestClient) -> str:
    """Hits any endpoint once so the middleware issues a session cookie,
    then returns that session_id."""
    response = client.get("/export.csv")
    assert response.status_code == 200
    from app.middleware.session import SESSION_COOKIE_NAME

    cookie_value = response.cookies[SESSION_COOKIE_NAME]
    session_id, _sig = cookie_value.rsplit(".", 1)
    return session_id


def _seed_paper(
    db_engine: Engine,
    *,
    pmid: str,
    title: str,
    authors: list[dict[str, str]],
    journal: str | None,
    pub_date: str | None,
    doi: str | None,
) -> Paper:
    with DBSession(db_engine) as db:
        paper = Paper(
            pmid=pmid,
            title=title,
            authors=authors,
            journal=journal,
            pub_date=pub_date,
            doi=doi,
        )
        db.add(paper)
        db.commit()
        db.refresh(paper)
        return paper


def _seed_decision(
    db_engine: Engine, *, session_id: str, pmid: str, position: int
) -> None:
    with DBSession(db_engine) as db:
        decision = QueueDecision(
            session_id=session_id,
            pmid=pmid,
            position=position,
            decision=DecisionState.interested,
        )
        db.add(decision)
        db.commit()


def _parse_csv(body: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(body)))


def test_export_returns_correct_column_set(db_engine) -> None:
    client = _client(db_engine)
    session_id = _establish_session(client)

    _seed_paper(
        db_engine,
        pmid="111",
        title="A Normal Title",
        authors=[{"first_name": "Ada", "last_name": "Lovelace"}],
        journal="Journal of Testing",
        pub_date="2024",
        doi="10.1234/abc",
    )
    _seed_decision(db_engine, session_id=session_id, pmid="111", position=0)

    response = client.get("/export.csv")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")

    rows = _parse_csv(response.text)
    assert rows[0] == ["Title", "Authors", "Journal", "Date", "DOI", "PMID", "URL"]
    assert rows[1] == [
        "A Normal Title",
        "Ada Lovelace",
        "Journal of Testing",
        "2024",
        "10.1234/abc",
        "111",
        "https://doi.org/10.1234/abc",
    ]


def test_missing_doi_exports_blank_doi_and_url_without_error(db_engine) -> None:
    client = _client(db_engine)
    session_id = _establish_session(client)

    _seed_paper(
        db_engine,
        pmid="222",
        title="An Old Record With No DOI",
        authors=[],
        journal=None,
        pub_date=None,
        doi=None,
    )
    _seed_decision(db_engine, session_id=session_id, pmid="222", position=0)

    response = client.get("/export.csv")
    assert response.status_code == 200

    rows = _parse_csv(response.text)
    assert len(rows) == 2  # header + one paper row, no crash
    header, row = rows
    doi_index = header.index("DOI")
    url_index = header.index("URL")
    assert row[doi_index] == ""
    assert row[url_index] == ""


@pytest.mark.parametrize(
    "adversarial_title",
    [
        "=1+1",
        "+CMD(1,2,'/C calc')!A1",
        "-2+3+cmd|' /C calc'!A1",
        "@SUM(1,2)",
    ],
)
def test_formula_injection_prefixes_are_neutralized(
    db_engine, adversarial_title: str
) -> None:
    client = _client(db_engine)
    session_id = _establish_session(client)

    _seed_paper(
        db_engine,
        pmid="333",
        title=adversarial_title,
        authors=[{"first_name": "=2+2", "last_name": "@evil"}],
        journal="+bad",
        pub_date="-1999",
        doi=None,
    )
    _seed_decision(db_engine, session_id=session_id, pmid="333", position=0)

    response = client.get("/export.csv")
    assert response.status_code == 200

    rows = _parse_csv(response.text)
    header, row = rows

    # Every cell in the data row must never have a raw formula-trigger
    # character as its literal first character.
    for cell in row:
        assert cell[:1] not in ("=", "+", "-", "@"), f"unneutralized cell: {cell!r}"

    # And the neutralization is specifically the documented leading
    # single-quote prefix, not e.g. silent stripping of the content.
    title_index = header.index("Title")
    assert row[title_index] == f"'{adversarial_title}"


@pytest.mark.parametrize(
    "adversarial_title",
    [
        "\t=1+1",
        " =1+1",
        f"{_RTL_OVERRIDE}=1+1",
    ],
    ids=["leading_tab", "leading_space", "leading_rtl_override"],
)
def test_formula_injection_neutralized_past_leading_whitespace_or_invisible_chars(
    db_engine, adversarial_title: str
) -> None:
    """Adversarial-review regression: a naive `str.startswith(...)` check
    misses a formula trigger hidden behind leading whitespace or an
    invisible Unicode format character (e.g. an RTL override) — some
    spreadsheet CSV importers strip those themselves before evaluating
    the trigger, so the importer's notion of "first character" can
    disagree with Python's raw indexing. All three variants here must
    still get neutralized, exactly like the bare `"=1+1"` case."""
    client = _client(db_engine)
    session_id = _establish_session(client)

    _seed_paper(
        db_engine,
        pmid="999",
        title=adversarial_title,
        authors=[],
        journal=None,
        pub_date=None,
        doi=None,
    )
    _seed_decision(db_engine, session_id=session_id, pmid="999", position=0)

    response = client.get("/export.csv")
    assert response.status_code == 200

    rows = _parse_csv(response.text)
    header, row = rows
    title_index = header.index("Title")

    assert row[title_index] == f"'{adversarial_title}"


@pytest.mark.parametrize(
    "value",
    [
        "\t=1+1",
        " =1+1",
        f"{_RTL_OVERRIDE}=1+1",
    ],
    ids=["leading_tab", "leading_space", "leading_rtl_override"],
)
def test_neutralize_formula_injection_unit_leading_whitespace_or_invisible_chars(
    value: str,
) -> None:
    """Direct unit-level check of `_neutralize_formula_injection` itself
    (in addition to the end-to-end route test above), pinning the exact
    contract: the single-quote prefix is applied to the *original*
    value, never a stripped copy."""
    assert _neutralize_formula_injection(value) == f"'{value}"


def test_export_only_includes_interested_decisions_for_current_session(
    db_engine,
) -> None:
    client = _client(db_engine)
    session_id = _establish_session(client)

    _seed_paper(
        db_engine,
        pmid="444",
        title="Saved Paper",
        authors=[],
        journal=None,
        pub_date=None,
        doi=None,
    )
    _seed_paper(
        db_engine,
        pmid="555",
        title="Not Saved Paper",
        authors=[],
        journal=None,
        pub_date=None,
        doi=None,
    )
    with DBSession(db_engine) as db:
        db.add(
            QueueDecision(
                session_id=session_id,
                pmid="444",
                position=0,
                decision=DecisionState.interested,
            )
        )
        db.add(
            QueueDecision(
                session_id=session_id,
                pmid="555",
                position=1,
                decision=DecisionState.pending,
            )
        )
        db.commit()

    response = client.get("/export.csv")
    rows = _parse_csv(response.text)
    titles = [row[0] for row in rows[1:]]
    assert titles == ["Saved Paper"]


def test_export_is_empty_but_valid_when_saved_list_is_empty(db_engine) -> None:
    client = _client(db_engine)
    _establish_session(client)

    response = client.get("/export.csv")
    assert response.status_code == 200
    rows = _parse_csv(response.text)
    assert rows == [["Title", "Authors", "Journal", "Date", "DOI", "PMID", "URL"]]


def test_export_never_leaks_another_sessions_saved_papers(db_engine) -> None:
    """§9.1/§9.2's session-scoping is the actual security boundary between
    two anonymous users' Saved Lists — one session's export must never
    include another session's `interested` decisions, even when both
    sessions have decisions on overlapping PMIDs. Uses two independent
    `TestClient` instances (separate cookie jars) against the *same* app/
    DB so each genuinely gets its own `session_id` via the middleware,
    rather than asserting this from reading the query alone."""
    app_instance = _make_app()
    SQLModel.metadata.create_all(db_engine)
    client_a = TestClient(app_instance, base_url="https://testserver")
    client_b = TestClient(app_instance, base_url="https://testserver")

    session_a = _establish_session(client_a)
    session_b = _establish_session(client_b)
    assert session_a != session_b

    # A paper only session A saved.
    _seed_paper(
        db_engine,
        pmid="666",
        title="Session A Only Paper",
        authors=[],
        journal=None,
        pub_date=None,
        doi=None,
    )
    # A paper only session B saved.
    _seed_paper(
        db_engine,
        pmid="777",
        title="Session B Only Paper",
        authors=[],
        journal=None,
        pub_date=None,
        doi=None,
    )
    # Both sessions have an `interested` decision on the SAME overlapping
    # PMID, each with its own row (distinct session_id) — the sharpest
    # version of the cross-session leak this test guards against.
    _seed_paper(
        db_engine,
        pmid="888",
        title="Shared Overlapping Paper",
        authors=[],
        journal=None,
        pub_date=None,
        doi=None,
    )

    with DBSession(db_engine) as db:
        db.add(
            QueueDecision(
                session_id=session_a,
                pmid="666",
                position=0,
                decision=DecisionState.interested,
            )
        )
        db.add(
            QueueDecision(
                session_id=session_b,
                pmid="777",
                position=0,
                decision=DecisionState.interested,
            )
        )
        db.add(
            QueueDecision(
                session_id=session_a,
                pmid="888",
                position=1,
                decision=DecisionState.interested,
            )
        )
        db.add(
            QueueDecision(
                session_id=session_b,
                pmid="888",
                position=1,
                decision=DecisionState.interested,
            )
        )
        db.commit()

    response_a = client_a.get("/export.csv")
    response_b = client_b.get("/export.csv")
    assert response_a.status_code == 200
    assert response_b.status_code == 200

    titles_a = {row[0] for row in _parse_csv(response_a.text)[1:]}
    titles_b = {row[0] for row in _parse_csv(response_b.text)[1:]}

    assert titles_a == {"Session A Only Paper", "Shared Overlapping Paper"}
    assert titles_b == {"Session B Only Paper", "Shared Overlapping Paper"}

    # The sharpest assertion: session A's export must never contain
    # session B's exclusive paper, and vice versa.
    assert "Session B Only Paper" not in titles_a
    assert "Session A Only Paper" not in titles_b
