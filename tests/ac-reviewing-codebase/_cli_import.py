"""Import the ac-reviewing-codebase CLI modules the way the CLI itself does.

The skill ships as `uv run --script` files, not an installed package: `cli.py`
puts its own directory first on `sys.path` so its sibling modules resolve. The
tests reproduce exactly that, and load `cli.py` itself from its file path under
a distinct module name, because two other skills in this repo also ship a
`scripts/cli.py`.
"""

import importlib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "ac-reviewing-codebase" / "scripts"
CLI_PATH = SCRIPTS_DIR / "cli.py"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def load(name: str) -> ModuleType:
    """Import a sibling module of `cli.py` by name."""
    return importlib.import_module(name)


def load_cli() -> ModuleType:
    """Load `cli.py` from its path, cached so every test module shares one app."""
    existing = sys.modules.get("reviewing_codebase_cli")
    if existing is not None:
        return existing
    spec = importlib.util.spec_from_file_location("reviewing_codebase_cli", CLI_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["reviewing_codebase_cli"] = module
    spec.loader.exec_module(module)
    return module
