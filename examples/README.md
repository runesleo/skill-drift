# Examples

假数据，用来演示漂移。不要把这里的句子当成真实规则。

| 树 | 故意放进去的问题 |
| --- | --- |
| `demo/` | 三方措辞分叉、`TODO` 空壳、正文一致、坏链接、同名两次、缺 frontmatter、`AGENTS.md` 委托行 |
| `agents-hash-drift/` | 两份 `AGENTS.md` 哈希不同，且差异那份没有委托行 |
| `subset/` | 短的一份没有自己的句子，长的一份多一句 |

演示：

```bash
sh examples/demo/run-demo.sh
```
