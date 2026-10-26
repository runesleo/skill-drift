"""Plan one symlink source. Files change only when apply=True."""

from __future__ import annotations

import os
import re
import shutil
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from skill_drift.compare import build_report
from skill_drift.scan import Location, normalize_name, scan_all

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9.-]{0,80}$")
Display = Callable[[Path], str]


class MergeError(Exception):
    pass


def safe_name(raw: str) -> str:
    if raw != raw.strip() or "/" in raw or "\\" in raw or ".." in raw:
        raise MergeError("name must be one skill or rule name, without a path")
    name = normalize_name(raw)
    if not name or not NAME_RE.fullmatch(name) or name.startswith("."):
        raise MergeError("name must be one skill or rule name, without a path")
    return name


def _show(display: Display | None, path: Path) -> str:
    if display is None:
        return path.as_posix()
    return display(path)


def _resolve_existing_ancestors(path: Path) -> Path:
    """Resolve symlink ancestors. Keep a missing final path lexical."""
    missing: list[str] = []
    current = path
    while current != current.parent:
        try:
            exists = current.exists() or current.is_symlink()
        except OSError:
            exists = False
        if exists:
            break
        missing.append(current.name)
        current = current.parent
    resolved = current.resolve()
    for name in reversed(missing):
        resolved = resolved / name
    return resolved


def _inside(root: Path, path: Path) -> bool:
    """True when path stays inside root after ancestor symlinks are resolved.

    The last component is not followed, so a symlink this tool is about to
    move still counts as inside even when its target is another root.
    """
    try:
        resolved_root = root.resolve()
        if path.is_symlink():
            located = path.parent.resolve() / path.name
        else:
            located = _resolve_existing_ancestors(path)
        located.relative_to(resolved_root)
        return True
    except (OSError, ValueError):
        return False


def _guard(root: Path, path: Path, label: str) -> None:
    if not _inside(root, path):
        raise MergeError(f"refusing to write outside {label}")


def _refuse_archive(root: Path, dest: Path, label: str) -> None:
    """Reject an archive dir that is a symlink or that resolves outside root."""
    archive = root / ".skill-drift-archive"
    try:
        linked = archive.is_symlink()
    except OSError as exc:
        raise MergeError(
            "refusing to archive: cannot inspect .skill-drift-archive"
            f" ({exc.strerror or 'unreadable'})"
        ) from exc
    if linked:
        raise MergeError(f"refusing to archive: .skill-drift-archive in {label} is a symlink")
    if archive.exists() and not _inside(root, archive):
        raise MergeError(
            f"refusing to archive: .skill-drift-archive in {label} resolves outside that directory"
        )
    if not _inside(root, dest):
        raise MergeError(
            f"refusing to archive: .skill-drift-archive in {label} resolves outside that directory"
        )


def _already_linked(path: Path, expected: Path) -> bool:
    try:
        if not path.is_symlink() or not path.exists():
            return False
        return path.resolve() == expected.resolve()
    except OSError:
        return False


def _rel_target(link_path: Path, target: Path) -> str:
    return Path(os.path.relpath(target.absolute(), start=link_path.parent.absolute())).as_posix()


def _archive_dest(root: Path, path: Path, stamp: str) -> Path:
    relative = path.absolute().relative_to(root.absolute())
    dest = root / ".skill-drift-archive" / stamp / relative
    base = dest
    index = 2
    while dest.exists() or dest.is_symlink():
        dest = base.with_name(f"{base.name}-{index}")
        index += 1
    return dest


def _archive_action(root: Path, root_name: str, path: Path, stamp: str, display: Display | None) -> dict:
    # Reject a symlinked archive before dest.exists() can follow it outside root.
    _refuse_archive(root, root / ".skill-drift-archive" / stamp, root_name)
    dest = _archive_dest(root, path, stamp)
    _guard(root, path, root_name)
    _refuse_archive(root, dest, root_name)
    return {
        "op": "archive",
        "root": root_name,
        "path": _show(display, path),
        "dest": _show(display, dest),
        "abs_path": path,
        "abs_dest": dest,
        "abs_root": root,
    }


def _symlink_action(root: Path, root_name: str, link_path: Path, target: Path, display: Display | None) -> dict:
    _guard(root, link_path, root_name)
    return {
        "op": "symlink",
        "root": root_name,
        "path": _show(display, link_path),
        "target": _rel_target(link_path, target),
        "abs_path": link_path,
        "abs_target": target,
        "abs_root": root,
    }


def _mkdir_action(root: Path, root_name: str, path: Path, display: Display | None) -> dict:
    _guard(root, path, root_name)
    return {
        "op": "mkdir",
        "root": root_name,
        "path": _show(display, path),
        "abs_path": path,
        "abs_root": root,
    }


def _named(locations: list[Location], name: str, root_name: str) -> list[Location]:
    return [
        item
        for item in locations
        if item.name == name and item.root_name == root_name and item.kind in {"skill", "rule"}
    ]


def _plan_rule(
    root: Path,
    root_name: str,
    name: str,
    existing: list[Location],
    canonical_file: Path,
    stamp: str,
    display: Display | None,
) -> list[dict]:
    if len(existing) > 1:
        raise MergeError(f"{root_name} has {len(existing)} copies of {name}; keep one before merge")
    dest = existing[0].path if existing else root / f"{name}.mdc"
    if _already_linked(dest, canonical_file):
        return [{"op": "skip", "root": root_name, "path": _show(display, dest), "reason": "already linked to source"}]
    actions = []
    if dest.exists() or dest.is_symlink():
        actions.append(_archive_action(root, root_name, dest, stamp, display))
    if not dest.parent.exists():
        actions.append(_mkdir_action(root, root_name, dest.parent, display))
    actions.append(_symlink_action(root, root_name, dest, canonical_file, display))
    return actions


def _plan_skill(
    root: Path,
    root_name: str,
    name: str,
    existing: list[Location],
    canonical: Location,
    stamp: str,
    display: Display | None,
) -> list[dict]:
    if len(existing) > 1:
        raise MergeError(f"{root_name} has {len(existing)} copies of {name}; keep one before merge")
    if existing and existing[0].path.name == "SKILL.md":
        dest_dir = existing[0].path.parent
    elif existing:
        dest_dir = existing[0].path
    else:
        dest_dir = root / name
    _guard(root, dest_dir, root_name)
    canonical_file = canonical.path
    if canonical.kind == "skill":
        expected_dir = canonical_file.parent
        if _already_linked(dest_dir, expected_dir):
            return [{
                "op": "skip",
                "root": root_name,
                "path": _show(display, dest_dir),
                "reason": "already linked to source",
            }]
        actions = []
        if dest_dir.exists() or dest_dir.is_symlink():
            actions.append(_archive_action(root, root_name, dest_dir, stamp, display))
        actions.append(_symlink_action(root, root_name, dest_dir, expected_dir, display))
        return actions

    if dest_dir.is_symlink():
        actions = [
            _archive_action(root, root_name, dest_dir, stamp, display),
            _mkdir_action(root, root_name, dest_dir, display),
        ]
    elif not dest_dir.exists():
        actions = [_mkdir_action(root, root_name, dest_dir, display)]
    elif not dest_dir.is_dir():
        actions = [
            _archive_action(root, root_name, dest_dir, stamp, display),
            _mkdir_action(root, root_name, dest_dir, display),
        ]
    else:
        actions = []
    link_path = dest_dir / "SKILL.md"
    if _already_linked(link_path, canonical_file):
        return [{"op": "skip", "root": root_name, "path": _show(display, link_path), "reason": "already linked to source"}]
    if link_path.exists() or link_path.is_symlink():
        actions.append(_archive_action(root, root_name, link_path, stamp, display))
    actions.append(_symlink_action(root, root_name, link_path, canonical_file, display))
    return actions


def _public(action: dict) -> dict:
    shown = {"op": action["op"]}
    for key in ("root", "path", "dest", "target", "reason"):
        if key in action:
            shown[key] = action[key]
    return shown


def plan_merge(
    roots: dict[str, Path],
    name: str,
    source: str,
    apply: bool,
    display: Display | None = None,
    stamp: str | None = None,
    add_missing: bool = False,
) -> dict:
    if source not in {"claude", "cursor"}:
        raise MergeError("--source must be claude or cursor")
    if source not in roots:
        raise MergeError(f"--source {source} needs --{source} DIR")
    skill_name = safe_name(name)
    locations = scan_all(roots)
    readable = [
        item
        for item in _named(locations, skill_name, source)
        if item.role != "broken" and not item.error
    ]
    if len(readable) != 1:
        raise MergeError(f"{source} needs exactly one readable copy of {skill_name}, found {len(readable)}")
    canonical = readable[0]
    if not _inside(roots[source], canonical.path):
        raise MergeError("source path is outside its root")
    stamp = stamp or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    actions: list[dict] = [{
        "op": "keep",
        "root": source,
        "path": _show(display, canonical.path),
        "reason": "source",
    }]
    for root_name in ("claude", "cursor", "agents"):
        if root_name == source or root_name not in roots:
            continue
        existing = _named(locations, skill_name, root_name)
        root = roots[root_name]
        if not existing and not add_missing:
            # A directory that never had this skill is left alone, so a merge
            # cannot quietly add a new Cursor rule or skill.
            actions.append({"op": "skip", "root": root_name, "path": _show(display, root),
                            "reason": "no copy here; pass --add-missing to create one"})
            continue
        if root_name == "cursor":
            actions.extend(_plan_rule(root, root_name, skill_name, existing, canonical.path, stamp, display))
        else:
            actions.extend(_plan_skill(root, root_name, skill_name, existing, canonical, stamp, display))
    if apply:
        _execute(actions)
    return {
        "tool": "skill-drift",
        "command": "merge",
        "name": skill_name,
        "source": source,
        "apply": apply,
        "canonical": _show(display, canonical.path),
        "actions": [_public(item) for item in actions],
    }


def _execute(actions: list[dict]) -> None:
    for action in actions:
        op = action["op"]
        if op in {"keep", "skip"}:
            continue
        root = action["abs_root"]
        path = action["abs_path"]
        _guard(root, path, action["root"])
        if op == "mkdir":
            path.mkdir(parents=True, exist_ok=True)
        elif op == "archive":
            dest = action["abs_dest"]
            _refuse_archive(root, dest, action["root"])
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(dest))
        elif op == "symlink":
            if path.exists() or path.is_symlink():
                raise MergeError(f"refusing to overwrite {path}")
            path.symlink_to(action["target"])
            if path.resolve() != action["abs_target"].resolve():
                raise MergeError("symlink does not resolve to the source")
        else:
            raise MergeError(f"unknown action {op}")


def check_report(roots: dict[str, Path], agents_md: list[Path] | None, display: Display | None):
    return build_report(scan_all(roots, agents_md), display)
