from __future__ import annotations


def extract_plan_steps(text: str) -> list[str]:
    lines = [line.strip(" -\t") for line in text.splitlines() if line.strip()]
    steps = [line for line in lines if line[:1].isdigit() or line.lower().startswith("step")]
    return steps or (lines[:3] or [text.strip() or "Solve the task directly."])


def extract_branches(text: str) -> list[str]:
    if "||" in text:
        return [part.strip() for part in text.split("||") if part.strip()]
    return [line.strip(" -\t") for line in text.splitlines() if line.strip()]
