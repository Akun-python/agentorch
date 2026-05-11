from __future__ import annotations

from pathlib import Path

from projects.ai_short_drama.backend.app.domain.models import DramaProjectRequest
from projects.ai_short_drama.backend.app.services.agent_team_service import AgentTorchDramaTeamService


def test_agent_team_uses_request_llm_stability_settings(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENAI_CHAT_MODEL", "test-model")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.com/v1")
    request = DramaProjectRequest(
        project_name="LLM 稳定性配置测试",
        premise="测试真实 LLM 调用参数",
        llm_timeout_seconds=300,
        llm_max_retries=3,
        llm_retry_base_delay_seconds=5,
        llm_retry_max_delay_seconds=90,
        llm_min_request_interval_seconds=1,
        llm_max_tokens=4096,
        agent_coordination_mode="guided",
        llm_parallel_agents=False,
    )

    service = AgentTorchDramaTeamService(workspace_root=tmp_path, request=request)
    try:
        config = service.shared_model.config

        assert config.timeout == 300
        assert config.max_retries == 3
        assert config.retry_base_delay == 5
        assert config.retry_max_delay == 90
        assert config.min_request_interval == 1
        assert config.max_tokens == 4096
        assert service.story_team.runtime.config.coordination_policy.route_mode == "guided"
    finally:
        service.close()
