from __future__ import annotations

import json

from projects.ai_short_drama.backend.app.domain.models import AssemblyPlan, ShortDramaPlan
from projects.ai_short_drama.backend.app.services.drama_output_parse_service import DramaPydanticRepairParser


def _story_plan_payload() -> dict:
    return {
        "project_title": "录像带预告",
        "logline": "女记者收到一盘预告自己死亡的录像带。",
        "visual_style": "都市悬疑，冷色霓虹，手持纪实感",
        "episode_summary": "女记者在旧档案室发现录像带，死亡倒计时开始。",
        "roles": [
            {
                "name": "林夏",
                "appearance": "黑色风衣，短发，眼神警觉",
                "personality": "冷静敏锐",
                "relationship": "主角，追查真相的人",
                "avatar_prompt": "都市悬疑女记者，黑色风衣，短发，冷色霓虹光",
                "voice_style": "低声、克制、带紧张感",
            }
        ],
        "shots": [
            {
                "shot_no": 1,
                "title": "录像带出现",
                "summary": "林夏在旧档案室发现贴着自己名字的录像带。",
                "duration_seconds": 4,
                "ratio": "16:9",
                "first_frame_prompt": "旧档案室门口，林夏推门进入，冷色顶光",
                "end_frame_prompt": "林夏右手拿起录像带，标签上的名字清晰可见",
                "video_prompt": "镜头跟随林夏走向档案柜，手电扫过录像带标签",
                "continuity_notes": ["黑色风衣不变", "手电光方向从画面左侧扫入"],
                "subtitle_text": "这是谁放在这里的？",
                "focus_roles": ["林夏"],
            }
        ],
    }


def test_story_plan_parser_unwraps_reviewer_markdown_json() -> None:
    parser = DramaPydanticRepairParser(ShortDramaPlan)
    raw = "[reviewer] ```json\n" + json.dumps(_story_plan_payload(), ensure_ascii=False) + "\n```"

    parsed = parser.parse_sync(raw)

    assert parsed.project_title == "录像带预告"
    assert parsed.roles[0].name == "林夏"
    assert parsed.shots[0].shot_no == 1


def test_story_plan_parser_unwraps_value_dict_from_failed_primary_parser() -> None:
    parser = DramaPydanticRepairParser(ShortDramaPlan)
    raw = {
        "value": "[reviewer] ```json\n" + json.dumps(_story_plan_payload(), ensure_ascii=False) + "\n```",
        "episode_summary": "",
    }

    parsed = parser.parse_sync(raw)

    assert parsed.logline.startswith("女记者收到")
    assert parsed.visual_style == "都市悬疑，冷色霓虹，手持纪实感"


def test_assembly_parser_unwraps_role_prefixed_json() -> None:
    parser = DramaPydanticRepairParser(AssemblyPlan)
    payload = {
        "episode_title": "录像带预告-第一集",
        "editing_style": "快节奏悬疑",
        "transitions": [
            {
                "transition_no": 1,
                "from_shot_no": 1,
                "to_shot_no": 2,
                "transition_type": "flash",
                "duration_seconds": 0.4,
                "overlap_seconds": 0.25,
                "audio_bridge": "录像机电流声跨到下一镜头",
                "visual_prompt": "强闪白后切入走廊尽头",
                "summary": "用闪白强化惊吓点",
            }
        ],
        "final_runtime_seconds": 8,
        "export_notes": ["先导出字幕包审稿"],
    }
    raw = "[qc_reviewer] 审校通过，最终 JSON 如下：\n" + json.dumps(payload, ensure_ascii=False)

    parsed = parser.parse_sync(raw)

    assert parsed.episode_title == "录像带预告-第一集"
    assert parsed.transitions[0].audio_bridge == "录像机电流声跨到下一镜头"
