"""A documented invocation has to be one that actually runs.

Docs in this repo tell the reader to execute a script directly (`./path/to.py`).
That only works if the file is executable AND carries the uv shebang plus the
PEP 723 inline metadata that installs its dependencies — otherwise the reader
gets "permission denied" or an ImportError for a dependency nobody installed.
"""

import re
import shutil
import stat
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
UV_SHEBANG = "#!/usr/bin/env -S uv run --script"
INLINE_METADATA = "# /// script"

_INVOCATION_RE = re.compile(r"(?<![\w/])\./([A-Za-z0-9_./-]+\.py)")


def _documented_scripts() -> dict[Path, list[str]]:
    """``{script path: docs that tell the reader to run it}``."""
    git = shutil.which("git")
    assert git is not None
    tracked = subprocess.run(
        [git, "-C", str(REPO_ROOT), "ls-files", "*.md"],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    ).stdout.split()
    found: dict[Path, list[str]] = {}
    for doc in tracked:
        text = (REPO_ROOT / doc).read_text(encoding="utf-8")
        for match in _INVOCATION_RE.findall(text):
            found.setdefault(REPO_ROOT / match, []).append(doc)
    return found


DOCUMENTED = _documented_scripts()


class TestDocumentedInvocationsRun:
    def test_the_docs_name_at_least_one_runnable_script(self) -> None:
        assert DOCUMENTED, "the scan found nothing — the invocation pattern drifted"

    def test_every_documented_script_exists(self) -> None:
        missing = {str(p.relative_to(REPO_ROOT)): docs for p, docs in DOCUMENTED.items() if not p.exists()}
        assert missing == {}

    def test_every_documented_script_is_executable(self) -> None:
        not_executable = [
            str(p.relative_to(REPO_ROOT)) for p in DOCUMENTED if p.exists() and not p.stat().st_mode & stat.S_IXUSR
        ]
        assert not_executable == []

    def test_every_documented_script_carries_the_uv_header(self) -> None:
        without_header = [
            str(p.relative_to(REPO_ROOT))
            for p in DOCUMENTED
            if p.exists()
            and not (
                p.read_text(encoding="utf-8").startswith(UV_SHEBANG)
                and INLINE_METADATA in p.read_text(encoding="utf-8")
            )
        ]
        assert without_header == []
