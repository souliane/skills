"""Reading ``~/.ac-reviewing-codebase`` and judging whether it still describes reality."""

import re
from pathlib import Path

import typer
from ui import console

CONFIG_PATH = Path("~/.ac-reviewing-codebase").expanduser()

CONFIG_FILES: dict[str, str] = {
    "~/.ac-reviewing-codebase": (
        "Codebase review config (shell). WORKSPACE_DIR, MAINTAINED_SKILLS, MANAGED_REPOS, BOILERPLATE_MAP."
    ),
}


def parse_shell_config(path: Path) -> dict[str, str]:
    """Parse simple KEY=VALUE pairs from a shell-sourceable config file."""
    result: dict[str, str] = {}
    if not path.exists():
        return result
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def expand(value: str) -> str:
    """Expand a leading ``~`` (or ``$HOME``) to the home directory.

    Only the leading path component is expanded; a ``~`` elsewhere in the value
    is a literal character (e.g. a backup-file suffix like ``foo~``), not a home
    reference, so it is left untouched.
    """
    home = str(Path.home())
    expanded = value.replace("$HOME", home)
    if expanded.startswith("~"):
        expanded = home + expanded[1:]
    return expanded


def load_config() -> dict[str, str]:
    if not CONFIG_PATH.exists():
        console.print(f"[red]Config not found:[/red] {CONFIG_PATH}")
        console.print("Create it with MAINTAINED_SKILLS and MANAGED_REPOS. See SKILL.md.")
        raise typer.Exit(1)
    return parse_shell_config(CONFIG_PATH)


def get_workspace_dir() -> Path:
    """Read ``WORKSPACE_DIR`` from ~/.ac-reviewing-codebase, defaulting to ~/workspace."""
    config = parse_shell_config(CONFIG_PATH)
    raw = config.get("WORKSPACE_DIR", "~/workspace")
    return Path(expand(raw)).resolve()


def parse_boilerplate_map(config: dict[str, str]) -> dict[str, list[str]]:
    raw = config.get("BOILERPLATE_MAP", "")
    if not raw:
        return {}
    result: dict[str, list[str]] = {}
    for part in raw.split(";"):
        cleaned = part.strip()
        if ":" not in cleaned:
            continue
        key, _, deps = cleaned.partition(":")
        result[key.strip()] = [d.strip() for d in deps.split(",") if d.strip()]
    return result


_REPO_ALTERNATION_RE = re.compile(r"([\w.-]+)/\(([^)]+)\)")
_REPO_LITERAL_RE = re.compile(r"^([\w.-]+/[\w.-]+)\$?$")


def unresolvable_managed_repos(config: dict[str, str]) -> list[str]:
    """Repos named literally in MANAGED_REPOS that are not git repos on disk.

    MANAGED_REPOS is a regex, so the set of repos it *intends* cannot be
    enumerated in general — but the literal alternations people actually write
    (``org/(a|b|c)$``) can be. Without this, a repo that is renamed or deleted
    just stops matching: it silently drops out of every review while the config
    still claims it, which is how two long-dead repos stayed listed for months.
    """
    workspace = get_workspace_dir()
    pattern = config.get("MANAGED_REPOS", "")
    named: set[str] = set()
    for org, alternatives in _REPO_ALTERNATION_RE.findall(pattern):
        named |= {f"{org}/{alt.strip()}" for alt in alternatives.split("|") if alt.strip()}
    # Whatever is left once the `org/(a|b)` groups are removed splits cleanly on
    # `|`, because the only pipes that survive are the top-level alternation.
    for branch in _REPO_ALTERNATION_RE.sub("", pattern).split("|"):
        literal = _REPO_LITERAL_RE.match(branch.strip())
        if literal:
            named.add(literal.group(1))
    return sorted(repo for repo in named if not (workspace / repo / ".git").exists())


def config_health_issues(config: dict[str, str]) -> list[str]:
    """Everything wrong with the loaded config, as printable rich markup."""
    issues: list[str] = []
    if not config.get("MANAGED_REPOS"):
        issues.append("[yellow]MANAGED_REPOS not set in ~/.ac-reviewing-codebase[/yellow]")
    if not config.get("MAINTAINED_SKILLS"):
        issues.append("[yellow]MAINTAINED_SKILLS not set in ~/.ac-reviewing-codebase[/yellow]")
    issues += [
        f"[yellow]MANAGED_REPOS names '{repo}', which is not a git repo under {get_workspace_dir()}[/yellow]"
        for repo in unresolvable_managed_repos(config)
    ]
    return issues


def print_config_health() -> None:
    issues = config_health_issues(parse_shell_config(CONFIG_PATH))
    if not issues:
        console.print("  [green]All checks passed.[/green]")
        return
    for issue in issues:
        console.print(f"  {issue}")
