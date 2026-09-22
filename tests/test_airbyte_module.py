"""Airbyte ingestion: graceful degradation without SDK or credentials."""
import asyncio

import src.airbyte_ingestion as airbyte


def test_airbyte_graceful_degradation():
    # Implemented fetchers (README Supported Sources, as amended).
    for fn in ("fetch_from_notion", "fetch_from_confluence", "fetch_from_github"):
        assert hasattr(airbyte, fn), f"missing implemented fetcher {fn}"

    # Sources named in the pre-amendment README but NOT implemented — the
    # reworded claim pins their absence so it cannot silently regress either way.
    for absent in ("fetch_from_google_drive", "fetch_from_airtable", "fetch_from_typeform"):
        assert not hasattr(airbyte, absent), f"unexpected fetcher {absent}"

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
