from __future__ import annotations

from projects.ai_short_drama.backend.app.domain.models import (
    AssemblyPlan,
    CameraAxisState,
    CharacterContinuityState,
    DramaProjectRequest,
    LightingState,
    PropContinuityState,
    RoleCard,
    ShortDramaPlan,
    ShotPlan,
    TransitionPlan,
)


class PlaceholderPlanningService:
    """生成本地演练用的确定性剧本规划，避免触发真实大模型。"""

    def build_story_plan(self, request: DramaProjectRequest) -> ShortDramaPlan:
        roles = self._build_roles(request)
        shots = self._build_shots(request, roles)
        return ShortDramaPlan(
            project_title=request.project_name,
            logline=request.premise,
            visual_style=request.style,
            episode_summary=f"{request.episode_goal}：用占位素材跑通完整短剧制作流程。",
            roles=roles,
            shots=shots,
        )

    def build_assembly_plan(self, plan: ShortDramaPlan) -> AssemblyPlan:
        transitions: list[TransitionPlan] = []
        for index, shot in enumerate(plan.shots[:-1], start=1):
            next_shot = plan.shots[index]
            transitions.append(
                TransitionPlan(
                    transition_no=index,
                    from_shot_no=shot.shot_no,
                    to_shot_no=next_shot.shot_no,
                    transition_type="match_cut",
                    duration_seconds=0.55,
                    overlap_seconds=0.35,
                    audio_bridge=f"延续镜头{shot.shot_no}尾部低频环境声，跨淡进入镜头{next_shot.shot_no}",
                    visual_prompt=f"用{shot.title}尾帧中的动作方向匹配切入{next_shot.title}首帧",
                    summary=f"{shot.title}到{next_shot.title}的连续性匹配转场",
                )
            )
        return AssemblyPlan(
            episode_title=f"{plan.project_title}-占位全流程样片",
            editing_style="先审稿、后替换真实素材的连续性装配",
            transitions=transitions,
            final_runtime_seconds=float(sum(shot.duration_seconds for shot in plan.shots)),
            export_notes=[
                "本方案用于本地全流程演练，不消耗真实视频生成额度。",
                "占位视频可在工程导入后逐镜替换为真实生成素材。",
            ],
        )

    def _build_roles(self, request: DramaProjectRequest) -> list[RoleCard]:
        templates = [
            ("林夏", "深色风衣、短发、随身旧相机", "冷静敏锐但被失忆阴影压迫", "失忆女记者，推动真相调查"),
            ("周砚", "灰色西装、旧录像带收纳盒", "克制隐忍，知道部分真相", "昔日恋人，既是盟友也是疑点"),
            ("许白", "白衬衫、黑色手套、银色钥匙", "温和外表下隐藏威胁", "潜在反派，制造时间压力"),
            ("陈队", "深蓝夹克、警徽、资料袋", "现实主义、行动果断", "外部压力与调查资源来源"),
        ]
        roles: list[RoleCard] = []
        for index in range(request.role_count):
            name, appearance, personality, relationship = templates[index % len(templates)]
            roles.append(
                RoleCard(
                    name=name if index < len(templates) else f"角色{index + 1}",
                    appearance=appearance,
                    personality=personality,
                    relationship=relationship,
                    avatar_prompt=f"{request.style}角色立绘，{appearance}，表情克制，电影感布光",
                    voice_style="中文短剧对白，情绪压低，关键字清晰",
                )
            )
        return roles

    def _build_shots(self, request: DramaProjectRequest, roles: list[RoleCard]) -> list[ShotPlan]:
        primary_role = roles[0].name if roles else "主角"
        secondary_role = roles[1].name if len(roles) > 1 else primary_role
        shot_templates = [
            (
                "录像带冷开场",
                f"{primary_role}在雨夜剪辑室看到旧录像带里出现自己的死亡画面",
                "剪辑室冷光，桌上旧录像带、监视器雪花屏，主角右手压住桌沿",
                "监视器画面突然定格在三天后的案发现场，主角瞳孔收紧但身体不后退",
                "低机位缓慢推近监视器，雪花屏闪出未来遇害画面，主角呼吸压低",
                "这不是过去，是三天后。",
            ),
            (
                "尾帧接力追问",
                f"{secondary_role}推门进入，旧录像带仍在桌面中央，二人视线第一次对上",
                "上一镜尾帧的监视器冷光延续，门从画面右侧打开，桌面录像带位置不变",
                "二人隔着桌面对峙，录像带在画面中央，主角左手仍靠近桌沿",
                "镜头从监视器尾帧拉到门口，再横移到二人视线交锋",
                "你为什么会有这盘带子？",
            ),
            (
                "证据反转特写",
                f"{primary_role}翻开资料袋，发现案发现场照片背面写着自己的笔迹",
                "资料袋被放在录像带右侧，台灯主光从画面左前方打入，照片边缘潮湿",
                "照片背面的字迹占据画面中心，主角右手悬停，指尖没有触碰墨迹",
                "手持近景跟随资料袋打开，快速切到照片背面文字，背景声音瞬间抽空",
                "这是我的字。",
            ),
            (
                "倒计时压迫",
                "手机倒计时亮起，三人同时意识到案发时间正在逼近",
                "手机在桌面左下角亮起倒计时，录像带和照片形成三角构图",
                "所有人物视线落在手机倒计时上，主光压暗，屏幕冷光打在脸上",
                "俯拍桌面证据形成闭环，再抬到人物表情，节奏突然加快",
                "我们只剩三天。",
            ),
            (
                "走廊尾声钩子",
                f"{primary_role}冲向走廊尽头，墙面浮现和录像带相同的死亡时间",
                "走廊尽头冷白灯闪烁，主角从画面左侧冲入，右手握着手机",
                "主角停在墙面血字前，手机倒计时与墙上时间完全一致",
                "跟拍冲刺后急停，焦点从人物后背拉到墙面血字，留下强钩子",
                "它已经开始了。",
            ),
        ]
        shots: list[ShotPlan] = []
        for index in range(request.shot_count):
            title, summary, first_frame, end_frame, video_prompt, subtitle = shot_templates[index % len(shot_templates)]
            shot_no = index + 1
            focus_roles = [primary_role] if index % 2 == 0 else [primary_role, secondary_role]
            shots.append(
                ShotPlan(
                    shot_no=shot_no,
                    title=title if index < len(shot_templates) else f"占位镜头{shot_no}",
                    summary=summary,
                    duration_seconds=4 + (index % 3),
                    ratio=request.image_aspect_ratio,
                    first_frame_prompt=f"{request.style}，{first_frame}，电影感构图，高细节，短剧强钩子",
                    end_frame_prompt=f"{request.style}，{end_frame}，作为下一镜头首帧连续参考",
                    video_prompt=f"{request.style}视频生成，{video_prompt}，动作连续，人物服装和道具不漂移",
                    continuity_notes=[
                        "上一镜尾帧中的人物站位、手势和视线必须延续到下一镜首帧",
                        "旧录像带、手机、资料袋等道具位置不能无原因跳变",
                        "冷色主光方向保持从画面左前方进入，避免色温突然改变",
                    ],
                    camera_axis=CameraAxisState(
                        axis_description="人物对峙轴线固定在桌面证据两侧，走廊段保持左到右推进",
                        screen_direction="主角运动方向优先由左向右，反打镜头不跳轴",
                        camera_position="机位保持在证据桌同侧或走廊同侧",
                    ),
                    lighting_state=LightingState(
                        key_light_direction="主光从画面左前方打入，屏幕冷光作为补光",
                        color_temperature="偏冷蓝灰，少量钠灯暖色只用于警示",
                        brightness_level="中低照度，高光集中在证据和眼神",
                    ),
                    prop_state=self._build_common_prop_state(),
                    character_state=[
                        CharacterContinuityState(
                            name=role_name,
                            blocking="围绕桌面证据形成稳定空间关系",
                            pose="身体重心前压，动作从上一镜尾帧继续",
                            expression="压抑震惊，不能突然松弛",
                            eyeline="视线在证据、对手和出口之间清晰切换",
                            wardrobe_state="服装、发型和雨水痕迹保持一致",
                        )
                        for role_name in focus_roles
                    ],
                    subtitle_text=subtitle,
                    focus_roles=focus_roles,
                )
            )
        return shots

    @staticmethod
    def _build_common_prop_state() -> list[PropContinuityState]:
        return [
            PropContinuityState(
                prop_name="旧录像带",
                placement="桌面中央或人物手边的核心视觉点",
                orientation="标签面朝镜头，倾斜角度保持稳定",
                hand_usage="如被拿起，优先保持右手持握",
                continuity_priority="high",
            ),
            PropContinuityState(
                prop_name="手机倒计时",
                placement="桌面左下角或主角右手中",
                orientation="屏幕面向镜头，倒计时可读",
                hand_usage="主角右手握持或放在桌面",
                continuity_priority="high",
            ),
        ]
