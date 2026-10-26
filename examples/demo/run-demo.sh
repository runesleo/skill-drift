#!/bin/sh
# Copy the fake tree, show drift, preview a merge, apply it, and check again.
set -eu
DEMO_DIR=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
ROOT=$(CDPATH= cd -- "$DEMO_DIR/../.." && pwd)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/demo"
cp -R "$DEMO_DIR/." "$TMP/demo/"
cd "$TMP/demo"
export PYTHONPATH="$ROOT/src"
export PYTHONDONTWRITEBYTECODE=1

echo "== check =="
code=0
python3 -m skill_drift check --claude claude --cursor cursor --agents agents > "$TMP/human.txt" || code=$?
cat "$TMP/human.txt"
if [ "$code" -ne 1 ]; then
  echo "check exit $code, expected 1" >&2
  exit 1
fi
code=0
python3 -m skill_drift check --claude claude --cursor cursor --agents agents --json > "$TMP/before.json" || code=$?
if [ "$code" -ne 1 ]; then
  echo "json check exit $code, expected 1" >&2
  exit 1
fi

echo "== merge dry-run =="
python3 -m skill_drift merge status-line --source claude --claude claude --cursor cursor --agents agents
if [ -d cursor/.skill-drift-archive ] || [ -L cursor/status-line.mdc ]; then
  echo "dry-run wrote files" >&2
  exit 1
fi

echo "== merge apply =="
python3 -m skill_drift merge status-line --source claude --claude claude --cursor cursor --agents agents --apply

echo "== check again =="
code=0
python3 -m skill_drift check --claude claude --cursor cursor --agents agents || code=$?
if [ "$code" -ne 1 ]; then
  echo "recheck exit $code, expected 1" >&2
  exit 1
fi
code=0
python3 -m skill_drift check --claude claude --cursor cursor --agents agents --json > "$TMP/after.json" || code=$?
if [ "$code" -ne 1 ]; then
  echo "recheck json exit $code, expected 1" >&2
  exit 1
fi
BEFORE="$TMP/before.json" AFTER="$TMP/after.json" python3 -c '
import json, os
before = json.load(open(os.environ["BEFORE"]))
after = json.load(open(os.environ["AFTER"]))

def one(report, kind, name):
    hits = [item for item in report["findings"] if item["kind"] == kind and item["name"] == name]
    if len(hits) != 1:
        raise SystemExit("expected one %s %s, got %s" % (kind, name, len(hits)))
    return hits[0]

ship = one(before, "wording_drift", "ship-note")
if ship["suggested_source"] != "undecided":
    raise SystemExit("ship-note should stay undecided")
if "2026-01-02" not in ship.get("semantic_dates", {}).get("cursor", []):
    raise SystemExit("semantic date missing")
shell = one(before, "wording_drift", "empty-shell")
if shell["suggested_source"] != "cursor":
    raise SystemExit("empty-shell source")
one(before, "broken_symlink", "missing-skill")
one(before, "duplicate", "dup-rule")
one(before, "rule_frontmatter", "no-frontmatter")
mirror = one(before, "agents_mirror", "AGENTS.md")
if mirror["status"] != "ok":
    raise SystemExit("agents mirror")
if before["mtime"] != "ignored":
    raise SystemExit("mtime")
status = one(after, "aligned", "status-line")
if status["actionable"]:
    raise SystemExit("status-line still actionable")
print("demo ok")
'
