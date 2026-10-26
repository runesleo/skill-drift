"""Unit tests against the fake trees in examples/. They never read a home directory."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from skill_drift import __version__  # noqa: E402
from skill_drift.cli import _render_check  # noqa: E402
from skill_drift.compare import build_report  # noqa: E402
from skill_drift.doctor import directory_status, doctor_report, python_status  # noqa: E402
from skill_drift.merge import MergeError, plan_merge, safe_name  # noqa: E402
from skill_drift.scan import scan_all  # noqa: E402

DEMO = ROOT / "examples" / "demo"
HASH_DRIFT = ROOT / "examples" / "agents-hash-drift"
SUBSET = ROOT / "examples" / "subset"


def _roots(base: Path) -> dict[str, Path]:
    return {"claude": base / "claude", "cursor": base / "cursor", "agents": base / "agents"}


def _report(base: Path) -> dict:
    return build_report(scan_all(_roots(base)))


def _by(report: dict, kind: str, name: str) -> dict:
    hits = [item for item in report["findings"] if item["kind"] == kind and item["name"] == name]
    if len(hits) != 1:
        raise AssertionError(f"{kind} {name}: {len(hits)}")
    return hits[0]


def _copy(src: Path, dest: Path) -> None:
    shutil.copytree(src, dest, symlinks=True)


def _frozen(base: Path) -> list[tuple]:
    rows = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames.sort()
        filenames.sort()
        for name in dirnames + filenames:
            path = Path(dirpath) / name
            st = path.lstat()
            payload = path.read_bytes() if path.is_file() and not path.is_symlink() else None
            rows.append((path.relative_to(base).as_posix(), st.st_mtime_ns, st.st_size, payload))
    return rows


def _digest_tree(base: Path) -> dict[str, str]:
    found = {}
    for path in base.rglob("*"):
        if path.is_symlink() or not path.is_file():
            continue
        if ".skill-drift-archive" in path.parts:
            continue
        found[path.relative_to(base).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return found


class CheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = _report(DEMO)

    def test_mtime_field_is_ignored(self):
        self.assertEqual(self.report["mtime"], "ignored")
        self.assertEqual(self.report["comparison"], "normalized-body")

    def test_fork_stays_undecided_with_semantic_date(self):
        ship = _by(self.report, "wording_drift", "ship-note")
        self.assertEqual(ship["suggested_source"], "undecided")
        self.assertIn("2026-01-02", ship["semantic_dates"]["cursor"])
        self.assertEqual(ship["semantic_dates"]["claude"], [])
        self.assertGreater(ship["unique_line_counts"]["claude"], 0)
        self.assertGreater(ship["unique_line_counts"]["cursor"], 0)

    def test_placeholder_suggests_full_copy(self):
        shell = _by(self.report, "wording_drift", "empty-shell")
        self.assertEqual(shell["suggested_source"], "cursor")
        self.assertTrue(any(item["shell"] for item in shell["locations"] if item["root"] == "claude"))

    def test_same_body_is_aligned(self):
        aligned = _by(self.report, "aligned", "aligned-note")
        self.assertFalse(aligned["actionable"])
        self.assertEqual(aligned["suggested_source"], "claude")

    def test_broken_symlink_and_duplicate_and_frontmatter(self):
        broken = _by(self.report, "broken_symlink", "missing-skill")
        self.assertIn("nowhere", broken["locations"][0]["link_target"])
        _by(self.report, "duplicate", "dup-rule")
        _by(self.report, "rule_frontmatter", "no-frontmatter")
        self.assertFalse(any(item["kind"] == "wording_drift" and item["name"] == "dup-rule" for item in self.report["findings"]))

    def test_agents_delegate_is_ok(self):
        mirror = _by(self.report, "agents_mirror", "AGENTS.md")
        self.assertEqual(mirror["status"], "ok")
        self.assertFalse(mirror["actionable"])
        self.assertEqual(mirror["suggested_source"], "claude")

    def test_newer_mtime_does_not_change_verdict(self):
        with tempfile.TemporaryDirectory() as raw:
            dest = Path(raw) / "demo"
            _copy(DEMO, dest)
            claude = dest / "claude" / "ship-note" / "SKILL.md"
            cursor = dest / "cursor" / "ship-note.mdc"
            stub = dest / "claude" / "empty-shell" / "SKILL.md"
            full = dest / "cursor" / "empty-shell.mdc"
            os.utime(claude, (1, 1))
            os.utime(cursor, (2_000_000_000, 2_000_000_000))
            os.utime(stub, (2_000_000_000, 2_000_000_000))
            os.utime(full, (1, 1))
            first = _report(dest)
            os.utime(claude, (2_000_000_000, 2_000_000_000))
            os.utime(cursor, (1, 1))
            os.utime(stub, (1, 1))
            os.utime(full, (2_000_000_000, 2_000_000_000))
            second = _report(dest)
            self.assertEqual(_by(first, "wording_drift", "ship-note")["suggested_source"], "undecided")
            self.assertEqual(_by(second, "wording_drift", "ship-note")["suggested_source"], "undecided")
            self.assertEqual(_by(first, "wording_drift", "empty-shell")["suggested_source"], "cursor")
            self.assertEqual(_by(second, "wording_drift", "empty-shell")["suggested_source"], "cursor")

    def test_check_does_not_write(self):
        with tempfile.TemporaryDirectory() as raw:
            dest = Path(raw) / "demo"
            _copy(DEMO, dest)
            before = _digest_tree(dest)
            _report(dest)
            self.assertEqual(before, _digest_tree(dest))
            self.assertFalse((dest / "cursor" / ".skill-drift-archive").exists())

    def test_hash_drift_and_subset_examples(self):
        drift = build_report(scan_all(_roots(HASH_DRIFT)))
        mirror = _by(drift, "agents_mirror", "AGENTS.md")
        self.assertEqual(mirror["status"], "drift")
        self.assertTrue(mirror["actionable"])
        self.assertEqual(mirror["suggested_source"], "undecided")
        subset = build_report(scan_all({"claude": SUBSET / "claude", "cursor": SUBSET / "cursor"}))
        note = _by(subset, "wording_drift", "subset-note")
        self.assertEqual(note["suggested_source"], "claude")
        self.assertEqual(note["unique_line_counts"]["cursor"], 0)
        self.assertGreater(note["unique_line_counts"]["claude"], 0)

    def test_source_never_reads_mtime_or_home(self):
        # doctor.py is the only module allowed to resolve the home directory.
        allowed_home = {"doctor.py"}
        for path in (ROOT / "src").rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for banned in ("st_mtime", "getmtime", "expanduser", "os.environ"):
                self.assertNotIn(banned, text, path.name)
            if path.name not in allowed_home:
                self.assertNotIn("Path.home", text, path.name)


class MergeTests(unittest.TestCase):
    def test_rejects_path_name(self):
        with self.assertRaises(MergeError):
            safe_name("../out")
        with self.assertRaises(MergeError):
            safe_name("nested/name")

    def test_merge_refuses_duplicate_source(self):
        with self.assertRaises(MergeError):
            plan_merge(_roots(DEMO), "dup-rule", "cursor", apply=False)

    def test_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as raw:
            dest = Path(raw) / "demo"
            _copy(DEMO, dest)
            before = _digest_tree(dest)
            report = plan_merge(_roots(dest), "status-line", "claude", apply=False)
            self.assertFalse(report["apply"])
            self.assertTrue(any(item["op"] == "symlink" for item in report["actions"]))
            self.assertEqual(before, _digest_tree(dest))
            self.assertFalse((dest / "cursor" / "status-line.mdc").is_symlink())

    def test_apply_symlinks_and_second_apply_skips(self):
        with tempfile.TemporaryDirectory() as raw:
            dest = Path(raw) / "demo"
            _copy(DEMO, dest)
            roots = _roots(dest)
            plan_merge(roots, "status-line", "claude", apply=True)
            cursor_rule = dest / "cursor" / "status-line.mdc"
            agents_dir = dest / "agents" / "status-line"
            source = dest / "claude" / "status-line" / "SKILL.md"
            self.assertTrue(cursor_rule.is_symlink())
            self.assertEqual(cursor_rule.resolve(), source.resolve())
            self.assertTrue(agents_dir.is_symlink())
            self.assertEqual(agents_dir.resolve(), source.parent.resolve())
            archived = list((dest / "cursor" / ".skill-drift-archive").rglob("status-line.mdc"))
            self.assertTrue(archived and archived[0].is_file() and not archived[0].is_symlink())
            report = build_report(scan_all(roots))
            self.assertEqual(_by(report, "aligned", "status-line")["kind"], "aligned")
            archive_count = len(list((dest).rglob(".skill-drift-archive/**/*")))
            again = plan_merge(roots, "status-line", "claude", apply=True)
            self.assertTrue(all(item["op"] in {"keep", "skip"} for item in again["actions"]))
            self.assertEqual(archive_count, len(list(dest.rglob(".skill-drift-archive/**/*"))))

    def test_merge_leaves_directories_without_a_copy_alone(self):
        with tempfile.TemporaryDirectory() as raw:
            dest = Path(raw) / "demo"
            _copy(DEMO, dest)
            (dest / "cursor" / "status-line.mdc").unlink()
            roots = _roots(dest)
            report = plan_merge(roots, "status-line", "claude", apply=True)
            self.assertFalse((dest / "cursor" / "status-line.mdc").exists())
            skipped = [a for a in report["actions"] if a["root"] == "cursor"]
            self.assertEqual([a["op"] for a in skipped], ["skip"])
            plan_merge(roots, "status-line", "claude", apply=True, add_missing=True)
            self.assertTrue((dest / "cursor" / "status-line.mdc").is_symlink())

    def test_apply_from_cursor_file(self):
        with tempfile.TemporaryDirectory() as raw:
            dest = Path(raw) / "demo"
            _copy(DEMO, dest)
            roots = _roots(dest)
            plan_merge(roots, "empty-shell", "cursor", apply=True)
            source = dest / "cursor" / "empty-shell.mdc"
            skill = dest / "claude" / "empty-shell" / "SKILL.md"
            self.assertFalse(source.is_symlink())
            self.assertTrue(skill.is_symlink())
            self.assertEqual(skill.resolve(), source.resolve())
            agents_skill = dest / "agents" / "empty-shell" / "SKILL.md"
            self.assertTrue(agents_skill.is_symlink())
            self.assertEqual(agents_skill.resolve(), source.resolve())
            report = build_report(scan_all(roots))
            aligned = _by(report, "aligned", "empty-shell")
            self.assertEqual(aligned["suggested_source"], "cursor")


class CliTests(unittest.TestCase):
    def _run(self, args: list[str], home: Path | None = None) -> subprocess.CompletedProcess[str]:
        env = {
            "PATH": os.environ["PATH"],
            "HOME": str(home or Path("/tmp/skill-drift-empty-home")),
            "PYTHONPATH": str(ROOT / "src"),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        if "TMPDIR" in os.environ:
            env["TMPDIR"] = os.environ["TMPDIR"]
        return subprocess.run(
            [sys.executable, "-m", "skill_drift", *args],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_json_stdout_has_no_human_text(self):
        result = self._run([
            "check",
            "--claude", str(DEMO / "claude"),
            "--cursor", str(DEMO / "cursor"),
            "--agents", str(DEMO / "agents"),
            "--json",
        ])
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertTrue(result.stdout.lstrip().startswith("{"))
        payload = json.loads(result.stdout)
        self.assertEqual(payload["mtime"], "ignored")
        self.assertNotIn("skill-drift check:", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_merge_path_escape_exits_2(self):
        result = self._run([
            "merge", "../out",
            "--source", "claude",
            "--claude", str(DEMO / "claude"),
        ])
        self.assertEqual(result.returncode, 2)
        self.assertIn("name", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_agents_md_flag_dedups_scanned_files(self):
        result = self._run([
            "check",
            "--claude", str(HASH_DRIFT / "claude"),
            "--cursor", str(HASH_DRIFT / "cursor"),
            "--agents", str(HASH_DRIFT / "agents"),
            "--agents-md", str(HASH_DRIFT / "claude" / "AGENTS.md"),
            "--json",
        ])
        self.assertEqual(result.returncode, 1, result.stderr)
        payload = json.loads(result.stdout)
        mirrors = [item for item in payload["findings"] if item["kind"] == "agents_mirror"]
        self.assertEqual(len(mirrors), 1)
        self.assertEqual(len(mirrors[0]["locations"]), 3)


class DoctorTests(unittest.TestCase):
    def _run(self, args: list[str], home: Path | None = None) -> subprocess.CompletedProcess[str]:
        env = {
            "PATH": os.environ["PATH"],
            "HOME": str(home or Path("/tmp/skill-drift-empty-home")),
            "PYTHONPATH": str(ROOT / "src"),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        if "TMPDIR" in os.environ:
            env["TMPDIR"] = os.environ["TMPDIR"]
        return subprocess.run(
            [sys.executable, "-m", "skill_drift", *args],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_python_boundary(self):
        old = python_status((3, 8, 20))
        self.assertEqual(old["status"], "BLOCKED")
        self.assertEqual(old["owner"], "user")
        self.assertIn("3.9", old["detail"])
        self.assertEqual(old["next"], "python3 --version")
        fresh = python_status((3, 9, 0))
        self.assertEqual(fresh["status"], "OK")
        self.assertEqual(fresh["detail"], "3.9.0")
        self.assertEqual(fresh["owner"], "none")
        self.assertEqual(fresh["next"], "")

    def test_directory_status_cases(self):
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            ready = base / "ready"
            ready.mkdir()
            (ready / "note.txt").write_text("x", encoding="utf-8")
            missing = base / "missing"
            wrong = base / "file"
            wrong.write_text("x", encoding="utf-8")
            self.assertEqual(directory_status(ready), ("OK", "directory readable"))
            self.assertEqual(directory_status(missing)[0], "MISSING")
            self.assertEqual(directory_status(wrong), ("BLOCKED", "not a directory"))

    def test_broken_symlink_is_blocked(self):
        with tempfile.TemporaryDirectory() as raw:
            link = Path(raw) / "broken"
            link.symlink_to(Path(raw) / "missing-target")
            status, detail = directory_status(link)
            self.assertEqual(status, "BLOCKED")
            self.assertIn("symlink", detail)
            result = self._run(["doctor", "--claude", str(link)])
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("BLOCKED", result.stdout)
        self.assertIn("next: ls -ld", result.stdout)
        self.assertNotIn("mkdir -p", result.stdout)

    def test_unreadable_directory_is_blocked(self):
        if os.geteuid() == 0:
            self.skipTest("root ignores file mode")
        with tempfile.TemporaryDirectory() as raw:
            blocked = Path(raw) / "blocked"
            blocked.mkdir()
            blocked.chmod(0)
            try:
                self.assertEqual(directory_status(blocked), ("BLOCKED", "not readable"))
            finally:
                blocked.chmod(0o755)

    def test_missing_home_blocks_default_dirs(self):
        report = doctor_report(
            claude=None,
            cursor=None,
            agents=None,
            version_info=(3, 11, 0),
            home=None,
        )
        self.assertFalse(report["ready"])
        claude = next(item for item in report["checks"] if item["id"] == "claude")
        self.assertEqual(claude["status"], "BLOCKED")
        self.assertEqual(claude["owner"], "user")
        self.assertEqual(claude["path"], "~/.claude/skills")

    def test_one_directory_flag_skips_the_others(self):
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            only = base / "only"
            only.mkdir()
            result = self._run(["doctor", "--cursor", str(only), "--json"], home=base / "home")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual([item["id"] for item in payload["checks"]], ["python", "cursor"])
        self.assertEqual(payload["version"], __version__)

    def test_doctor_on_demo_is_ready_and_writes_nothing(self):
        before = _digest_tree(DEMO)
        result = self._run([
            "doctor",
            "--claude", str(DEMO / "claude"),
            "--cursor", str(DEMO / "cursor"),
            "--agents", str(DEMO / "agents"),
        ])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("skill-drift doctor: ready", result.stdout)
        self.assertNotIn("not ready", result.stdout)
        for name in ("python  OK", "claude  OK", "cursor  OK", "agents  OK"):
            self.assertIn(name, result.stdout)
        self.assertEqual(result.stderr, "")
        self.assertEqual(before, _digest_tree(DEMO))

    def test_doctor_json_is_only_json(self):
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            claude = base / "claude"
            claude.mkdir()
            missing = base / "missing"
            result = self._run([
                "doctor",
                "--claude", str(claude),
                "--cursor", str(missing),
                "--json",
            ])
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertTrue(result.stdout.lstrip().startswith("{"))
        self.assertNotIn("skill-drift doctor:", result.stdout)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["ready"])
        by_id = {item["id"]: item for item in payload["checks"]}
        self.assertEqual(set(by_id), {"python", "claude", "cursor"})
        self.assertEqual(by_id["claude"]["status"], "OK")
        self.assertEqual(by_id["claude"]["next"], "")
        self.assertEqual(by_id["cursor"]["status"], "MISSING")
        self.assertEqual(by_id["cursor"]["owner"], "agent")
        self.assertIn("mkdir -p", by_id["cursor"]["next"])

    def test_defaults_follow_home_and_hide_absolute_path(self):
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw)
            for relative in (".claude/skills", ".cursor/rules", ".agents/skills"):
                (home / relative).mkdir(parents=True)
            result = self._run(["doctor", "--json"], home=home)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn(str(home), result.stdout)
        payload = json.loads(result.stdout)
        paths = {item["id"]: item["path"] for item in payload["checks"]}
        self.assertEqual(paths["claude"], "~/.claude/skills")
        self.assertEqual(paths["cursor"], "~/.cursor/rules")
        self.assertEqual(paths["agents"], "~/.agents/skills")
        self.assertTrue(payload["ready"])

    def test_missing_default_dirs_name_the_next_command(self):
        with tempfile.TemporaryDirectory() as raw:
            result = self._run(["doctor"], home=Path(raw))
        self.assertEqual(result.returncode, 1)
        self.assertIn("skill-drift doctor: not ready", result.stdout)
        self.assertIn("claude  MISSING", result.stdout)
        self.assertIn("owner=agent", result.stdout)
        self.assertIn("next: mkdir -p ~/.claude/skills", result.stdout)
        self.assertIn("next: mkdir -p ~/.cursor/rules", result.stdout)
        self.assertIn("next: mkdir -p ~/.agents/skills", result.stdout)
        self.assertNotIn(raw, result.stdout)

    def test_file_where_a_directory_should_be(self):
        with tempfile.TemporaryDirectory() as raw:
            weird = Path(raw) / "not-a-dir"
            weird.write_text("x", encoding="utf-8")
            result = self._run(["doctor", "--claude", str(weird)])
        self.assertEqual(result.returncode, 1)
        self.assertIn("BLOCKED", result.stdout)
        self.assertIn("not a directory", result.stdout)
        self.assertIn("owner=user", result.stdout)
        self.assertIn("next: ls -ld", result.stdout)

    def test_unreadable_directory_cli(self):
        if os.geteuid() == 0:
            self.skipTest("root ignores file mode")
        with tempfile.TemporaryDirectory() as raw:
            blocked = Path(raw) / "blocked"
            blocked.mkdir()
            blocked.chmod(0)
            try:
                result = self._run(["doctor", "--agents", str(blocked)])
            finally:
                blocked.chmod(0o755)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("agents  BLOCKED", result.stdout)
        self.assertIn("owner=user", result.stdout)
        self.assertIn("next: ls -ld", result.stdout)

    def test_module_entry_and_source_stay_independent(self):
        text = (ROOT / "src" / "skill_drift" / "doctor.py").read_text(encoding="utf-8")
        self.assertNotIn("skill_drift.merge", text)
        self.assertNotIn("skill_drift.scan", text)
        self.assertNotIn("skill_drift.compare", text)
        with tempfile.TemporaryDirectory() as raw:
            only = Path(raw) / "only"
            only.mkdir()
            env = {
                "PATH": os.environ["PATH"],
                "HOME": raw,
                "PYTHONPATH": str(ROOT / "src"),
                "PYTHONDONTWRITEBYTECODE": "1",
            }
            if "TMPDIR" in os.environ:
                env["TMPDIR"] = os.environ["TMPDIR"]
            result = subprocess.run(
                [sys.executable, "-m", "skill_drift.doctor", "--claude", str(only), "--json"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["command"], "doctor")
        self.assertTrue(payload["ready"])


class BoundaryTests(unittest.TestCase):
    def test_archive_symlink_outside_root_is_refused(self):
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            dest = base / "demo"
            outside = base / "outside"
            outside.mkdir()
            (outside / "marker.txt").write_text("keep", encoding="utf-8")
            before = _frozen(outside)
            _copy(DEMO, dest)
            (dest / "cursor" / ".skill-drift-archive").symlink_to(outside, target_is_directory=True)
            with self.assertRaises(MergeError) as caught:
                plan_merge(_roots(dest), "status-line", "claude", apply=True)
            message = str(caught.exception)
            self.assertIn(".skill-drift-archive", message)
            self.assertIn("symlink", message)
            self.assertEqual(before, _frozen(outside))
            rule = dest / "cursor" / "status-line.mdc"
            self.assertTrue(rule.is_file())
            self.assertFalse(rule.is_symlink())

    def test_archive_symlink_inside_root_is_refused(self):
        with tempfile.TemporaryDirectory() as raw:
            dest = Path(raw) / "demo"
            _copy(DEMO, dest)
            kept = dest / "cursor" / "kept-archive"
            kept.mkdir()
            (kept / "marker.txt").write_text("stay", encoding="utf-8")
            (dest / "cursor" / ".skill-drift-archive").symlink_to(kept, target_is_directory=True)
            with self.assertRaises(MergeError) as caught:
                plan_merge(_roots(dest), "status-line", "claude", apply=True)
            self.assertIn("symlink", str(caught.exception))
            self.assertEqual((kept / "marker.txt").read_text(encoding="utf-8"), "stay")
            self.assertEqual([item.name for item in kept.iterdir()], ["marker.txt"])
            self.assertFalse((dest / "cursor" / "status-line.mdc").is_symlink())

    def test_archive_destination_resolving_outside_is_refused(self):
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            dest = base / "demo"
            outside = base / "outside"
            outside.mkdir()
            (outside / "marker.txt").write_text("keep", encoding="utf-8")
            before = _frozen(outside)
            _copy(DEMO, dest)
            archive = dest / "cursor" / ".skill-drift-archive"
            archive.mkdir()
            (archive / "fixed").symlink_to(outside, target_is_directory=True)
            with self.assertRaises(MergeError) as caught:
                plan_merge(_roots(dest), "status-line", "claude", apply=True, stamp="fixed")
            self.assertIn("resolves outside", str(caught.exception))
            self.assertEqual(before, _frozen(outside))
            self.assertFalse((dest / "cursor" / "status-line.mdc").is_symlink())

    def test_rule_symlink_outside_root_is_not_read(self):
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            cursor = base / "cursor"
            cursor.mkdir()
            outside = base / "outside"
            outside.mkdir()
            secret = outside / "secret.mdc"
            secret.write_text(
                "---\ndescription: secret\nalwaysApply: false\n---\nSECRET_PHRASE_DO_NOT_LEAK\n",
                encoding="utf-8",
            )
            (cursor / "secret.mdc").symlink_to(secret)
            (cursor / "local.mdc").write_text(
                "---\ndescription: local\nalwaysApply: false\n---\nlocal only\n",
                encoding="utf-8",
            )
            before = secret.read_bytes()
            report = build_report(scan_all({"cursor": cursor}))
            text = _render_check(report)
            blob = json.dumps(report, ensure_ascii=False)
            self.assertEqual(text.count("链接指向指定目录之外，已跳过"), 1)
            self.assertNotIn("SECRET_PHRASE_DO_NOT_LEAK", text)
            self.assertNotIn("SECRET_PHRASE_DO_NOT_LEAK", blob)
            self.assertEqual(secret.read_bytes(), before)

    def test_skill_dir_symlink_outside_root_is_not_read(self):
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            claude = base / "claude"
            claude.mkdir()
            outside = base / "outside" / "leaked"
            outside.mkdir(parents=True)
            secret = outside / "SKILL.md"
            secret.write_text("---\nname: leaked\n---\nSECRET_SKILL_BODY\n", encoding="utf-8")
            (claude / "leaked").symlink_to(outside, target_is_directory=True)
            before = secret.read_bytes()
            report = build_report(scan_all({"claude": claude}))
            text = _render_check(report)
            blob = json.dumps(report, ensure_ascii=False)
            self.assertEqual(text.count("链接指向指定目录之外，已跳过"), 1)
            self.assertNotIn("SECRET_SKILL_BODY", text)
            self.assertNotIn("SECRET_SKILL_BODY", blob)
            self.assertEqual(secret.read_bytes(), before)

    def test_symlink_into_another_named_root_is_read(self):
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            skill_dir = base / "claude" / "note"
            skill_dir.mkdir(parents=True)
            skill = skill_dir / "SKILL.md"
            skill.write_text("---\nname: note\ndescription: shared\n---\nSHARED_BODY_LINE\n", encoding="utf-8")
            cursor = base / "cursor"
            cursor.mkdir()
            (cursor / "note.mdc").symlink_to(skill)
            report = build_report(scan_all({"claude": base / "claude", "cursor": cursor}))
            blob = json.dumps(report, ensure_ascii=False)
            self.assertNotIn("链接指向指定目录之外，已跳过", blob)
            digest = hashlib.sha256(skill.read_bytes()).hexdigest()
            aligned = _by(report, "aligned", "note")
            self.assertEqual([item["sha256"] for item in aligned["locations"]], [digest, digest])

    def test_truncated_depth_is_listed(self):
        with tempfile.TemporaryDirectory() as raw:
            cursor = Path(raw) / "cursor"
            deep = cursor / "l1" / "l2" / "l3" / "l4"
            deep.mkdir(parents=True)
            (cursor / "l1" / "l2" / "l3" / "seen.mdc").write_text(
                "---\ndescription: seen\nalwaysApply: false\n---\nSEEN_PHRASE\n",
                encoding="utf-8",
            )
            (deep / "hidden.mdc").write_text(
                "---\ndescription: hidden\nalwaysApply: false\n---\nHIDDEN_PHRASE\n",
                encoding="utf-8",
            )
            report = build_report(scan_all({"cursor": cursor}))
            text = _render_check(report)
            blob = json.dumps(report, ensure_ascii=False)
            self.assertIn("未完整扫描", text)
            self.assertNotIn("HIDDEN_PHRASE", text)
            self.assertNotIn("HIDDEN_PHRASE", blob)
            self.assertTrue(any("l4" in item["path"] and "未完整扫描" in item["reason"] for item in report["incomplete"]))

    def test_unreadable_directory_is_listed(self):
        if os.geteuid() == 0:
            self.skipTest("root ignores file mode")
        with tempfile.TemporaryDirectory() as raw:
            cursor = Path(raw) / "cursor"
            blocked = cursor / "blocked"
            blocked.mkdir(parents=True)
            (cursor / "ok.mdc").write_text(
                "---\ndescription: ok\nalwaysApply: true\n---\nok\n",
                encoding="utf-8",
            )
            blocked.chmod(0)
            try:
                report = build_report(scan_all({"cursor": cursor}))
            finally:
                blocked.chmod(0o755)
        self.assertTrue(
            any("无法读取" in item["reason"] and "blocked" in item["path"] for item in report["incomplete"])
        )
        self.assertIn("未完整扫描", _render_check(report))


if __name__ == "__main__":
    unittest.main()
