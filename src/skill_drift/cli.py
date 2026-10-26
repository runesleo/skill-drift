"""Command line for skill-drift."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from skill_drift import __version__
from skill_drift.merge import MergeError, check_report, plan_merge

ROOT_FLAGS = ("claude", "cursor", "agents")


def display_path(path: Path) -> str:
    try:
        return path.absolute().relative_to(Path.cwd().absolute()).as_posix()
    except ValueError:
        return path.as_posix()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="skill-drift")
    parser.add_argument("--version", action="version", version=f"skill-drift {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_roots(target: argparse.ArgumentParser) -> None:
        target.add_argument("--claude", help="Claude skills directory")
        target.add_argument("--cursor", help="Cursor rules directory (.mdc files)")
        target.add_argument("--agents", help="second skills directory")
        target.add_argument("--json", action="store_true", help="print JSON only on stdout")

    check = sub.add_parser("check", help="compare skill and rule text")
    add_roots(check)
    check.add_argument(
        "--agents-md",
        action="append",
        default=[],
        help="extra AGENTS.md file to hash-compare; repeat for each copy",
    )
    merge = sub.add_parser("merge", help="plan a symlink to one source")
    merge.add_argument("name", help="skill or rule name")
    merge.add_argument("--source", required=True, choices=["claude", "cursor"])
    merge.add_argument("--apply", action="store_true", help="write the plan; default is dry-run")
    merge.add_argument(
        "--add-missing",
        action="store_true",
        help="also link the source into directories that have no copy yet",
    )
    add_roots(merge)
    doctor = sub.add_parser("doctor", help="read-only check of Python and the skill directories")
    doctor.add_argument("--claude", help="Claude skills directory")
    doctor.add_argument("--cursor", help="Cursor rules directory")
    doctor.add_argument("--agents", help="second skills directory")
    doctor.add_argument("--json", action="store_true", help="print JSON only on stdout")
    return parser


def _roots(args: argparse.Namespace) -> dict[str, Path]:
    roots: dict[str, Path] = {}
    for name in ROOT_FLAGS:
        raw = getattr(args, name)
        if not raw:
            continue
        path = Path(raw)
        if not path.exists():
            raise MergeError(f"{name} directory not found: {raw}")
        if not path.is_dir():
            raise MergeError(f"{name} is not a directory: {raw}")
        roots[name] = path
    return roots


def _agents_md(args: argparse.Namespace) -> list[Path]:
    paths: list[Path] = []
    for raw in getattr(args, "agents_md", None) or []:
        path = Path(raw)
        if not path.exists():
            raise MergeError(f"AGENTS.md not found: {raw}")
        if not path.is_file():
            raise MergeError(f"AGENTS.md is not a file: {raw}")
        paths.append(path)
    return paths


def _render_check(report: dict) -> str:
    summary = report["summary"]
    lines = [
        f"skill-drift check: {summary['actionable']} actionable, {summary['aligned']} aligned",
        "comparison: normalized body text; file modification time is ignored",
    ]
    for finding in report["findings"]:
        if finding["kind"] == "aligned":
            continue
        lines.append("")
        lines.append(f"{finding['kind']}  {finding['name']}")
        for loc in finding["locations"]:
            suffix = f" -> {loc['link_target']}" if loc.get("link_target") else ""
            digest = (loc.get("sha256") or "-")[:12]
            lines.append(f"  {loc['root']}  {loc['role']}  {digest}  {loc['path']}{suffix}")
        lines.append(f"  suggested source: {finding['suggested_source']}")
        if finding.get("status"):
            lines.append(f"  status: {finding['status']}")
        lines.append(f"  {finding['reason']}")
        for root, samples in (finding.get("unique_line_samples") or {}).items():
            if samples:
                lines.append(f"  unique {root}: " + " | ".join(samples))
    aligned = [item["name"] for item in report["findings"] if item["kind"] == "aligned"]
    if aligned:
        lines.append("")
        lines.append("aligned: " + ", ".join(aligned))
    incomplete = report.get("incomplete") or []
    if incomplete:
        lines.append("")
        lines.append("未完整扫描:")
        for item in incomplete:
            lines.append(f"  {item['path']}  {item['reason']}")
    return "\n".join(lines) + "\n"


def _render_merge(report: dict) -> str:
    mode = "apply" if report["apply"] else "dry-run"
    lines = [
        f"skill-drift merge {report['name']} --source {report['source']} ({mode})",
        f"canonical: {report['canonical']}",
    ]
    for action in report["actions"]:
        if action["op"] == "archive":
            lines.append(f"  archive {action['root']}  {action['path']} -> {action['dest']}")
        elif action["op"] == "symlink":
            lines.append(f"  symlink {action['root']}  {action['path']} -> {action['target']}")
        elif action["op"] == "mkdir":
            lines.append(f"  mkdir {action['root']}  {action['path']}")
        else:
            reason = action.get("reason", "")
            lines.append(f"  {action['op']} {action.get('root', '')}  {action.get('path', '')}  {reason}".rstrip())
    if report["apply"]:
        lines.append("applied")
    else:
        lines.append("dry-run: no files written")
    return "\n".join(lines) + "\n"


def _emit(payload: dict, as_json: bool, text: str) -> None:
    if as_json:
        sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    else:
        sys.stdout.write(text)


def cmd_check(args: argparse.Namespace) -> int:
    roots = _roots(args)
    extra = _agents_md(args)
    if not roots and not extra:
        raise MergeError("pass at least one of --claude, --cursor, --agents, or --agents-md")
    report = check_report(roots, extra, display_path)
    report["version"] = __version__
    report["command"] = "check"
    report["roots"] = {name: display_path(path) for name, path in roots.items()}
    if extra:
        report["agents_md"] = [display_path(path) for path in extra]
    _emit(report, args.json, _render_check(report))
    return 1 if report["summary"]["actionable"] else 0


def cmd_doctor(args: argparse.Namespace) -> int:
    from skill_drift.doctor import execute

    return execute(claude=args.claude, cursor=args.cursor, agents=args.agents, as_json=args.json)


def cmd_merge(args: argparse.Namespace) -> int:
    roots = _roots(args)
    if not roots:
        raise MergeError("pass the directories to merge with --claude, --cursor, or --agents")
    report = plan_merge(roots, args.name, args.source, args.apply, display_path, add_missing=args.add_missing)
    report["version"] = __version__
    _emit(report, args.json, _render_merge(report))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "check":
            return cmd_check(args)
        if args.command == "merge":
            return cmd_merge(args)
        if args.command == "doctor":
            return cmd_doctor(args)
    except MergeError as exc:
        print(f"skill-drift: {exc}", file=sys.stderr)
        return 2
    print("skill-drift: unknown command", file=sys.stderr)
    return 2
