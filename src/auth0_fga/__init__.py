"""
Auth0 FGA (Fine-Grained Authorization) integration for senso-ai.

This package provides document-level access control for the senso-ai
enterprise knowledge base, ensuring that the RAG pipeline never retrieves
or surfaces documents the requesting user is not authorized to read.

Modules:
    authorization  -- Core FGAClient for Auth0 FGA API interaction
    models         -- Authorization model definitions, dataclasses, and role hierarchy
    retrieval_filter -- Pre-filter and post-filter enforcement for RAG retrieval

Typical usage::

    from auth0_fga import FGAClient, DocumentPolicy, RetrievalFilter

    fga = FGAClient()
    fga.assign_role("user:alice", "viewer", "repo:financial-data")

    policy = DocumentPolicy(
        resource_type="document",
        resource_id="doc:quarterly-report",
        viewers=["user:alice"],
    )
    fga.create_policy("document", "doc:quarterly-report", policy.to_relations())

    rfilter = RetrievalFilter(fga_client=fga, vector_store=store)
    results = rfilter.query("user:alice", "Q3 revenue", top_k=5)
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Re-export primary public API
from auth0_fga.authorization import FGAClient
from auth0_fga.models import (
    AccessDecision,
    AuthorizationModel,
    DocumentPolicy,
    Resource,
    Role,
)
from auth0_fga.retrieval_filter import RetrievalFilter

__all__ = [
    "FGAClient",
    "DocumentPolicy",
    "RetrievalFilter",
    "AccessDecision",
    "AuthorizationModel",
    "Resource",
    "Role",
]

__version__ = "1.0.0"
