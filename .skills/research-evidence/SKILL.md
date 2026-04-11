---
name: research-evidence
description: Use this skill when the task requires evidence-first research, comparing sources, grounding claims with citations, or combining local knowledge with web search.
triggers: research, investigate, compare sources, cite evidence, summarize findings, strongest evidence
allowed_tools: deliberative_retrieve, search_knowledge_assets, open_retrieved_evidence, brave_search, read_file
tags: research, evidence, citations, synthesis
summary: Gather evidence before concluding, compare competing claims, and surface uncertainty clearly.
---
Use this skill for trustworthy research. Prefer local knowledge first, then web search when local coverage is incomplete or outdated.

Workflow:
1. Break the question into sub-questions before retrieving anything.
2. Search local knowledge first with `deliberative_retrieve` or `search_knowledge_assets`.
3. Open the strongest evidence items instead of citing snippets blindly.
4. Use `brave_search` only when local evidence is missing, stale, or insufficiently specific.
5. Compare sources, note uncertainty, and distinguish confirmed facts from inference.
6. End with a synthesis that keeps citations visible and states what remains unknown.

When to use:
- The user asks for research, comparison, or evidence-backed synthesis.
- The task has factual risk or requires citations.
- Local project knowledge should be used before the web.

What good output looks like:
- Evidence grouped by claim.
- Source quality is discussed, not just listed.
- Uncertainty is explicit and not hidden behind confident wording.

Common failure modes:
- Concluding before checking evidence.
- Mixing local notes and web claims without marking provenance.
- Treating one retrieved snippet as sufficient proof.
