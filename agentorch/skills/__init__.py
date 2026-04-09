"""Skill package loading and registry utilities.

Skills are task-oriented resource bundles that contribute instructions,
references, scripts, and metadata without becoming execution engines themselves.
"""

from .base import Skill, SkillManifest
from .loader import SkillLoader
from .registry import SkillRegistry

__all__ = ["Skill", "SkillLoader", "SkillManifest", "SkillRegistry"]
