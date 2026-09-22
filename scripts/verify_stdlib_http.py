#!/usr/bin/env python3
"""Evidence check: FGA modules use stdlib urllib for HTTP, not a third-party client.

Backs the README "Key Features" claim as reworded: HTTP transport in
auth0_fga is standard-library ``urllib.request`` only — no requests/httpx/
aiohttp/urllib3 — while the one non-stdlib runtime dependency is the
``cubiczan-resilience`` retry wrapper (pinned in requirements.txt).

Runs offline: AST-scans the source tree. Exit 0 = held.
"""
import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

FORBIDDEN_HTTP_CLIENTS = {"requests", "httpx", "aiohttp", "urllib3", "pycurl"}

SCAN_PACKAGES = ("src/auth0_fga", "src/retrieval")


def main() -> int:
    scanned = 0
    for package in SCAN_PACKAGES:
        for py_file in sorted((REPO_ROOT / package).rglob("*.py")):
            tree = ast.parse(py_file.read_text())
            imports = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.update(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                    imports.add(node.module.split(".")[0])
            bad = imports & FORBIDDEN_HTTP_CLIENTS
            assert not bad, f"{py_file.relative_to(REPO_ROOT)} imports third-party HTTP client(s): {sorted(bad)}"
            scanned += 1

    authorization_text = (REPO_ROOT / "src" / "auth0_fga" / "authorization.py").read_text()
    assert "urllib.request" in authorization_text, "FGA HTTP transport is not urllib.request"
    assert "from cubiczan_resilience import" in authorization_text, (
        "cubiczan_resilience import missing — README and requirements.txt document it as the resilience dependency"
    )

    requirements = (REPO_ROOT / "requirements.txt").read_text()
    assert "cubiczan-resilience" in requirements

    print(f"verify_stdlib_http: PASS ({scanned} modules scanned; no third-party HTTP client; urllib.request transport + cubiczan_resilience retry wrapper)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
