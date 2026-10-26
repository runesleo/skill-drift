只读审查；未运行测试或演示脚本。

## 🔴 Blockers

- **归档可越界移动用户文件：** [`merge.py:40`](src/skill_drift/merge.py:40) 的边界检查不解析符号链接；若指定目录里的 `.skill-drift-archive` 指向外部目录，归档会经该链接把文件移出指定目录，违背 [`README.md:106`](README.md:106) 的承诺。
- **扫描可读取指定目录外的内容：** [`scan.py:293`](src/skill_drift/scan.py:293) 和 [`scan.py:307`](src/skill_drift/scan.py:307) 会跟随符号链接读取目标，却不核对目标是否仍在根目录内；发生差异时，报告还会输出独有内容片段（[`compare.py:48`](src/skill_drift/compare.py:48)、[`cli.py:108`](src/skill_drift/cli.py:108)）。
- **Cursor 安装步骤不能保证加载规则或插件：** [`install.md:55`](install.md:55) 只把单个 `.mdc` 链接到 `~/.cursor/rules`，没有安装仓库插件；按 Cursor 当前文档，项目规则位于项目的 `.cursor/rules`，本地插件从 `~/.cursor/plugins/local` 加载，且指向外部仓库的插件链接会被跳过。[规则文档](https://cursor.com/docs/rules) · [插件文档](https://prod.cursor.com/docs/plugins)
- **README 暴露作者机器的文件规模：** [`README.md:126`](README.md:126) 和 [`README.zh.md:130`](README.zh.md:130) 写出作者机器的技能数量与差异状态；这是与工具说明无关的本机目录信息，且仓库内无法复核。

## 🟡 Warnings

- **检查可能静默漏项：** [`scan.py:273`](src/skill_drift/scan.py:273) 截断四层以外的目录， [`scan.py:277`](src/skill_drift/scan.py:277) 遇到无法读取的子目录会直接跳过，因此不完整扫描可能看起来没有差异。
- **应用过程不是原子操作：** [`merge.py:271`](src/skill_drift/merge.py:271) 按顺序执行动作；文件归档成功后若建链接失败（[`merge.py:284`](src/skill_drift/merge.py:284)、[`merge.py:288`](src/skill_drift/merge.py:288)），会留下未完成的合并状态。
- **合并技能目录会一并归档附属文件：** [`merge.py:175`](src/skill_drift/merge.py:175) 会移动整个目标技能目录；其中未出现在选定源目录里的脚本或资源会从活动路径消失，虽然仍在归档中。
- **Cursor frontmatter 检查较浅：** [`scan.py:73`](src/skill_drift/scan.py:73) 只凭闭合分隔符判定 frontmatter 有效，未解析 YAML；格式错误的元数据可能未被报告。
- **给代理的规则与 README 对 `undecided` 的处理相矛盾：** [`README.md:134`](README.md:134) 说用户可自行指定来源，而 [`rules/skill-drift.mdc:8`](rules/skill-drift.mdc:8) 禁止在建议为 `undecided` 时应用合并。
- **Marketplace 材料尚未就绪：** [`docs/listing/cursor.md:3`](docs/listing/cursor.md:3) 和 [`docs/listing/claude.md:3`](docs/listing/claude.md:3) 都标为未提交，截图仍是占位文件（[`screenshot-placeholder.txt:1`](docs/listing/screenshot-placeholder.txt:1)）；若首发包含商店上架，需要补齐。
- **Skill 未说明命令不在 PATH 时的回退方式：** [`skills/skill-drift/SKILL.md:15`](skills/skill-drift/SKILL.md:15) 只调用 `skill-drift`，而 README 承认 `pip --user` 可能未把命令加入 PATH（[`README.md:140`](README.md:140)）。

## 🟢 OK

- **`doctor` 实现只读：** [`doctor.py:36`](src/skill_drift/doctor.py:36) 只检查路径、权限并读取目录项；已有测试会比较运行前后的目录摘要（[`test_skill_drift.py:384`](tests/test_skill_drift.py:384)）。
- **仓库内插件组件齐全：** Claude manifest 与 skill 存在（[`.claude-plugin/plugin.json:1`](.claude-plugin/plugin.json:1)、[`SKILL.md:1`](skills/skill-drift/SKILL.md:1)）；Cursor manifest、rule 与 skill 也存在（[`.cursor-plugin/plugin.json:1`](.cursor-plugin/plugin.json:1)、[`skill-drift.mdc:1`](rules/skill-drift.mdc:1)）。这是单插件仓库，按 Cursor 当前结构说明不需要 marketplace manifest。[Cursor 插件结构参考](https://prod.cursor.com/docs/reference/plugins)
- **正文比较与 README 的 mtime 说明一致：** [`compare.py:3`](src/skill_drift/compare.py:3) 明确将修改时间排除在比较之外。

归档检查：可以归档（只读审查结论已交付）

## 修复记录

对照上面的条目。测试：`python3 -m unittest tests.test_skill_drift`，40 项通过。

### 🔴

1. **归档越界。** `merge.py` 的边界检查会先解析已存在的祖先符号链接。`.skill-drift-archive` 本身是符号链接，或者归档路径解析后不在该根目录内，就拒绝，报错里点明 `.skill-drift-archive`。计划阶段就停，不会先把文件移出去。测试：归档目录指向外部、指向根目录内部、以及归档路径中某一层指向外部，三种都拒绝，外部目录内容不变。
2. **扫描越界。** 跟随符号链接读到的目标，若不在本次点名的任一根目录内，就不读正文。报告只给一条 `skipped_link`，原因是「链接指向指定目录之外，已跳过」，不含该文件的内容片段。指向另一个已点名根目录的链接仍会读取。测试覆盖了规则文件、技能目录，以及指向已点名根目录的链接。
3. **Cursor 安装。** 按当前文档改写了 `install.md` 和两份 README 的 Cursor 部分：规则复制到项目 `.cursor/rules`；插件按真实目录复制到 `~/.cursor/plugins/local/skill-drift`（`.cursor-plugin`、`rules`、`skills`），不用指向仓库外的符号链接。写明要重新加载窗口，并在 Customize 里看到组件之后才算装上。`doctor` 对 `~/.cursor/rules` 的检查只说明目录能不能列出。
4. **本机技能数量。** 两份 README 的 Verified 去掉了作者机器上的技能数量和漂移状态，只保留可复现的测试数和 `examples/demo` 的 `demo ok`。

### 🟡

- **未完整扫描。** 目录深过 4 层，或子目录无法读取时，报告列出「未完整扫描」及原因。不再静默跳过。
- **`undecided`。** `rules/skill-drift.mdc`、两份 README、`SKILL.md`、`docs/single-source.md` 改为同一说法：用户可以显式传 `--source` 再合并；代理不得自己选来源。
- **命令不在 PATH。** `SKILL.md` 写了改用 `python3 -m skill_drift`。
- **未改。** 合并不是原子操作、合并技能目录会带走附属文件、Cursor frontmatter 不解析 YAML、商店材料未齐。这四条本次不改。
