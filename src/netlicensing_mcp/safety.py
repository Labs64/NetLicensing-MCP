"""Safety layer: confirmation tokens for destructive and sensitive operations.

Pattern:
  1. Call the preview tool (or the delete/update tool without a token) to receive
     a preview dict that includes a `confirmation_token`.
  2. Review the preview.
  3. Call the delete/update tool again, passing the `confirmation_token`.
     The token is consumed on first use; expired or reused tokens are rejected.
"""

from __future__ import annotations

import hmac
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Any

from netlicensing_mcp.client import api_key_ctx

TOKEN_TTL = timedelta(minutes=5)

_SUFFIX_LENGTH = 10

# token_str → (operation, target, expires_at, owner)
# *owner* is a keyed digest of the caller's API key, so in a shared HTTP deployment
# one tenant cannot consume or invalidate another tenant's confirmation token.
_store: dict[str, tuple[str, str, datetime, str]] = {}

# Random per-process key for the owner digest. The digest is only compared inside
# this process and dies with it, so it is a keyed MAC used as an opaque identity
# label, not a stored password hash.
_OWNER_MAC_KEY = secrets.token_bytes(32)


def _owner() -> str:
    """Return an opaque label for the current caller's API key (never the key)."""
    return hmac.new(_OWNER_MAC_KEY, api_key_ctx.get().encode(), "sha256").hexdigest()


def _purge_expired() -> None:
    now = datetime.now(timezone.utc)
    for k in [k for k, (_, _, exp, _o) in _store.items() if exp < now]:
        del _store[k]


def issue_token(operation: str, target: str) -> tuple[str, datetime]:
    """Issue a single-use confirmation token scoped to (operation, target).

    Any previously issued token for the same (operation, target) pair is
    invalidated before the new token is created.
    """
    _purge_expired()
    # Invalidate existing tokens for this (operation, target)
    owner = _owner()
    stale = [
        k
        for k, (op, tgt, _, own) in _store.items()
        if op == operation and tgt == target and hmac.compare_digest(own, owner)
    ]
    for k in stale:
        del _store[k]

    # The token deliberately does not embed the target: for a token delete the
    # target is the API key itself.
    while True:
        suffix = "".join(
            secrets.choice(string.ascii_uppercase + string.digits) for _ in range(_SUFFIX_LENGTH)
        )
        token = f"CONF-{suffix}"
        if token not in _store:
            break

    expires_at = datetime.now(timezone.utc) + TOKEN_TTL
    _store[token] = (operation, target, expires_at, owner)
    return token, expires_at


def validate_and_consume(token: str, operation: str, target: str) -> None:
    """Validate and consume a confirmation token.

    Raises ValueError if the token is unknown, expired, issued under a different
    API key, or scoped to a different operation/target pair.  On success the token is removed (single-use).
    """
    entry = _store.get(token)
    # A token issued under a different API key is reported as unknown.
    if entry is not None and not hmac.compare_digest(entry[3], _owner()):
        entry = None
    if entry is None:
        raise ValueError(f"Invalid or already used confirmation token: {token!r}")

    stored_op, stored_target, expires_at, _ = entry
    if datetime.now(timezone.utc) > expires_at:
        del _store[token]
        raise ValueError(f"Confirmation token {token!r} has expired")

    if stored_op != operation or stored_target != target:
        raise ValueError(
            f"Token {token!r} is for {stored_op!r}/{stored_target!r}, not {operation!r}/{target!r}"
        )

    del _store[token]


def make_delete_preview(
    operation: str,
    target: str,
    affected: dict[str, Any],
    samples: dict[str, Any] | None = None,
) -> dict:
    """Build a preview response for a destructive delete and issue a confirmation token."""
    token, expires_at = issue_token(operation, target)
    return {
        "operation": operation,
        "target": target,
        "affected": affected,
        "samples": samples or {},
        "confirmation_token": token,
        "expires_at": expires_at.isoformat(),
        "instructions": (
            f"To execute this deletion, call the delete tool again with confirm_token={token!r}"
        ),
    }


def make_update_preview(
    operation: str,
    target: str,
    diff: list[dict[str, Any]],
) -> dict:
    """Build a preview response for a sensitive-field update and issue a token."""
    token, expires_at = issue_token(operation, target)
    return {
        "operation": operation,
        "target": target,
        "changes": diff,
        "confirmation_token": token,
        "expires_at": expires_at.isoformat(),
        "instructions": (
            f"To execute this update, call the update tool again with confirm_token={token!r}"
        ),
    }
