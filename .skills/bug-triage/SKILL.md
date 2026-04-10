---
name: bug-triage
description: Use this skill when the task is to diagnose an error, traceback, failing behavior, or regression and isolate the most likely root cause before applying a fix.
triggers: traceback, error, failing, regression, bug, exception, why is this broken
allowed_tools: read_file, search_text, find_files, run_command, git_status, git_diff_summary, git_recent_commits
tags: debugging, triage, root-cause, regression
summary: Diagnose failures by separating symptom, trigger path, and root cause before changing code.
---
Use this skill to debug methodically. The goal is to explain why the system failed and identify the smallest high-confidence fix.

Workflow:
1. Copy the exact error message, exception type, and failing location.
2. Trace the stack upward to find the first project-owned frame that matters.
3. Inspect recent edits, config, and runtime wiring that could change the behavior.
4. Form one primary hypothesis and one fallback hypothesis instead of many vague guesses.
5. Confirm the hypothesis using code paths, state assumptions, or a small reproducible command.
6. Only then propose or apply the fix.

When to use:
- The user provides a traceback or failing command output.
- A feature used to work and now fails.
- A multi-step system is failing and the first visible error may not be the root cause.

What good output looks like:
- Symptom, cause, and fix are clearly separated.
- Root cause is tied to file/function boundaries.
- Environmental or API-side causes are explicitly called out when code is not the primary issue.

Common failure modes:
- Treating the last stack frame as the root cause.
- Fixing the symptom without checking configuration or upstream inputs.
- Ignoring recent changes or external rate-limit / API behavior.
