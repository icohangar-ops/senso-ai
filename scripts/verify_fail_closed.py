#!/usr/bin/env python3
"""Evidence check: default-deny when the FGA service is unavailable or misconfigured.

Backs README "Security Model" (Default deny) and docs/auth0-fga-integration.md
"Security Guarantees" (Deny by default): check_access denies closed on FGA
authentication and service errors, and get_accessible_repos propagates a
service outage instead of silently treating it as an empty allowlist.

Runs offline: the HTTP transport is monkeypatched, no network is touched.
"""
import sys
import types
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _bootstrap_stubs() -> None:
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


def main() -> int:
    _bootstrap_stubs()
    from auth0_fga.authorization import (
        FGAAuthenticationError,
        FGAError,
        FGAClient,
        FGAUnavailableError,
    )

    # FGAUnavailableError is an FGAError, so every FGAError handler denies closed.
    assert issubclass(FGAUnavailableError, FGAError)
    assert issubclass(FGAAuthenticationError, FGAError)

    client = FGAClient(api_url="https://fga.invalid", api_token="test-token", store_id="store-1")

    # ---- Authentication failure -> deny by default -------------------------
    def raise_auth(*args, **kwargs):
        raise FGAAuthenticationError("bad credentials")

    client._request = raise_auth  # type: ignore[method-assign]
    decision = client.check_access("user:alice", "can_read", "document:q3-revenue")
    assert decision.allowed is False, "authentication failure must deny"
    assert "denied by default" in decision.reason, decision.reason
    assert decision.resource_id == "document:q3-revenue"

    # ---- Service unavailable -> deny by default ----------------------------
    def raise_unavailable(*args, **kwargs):
        raise FGAUnavailableError("FGA service down")

    client._request = raise_unavailable  # type: ignore[method-assign]
    decision = client.check_access("user:alice", "can_read", "document:q3-revenue")
    assert decision.allowed is False, "service unavailability must deny"
    assert decision.reason.startswith("FGA service error"), decision.reason

    # ---- batch_check_access: one AccessDecision per item, all denied -------
    decisions = client.batch_check_access(
        "user:alice",
        [("can_read", "document:a"), ("can_read", "document:b"), ("can_read", "document:c")],
    )
    assert len(decisions) == 3 and all(d.allowed is False for d in decisions)

    # ---- Pre-filter propagation: outage is not an empty allowlist ----------
    from auth0_fga.retrieval_filter import RetrievalFilter

    class OutageFGA(FGAClient):
        def list_resources(self, user_id, relation, resource_type=None):
            raise FGAUnavailableError("FGA service down")

    rfilter = RetrievalFilter(fga_client=OutageFGA(api_url="https://fga.invalid", api_token="t", store_id="s"))
    try:
        rfilter.get_accessible_repos("user:alice")
    except FGAUnavailableError:
        pass  # correct: the outage propagates so callers fail closed deliberately
    else:
        raise AssertionError("FGAUnavailableError was swallowed by get_accessible_repos")

    print("verify_fail_closed: PASS (auth failure denies, service outage denies, batch denies, outage propagates from pre-filter)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
