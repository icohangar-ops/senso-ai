#!/usr/bin/env python3
"""Evidence check: the packaged demo runs offline and enforces per-user access.

Backs auth0_fga_rag/README.md "Run the Demo" (``python -m
auth0_fga_rag.demo`` requires no Auth0 credentials — simulated mode) and
"Sample Documents" (the demo's document set and its per-user access mapping).

Runs fully offline: ``requests`` (live-API path only) and any ambient Auth0
token are neutralized so the FGA client stays in in-memory simulated mode.
Exit 0 = held.
"""
import contextlib
import io
import os
import runpy
import sys
import types
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _bootstrap_stubs() -> None:
    # auth0_fga_rag/fga_client.py imports requests at module top; the demo's
    # simulated mode never calls it. A module-level stub keeps this check
    # deterministic in a bare CI environment (no install step precedes the
    # evidence gate). The real package is preferred when installed.
    try:
        import requests  # noqa: F401
    except ImportError:
        stub = types.ModuleType("requests")
        stub.post = None  # live-API calls would fail loudly if ever reached
        sys.modules["requests"] = stub
    # No Auth0 token -> fga_config.SIMULATED_MODE is True (in-memory FGA).
    os.environ.pop("AUTH0_FGA_API_TOKEN", None)
    os.environ.pop("AUTH0_FGA_STORE_ID", None)
    sys.path.insert(0, str(REPO_ROOT))


def main() -> int:
    _bootstrap_stubs()
    from auth0_fga_rag.document_store import SAMPLE_DOCUMENTS, DocumentStore
    from auth0_fga_rag.fga_client import FGAClient, AuthorizationTuple

    # The committed document set the README documents.
    assert len(SAMPLE_DOCUMENTS) == 14, f"expected 14 sample documents, found {len(SAMPLE_DOCUMENTS)}"

    def build_fga(user: str, readable) -> FGAClient:
        fga = FGAClient(store_id="evidence-check")
        fga.write_tuples(
            [AuthorizationTuple(user=user, relation="reader", object=f"document:{d.doc_id}") for d in readable]
        )
        return fga

    store = DocumentStore(SAMPLE_DOCUMENTS)

    # CEO: unrestricted access to all 14 documents.
    dave = build_fga("user:dave", SAMPLE_DOCUMENTS)
    assert all(dave.check("user:dave", d.fga_object_id, "reader") for d in SAMPLE_DOCUMENTS)

    # HR intern: public docs only — salary/executive/finance are denied.
    public = [d for d in SAMPLE_DOCUMENTS if d.department == "Public"]
    assert len(public) == 3
    bob = build_fga("user:bob", public)
    for doc_id in ("document:salary_band_guide", "document:executive_comp_report", "document:ma_strategy_2025"):
        assert not bob.check("user:bob", doc_id, "reader"), f"Bob was granted {doc_id}"

    # Finance manager: finance docs and the salary guide, not executive strategy.
    alice_docs = [d for d in SAMPLE_DOCUMENTS if d.department in ("Finance", "Public")] + [
        d for d in SAMPLE_DOCUMENTS if d.doc_id == "salary_band_guide"
    ]
    alice = build_fga("user:alice", alice_docs)
    assert alice.check("user:alice", "document:salary_band_guide", "reader")
    assert alice.check("user:alice", "document:budget_Q4_2025", "reader")
    assert not alice.check("user:alice", "document:ma_strategy_2025", "reader")

    # Store search is FGA-filtered: Bob's results never contain a denied document.
    for doc, _score in store.search("salary compensation bands", "user:bob", bob, top_k=10):
        assert doc.department == "Public", f"leaked {doc.doc_id} to unauthorized user"

    # The documented command runs end-to-end in simulated mode.
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        runpy.run_module("auth0_fga_rag.demo", run_name="__main__")
    output = captured.getvalue()
    assert "Demo Complete" in output, "demo did not reach its completion banner"
    assert "DENIED" in output, "demo output showed no FGA denials"
    for user_name in ("Alice (Finance Manager)", "Bob (HR Intern)", "Carol (Engineering Analyst)", "Dave (CEO / Executive)"):
        assert user_name in output, f"demo output missing per-user section: {user_name}"

    print("verify_rag_demo: PASS (demo runs offline in simulated mode; 14 docs; Bob denied salary/executive; Dave unrestricted; search is FGA-filtered)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
