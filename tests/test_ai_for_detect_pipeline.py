from __future__ import annotations

import os
from pathlib import Path

import pytest

pd = pytest.importorskip("pandas")
pytest.importorskip("openpyxl")

from projects.ai_for_detect.config import resolve_model_names
from projects.ai_for_detect.env_loader import load_project_env
from projects.ai_for_detect.generator import MultiModelSentenceGenerator
from projects.ai_for_detect.pipeline import AIDetectBatchPipeline, PipelineConfig
from projects.ai_for_detect.prompts import build_rewrite_prompt


class FakeSentenceGenerator:
    model_name = "fake-model"
    model_names = ["fake-model"]

    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None, str]] = []

    def rewrite_text(self, *, source_text: str, domain_label: str | None, thread_id: str, row_index: int = 0) -> str:
        self.calls.append((source_text, domain_label, thread_id))
        return f"AI::{domain_label}::{source_text}"

    def close(self) -> None:
        return None


def test_build_rewrite_prompt_contains_domain_and_text() -> None:
    prompt = build_rewrite_prompt(source_text="菜品温度差菜品味道佳", domain_label="外卖")

    assert "领域标签：外卖" in prompt
    assert "原始文本：菜品温度差菜品味道佳" in prompt
    assert "改写成一句新的中文表述" in prompt
    assert "最终只返回一条中文句子" in prompt


def test_load_project_env_reads_local_env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "OPENAI_API_KEY=test-key\n"
        "OPENAI_BASE_URL=https://example.com/v1\n"
        "AI_FOR_DETECT_MODEL=test-model\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("AI_FOR_DETECT_MODEL", raising=False)

    loaded_path = load_project_env(env_path)

    assert loaded_path == env_path
    assert os.getenv("OPENAI_API_KEY") == "test-key"
    assert os.getenv("OPENAI_BASE_URL") == "https://example.com/v1"
    assert os.getenv("AI_FOR_DETECT_MODEL") == "test-model"


def test_resolve_model_names_prefers_multi_model_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_FOR_DETECT_MODELS", "model-a, model-b,model-c")
    monkeypatch.delenv("AI_FOR_DETECT_MODEL", raising=False)

    assert resolve_model_names(None) == ["model-a", "model-b", "model-c"]


def test_multi_model_sentence_generator_rotates_models() -> None:
    generator = MultiModelSentenceGenerator.__new__(MultiModelSentenceGenerator)
    generator.model_names = ["model-a", "model-b", "model-c"]

    assert generator.select_model(row_index=0).model_name == "model-a"
    assert generator.select_model(row_index=1).model_name == "model-b"
    assert generator.select_model(row_index=2).model_name == "model-c"
    assert generator.select_model(row_index=3).model_name == "model-a"


def test_pipeline_writes_output_and_resume_skips_existing_rows(tmp_path: Path) -> None:
    input_dir = tmp_path / "data"
    output_dir = tmp_path / "outputs"
    input_dir.mkdir()

    source_path = input_dir / "银行.xlsx"
    source_df = pd.DataFrame(
        [
            {"文本": "一万不过一般都是的存", "领域标签": "银行"},
            {"文本": "手机银行一个手机号只能绑定一次", "领域标签": "银行"},
        ]
    )
    source_df.to_excel(source_path, index=False)

    first_generator = FakeSentenceGenerator()
    first_pipeline = AIDetectBatchPipeline(
        generator=first_generator,
        config=PipelineConfig(
            input_path=input_dir,
            output_dir=output_dir,
            flush_every=1,
        ),
    )
    first_summaries = first_pipeline.run()

    assert len(first_summaries) == 1
    assert first_summaries[0].generated_rows == 2
    assert len(first_generator.calls) == 2

    output_path = output_dir / "银行_ai生成.xlsx"
    output_df = pd.read_excel(output_path)
    assert output_df["AI生成文本"].tolist() == [
        "AI::银行::一万不过一般都是的存",
        "AI::银行::手机银行一个手机号只能绑定一次",
    ]
    assert output_df["生成状态"].tolist() == ["success", "success"]

    second_generator = FakeSentenceGenerator()
    second_pipeline = AIDetectBatchPipeline(
        generator=second_generator,
        config=PipelineConfig(
            input_path=input_dir,
            output_dir=output_dir,
            flush_every=1,
        ),
    )
    second_summaries = second_pipeline.run()

    assert second_summaries[0].generated_rows == 0
    assert second_summaries[0].skipped_rows == 2
    assert second_generator.calls == []


def test_pipeline_records_rotated_model_names(tmp_path: Path) -> None:
    class RotatingFakeGenerator(FakeSentenceGenerator):
        model_names = ["model-a", "model-b"]

        def resolve_model_for_row(self, *, row_index: int) -> str:
            return self.model_names[row_index % len(self.model_names)]

    input_dir = tmp_path / "data_multi"
    output_dir = tmp_path / "outputs_multi"
    input_dir.mkdir()

    source_path = input_dir / "金融.xlsx"
    pd.DataFrame(
        [
            {"文本": "文本1", "领域标签": "金融"},
            {"文本": "文本2", "领域标签": "金融"},
            {"文本": "文本3", "领域标签": "金融"},
        ]
    ).to_excel(source_path, index=False)

    generator = RotatingFakeGenerator()
    pipeline = AIDetectBatchPipeline(
        generator=generator,
        config=PipelineConfig(
            input_path=input_dir,
            output_dir=output_dir,
            flush_every=1,
        ),
    )

    pipeline.run()

    output_df = pd.read_excel(output_dir / "金融_ai生成.xlsx")
    assert output_df["AI生成模型"].tolist() == ["model-a", "model-b", "model-a"]
