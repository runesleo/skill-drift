# Claude 插件目录草稿

未提交。提交入口：https://claude.ai/directory/manage  
官方说明：https://www.claude.com/docs/plugins/submit  
插件结构：https://code.claude.com/docs/en/plugins-reference

目录上线前仓库要公开，并通过校验、安全扫描和审核。本草稿不建仓库、不提交。

- 名称：Skill Drift
- name：`skill-drift`
- 一句话：Find drifted Claude skills and Cursor rules, then merge them onto one symlink.
- 描述：The plugin adds a skill that tells Claude Code to run `skill-drift check` and a dry-run `skill-drift merge`. The check compares skill and rule text, broken symlinks, and duplicate names. It does not use file modification time. Install the CLI with `python3 -m pip install --user .` from this repo. The directory copy is free.
- 截图位：`docs/listing/screenshot-placeholder.txt`（提交前换成演示终端图，图里不要出现本机用户目录）
- 分类：Developer tools（以提交表单上的选项为准）
- 清单：仓库根的 `.claude-plugin/plugin.json` 和 `skills/skill-drift/SKILL.md`。不要加 `bin/`，claude.ai 不安装带 `bin/` 的插件。
- 许可：MIT
- 本地校验：在装了 Claude Code 的机器上跑 `claude plugin validate` 指向本仓库根目录。

不写价格。咨询入口只放在 README 底部。
