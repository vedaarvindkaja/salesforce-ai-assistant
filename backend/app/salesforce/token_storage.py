"""Persistence layer for OAuth tokens.

Tokens live in tokens.json (gitignored). When the server starts, we load this
to see if we have a valid session; if not, the user runs through /auth/login.

This is the deliberately-dumb Phase 1 implementation:
- Single-user (no token namespacing by user/org)
- File-based (no DB)
- No encryption at rest (file is gitignored; OS file permissions are the only barrier)

Phase 2 multi-tenant will replace this with database storage keyed by user.
Week 7's SQLite caching layer may also subsume this — we'll decide when we get there.
"""

import json
from pathlib import Path
from typing import Optional

from app.salesforce.oauth_models import StoredTokens

# Token file lives in backend/ alongside .env
# Resolved relative to this file's location so it works regardless of CWD
_TOKEN_FILE = Path(__file__).resolve().parent.parent.parent / "tokens.json"


def save_tokens(tokens: StoredTokens) -> None:
    """Write tokens to disk, replacing any existing file."""
    _TOKEN_FILE.write_text(tokens.model_dump_json(indent=2))


def load_tokens() -> Optional[StoredTokens]:
    """Read tokens from disk. Returns None if the file doesn't exist."""
    if not _TOKEN_FILE.exists():
        return None
    return StoredTokens.model_validate_json(_TOKEN_FILE.read_text())


def clear_tokens() -> None:
    """Delete the token file. Used for testing and 'logout'."""
    if _TOKEN_FILE.exists():
        _TOKEN_FILE.unlink()


def tokens_file_path() -> Path:
    """Return the path where tokens are stored. Useful for diagnostics."""
    return _TOKEN_FILE


# No direct Apex equivalent — file I/O for local dev; Apex would use a custom
# object, Custom Settings, or Custom Metadata Types, but those are platform-side
# concerns that don't translate to this kind of dev-tool persistence.