#!/usr/bin/env python3
"""Evidence check: the Quick Start snippets' imports and API surface exist.

Backs README "Quick Start" (as amended with the PYTHONPATH=src note): the
documented import paths (``from auth0_fga import ...``,
``from retrieval.rag_engine import ...``) resolve, the documented classes and
methods exist, the authorization model builds, and the documented response
fields (answer, sources with access_verified) are real.

Runs offline: imports the packages with a stubbed resilience dependency and
asserts the API surface without calling any network method.
"""
import inspect
import sys
import types
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _bootstrap_stubs():
    try:
        import cubiczan_resilience  # noqa: F401
    except ImportError:
        stub = types.ModuleType("cubiczan_resilience")

        def _passthrough(*decorator_args, **decorator_kwargs):
            def decorator(fn):
                return fn

            return decorator

        stub.resilient = _passthrough
        stub.RetriesExhausted = type("RetriesExhausted", (Exception,), {})
        sys.modules["cubiczan_resilience"] = stub
    sys.path.insert(0, str(REPO_ROOT / "src"))


def main():
    _bootstrap_stubs()

    # Quick Start snippet 1 imports.
    import auth0_fga
    from auth0_fga import AuthorizationModel, FGAClient, RetrievalFilter
    from retrieval.rag_engine import PrivateRAGEngine  # Quick Start snippet 2 import

    # The deployment snippet's model source exists and builds in memory
    # with the five documented resource types.
    model = AuthorizationModel.default_model()
    assert {rt["type"] for rt in model.resource_types} == {
        "organization",
        "repository",
        "document",
        "section",
        "code_block",
    }

    # FGAClient methods used across the README examples.
    for method in (
        "write_authorization_model",
        "create_policy",
        "assign_role",
        "check_access",
        "batch_check_access",
        "list_resources",
        "health_check",
    ):
        assert hasattr(FGAClient, method), f"FGAClient.{method} missing"

    # Environment-only construction matches the README (no args required);
    # with credentials set via environment they are picked up.
    import os

    client = FGAClient()
    assert client.api_url  # falls back to the packaged default endpoint
    os.environ["AUTH0_FGA_API_URL"] = "https://api.us1.fga.dev"
    os.environ["AUTH0_FGA_STORE_ID"] = "store-from-env"
    try:
        client_env = FGAClient()
        assert client_env.api_url == "https://api.us1.fga.dev"
        assert client_env.store_id == "store-from-env"
    finally:
        os.environ.pop("AUTH0_FGA_API_URL", None)
        os.environ.pop("AUTH0_FGA_STORE_ID", None)

    # RetrievalFilter construction matches the README signature.
    params = inspect.signature(RetrievalFilter.__init__).parameters
    for expected in ("fga_client", "vector_search_fn", "resource_type"):
        assert expected in params, f"RetrievalFilter param {expected} missing"

    # PrivateRAGEngine construction and documented response shape.
    engine_params = inspect.signature(PrivateRAGEngine.__init__).parameters
    for expected in ("fga_client", "vector_store", "llm_client", "context_window"):
        assert expected in engine_params, f"PrivateRAGEngine param {expected} missing"
    assert auth0_fga.FGAClient is FGAClient
    from retrieval.rag_engine import RAGResponse, RAGSource

    assert "answer" in RAGResponse.__dataclass_fields__ and "sources" in RAGResponse.__dataclass_fields__
    assert "document_id" in RAGSource.__dataclass_fields__ and "access_verified" in RAGSource.__dataclass_fields__

    print("verify_quick_start: PASS (Quick Start imports, FGAClient/RetrievalFilter/PrivateRAGEngine surfaces, model build, response fields)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
