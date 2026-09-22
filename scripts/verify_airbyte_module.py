#!/usr/bin/env python3
"""Evidence check: Airbyte ingestion module surface, graceful degradation, MCP config.

Backs README "Airbyte Integration" (as amended): the module implements
fetchers for Notion, Confluence, and GitHub; sync_all_sources dispatches those
three; without the Airbyte SDK or credentials the module imports cleanly,
is_airbyte_available() reports False, and sync_all_sources returns a graceful
summary instead of raising; get_mcp_config() exposes the documented MCP
server URL and setup instructions.

Runs offline: never touches the network or requires the Airbyte SDK.
"""
import asyncio
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def main():
    # Clear Airbyte credentials so the graceful-degradation path is the one
    # under test, regardless of the ambient environment.
    for var in list(os.environ):
        if var.startswith("AIRBYTE_"):
            del os.environ[var]

    sys.path.insert(0, str(REPO_ROOT))
    import src.airbyte_ingestion as airbyte

    # Implemented fetchers (README Supported Sources, as amended).
    for fn in ("fetch_from_notion", "fetch_from_confluence", "fetch_from_github"):
        assert hasattr(airbyte, fn), f"missing implemented fetcher {fn}"

    # Sources named in the pre-amendment README but NOT implemented — the
    # reworded claim pins their absence so it cannot silently regress either way.
    for absent in ("fetch_from_google_drive", "fetch_from_airtable", "fetch_from_typeform"):
        assert not hasattr(airbyte, absent), f"unexpected fetcher {absent} — update the README table and this check together"

    assert hasattr(airbyte, "sync_all_sources")
    assert hasattr(airbyte, "ingest_documents_into_rag")

    # Graceful degradation: no SDK/creds -> available flag False, and a sync
    # with no configured sources returns an empty summary rather than raising.
    assert airbyte.is_airbyte_available() is False
    summary = asyncio.run(airbyte.sync_all_sources(engine=object()))
    assert summary["total_fetched"] == 0, summary
    assert summary["ingestion"] == {"message": "No documents fetched from any source"}, summary
    assert "synced_at" in summary

    # MCP server access surface documented in README.
    mcp = airbyte.get_mcp_config()
    assert mcp["mcp_server_url"] == "https://mcp.airbyte.ai/mcp", mcp
    assert "claude_code" in mcp["setup"] and mcp["setup"]["claude_code"].strip()

    print("verify_airbyte_module: PASS (3 implemented fetchers, unimplemented sources pinned absent, graceful no-credential degradation, MCP config surface)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
