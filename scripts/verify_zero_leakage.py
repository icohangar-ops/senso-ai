#!/usr/bin/env python3
"""Evidence check: zero document leakage through the PrivateRAGEngine.

Backs README "Zero Leakage Guarantee" and docs/auth0-fga-integration.md
"Security Guarantees": a document the user is not authorized to read never
reaches the LLM context, never appears in the answer, and never appears in a
source citation; every returned source carries access_verified=True.

Runs offline with duck-typed FGA/vector/LLM fakes. Exit 0 = held.
"""
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
    from retrieval.rag_engine import FilteredResult, PrivateRAGEngine

    ALLOWED_DOC = "document:public-notes"
    DENIED_DOC = "document:salary-confidential"

    class FakeFGA:
        """can_query granted; post-filter denies the salary document."""

        def check_access(self, user_id, relation, resource_id):
            return AccessDecision(
                allowed=True,
                resource_id=resource_id,
                relation=relation,
                reason="fake: can_query granted",
            )

        def list_resources(self, user_id, relation, resource_type=None):
            # Pre-filter allowlist includes both ids (a stale grant on the
            # salary document) — the post-filter must catch it.
            return [ALLOWED_DOC, DENIED_DOC]

        def batch_check_access(self, user_id, items):
            decisions = []
            for relation, resource_id in items:
                allowed = resource_id == ALLOWED_DOC
                decisions.append(
                    AccessDecision(
                        allowed=allowed,
                        resource_id=resource_id,
                        relation=relation,
                        reason="fake allow" if allowed else "fake: denied by FGA",
                    )
                )
            return decisions

    class FakeVectorStore:
        def similarity_search(self, query_text, top_k, metadata_filter):
            # Deliberately returns BOTH documents regardless of the pre-filter
            # constraint, to prove the post-filter alone prevents leakage.
            return [
                FilteredResult(
                    document_id=ALLOWED_DOC,
                    content="quarterly public product notes",
                    score=0.95,
                    metadata={"title": "Public Notes", "repository": "computer-vision-ai"},
                ),
                FilteredResult(
                    document_id=DENIED_DOC,
                    content="TOP SECRET salary bands and executive compensation",
                    score=0.93,
                    metadata={"title": "Salary Confidential", "repository": "financial-data-ai"},
                ),
            ]

    class FakeLLM:
        def __init__(self):
            self.last_prompt = None

        def generate(self, prompt, system_message=None, temperature=0.1, max_tokens=1024):
            self.last_prompt = prompt
            return "answer-from-llm"

    llm = FakeLLM()
    engine = PrivateRAGEngine(fga_client=FakeFGA(), vector_store=FakeVectorStore(), llm_client=llm)
    response = engine.query(user_id="user:alice", question="What are the salary bands?")

    # The denied document never enters the LLM prompt or the answer.
    assert llm.last_prompt is not None
    assert "salary-confidential" not in llm.last_prompt, "denied document id reached the LLM context"
    assert "TOP SECRET" not in llm.last_prompt, "denied document content reached the LLM context"
    assert "salary-confidential" not in response.answer
    assert "TOP SECRET" not in response.answer

    # Sources are only the authorized, verified documents.
    assert [s.document_id for s in response.sources] == [ALLOWED_DOC]
    assert all(s.access_verified is True for s in response.sources)

    # The README's documented response shape holds.
    assert isinstance(response.answer, str) and response.answer
    # The post-filter removes denied candidates before the RAG engine's
    # context loop (RAGResponse.access_denied_count only counts step-3 loop
    # drops, which cannot trigger after stage-2 removal); the denial count is
    # surfaced in the retrieval audit record instead.
    import logging as _logging

    _audit_records = []

    class _Capture(_logging.Handler):
        def emit(self, record):
            _audit_records.append(record.getMessage())

    audit_logger = _logging.getLogger("auth0_fga.audit")
    previous_level = audit_logger.level
    audit_logger.setLevel(_logging.INFO)
    handler = _Capture(level=_logging.DEBUG)
    audit_logger.addHandler(handler)
    try:
        response = engine.query(user_id="user:alice", question="What are the salary bands?")
    finally:
        audit_logger.removeHandler(handler)
        audit_logger.setLevel(previous_level)
    audit_text = "\n".join(_audit_records)
    assert "post_filtered=1" in audit_text, f"post-filter denial not recorded: {audit_text!r}"

    # ---- can_query denied -> hard early denial, no retrieval at all -------
    class DenyingFGA(FakeFGA):
        def check_access(self, user_id, relation, resource_id):
            return AccessDecision(
                allowed=False,
                resource_id=resource_id,
                relation=relation,
                reason="fake: can_query denied",
            )

    engine_denied = PrivateRAGEngine(
        fga_client=DenyingFGA(), vector_store=FakeVectorStore(), llm_client=FakeLLM()
    )
    response_denied = engine_denied.query(user_id="user:mallory", question="salary bands")
    assert response_denied.sources == []
    assert "Access denied" in response_denied.answer

    print("verify_zero_leakage: PASS (denied doc absent from context/answer/citations; sources access-verified; can_query gate denies closed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
