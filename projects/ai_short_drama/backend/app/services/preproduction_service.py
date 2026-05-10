from __future__ import annotations

from projects.ai_short_drama.backend.app.domain.models import (
    CharacterBible,
    CharacterDirection,
    DirectorNotebook,
    QualityCheckItem,
    QualityCheckReport,
    SceneBeat,
    SceneBeatSheet,
    ShortDramaPlan,
    ShotDirectionCard,
    StoryBible,
)


class StoryBibleService:
    """把高层故事约束整理成可检查的故事圣经。"""

    def build(self, plan: ShortDramaPlan) -> StoryBible:
        roles = [role.name for role in plan.roles]
        must_have = [shot.summary for shot in plan.shots[:3]]
        return StoryBible(
            title=plan.project_title,
            core_theme=plan.logline,
            emotional_hook=plan.episode_summary,
            world_rules=[
                "所有角色行为必须服从当前集设定，不可无因跳变",
                "视觉风格必须围绕同一类型气质，不允许镜头间审美断裂",
                "每个镜头都要推进情节、情绪或信息中的至少一项",
            ],
            style_keywords=[plan.visual_style, "高信息密度", "强情绪推进"],
            forbidden_cliches=[
                "无原因的煽情慢镜头",
                "与角色设定冲突的突然口号式台词",
                "只靠旁白解释剧情",
            ],
            target_audience="喜欢高节奏反转和强视觉钩子的短剧观众",
            must_have_moments=must_have + ([f"核心角色：{'、'.join(roles)}"] if roles else []),
        )


class CharacterBibleService:
    """把角色卡扩展成更适合导演查看的角色手册。"""

    def build(self, plan: ShortDramaPlan) -> CharacterBible:
        characters: list[CharacterDirection] = []
        for role in plan.roles:
            characters.append(
                CharacterDirection(
                    name=role.name,
                    dramatic_need=role.relationship or "推动主线",
                    fear_or_wound=role.personality,
                    arc_start=f"{role.name} 初始状态：{role.personality}",
                    arc_end_hint=f"{role.name} 后续应围绕主线发生明显变化",
                    body_language=f"{role.name} 的默认身体状态应与外形和性格一致",
                    speech_style=role.voice_style,
                    visual_anchor=role.appearance,
                    performance_notes=[
                        "表演不要平均用力，要把情绪集中在关键动作点上",
                        "角色的每次出场都要延续同一套身体和眼神逻辑",
                    ],
                )
            )
        return CharacterBible(characters=characters)


class SceneBeatService:
    """按镜头近似拆出场景节拍，便于导演和编剧回看。"""

    def build(self, plan: ShortDramaPlan) -> SceneBeatSheet:
        scenes: list[SceneBeat] = []
        for index, shot in enumerate(plan.shots, start=1):
            scenes.append(
                SceneBeat(
                    scene_no=index,
                    location=shot.title,
                    dramatic_goal=shot.summary,
                    conflict="角色目标与未知阻力的碰撞",
                    emotional_turn=f"从镜头起始状态转向：{shot.summary}",
                    reveal=shot.subtitle_text or "通过动作与画面完成信息揭示",
                    exit_hook=shot.video_prompt,
                )
            )
        return SceneBeatSheet(scenes=scenes)


class DirectorNotebookService:
    """把镜头计划扩展为可执行的导演手册。"""

    def build(self, plan: ShortDramaPlan) -> DirectorNotebook:
        shot_cards: list[ShotDirectionCard] = []
        for shot in plan.shots:
            shot_cards.append(
                ShotDirectionCard(
                    shot_no=shot.shot_no,
                    title=shot.title,
                    story_purpose=shot.summary,
                    framing="主体必须一眼可识别，构图优先服务信息读取速度",
                    camera_angle="优先中近景，必要时补强特写制造冲击",
                    camera_movement="镜头运动只服务情绪推进，避免无意义炫技",
                    lens_feel="电影感但保持短剧节奏，不拖沓",
                    lighting_notes="主视觉风格需在所有镜头间稳定延续",
                    acting_notes=[
                        "动作起点和情绪转折点要对齐镜头节拍",
                        "关键表情给足停顿，确保可被视频模型捕捉",
                    ],
                    prop_notes=[
                        "道具必须和镜头提示词一致，不要出现设定外物件",
                        "连续镜头中的关键道具位置要稳定",
                    ],
                    sound_notes=[
                        "环境声和动作声要提前想好，不要只依赖后期补救",
                        "字幕出现时机要与角色动作点同步",
                    ],
                    continuity_risks=[
                        "人物服装、手部动作、视线方向必须连续",
                        "光线方向与场景情绪不能前后打架",
                    ],
                )
            )
        return DirectorNotebook(
            episode_title=plan.project_title,
            directing_strategy="每个镜头都同时承担情节推进和情绪施压，避免空镜头。",
            pacing_plan=[
                "开场前 3 秒必须有信息钩子",
                "每个镜头结尾都要给下一个镜头留张力",
                "在情绪峰值处才使用最强的运动和声音刺激",
            ],
            visual_motifs=[
                plan.visual_style,
                "重复出现的视觉锚点要服务悬念或情感主题",
            ],
            actor_guidance=[
                "把外放表演留给高潮，其余时间尽量克制",
                "眼神移动顺序要先于身体动作，形成真实反应链",
            ],
            shot_cards=shot_cards,
        )


class QualityCheckService:
    """对导演视角的细节做规则化质检。"""

    def build(self, plan: ShortDramaPlan, notebook: DirectorNotebook) -> QualityCheckReport:
        checks: list[QualityCheckItem] = []

        for shot in plan.shots:
            if not shot.subtitle_text:
                checks.append(
                    QualityCheckItem(
                        item_no=len(checks) + 1,
                        category="subtitle",
                        description=f"镜头 {shot.shot_no} 缺少字幕文案，可能削弱短剧信息密度。",
                        severity="medium",
                        suggestion="至少补一句可强化情绪或信息的字幕。",
                    )
                )

        for card in notebook.shot_cards:
            if not card.sound_notes:
                checks.append(
                    QualityCheckItem(
                        item_no=len(checks) + 1,
                        category="sound",
                        description=f"镜头 {card.shot_no} 缺少声音设计说明。",
                        severity="medium",
                        suggestion="补环境声、动作声或音乐进入点。",
                    )
                )

        summary = "已完成导演级细节检查。" if not checks else f"共发现 {len(checks)} 个需要人工关注的细节点。"
        return QualityCheckReport(summary=summary, checks=checks)
