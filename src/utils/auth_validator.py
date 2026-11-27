"""
Amazon Cognito Authentication & Authorization Helper.
Extracts and validates Cognito claims from API Gateway request context.
"""

from typing import Any, Dict, List, Optional


class AuthContext:
    """Represents authenticated caller identity from Cognito User Pool Authorizer."""

    def __init__(
        self,
        username: str,
        email: Optional[str] = None,
        groups: Optional[List[str]] = None,
        sub: Optional[str] = None,
        raw_claims: Optional[Dict[str, Any]] = None,
    ):
        self.username = username
        self.email = email or ""
        self.groups = groups or []
        self.sub = sub or ""
        self.raw_claims = raw_claims or {}

    def is_admin(self) -> bool:
        return "Admins" in self.groups or "admin" in self.groups

    def has_role(self, role: str) -> bool:
        return role in self.groups

    def to_dict(self) -> Dict[str, Any]:
        return {
            "username": self.username,
            "email": self.email,
            "groups": self.groups,
            "sub": self.sub,
        }


def extract_auth_context(event: Dict[str, Any]) -> AuthContext:
    """
    Extract Cognito User Pool authorizer claims from API Gateway proxy event.
    Falls back to anonymous / development context if auth is disabled or for local testing.
    """
    request_context = event.get("requestContext", {})
    authorizer = request_context.get("authorizer", {})
    claims = authorizer.get("claims", {})

    # If Cognito User Pool Authorizer is attached to API Gateway:
    if claims:
        username = claims.get("cognito:username") or claims.get("username") or claims.get("sub", "unknown_user")
        email = claims.get("email", "")
        sub = claims.get("sub", "")

        # Groups can be a comma-separated string or list in Cognito claims
        raw_groups = claims.get("cognito:groups", [])
        if isinstance(raw_groups, str):
            groups = [g.strip() for g in raw_groups.split(",") if g.strip()]
        elif isinstance(raw_groups, list):
            groups = raw_groups
        else:
            groups = []

        return AuthContext(
            username=username,
            email=email,
            groups=groups,
            sub=sub,
            raw_claims=claims,
        )

    # In local testing or unauthenticated dev mode:
    headers = event.get("headers") or {}
    dev_user = headers.get("X-Dev-User", headers.get("x-dev-user", "dev-operator"))
    dev_role = headers.get("X-Dev-Role", headers.get("x-dev-role", "Engineers"))
    return AuthContext(
        username=dev_user,
        email=f"{dev_user}@internal.corp",
        groups=[dev_role],
        sub="local-mock-sub",
        raw_claims={"dev_mode": True},
    )
