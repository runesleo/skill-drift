"""Read-only install self-check. Standard library only."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from skill_drift import __version__

MIN_PYTHON = (3, 9)
DEFAULT_DIRS = (
    ("claude", "~/.claude/skills"),
    ("cursor", "~/.cursor/rules"),
    ("agents", "~/.agents/skills"),
)
_SAFE_PATH = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_@%+=:,./-~")


def python_status(version_info: tuple[int, ...]) -> dict:
    shown = ".".join(str(part) for part in version_info[:3])
    if (version_info[0], version_info[1]) >= MIN_PYTHON:
        return _item("python", "OK", "none", shown, "", "")
    return _item(
        "python",
        "BLOCKED",
        "user",
        f"{shown} is older than 3.9",
        "",
        "python3 --version",
    )


def directory_status(path: Path) -> tuple[str, str]:
    try:
        if path.is_symlink() and not path.exists():
            return "BLOCKED", "symlink target is missing"
        exists = path.exists()
    except OSError:
        return "BLOCKED", "not readable"
    if not exists:
        return "MISSING", "directory does not exist"
    try:
        is_dir = path.is_dir()
    except OSError:
        return "BLOCKED", "not readable"
    if not is_dir:
        return "BLOCKED", "not a directory"
    try:
        if not os.access(path, os.R_OK | os.X_OK):
            return "BLOCKED", "not readable"
        with os.scandir(path) as listing:
            next(listing, None)
    except FileNotFoundError:
        return "MISSING", "directory does not exist"
    except OSError:
        return "BLOCKED", "not readable"
    return "OK", "directory readable"


def doctor_report(
    *,
    claude: str | None,
    cursor: str | None,
    agents: str | None,
    version_info: tuple[int, ...],
    home: Path | None,
) -> dict:
    checks = [python_status(version_info)]
    provided = (("claude", claude), ("cursor", cursor), ("agents", agents))
    if any(value for _, value in provided):
        for name, value in provided:
            if not value:
                continue
            checks.append(_path_check(name, Path(value), value))
    else:
        for name, display in DEFAULT_DIRS:
            if home is None:
                checks.append(
                    _item(
                        name,
                        "BLOCKED",
                        "user",
                        "home directory is not available",
                        display,
                        "python3 -c 'import pathlib; pathlib.Path.home()'",
                    )
                )
                continue
            checks.append(_path_check(name, _under_home(home, display), display))
    ready = all(item["status"] == "OK" for item in checks)
    return {
        "tool": "skill-drift",
        "version": __version__,
        "command": "doctor",
        "ready": ready,
        "checks": checks,
    }


def render(report: dict) -> str:
    state = "ready" if report["ready"] else "not ready"
    lines = [f"skill-drift doctor: {state}"]
    for item in report["checks"]:
        path = f"  {item['path']}" if item["path"] else ""
        line = f"{item['id']}  {item['status']}  {item['detail']}{path}"
        if item["status"] != "OK":
            line += f"  owner={item['owner']}  next: {item['next']}"
        lines.append(line)
    return "\n".join(lines) + "\n"


def execute(
    *,
    claude: str | None = None,
    cursor: str | None = None,
    agents: str | None = None,
    as_json: bool = False,
) -> int:
    home = None
    if not any((claude, cursor, agents)):
        try:
            home = Path.home()
        except RuntimeError:
            home = None
    report = doctor_report(
        claude=claude,
        cursor=cursor,
        agents=agents,
        version_info=sys.version_info,
        home=home,
    )
    if as_json:
        sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    else:
        sys.stdout.write(render(report))
    return 0 if report["ready"] else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="skill-drift doctor")
    parser.add_argument("--claude", help="Claude skills directory")
    parser.add_argument("--cursor", help="Cursor rules directory")
    parser.add_argument("--agents", help="second skills directory")
    parser.add_argument("--json", action="store_true", help="print JSON only on stdout")
    args = parser.parse_args(argv)
    return execute(claude=args.claude, cursor=args.cursor, agents=args.agents, as_json=args.json)


def _under_home(home: Path, display: str) -> Path:
    if not display.startswith("~/"):
        raise ValueError(display)
    return home / display[2:]


def _command_path(display: str) -> str:
    if display and all(char in _SAFE_PATH for char in display):
        return display
    return "'" + display.replace("'", "'\"'\"'") + "'"


def _path_check(name: str, path: Path, display: str) -> dict:
    status, detail = directory_status(path)
    if status == "OK":
        return _item(name, status, "none", detail, display, "")
    shown = _command_path(display)
    if status == "MISSING":
        return _item(name, status, "agent", detail, display, f"mkdir -p {shown}")
    return _item(name, status, "user", detail, display, f"ls -ld {shown}")


def _item(check_id: str, status: str, owner: str, detail: str, path: str, nxt: str) -> dict:
    return {
        "id": check_id,
        "status": status,
        "owner": owner,
        "detail": detail,
        "path": path,
        "next": nxt,
    }


if __name__ == "__main__":
    raise SystemExit(main())
