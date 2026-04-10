"""Skill package loading and registry utilities.

Skills are task-oriented resource bundles that contribute instructions,
references, scripts, and metadata without becoming execution engines themselves.
"""

from .base import Skill, SkillDescriptor, SkillManifest, SkillRoute, SkillRoutingConfig
from .loader import SkillLoader
from .registry import SkillRegistry

__all__ = ["Skill", "SkillDescriptor", "SkillLoader", "SkillManifest", "SkillRoute", "SkillRoutingConfig", "SkillRegistry"]
