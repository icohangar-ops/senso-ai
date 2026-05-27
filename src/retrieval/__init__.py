"""
Privacy-aware RAG retrieval engine for senso-ai.

This package provides the :class:`PrivateRAGEngine` that combines
Auth0 FGA authorization enforcement with standard RAG retrieval
to guarantee zero document leakage in enterprise AI knowledge base
queries.

Modules:
    rag_engine  -- The main PrivateRAGEngine class

Typical usage::

    from retrieval import PrivateRAGEngine
    from auth0_fga import FGAClient

    fga = FGAClient()
    engine = PrivateRAGEngine(fga_client=fga, vector_store=my_store, llm_client=my_llm)
    response = engine.query(user_id="user:alice", question="What is RAG?")
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

from retrieval.rag_engine import PrivateRAGEngine, RAGResponse, RAGSource

__all__ = [
    "PrivateRAGEngine",
    "RAGResponse",
    "RAGSource",
]

__version__ = "1.0.0"
