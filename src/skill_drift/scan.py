"""Read skill and rule trees. Comparison uses file text, never mtime."""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path

MAX_BYTES = 1_000_000
MAX_DEPTH = 4
OUTSIDE_LINK = "链接指向指定目录之外，已跳过"
DEPTH_GAP = f"未完整扫描：超过 {MAX_DEPTH} 层，未进入此目录"
UNREADABLE_GAP = "未完整扫描：目录无法读取"
SKIP_NAMES = {
    ".git",
    ".skill-drift-archive",
    "__pycache__",
    "node_modules",
    ".venv",
}
DATE_RE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")
DELEGATE_LINE = "delegates to canonical AGENTS.md"


@dataclass
class Location:
    root_name: str
    root: Path
    path: Path
    name: str
    kind: str
    role: str
    raw_sha256: str | None = None
    normalized: str | None = None
    size: int | None = None
    semantic_dates: tuple[str, ...] = ()
    frontmatter_ok: bool | None = None
    link_target: str | None = None
    shell: bool = False
    delegate: bool = False
    error: str | None = None


def normalize_name(raw: str) -> str:
    text = raw.strip().lower().replace("_", "-").replace(" ", "-")
    text = re.sub(r"[^a-z0-9.-]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text


def parse_frontmatter(text: str) -> tuple[dict[str, str], str, bool]:
    if not text.startswith("---"):
        return {}, text, False
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text, False
    end = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end = index
            break
    if end is None:
        return {}, text, False
    fields: dict[str, str] = {}
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        if not key or " " in key:
            continue
        fields[key] = value.strip().strip('"').strip("'")
    body = "\n".join(lines[end + 1 :]).strip()
    return fields, body, True


def normalize_body(body: str) -> str:
    body = body.replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in body.split("\n")]
    text = "\n".join(lines).strip()
    return re.sub(r"\n{3,}", "\n\n", text)


def is_shell(normalized: str) -> bool:
    compact = re.sub(r"\s+", " ", normalized.strip().lower())
    if compact in {"", "todo", "tbd", "placeholder", "fixme", "wip"}:
        return True
    return compact.startswith("todo:") or compact.startswith("todo ")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_text(path: Path) -> dict:
    try:
        size = path.stat().st_size
    except OSError as exc:
        return {"error": exc.strerror or "unreadable"}
    if size > MAX_BYTES:
        return {"error": "too_large", "size": size}
    try:
        data = path.read_bytes()
    except OSError as exc:
        return {"error": exc.strerror or "unreadable"}
    digest = _sha256(data)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return {"error": "not_utf8", "size": len(data), "raw_sha256": digest}
    fields, body, frontmatter_ok = parse_frontmatter(text)
    normalized = normalize_body(body)
    return {
        "raw_sha256": digest,
        "normalized": normalized,
        "size": len(data),
        "semantic_dates": tuple(sorted(set(DATE_RE.findall(text)))),
        "frontmatter_ok": frontmatter_ok,
        "shell": is_shell(normalized),
        "fields": fields,
        "delegate": any(line.strip() == DELEGATE_LINE for line in text.splitlines()),
    }


def _link_target(path: Path) -> str | None:
    if path.is_symlink():
        return os.readlink(path)
    if path.parent.is_symlink():
        return os.readlink(path.parent)
    return None


def _role(path: Path) -> str:
    try:
        linked = path.is_symlink() or path.parent.is_symlink()
        exists = path.exists()
    except OSError:
        return "broken"
    if not exists:
        return "broken"
    if linked:
        return "symlink"
    return "real"


def _target_allowed(path: Path, allowed: list[Path]) -> bool:
    try:
        if not path.exists():
            return True
        resolved = path.resolve()
    except OSError:
        return False
    for root in allowed:
        try:
            resolved.relative_to(root.resolve())
            return True
        except (OSError, ValueError):
            continue
    return False


def _apply_content(loc: Location, allowed: list[Path]) -> Location:
    if loc.role == "broken":
        loc.link_target = _link_target(loc.path)
        return loc
    if not _target_allowed(loc.path, allowed):
        loc.error = OUTSIDE_LINK
        loc.link_target = _link_target(loc.path)
        return loc
    loaded = _read_text(loc.path)
    loc.error = loaded.get("error")
    loc.raw_sha256 = loaded.get("raw_sha256")
    loc.normalized = loaded.get("normalized")
    loc.size = loaded.get("size")
    loc.semantic_dates = loaded.get("semantic_dates") or ()
    loc.frontmatter_ok = loaded.get("frontmatter_ok")
    loc.shell = bool(loaded.get("shell"))
    loc.delegate = bool(loaded.get("delegate"))
    loc.link_target = _link_target(loc.path)
    front_name = (loaded.get("fields") or {}).get("name")
    if front_name:
        renamed = normalize_name(front_name)
        if renamed:
            loc.name = renamed
    return loc


def load_agents_file(
    path: Path,
    root_name: str,
    root: Path | None = None,
    allowed: list[Path] | None = None,
) -> Location:
    path = path.absolute()
    parent = root.absolute() if root is not None else path.parent
    allowed_roots = [item.absolute() for item in (allowed if allowed is not None else [parent])]
    loc = Location(
        root_name=root_name,
        root=parent,
        path=path,
        name="AGENTS.md",
        kind="agents_md",
        role="real",
    )
    if path.is_symlink() and not path.exists():
        loc.role = "broken"
        loc.link_target = os.readlink(path)
        loc.error = "broken symlink"
        return loc
    if not path.exists():
        loc.role = "broken"
        loc.error = "missing"
        return loc
    loc.role = _role(path)
    return _apply_content(loc, allowed_roots)


def _broken(root_name: str, root: Path, path: Path) -> Location:
    if path.name == "SKILL.md":
        name = normalize_name(path.parent.name)
        kind = "skill"
    elif path.suffix == ".mdc":
        name = normalize_name(path.stem)
        kind = "rule"
    elif path.suffix == "" and root_name in {"claude", "agents"}:
        name = normalize_name(path.name)
        kind = "skill"
    else:
        name = path.name
        kind = "symlink"
    target = None
    try:
        if path.is_symlink():
            target = os.readlink(path)
    except OSError:
        target = None
    return Location(
        root_name=root_name,
        root=root,
        path=path,
        name=name or path.name,
        kind=kind,
        role="broken",
        link_target=target,
        error="broken symlink",
    )


def _gap(root_name: str, root: Path, path: Path, reason: str) -> Location:
    return Location(
        root_name=root_name,
        root=root,
        path=path,
        name=path.name or root_name,
        kind="scan_note",
        role="real",
        error=reason,
    )


def _skill_from_dir(root_name: str, root: Path, directory: Path, allowed: list[Path]) -> Location | None:
    skill_md = directory / "SKILL.md"
    try:
        present = skill_md.exists() or skill_md.is_symlink()
    except OSError:
        present = skill_md.is_symlink()
    if not present:
        return None
    loc = Location(
        root_name=root_name,
        root=root,
        path=skill_md,
        name=normalize_name(directory.name),
        kind="skill",
        role=_role(skill_md),
    )
    if loc.role == "broken":
        loc.link_target = _link_target(skill_md)
        loc.error = "broken symlink"
        return loc
    return _apply_content(loc, allowed)


def _rule_from_file(root_name: str, root: Path, path: Path, allowed: list[Path]) -> Location:
    loc = Location(
        root_name=root_name,
        root=root,
        path=path,
        name=normalize_name(path.stem),
        kind="rule",
        role=_role(path),
    )
    if loc.role == "broken":
        loc.link_target = _link_target(path)
        loc.error = "broken symlink"
        return loc
    return _apply_content(loc, allowed)


def scan_root(root_name: str, root: Path, allowed: list[Path] | None = None) -> list[Location]:
    if root_name not in {"claude", "cursor", "agents"}:
        raise ValueError(f"unknown root {root_name}")
    root = root.absolute()
    if not root.is_dir():
        raise NotADirectoryError(root)
    allowed_roots = [item.absolute() for item in (allowed if allowed is not None else [root])]
    found: list[Location] = []
    agents = root / "AGENTS.md"
    if agents.exists() or agents.is_symlink():
        found.append(load_agents_file(agents, root_name, root, allowed_roots))

    def visit(directory: Path, depth: int) -> None:
        if depth > MAX_DEPTH:
            found.append(_gap(root_name, root, directory, DEPTH_GAP))
            return
        try:
            entries = sorted(directory.iterdir(), key=lambda item: item.name)
        except OSError:
            found.append(_gap(root_name, root, directory, UNREADABLE_GAP))
            return
        for entry in entries:
            if entry.name in SKIP_NAMES or entry.name.startswith("."):
                continue
            if entry.name == "AGENTS.md" and directory == root:
                continue
            try:
                symlink = entry.is_symlink()
                exists = entry.exists()
            except OSError:
                found.append(_broken(root_name, root, entry))
                continue
            if symlink and not exists:
                found.append(_broken(root_name, root, entry))
                continue
            if symlink and entry.is_dir():
                if root_name in {"claude", "agents"}:
                    skill = _skill_from_dir(root_name, root, entry, allowed_roots)
                    if skill is not None:
                        found.append(skill)
                continue
            if entry.is_dir():
                if root_name in {"claude", "agents"}:
                    skill = _skill_from_dir(root_name, root, entry, allowed_roots)
                    if skill is not None:
                        found.append(skill)
                if depth < MAX_DEPTH:
                    visit(entry, depth + 1)
                else:
                    found.append(_gap(root_name, root, entry, DEPTH_GAP))
                continue
            if root_name == "cursor" and entry.is_file() and entry.suffix == ".mdc":
                found.append(_rule_from_file(root_name, root, entry, allowed_roots))

    visit(root, 1)
    return found


def scan_all(roots: dict[str, Path], agents_md: list[Path] | None = None) -> list[Location]:
    found: list[Location] = []
    allowed: list[Path] = []
    for name in ("claude", "cursor", "agents"):
        path = roots.get(name)
        if path is not None:
            allowed.append(path.absolute())
    for name in ("claude", "cursor", "agents"):
        path = roots.get(name)
        if path is not None:
            found.extend(scan_root(name, path, allowed))
    used = {item.root_name for item in found if item.kind == "agents_md"}
    seen = {item.path.absolute() for item in found if item.kind == "agents_md"}
    for path in agents_md or []:
        absolute = path.absolute()
        if absolute in seen:
            continue
        parent = normalize_name(absolute.parent.name)
        label = parent if parent in {"claude", "cursor", "agents"} and parent not in used else "agents-md"
        if label in used:
            index = 2
            while f"{label}-{index}" in used:
                index += 1
            label = f"{label}-{index}"
        used.add(label)
        seen.add(absolute)
        found.append(load_agents_file(path, label, absolute.parent, allowed + [absolute.parent]))
    return found
