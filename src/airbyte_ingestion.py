"""
Airbyte document ingestion pipeline for senso-ai RAG engine.

Enables automatic document ingestion from external sources into the
PrivateRAGEngine knowledge base via Airbyte connectors.

Supported sources (via Airbyte connectors):
- Notion: pages, databases, docs
- Confluence: wiki pages, blog posts
- Google Drive: docs, sheets, PDFs
- Airtable: records from any base
- GitHub: READMEs, issues, pull requests, code files
- Typeform: survey responses

The pipeline:
    Airbyte Connector → fetch documents → chunk → ingest into VectorStore + FGA policy

Setup:
    export AIRBYTE_CLIENT_ID=<your_client_id>
    export AIRBYTE_CLIENT_SECRET=<your_client_secret>
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Airbyte SDK bridge
# ---------------------------------------------------------------------------

_airbyte_available = False
try:
    from airbyte_agent_sdk import connect, Workspace, AirbyteError
    _airbyte_available = True
except ImportError:
    logger.info("airbyte-agent-sdk not installed; document ingestion limited to local files")


def is_airbyte_available() -> bool:
    if not _airbyte_available:
        return False
    return bool(os.environ.get("AIRBYTE_CLIENT_ID") and os.environ.get("AIRBYTE_CLIENT_SECRET"))


# ---------------------------------------------------------------------------
# Document models
# ---------------------------------------------------------------------------

class IngestedDocument:
    """A document fetched from an external source via Airbyte."""

    def __init__(
        self,
        document_id: str,
        title: str,
        content: str,
        source: str,
        source_url: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.document_id = document_id
        self.title = title
        self.content = content
        self.source = source
        self.source_url = source_url
        self.metadata = metadata or {}

    def __repr__(self) -> str:
        return f"IngestedDocument(id={self.document_id!r}, source={self.source!r}, title={self.title!r})"


# ---------------------------------------------------------------------------
# Source-specific fetchers
# ---------------------------------------------------------------------------

async def fetch_from_notion(
    connector_id: Optional[str] = None,
    database_id: Optional[str] = None,
) -> List[IngestedDocument]:
    """
    Fetch documents from Notion via Airbyte.

    Requires a Notion connector configured in Airbyte with access to
    the target database or pages.
    """
    if not is_airbyte_available():
        raise RuntimeError("Airbyte SDK not configured")

    notion = connect("notion", connector_id=connector_id)
    docs: List[IngestedDocument] = []

    try:
        # Fetch pages from a database
        if database_id:
            result = await notion.execute("pages", "list", params={
                "database_id": database_id,
            })
            for page in result.data:
                props = page.get("properties", {})
                title_prop = props.get("title", props.get("Name", props.get("Page", {})))
                title = ""
                if isinstance(title_prop, dict):
                    title_parts = title_prop.get("title", [])
                    title = " ".join(p.get("plain_text", "") for p in title_parts)
                elif isinstance(title_prop, str):
                    title = title_prop

                content = page.get("content", "")
                if not content and title:
                    content = f"[Notion page: {title}]"

                doc = IngestedDocument(
                    document_id=f"notion_{page.get('id', '')}",
                    title=title or "Untitled",
                    content=content,
                    source="notion",
                    source_url=page.get("url", ""),
                    metadata={"notion_id": page.get("id", ""), "database_id": database_id or ""},
                )
                docs.append(doc)

        logger.info("Fetched %d documents from Notion", len(docs))
    except AirbyteError as exc:
        logger.error("Notion fetch failed: %s", exc)
        raise

    return docs


async def fetch_from_confluence(
    connector_id: Optional[str] = None,
    space_key: Optional[str] = None,
    limit: int = 50,
) -> List[IngestedDocument]:
    """Fetch wiki pages from Confluence via Airbyte."""
    if not is_airbyte_available():
        raise RuntimeError("Airbyte SDK not configured")

    confluence = connect("confluence", connector_id=connector_id)
    docs: List[IngestedDocument] = []

    try:
        result = await confluence.execute("pages", "list", params={
            "space_key": space_key or os.environ.get("CONFLUENCE_SPACE", ""),
            "limit": limit,
        })
        for page in result.data:
            doc = IngestedDocument(
                document_id=f"confluence_{page.get('id', '')}",
                title=page.get("title", "Untitled"),
                content=page.get("body", ""),
                source="confluence",
                source_url=page.get("url", page.get("link", "")),
                metadata={"space": space_key or "", "page_id": page.get("id", "")},
            )
            docs.append(doc)

        logger.info("Fetched %d documents from Confluence", len(docs))
    except AirbyteError as exc:
        logger.error("Confluence fetch failed: %s", exc)
        raise

    return docs


async def fetch_from_github(
    connector_id: Optional[str] = None,
    owner: Optional[str] = None,
    repo: Optional[str] = None,
) -> List[IngestedDocument]:
    """
    fetch READMEs and documentation files from a GitHub repo via Airbyte.
    """
    if not is_airbyte_available():
        raise RuntimeError("Airbyte SDK not configured")

    github = connect("github", connector_id=connector_id)
    docs: List[IngestedDocument] = []

    try:
        result = await github.execute("repositories", "get", params={
            "owner": owner or os.environ.get("GH_OWNER", ""),
            "repo": repo or os.environ.get("GH_REPO", ""),
        })
        repo_data = result.data

        # Try to get README
        try:
            readme_result = await github.execute("repositories", "readme", params={
                "owner": owner or os.environ.get("GH_OWNER", ""),
                "repo": repo or os.environ.get("GH_REPO", ""),
            })
            readme_content = readme_result.data.get("content", "")
            if readme_content:
                import base64
                try:
                    readme_content = base64.b64decode(readme_content).decode("utf-8")
                except Exception:
                    pass

                docs.append(IngestedDocument(
                    document_id=f"github_{owner}_{repo}_readme",
                    title=f"README - {repo}",
                    content=readme_content,
                    source="github",
                    source_url=f"https://github.com/{owner}/{repo}",
                    metadata={"owner": owner or "", "repo": repo or ""},
                ))
        except Exception as exc:
            logger.debug("Could not fetch README: %s", exc)

        logger.info("Fetched %d documents from GitHub/%s/%s", len(docs), owner, repo)
    except AirbyteError as exc:
        logger.error("GitHub fetch failed: %s", exc)
        raise

    return docs


# ---------------------------------------------------------------------------
# Bulk ingestion into PrivateRAGEngine
# ---------------------------------------------------------------------------

async def ingest_documents_into_rag(
    engine: Any,
    documents: List[IngestedDocument],
    default_policy_resource: str = "organization:senso-ai",
    default_role: str = "viewer",
) -> Dict[str, Any]:
    """
    Bulk ingest documents from any Airbyte source into the RAG engine.

    Parameters:
        engine: A PrivateRAGEngine instance
        documents: List of IngestedDocument to ingest
        default_policy_resource: FGA resource ID for access policy
        default_role: Default access role (viewer, editor, admin)

    Returns:
        Summary dict with success/failure counts
    """
    from auth0_fga.models import DocumentPolicy, PolicyRelation

    results = {"success": 0, "failed": 0, "errors": [], "ingested_ids": []}

    for doc in documents:
        try:
            policy = DocumentPolicy(
                policy_id=f"policy_{doc.document_id}",
                resource_id=default_policy_resource,
                document_id=doc.document_id,
                relations=[
                    PolicyRelation(relation=default_role, users=["*"]),
                ],
            )

            engine.ingest(
                document_id=doc.document_id,
                content=doc.content,
                access_policy=policy,
                metadata={
                    "title": doc.title,
                    "source": doc.source,
                    "source_url": doc.source_url,
                    "ingested_at": datetime.utcnow().isoformat() + "Z",
                    **doc.metadata,
                },
            )
            results["success"] += 1
            results["ingested_ids"].append(doc.document_id)
        except Exception as exc:
            results["failed"] += 1
            results["errors"].append({"document_id": doc.document_id, "error": str(exc)})
            logger.error("Failed to ingest %s: %s", doc.document_id, exc)

    logger.info(
        "Bulk ingestion complete: %d success, %d failed",
        results["success"],
        results["failed"],
    )
    return results


# ---------------------------------------------------------------------------
# Unified sync entry point
# ---------------------------------------------------------------------------

async def sync_all_sources(
    engine: Any,
    sources: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Sync documents from all configured Airbyte sources into the RAG engine.

    Parameters:
        engine: A PrivateRAGEngine instance
        sources: Config dict with source settings, e.g.:
            {
                "notion": {"database_id": "xxx", "connector_id": "yyy"},
                "confluence": {"space_key": "ENG", "limit": 50},
                "github": {"owner": "myorg", "repo": "docs"},
            }

    Returns:
        Aggregated results from all sources
    """
    source_config = sources or {}
    all_docs: List[IngestedDocument] = []
    summary: Dict[str, Any] = {}

    # Notion
    if "notion" in source_config or os.environ.get("NOTION_DATABASE_ID"):
        try:
            notion_docs = await fetch_from_notion(
                connector_id=source_config.get("notion", {}).get("connector_id"),
                database_id=source_config.get("notion", {}).get("database_id") or os.environ.get("NOTION_DATABASE_ID"),
            )
            all_docs.extend(notion_docs)
            summary["notion"] = len(notion_docs)
        except Exception as exc:
            summary["notion"] = f"error: {exc}"

    # Confluence
    if "confluence" in source_config or os.environ.get("CONFLUENCE_SPACE"):
        try:
            confluence_docs = await fetch_from_confluence(
                connector_id=source_config.get("confluence", {}).get("connector_id"),
                space_key=source_config.get("confluence", {}).get("space_key") or os.environ.get("CONFLUENCE_SPACE"),
                limit=source_config.get("confluence", {}).get("limit", 50),
            )
            all_docs.extend(confluence_docs)
            summary["confluence"] = len(confluence_docs)
        except Exception as exc:
            summary["confluence"] = f"error: {exc}"

    # GitHub
    if "github" in source_config or (os.environ.get("GH_OWNER") and os.environ.get("GH_REPO")):
        try:
            gh_docs = await fetch_from_github(
                connector_id=source_config.get("github", {}).get("connector_id"),
                owner=source_config.get("github", {}).get("owner") or os.environ.get("GH_OWNER"),
                repo=source_config.get("github", {}).get("repo") or os.environ.get("GH_REPO"),
            )
            all_docs.extend(gh_docs)
            summary["github"] = len(gh_docs)
        except Exception as exc:
            summary["github"] = f"error: {exc}"

    # Bulk ingest
    if all_docs:
        ingest_results = await ingest_documents_into_rag(engine, all_docs)
        summary["ingestion"] = ingest_results
    else:
        summary["ingestion"] = {"message": "No documents fetched from any source"}

    summary["total_fetched"] = len(all_docs)
    summary["synced_at"] = datetime.utcnow().isoformat() + "Z"
    return summary


# ---------------------------------------------------------------------------
# MCP configuration
# ---------------------------------------------------------------------------

def get_mcp_config() -> Dict[str, Any]:
    """Return MCP server config for AI agent access to knowledge base sources."""
    return {
        "mcp_server_url": "https://mcp.airbyte.ai/mcp",
        "setup": {
            "claude_code": "claude mcp add --transport http airbyte-agent https://mcp.airbyte.ai/mcp",
            "cursor": '{"mcpServers": {"Agent MCP": {"url": "https://mcp.airbyte.ai/mcp"}}}',
        },
        "recommended_connectors": [
            "notion (for knowledge base pages and databases)",
            "confluence (for internal wiki documentation)",
            "google_drive (for shared documents and PDFs)",
            "github (for code documentation and READMEs)",
            "airtable (for structured knowledge records)",
        ],
    }
