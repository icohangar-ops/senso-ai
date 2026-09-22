#!/usr/bin/env python3
"""Evidence check: the RAG retrieval filter is dual-stage (pre-filter + post-filter).

Backs README "Dual-Stage Authorization": the pre-filter scopes the vector
search to resources the user can access, and the post-filter re-verifies every
candidate so stale grants cannot leak a revoked document through.

Runs offline: the FGA client is a duck-typed fake carrying canned decisions,
so no network is touched. Exit 0 = every assertion held.
"""
import sys
import types
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _bootstrap_stubs() -> None:
    """Make the src/ packages importable without installed dependencies.

    ``auth0_fga/authorization.py`` hard-imports ``cubiczan_resilience`` (the
    retry wrapper). The wrapper is a passthrough whenever the wrapped call
    succeeds, which is the only path exercised here, so a stdlib stub keeps
    this check deterministic in a bare CI environment. The real package is
    preferred when it is installed.
    """
    try:
        import cubiczan_resilience  # noqa: F401
    except ImportError:
        stub = types.ModuleType("cubiczan_resilience")

        def _passthrough(*decorator_args, **decorator_kwargs):
            def decorator(fn):
                return fn

            return decorator

        stub.resilient = _passthrough
        stub.RetriesExhausted = type("RetriesExhausted", (Exception,), {})
        sys.modules["cubiczan_resilience"] = stub
    sys.path.insert(0, str(REPO_ROOT / "src"))


def main() -> int:
    _bootstrap_stubs()
    from auth0_fga.models import AccessDecision
    from auth0_fga.retrieval_filter import FilteredResult, RetrievalFilter

    class FakeFGAClient:
        """Duck-typed FGAClient with canned allow/deny sets — no network."""

        def __init__(self, accessible_ids, denied_ids):
            self._accessible = set(accessible_ids)
            self._denied = set(denied_ids)
            self.list_resources_calls = []
            self.batch_calls = []
            self.search_metadata_filters = []

        def list_resources(self, user_id, relation, resource_type=None):
            self.list_resources_calls.append((user_id, relation, resource_type))
            return sorted(self._accessible)

        def batch_check_access(self, user_id, items):
            self.batch_calls.append(items)
            decisions = []
            for relation, resource_id in items:
                allowed = resource_id in self._accessible and resource_id not in self._denied
                decisions.append(
                    AccessDecision(
                        allowed=allowed,
                        resource_id=resource_id,
                        relation=relation,
                        reason="fake allow" if allowed else "fake denial (stale grant)",
                    )
                )
            return decisions

    def fake_vector_search(query_text, top_k, metadata_filter):
        store.last_metadata_filter = metadata_filter
        # Ignore the pre-filter constraint on purpose: the post-filter must
        # still drop documents the pre-filter's (possibly stale) allowlist
        # let through.
        return [
            FilteredResult(document_id="document:allowed-1", content="public notes", score=0.9),
            FilteredResult(document_id="document:revoked-1", content="revoked salary data", score=0.8),
        ]

    store = types.SimpleNamespace(last_metadata_filter=None)

    # ---- Stage 1+2+3 happy path with one stale grant ----------------------
    fga = FakeFGAClient(
        accessible_ids={"document:allowed-1", "document:revoked-1"},
        denied_ids={"document:revoked-1"},
    )
    rfilter = RetrievalFilter(fga_client=fga, vector_search_fn=fake_vector_search)
    results = rfilter.query("user:alice", "salary", top_k=5)

    # Pre-filter: accessible ids were fetched and injected into the search.
    assert fga.list_resources_calls, "pre-filter never queried accessible resources"
    assert store.last_metadata_filter is not None, "pre-filter did not constrain the vector search"
    injected = store.last_metadata_filter.get("document_id", {}).get("$in")
    assert injected == ["document:allowed-1", "document:revoked-1"], injected

    # Post-filter: every candidate was re-verified...
    assert fga.batch_calls, "post-filter never re-verified candidates"
    checked = {resource_id for _relation, resource_id in fga.batch_calls[0]}
    assert checked == {"document:allowed-1", "document:revoked-1"}, checked

    # ...the stale-grant document was dropped after the vector search...
    assert [r.document_id for r in results] == ["document:allowed-1"], results

    # ...and only the authorized result comes back, verified.
    assert results[0].access_allowed is True
    assert results[0].filter_stage == "none"

    # ---- Fail-closed pre-filter: no accessible resources -> no results ----
    fga_empty = FakeFGAClient(accessible_ids=set(), denied_ids=set())
    rfilter_empty = RetrievalFilter(fga_client=fga_empty, vector_search_fn=fake_vector_search)
    assert rfilter_empty.query("user:nobody", "salary", top_k=5) == []

    print("verify_dual_stage_filter: PASS (pre-filter scoping, post-filter re-verification, fail-closed empty access)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
