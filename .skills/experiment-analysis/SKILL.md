---
name: experiment-analysis
description: Use this skill when the task is to analyze experiment outputs, runtime logs, benchmark results, or iterative agent traces and extract the most important signals.
triggers: analyze logs, inspect traces, benchmark result, experiment output, runtime events, telemetry
allowed_tools: read_file, search_text, find_files, python_interpreter, git_recent_commits
tags: experiments, logs, analysis, telemetry
summary: Turn logs and experiment artifacts into a concise explanation of what happened, why it happened, and what to try next.
---
Use this skill to analyze runs instead of just restating logs. Focus on stage transitions, resource usage, failure boundaries, and repeatable signals.

Workflow:
1. Identify the artifact type: raw log, JSON events, benchmark output, or generated report.
2. Extract the smallest set of fields that explain the run: stage, status, step index, token budget, tool calls, and terminal error.
3. Separate normal milestones from the first abnormal event.
4. Look for compounding factors such as large prompts, repeated retries, missing backoff, or configuration conflicts.
5. Summarize the run as:
   - what succeeded
   - where it diverged
   - the highest-confidence explanation
   - the next experiment to run

When to use:
- The user pastes verbose logs or event traces.
- A multi-step agent run needs postmortem analysis.
- You need to compare two runs or isolate one unstable stage.

What good output looks like:
- A short narrative of the run.
- Concrete signals instead of generic speculation.
- One or two focused next steps, not a long wish list.

Common failure modes:
- Repeating the full log without analysis.
- Missing the first abnormal event because later errors are louder.
- Ignoring token/context growth in long-running agent traces.
