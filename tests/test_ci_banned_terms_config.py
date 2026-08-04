"""CI must hand the banned-terms gate its config — and must not silence the gate instead.

The gate refuses to run without a config (exit 2) rather than passing silently, which is the
whole point of it. That turned the `lint` job red: a fresh runner has no such file. The fix
belongs in the workflow, not in the gate, so every assertion here is about the workflow: it
writes the path the hook actually reads, it writes it before prek runs, and it never takes the
shortcut of adding the hook to prek's SKIP list.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRE_COMMIT = ROOT / ".pre-commit-config.yaml"
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
PREK_ACTION = "j178/prek-action"


def config_path_the_hook_reads() -> str:
    """The --config path the banned-terms hook is wired to, spelled as the workflow must write it."""
    entry = re.search(r"check-banned-terms\.sh --config (\S+)", PRE_COMMIT.read_text(encoding="utf-8"))
    assert entry, "the banned-terms hook no longer passes --config; re-point this test at the new wiring"
    return entry.group(1).replace("~", "$HOME", 1)


class TestLintJobProvisionsTheConfig:
    def test_workflow_writes_the_path_the_hook_reads(self):
        # Not a hardcoded "$HOME/.skills": re-pointing the hook at another path without
        # teaching CI about it must fail here, not two minutes into a red lint job.
        assert config_path_the_hook_reads() in WORKFLOW.read_text(encoding="utf-8")

    def test_the_config_is_written_before_prek_runs(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        assert workflow.index(config_path_the_hook_reads()) < workflow.index(PREK_ACTION)


class TestTheGateIsNotSilencedInstead:
    def test_banned_terms_is_not_in_preks_skip_list(self):
        skipped = re.findall(r"^\s*SKIP:\s*(.+)$", WORKFLOW.read_text(encoding="utf-8"), re.MULTILINE)
        assert not any("banned-terms" in line for line in skipped)
