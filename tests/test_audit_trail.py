"""Audit trail: retrieval and denial records carry the documented fields."""
import logging

from auth0_fga.models import AccessDecision
from auth0_fga.retrieval_filter import FilteredResult, RetrievalFilter


class FakeFGA:
    def __init__(self):
        self._denied = {"document:secret-1"}

    def list_resources(self, user_id, relation, resource_type=None):
        return ["document:public-1", "document:secret-1"]

    def batch_check_access(self, user_id, items):
        return [
            AccessDecision(
                allowed=resource_id not in self._denied,
                resource_id=resource_id,
                relation=relation,
                reason="ok" if resource_id not in self._denied else "no reader relation",
            )
            for relation, resource_id in items
        ]


def test_audit_records_include_user_query_counts_and_denials():
    records = []

    class Capture(logging.Handler):
        def emit(self, record):
            records.append(record.getMessage())

    audit_logger = logging.getLogger("auth0_fga.audit")
    previous_level = audit_logger.level
    audit_logger.setLevel(logging.INFO)
    handler = Capture(level=logging.DEBUG)
    audit_logger.addHandler(handler)
    try:
        rfilter = RetrievalFilter(
            fga_client=FakeFGA(),
            vector_search_fn=lambda q, top_k, meta: [
                FilteredResult(document_id="document:public-1", content="public", score=0.9),
                FilteredResult(document_id="document:secret-1", content="secret", score=0.8),
            ],
        )
        results = rfilter.query("user:alice", "company outlook", top_k=5)
    finally:
        audit_logger.removeHandler(handler)
        audit_logger.setLevel(previous_level)

    assert len(results) == 1 and results[0].document_id == "document:public-1"
    text = "\n".join(records)
    assert "AUDIT retrieval" in text
    assert "user=user:alice" in text
    assert "query='company outlook'" in text
    assert "total=2" in text and "post_filtered=1" in text and "final=1" in text
    assert "AUDIT denial" in text
    assert "document=document:secret-1" in text
    assert "reason=no reader relation" in text
    assert "decision_id=" in text
