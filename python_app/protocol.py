"""Shared command validation for the Python and ESP32 protocol."""
from config import VALID_COMMANDS

MAX_COMMAND_LENGTH = 32


def normalize_command(raw: str) -> str:
    """Normalize a line received from a UI or serial stream."""
    return " ".join(raw.strip().upper().split())


def is_valid_command(command: str) -> bool:
    """Return whether a normalized command is in the allow-list."""
    return normalize_command(command) in VALID_COMMANDS


def encode_command(command: str) -> bytes:
    """Validate and encode one newline-terminated command."""
    normalized = normalize_command(command)
    if len(normalized) > MAX_COMMAND_LENGTH or normalized not in VALID_COMMANDS:
        raise ValueError(f"Unsupported command: {command!r}")
    return f"{normalized}\n".encode("ascii")
