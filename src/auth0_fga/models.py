"""
Authorization models for Auth0 FGA integration.

Defines the Cedar authorization model, resource types, role hierarchy,
and access decision data structures used throughout the senso-ai platform.

Role Hierarchy:
    admin > editor > viewer
    org_member is an implicit base role for all authenticated users.

Resource Hierarchy:
    organization > repository > document > section > code_block
"""

from __future__ import annotations

import enum
import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class ResourceType(str, Enum):
    """Types of resources managed in the senso-ai knowledge base."""

    ORGANIZATION = "organization"
    REPOSITORY = "repository"
    DOCUMENT = "document"
    SECTION = "section"
    CODE_BLOCK = "code_block"


class Relation(str, Enum):
    """User relations (roles) on a resource."""

    OWNER = "owner"
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"
    ORG_MEMBER = "org_member"


class Permission(str, Enum):
    """Permissions that can be granted on a resource."""

    CAN_READ = "can_read"
    CAN_EDIT = "can_edit"
    CAN_DELETE = "can_delete"
    CAN_SHARE = "can_share"
    CAN_QUERY = "can_query"


class Role(str, enum.Enum):
    """High-level role abstractions mapping to Cedar relations."""

    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"
    ORG_MEMBER = "org_member"
    OWNER = "owner"


# ---------------------------------------------------------------------------
# Role hierarchy
# ---------------------------------------------------------------------------

# Higher index = more privilege.  An admin implicitly has editor and viewer.
_ROLE_PRIVILEGE: Dict[Role, int] = {
    Role.VIEWER: 0,
    Role.ORG_MEMBER: 0,
    Role.EDITOR: 1,
    Role.ADMIN: 2,
    Role.OWNER: 3,
}

# Mapping from role to the set of permissions it grants.
_ROLE_PERMISSIONS: Dict[Role, List[Permission]] = {
    Role.VIEWER: [Permission.CAN_READ, Permission.CAN_QUERY],
    Role.ORG_MEMBER: [Permission.CAN_READ, Permission.CAN_QUERY],
    Role.EDITOR: [
        Permission.CAN_READ,
        Permission.CAN_QUERY,
        Permission.CAN_EDIT,
        Permission.CAN_SHARE,
    ],
    Role.ADMIN: [
        Permission.CAN_READ,
        Permission.CAN_QUERY,
        Permission.CAN_EDIT,
        Permission.CAN_DELETE,
        Permission.CAN_SHARE,
    ],
    Role.OWNER: [
        Permission.CAN_READ,
        Permission.CAN_QUERY,
        Permission.CAN_EDIT,
        Permission.CAN_DELETE,
        Permission.CAN_SHARE,
    ],
}


def role_has_permission(role: Role, permission: Permission) -> bool:
    """Return ``True`` if *role* grants *permission*."""
    return permission in _ROLE_PERMISSIONS.get(role, [])


def role_is_higher_or_equal(a: Role, b: Role) -> bool:
    """Return ``True`` if role *a* has at least the privilege of role *b*."""
    return _ROLE_PRIVILEGE.get(a, -1) >= _ROLE_PRIVILEGE.get(b, -1)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Resource:
    """Represents a protectable resource in the knowledge base.

    Attributes:
        resource_type: The type of resource (repository, document, etc.).
        resource_id: Unique identifier (e.g. ``"repo:computer-vision"``).
        attributes: Arbitrary metadata attached to the resource.
    """

    resource_type: ResourceType
    resource_id: str
    attributes: Dict[str, Any] = field(default_factory=dict)

    def fga_object(self) -> Dict[str, str]:
        """Return the Auth0 FGA object representation ``{"object": "..."}``."""
        return {"object": f"{self.resource_type.value}:{self.resource_id}"}

    def __hash__(self) -> int:
        return hash((self.resource_type, self.resource_id))


@dataclass
class AccessDecision:
    """Result of an authorization check.

    Attributes:
        allowed: Whether access was granted.
        resource_id: The resource that was checked.
        relation: The relation / permission that was evaluated.
        reason: Human-readable explanation.
        policy_id: Optional identifier linking back to the governing policy.
    """

    allowed: bool
    resource_id: str
    relation: str
    reason: str = ""
    policy_id: Optional[str] = None
    checked_at: float = field(default_factory=time.time)
    decision_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def __bool__(self) -> bool:
        return self.allowed


@dataclass
class DocumentPolicy:
    """Convenience wrapper for defining a document's access policy.

    Attributes:
        resource_type: Type of resource this policy applies to.
        resource_id: Unique identifier for the resource.
        owners: Users with owner privileges.
        admins: Users with admin privileges.
        editors: Users who can edit.
        viewers: Users who can read.
        org_members: Users who are implicit org members.
        conditions: Optional Cedar conditions (e.g. ``{"document": {"published": true}}``).
    """

    resource_type: str = "document"
    resource_id: str = ""
    owners: List[str] = field(default_factory=list)
    admins: List[str] = field(default_factory=list)
    editors: List[str] = field(default_factory=list)
    viewers: List[str] = field(default_factory=list)
    org_members: List[str] = field(default_factory=list)
    conditions: Optional[Dict[str, Any]] = None

    def to_relations(self) -> Dict[str, List[str]]:
        """Convert to a flat relation map suitable for FGA write tuples."""
        relations: Dict[str, List[str]] = {}
        if self.owners:
            relations["owner"] = self.owners
        if self.admins:
            relations["admin"] = self.admins
        if self.editors:
            relations["editor"] = self.editors
        if self.viewers:
            relations["viewer"] = self.viewers
        if self.org_members:
            relations["org_member"] = self.org_members
        return relations

    @property
    def policy_id(self) -> str:
        """Deterministic policy hash for audit / correlation."""
        payload = json.dumps(
            {
                "resource_type": self.resource_type,
                "resource_id": self.resource_id,
                "relations": self.to_relations(),
                "conditions": self.conditions,
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()[:16]


@dataclass
class AuthorizationModel:
    """Represents a Cedar authorization model for the knowledge base.

    This model defines five resource types (``organization``, ``repository``,
    ``document``, ``section``, ``code_block``) with role-based access control
    and conditional permission rules.

    Attributes:
        model_id: Unique identifier assigned by Auth0 FGA after writing.
        schema_version: Cedar schema version.
        resource_types: List of resource type definitions.
        conditions: Optional conditional policy definitions.
    """

    model_id: Optional[str] = None
    schema_version: str = "1.1"
    resource_types: List[Dict[str, Any]] = field(default_factory=list)
    conditions: List[Dict[str, Any]] = field(default_factory=list)

    # ---- Construction helpers ------------------------------------------------

    @classmethod
    def default_model(cls) -> "AuthorizationModel":
        """Build the default senso-ai authorization model.

        Returns a complete model with all five resource types, their
        relations, and permission rules that implement the role hierarchy
        (owner > admin > editor > viewer) with organization-level
        inheritance.
        """
        model = cls()

        # -- Organization -------------------------------------------------------
        model.resource_types.append(
            {
                "type": "organization",
                "relations": {
                    "owner": {"directly_related_user_types": [{"type": "user"}]},
                    "admin": {
                        "union": [
                            {"child": ["owner"]},
                            {"directly_related_user_types": [{"type": "user"}]},
                        ]
                    },
                    "member": {
                        "union": [
                            {"child": ["admin"]},
                            {"directly_related_user_types": [{"type": "user"}]},
                        ]
                    },
                },
                "permissions": {
                    "can_read": {"union": [{"child": ["member"]}]},
                    "can_edit": {"union": [{"child": ["admin"]}]},
                    "can_delete": {"union": [{"child": ["owner"]}]},
                    "can_share": {"union": [{"child": ["admin"]}]},
                    "can_query": {"union": [{"child": ["member"]}]},
                },
            }
        )

        # -- Repository ---------------------------------------------------------
        model.resource_types.append(
            {
                "type": "repository",
                "relations": {
                    "owner": {"directly_related_user_types": [{"type": "user"}]},
                    "admin": {
                        "union": [
                            {"child": ["owner"]},
                            {"directly_related_user_types": [{"type": "user"}]},
                        ]
                    },
                    "editor": {
                        "union": [
                            {"child": ["admin"]},
                            {"directly_related_user_types": [{"type": "user"}]},
                        ]
                    },
                    "viewer": {
                        "union": [
                            {"child": ["editor"]},
                            {"directly_related_user_types": [{"type": "user"}]},
                            {"computedUserset": {"relation": "member", "object": "organization"}},
                        ]
                    },
                    "organization": {"directly_related_user_types": [{"type": "organization"}]},
                },
                "permissions": {
                    "can_read": {"union": [{"child": ["viewer"]}]},
                    "can_edit": {"union": [{"child": ["editor"]}]},
                    "can_delete": {"union": [{"child": ["owner"]}]},
                    "can_share": {"union": [{"child": ["admin"]}]},
                    "can_query": {"union": [{"child": ["viewer"]}]},
                },
            }
        )

        # -- Document -----------------------------------------------------------
        model.resource_types.append(
            {
                "type": "document",
                "relations": {
                    "owner": {"directly_related_user_types": [{"type": "user"}]},
                    "admin": {
                        "union": [
                            {"child": ["owner"]},
                            {"directly_related_user_types": [{"type": "user"}]},
                        ]
                    },
                    "editor": {
                        "union": [
                            {"child": ["admin"]},
                            {"directly_related_user_types": [{"type": "user"}]},
                        ]
                    },
                    "viewer": {
                        "union": [
                            {"child": ["editor"]},
                            {"directly_related_user_types": [{"type": "user"}]},
                        ]
                    },
                    "repository": {"directly_related_user_types": [{"type": "repository"}]},
                },
                "permissions": {
                    "can_read": {
                        "union": [
                            {"child": ["viewer"]},
                            {"computedUserset": {"relation": "viewer", "object": "repository"}},
                        ]
                    },
                    "can_edit": {
                        "union": [
                            {"child": ["editor"]},
                            {"computedUserset": {"relation": "editor", "object": "repository"}},
                        ]
                    },
                    "can_delete": {
                        "union": [
                            {"child": ["owner"]},
                            {"computedUserset": {"relation": "owner", "object": "repository"}},
                        ]
                    },
                    "can_share": {
                        "union": [
                            {"child": ["admin"]},
                            {"computedUserset": {"relation": "admin", "object": "repository"}},
                        ]
                    },
                    "can_query": {
                        "union": [
                            {"child": ["viewer"]},
                            {"computedUserset": {"relation": "viewer", "object": "repository"}},
                        ]
                    },
                },
            }
        )

        # -- Section ------------------------------------------------------------
        model.resource_types.append(
            {
                "type": "section",
                "relations": {
                    "owner": {"directly_related_user_types": [{"type": "user"}]},
                    "editor": {
                        "union": [
                            {"child": ["owner"]},
                            {"directly_related_user_types": [{"type": "user"}]},
                        ]
                    },
                    "viewer": {
                        "union": [
                            {"child": ["editor"]},
                            {"directly_related_user_types": [{"type": "user"}]},
                        ]
                    },
                    "document": {"directly_related_user_types": [{"type": "document"}]},
                },
                "permissions": {
                    "can_read": {
                        "union": [
                            {"child": ["viewer"]},
                            {"computedUserset": {"relation": "viewer", "object": "document"}},
                        ]
                    },
                    "can_edit": {
                        "union": [
                            {"child": ["editor"]},
                            {"computedUserset": {"relation": "editor", "object": "document"}},
                        ]
                    },
                    "can_delete": {
                        "union": [
                            {"child": ["owner"]},
                            {"computedUserset": {"relation": "owner", "object": "document"}},
                        ]
                    },
                },
            }
        )

        # -- Code Block ---------------------------------------------------------
        model.resource_types.append(
            {
                "type": "code_block",
                "relations": {
                    "owner": {"directly_related_user_types": [{"type": "user"}]},
                    "editor": {
                        "union": [
                            {"child": ["owner"]},
                            {"directly_related_user_types": [{"type": "user"}]},
                        ]
                    },
                    "viewer": {
                        "union": [
                            {"child": ["editor"]},
                            {"directly_related_user_types": [{"type": "user"}]},
                        ]
                    },
                    "section": {"directly_related_user_types": [{"type": "section"}]},
                },
                "permissions": {
                    "can_read": {
                        "union": [
                            {"child": ["viewer"]},
                            {"computedUserset": {"relation": "viewer", "object": "section"}},
                        ]
                    },
                    "can_edit": {
                        "union": [
                            {"child": ["editor"]},
                            {"computedUserset": {"relation": "editor", "object": "section"}},
                        ]
                    },
                },
            }
        )

        return model

    # -- Serialization ---------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the model to a plain dictionary."""
        payload: Dict[str, Any] = {
            "schema_version": self.schema_version,
            "type_definitions": self.resource_types,
        }
        if self.conditions:
            payload["conditions"] = self.conditions
        if self.model_id:
            payload["id"] = self.model_id
        return payload

    def to_json(self, indent: int = 2) -> str:
        """Serialize the model to a JSON string."""
        return json.dumps(self.to_dict(), indent=indent)
