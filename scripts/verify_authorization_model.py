#!/usr/bin/env python3
"""Evidence check: Cedar authorization model, role hierarchy, conditional policies.

Backs README "Security Model" (Cedar model + role hierarchy + conditional
policies) and docs/auth0-fga-integration.md "Security Guarantees" (role
hierarchy enforcement, confidential document isolation, condition-based
policies): five FGA resource types, transitive reader access, the
owner > admin > editor > viewer privilege ordering, and the three named
conditional policies declared in policy_config.yaml and the Cedar model.

Runs offline: builds AuthorizationModel.default_model() in memory and reads
committed config files. Exit 0 = held.
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
    from auth0_fga.models import (
        AuthorizationModel,
        Permission,
        Role,
        role_has_permission,
        role_is_higher_or_equal,
    )

    model = AuthorizationModel.default_model()

    # Five resource types: organization > repository > document/section/code_block.
    type_names = {rt["type"] for rt in model.resource_types}
    assert type_names == {"organization", "repository", "document", "section", "code_block"}, type_names

    # Repository inherits from organization; document from repository (transitive can_read).
    repo_type = next(rt for rt in model.resource_types if rt["type"] == "repository")
    assert "can_read" in repo_type["permissions"]
    assert "organization" in repo_type["relations"], "repository must inherit from organization"
    doc_type = next(rt for rt in model.resource_types if rt["type"] == "document")
    assert "can_read" in doc_type["permissions"]
    assert "repository" in doc_type["relations"], "document must inherit from repository"

    # Role hierarchy: owner > admin > editor > viewer, enforced pairwise.
    assert role_is_higher_or_equal(Role.OWNER, Role.ADMIN)
    assert role_is_higher_or_equal(Role.ADMIN, Role.EDITOR)
    assert role_is_higher_or_equal(Role.EDITOR, Role.VIEWER)
    assert not role_is_higher_or_equal(Role.VIEWER, Role.EDITOR)
    assert role_is_higher_or_equal(Role.OWNER, Role.VIEWER)

    # Privilege checks: admin deletes, viewer only reads.
    assert role_has_permission(Role.ADMIN, Permission.CAN_DELETE)
    assert role_has_permission(Role.EDITOR, Permission.CAN_EDIT)
    assert role_has_permission(Role.VIEWER, Permission.CAN_READ)
    assert not role_has_permission(Role.VIEWER, Permission.CAN_DELETE)

    # Conditional policies declared in the committed policy configuration.
    policy_text = (REPO_ROOT / "src" / "auth0_fga" / "policy_config.yaml").read_text()
    assert "conditional_policies:" in policy_text
    for policy_name in (
        "viewer_read_published_only",
        "confidential_requires_explicit_access",
        "audit_documents_restricted",
    ):
        assert policy_name in policy_text, f"missing conditional policy: {policy_name}"

    # The same conditions exist in the committed Cedar model.
    cedar_text = (REPO_ROOT / "schema" / "authorization_model.cedar").read_text()
    for condition in ("isPublished", "isNotConfidential", "isNotAudit"):
        assert condition in cedar_text, f"missing Cedar condition: {condition}"

    print("verify_authorization_model: PASS (5 resource types, transitive document read, owner>admin>editor>viewer, 3 conditional policies in YAML+Cedar)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
