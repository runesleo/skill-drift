"""Group scanned files into drift findings.

File modification time is not evidence. This module only sees text.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from skill_drift.scan import OUTSIDE_LINK, Location

ROOT_ORDER = ("claude", "cursor", "agents")
KIND_ORDER = (
    "wording_drift",
    "broken_symlink",
    "skipped_link",
    "duplicate",
    "rule_frontmatter",
    "agents_mirror",
    "aligned",
)
Display = Callable[[Path], str]


def _root_index(name: str) -> tuple[int, str]:
    try:
        return (ROOT_ORDER.index(name), name)
    except ValueError:
        return (len(ROOT_ORDER), name)


def _line_set(text: str | None) -> set[str]:
    if not text:
        return set()
    return {line for line in text.split("\n") if line.strip()}


def _samples(loc: Location, others: list[Location]) -> list[str]:
    other_lines: set[str] = set()
    for item in others:
        other_lines.update(_line_set(item.normalized))
    samples: list[str] = []
    seen: set[str] = set()
    for line in (loc.normalized or "").split("\n"):
        if not line.strip() or line in other_lines or line in seen:
            continue
        seen.add(line)
        samples.append(line[:80])
        if len(samples) == 3:
            break
    return samples


def _unique_count(loc: Location, others: list[Location]) -> int:
    other_lines: set[str] = set()
    for item in others:
        other_lines.update(_line_set(item.normalized))
    return len(_line_set(loc.normalized) - other_lines)


def _prefer(locs: list[Location]) -> Location | None:
    real = [item for item in locs if item.role == "real"]
    pool = real or list(locs)
    for root in ROOT_ORDER:
        for item in pool:
            if item.root_name == root:
                return item
    return pool[0] if pool else None


def _location_dict(loc: Location, display: Display) -> dict:
    return {
        "root": loc.root_name,
        "path": display(loc.path),
        "role": loc.role,
        "kind": loc.kind,
        "sha256": loc.raw_sha256,
        "bytes": loc.size,
        "semantic_dates": list(loc.semantic_dates),
        "link_target": loc.link_target,
        "shell": loc.shell,
        "error": loc.error,
    }


def _base(
    kind: str,
    name: str,
    locs: list[Location],
    display: Display,
    suggested: str,
    reason: str,
    actionable: bool,
) -> dict:
    ordered = sorted(locs, key=lambda item: _root_index(item.root_name))
    return {
        "kind": kind,
        "name": name,
        "suggested_source": suggested,
        "reason": reason,
        "actionable": actionable,
        "locations": [_location_dict(item, display) for item in ordered],
    }


def _dates(locs: list[Location]) -> dict[str, list[str]]:
    return {item.root_name: list(item.semantic_dates) for item in locs}


def _classify(name: str, locs: list[Location], display: Display) -> dict:
    readable = [item for item in locs if item.error is None and item.normalized is not None]
    if len(readable) < len(locs):
        return _base(
            "wording_drift",
            name,
            locs,
            display,
            "undecided",
            "one copy is missing or unreadable, so there is no single source yet",
            True,
        )
    if len({item.normalized for item in readable}) == 1:
        chosen = _prefer(readable)
        placeholder = any(item.shell for item in readable)
        reason = (
            "bodies match, and the copies are placeholders; confirm this is the skill you mean"
            if placeholder
            else "bodies match; keep the real file and symlink the others when you want one source"
        )
        return _base(
            "aligned",
            name,
            locs,
            display,
            chosen.root_name if chosen else "undecided",
            reason,
            False,
        )
    shells = [item for item in readable if item.shell]
    substantial = [item for item in readable if not item.shell]
    dates = _dates(readable)
    if substantial and len({item.normalized for item in substantial}) == 1:
        chosen = _prefer(substantial)
        finding = _base(
            "wording_drift",
            name,
            locs,
            display,
            chosen.root_name if chosen else "undecided",
            "a short placeholder sits beside a fuller copy; confirm they are the same skill before merge",
            True,
        )
        finding["semantic_dates"] = dates
        return finding
    pool = substantial or readable
    counts = {
        item.root_name: _unique_count(item, [other for other in pool if other is not item])
        for item in pool
    }
    contributors = [root for root, count in counts.items() if count > 0]
    if len(contributors) >= 2 or (len({item.normalized for item in pool}) > 1 and not contributors):
        suggested = "undecided"
        reason = (
            "each copy has lines the others lack, or the same lines in a different order; "
            "pick --source yourself. Dates in the text are evidence only"
        )
    elif len(contributors) == 1:
        suggested = contributors[0]
        reason = "only one copy adds lines the others lack; confirm they are the same skill before merge"
    else:
        suggested = "undecided"
        reason = "bodies differ; pick --source yourself"
    finding = _base("wording_drift", name, locs, display, suggested, reason, True)
    finding["semantic_dates"] = dates
    finding["unique_line_counts"] = counts
    finding["unique_line_samples"] = {
        item.root_name: _samples(item, [other for other in pool if other is not item]) for item in pool
    }
    return finding


def _agents_finding(locs: list[Location], display: Display) -> dict | None:
    if not locs:
        return None
    readable = [item for item in locs if item.role != "broken" and item.raw_sha256 and not item.error]
    broken = [item for item in locs if item not in readable]
    delegates = [item for item in readable if item.delegate]
    canonicals = [item for item in readable if not item.delegate]
    hashes = {item.raw_sha256 for item in canonicals}
    if broken or not canonicals or len(hashes) > 1:
        if broken:
            reason = "an AGENTS.md copy is broken or unreadable"
        elif not canonicals:
            reason = "every AGENTS.md copy delegates; none holds the canonical bytes"
        else:
            reason = "AGENTS.md hashes differ, and a differing copy does not delegate"
        status = "drift"
        suggested = "undecided"
        actionable = True
    else:
        chosen = _prefer(canonicals)
        suggested = chosen.root_name if chosen else "undecided"
        status = "ok"
        actionable = False
        if delegates:
            reason = "non-delegate copies share one hash; the other copies delegate"
        elif len(canonicals) == 1:
            reason = "only one AGENTS.md was found"
        else:
            reason = "AGENTS.md copies share one hash"
    finding = _base("agents_mirror", "AGENTS.md", locs, display, suggested, reason, actionable)
    finding["status"] = status
    return finding


def build_report(locations: list[Location], display: Display | None = None) -> dict:
    def show(path: Path) -> str:
        if display is not None:
            return display(path)
        return path.as_posix()

    incomplete = []
    visible: list[Location] = []
    for loc in locations:
        if loc.kind == "scan_note":
            incomplete.append({
                "root": loc.root_name,
                "path": show(loc.path),
                "reason": loc.error or "未完整扫描",
            })
            continue
        visible.append(loc)
    locations = visible

    findings: list[dict] = []
    for loc in locations:
        if loc.error == OUTSIDE_LINK:
            findings.append(
                _base(
                    "skipped_link",
                    loc.name,
                    [loc],
                    show,
                    "undecided",
                    OUTSIDE_LINK,
                    True,
                )
            )
            continue
        if loc.role == "broken":
            findings.append(
                _base(
                    "broken_symlink",
                    loc.name,
                    [loc],
                    show,
                    "undecided",
                    "symlink target is missing; fix or remove the link before using it as a source",
                    True,
                )
            )
    groups: dict[str, list[Location]] = {}
    for loc in locations:
        if loc.kind not in {"skill", "rule"} or loc.role == "broken" or loc.error == OUTSIDE_LINK:
            continue
        groups.setdefault(loc.name, []).append(loc)
    for name, locs in groups.items():
        by_root: dict[str, list[Location]] = {}
        for loc in locs:
            by_root.setdefault(loc.root_name, []).append(loc)
        duplicated = False
        for items in by_root.values():
            if len(items) > 1:
                duplicated = True
                findings.append(
                    _base(
                        "duplicate",
                        name,
                        items,
                        show,
                        "undecided",
                        "the same name appears more than once in one directory; keep one copy before merge",
                        True,
                    )
                )
        if duplicated or len(locs) < 2:
            continue
        findings.append(_classify(name, locs, show))
    for loc in locations:
        if (
            loc.kind == "rule"
            and loc.role != "broken"
            and loc.error != OUTSIDE_LINK
            and loc.frontmatter_ok is False
        ):
            findings.append(
                _base(
                    "rule_frontmatter",
                    loc.name,
                    [loc],
                    show,
                    "undecided",
                    "this .mdc file does not open with a closed --- frontmatter block, so Cursor will not load it",
                    True,
                )
            )
    agents = _agents_finding(
        [item for item in locations if item.kind == "agents_md" and item.error != OUTSIDE_LINK],
        show,
    )
    if agents is not None:
        findings.append(agents)
    findings.sort(key=lambda item: (KIND_ORDER.index(item["kind"]), item["name"], item["locations"][0]["root"]))
    summary = {kind: 0 for kind in KIND_ORDER}
    for item in findings:
        summary[item["kind"]] += 1
    summary["actionable"] = sum(1 for item in findings if item["actionable"])
    return {
        "tool": "skill-drift",
        "comparison": "normalized-body",
        "mtime": "ignored",
        "findings": findings,
        "summary": summary,
        "incomplete": incomplete,
    }
