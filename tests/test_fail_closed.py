"""Fail-closed semantics: FGA errors deny rather than allow."""
import auth0_fga.authorization as authorization_module
from auth0_fga.models import AccessDecision
from auth0_fga.retrieval_filter import FilteredResult, RetrievalFilter


class ErrorFGA:
    """Every FGA interaction raises — the system must deny, never allow."""

    def check_access(self, user_id, relation, resource_id):
        raise RuntimeError("FGA service down")

    def list_resources(self, user_id, relation, resource_type=None):
        raise RuntimeError("FGA service down")

    def batch_check_access(self, user_id, items):
        raise RuntimeError("FGA service down")


def test_fga_errors_deny_access():
    client = authorization_module.FGAClient(api_url="https://fga.example", api_token="t", store_id="s")

    def raise_unavailable(*args, **kwargs):
        raise authorization_module.FGAUnavailableError("FGA service down")

    client._request = raise_unavailable  # type: ignore[method-assign]

    # Service outage denies closed: check_access returns AccessDecision(allowed=False).
    decision = client.check_access("user:alice", "can_read", "document:q3-revenue")
    assert isinstance(decision, AccessDecision)
    assert decision.allowed is False
    assert decision.reason.startswith("FGA service error"), decision.reason

    # batch_check_access: one denied decision per item.
    decisions = client.batch_check_access(
        "user:alice",
        [("can_read", "document:a"), ("can_read", "document:b")],
    )
    assert len(decisions) == 2 and all(d.allowed is False for d in decisions)


def test_prefilter_failure_returns_empty_not_error():
    rfilter = RetrievalFilter(
        fga_client=ErrorFGA(),
        vector_search_fn=lambda q, top_k, meta: [
            FilteredResult(document_id="document:d1", content="c", score=0.9)
        ],
    )
    results = rfilter.query("user:u", "query", top_k=5)
    assert results == []
