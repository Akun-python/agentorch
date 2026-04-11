---
name: code-editing
description: Use this skill when the task requires implementing or modifying code, especially after the relevant files and execution path are already known.
triggers: implement change, modify code, add feature, patch logic, edit file, update implementation
allowed_tools: read_file, write_file, append_file, replace_in_file, search_text, find_files
tags: coding, implementation, patching, refactor
summary: Make focused code changes with minimal surface area and preserve surrounding behavior.
---
Use this skill after the relevant code path is known. The goal is to implement a focused change with clear intent and low regression risk.

Workflow:
1. Re-read the exact target file and nearby logic before editing.
2. Prefer the smallest change that satisfies the requirement.
3. Preserve established naming, error handling, and data shapes unless the user asked for a larger refactor.
4. If the change affects runtime wiring or config, update the corresponding example or test when practical.
5. After editing, verify syntax and obvious import issues before handing back the result.

When to use:
- The user asks for a code change rather than just explanation.
- A narrow patch or incremental refactor is needed.
- You already know which modules own the behavior.

What good output looks like:
- Minimal but complete edits.
- No unrelated cleanup mixed into the patch.
- Clear alignment with existing project patterns.

Common failure modes:
- Editing before understanding ownership of the file.
- Making broad stylistic rewrites unrelated to the request.
- Forgetting to update adjacent config, imports, or examples.
