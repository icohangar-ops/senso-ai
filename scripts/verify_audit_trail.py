#!/usr/bin/env python3
"""Evidence check: structured audit trail for every access decision.

Backs README "Audit Trail" and docs/auth0-fga-integration.md "Security
Guarantees" (Full audit trail): a retrieval emits an audit record with the
user id, query text, candidate counts before/after filtering, and latency;
each denial is logged with the document, reason, and decision id.

Runs offline with a duck-typed FGA fake. Exit 0 = held.
"""
import logging
import sys
import types
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _bootstrap_stubs() -> None:
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

    records = []

    class CaptureHandler(logging.Handler):
        def emit(self, record):
            records.append(record.getMessage())

    audit_logger = logging.getLogger("auth0_fga.audit")
    # The retrieval audit record is INFO-level; without an explicit level the
    # logger inherits WARNING from the root logger and drops it.
    previous_level = audit_logger.level
    audit_logger.setLevel(logging.INFO)
    handler = CaptureHandler(level=logging.DEBUG)
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

    audit_text = "\n".join(records)
    # Retrieval audit line: user, query, counts before/after, latency.
    assert "AUDIT retrieval" in audit_text
    assert "user=user:alice" in audit_text
    assert "query='company outlook'" in audit_text
    assert "total=2" in audit_text, "candidate count before filtering missing"
    assert "post_filtered=1" in audit_text, "post-filter count missing"
    assert "final=1" in audit_text, "final count missing"
    assert "latency_ms=" in audit_text
    # Denial audit line: document, reason, decision id.
    assert "AUDIT denial" in audit_text
    assert "document=document:secret-1" in audit_text
    assert "reason=no reader relation" in audit_text
    assert "decision_id=" in audit_text

    print("verify_audit_trail: PASS (retrieval audit with user/query/counts/latency; denial audit with document/reason/decision id)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
