"""Safety layer: confirmation tokens for destructive and sensitive operations.

Pattern:
  1. Call the preview tool (or the delete/update tool without a token) to receive
     a preview dict that includes a `confirmation_token`.
  2. Review the preview.
  3. Call the delete/update tool again, passing the `confirmation_token`.
     The token is consumed on first use; expired or reused tokens are rejected.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Any

from netlicensing_mcp.client import api_key_ctx
from netlicensing_mcp.redaction import mask_token_number

TOKEN_TTL = timedelta(minutes=5)

_SUFFIX_LENGTH = 10

# token_str → (operation, target, expires_at, owner, force_cascade)
# *owner* is a keyed digest of the caller's API key, so in a shared HTTP deployment
# one tenant cannot consume or invalidate another tenant's confirmation token.
_store: dict[str, tuple[str, str, datetime, str, bool]] = {}

# Random per-process salt for the owner label. The label is only compared inside
# this process and dies with it.
_OWNER_SALT = secrets.token_bytes(16)


#: Operations whose target is a credential: for a token delete the target is the
#: token number, which for APIKEY and SHOP tokens is the key itself. Their targets
#: are masked in every message this module builds (preview ``target``, mismatch
#: error). The store keeps and compares the real target.
_SECRET_TARGET_OPS = frozenset({"delete_token"})


def _shown(operation: str, target: str) -> str:
    """Return *target* as it may be shown for *operation* (display only)."""
    return mask_token_number(target) if operation in _SECRET_TARGET_OPS else target


_SHOWN_TOKEN_CHARS = 6


def _shown_token(token: str) -> str:
    """Return the caller's ``confirm_token`` input as it may appear in an error.

    Unknown and expired tokens are arbitrary caller input (a key pasted into the
    wrong argument, say), so only the first characters are repeated.
    """
    return token[:_SHOWN_TOKEN_CHARS] + "…" if len(token) > _SHOWN_TOKEN_CHARS else token


def _owner() -> str:
    """Return an opaque label for the current caller's API key (never the key).

    Uses scrypt (a KDF, which also keeps static analysis happy about hashing a
    credential) with a deliberately low work factor: the label is never stored or
    sent anywhere, so brute-force resistance is not needed, and a small cost keeps
    repeated calls from becoming a CPU/memory lever. It runs once per issued token
    and only for a token that exists in the store when one is consumed; unknown or
    expired tokens are rejected before any hashing.
    """
    return hashlib.scrypt(api_key_ctx.get().encode(), salt=_OWNER_SALT, n=2**12, r=8, p=1).hex()


def _purge_expired() -> None:
    now = datetime.now(timezone.utc)
    for k in [k for k, entry in _store.items() if entry[2] < now]:
        del _store[k]


def issue_token(operation: str, target: str, force_cascade: bool = False) -> tuple[str, datetime]:
    """Issue a single-use confirmation token scoped to (operation, target, force_cascade).

    Earlier tokens for the same pair stay valid until they expire or are used, so
    repeated previews (or a preview after a token-less delete call) never burn a
    token the user may already hold. Each token is single-use.
    """
    _purge_expired()
    owner = _owner()

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
    _store[token] = (operation, target, expires_at, owner, force_cascade)
    return token, expires_at


def validate_and_consume(
    token: str, operation: str, target: str, force_cascade: bool = False
) -> None:
    """Validate and consume a confirmation token.

    Raises ValueError if the token is unknown, expired, issued under a different
    API key, or scoped to a different operation/target pair.  On success the token is removed (single-use).
    """
    entry = _store.get(token)
    # A token issued under a different API key is reported as unknown.
    if entry is not None and not hmac.compare_digest(entry[3], _owner()):
        entry = None
    if entry is None:
        raise ValueError(f"Invalid or already used confirmation token: {_shown_token(token)!r}")

    stored_op, stored_target, expires_at, _, stored_cascade = entry
    if datetime.now(timezone.utc) > expires_at:
        del _store[token]
        raise ValueError(f"Confirmation token {_shown_token(token)!r} has expired")

    if stored_op != operation or stored_target != target:
        # The comparison above uses the real targets; only the message masks them.
        raise ValueError(
            f"Token {token!r} is for {stored_op!r}/{_shown(stored_op, stored_target)!r}, "
            f"not {operation!r}/{_shown(operation, target)!r}"
        )

    if stored_cascade != force_cascade:
        # Not consumed: the token stays usable with the matching force_cascade value.
        issued = "a cascade" if stored_cascade else "a non-cascade"
        used = "force_cascade=true" if force_cascade else "force_cascade=false"
        raise ValueError(
            f"This token was issued for {issued} delete but was used with {used}. "
            "Request a new preview with the matching force_cascade value, or retry "
            f"with force_cascade={'true' if stored_cascade else 'false'}."
        )

    del _store[token]


def make_delete_preview(
    operation: str,
    target: str,
    affected: dict[str, Any],
    samples: dict[str, Any] | None = None,
    force_cascade: bool = False,
    blocking: dict[str, int] | None = None,
) -> dict:
    """Build a preview response for a destructive delete and issue a confirmation token.

    The token is bound to the real *target*; the returned ``target`` is masked
    for operations whose target is a credential (``delete_token``).
    """
    token, expires_at = issue_token(operation, target, force_cascade)
    preview: dict[str, Any] = {
        "operation": operation,
        "target": _shown(operation, target),
        "affected": affected,
        "samples": samples or {},
        "force_cascade": force_cascade,
        "confirmation_token": token,
        "expires_at": expires_at.isoformat(),
    }
    cascade_arg = ", force_cascade=true" if force_cascade else ""
    instructions = (
        f"To execute this deletion, call the delete tool again with confirm_token={token!r}"
        f"{cascade_arg}."
    )
    if blocking is not None:
        blocking = {k: v for k, v in blocking.items() if v}
        preview["requires_force_cascade"] = bool(blocking)
        preview["blocking_dependencies"] = blocking
        if blocking and not force_cascade:
            found = ", ".join(f"{n} {k.replace('_', ' ')}" for k, n in blocking.items())
            instructions = (
                f"This delete will fail without force_cascade: it has {found}. "
                "Request a preview with force_cascade=true to delete them too (the token "
                "is bound to that choice), or remove them first. " + instructions
            )
    preview["instructions"] = instructions
    return preview


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
