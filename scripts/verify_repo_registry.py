#!/usr/bin/env python3
"""Evidence check: the FGA registry really protects the 15 advertised repositories.

Backs README "Repository Listing" (15 specialized AI/ML repositories) and the
Cedar model's 15-repo scope: policy_config.yaml must declare exactly 15
``repository`` resources, and the slug set must equal the README table.

Runs offline: reads policy_config.yaml and README.md text. Exit 0 = held.
"""
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    policy_text = (REPO_ROOT / "src" / "auth0_fga" / "policy_config.yaml").read_text()
    readme_text = (REPO_ROOT / "README.md").read_text()

    # policy_config.yaml: repository resources under initial_assignments.
    registry_ids = re.findall(r'- resource:\s*"repository:([^"]+)"', policy_text)
    assert len(registry_ids) == 15, f"expected 15 repository resources, found {len(registry_ids)}: {registry_ids}"
    assert len(set(registry_ids)) == 15, "duplicate repository resources in policy_config.yaml"

    # README table: slugs appear in the second cell of Repository Listing rows.
    readme_slugs = re.findall(r"\|\s*\d+\s*\|\s*`([a-z0-9-]+)`", readme_text)
    assert len(readme_slugs) == 15, f"expected 15 README table rows, found {len(readme_slugs)}: {readme_slugs}"

    registry_set = set(registry_ids)
    readme_set = set(readme_slugs)
    assert registry_set == readme_set, (
        f"README/policy mismatch — in README only: {sorted(readme_set - registry_set)}, "
        f"in policy_config only: {sorted(registry_set - readme_set)}"
    )

    # The Cedar model comment pins the same scope.
    cedar_text = (REPO_ROOT / "schema" / "authorization_model.cedar").read_text()
    assert "15 repos" in cedar_text, "Cedar model scope comment missing"

    print(f"verify_repo_registry: PASS (policy_config declares exactly the 15 README slugs: {sorted(registry_set)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
