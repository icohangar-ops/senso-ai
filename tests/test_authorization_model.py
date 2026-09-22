"""Cedar authorization model: resource types, role hierarchy, permissions."""
from auth0_fga.models import (
    AuthorizationModel,
    Permission,
    Role,
    role_has_permission,
    role_is_higher_or_equal,
)


def test_role_hierarchy_and_resource_types():
    model = AuthorizationModel.default_model()
    assert {rt["type"] for rt in model.resource_types} == {
        "organization",
        "repository",
        "document",
        "section",
        "code_block",
    }

    # Repository inherits from organization; document from repository.
    repo_type = next(rt for rt in model.resource_types if rt["type"] == "repository")
    assert "can_read" in repo_type["permissions"]
    assert "organization" in repo_type["relations"]
    doc_type = next(rt for rt in model.resource_types if rt["type"] == "document")
    assert "can_read" in doc_type["permissions"]
    assert "repository" in doc_type["relations"]

    # owner > admin > editor > viewer, enforced pairwise.
    assert role_is_higher_or_equal(Role.OWNER, Role.ADMIN)
    assert role_is_higher_or_equal(Role.ADMIN, Role.EDITOR)
    assert role_is_higher_or_equal(Role.EDITOR, Role.VIEWER)
    assert not role_is_higher_or_equal(Role.VIEWER, Role.EDITOR)
    assert role_is_higher_or_equal(Role.OWNER, Role.VIEWER)

    assert role_has_permission(Role.ADMIN, Permission.CAN_DELETE)
    assert role_has_permission(Role.EDITOR, Permission.CAN_EDIT)
    assert role_has_permission(Role.VIEWER, Permission.CAN_READ)
    assert not role_has_permission(Role.VIEWER, Permission.CAN_DELETE)
