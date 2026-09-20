"""
Core Auth0 FGA authorization engine.

Provides the :class:`FGAClient` class for interacting with the Auth0 FGA
API using ``urllib.request`` (zero external dependencies).  Supports
checking, granting, revoking, and enumerating access for knowledge-base
resources governed by Cedar authorization models.

Environment variables:
    AUTH0_FGA_API_URL   -- Base URL of the Auth0 FGA API (default ``https://api.us1.fga.dev``)
    AUTH0_FGA_API_TOKEN -- Bearer token for API authentication
    AUTH0_FGA_STORE_ID   -- FGA store identifier
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Iterable, List, Optional, Tuple

from auth0_fga.models import (
    AccessDecision,
    AuthorizationModel,
    DocumentPolicy,
    Resource,
    ResourceType,
    Role,
)

from cubiczan_resilience import RetriesExhausted, resilient

logger = logging.getLogger(__name__)

_DEFAULT_API_URL = "https://api.us1.fga.dev"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class FGAError(Exception):
    """Base exception for all FGA client errors."""


class FGAAuthenticationError(FGAError):
    """Raised when the API token is missing or invalid."""


class FGAAuthorizationDenied(FGAError):
    """Raised when the caller is not authorized for an operation."""


class FGANotFoundError(FGAError):
    """Raised when a resource or store is not found."""


class FGARateLimitedError(FGAError):
    """Raised when the API rate limit has been exceeded."""


class FGATransientError(FGAError):
    """Raised for transient failures that are safe to retry.

    Covers network errors (``URLError``), HTTP 429 (rate limited) and
    HTTP 5xx (server) responses.  The :func:`resilient` decorator on
    :meth:`FGAClient._request` retries these with exponential backoff.
    """


class FGAUnavailableError(FGAError):
    """Raised when FGA is unreachable after retries are exhausted.

    This is distinct from a clean *no access* decision: it signals that
    the authorization service itself could not be consulted, letting
    callers tell "the user has no resources" apart from "FGA is down"
    while still failing closed (treating the user as having no access).
    """


# ---------------------------------------------------------------------------
# HTTP helpers (urllib-based)
# ---------------------------------------------------------------------------

def _build_request(
    url: str,
    method: str = "GET",
    body: Optional[Dict[str, Any]] = None,
    token: Optional[str] = None,
) -> urllib.request.Request:
    """Construct an :class:`urllib.request.Request` with JSON headers."""
    headers: Dict[str, str] = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    data: Optional[bytes] = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    return req


def _parse_response(resp: urllib.request.Request, raw: bytes) -> Dict[str, Any]:
    """Parse a JSON API response, raising on HTTP errors."""
    status = resp.status  # type: ignore[attr-defined]
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        payload = {"raw": raw.decode("utf-8", errors="replace")}

    if status >= 400:
        msg = payload.get("message", payload.get("error", "Unknown FGA API error"))
        code = payload.get("code", "unknown")
        if status == 401 or status == 403:
            raise FGAAuthenticationError(f"[{code}] {msg}")
        if status == 404:
            raise FGANotFoundError(f"[{code}] {msg}")
        if status == 429:
            # Transient: rate-limited requests are safe to retry with backoff.
            raise FGATransientError(f"[{code}] {msg} (HTTP 429)")
        if status >= 500:
            # Transient: server errors are safe to retry with backoff.
            raise FGATransientError(f"[{code}] {msg} (HTTP {status})")
        raise FGAError(f"[{code}] {msg} (HTTP {status})")

    return payload


# ---------------------------------------------------------------------------
# FGAClient
# ---------------------------------------------------------------------------

class FGAClient:
    """Client for Auth0 Fine-Grained Authorization (FGA).

    Communicates with the Auth0 FGA REST API using only the Python
    standard library.  All mutating operations are idempotent when
    possible (``write`` tuples can be re-sent safely).

    Parameters:
        api_url: Base URL of the FGA API.  Falls back to ``AUTH0_FGA_API_URL``
                 or the default ``https://api.us1.fga.dev``.
        api_token: Bearer token.  Falls back to ``AUTH0_FGA_API_TOKEN``.
        store_id: FGA store identifier.  Falls back to ``AUTH0_FGA_STORE_ID``.
        timeout: HTTP request timeout in seconds.

    Example::

        fga = FGAClient()
        fga.assign_role("user:alice", "viewer", "repo:computer-vision")
        decision = fga.check_access("user:alice", "can_read", "repository:computer-vision")
        assert decision.allowed
    """

    def __init__(
        self,
        api_url: Optional[str] = None,
        api_token: Optional[str] = None,
        store_id: Optional[str] = None,
        timeout: int = 30,
    ) -> None:
        self.api_url = (api_url or os.environ.get("AUTH0_FGA_API_URL") or _DEFAULT_API_URL).rstrip("/")
        self.api_token = api_token or os.environ.get("AUTH0_FGA_API_TOKEN", "")
        self.store_id = store_id or os.environ.get("AUTH0_FGA_STORE_ID", "")
        self.timeout = timeout

        if not self.api_token:
            logger.warning("AUTH0_FGA_API_TOKEN is not set — most API calls will fail.")
        if not self.store_id:
            logger.warning("AUTH0_FGA_STORE_ID is not set — store-scoped calls will fail.")

    # ---- Internal helpers ----------------------------------------------------

    def _url(self, path: str) -> str:
        """Build a fully-qualified API URL."""
        return f"{self.api_url}{path}"

    def _emit_unavailable_alert(
        self,
        operation: str,
        user_id: str,
        exc: BaseException,
    ) -> None:
        """Emit a metric/alert when FGA is unavailable after retries.

        Logged at CRITICAL with a stable, parseable prefix
        (``FGA_UNAVAILABLE``) so log-based metrics / alerting can fire on
        the authorization service being down (distinct from clean access
        denials).
        """
        logger.critical(
            "FGA_UNAVAILABLE operation=%s user=%s error=%r",
            operation,
            user_id,
            exc,
        )

    def _request(
        self,
        method: str,
        path: str,
        body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute an HTTP request and return the parsed JSON body.

        Transient failures (network errors, HTTP 429, HTTP 5xx) are
        retried up to 3 attempts with exponential backoff + jitter via
        :func:`resilient`.  Once retries are exhausted the underlying
        :class:`FGATransientError` is re-raised so callers' existing
        ``except FGAError`` handling continues to apply.
        """
        try:
            return self._request_with_retry(method, path, body)
        except RetriesExhausted as exc:
            # Re-raise the last transient error as an FGAError subclass so
            # callers that catch FGAError keep their fail-closed behavior.
            last = exc.last_exc
            if isinstance(last, FGAError):
                raise last from exc
            raise FGATransientError(str(exc)) from exc

    @resilient(timeout=30, max_attempts=3, retryable_exceptions=(FGATransientError,))
    def _request_with_retry(
        self,
        method: str,
        path: str,
        body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute one HTTP attempt; retried by :func:`resilient`."""
        url = self._url(path)
        req = _build_request(url, method, body, token=self.api_token)
        logger.debug("FGA request: %s %s", method, url)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
                result = _parse_response(resp, raw)  # type: ignore[arg-type]
                return result
        except urllib.error.URLError as exc:
            # Network-level failures are transient — let resilient retry them.
            raise FGATransientError(f"Network error calling {url}: {exc}") from exc

    # ---- Authorization model management --------------------------------------

    def write_authorization_model(
        self,
        model: AuthorizationModel,
    ) -> str:
        """Deploy (write) a Cedar authorization model to FGA.

        Args:
            model: The :class:`AuthorizationModel` to deploy.

        Returns:
            The model ID assigned by Auth0 FGA.

        Raises:
            FGAError: If the API request fails.
        """
        body = {
            "schema_version": model.schema_version,
            "type_definitions": model.resource_types,
        }
        if model.conditions:
            body["conditions"] = model.conditions

        result = self._request("POST", "/stores/{store_id}/authorization-models".format(store_id=self.store_id), body)
        model_id = result.get("authorization_model_id", "")
        model.model_id = model_id
        logger.info("Deployed authorization model %s", model_id)
        return model_id

    def read_authorization_model(self, model_id: str) -> Dict[str, Any]:
        """Read an existing authorization model by its ID."""
        return self._request(
            "GET",
            "/stores/{store_id}/authorization-models/{model_id}".format(
                store_id=self.store_id, model_id=model_id,
            ),
        )

    # ---- Tuple writes (create_policy, assign_role, revoke_role) --------------

    def _write_tuples(
        self,
        writes: List[Dict[str, str]],
        deletes: Optional[List[Dict[str, str]]] = None,
    ) -> None:
        """Low-level tuple write.  Used by all policy mutation methods."""
        body: Dict[str, Any] = {"writes": writes}
        if deletes:
            body["deletes"] = deletes

        self._request("POST", "/stores/{store_id}/write".format(store_id=self.store_id), body)

    def create_policy(
        self,
        resource_type: str,
        resource_id: str,
        relations: Dict[str, List[str]],
    ) -> None:
        """Create an authorization policy by writing relationship tuples.

        Args:
            resource_type: FGA resource type (e.g. ``"repository"``, ``"document"``).
            resource_id: Unique resource identifier.
            relations: Mapping of relation names to lists of user IDs.

        Example::

            fga.create_policy(
                "document",
                "doc:annual-report",
                {"viewer": ["user:alice", "user:bob"], "editor": ["user:carol"]},
            )
        """
        writes: List[Dict[str, str]] = []
        for relation, users in relations.items():
            for user in users:
                writes.append({
                    "user": user,
                    "relation": relation,
                    "object": f"{resource_type}:{resource_id}",
                })

        if writes:
            self._write_tuples(writes)
            logger.info(
                "Created policy on %s:%s with %d tuple(s)",
                resource_type,
                resource_id,
                len(writes),
            )

    def create_policy_from_document_policy(self, policy: DocumentPolicy) -> None:
        """Create an authorization policy from a :class:`DocumentPolicy`."""
        self.create_policy(policy.resource_type, policy.resource_id, policy.to_relations())

    def assign_role(
        self,
        user_id: str,
        role: str,
        resource_id: str,
    ) -> None:
        """Assign a role (relation) to a user on a resource.

        Args:
            user_id: Auth0 user identifier (e.g. ``"user:alice"``).
            role: Relation name (``"owner"``, ``"admin"``, ``"editor"``, ``"viewer"``).
            resource_id: FGA object string (e.g. ``"repository:computer-vision"``).
        """
        self._write_tuples([
            {
                "user": user_id,
                "relation": role,
                "object": resource_id,
            }
        ])
        logger.info("Assigned role %s to %s on %s", role, user_id, resource_id)

    def revoke_role(
        self,
        user_id: str,
        role: str,
        resource_id: str,
    ) -> None:
        """Revoke a role (relation) from a user on a resource.

        This removes the specific relationship tuple, effectively revoking
        the role.
        """
        self._write_tuples(
            writes=[],
            deletes=[
                {
                    "user": user_id,
                    "relation": role,
                    "object": resource_id,
                }
            ],
        )
        logger.info("Revoked role %s from %s on %s", role, user_id, resource_id)

    # ---- Access checks -------------------------------------------------------

    def check_access(
        self,
        user_id: str,
        relation: str,
        resource_id: str,
    ) -> AccessDecision:
        """Check whether *user_id* has *relation* on *resource_id*.

        Args:
            user_id: Auth0 user identifier.
            relation: The relation or permission to check (e.g. ``"can_read"``).
            resource_id: FGA object string.

        Returns:
            An :class:`AccessDecision` with ``allowed`` set to ``True`` or ``False``.
        """
        try:
            body = {
                "tuple_key": {
                    "user": user_id,
                    "relation": relation,
                    "object": resource_id,
                }
            }
            result = self._request(
                "POST",
                "/stores/{store_id}/check".format(store_id=self.store_id),
                body,
            )
            allowed: bool = result.get("allowed", False)
            reason = f"User {user_id} {'has' if allowed else 'does not have'} "
            reason += f"{relation} on {resource_id}"
            decision = AccessDecision(
                allowed=allowed,
                resource_id=resource_id,
                relation=relation,
                reason=reason,
            )
            logger.debug("Access decision: %s", reason)
            return decision
        except FGAAuthenticationError:
            # Deny by default if the service is misconfigured.
            logger.error("FGA authentication failed — denying access by default.")
            return AccessDecision(
                allowed=False,
                resource_id=resource_id,
                relation=relation,
                reason="FGA service authentication failed; access denied by default",
            )
        except FGAError as exc:
            logger.error("FGA check_access error: %s", exc)
            return AccessDecision(
                allowed=False,
                resource_id=resource_id,
                relation=relation,
                reason=f"FGA service error: {exc}",
            )

    def batch_check_access(
        self,
        user_id: str,
        items: List[Tuple[str, str]],
    ) -> List[AccessDecision]:
        """Check access for multiple (relation, resource_id) pairs at once.

        Args:
            user_id: Auth0 user identifier.
            items: List of ``(relation, resource_id)`` tuples.

        Returns:
            A list of :class:`AccessDecision` objects, one per item.
        """
        if not items:
            return []

        # The FGA ``/check`` endpoint evaluates exactly one ``tuple_key`` per
        # request — it has no ``tuple_keys`` batch form, so the previous
        # single-call implementation silently returned bogus decisions.
        # Issue one correct ``/check`` per item and reuse :meth:`check_access`,
        # which already fails closed (deny) on auth and service errors.
        return [
            self.check_access(user_id, relation, resource_id)
            for relation, resource_id in items
        ]

    # ---- Listing / enumeration -----------------------------------------------

    def list_resources(
        self,
        user_id: str,
        relation: str,
        resource_type: Optional[str] = None,
    ) -> List[str]:
        """List all resource IDs that *user_id* has *relation* on.

        Uses the FGA ``list-objects`` endpoint.

        Args:
            user_id: Auth0 user identifier.
            relation: The relation or permission to check.
            resource_type: Optional resource type filter (e.g. ``"repository"``).

        Returns:
            A list of FGA object strings the user can access.
        """
        body: Dict[str, Any] = {
            "user": user_id,
            "relation": relation,
        }
        if resource_type:
            body["type"] = resource_type

        try:
            result = self._request(
                "POST",
                "/stores/{store_id}/list-objects".format(store_id=self.store_id),
                body,
            )
            objects: List[str] = result.get("objects", [])
            logger.debug(
                "User %s has %s on %d resource(s)",
                user_id,
                relation,
                len(objects),
            )
            return objects
        except FGATransientError as exc:
            # FGA was unreachable even after retries.  We still fail closed
            # (callers should treat the allowlist as empty), but raise a
            # structured error + alert so the caller can distinguish
            # "user has no access" from "authorization service is down".
            logger.error("FGA list_resources unavailable after retries: %s", exc)
            self._emit_unavailable_alert("list_resources", user_id, exc)
            raise FGAUnavailableError(
                "FGA list-objects unavailable after retries; "
                "failing closed with an empty allowlist"
            ) from exc
        except FGAError as exc:
            # Non-transient (e.g. auth/not-found): genuinely no access /
            # misconfiguration — fail closed with an empty allowlist.
            logger.error("FGA list_resources error: %s", exc)
            return []

    def list_user_relations(
        self,
        user_id: str,
        resource_id: str,
    ) -> List[str]:
        """List all relations (roles) that *user_id* has on *resource_id*.

        Uses the ``read`` endpoint to inspect the relationship tuples for
        a specific object.

        Args:
            user_id: Auth0 user identifier.
            resource_id: FGA object string.

        Returns:
            A list of relation names (e.g. ``["viewer", "editor"]``).
        """
        body = {
            "tuple_key": {
                "user": user_id,
                "relation": "",
                "object": resource_id,
            },
            "page_size": 100,
        }

        try:
            result = self._request(
                "POST",
                "/stores/{store_id}/read".format(store_id=self.store_id),
                body,
            )
            relations: List[str] = []
            for t in result.get("tuples", []):
                key = t.get("key", {})
                if key.get("user") == user_id and key.get("object") == resource_id:
                    rel = key.get("relation", "")
                    if rel and rel not in relations:
                        relations.append(rel)
            return relations
        except FGAError as exc:
            logger.error("FGA list_user_relations error: %s", exc)
            return []

    # ---- Store management (convenience) --------------------------------------

    def health_check(self) -> bool:
        """Return ``True`` if the FGA API is reachable and authenticated."""
        try:
            self._request("GET", "/stores")
            return True
        except FGAError:
            return False
