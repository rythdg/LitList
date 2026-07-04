"""Authentication-adjacent backend concerns (BuildPlan.md Task 1C).

Currently just the Zotero OAuth 1.0a handshake (`app.auth.oauth`). This
package holds handshake *logic* only — no FastAPI route handlers live
here (those are Task 3B's job, wiring `app/routes/zotero.py` on top of the
functions this module exposes).
"""
