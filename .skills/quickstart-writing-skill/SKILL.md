---
name: quickstart-writing-skill
description: Quickstart notebook demo skill for structured short writing tasks.
triggers:
  - write
  - summary
  - rewrite
  - notebook demo
allowed-tools:
  - load_skill_resource
summary: 生成结构化短文时，先给结论，再给要点，保持简洁。
---
# quickstart-writing-skill

适用场景：

- 需要把一个主题整理成短说明、短摘要、课堂演示文案
- 希望输出结构稳定，不要散文化长篇回答

执行要求：

1. 先输出一句结论。
2. 再输出 2 到 4 条要点。
3. 每条要点控制在一句话内。
4. 不要编造未给出的事实。

本次用户补充要求：

$ARGUMENTS
