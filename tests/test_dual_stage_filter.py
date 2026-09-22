"""Dual-stage authorization: pre-filter scoping and post-filter re-verification."""
from auth0_fga.models import AccessDecision
from auth0_fga.retrieval_filter import FilteredResult, RetrievalFilter

ALLOWED_DOC = "document:public-notes"
STALE_DOC = "document:revoked-1"


class FakeFGA:
    """Pre-filter allowlist includes a stale grant the post-filter must catch."""

    def list_resources(self, user_id, relation, resource_type=None):
        return [ALLOWED_DOC, STALE_DOC]

    def batch_check_access(self, user_id, items):
        return [
            AccessDecision(
                allowed=resource_id == ALLOWED_DOC,
                resource_id=resource_id,
                relation=relation,
                reason="ok" if resource_id == ALLOWED_DOC else "fake denial (stale grant)",
            )
            for relation, resource_id in items
        ]


def _candidates():
    return [
        FilteredResult(document_id=ALLOWED_DOC, content="public", score=0.9),
        FilteredResult(document_id=STALE_DOC, content="secret", score=0.8),
    ]


def test_dual_stage_pre_and_post_filter():
    rfilter = RetrievalFilter(
        fga_client=FakeFGA(),
        vector_search_fn=lambda q, top_k, meta: _candidates(),
    )
    results = rfilter.query("user:alice", "company outlook", top_k=5)
    # Post-filter re-verification removed the stale-grant document.
    assert [r.document_id for r in results] == [ALLOWED_DOC]
    assert all(r.access_allowed for r in results)
