from __future__ import annotations

from .base import Skill


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        self._skills[skill.manifest.name] = skill

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def select(self, text: str) -> list[Skill]:
        return [skill for skill in self._skills.values() if skill.matches(text)]

    def instructions_for(self, text: str) -> list[str]:
        return [skill.instructions for skill in self.select(text)]
