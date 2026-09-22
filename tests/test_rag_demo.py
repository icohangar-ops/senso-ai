"""The packaged demo runs offline in simulated mode with per-user access."""
import contextlib
import io
import os
import runpy

from auth0_fga_rag.document_store import SAMPLE_DOCUMENTS


def test_demo_runs_simulated():
    # No Auth0 token -> simulated in-memory FGA.
    os.environ.pop("AUTH0_FGA_API_TOKEN", None)
    os.environ.pop("AUTH0_FGA_STORE_ID", None)

    assert len(SAMPLE_DOCUMENTS) == 14

    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        runpy.run_module("auth0_fga_rag.demo", run_name="__main__")
    output = captured.getvalue()

    assert "Demo Complete" in output, "demo did not reach its completion banner"
    assert "DENIED" in output, "demo output showed no FGA denials"
    for user_name in (
        "Alice (Finance Manager)",
        "Bob (HR Intern)",
        "Carol (Engineering Analyst)",
        "Dave (CEO / Executive)",
    ):
        assert user_name in output, f"demo output missing per-user section: {user_name}"
