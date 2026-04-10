---
name: git-review
description: Use this skill when the task is to review local changes, summarize a diff, assess regression risk, or inspect recent commits before merging or debugging.
triggers: review diff, inspect changes, summarize commit, regression risk, what changed, code review
allowed_tools: git_status, git_diff_summary, git_recent_commits, read_file, search_text
tags: git, review, diff, regression
summary: Review local changes with a bug-first mindset and connect diffs to likely behavior changes.
---
Use this skill to analyze repository changes before trusting them. Prioritize bugs, regressions, and testing gaps over style comments.

Workflow:
1. Start with `git_status` to understand scope and whether the worktree is dirty.
2. Use `git_diff_summary` to find the highest-risk files and categories of change.
3. Read only the most relevant changed files instead of everything.
4. Check whether configuration, runtime wiring, or public interfaces changed.
5. Report findings ordered by severity with file references when possible.

When to use:
- The user asks for a review.
- A new error appeared after recent code changes.
- You need a quick summary of active work in the branch.

What good output looks like:
- Findings first, summary second.
- Clear discussion of behavior change and test coverage gaps.
- Explicit note when no substantial findings are present.

Common failure modes:
- Turning review into a style pass.
- Missing hidden behavior changes in config or initialization code.
- Not distinguishing user changes from unrelated dirty files.
