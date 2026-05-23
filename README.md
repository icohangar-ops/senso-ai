# Senso.AI — Agent-Ready Knowledge Base

> **15-repo enterprise AI portfolio** compiled into a single agent-ready knowledge base. Covers healthcare intelligence, commodity risk, CFO operations, carbon markets, sports prediction, procurement automation, and zero-trust security — all built by Cubiczan.

---

## Portfolio Architecture

```
                              ┌──────────────────────┐
                              │      Senso.AI        │
                              │   Knowledge Base     │
                              │   (This Repository)  │
                              └──────────┬───────────┘
              ┌─────────────────┬────────┴────────┬─────────────────┐
              │                 │                 │                  │
     ┌────────┴──────┐  ┌─────┴──────────┐  ┌───┴────────────┐  ┌─┴──────────────┐
     │ Healthcare &  │  │  CFO & Finance │  │  Commodity &   │  │  Security &    │
     │ Life Sciences │  │  Operations    │  │  Mining        │  │  Blockchain    │
     ├───────────────┤  ├────────────────┤  ├────────────────┤  ├────────────────┤
     │ healthguard-ai│  │ cfo-resilience │  │ battery-erp    │  │ metacomp-vx    │
     │               │  │ cfo-command    │  │ databricks-cre │  │ shieldgate     │
     │               │  │ cash-flow-opt  │  │ databricks-lhi │  │ courtvision-ai │
     │               │  │ p2p-copilot    │  │ snowflake-csc  │  │ greenverify-ai │
     │               │  │                │  │ snowflake-crtx │  │                │
     └───────────────┘  └────────────────┘  └────────────────┘  └────────────────┘
                                             ┌────────────────┐
                                             │ Innovation &   │
                                             │ Product Dev    │
                                             ├────────────────┤
                                             │ first-principles│
                                             └────────────────┘
```

---

## All 15 Repositories

### 🏥 Healthcare & Life Sciences

#### [healthguard-ai](https://codeberg.org/cubiczan/healthguard-ai)
**Health Intelligence Platform** — Unified dashboard combining ClickHouse Cloud (10 custom UDFs), Nimble SDK (web scraping), RapidReview Papyrus (academic research maps), and Datadog Lapdog (LLM observability).

- **Stack**: Next.js 16, TypeScript, Tailwind CSS 4, shadcn/ui, Recharts, ClickHouse Cloud
- **Key Features**: 7-tab dashboard (Overview, Claims Fraud, Provider Risk, Drug Safety, Clinical Intel, Compliance, Research Map), 10 SQL UDFs for fraud detection, synthetic data fallback
- **Integrations**: ClickHouse Cloud, Nimble SDK, RapidReview Papyrus, Datadog Lapdog
- **Repo Size**: ~500 LOC (dashboard) + 10 ClickHouse UDFs
- **License**: MIT

---

### 💰 CFO & Finance Operations

#### [cfo-resilience-matrix](https://codeberg.org/cubiczan/cfo-resilience-matrix)
**6-Layer AI Agent Resilience for CFO Operations** — Resilience stack wrapping every LLM call through provider failover, circuit breakers, semantic caching, prompt fallbacks, response validation, and dead-letter queuing.

- **Stack**: Python 3.11+, TrueFoundry AI Gateway
- **Key Features**: 6-layer resilience stack, 153 passing tests, graceful degradation for CFO agents
- **Integrations**: OpenAI, Claude, Gemini (multi-provider), TrueFoundry AI Gateway
- **Repo Size**: 153 tests, comprehensive resilience patterns
- **License**: Apache 2.0

#### [cfo-command-center](https://codeberg.org/cubiczan/cfo-command-center)
**AI-Powered Finance Operations Hub on Notion** — Transforms Notion workspace into a full-stack CFO operating system with vendor scoring, cash flow forecasting, and payment prioritization.

- **Stack**: Notion API, AI Agents
- **Key Features**: Vendor database, cash flow analytics, working capital optimization, payment queue, all inside Notion
- **Integrations**: Notion Workspace, Notion API
- **License**: MIT

#### [cash-flow-optimizer](https://codeberg.org/cubiczan/cash-flow-optimizer)
**Vellum-Powered Cash Flow Intelligence** — Daily cash position reporting, invoice ingestion with 3-way PO matching, and 13-week rolling forecast with LLM narrative analysis.

- **Stack**: Vellum AI, Xero API, Precoro API, Microsoft Graph API
- **Key Features**: Automated 7am cash reports, PDF invoice extraction, PO auto-matching, LLM risk narrative
- **Integrations**: Xero (accounting), Precoro (procurement), Outlook (email), Vellum (AI orchestration)
- **Architecture**: Triggers → API Nodes → Code Nodes → Agent Node → Guardrail Node → Output
- **License**: MIT

#### [p2p-copilot](https://codeberg.org/cubiczan/p2p-copilot)
**AI-Powered Procure-to-Pay on UiPath Maestro** — End-to-end invoice processing pipeline from intake through payment using BPMN 2.0 orchestration, Claude AI, and Python ML.

- **Stack**: UiPath Maestro (BPMN), Claude AI (Vision API), Python ML
- **Key Features**: 6-stage P2P pipeline (Invoice → OCR → Validate → Anomaly Detect → Approve → Pay), Claude Vision for PDF extraction, anomaly detection, full audit trail
- **Integrations**: UiPath Maestro, Claude Vision, UiPath Action Center
- **License**: MIT

---

### ⛏️ Commodity, Mining & Supply Chain

#### [battery-erp](https://codeberg.org/cubiczan/battery-erp)
**Battery Value Chain ERP** — Full battery lifecycle management from raw materials (lithium, cobalt, nickel) through cell chemistries (NMC-811, NCA, LFP) to pack assembly with BOM costing and supplier scoring.

- **Stack**: Python 3.10+, Microsoft Fabric Lakehouse, Delta Tables
- **Key Features**: 11 Delta tables, supplier scoring (A-D grades), BOM cost rollups, what-if scenarios, AlphaVantage commodity pricing
- **Integrations**: Microsoft Fabric, AlphaVantage, FRED (macro overlay)
- **Repo Size**: 32 passing tests
- **License**: MIT

#### [databricks-commodity-risk-engine](https://codeberg.org/cubiczan/databricks-commodity-risk-engine)
**Delta Lake + MLflow + VaR + Margin Analytics** — Risk analytics for critical metals and energy commodities with Value-at-Risk (VaR), contract-level margin assessment, and ML-powered predictions.

- **Stack**: Databricks (Serverless), Delta Lake, MLflow, scikit-learn
- **Key Features**: Medallion architecture (Bronze/Silver/Gold), VaR at 95% / CVaR at 99%, 10 physical commodity contracts, MLflow experiment tracking
- **Commodities**: Nickel, Cobalt, Lithium, MHP, Copper, Iron Ore
- **Counterparties**: Toyota, Samsung SDI, CATL, Tesla, GM, BYD
- **License**: MIT

#### [databricks-lakehouse-intelligence](https://codeberg.org/cubiczan/databricks-lakehouse-intelligence)
**Mining & Metals Analytics on Databricks** — Medallion architecture with Unity Catalog governance processing mining company production volumes, AISC costs, and financial metrics into composite intelligence scores.

- **Stack**: Databricks, Unity Catalog, MLflow, Delta Tables
- **Key Features**: 5 managed schemas, 9 Delta tables, 8 MLflow runs across 4 weight configs, composite signal scores (Grade, Cost, Production, Growth, ESG)
- **Integrations**: Databricks REST API v2.0/2.1
- **License**: MIT

#### [snowflake-commodity-supply-chain](https://codeberg.org/cubiczan/snowflake-commodity-supply-chain)
**Contract Pricing & Risk Analytics on Snowflake** — Production-grade data platform for commodity supply chain risk with Snowpark UDFs, Zero-Copy Cloning, Dynamic Data Masking, and Row Access Policies.

- **Stack**: Snowflake, dbt, Snowpark (Python UDFs)
- **Key Features**: Dynamic Tables, Streams & Tasks, Zero-Copy Cloning, Dynamic Data Masking, Row Access Policies
- **Architecture**: Raw → dbt transforms → Analytics layer
- **License**: MIT

#### [snowflake-cortex-research](https://codeberg.org/cubiczan/snowflake-cortex-research)
**AI-Powered Earnings & Filing Analytics** — SEC filings and earnings call analysis using Snowflake Cortex AI with version-controlled dbt transformations and Dynamic Tables.

- **Stack**: Snowflake Cortex AI, dbt 1.8+
- **Key Features**: SEC EDGAR filing analysis (10-K, 10-Q, 8-K), earnings call NLP, Dynamic Tables, Streams & Tasks, Zero-Copy Cloning
- **Integrations**: SEC EDGAR, Market Data APIs
- **License**: MIT

---

### 🔒 Security, Blockchain & Decentralized

#### [metacomp-visionx-dashboard](https://codeberg.org/cubiczan/metacomp-visionx-dashboard)
**Crypto AML/KYT Compliance Dashboard** — Real-time crypto compliance screening aggregating risk signals from Chainalysis, Beosin, Elliptic, and Merkle Science.

- **Stack**: Next.js 16, TypeScript, Tailwind CSS 4
- **Key Features**: Cross-validated risk reports, per-vendor breakdowns, unified compliance conclusions
- **Integrations**: MetaComp Vision X API (4 blockchain intelligence vendors)
- **License**: MIT

#### [shieldgate](https://codeberg.org/cubiczan/shieldgate)
**Least-Privilege Agentic SOC** — AuthZed (SpiceDB) authorization layer enforcing zero-trust permissions for AI agents interacting with Splunk.

- **Stack**: Next.js 16, AuthZed/SpiceDB, Splunk, MCP Protocol
- **Key Features**: Every tool call passes through SpiceDB permission check, least-privilege enforcement, blast radius containment
- **Integrations**: AuthZed, Splunk (MCP Server)
- **License**: MIT

#### [courtvision-ai](https://codeberg.org/cubiczan/courtvision-ai)
**AI-Powered NBA Prediction Market on Polygon** — Decentralized prediction market using Azuro Protocol with Qwen LLM analysis.

- **Stack**: Next.js, React, Tailwind CSS, FastAPI, Solidity
- **Key Features**: AI game analysis, player performance forecasting, on-chain betting via Azuro Protocol, Polygon Amoy testnet
- **Integrations**: Azuro Protocol, Qwen LLM (DashScope), Polygon
- **License**: MIT

#### [greenverify-ai](https://codeberg.org/cubiczan/greenverify-ai)
**AI Carbon Credit Verification & Trading on Portaldot** — Carbon credit verification system with Rust smart contracts and Next.js dashboard.

- **Stack**: Next.js 16, Rust (ink! 5.0), Python 3.11+
- **Key Features**: AI-powered carbon credit verification, on-chain trading marketplace, 4-tab dashboard
- **Integrations**: Portaldot (DoraHacks), Substrate/ink! smart contracts
- **License**: MIT

---

### 💡 Innovation & Product Development

#### [first-principles-product-incubator](https://codeberg.org/cubiczan/first-principles-product-incubator)
**Structured Innovation Workspace** — Guides teams from ideation to validated MVP using four proven innovation frameworks in a five-phase workflow.

- **Stack**: Next.js, Bun, TypeScript
- **Key Features**: First-principles decomposition, user empathy mapping, bottleneck analysis, hypothesis validation, integrated tool
- **License**: MIT

---

## Cross-Cutting Patterns

### Data Architecture Patterns
| Pattern | Used In |
|---------|---------|
| Medallion (Bronze/Silver/Gold) | databricks-commodity-risk-engine, databricks-lakehouse-intelligence |
| Delta Lake | battery-erp, databricks-cre, databricks-lhi |
| Zero-Copy Cloning | snowflake-csc, snowflake-cortex-research |
| Dynamic Tables | snowflake-csc, snowflake-cortex-research |
| Unity Catalog | databricks-lakehouse-intelligence |

### AI/ML Patterns
| Pattern | Used In |
|---------|---------|
| Multi-provider LLM failover | cfo-resilience-matrix |
| Vector embeddings + semantic search | healthguard-ai (ClickHouse Vector(768)) |
| LLM orchestration (Vellum) | cash-flow-optimizer |
| AI Vision for document extraction | p2p-copilot (Claude Vision) |
| Cortex AI for NLP | snowflake-cortex-research |
| MLflow experiment tracking | databricks-cre, databricks-lhi |
| AI-powered compliance | greenverify-ai, healthguard-ai |

### Security Patterns
| Pattern | Used In |
|---------|---------|
| Dynamic Data Masking | snowflake-csc |
| Row Access Policies | snowflake-csc |
| Zero-trust authorization | shieldgate (AuthZed/SpiceDB) |
| Multi-vendor cross-validation | metacomp-visionx-dashboard |
| Audit trail | p2p-copilot |

### Dashboard Patterns
| Pattern | Used In |
|---------|---------|
| Dark-themed ops dashboard | healthguard-ai, metacomp-visionx-dashboard, greenverify-ai |
| Multi-tab SPA | healthguard-ai (7 tabs), greenverify-ai (4 tabs) |
| Real-time data streaming | cash-flow-optimizer, courtvision-ai |
| Synthetic data fallback | healthguard-ai |

---

## Technology Stack Summary

### Languages
- TypeScript (7 repos: healthguard-ai, metacomp-vx, shieldgate, courtvision-ai, greenverify-ai, first-principles, cfo-command-center)
- Python (7 repos: battery-erp, cfo-resilience, cash-flow-optimizer, databricks-cre, databricks-lhi, snowflake-cortex, greenverify-ai)
- SQL / UDFs (5 repos: healthguard-ai, databricks-cre, databricks-lhi, snowflake-csc, snowflake-cortex)
- Rust (1 repo: greenverify-ai — ink! smart contracts)
- Solidity (1 repo: courtvision-ai)

### Frameworks & Platforms
- **Next.js 16** (5 repos)
- **Databricks** (2 repos)
- **Snowflake** (2 repos)
- **Microsoft Fabric** (1 repo)
- **UiPath Maestro** (1 repo)
- **Notion API** (1 repo)

### Databases
- ClickHouse Cloud, Delta Lake, Snowflake, Microsoft Fabric Lakehouse, Unity Catalog

### AI/ML
- OpenAI, Claude, Gemini, Qwen LLM, Snowflake Cortex AI, MLflow, scikit-learn, Vellum AI

### Blockchain
- Polygon (Azuro Protocol), Substrate/ink!, Portaldot

### Orchestration
- dbt, UiPath Maestro (BPMN), TrueFoundry AI Gateway, MCP Protocol

---

## Codeberg Organization

All 15 repositories are available at: **https://codeberg.org/cubiczan**

| Repository | Description |
|-----------|-------------|
| [battery-erp](https://codeberg.org/cubiczan/battery-erp) | Battery value chain ERP with Fabric Lakehouse |
| [cash-flow-optimizer](https://codeberg.org/cubiczan/cash-flow-optimizer) | Vellum-powered cash flow intelligence |
| [cfo-command-center](https://codeberg.org/cubiczan/cfo-command-center) | AI finance ops hub on Notion |
| [cfo-resilience-matrix](https://codeberg.org/cubiczan/cfo-resilience-matrix) | 6-layer AI agent resilience for CFO ops |
| [courtvision-ai](https://codeberg.org/cubiczan/courtvision-ai) | NBA prediction market on Polygon |
| [databricks-commodity-risk-engine](https://codeberg.org/cubiczan/databricks-commodity-risk-engine) | VaR + margin analytics on Databricks |
| [databricks-lakehouse-intelligence](https://codeberg.org/cubiczan/databricks-lakehouse-intelligence) | Mining analytics with Unity Catalog |
| [first-principles-product-incubator](https://codeberg.org/cubiczan/first-principles-product-incubator) | Innovation workspace (ideation → MVP) |
| [greenverify-ai](https://codeberg.org/cubiczan/greenverify-ai) | Carbon credit verification & trading |
| [healthguard-ai](https://codeberg.org/cubiczan/healthguard-ai) | Health intelligence platform (7 tabs, 10 UDFs) |
| [metacomp-visionx-dashboard](https://codeberg.org/cubiczan/metacomp-visionx-dashboard) | Crypto AML/KYT compliance dashboard |
| [p2p-copilot](https://codeberg.org/cubiczan/p2p-copilot) | Procure-to-pay on UiPath Maestro |
| [shieldgate](https://codeberg.org/cubiczan/shieldgate) | Least-privilege agentic SOC (AuthZed × Splunk) |
| [snowflake-commodity-supply-chain](https://codeberg.org/cubiczan/snowflake-commodity-supply-chain) | Commodity risk on Snowflake + dbt |
| [snowflake-cortex-research](https://codeberg.org/cubiczan/snowflake-cortex-research) | SEC filing analytics with Cortex AI |

---

## License

All repositories are MIT or Apache 2.0 licensed. See individual repository LICENSE files for details.
