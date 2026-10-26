# skill-drift

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**English** · [中文](README.zh.md)

> Set up skill-drift on this computer by following the official instructions at https://github.com/runesleo/skill-drift/blob/main/install.md.

> 按照 https://github.com/runesleo/skill-drift/blob/main/install.md 的官方说明，在这台电脑上安装 skill-drift。

Compare Claude skills, Cursor rules, and a second skills directory, then point the copies at one file after you confirm.

## What you get

- A read-only report of same-named files whose body text differs
- Separate findings for a broken symlink, a duplicate name, and a Cursor rule Cursor will not load
- A merge plan that writes nothing until you pass `--apply`
- Replaced files moved into `.skill-drift-archive/` inside that directory
- `doctor`, a read-only check of your Python version and the three usual directories

## How it works

The comparison uses the body text. A newer modification time does not choose a winner.

`examples/demo` is a fake tree. `sh examples/demo/run-demo.sh` copies it, runs `check`, prints a merge plan for `status-line`, applies that plan, and runs `check` again.

Shortened from one demo run. The script prints every finding.

```text
skill-drift check: 6 actionable, 1 aligned
comparison: normalized body text; file modification time is ignored

wording_drift  status-line
  claude  real  2f770cea0f96  claude/status-line/SKILL.md
  cursor  real  fa599228ec37  cursor/status-line.mdc
  agents  real  08f6ae7a81f9  agents/status-line/SKILL.md
  suggested source: undecided
  each copy has lines the others lack, or the same lines in a different order; pick --source yourself. Dates in the text are evidence only
  unique claude: Write one status sentence: what changed, and that you checked it.
  unique cursor: Write one status sentence: what changed, plus the folder you edited.
  unique agents: Write one status sentence: what changed, plus who asked for it.

wording_drift  ship-note
  suggested source: undecided

broken_symlink  missing-skill
  claude  broken  -  claude/missing-skill -> ../nowhere/missing-skill

duplicate  dup-rule
  cursor  real  2019a4a8b3da  cursor/dup-rule.mdc
  cursor  real  efa6ed307b3b  cursor/extra/dup-rule.mdc

rule_frontmatter  no-frontmatter
  cursor  real  c8b80901a032  cursor/no-frontmatter.mdc

aligned: aligned-note
```

`status-line` is undecided because each copy has a line the others lack. The demo then runs a dry-run merge. The archive directory name below is the UTC time of that run, written here as `<timestamp>`.

```text
skill-drift merge status-line --source claude (dry-run)
canonical: claude/status-line/SKILL.md
  keep claude  claude/status-line/SKILL.md  source
  archive cursor  cursor/status-line.mdc -> cursor/.skill-drift-archive/<timestamp>/status-line.mdc
  symlink cursor  cursor/status-line.mdc -> ../claude/status-line/SKILL.md
  archive agents  agents/status-line -> agents/.skill-drift-archive/<timestamp>/status-line
  symlink agents  agents/status-line -> ../claude/status-line
dry-run: no files written
```

After `--apply`, the next check prints `aligned: aligned-note, status-line`. `ship-note` stays `undecided`. The script ends with `demo ok`.

## Setup

```bash
git clone https://github.com/runesleo/skill-drift.git
cd skill-drift
python3 -m pip install --user .
```

If the shell cannot find `skill-drift`, run `python3 -m skill_drift`.

Before that install, from the clone:

```bash
PYTHONPATH=src python3 -m skill_drift.doctor
```

Any AI coding agent: follow [install.md](install.md). Claude Code, Codex, and Cursor use this same CLI.

### Cursor

Cursor loads a project rule from that project's `.cursor/rules/*.mdc`. It loads a local plugin from `~/.cursor/plugins/local/<name>` only when that folder is a real directory. A symlink there to this clone is skipped. Copy the rule into the project, and copy `.cursor-plugin`, `rules`, and `skills` into `~/.cursor/plugins/local/skill-drift`. Then reload the window and check Customize. The steps are in [install.md](install.md). `doctor` only checks that `~/.cursor/rules` can be listed. That check does not install the rule.

## Requirements

- Python 3.9 or newer
- A filesystem that can create a symlink, for `merge --apply`
- No API key

**Privacy.** The tool reads files on this computer. It does not open a network connection and it does not upload file contents.

`doctor` checks the Python version. With no directory flags it also checks that these directories exist and can be listed:

- `~/.claude/skills`
- `~/.cursor/rules`
- `~/.agents/skills`

`check` reads the skill and rule text in the directories you pass. `merge` without `--apply` writes nothing. `merge --apply` moves and links files only inside those directories.

## Quick start

```bash
sh examples/demo/run-demo.sh
skill-drift doctor
skill-drift check --claude ~/.claude/skills --cursor ~/.cursor/rules --agents ~/.agents/skills
```

`--cursor` is the directory of `.mdc` files you want to compare. For a project, pass that project's `.cursor/rules`.

`check` exits 1 when the report has something to resolve. Exit 2 means the command was wrong.

`merge` prints a plan. Pass `--apply` after you agree with `--source`. Pass `--add-missing` when a directory has no copy yet and you want a link there.

## Verified

| Case | Environment | Result |
|------|-------------|--------|
| 40 tests | macOS | `python3 -m unittest tests.test_skill_drift` |
| Demo | macOS | `sh examples/demo/run-demo.sh` prints `demo ok` |

Doctor tests are in the same file. On `examples/demo`, `doctor` reports `OK` for Python and for the three directories in that tree.

## Known limitations (v0.1.0)

- `--source` accepts `claude` or `cursor`. Copy a file into one of those directories first when the copy you want lives only under `--agents`.
- The same name can be two different skills. Read a short placeholder before you apply the suggestion.
- `undecided` means each side has lines the others lack. You may pass `--source` and then merge. An agent must not choose the source.
- After a merge, the skill and the rule are the same bytes. The source frontmatter needs `description` and `alwaysApply`, or Cursor will not load the rule.
- A duplicate name or a broken symlink has to be fixed before that name can be a source.
- Directories that never had this skill are left alone unless you pass `--add-missing`.
- Archive files stay in `.skill-drift-archive/`. The links are relative, so moving one directory alone breaks them.
- If `.skill-drift-archive` is a symlink, or the archive path resolves outside that directory, `merge` stops before it moves a file.
- `doctor` does not create missing directories and does not read the files inside them.
- `pip install --user` can leave `skill-drift` off `PATH`. `python3 -m skill_drift` still runs it.

## Roadmap

**Sources**

- [ ] Accept `agents` as `--source`

**Large trees**

- [ ] A name-only summary when one directory holds many skills

## About the author

*Leo ([@runes_leo](https://x.com/runes_leo)) — AI × Crypto independent builder. Trading on [Polymarket](https://polymarket.com/?via=runes-leo&r=runesleo&utm_source=github&utm_content=skill-drift), building data and content pipelines with Claude Code and Codex.*

*[leolabs.me](https://leolabs.me) — writing · community · open-source tools · indie projects · all platforms.*

*[X Subscription](https://x.com/runes_leo/creator-subscriptions/subscribe) — paid content weekly, or just buy me a coffee 😁*

*Learn in public, Build in public.*

## License

MIT. See [LICENSE](LICENSE).

Need a person to fold a whole ruleset into one source? Contact [LeoLabs](https://leolabs.me) (X [@runes_leo](https://x.com/runes_leo)).
