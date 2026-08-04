"""The single rich console every command in this CLI prints through."""

from rich.console import Console

console = Console()


def truncate(value: str, max_len: int) -> str:
    """Shorten ``value`` to ``max_len`` characters, ellipsis included."""
    return value if len(value) <= max_len else value[: max_len - 3] + "..."
