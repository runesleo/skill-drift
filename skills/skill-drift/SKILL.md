---
name: skill-drift
description: Compare Claude skills, Cursor rules, and a second skills directory for content drift, broken symlinks, and duplicate names. Use when skills and rules disagree, copies may have forked, or the user mentions skill-drift.
---

# skill-drift

Compare the text of same-named skills and rules. File modification time is ignored. A later timestamp can be a fresh copy of an older draft.

## Commands

From the repo root, or after `python3 -m pip install --user .`:

```bash
skill-drift check --claude DIR --cursor DIR --agents DIR
skill-drift check --claude DIR --cursor DIR --agents DIR --json
skill-drift merge NAME --source claude --claude DIR --cursor DIR --agents DIR
skill-drift merge NAME --source cursor --claude DIR --cursor DIR --agents DIR --apply
```

If `skill-drift` is not on `PATH`, use `python3 -m skill_drift` with the same arguments.

`--cursor` is the rules directory full of `.mdc` files. `--claude` and `--agents` are skills directories. Add `--agents-md FILE` once per `AGENTS.md` when those files sit outside the three directories.

## How to read the report

- `aligned`: normalized bodies match. Frontmatter may differ.
- `wording_drift` with `suggested_source: undecided`: each copy has lines the others lack. Ask which side to keep. The user may pass `--source` and then apply. Do not choose that source yourself. Do not pick the side with the newer timestamp, and do not treat a date inside the file as a winner by itself.
- `wording_drift` with a named source: the other copy is a short placeholder, or it adds no lines of its own. Confirm it is the same skill before merging. The same name can be two different skills.
- `broken_symlink`, `duplicate`, `rule_frontmatter`: fix these before treating that name as one source.
- `agents_mirror`: raw hashes of `AGENTS.md`. A copy that contains the line `delegates to canonical AGENTS.md` may differ. Any other hash difference is drift.

## Merge

Default is dry-run. `--apply` moves the replaced file or directory into `.skill-drift-archive/` under that root, then creates a relative symlink to the source. It does not delete. The source file stays in place. Writes stay inside the directories named on the command.

`--source` is `claude` or `cursor`. If the report says the body lives only under `agents`, copy that file into claude or cursor yourself, then merge from that side.

After a symlink, the skill file and the rule file are the same bytes. Put `description` and `alwaysApply` in the source frontmatter so Cursor still loads the rule.

## Demo

```bash
sh examples/demo/run-demo.sh
```

The demo uses fake skills. Do not point it at a real skills directory unless the user asked you to check that directory.
