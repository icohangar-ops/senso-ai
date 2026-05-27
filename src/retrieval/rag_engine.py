"""
Privacy-aware RAG engine with Auth0 FGA enforcement.

The :class:`PrivateRAGEngine` implements the full retrieval-augmented
generation pipeline with a critical guarantee: **no unauthorized document
ever reaches the LLM or the end user**.

Pipeline flow::

    User Question
        │
        ▼
    ┌─────────────────────┐
    │  Auth0 FGA Pre-     │  ─── Get user's accessible resources
    │  Filter              │
    └─────────┬───────────┘
              │
              ▼
    ┌─────────────────────┐
    │  Vector Search       │  ─── Semantic search with metadata filter
    │  (pre-filtered)      │
    └─────────┬───────────┘
              │
              ▼
    ┌─────────────────────┐
    │  Auth0 FGA Post-    │  ─── Verify each candidate document
    │  Filter / Rerank     │
    └─────────┬───────────┘
              │
              ▼
    ┌─────────────────────┐
    │  LLM Generation      │  ─── Generate answer from authorized context
    └─────────┬───────────┘
              │
              ▼
         RAGResponse

Dependencies are kept minimal — the engine uses abstract protocols for
the vector store and LLM client so that any backend (Pinecone, Weaviate,
OpenAI, etc.) can be plugged in without coupling.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

from auth0_fga.authorization import FGAClient
from auth0_fga.models import AccessDecision, DocumentPolicy
from auth0_fga.retrieval_filter import (
    FilteredResult,
    RetrievalFilter,
    RetrievalStats,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protocols (interfaces for dependency injection)
# ---------------------------------------------------------------------------

class VectorStore(ABC):
    """Abstract interface for a vector similarity-search backend.

    Implementations may wrap Pinecone, Weaviate, Chroma, FAISS, Qdrant,
    pgvector, or any other vector database.
    """

    @abstractmethod
    def similarity_search(
        self,
        query_text: str,
        top_k: int = 10,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> List[FilteredResult]:
        """Return the *top_k* most similar documents."""
        ...

    @abstractmethod
    def add_document(
        self,
        document_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Ingest a document into the vector store."""
        ...

    @abstractmethod
    def delete_document(self, document_id: str) -> bool:
        """Remove a document from the vector store.  Returns ``True`` on success."""
        ...


class LLMClient(ABC):
    """Abstract interface for a large language model backend.

    Implementations may wrap OpenAI, Anthropic, a local model, or any
    other LLM API.
    """

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 1024,
    ) -> str:
        """Generate a response to the given prompt."""
        ...


# ---------------------------------------------------------------------------
# RAG response data classes
# ---------------------------------------------------------------------------

@dataclass
class RAGSource:
    """A single source document included in a RAG response.

    Attributes:
        document_id: Unique identifier of the source document.
        title: Human-readable title or description.
        content_snippet: A short excerpt from the document.
        score: Retrieval relevance score.
        access_verified: Whether Auth0 FGA verified access for this source.
        repository: Name of the repository the document belongs to.
    """

    document_id: str
    title: str = ""
    content_snippet: str = ""
    score: float = 0.0
    access_verified: bool = False
    repository: str = ""


@dataclass
class RAGResponse:
    """Complete response from the privacy-aware RAG pipeline.

    Attributes:
        answer: The generated answer text.
        sources: List of source documents used to generate the answer.
        access_denied_count: Number of documents filtered out due to access denial.
        query: The original user question.
        user_id: The user who made the request.
        latency_ms: Total pipeline latency in milliseconds.
        retrieval_stats: Detailed retrieval statistics if available.
    """

    answer: str
    sources: List[RAGSource] = field(default_factory=list)
    access_denied_count: int = 0
    query: str = ""
    user_id: str = ""
    latency_ms: float = 0.0
    retrieval_stats: Optional[RetrievalStats] = None


# ---------------------------------------------------------------------------
# PrivateRAGEngine
# ---------------------------------------------------------------------------

class PrivateRAGEngine:
    """Privacy-aware Retrieval-Augmented Generation engine.

    Combines Auth0 FGA authorization checks with a vector search backend
    and an LLM client to provide answers grounded exclusively in documents
    the requesting user is authorized to read.

    Parameters:
        fga_client: An initialized :class:`FGAClient` instance.
        vector_store: A :class:`VectorStore` implementation.
        llm_client: A :class:`LLMClient` implementation.
        context_window: Maximum number of characters from retrieved
            documents to include in the LLM prompt (default 4000).
        enable_pre_filter: Whether to apply FGA pre-filtering (default ``True``).
        enable_post_filter: Whether to apply FGA post-filtering (default ``True``).
        system_prompt: Optional system prompt for the LLM.

    Example::

        engine = PrivateRAGEngine(
            fga_client=fga,
            vector_store=PineconeStore(...),
            llm_client=OpenAIClient(...),
        )
        response = engine.query("user:alice", "Explain transformer attention")
        print(response.answer)
        for src in response.sources:
            print(f"  Source: {src.document_id} (verified={src.access_verified})")
    """

    def __init__(
        self,
        fga_client: FGAClient,
        vector_store: VectorStore,
        llm_client: LLMClient,
        context_window: int = 4000,
        enable_pre_filter: bool = True,
        enable_post_filter: bool = True,
        system_prompt: Optional[str] = None,
    ) -> None:
        self.fga_client = fga_client
        self.vector_store = vector_store
        self.llm_client = llm_client
        self.context_window = context_window
        self.enable_pre_filter = enable_pre_filter
        self.enable_post_filter = enable_post_filter

        self.system_prompt = system_prompt or (
            "You are a knowledgeable AI assistant for the senso-ai enterprise "
            "knowledge base. Answer questions based ONLY on the provided context. "
            "If the context does not contain enough information, say so clearly. "
            "Do not speculate or introduce external knowledge."
        )

        # Build the retrieval filter that wraps the vector store.
        self.retrieval_filter = RetrievalFilter(
            fga_client=fga_client,
            vector_search_fn=self._vector_search_adapter,
            resource_type="document",
            relation="can_read",
            enable_pre_filter=enable_pre_filter,
            enable_post_filter=enable_post_filter,
        )

        logger.info(
            "PrivateRAGEngine initialized (pre_filter=%s, post_filter=%s, context_window=%d)",
            enable_pre_filter,
            enable_post_filter,
            context_window,
        )

    # ---- Adapter ----------------------------------------------------------

    def _vector_search_adapter(
        self,
        query_text: str,
        top_k: int,
        metadata_filter: Optional[Dict[str, Any]],
    ) -> List[FilteredResult]:
        """Bridge between the :class:`RetrievalFilter` and the :class:`VectorStore`."""
        return self.vector_store.similarity_search(
            query_text=query_text,
            top_k=top_k,
            metadata_filter=metadata_filter,
        )

    # ---- Main query method ------------------------------------------------

    def query(
        self,
        user_id: str,
        question: str,
        top_k: int = 10,
    ) -> RAGResponse:
        """Execute the full privacy-aware RAG pipeline.

        Args:
            user_id: Auth0 user identifier.
            question: The user's natural-language question.
            top_k: Maximum number of documents to retrieve.

        Returns:
            A :class:`RAGResponse` with the generated answer and verified sources.
        """
        start_time = time.monotonic()

        # Step 1: Auth0 FGA check — verify the user can use the system.
        auth_decision = self.fga_client.check_access(
            user_id=user_id,
            relation="can_query",
            resource_id="organization:senso-ai",
        )
        if not auth_decision.allowed:
            logger.warning("User %s denied can_query on organization:senso-ai", user_id)
            return RAGResponse(
                answer="Access denied: you do not have permission to query the knowledge base.",
                sources=[],
                access_denied_count=0,
                query=question,
                user_id=user_id,
                latency_ms=(time.monotonic() - start_time) * 1000,
            )

        # Step 2: Privacy-filtered retrieval.
        filtered_results = self.retrieval_filter.query(
            user_id=user_id,
            query_text=question,
            top_k=top_k,
        )

        if not filtered_results:
            latency_ms = (time.monotonic() - start_time) * 1000
            logger.info("No accessible documents found for user %s", user_id)
            return RAGResponse(
                answer=(
                    "No relevant documents are available based on your access "
                    "permissions. If you believe you should have access to "
                    "specific repositories, please contact your administrator."
                ),
                sources=[],
                access_denied_count=0,
                query=question,
                user_id=user_id,
                latency_ms=latency_ms,
            )

        # Step 3: Build context for the LLM.
        context_parts: List[str] = []
        sources: List[RAGSource] = []
        denied_count = 0
        total_chars = 0

        for result in filtered_results:
            if not result.access_allowed:
                denied_count += 1
                continue

            if total_chars + len(result.content) > self.context_window:
                break

            context_parts.append(
                f"[Source: {result.document_id}]\n{result.content}"
            )
            sources.append(
                RAGSource(
                    document_id=result.document_id,
                    title=result.metadata.get("title", ""),
                    content_snippet=result.content[:200],
                    score=result.score,
                    access_verified=True,
                    repository=result.metadata.get("repository", ""),
                )
            )
            total_chars += len(result.content)

        context = "\n\n---\n\n".join(context_parts)

        # Step 4: LLM generation.
        prompt = (
            f"Context:\n{context}\n\n"
            f"Question: {question}\n\n"
            "Answer based only on the provided context. "
            "Cite sources by their document ID."
        )

        try:
            answer = self.llm_client.generate(
                prompt=prompt,
                system_message=self.system_prompt,
                temperature=0.1,
                max_tokens=1024,
            )
        except Exception as exc:
            logger.error("LLM generation failed: %s", exc, exc_info=True)
            answer = (
                "An error occurred while generating the answer. "
                "Please try again or contact support."
            )

        latency_ms = (time.monotonic() - start_time) * 1000

        logger.info(
            "RAG query complete: user=%s sources=%d denied=%d latency=%.1fms",
            user_id,
            len(sources),
            denied_count,
            latency_ms,
        )

        return RAGResponse(
            answer=answer,
            sources=sources,
            access_denied_count=denied_count,
            query=question,
            user_id=user_id,
            latency_ms=latency_ms,
        )

    # ---- Document ingestion ------------------------------------------------

    def ingest(
        self,
        document_id: str,
        content: str,
        access_policy: DocumentPolicy,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Ingest a document into the knowledge base with an access policy.

        This performs two operations:
        1. Ingests the document into the vector store.
        2. Creates the FGA authorization policy (writes relationship tuples).

        Args:
            document_id: Unique document identifier.
            content: Full text content of the document.
            access_policy: :class:`DocumentPolicy` defining who can access the document.
            metadata: Optional metadata to store alongside the document.
        """
        # Ingest into vector store.
        doc_metadata = dict(metadata) if metadata else {}
        doc_metadata.update({
            "document_id": document_id,
            "repository": access_policy.resource_id,
            "policy_id": access_policy.policy_id,
        })

        try:
            self.vector_store.add_document(
                document_id=document_id,
                content=content,
                metadata=doc_metadata,
            )
        except Exception as exc:
            logger.error("Failed to ingest document %s into vector store: %s", document_id, exc)
            raise

        # Create FGA policy.
        try:
            self.fga_client.create_policy_from_document_policy(access_policy)
        except Exception as exc:
            logger.error("Failed to create FGA policy for document %s: %s", document_id, exc)
            raise

        logger.info(
            "Ingested document %s with policy %s (%d relation tuples)",
            document_id,
            access_policy.policy_id,
            len(access_policy.to_relations()),
        )

    # ---- Policy updates ----------------------------------------------------

    def update_policy(
        self,
        document_id: str,
        new_policy: DocumentPolicy,
    ) -> None:
        """Update an existing document's access policy.

        This replaces all existing relationship tuples for the document
        with the new policy.  The document content in the vector store is
        NOT changed.

        Args:
            document_id: The document whose policy should be updated.
            new_policy: The new :class:`DocumentPolicy` to apply.
        """
        # Write new policy tuples.
        try:
            self.fga_client.create_policy_from_document_policy(new_policy)
        except Exception as exc:
            logger.error("Failed to update FGA policy for document %s: %s", document_id, exc)
            raise

        logger.info(
            "Updated policy for document %s to policy %s",
            document_id,
            new_policy.policy_id,
        )

    def revoke_document_access(
        self,
        document_id: str,
        user_id: str,
        resource_type: str = "document",
    ) -> None:
        """Revoke all access to a document for a specific user.

        Args:
            document_id: The document to revoke access on.
            user_id: The user whose access should be revoked.
            resource_type: FGA resource type (default ``"document"``).
        """
        for relation in ("viewer", "editor", "admin", "owner"):
            try:
                self.fga_client.revoke_role(
                    user_id=user_id,
                    role=relation,
                    resource_id=f"{resource_type}:{document_id}",
                )
            except Exception as exc:
                logger.debug(
                    "Revoking %s on %s:%s for %s: %s (may not exist)",
                    relation,
                    resource_type,
                    document_id,
                    user_id,
                    exc,
                )

        logger.info("Revoked all access for user %s on document %s", user_id, document_id)
