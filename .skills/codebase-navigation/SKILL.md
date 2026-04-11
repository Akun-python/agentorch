---
name: codebase-navigation
description: Use this skill when the task is to understand an unfamiliar repository, locate relevant files, trace execution paths, or identify where a feature is implemented before making changes.
triggers: understand codebase, locate file, trace flow, find implementation, inspect repository, where is this defined
allowed_tools: list_directory, find_files, search_text, read_file, get_file_info
tags: codebase, navigation, architecture, tracing
summary: Quickly map a repository before editing so later changes are grounded in the actual implementation.
---
Use this skill to explore before editing. The goal is to reduce wrong assumptions and build a small, accurate map of the relevant code.

Workflow:
1. Start with `find_files` or `search_text` to identify the narrowest file set related to the user request.
2. Use `read_file` on entrypoints, registries, configuration files, and tests before reading deep implementation files.
3. Trace data flow in this order when possible: public API -> runtime wiring -> implementation -> tests.
4. Keep a short inventory of the files that matter and the responsibility of each one.
5. Stop broad exploration once you can answer:
   - where the feature starts
   - where state changes
   - where outputs are produced
   - which tests should guard the behavior

When to use:
- The user asks "where is this implemented" or "how does this work".
- The codebase is large or unfamiliar.
- A bug fix requires finding the true source of behavior rather than patching symptoms.

What good output looks like:
- Identify the exact files and functions involved.
- Summarize the execution path in plain language.
- Call out configuration or runtime indirection that could hide behavior.

Common failure modes:
- Reading too many files too early instead of narrowing first.
- Missing registries, factory methods, or presets that wire the feature together.
- Ignoring tests that reveal intended behavior.
