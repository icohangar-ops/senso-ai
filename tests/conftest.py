"""Shared test bootstrap: path setup and offline stubs.

The suite runs without installing dependencies (CI has no install step for
the evidence job and installs only pytest for this job). Optional runtime
dependencies that the simulated/offline paths never exercise are stubbed:
``cubiczan_resilience`` (retry decorator passthrough) and ``requests``
(live-API HTTP client in ``auth0_fga_rag.fga_client``).
"""
import sys
import types
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
for p in (str(REPO_ROOT), str(REPO_ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

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

try:
    import requests  # noqa: F401
except ImportError:
    stub = types.ModuleType("requests")
    stub.post = None  # live-API calls would fail loudly if ever reached
    sys.modules["requests"] = stub
