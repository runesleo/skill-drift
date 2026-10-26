# skill-drift

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

English: [README.md](./README.md)

> 按照 https://github.com/runesleo/skill-drift/blob/main/install.md 的官方说明，在这台电脑上安装 skill-drift。

> Set up skill-drift on this computer by following the official instructions at https://github.com/runesleo/skill-drift/blob/main/install.md.

你在 Claude 里改过一份 skill，Cursor 里的同名 rule 还是旧句子。文件时间只能说明谁刚被保存过，不能说明你要留哪一版。skill-drift 按正文找出这种分叉，你确认来源之后，再把副本收成一个符号链接。

## 你能得到什么

- 一份只读清单：同名文件里，哪些正文已经对不上
- 坏掉的符号链接、同一个名字出现两次、Cursor 不会加载的 `.mdc`，单独标出来
- 合并先给计划。加上 `--apply` 才移动文件、写相对路径的链接
- 被换掉的文件进该目录下的 `.skill-drift-archive/`，不直接删除
- `doctor` 只检查 Python 版本，以及三个常见目录在不在、能不能列出来

## 怎么工作

仓库里的 `examples/demo` 是假数据。运行：

```bash
sh examples/demo/run-demo.sh
```

脚本会复制这棵树，先检查，再预览把 `status-line` 收成 Claude 那一份，然后真正写入，最后再检查一次。

演示里 `status-line` 三边各有一句别人没有的话，所以建议来源是 `undecided`。脚本指定 `--source claude`。`ship-note` 三边也都有自己的句子，写入之后它仍然分叉，工具不替你选。

下面是这次演示的真实输出，做了删节，脚本会把每条发现都打出来。归档目录名里的时间写成了 `<timestamp>`。

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

应用之后，对齐的名字变成 `aligned-note, status-line`。脚本最后一行是 `demo ok`。

## 安装

```bash
git clone https://github.com/runesleo/skill-drift.git
cd skill-drift
python3 -m pip install --user .
```

终端找不到 `skill-drift` 时，用 `python3 -m skill_drift`。

还没安装时，在克隆下来的目录里先跑：

```bash
PYTHONPATH=src python3 -m skill_drift.doctor
```

Claude Code、Codex、Cursor 都用这同一个命令行。给 AI 代理的安装步骤在 [install.md](install.md)。

### Cursor

项目规则放在该项目的 `.cursor/rules/*.mdc`。本地插件只从 `~/.cursor/plugins/local/<name>` 加载，而且必须是真实目录。指向这份克隆的符号链接会被跳过。把规则文件复制进项目，再把 `.cursor-plugin`、`rules`、`skills` 复制到 `~/.cursor/plugins/local/skill-drift`。然后重新加载窗口，到 Customize 里确认已经出现。步骤写在 [install.md](install.md)。`doctor` 只检查 `~/.cursor/rules` 能不能列出内容，这一步并不安装规则。

## 环境要求

- Python 3.9 或更高
- `merge --apply` 需要文件系统能创建符号链接
- 不需要 API key

**隐私。** 它只读这台电脑上的文件，不联网，也不上传文件内容。

`doctor` 看 Python 版本。不传目录参数时，还看这三个目录在不在、能不能列出内容：

- `~/.claude/skills`
- `~/.cursor/rules`
- `~/.agents/skills`

`check` 会读你在参数里点名的那些目录里的 skill 和 rule 正文。不加 `--apply` 的 `merge` 不写文件。`--apply` 只改你点名的目录，被替换的文件留在该目录的归档夹里。

## 快速开始

```bash
sh examples/demo/run-demo.sh
skill-drift doctor
skill-drift check --claude ~/.claude/skills --cursor ~/.cursor/rules --agents ~/.agents/skills
```

`--cursor` 是你要比较的 `.mdc` 目录。项目规则就传该项目的 `.cursor/rules`。

有需要处理的差异时，`check` 的退出码是 1。退出码 2 表示命令本身不对。

`merge` 默认只打印计划。你认可 `--source` 之后再加 `--apply`。某个目录里本来没有这份技能、你又想补上链接时，加 `--add-missing`。

## 已验证

| 场景 | 环境 | 结果 |
|------|------|------|
| 40 项测试 | macOS | `python3 -m unittest tests.test_skill_drift` |
| 演示 | macOS | `sh examples/demo/run-demo.sh` 最后打印 `demo ok` |

`doctor` 的测试在同一个文件里。对 `examples/demo` 跑 `doctor`，Python 和那三个目录都会是 `OK`。

## 已知限制（v0.1.0）

- `--source` 只能是 `claude` 或 `cursor`。要留的那份如果只在 `--agents` 里，先抄到这两边的其中一个再合并。
- 同名可能是两个不同的技能。报告建议用完整的那份时，先看一眼短的那份是不是空壳。
- 报告写 `undecided` 时，每一边都有别人没有的句子。你可以显式传入 `--source` 再合并。代理不得替你选来源。
- 合并之后 skill 和 rule 是同一份字节。源文件的 frontmatter 里要有 `description` 和 `alwaysApply`，Cursor 才会继续加载这条 rule。
- 同一个目录里有两份同名文件，或者链接已经断了，这个名字就不能当来源。
- 某个目录里从来没有这份技能时，工具不会顺手新建，除非你加 `--add-missing`。
- 归档一直留在 `.skill-drift-archive/`。链接是相对路径，只搬走其中一个目录，链接会断。
- `.skill-drift-archive` 如果本身是符号链接，或者归档路径解析后跑到该目录外面，合并会停住，一个文件都不挪。
- `doctor` 不创建缺失目录，也不读目录里面的文件内容。
- `pip install --user` 之后，`skill-drift` 可能不在 `PATH` 里。这时用 `python3 -m skill_drift`。

## 路线图

**来源**

- [ ] `--source` 可以指定第二份 skills 目录

**大目录**

- [ ] 技能很多时，先输出只有名字的摘要

## 关于作者

*Leo（[@runes_leo](https://x.com/runes_leo)）— AI × Crypto 独立构建者。在 [Polymarket](https://polymarket.com/?via=runes-leo&r=runesleo&utm_source=github&utm_content=skill-drift) 做量化，用 Claude Code 和 Codex 搭数据与内容管线。*

*[leolabs.me](https://leolabs.me) — 写作 · 社群 · 开源工具 · 独立项目*

*[X 订阅](https://x.com/runes_leo/creator-subscriptions/subscribe) — 付费内容周刊*

*Learn in public, Build in public.*

## License

MIT。见 [LICENSE](LICENSE)。

想让人把整套规则收成一份，可以联系 [LeoLabs](https://leolabs.me)（X [@runes_leo](https://x.com/runes_leo)）。
