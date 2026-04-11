from __future__ import annotations

from .base import Skill, SkillRoute, SkillRoutingConfig


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
        return [route.content for route in self.route_for(text, config="full")]

    def route_for(self, text: str, *, config: SkillRoutingConfig | str | dict[str, object] | None = None, available_tools: list[str] | None = None) -> list[SkillRoute]:
        resolved = SkillRoutingConfig.from_any(config)
        if resolved.mode == "off":
            return []
        available = set(available_tools or [])
        routes: list[SkillRoute] = []
        for skill in self._skills.values():
            matched = skill.matched_triggers(text)
            if not matched:
                continue
            overlap = len(available.intersection(skill.manifest.allowed_tools))
            score = float(len(matched) * 10 + overlap)
            if resolved.disclosure_level == "full" or resolved.mode == "full":
                level = "full"
            elif resolved.disclosure_level == "summary" or resolved.mode == "summary":
                level = "summary"
            elif resolved.disclosure_level == "descriptor" or resolved.mode == "descriptor":
                level = "descriptor"
            else:
                level = "summary"
            routes.append(
                SkillRoute(
                    skill_name=skill.manifest.name,
                    score=score,
                    trigger_matches=matched,
                    disclosure_level=level,
                    content=skill.disclosure(level),
                    allowed_tools=list(skill.manifest.allowed_tools) if resolved.include_allowed_tools else [],
                    descriptor=skill.descriptor(),
                    rationale=f"matched triggers: {', '.join(matched)}",
                )
            )
        routes.sort(key=lambda item: (-item.score, item.skill_name))
        return routes[: resolved.max_active]
