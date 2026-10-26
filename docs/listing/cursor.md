# Cursor Marketplace 草稿

未提交。提交页：https://cursor.com/marketplace/publish  
官方说明：https://cursor.com/docs/plugins

商店要求插件开源，并用 Git 仓库分发。每次上架和更新都要人工审核。本草稿不建仓库、不提交。

- 名称：Skill Drift
- name：`skill-drift`
- 一句话：Find drifted Claude skills and Cursor rules, then merge them onto one symlink.
- 描述：skill-drift compares the text of same-named Claude skills and Cursor rules. It lists wording differences, broken symlinks, and duplicate names. File modification time is ignored. `merge` prints a symlink plan and writes only with `--apply`, moving the old file aside instead of deleting it. The marketplace copy is free.
- 截图位：`docs/listing/screenshot-placeholder.txt`（提交前换成终端跑 `sh examples/demo/run-demo.sh` 的图，图里不要出现本机用户目录）
- 分类：Developer Tools
- 清单：仓库根的 `.cursor-plugin/plugin.json`，外加 `skills/skill-drift/SKILL.md` 和 `rules/skill-drift.mdc`
- 许可：MIT

不写价格。咨询入口只放在 README 底部。
