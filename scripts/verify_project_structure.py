#!/usr/bin/env python3
"""Evidence check: the README Project Structure tree matches the actual tree.

Backs README "Project Structure": every file path shown in the README's
structure listing exists in the repository, and the listing covers the
implementation packages (src/auth0_fga, src/retrieval, src/airbyte_ingestion.py,
auth0_fga_rag/, schema/, docs/).

Runs offline: parses README.md and walks the tree. Exit 0 = held.
"""
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

REQUIRED_ENTRIES = (
    "src/auth0_fga/authorization.py",
    "src/auth0_fga/retrieval_filter.py",
    "src/retrieval/rag_engine.py",
    "src/airbyte_ingestion.py",
    "schema/authorization_model.cedar",
)


def _parse_structure_fence(readme_text):
    """Extract file paths from the README's Project Structure code fence."""
    match = re.search(r"##\s+Project Structure.*?```\n(.*?)```", readme_text, re.DOTALL)
    if not match:
        raise AssertionError("README Project Structure code fence not found")
    lines = match.group(1).splitlines()

    # Reconstruct relative paths from box-drawing indentation depth.
    stack = []  # (depth, name)
    paths = []
    for line in lines:
        marker = re.search(r"[├└]──\s+(\S+)", line)
        if not marker:
            continue
        name = marker.group(1).rstrip("/")
        depth = (marker.start() + 1) // 4
        while stack and stack[-1][0] >= depth:
            stack.pop()
        stack.append((depth, name))
        paths.append(("/".join(name for _d, name in stack), name.endswith("/")))
    return paths


def main():
    readme_text = (REPO_ROOT / "README.md").read_text()
    paths = _parse_structure_fence(readme_text)
    assert paths, "no structure entries parsed from README"

    file_paths = [p for p, is_dir in paths if not is_dir]
    missing = [p for p in file_paths if not (REPO_ROOT / p).exists()]
    assert not missing, f"README structure lists paths that do not exist: {missing}"

    for required in REQUIRED_ENTRIES:
        assert required in file_paths, f"README structure is missing {required}"

    print(f"verify_project_structure: PASS ({len(file_paths)} README-listed files all exist; implementation packages covered)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
