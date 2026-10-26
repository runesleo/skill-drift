# 单一来源操作卡

1. 跑 `skill-drift check`，传入 Claude skills 目录、Cursor rules 目录、另一份 skills 目录。
2. 先处理 `broken_symlink` 和 `duplicate`。链接断了或同名有两份时，不要合并这个名字。
3. 看 `suggested_source`。
   - `undecided`：每份都有别人没有的句子。你可以显式传入 `--source claude` 或 `--source cursor` 再合并。代理不得替你选来源。文件里的日期只是对照，不自动胜出。文件修改时间不参与。
   - 一个具体目录：另一份是 `TODO` 这类短占位，或没有多出来的句子。先确认它们是同一个 skill，再合并。同名可以是两件不同的事。
4. `skill-drift merge NAME --source claude` 先看计划。确认后加 `--apply`。
5. 被替换的文件或目录会移到该根目录的 `.skill-drift-archive/`。需要退回时，把归档移回去，删掉新链接。
6. 源如果是 skill 目录，Cursor 的 `.mdc` 会链接到里面的 `SKILL.md`。源文件的 frontmatter 要同时能被 Cursor 加载：至少有 `description` 和 `alwaysApply`。
7. `--source` 只有 `claude` 和 `cursor`。正文只在 agents 那一侧时，先把那份拷进 claude 或 cursor，再合并。

# Single source

Run `check`. Clear broken links and duplicate names first. If the suggested source is `undecided`, you may pass `--source` and then merge. An agent must not choose the source. Dates in the file and file modification times do not choose for you. `merge` is a dry-run until `--apply`. Replaced files move to `.skill-drift-archive/`. Put `description` and `alwaysApply` on the source file so the linked `.mdc` still loads.
