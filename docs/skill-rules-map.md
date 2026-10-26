# skill 与 rule 怎么对上名字

| 你传入的目录 | 认作什么 | 名字从哪来 |
| --- | --- | --- |
| `--claude` | 含 `SKILL.md` 的目录 | frontmatter 的 `name`，否则目录名 |
| `--cursor` | `*.mdc` | frontmatter 的 `name`，否则文件名（去掉 `.mdc`） |
| `--agents` | 含 `SKILL.md` 的目录 | 与 Claude 相同 |
| 目录顶层的 `AGENTS.md`，或 `--agents-md` | 原始字节 | 固定比 `AGENTS.md` |

名字会先变成小写，空格和下划线换成连字符。正文比对会去掉 frontmatter，再压缩空白。`AGENTS.md` 比的是整个文件的 SHA-256。某一份单独包含这一行时，可以和其余副本不同：

```text
delegates to canonical AGENTS.md
```

合并时：

- 源是 Claude skill 目录：agents 里的同名目录改成指向它的符号链接；Cursor 的 `.mdc` 指向该目录里的 `SKILL.md`。
- 源是 Cursor 的 `.mdc`：另一侧的 `SKILL.md` 指向这个文件。

# Name matching

A Claude skill directory, a Cursor `.mdc` file, and an agents skill directory match when the normalized name is the same. Body comparison strips frontmatter. `AGENTS.md` uses the raw file hash, with one allowed delegate line.
