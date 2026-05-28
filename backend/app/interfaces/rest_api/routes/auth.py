"""OAuth authentication endpoints.

Two endpoints implement the OAuth 2.0 Web Server Flow with PKCE:

GET /auth/login    → generates PKCE pair, stores verifier, redirects user to Salesforce
GET /auth/callback → receives authorization code, exchanges it for tokens, saves them

The flow is stateful across the two requests: we need to remember the PKCE
verifier we generated in /auth/login when /auth/callback arrives.

For Phase 1 (local single-user), we store pending flows in a module-level dict
keyed by the OAuth `state` parameter. This is intentionally not session-based
because we don't have multi-user concerns yet.

For Phase 2 multi-tenant, this becomes a server-side session store
(signed cookie + Redis or similar). Flagged as ADR-worthy.
"""

import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse

from app.salesforce import auth as oauth
from app.salesforce.oauth_models import StoredTokens
from app.salesforce.token_storage import load_tokens, save_tokens

router = APIRouter(prefix="/auth", tags=["auth"])


# ============================================================
# Pending OAuth flows — verifier kept between /login and /callback
# ============================================================
# state → code_verifier
# Cleared after callback completes (or should be — see TODO in callback)
_pending_flows: dict[str, str] = {}


# ============================================================
# GET /auth/login
# ============================================================

@router.get("/login")
async def login() -> RedirectResponse:
    """Start the OAuth flow.

    Generates a PKCE pair and a random state token, remembers them server-side,
    and redirects the user's browser to Salesforce's authorize endpoint.
    """
    verifier, challenge = oauth.generate_pkce_pair()
    state = secrets.token_urlsafe(16)

    # Remember the verifier so /callback can retrieve it
    _pending_flows[state] = verifier

    authorize_url = oauth.build_authorize_url(challenge, state=state)
    return RedirectResponse(url=authorize_url)


# ============================================================
# GET /auth/callback
# ============================================================

@router.get("/callback")
async def callback(
    code: str | None = Query(None, description="Authorization code from Salesforce"),
    state: str | None = Query(None, description="The state token we sent in /login"),
    error: str | None = Query(None, description="OAuth error code (if any)"),
    error_description: str | None = Query(None, description="Error details"),
) -> dict:
    """Handle the OAuth callback from Salesforce.

    Salesforce redirects the browser here after the user authorizes (or denies)
    the request. Either:
    - We get ?code=...&state=... → exchange code for tokens, save them
    - We get ?error=...&error_description=... → user denied or something failed
    """
    if error:
        raise HTTPException(
            status_code=400,
            detail=f"OAuth error from Salesforce: {error} — {error_description}",
        )

    if not code or not state:
        raise HTTPException(
            status_code=400,
            detail="Missing code or state parameter — invalid callback request.",
        )

    # Retrieve and remove the verifier (single-use)
    verifier = _pending_flows.pop(state, None)
    if not verifier:
        raise HTTPException(
            status_code=400,
            detail="Unknown state token. Either expired, already used, "
                   "or the server was restarted mid-flow.",
        )

    # Exchange the code for tokens
    token_response = await oauth.exchange_code_for_tokens(
        authorization_code=code,
        code_verifier=verifier,
    )

    # Persist tokens for future API calls
    if not token_response.refresh_token:
        # This should not happen with our requested scopes, but be defensive
        raise HTTPException(
            status_code=500,
            detail="Salesforce did not return a refresh_token. "
                   "Check the Connected App's enabled scopes — must include refresh_token.",
        )

    stored = StoredTokens(
        access_token=token_response.access_token,
        refresh_token=token_response.refresh_token,
        instance_url=token_response.instance_url,
        issued_at=datetime.now(timezone.utc),
    )
    save_tokens(stored)

    return {
        "status": "authenticated",
        "instance_url": token_response.instance_url,
        "scope": token_response.scope,
        "message": "Authentication successful. You can now use the API.",
    }


# ============================================================
# GET /auth/status — diagnostic
# ============================================================

@router.get("/status")
async def status() -> dict:
    """Report current authentication state. Useful for debugging."""
    tokens = load_tokens()
    if not tokens:
        return {"authenticated": False, "message": "No tokens stored. Visit /auth/login."}

    return {
        "authenticated": True,
        "instance_url": tokens.instance_url,
        "issued_at": tokens.issued_at.isoformat(),
        # Don't return the actual tokens — even on localhost, don't form the habit
    }


# ============================================================
# APEX EQUIVALENT (for comparison)
# ============================================================
#
# In Apex/Salesforce, the equivalent endpoints would be implemented as a
# @RestResource class — but Salesforce is usually the OAuth PROVIDER, not the
# consumer. So the actual analog depends on what side of the OAuth flow you're on.
#
# IF YOU WERE BUILDING THIS IN APEX (Apex calling another OAuth-protected API):
#
#    @RestResource(urlMapping='/auth/*')
#    global with sharing class AuthEndpoints {
#
#        @HttpGet  // Maps to GET /auth/login OR /auth/callback based on URL
#        global static void handle() {
#            String path = RestContext.request.requestURI;
#            if (path.endsWith('/login')) {
#                handleLogin();
#            } else if (path.endsWith('/callback')) {
#                handleCallback();
#            }
#        }
#
#        private static void handleLogin() {
#            String verifier = OAuthHelper.generateVerifier();
#            String challenge = OAuthHelper.generateChallenge(verifier);
#            String state = OAuthHelper.generateState();
#
#            // Persist verifier for the callback — can't use in-memory dict because
#            // each Apex transaction is stateless. Need DB-backed storage:
#            insert new OAuth_Flow__c(State__c = state, Verifier__c = verifier);
#
#            RestContext.response.statusCode = 302;
#            RestContext.response.headers.put('Location',
#                OAuthHelper.buildAuthorizeUrl(challenge, state));
#        }
#
#        private static void handleCallback() {
#            String code = RestContext.request.params.get('code');
#            String state = RestContext.request.params.get('state');
#
#            OAuth_Flow__c flow = [SELECT Verifier__c FROM OAuth_Flow__c
#                                  WHERE State__c = :state LIMIT 1];
#            delete flow;  // single-use
#
#            TokenResponse tokens = OAuthHelper.exchangeCode(code, flow.Verifier__c);
#            // Store tokens — typically in a custom object or Named Credential
#            saveTokens(tokens);
#        }
#    }
#
# Concept mapping:
# - APIRouter(prefix="/auth")            → @RestResource(urlMapping='/auth/*')
# - @router.get("/login")                → @HttpGet on a method (or routed via URI parsing)
# - Query(None, description=...)         → RestContext.request.params.get('name')
# - RedirectResponse(url=...)            → RestContext.response.statusCode = 302
#                                          + headers.put('Location', url)
# - HTTPException(status_code=400, ...)  → RestContext.response.statusCode = 400
#                                          + RestContext.response.responseBody = ...
# - Module-level _pending_flows dict     → Custom object (Apex transactions are stateless,
#                                          no in-memory persistence between requests)
# - secrets.token_urlsafe(16)            → Crypto.generateAesKey(128) + Base64 encode
# - datetime.now(timezone.utc)           → Datetime.now() (always UTC under the hood)
#
# Key philosophical difference:
# - Python keeps the PKCE verifier in process memory between two HTTP calls.
# - Apex CANNOT do this — every @RestResource invocation is a fresh transaction
#   with no shared state. You must persist the verifier to the database between
#   calls, which adds a Custom Object and DML overhead.
#
# Apex's statelessness is a feature for scalability (no session affinity needed
# across the platform's load-balanced servers) but a constraint when implementing
# multi-step protocols. Python's process-affinity model is the opposite tradeoff.
# ============================================================