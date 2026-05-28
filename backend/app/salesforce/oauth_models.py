"""Pydantic models for Salesforce OAuth 2.0 token responses.

Salesforce's /services/oauth2/token endpoint returns a specific JSON
structure for the Web Server Flow. These models give us typed access.

See: https://help.salesforce.com/s/articleView?id=sf.remoteaccess_oauth_web_server_flow.htm
"""

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class OAuthTokenResponse(BaseModel):
    """Response from Salesforce's /services/oauth2/token endpoint.

    Returned for both initial authorization-code exchange AND refresh-token grants.
    Salesforce returns the same shape for both, just with different fields populated.
    """

    access_token: str
    """The bearer token used in Authorization: Bearer <token> headers."""

    refresh_token: Optional[str] = None
    """Long-lived token used to get a new access_token without re-prompting the user.
    
    Only present in the initial Web Server Flow response (not always present in
    refresh responses unless Refresh Token Rotation is enabled, which is mandatory
    as of May 2026 — so we should always get a fresh one).
    """

    instance_url: str
    """The Salesforce instance URL (e.g., https://arvindcom-dev-ed.develop.my.salesforce.com).
    
    Use this URL — not login.salesforce.com — for all subsequent API calls.
    """

    id: str
    """Identity URL — combination of org ID and user ID, useful for knowing who is auth'd."""

    token_type: str = "Bearer"
    """Always 'Bearer' for OAuth 2.0. Included in Authorization headers."""

    issued_at: str
    """Unix timestamp (as string!) when the token was issued."""

    signature: str
    """HMAC-SHA256 signature of issued_at + client_id, signed with the client_secret.
    Used to verify the response came from Salesforce. We don't validate this in Phase 1
    because we received it over HTTPS — but production systems should."""

    scope: Optional[str] = None
    """Space-separated list of granted scopes (e.g., 'api refresh_token id')."""


class OAuthErrorResponse(BaseModel):
    """Response from Salesforce when OAuth fails.

    Salesforce uses the OAuth 2.0 RFC 6749 error format.
    Common error codes: invalid_grant, invalid_client_id, invalid_request, redirect_uri_mismatch.
    """

    error: str
    """Short error code from RFC 6749."""

    error_description: str
    """Human-readable description of what went wrong."""


class StoredTokens(BaseModel):
    """Token state we persist between server restarts.

    Lives on disk in tokens.json (gitignored). When the server starts, we load this
    and check if the access_token is still valid; if expired, we use the refresh_token
    to get a new one.
    """

    access_token: str
    refresh_token: str
    instance_url: str
    issued_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    """When we received this token. Salesforce access tokens are valid for ~2 hours
    by default, but the exact lifetime isn't returned — we just refresh on first use
    after a long gap, or on 401 response."""


# ============================================================
# APEX EQUIVALENT (for comparison)
# ============================================================
#
# Apex doesn't have a single "OAuth response model" pattern because OAuth
# flows in Apex are handled by the platform via Auth.AuthProviderPluginClass
# and Named Credentials. You rarely see the raw token JSON.
#
# When you DO see it (e.g., custom OAuth integration where you can't use Named
# Credentials), you'd write an inner class on the consuming class:
#
#   public class SalesforceOAuthClient {
#       public class TokenResponse {
#           public String access_token;
#           public String refresh_token;
#           public String instance_url;
#           public String id;
#           public String token_type;
#           public String issued_at;
#           public String signature;
#           public String scope;
#       }
#
#       public class ErrorResponse {
#           public String error;
#           public String error_description;
#       }
#
#       public static TokenResponse parseToken(String jsonBody) {
#           return (TokenResponse) JSON.deserialize(jsonBody, TokenResponse.class);
#       }
#   }
#
# Concept mapping:
# - Pydantic BaseModel              → public Apex inner class
# - Optional[str] = None            → public String (Apex allows null by default)
# - Field(default_factory=...)      → constructor or @TestVisible setter
# - .model_validate_json()          → JSON.deserialize(jsonBody, ClassName.class)
# - Runtime validation on fields    → Apex has no equivalent; you validate manually
#                                      after deserialization (if (response.access_token == null)...)
#
# Note: in Apex, you typically wouldn't store tokens yourself — you'd register
# the integration as a Named Credential and let the platform manage token storage,
# refresh, and injection. Phase 1 Python code does it manually because we're
# building a local dev tool, not running inside the Salesforce platform.
# ============================================================