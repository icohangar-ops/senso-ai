# Auth0 FGA Privacy-Aware RAG Bot

> MLH Global Hack Week: GenAI — Auth0 Partner Challenge
> Demonstrate document-level access control in RAG using Auth0 Fine-Grained Authorization

---

## The Challenge

Build an internal-facing knowledge assistant that sources answers from a document database via RAG (Retrieval-Augmented Generation), where the assistant enforces **document-level access control** based on the logged-in user's role and department.

**Key Requirement:** A manager can access salary documents, but a general employee cannot — even if the document exists in the RAG index.

## How It Works

```
┌──────────┐     ┌──────────────┐     ┌───────────┐     ┌──────────────┐
│   User    │────▶│   RAG Query  │────▶│  RAG Index │────▶│  Candidate   │
│ (Alice)   │     │  "financial  │     │  (All Docs)│     │  Documents   │
│           │     │   outlook?"  │     │            │     │  (5 results) │
└──────────┘     └──────────────┘     └─────────────┘     └──────┬───────┘
                                                               │
                                                               ▼
                                                     ┌──────────────────┐
                                                     │   Auth0 FGA      │
                                                     │   Access Check   │
                                                     │                  │
                                                     │  budget_Q4_2025  │──▶ ✓ Alice can read
                                                     │  salary_band_guide │─▶ ✗ Alice DENIED
                                                     │  company_handbook │──▶ ✓ Alice can read
                                                     └────────┬─────────┘
                                                              │
                                                              ▼
                                                     ┌──────────────────┐
                                                     │  Filtered RAG    │
                                                     │  Context         │
                                                     │  (2 docs only)   │
                                                     └────────┬─────────┘
                                                              │
                                                              ▼
                                                     ┌──────────────────┐
                                                     │  LLM Response    │
                                                     │  (based ONLY on  │
                                                     │  accessible docs)│
                                                     └──────────────────┘
```

## Architecture

### Authorization Model

```yaml
model
  schema 1.1

type user

type document
  relations
    define owner: [user]
    define editor: [user, manager#member] or owner
    define reader: [user, editor] or manager#member or public_reader
    define manager: [user] or manager#member

type department
  relations
    define member: [user]
    define head: [user]
```

### Module Structure

```
auth0_fga_rag/
├── __init__.py                # Package exports and version
├── fga_config.py              # Auth0 FGA API configuration
├── authorization_model.py     # FGA authorization model definition
├── fga_client.py              # Auth0 FGA API client (check/write/list)
├── document_store.py          # Document database with 14 sample documents
├── rag_engine.py              # RAG engine with FGA-filtered retrieval
├── demo.py                    # Demo script (runs offline in simulated mode)
└── README.md                  # This file
```

### Sample Users & Access

| User | Role | Department | Accessible Docs |
|------|------|-----------|----------------|
| Alice | Finance Manager | Finance | Q4 Budget, Revenue Forecast, Salary Band Guide, Public docs |
| Bob | HR Intern | HR | Public docs only |
| Carol | Engineering Analyst | Engineering | Architecture, Code Review, Incident Postmortem, Public docs |
| Dave | CEO | Executive | **ALL documents** (unrestricted) |

### Sample Documents

`document_store.py` ships 14 sample documents (`SAMPLE_DOCUMENTS`):

| Document ID | Department | Sensitivity | Owner |
|-------------|-----------|-------------|-------|
| `budget_Q4_2025` | Finance | Confidential | `user:alice` |
| `revenue_forecast_2025` | Finance | Confidential | `user:alice` |
| `salary_band_guide` | HR | Restricted | `user:hr_director` |
| `executive_comp_report` | HR | Restricted | `user:dave` |
| `performance_reviews_Q4` | HR | Confidential | `user:hr_director` |
| `architecture_v3` | Engineering | Internal | `user:carol` |
| `code_review_standards` | Engineering | Internal | `user:carol` |
| `incident_postmortem_2024_12` | Engineering | Internal | `user:carol` |
| `ma_strategy_2025` | Executive | Restricted | `user:dave` |
| `company_strategy_2025` | Executive | Restricted | `user:dave` |
| `board_deck_Q4` | Executive | Restricted | `user:dave` |
| `company_handbook` | Public | Public | `user:hr_director` |
| `org_chart` | Public | Public | `user:hr_director` |
| `engineering_tech_stack` | Public | Public | `user:carol` |

## Quick Start

### Prerequisites

- Python 3.11+
- `requests` (`pip install requests`) — imported by the FGA client for the live-API path; the demo itself runs offline in simulated mode

### Run the Demo

```bash
cd senso-ai
python -m auth0_fga_rag.demo
```

No Auth0 credentials required — the demo runs in simulated mode with an in-memory FGA store.

### Output

The demo runs the same query (`"What is the company's financial outlook and strategy?"`) for 4 different users and shows:

1. **Individual FGA checks** — Each document is checked: ✓ ALLOWED or ✗ DENIED
2. **RAG retrieval results** — Only accessible documents appear in results
3. **LLM-generated response** — Based ONLY on documents the user can access
4. **Comparison table** — Same query, different result counts per user

### Key Demonstrations

| Scenario | Expected Behavior |
|----------|-------------------|
| Bob queries salary info | ✗ DENIED — HR Intern cannot see salary docs |
| Alice queries budget | ✓ ALLOWED — Finance Manager sees budget |
| Dave queries M&A strategy | ✓ ALLOWED — CEO has unrestricted access |
| Carol queries financial outlook | ✗ DENIED — Engineer cannot see finance docs |
| Same query, 4 users | 4 different responses based on role |

## Auth0 FGA Setup (Production)

To connect to a real Auth0 FGA instance:

```bash
export AUTH0_FGA_API_URL=https://api.us.auth0.com
export AUTH0_FGA_API_TOKEN=your-fga-api-token
export AUTH0_FGA_STORE_ID=your-store-id
```

Then run the demo — it will use the real FGA API for authorization checks.

## MLH Challenge Requirements Mapping

| Requirement | Implementation |
|-------------|---------------|
| ✅ Auth0 FGA for access control | `fga_client.py` — check/write/list tuples |
| ✅ RAG pipeline | `rag_engine.py` — embed → retrieve → generate |
| ✅ Document-level access control | `document_store.py` — FGA check on every retrieval |
| ✅ Manager vs employee access | Demo shows Dave (CEO) vs Bob (Intern) |
| ✅ Correct denial of sensitive docs | Bob cannot access salary, M&A, or budget docs |
| ✅ LLM respects authorization | Response generated only from accessible documents |

## Tech Stack

- **Python 3.11+**
- **Auth0 FGA** (Fine-Grained Authorization)
- **RAG** (Retrieval-Augmented Generation)
- **requests** (HTTP client)

## Evidence Matrix

Every capability claim in this file is backed by `evidence/matrix.yaml` at the repository root; CI refuses builds while any row is unverifiable (`python3 tools/verify_evidence_matrix.py`).
