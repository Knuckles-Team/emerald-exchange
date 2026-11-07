"""Wallet custody: every wallet secret resolves from a reference (CONN-EMERALD-EXCHANGE-X402-R011.1).

Config holds only secret references in the SDK grammar (``openbao://`` or
``env://``); a literal value is refused. The MCP process resolves the agent
credential and the public wallet profile; only the daemon launcher resolves
the vault password and the encrypted daemon state.
"""

from __future__ import annotations

import base64
import binascii
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from scion_sdk.credentials.references import (
    SecretReferenceError,
    parse_secret_reference,
)
from scion_sdk.credentials.resolution import resolve_secret_reference
from scion_sdk.credentials.resolver import (
    CredentialResolver,
    CredentialUnavailableError,
)

from emerald_exchange.payments.refusals import PaymentRefused

AGENT_REFS = ("agent_key_id_ref", "agent_auth_token_ref", "profile_ref")
DAEMON_REFS = ("vault_password_ref", "state_ref")


def require_reference(section: Mapping[str, Any], key: str) -> str:
    """Return ``section[key]`` if it is a well-formed secret reference."""
    value = section.get(key)
    if not isinstance(value, str) or not value.strip():
        raise PaymentRefused("PAYMENTS_WALLET_UNSET", field=key)
    try:
        parse_secret_reference(value.strip())
    except SecretReferenceError:
        raise PaymentRefused("WALLET_SECRET_REF_INVALID", field=key) from None
    return value.strip()


def _resolve(
    section: Mapping[str, Any], key: str, resolver: CredentialResolver | None
) -> str:
    reference = require_reference(section, key)
    try:
        return resolve_secret_reference(reference, resolver)
    except (CredentialUnavailableError, SecretReferenceError):
        raise PaymentRefused("WALLET_SECRET_UNAVAILABLE", field=key) from None


@dataclass(frozen=True)
class AgentCredential:
    """The agent key id, its auth token and the public wallet profile."""

    key_id: str
    auth_token: str = field(repr=False)
    profile: dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:  # never print the token
        return f"AgentCredential(key_id={self.key_id!r}, auth_token=<redacted>)"


@dataclass(frozen=True)
class DaemonMaterial:
    """The daemon unlock password and the encrypted daemon state seed."""

    vault_password: str = field(repr=False)
    state: bytes = field(repr=False)

    def __repr__(self) -> str:
        return "DaemonMaterial(<redacted>)"


def resolve_agent_credential(
    wallet: Mapping[str, Any], resolver: CredentialResolver | None = None
) -> AgentCredential:
    """Resolve ``payments.wallet``: agent key id, auth token and wallet profile."""
    key_id = _resolve(wallet, "agent_key_id_ref", resolver).strip()
    token = _resolve(wallet, "agent_auth_token_ref", resolver).strip()
    try:
        profile = json.loads(_resolve(wallet, "profile_ref", resolver))
    except json.JSONDecodeError:
        raise PaymentRefused("WALLET_SECRET_UNAVAILABLE", field="profile_ref") from None
    if not isinstance(profile, dict):
        raise PaymentRefused("WALLET_SECRET_UNAVAILABLE", field="profile_ref")
    return AgentCredential(key_id=key_id, auth_token=token, profile=profile)


def resolve_daemon_material(
    daemon: Mapping[str, Any], resolver: CredentialResolver | None = None
) -> DaemonMaterial:
    """Resolve ``payments.daemon``: the vault password and the base64 state."""
    password = _resolve(daemon, "vault_password_ref", resolver)
    try:
        state = base64.b64decode(_resolve(daemon, "state_ref", resolver), validate=True)
    except (binascii.Error, ValueError):
        raise PaymentRefused("WALLET_SECRET_UNAVAILABLE", field="state_ref") from None
    if not password.strip() or not state:
        raise PaymentRefused("WALLET_SECRET_UNAVAILABLE", field="vault_password_ref")
    return DaemonMaterial(vault_password=password.rstrip("\r\n"), state=state)
