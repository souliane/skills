"""Import the ac-django hooks package for the meta-tests.

The package lives under the hyphenated skill dir ``ac-django/``; putting that
dir on ``sys.path`` makes ``hooks`` importable as a normal package — the same
mechanism ``ac-django/hooks/cli.py`` uses when prek runs it.
"""

import sys
from pathlib import Path

_SKILL_DIR = Path(__file__).resolve().parents[2] / "ac-django"
if str(_SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(_SKILL_DIR))

from hooks import checkers, cli, ratchet  # noqa: E402
from hooks.ratchet import Violation  # noqa: E402

__all__ = ["Violation", "checkers", "cli", "ratchet"]
