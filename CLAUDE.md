# Senso.AI — Agent Context

## Identity
Senso.AI is the unified knowledge base for Cubiczan's 15-repo enterprise AI portfolio on Codeberg (https://codeberg.org/cubiczan). It serves as the agent-ready compilation point for cross-repo intelligence.

## Repository Map
All repos live at `/home/z/my-project/<repo-name>/`.

### Healthcare & Life Sciences
- `healthguard-ai` — 7-tab Next.js dashboard, ClickHouse 10 UDFs, Nimble SDK, RapidReview Papyrus, Lapdog

### CFO & Finance
- `cfo-resilience-matrix` — 6-layer LLM resilience (provider failover, circuit breakers, semantic caching), 153 tests
- `cfo-command-center` — AI finance ops on Notion
- `cash-flow-optimizer` — Vellum + Xero + Precoro cash flow intelligence
- `p2p-copilot` — UiPath Maestro BPMN procure-to-pay with Claude Vision

### Commodity & Mining
- `battery-erp` — Full battery value chain ERP, 11 Delta tables, Fabric Lakehouse
- `databricks-commodity-risk-engine` — VaR/CVaR + margin analytics, 10 commodity contracts, MLflow
- `databricks-lakehouse-intelligence` — Mining analytics, Unity Catalog, 9 Delta tables, ESG scores
- `snowflake-commodity-supply-chain` — Snowpark UDFs, Zero-Copy Clone, Dynamic Masking, dbt
- `snowflake-cortex-research` — SEC filing NLP via Snowflake Cortex AI, dbt

### Security & Blockchain
- `metacomp-visionx-dashboard` — Crypto AML/KYT (Chainalysis, Beosin, Elliptic, Merkle Science)
- `shieldgate` — AuthZed/SpiceDB zero-trust for AI agents + Splunk
- `courtvision-ai` — NBA prediction market on Polygon + Azuro Protocol + Qwen LLM
- `greenverify-ai` — Carbon credit verification, Rust ink! contracts, Next.js dashboard

### Innovation
- `first-principles-product-incubator` — 5-phase innovation workspace, Next.js + Bun

## Key Architectural Patterns
- Medallion architecture (Bronze/Silver/Gold) → databricks-cre, databricks-lhi
- Multi-provider LLM failover → cfo-resilience-matrix
- Dark-themed multi-tab dashboard → healthguard-ai, metacomp-vx, greenverify-ai
- Zero-trust authorization → shieldgate
- Dynamic data masking + RAP → snowflake-csc
- Synthetic data fallback → healthguard-ai
- BPMN orchestration → p2p-copilot

## Git Workflow
- 3 remotes per repo: GitHub Cubiczan, GitHub zan-maker, Codeberg cubiczan
- Codeberg push may require retry due to rate limiting

## Common Commands
```bash
# Regenerate screenshots (healthguard-ai)
cd healthguard-ai && python3 scripts/screenshot_py.py

# Run tests (cfo-resilience-matrix)
cd cfo-resilience-matrix && python -m pytest

# Build video (healthguard-ai)
cd healthguard-ai && python3 scripts/create_video.py
```
