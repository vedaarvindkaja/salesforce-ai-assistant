"""Salesforce OAuth 2.0 Web Server Flow with PKCE.

Implements the authorization-code flow with PKCE (Proof Key for Code Exchange).
PKCE is mandatory for External Client Apps as of May 2026.

This module knows about:
- The OAuth protocol (endpoints, parameters, PKCE math)
- How to talk to Salesforce's token endpoint via httpx

This module does NOT know about:
- FastAPI (no imports from fastapi)
- Where tokens get stored (no file I/O — that's token_storage.py)
- Session management (the caller passes us the verifier when needed)

Reference: https://help.salesforce.com/s/articleView?id=sf.remoteaccess_oauth_web_server_flow.htm
"""

import base64
import hashlib
import os
import secrets
import urllib.parse
from typing import Optional

import httpx
from dotenv import load_dotenv

from app.salesforce.oauth_models import OAuthErrorResponse, OAuthTokenResponse

# Load .env once at import time
load_dotenv()


# ============================================================
# Configuration — read from environment
# ============================================================

CLIENT_ID = os.environ.get("SALESFORCE_CLIENT_ID")
CLIENT_SECRET = os.environ.get("SALESFORCE_CLIENT_SECRET")
LOGIN_URL = os.environ.get("SALESFORCE_LOGIN_URL", "https://login.salesforce.com")
REDIRECT_URI = os.environ.get("SALESFORCE_REDIRECT_URI", "http://localhost:8000/auth/callback")

# Scopes we ask the user to grant.
# 'api' = call REST APIs; 'refresh_token' = give us a refresh token; 'id' = identity URL access
SCOPES = ["api", "refresh_token", "id"]


def _require_config() -> None:
    """Fail fast if OAuth config is missing.
    
    Called at the start of every public function so misconfiguration shows up
    as a clear error, not a cryptic 400 from Salesforce.
    """
    if not CLIENT_ID:
        raise RuntimeError(
            "SALESFORCE_CLIENT_ID not set. Check backend/.env."
        )
    if not CLIENT_SECRET:
        raise RuntimeError(
            "SALESFORCE_CLIENT_SECRET not set. Check backend/.env."
        )


# ============================================================
# PKCE — Proof Key for Code Exchange
# ============================================================

def generate_pkce_pair() -> tuple[str, str]:
    """Generate a PKCE code_verifier and its corresponding code_challenge.
    
    The verifier is a random string we keep secret server-side.
    The challenge is sha256(verifier), base64url-encoded, sent in the authorize URL.
    
    When we later exchange the code for tokens, we send the verifier as proof
    that this server is the same server that initiated the flow. This prevents
    an attacker who intercepts the redirect from completing the flow themselves.
    
    Returns:
        (verifier, challenge) — store the verifier; send the challenge.
    """
    # 32 bytes of randomness, base64url-encoded ≈ 43 characters.
    # RFC 7636 requires the verifier to be 43-128 characters of [A-Z, a-z, 0-9, -._~].
    verifier = secrets.token_urlsafe(32)
    
    # SHA-256 of the verifier, base64url-encoded, with trailing '=' padding stripped.
    challenge_bytes = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(challenge_bytes).rstrip(b"=").decode("ascii")
    
    return verifier, challenge


# ============================================================
# Step 1 of the flow: build the authorize URL
# ============================================================

def build_authorize_url(code_challenge: str, state: Optional[str] = None) -> str:
    """Build the URL that the user's browser visits to authorize this app.
    
    The user clicks this URL → Salesforce login page → user logs in →
    Salesforce shows 'Allow Access?' → user clicks Allow → Salesforce redirects
    browser to REDIRECT_URI with ?code=... in the query string.
    
    Args:
        code_challenge: The PKCE challenge (from generate_pkce_pair).
        state: Optional CSRF token. We don't use it in Phase 1 because we're
               single-user local; production systems should always set this.
    
    Returns:
        Full URL to redirect the user's browser to.
    """
    _require_config()
    
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": " ".join(SCOPES),
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    if state:
        params["state"] = state
    
    return f"{LOGIN_URL}/services/oauth2/authorize?" + urllib.parse.urlencode(params)


# ============================================================
# Step 2 of the flow: exchange the code for tokens
# ============================================================

async def exchange_code_for_tokens(
    authorization_code: str,
    code_verifier: str,
) -> OAuthTokenResponse:
    """Exchange an authorization code for access + refresh tokens.
    
    Called from the /auth/callback endpoint after Salesforce redirects the
    browser back with ?code=... in the URL.
    
    Args:
        authorization_code: The 'code' query parameter from the callback URL.
        code_verifier: The PKCE verifier we generated in generate_pkce_pair.
                       Must match the challenge we sent in build_authorize_url.
    
    Returns:
        OAuthTokenResponse with access_token, refresh_token, instance_url, etc.
    
    Raises:
        RuntimeError: if Salesforce returns an error or the request fails.
    """
    _require_config()
    
    token_url = f"{LOGIN_URL}/services/oauth2/token"
    data = {
        "grant_type": "authorization_code",
        "code": authorization_code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "code_verifier": code_verifier,
    }
    
    async with httpx.AsyncClient(timeout=30.0) as http:
        response = await http.post(token_url, data=data)
    
    return _parse_token_response(response)


# ============================================================
# Refresh: get a new access token using the refresh token
# ============================================================

async def refresh_access_token(refresh_token: str) -> OAuthTokenResponse:
    """Get a new access token using a stored refresh token.
    
    Salesforce access tokens are short-lived (~2 hours). Refresh tokens are
    long-lived. We use the refresh token to get a new access token without
    making the user log in again.
    
    With Refresh Token Rotation enabled (mandatory May 2026), Salesforce
    returns a NEW refresh_token in the response. We must replace the stored
    one — the old refresh_token is now invalid.
    
    Args:
        refresh_token: The stored refresh token.
    
    Returns:
        OAuthTokenResponse with a fresh access_token and (likely) a new refresh_token.
    """
    _require_config()
    
    token_url = f"{LOGIN_URL}/services/oauth2/token"
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }
    
    async with httpx.AsyncClient(timeout=30.0) as http:
        response = await http.post(token_url, data=data)
    
    return _parse_token_response(response)


# ============================================================
# Internal: parse Salesforce's token response
# ============================================================

def _parse_token_response(response: httpx.Response) -> OAuthTokenResponse:
    """Parse a token endpoint response, raising a clear error on failure."""
    if response.status_code == 200:
        return OAuthTokenResponse.model_validate_json(response.text)
    
    # Salesforce returned an error — try to parse it as OAuthErrorResponse
    try:
        error = OAuthErrorResponse.model_validate_json(response.text)
        raise RuntimeError(
            f"Salesforce OAuth error: {error.error} — {error.error_description}"
        )
    except ValueError:
        # Response wasn't JSON or didn't match the error schema
        raise RuntimeError(
            f"Salesforce OAuth request failed: HTTP {response.status_code} — {response.text[:200]}"
        )


# ============================================================
# APEX EQUIVALENT (for comparison)
# ============================================================
#
# In Apex, you almost never write OAuth code by hand. The platform provides
# higher-level abstractions for the common cases:
#
# 1) FOR INBOUND OAUTH (other apps calling your Salesforce org):
#    Salesforce IS the OAuth provider. You configure Connected Apps / External
#    Client Apps in Setup. No code needed.
#
# 2) FOR OUTBOUND OAUTH (your Apex calling another OAuth-protected API):
#    Use Named Credentials + External Credentials. The platform handles the
#    entire token dance — authorization, token exchange, refresh, storage.
#    Your callout code just says:
#
#        HttpRequest req = new HttpRequest();
#        req.setEndpoint('callout:My_Named_Credential/services/data/v60.0/...');
#        // No auth headers needed — platform injects them
#        HttpResponse res = new Http().send(req);
#
# 3) IF YOU INSIST ON MANUAL OAUTH (rare, usually for unsupported flows):
#    You'd write something like this — but you usually shouldn't:
#
#    public class SalesforceOAuthClient {
#        private static final String CLIENT_ID = '<from Custom Setting>';
#        private static final String CLIENT_SECRET = '<from Protected Custom Metadata>';
#        private static final String REDIRECT_URI = '<your callback>';
#
#        // PKCE in Apex requires manual SHA-256 + Base64URL encoding:
#        public static String generateCodeChallenge(String verifier) {
#            Blob hash = Crypto.generateDigest('SHA-256', Blob.valueOf(verifier));
#            String b64 = EncodingUtil.base64Encode(hash);
#            // Base64URL: replace + with -, / with _, strip trailing =
#            return b64.replace('+', '-').replace('/', '_').replace('=', '');
#        }
#
#        public static TokenResponse exchangeCode(String code, String verifier) {
#            HttpRequest req = new HttpRequest();
#            req.setEndpoint('https://login.salesforce.com/services/oauth2/token');
#            req.setMethod('POST');
#            req.setHeader('Content-Type', 'application/x-www-form-urlencoded');
#            req.setBody('grant_type=authorization_code'
#                + '&code=' + EncodingUtil.urlEncode(code, 'UTF-8')
#                + '&client_id=' + CLIENT_ID
#                + '&client_secret=' + CLIENT_SECRET
#                + '&redirect_uri=' + EncodingUtil.urlEncode(REDIRECT_URI, 'UTF-8')
#                + '&code_verifier=' + verifier);
#            HttpResponse res = new Http().send(req);
#            return (TokenResponse) JSON.deserialize(res.getBody(), TokenResponse.class);
#        }
#    }
#
# Concept mapping:
# - secrets.token_urlsafe(32)        → Crypto.generateAesKey(256) + Base64URL encode
# - hashlib.sha256(...).digest()     → Crypto.generateDigest('SHA-256', Blob.valueOf(...))
# - base64.urlsafe_b64encode(...)    → EncodingUtil.base64Encode + replace +/= chars
# - httpx.AsyncClient.post()         → new Http().send(new HttpRequest())
# - os.environ.get()                 → Custom Settings or Custom Metadata Types
# - async/await                      → Apex callouts are synchronous in @RestResource;
#                                       use @future or Queueable for async
#
# Philosophical note:
# Python gives you the low-level OAuth primitives and you assemble them.
# Apex gives you a framework (Named Credentials) and hides the primitives.
# Both are valid for their contexts — Python here because we're building a
# dev tool that runs outside Salesforce; Apex's framework approach only
# makes sense when you're INSIDE Salesforce's platform.
# ============================================================