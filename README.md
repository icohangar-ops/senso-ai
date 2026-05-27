# senso-ai — Enterprise AI Knowledge Base

> A privacy-aware enterprise knowledge base with 15 specialized AI/ML repositories, powered by Auth0 Fine-Grained Authorization (FGA) for document-level access control in every RAG query.

**Built for the MLH Privacy-Aware RAG Bot Challenge.**

---

## Overview

senso-ai is an enterprise-grade AI knowledge base that aggregates research papers, code examples, best practices, and internal documentation across 15 AI/ML domains. Its key innovation is the **privacy-aware RAG engine**: a retrieval-augmented generation pipeline that guarantees **zero document leakage** by enforcing Auth0 FGA authorization at every stage of retrieval.

### Key Features

- **15 specialized AI/ML repositories** covering the full spectrum of modern AI
- **Auth0 FGA integration** for fine-grained, document-level access control
- **Dual-stage filtering** (pre-filter + post-filter) eliminates unauthorized access
- **Cedar authorization model** with role hierarchy and conditional policies
- **Full audit trail** for every access decision
- **Zero external dependencies** — uses only `urllib.request` for HTTP calls
- **Production-quality Python** with type hints, docstrings, and logging

---

## Architecture

```
                        ┌─────────────────┐
                        │   Auth0 Login    │
                        │   (JWT Token)    │
                        └────────┬────────┘
                                 │
                        ┌────────▼────────┐
                        │   Auth0 FGA     │
                        │   ┌──────────┐  │
                        │   │ Pre-     │  │  ← Get user's accessible resources
                        │   │ Filter   │  │
                        │   └────┬─────┘  │
                        │        │        │
                        │   ┌────▼─────┐  │
                        │   │ Vector   │  │  ← Semantic search (filtered)
                        │   │ Search   │  │
                        │   └────┬─────┘  │
                        │        │        │
                        │   ┌────▼─────┐  │
                        │   │ Post-    │  │  ← Verify each result
                        │   │ Filter   │  │
                        │   └────┬─────┘  │
                        │        │        │
                        │   ┌────▼─────┐  │
                        │   │   LLM    │  │  ← Generate answer
                        │   │  Answer  │  │
                        │   └────┬─────┘  │
                        └────────┼────────┘
                                 │
                        ┌────────▼────────┐
                        │  RAG Response   │
                        │  (verified ✓)   │
                        └─────────────────┘
```

---

## Quick Start

### Prerequisites

- Python 3.9+
- Auth0 account with FGA enabled
- Auth0 Domain: `dev-c3wp4h1e4gv0t64i.us.auth0.com`

### Configuration

```bash
# Set Auth0 FGA credentials
export AUTH0_FGA_API_URL="https://api.us1.fga.dev"
export AUTH0_FGA_API_TOKEN="your-api-token"
export AUTH0_FGA_STORE_ID="your-store-id"
```

### Deploy the Authorization Model

```python
from auth0_fga import FGAClient, AuthorizationModel

fga = FGAClient()
model = AuthorizationModel.default_model()
model_id = fga.write_authorization_model(model)
print(f"Authorization model deployed: {model_id}")
```

### Query with Access Control

```python
from auth0_fga import FGAClient, RetrievalFilter
from retrieval import PrivateRAGEngine

# Initialize
fga = FGAClient()
engine = PrivateRAGEngine(
    fga_client=fga,
    vector_store=my_vector_store,
    llm_client=my_llm_client,
)

# Assign access
fga.assign_role("user:alice@company.com", "viewer", "repository:computer-vision-ai")

# Query (privacy-aware — only returns authorized documents)
response = engine.query(user_id="user:alice@company.com", question="How does ViT work?")
print(response.answer)
for source in response.sources:
    print(f"  [{source.document_id}] access_verified={source.access_verified}")
```

---

## Repository Listing

The senso-ai knowledge base contains 15 specialized repositories:

| # | Repository | Description | Default Access |
|---|-----------|-------------|----------------|
| 1 | `computer-vision-ai` | Image recognition, object detection, segmentation | Org members |
| 2 | `natural-language-processing-ai` | Text analysis, NER, sentiment, translation | Org members |
| 3 | `reinforcement-learning-ai` | RL algorithms, multi-agent systems, robotics | Org members |
| 4 | `generative-models-ai` | GANs, VAEs, diffusion models, LLMs | Org members |
| 5 | `mlops-and-deployment-ai` | Model serving, monitoring, CI/CD for ML | Org members |
| 6 | `ethical-ai-and-fairness` | Bias detection, fairness metrics, responsible AI | Org members |
| 7 | `time-series-forecasting-ai` | ARIMA, Prophet, transformer-based forecasting | Org members |
| 8 | `recommendation-systems-ai` | Collaborative filtering, content-based, hybrid | Org members |
| 9 | `graph-neural-networks-ai` | GNN architectures, knowledge graphs, node classification | Org members |
| 10 | `robotics-and-control-ai` | Motion planning, inverse kinematics, sim-to-real | Org members |
| 11 | `audio-and-speech-ai` | ASR, TTS, audio classification, music generation | Org members |
| 12 | `explainable-ai-ai` | XAI methods, SHAP, LIME, attention visualization | Org members |
| 13 | `financial-data-ai` | **Confidential** — Revenue, budgets, forecasts | Finance team only |
| 14 | `auditing-and-compliance-ai` | **Restricted** — Audit logs, compliance reviews | Auditors only |
| 15 | `privacy-preserving-ai` | **Confidential** — DP, federated learning, anonymization | Privacy team only |

### Access Levels

- **Org members**: Full access to repos 1–12
- **Finance team**: Repo 13 + org-level access
- **Auditors**: Repo 14 (explicit assignment only)
- **Privacy team**: Repo 15 + org-level access
- **Admins**: Full access to all repositories

---

## Privacy-Aware RAG Bot Features

### Dual-Stage Authorization

1. **Pre-filter**: Before any vector search, the system queries Auth0 FGA to determine which resources the user can access. The vector store query is scoped to only those resources.

2. **Post-filter**: After the vector store returns candidates, each result is individually verified against the FGA API to catch any stale grants or cache inconsistencies.

### Zero Leakage Guarantee

The RAG engine will **never**:
- Return a document the user cannot read
- Include unauthorized content in the LLM context
- Cite a source that wasn't access-verified
- Expose document existence through side channels

### Audit Trail

Every retrieval request generates structured audit logs including:
- User ID and query text
- Number of candidates before and after filtering
- Documents denied (with reasons)
- Total latency

---

## Security Model

| Aspect | Implementation |
|--------|---------------|
| **Authentication** | Auth0 JWT tokens |
| **Authorization** | Auth0 FGA (Cedar policy language) |
| **Role hierarchy** | owner > admin > editor > viewer; org_member implicit |
| **Resource hierarchy** | organization > repository > document > section > code_block |
| **Conditional policies** | Published-only, confidential, audit-restricted |
| **Default deny** | All access denied if FGA service is unavailable |
| **Audit logging** | Every allow/deny decision recorded |

---

## Project Structure

```
senso-ai/
├── src/
│   ├── auth0_fga/
│   │   ├── __init__.py              # Package exports
│   │   ├── authorization.py         # FGAClient — core FGA API engine
│   │   ├── models.py                # Data models, role hierarchy, Cedar model
│   │   ├── retrieval_filter.py      # Dual-stage RAG retrieval filter
│   │   └── policy_config.yaml       # Policy configuration (YAML)
│   └── retrieval/
│       ├── __init__.py              # Package exports
│       └── rag_engine.py            # PrivateRAGEngine — full RAG pipeline
├── schema/
│   └── authorization_model.cedar    # Cedar authorization model
├── docs/
│   └── auth0-fga-integration.md    # Integration documentation
└── README.md                        # This file
```

---

## Technology Stack

- **Auth0 FGA** — Fine-grained authorization using Cedar policy language
- **Python 3.9+** — Zero external dependencies for FGA modules
- **Cedar** — Auth0's authorization policy language (Open Policy Agent compatible)
- **urllib.request** — HTTP client (no third-party dependencies)

---

## Auth0 Domain

```
dev-c3wp4h1e4gv0t64i.us.auth0.com
```

---

## License

MIT
