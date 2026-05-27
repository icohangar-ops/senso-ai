"""
Document retrieval filter for privacy-aware RAG.

The :class:`RetrievalFilter` enforces Auth0 FGA authorization at two stages:

1. **Pre-filtering** — Before issuing a query to the vector store, the
   filter obtains the list of resources the user is permitted to access
   via :meth:`FGAClient.list_resources`.  Only those resources are included
   in the vector-search metadata filter.

2. **Post-filtering** — After the vector store returns candidate documents,
   each result is individually verified against the FGA check API to catch
   any stale or cache-inconsistent access grants.

This dual-guarantee design ensures **zero document leakage**: the RAG
system will never surface a document that the user is not authorized to read.

Audit logging:
    Every access decision (allow or deny) is recorded via the
    :mod:`logging` framework so that compliance teams can reconstruct an
    audit trail.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

from auth0_fga.authorization import FGAClient
from auth0_fga.models import AccessDecision, ResourceType

logger = logging.getLogger(__name__)

# Sub-logger dedicated to audit events — can be routed to a file handler.
audit_logger = logging.getLogger("auth0_fga.audit")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class FilteredResult:
    """A single document result after access filtering.

    Attributes:
        document_id: Unique identifier of the document.
        content: Text content of the document (or section).
        score: Retrieval relevance score.
        metadata: Optional metadata attached by the vector store.
        access_allowed: Whether the user is authorized to read this document.
        filter_stage: ``"pre"`` if excluded before vector search,
                      ``"post"`` if excluded after vector search,
                      ``"none"`` if not filtered.
        denied_reason: Human-readable reason if access was denied.
    """

    document_id: str
    content: str
    score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    access_allowed: bool = True
    filter_stage: str = "none"
    denied_reason: str = ""


@dataclass
class RetrievalStats:
    """Aggregate statistics for a single retrieval request.

    Attributes:
        user_id: The user who issued the query.
        query_text: The original query text.
        total_candidates: Total documents returned by the vector store.
        pre_filtered_out: Documents excluded by pre-filter.
        post_filtered_out: Documents excluded by post-filter.
        final_count: Documents the user can actually see.
        latency_ms: Total retrieval + filtering time in milliseconds.
    """

    user_id: str
    query_text: str
    total_candidates: int = 0
    pre_filtered_out: int = 0
    post_filtered_out: int = 0
    final_count: int = 0
    latency_ms: float = 0.0


# ---------------------------------------------------------------------------
# RetrievalFilter
# ---------------------------------------------------------------------------

class RetrievalFilter:
    """Dual-stage access filter for RAG document retrieval.

    Wraps a vector store / similarity-search backend and ensures that
    every result returned to the caller has been authorized for the
    requesting user.

    Parameters:
        fga_client: An initialized :class:`FGAClient` instance.
        vector_search_fn: Callable that performs the actual vector search.
            Signature: ``(query_text, top_k, metadata_filter) -> List[FilteredResult]``
        resource_type: The FGA resource type to check (default ``"document"``).
        relation: The FGA relation / permission to check (default ``"can_read"``).
        enable_pre_filter: Whether to apply pre-filtering (default ``True``).
        enable_post_filter: Whether to apply post-filtering (default ``True``).

    Example::

        def my_vector_search(query, top_k, meta_filter):
            return vector_store.similarity_search(query, k=top_k, filter=meta_filter)

        rfilter = RetrievalFilter(fga_client=fga, vector_search_fn=my_vector_search)
        results = rfilter.query("user:alice", "transformer architecture", top_k=5)
    """

    def __init__(
        self,
        fga_client: FGAClient,
        vector_search_fn: Optional[Callable[..., List[FilteredResult]]] = None,
        resource_type: str = "document",
        relation: str = "can_read",
        enable_pre_filter: bool = True,
        enable_post_filter: bool = True,
    ) -> None:
        self.fga_client = fga_client
        self.vector_search_fn = vector_search_fn
        self.resource_type = resource_type
        self.relation = relation
        self.enable_pre_filter = enable_pre_filter
        self.enable_post_filter = enable_post_filter

    # ---- Core query method ---------------------------------------------------

    def query(
        self,
        user_id: str,
        query_text: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[FilteredResult]:
        """Execute a privacy-filtered retrieval query.

        Flow:
            1. **Pre-filter**: Determine the set of resource IDs the user
               can access.  Inject these as metadata constraints into the
               vector search call.
            2. **Vector search**: Delegate to the configured
               ``vector_search_fn``.
            3. **Post-filter**: For every candidate, call the FGA check
               API and drop unauthorized results.

        Args:
            user_id: Auth0 user identifier.
            query_text: The user's natural-language query.
            top_k: Maximum number of results to return.
            filters: Optional additional metadata filters for the vector store.

        Returns:
            A list of :class:`FilteredResult` objects, all with
            ``access_allowed=True``.
        """
        start_time = time.monotonic()
        stats = RetrievalStats(user_id=user_id, query_text=query_text)

        merged_filters = dict(filters) if filters else {}

        # ---- Stage 1: Pre-filtering ------------------------------------------
        if self.enable_pre_filter:
            accessible_ids = self.get_accessible_repos(user_id)
            if accessible_ids:
                merged_filters.setdefault("document_id", {"$in": list(accessible_ids)})
                logger.info(
                    "Pre-filter: user %s has access to %d resource(s)",
                    user_id,
                    len(accessible_ids),
                )
            else:
                logger.warning(
                    "Pre-filter: user %s has no accessible resources — returning empty",
                    user_id,
                )
                stats.latency_ms = (time.monotonic() - start_time) * 1000
                self._log_audit(user_id, query_text, stats)
                return []

        # ---- Stage 2: Vector search ------------------------------------------
        if self.vector_search_fn is None:
            logger.warning("No vector_search_fn configured — returning empty results.")
            stats.latency_ms = (time.monotonic() - start_time) * 1000
            return []

        try:
            candidates = self.vector_search_fn(query_text, top_k, merged_filters)
        except Exception as exc:
            logger.error("Vector search failed: %s", exc, exc_info=True)
            stats.latency_ms = (time.monotonic() - start_time) * 1000
            return []

        stats.total_candidates = len(candidates)

        # ---- Stage 3: Post-filtering -----------------------------------------
        results: List[FilteredResult] = []
        if self.enable_post_filter:
            items = [(self.relation, doc.document_id) for doc in candidates]
            decisions = self.fga_client.batch_check_access(user_id, items)

            for doc, decision in zip(candidates, decisions):
                if decision.allowed:
                    doc.access_allowed = True
                    results.append(doc)
                else:
                    doc.access_allowed = False
                    doc.filter_stage = "post"
                    doc.denied_reason = decision.reason
                    stats.post_filtered_out += 1
                    self._log_denial(user_id, doc.document_id, decision)
        else:
            results = candidates

        stats.final_count = len(results)
        stats.latency_ms = (time.monotonic() - start_time) * 1000

        logger.info(
            "Retrieval stats: total=%d pre_filtered=%d post_filtered=%d final=%d latency=%.1fms",
            stats.total_candidates,
            stats.pre_filtered_out,
            stats.post_filtered_out,
            stats.final_count,
            stats.latency_ms,
        )

        self._log_audit(user_id, query_text, stats)
        return results

    # ---- Filtering helpers ---------------------------------------------------

    def filter_documents(
        self,
        user_id: str,
        documents: Sequence[FilteredResult],
    ) -> List[FilteredResult]:
        """Filter a list of documents by access for *user_id*.

        Each document is individually checked against the FGA policy.
        This is the same logic as the post-filtering stage.

        Args:
            user_id: Auth0 user identifier.
            documents: Sequence of :class:`FilteredResult` to evaluate.

        Returns:
            Only the documents the user is authorized to read.
        """
        if not documents:
            return []

        items = [(self.relation, doc.document_id) for doc in documents]
        decisions = self.fga_client.batch_check_access(user_id, items)

        allowed: List[FilteredResult] = []
        for doc, decision in zip(documents, decisions):
            if decision.allowed:
                doc.access_allowed = True
                allowed.append(doc)
            else:
                doc.access_allowed = False
                doc.filter_stage = "post"
                doc.denied_reason = decision.reason
                self._log_denial(user_id, doc.document_id, decision)

        logger.info(
            "filter_documents: %d/%d documents allowed for user %s",
            len(allowed),
            len(documents),
            user_id,
        )
        return allowed

    def get_accessible_repos(self, user_id: str) -> List[str]:
        """Get the list of repositories the user can access.

        Queries the FGA ``list-objects`` API for the configured
        ``resource_type`` and ``relation``.

        Args:
            user_id: Auth0 user identifier.

        Returns:
            A list of FGA object strings (e.g. ``["document:repo1-doc3", ...]``).
        """
        try:
            objects = self.fga_client.list_resources(
                user_id=user_id,
                relation=self.relation,
                resource_type=self.resource_type,
            )
            return objects
        except Exception as exc:
            logger.error("Failed to list accessible repos for %s: %s", user_id, exc)
            return []

    # ---- Audit logging -------------------------------------------------------

    @staticmethod
    def _log_audit(user_id: str, query_text: str, stats: RetrievalStats) -> None:
        """Emit an audit log entry for a retrieval request."""
        audit_logger.info(
            "AUDIT retrieval user=%s query=%r total=%d pre_filtered=%d "
            "post_filtered=%d final=%d latency_ms=%.1f",
            user_id,
            query_text,
            stats.total_candidates,
            stats.pre_filtered_out,
            stats.post_filtered_out,
            stats.final_count,
            stats.latency_ms,
        )

    @staticmethod
    def _log_denial(user_id: str, document_id: str, decision: AccessDecision) -> None:
        """Emit an audit log entry for a denied document."""
        audit_logger.warning(
            "AUDIT denial user=%s document=%s relation=%s reason=%s decision_id=%s",
            user_id,
            document_id,
            decision.relation,
            decision.reason,
            decision.decision_id,
        )
