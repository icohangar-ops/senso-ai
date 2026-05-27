# Auth0 FGA Integration — senso-ai Knowledge Base

## Overview

The senso-ai knowledge base uses **Auth0 Fine-Grained Authorization (FGA)** to enforce document-level access control on every RAG (Retrieval-Augmented Generation) query. This ensures that the AI assistant **never retrieves, surfaces, or cites documents the requesting user is not authorized to read**.

This is a critical requirement for enterprise deployments where the knowledge base contains sensitive financial data, proprietary algorithms, and compliance documents across 15 specialized AI/ML repositories.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         User Request Flow                                │
│                                                                          │
│  ┌─────────┐     ┌──────────────┐     ┌──────────────────────────────┐  │
│  │  User    │────▶│  Auth0 Login  │────▶│  Auth0 FGA Check             │  │
│  │ (Alice)  │     │  (JWT token)  │     │  "can user:alice can_query   │  │
│  └─────────┘     └──────────────┘     │   organization:senso-ai?"     │  │
│                                        └──────────┬───────────────────┘  │
│                                                   │ Allowed?             │
│                                                   ▼                      │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │                    RAG Pipeline (Privacy-Aware)                   │    │
│  │                                                                   │    │
│  │  ┌──────────────┐    ┌──────────────┐    ┌───────────────────┐   │    │
│  │  │  FGA Pre-    │───▶│  Vector      │───▶│  FGA Post-        │   │    │
│  │  │  Filter      │    │  Search      │    │  Filter / Rerank  │   │    │
│  │  │              │    │              │    │                   │   │    │
│  │  │  Get user's  │    │  Semantic    │    │  Verify EACH      │   │    │
│  │  │  accessible  │    │  search with │    │  result against   │   │    │
│  │  │  resource    │    │  metadata    │    │  FGA policy       │   │    │
│  │  │  IDs         │    │  filter      │    │                   │   │    │
│  │  └──────────────┘    └──────────────┘    └────────┬──────────┘   │    │
│  │                                                    │              │    │
│  │                                                    ▼              │    │
│  │                                          ┌───────────────────┐   │    │
│  │                                          │  LLM Generation   │   │    │
│  │                                          │  (authorized      │   │    │
│  │                                          │   context only)   │   │    │
│  │                                          └────────┬──────────┘   │    │
│  │                                                   │              │    │
│  └───────────────────────────────────────────────────┼──────────────┘    │
│                                                      │                   │
│                                                      ▼                   │
│                                            ┌──────────────────┐         │
│                                            │  RAG Response     │         │
│                                            │  ┌──────────────┐ │         │
│                                            │  │ answer        │ │         │
│                                            │  │ sources[]     │ │         │
│                                            │  │  └ verified ✓ │ │         │
│                                            │  │ denied_count  │ │         │
│                                            │  └──────────────┘ │         │
│                                            └──────────────────┘         │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Authorization Model

### Resource Types

| Type | Description | Parent |
|------|-------------|--------|
| `organization` | Top-level container (senso-ai) | — |
| `repository` | One of 15 AI/ML domain repos | organization |
| `document` | Individual papers, reports, guides | repository |
| `section` | Sub-section within a document | document |
| `code_block` | Code snippet within a section | section |

### Roles (Relations)

| Role | Privileges | Notes |
|------|-----------|-------|
| `owner` | Full control (read, edit, delete, share, query) | Highest privilege |
| `admin` | Read, edit, share, query | Cannot delete |
| `editor` | Read, edit, share, query | Cannot delete |
| `viewer` | Read, query only | Can only read published docs |
| `org_member` | Read, query (inherited) | Implicit for all authenticated users |

### Permissions

| Permission | Description |
|-----------|-------------|
| `can_read` | View the resource content |
| `can_edit` | Modify the resource content |
| `can_delete` | Remove the resource |
| `can_share` | Grant access to other users |
| `can_query` | Use in RAG retrieval queries |

### Inheritance Rules

1. **Organization → Repository**: Org members are automatically viewers on repositories that have an `organization` relation.
2. **Repository → Document**: Viewers of a repository can read all non-confidential documents within it.
3. **Document → Section → Code Block**: Access propagates downward through the hierarchy.
4. **Confidential Override**: Documents marked `confidential: true` do NOT inherit repository-level viewer access. Only explicitly assigned viewers, editors, admins, and owners can read them.
5. **Published Guard**: Viewers can only read documents where `published: true`. Editors and admins bypass this guard.

---

## Setup Guide

### 1. Auth0 FGA Dashboard

1. Log in to [Auth0 Dashboard](https://manage.auth0.com/).
2. Navigate to **Applications → APIs → Auth0 FGA**.
3. Note the **API URL** and **API Token**.
4. Create a **store** and note the **Store ID**.

### 2. Environment Configuration

```bash
export AUTH0_FGA_API_URL="https://api.us1.fga.dev"
export AUTH0_FGA_API_TOKEN="your-api-token-here"
export AUTH0_FGA_STORE_ID="your-store-id-here"
```

### 3. Deploy the Authorization Model

```python
from auth0_fga import FGAClient, AuthorizationModel

fga = FGAClient()

# Build and deploy the default authorization model
model = AuthorizationModel.default_model()
model_id = fga.write_authorization_model(model)
print(f"Deployed model: {model_id}")
```

Alternatively, deploy the Cedar model file directly via the Auth0 FGA CLI:

```bash
fga model write --file schema/authorization_model.cedar --store-id $AUTH0_FGA_STORE_ID
```

### 4. Configure Initial Policies

```python
from auth0_fga import FGAClient, DocumentPolicy

fga = FGAClient()

# Assign a user as viewer on a repository
fga.assign_role("user:alice@company.com", "viewer", "repository:computer-vision-ai")

# Create a document-level policy
policy = DocumentPolicy(
    resource_type="document",
    resource_id="doc:quarterly-report",
    viewers=["user:cfo@company.com", "user:finance-lead@company.com"],
    editors=["user:financial-analyst@company.com"],
    owners=["user:cfo@company.com"],
)
fga.create_policy_from_document_policy(policy)
```

---

## How Document-Level Access Control Works

### Pre-Filter Stage

Before any vector search happens, the system queries Auth0 FGA to get the list of resource IDs the user can access:

```python
accessible = fga.list_resources(user_id="user:alice", relation="can_read", resource_type="document")
# Returns: ["document:cv-paper-001", "document:cv-tutorial-002", ...]
```

These IDs are injected as a metadata filter into the vector search, ensuring the embedding database never returns unauthorized documents.

### Post-Filter Stage

After the vector search returns candidates, each result is individually verified:

```python
decisions = fga.batch_check_access("user:alice", [("can_read", "document:cv-paper-001"), ...])
```

This catches any edge cases where the pre-filter might be stale (e.g., a role was just revoked, cache hasn't propagated).

### Result

The LLM only receives context from documents that passed **both** filters. The response includes an `access_verified` flag on every source citation.

---

## Security Guarantees

| Guarantee | Mechanism |
|-----------|-----------|
| **Zero document leakage** | Pre-filter limits vector search; post-filter verifies each result |
| **Zero-trust verification** | Every access decision is independently verified via FGA API |
| **Deny by default** | If the FGA service is unavailable, all access is denied |
| **Full audit trail** | Every allow/deny decision is logged with user, document, and reason |
| **Role hierarchy enforcement** | Admin > Editor > Viewer; org_member is implicit |
| **Confidential document isolation** | Confidential documents bypass org-level inheritance |
| **Condition-based policies** | Published-only, audit-restricted, and explicit-access rules |

---

## API Reference

### `FGAClient`

```python
class FGAClient:
    def __init__(self, api_url=None, api_token=None, store_id=None, timeout=30): ...
    def check_access(user_id, relation, resource_id) -> AccessDecision: ...
    def create_policy(resource_type, resource_id, relations) -> None: ...
    def create_policy_from_document_policy(policy: DocumentPolicy) -> None: ...
    def assign_role(user_id, role, resource_id) -> None: ...
    def revoke_role(user_id, role, resource_id) -> None: ...
    def list_resources(user_id, relation, resource_type=None) -> List[str]: ...
    def batch_check_access(user_id, items) -> List[AccessDecision]: ...
    def write_authorization_model(model: AuthorizationModel) -> str: ...
    def health_check() -> bool: ...
```

### `RetrievalFilter`

```python
class RetrievalFilter:
    def __init__(self, fga_client, vector_search_fn, resource_type="document", ...): ...
    def query(user_id, query_text, top_k=10, filters=None) -> List[FilteredResult]: ...
    def filter_documents(user_id, documents) -> List[FilteredResult]: ...
    def get_accessible_repos(user_id) -> List[str]: ...
```

### `PrivateRAGEngine`

```python
class PrivateRAGEngine:
    def __init__(self, fga_client, vector_store, llm_client, context_window=4000, ...): ...
    def query(user_id, question, top_k=10) -> RAGResponse: ...
    def ingest(document_id, content, access_policy, metadata=None) -> None: ...
    def update_policy(document_id, new_policy) -> None: ...
    def revoke_document_access(document_id, user_id) -> None: ...
```

---

## Example Scenarios

### Scenario 1: CFO Queries Financial Data

```
User: cfo@senso-ai.com
Query: "What was our Q3 revenue growth?"

Flow:
  1. Auth0 login → JWT token issued
  2. FGA check: can_query organization:senso-ai → ALLOWED (org_member)
  3. Pre-filter: list_resources(cfo, can_read, document)
     → ["doc:q3-report", "doc:q3-forecast", "doc:annual-budget", ...]
  4. Vector search with metadata filter → returns 5 candidates
  5. Post-filter: batch_check_access → all 5 allowed
  6. LLM generates answer citing verified sources

Result: CFO sees financial documents with full access_verified flags.
```

### Scenario 2: Engineer Queries Computer Vision

```
User: ml-engineer@senso-ai.com
Query: "How does the ViT attention mechanism work?"

Flow:
  1. Auth0 login → JWT token issued
  2. FGA check: can_query organization:senso-ai → ALLOWED
  3. Pre-filter: accessible docs include computer-vision-ai repo docs
  4. Vector search → returns 8 candidates (CV papers, tutorials)
  5. Post-filter: 7 allowed, 1 denied (confidential internal strategy doc)
  6. LLM generates answer from 7 verified sources

Result: Engineer sees CV content but NOT confidential strategy documents.
        access_denied_count = 1 in the response.
```

### Scenario 3: Auditor Sees Audit Trail

```
User: auditor@senso-ai.com
Query: "Show me the compliance review for the bias detection model"

Flow:
  1. Auth0 login → JWT token issued
  2. FGA check: can_query organization:senso-ai → ALLOWED
  3. Pre-filter: auditor has explicit access to auditing-and-compliance-ai repo
  4. Vector search → returns audit documents
  5. Post-filter: all verified
  6. LLM generates answer citing audit sources

Result: Auditor sees compliance docs with full audit trail logged.
```

### Scenario 4: New Employee (No Special Access)

```
User: new-hire@senso-ai.com
Query: "What are our financial projections?"

Flow:
  1. Auth0 login → JWT token issued
  2. FGA check: can_query organization:senso-ai → ALLOWED (org_member)
  3. Pre-filter: NO access to financial-data-ai repo (confidential)
  4. Vector search with empty filter → returns general docs only
  5. Post-filter: further removes any leaked financial docs
  6. LLM responds: "No relevant documents available based on your access permissions."

Result: New employee sees ZERO financial data. Complete isolation.
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `AUTH0_FGA_API_URL` | No (has default) | Base URL of the Auth0 FGA API |
| `AUTH0_FGA_API_TOKEN` | Yes | Bearer token for API authentication |
| `AUTH0_FGA_STORE_ID` | Yes | FGA store identifier |

---

## Auth0 Domain

- **Domain**: `dev-c3wp4h1e4gv0t64i.us.auth0.com`
- **FGA API**: `https://api.us1.fga.dev` (default)
