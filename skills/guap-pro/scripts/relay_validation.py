"""Validation shared by the direct and SSH-backed relay entry points."""

from __future__ import annotations

from urllib.parse import SplitResult, urlsplit


def _reject_controls(value: str, label: str) -> None:
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in value):
        raise ValueError(f"{label} must not contain control characters")


def validate_public_url(value: str) -> str:
    """Require an HTTPS authority with an optional path and no secrets."""
    if not isinstance(value, str) or not value:
        raise ValueError("The relay public URL must not be empty")
    _reject_controls(value, "The relay public URL")
    if "?" in value:
        raise ValueError("The relay public URL must not contain a query")
    if "#" in value:
        raise ValueError("The relay public URL must not contain a fragment")
    try:
        parsed: SplitResult = urlsplit(value)
        hostname = parsed.hostname
        authority = parsed.netloc.rsplit("@", 1)[-1]
        if authority.endswith(":"):
            raise ValueError("The relay public URL contains an empty port")
        # Accessing .port is required: urlsplit defers malformed-port errors.
        parsed.port
    except ValueError as exc:
        raise ValueError("The relay public URL contains an invalid host or port") from exc
    if parsed.scheme != "https" or not hostname:
        raise ValueError("The relay public URL must use HTTPS and include a host")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("The relay public URL must not contain credentials")
    return value.rstrip("/")


def validate_port(value: int, label: str) -> int:
    """Validate a TCP port before it is interpolated into an argv element."""
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 65535:
        raise ValueError(f"{label} must be an integer from 1 to 65535")
    return value


def validate_ssh_part(value: str, label: str) -> str:
    """Reject SSH endpoint values that can alter argv or destination syntax."""
    if not isinstance(value, str) or not value:
        raise ValueError(f"SSH {label} must not be empty")
    _reject_controls(value, f"SSH {label}")
    if any(character.isspace() for character in value):
        raise ValueError(f"SSH {label} must not contain whitespace")
    if value.startswith("-"):
        raise ValueError(f"SSH {label} must not start with '-'")
    if any(character in value for character in ("@", "/")):
        raise ValueError(f"SSH {label} contains ambiguous destination syntax")
    return value
