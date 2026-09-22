"""Zero-leakage: unauthorized documents never reach the LLM or citations."""
from auth0_fga.models import AccessDecision
from retrieval.rag_engine import FilteredResult, PrivateRAGEngine

ALLOWED_DOC = "document:public-notes"
DENIED_DOC = "document:salary-confidential"


class FakeFGA:
    def check_access(self, user_id, relation, resource_id):
        return AccessDecision(allowed=True, resource_id=resource_id, relation=relation, reason="fake")

    def list_resources(self, user_id, relation, resource_type=None):
        return [ALLOWED_DOC, DENIED_DOC]  # stale grant on the salary document

    def batch_check_access(self, user_id, items):
        return [
            AccessDecision(
                allowed=resource_id == ALLOWED_DOC,
                resource_id=resource_id,
                relation=relation,
                reason="fake" if resource_id == ALLOWED_DOC else "denied by FGA",
            )
            for relation, resource_id in items
        ]


class FakeVectorStore:
    def similarity_search(self, query_text, top_k, metadata_filter):
        # Ignores the pre-filter constraint on purpose: the post-filter alone
        # must prevent the leak.
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


def test_unauthorized_document_never_reaches_answer():
    llm = FakeLLM()
    engine = PrivateRAGEngine(fga_client=FakeFGA(), vector_store=FakeVectorStore(), llm_client=llm)
    response = engine.query(user_id="user:alice", question="What are the salary bands?")

    assert "salary-confidential" not in llm.last_prompt, "denied document id reached the LLM context"
    assert "TOP SECRET" not in llm.last_prompt, "denied document content reached the LLM context"
    assert "salary-confidential" not in response.answer
    assert [s.document_id for s in response.sources] == [ALLOWED_DOC]
    assert all(s.access_verified is True for s in response.sources)
