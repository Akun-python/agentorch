from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from agentorch.models.media import (
    ImageGenerationCapableModelAdapter,
    VideoAnalysisCapableModelAdapter,
    build_default_video_output_base_path,
    resolve_response_model_name,
    write_video_analysis_outputs,
)
from agentorch.models.speech import (
    DEFAULT_SPEECH_RESPONSE_FORMAT,
    SpeechCapableModelAdapter,
    build_default_speech_output_path,
    validate_speech_response_format,
)
from agentorch.tools.base import FunctionTool
from agentorch.tools.common import resolve_workspace_path


class TextToSpeechInput(BaseModel):
    text: str = Field(description="Text content to synthesize into speech.")
    voice: str | None = Field(default=None, description="Optional voice name override.")
    response_format: str | None = Field(default=None, description="Optional audio format such as mp3 or wav.")
    speed: float | None = Field(default=None, description="Optional speech speed multiplier.")
    speech_model: str | None = Field(default=None, description="Optional speech model override.")
    output_path: str | None = Field(default=None, description="Optional output path relative to the workspace root.")


class GenerateImageInput(BaseModel):
    prompt: str = Field(description="Prompt used to generate an image.")
    aspect_ratio: str | None = Field(default=None, description="Optional image aspect ratio override.")
    image_size: str | None = Field(default=None, description="Optional image size override.")
    image_model: str | None = Field(default=None, description="Optional image model override.")
    output_path: str | None = Field(default=None, description="Optional output path relative to the workspace root.")


class AnalyzeVideoInput(BaseModel):
    question: str = Field(description="Question or instruction about the video.")
    video_path: str = Field(description="Path to a local video file inside the workspace.")
    video_model: str | None = Field(default=None, description="Optional video-capable model override.")
    mime_type: str | None = Field(default=None, description="Optional MIME type override for the video.")
    save_outputs: bool = Field(default=False, description="Whether to save txt/json analysis artifacts.")
    output_basename: str | None = Field(
        default=None,
        description="Optional output basename relative to the workspace root when save_outputs is true.",
    )


def create_text_to_speech_tool(
    model: SpeechCapableModelAdapter,
    workspace_root: str | Path,
    *,
    name: str = "text_to_speech",
) -> FunctionTool:
    if not isinstance(model, SpeechCapableModelAdapter):
        raise ValueError("create_text_to_speech_tool(...) requires a SpeechCapableModelAdapter instance.")

    root = Path(workspace_root).resolve()

    async def text_to_speech(input: TextToSpeechInput):
        model_config = getattr(model, "config", None)
        selected_format = validate_speech_response_format(
            input.response_format or getattr(model_config, "speech_format", DEFAULT_SPEECH_RESPONSE_FORMAT)
        )
        if input.output_path:
            target = resolve_workspace_path(root, input.output_path, tool_name=name)
        else:
            target = (root / build_default_speech_output_path(response_format=selected_format)).resolve()
        result = await model.synthesize_speech(
            input.text,
            voice=input.voice,
            response_format=selected_format,
            speed=input.speed,
            speech_model=input.speech_model,
            output_path=target,
        )
        return result.model_dump()

    return FunctionTool(
        name=name,
        description="Convert text into an audio file stored inside the workspace.",
        input_model=TextToSpeechInput,
        func=text_to_speech,
        risk_level="low",
    )


def create_generate_image_tool(
    model: ImageGenerationCapableModelAdapter,
    workspace_root: str | Path,
    *,
    name: str = "generate_image",
) -> FunctionTool:
    if not isinstance(model, ImageGenerationCapableModelAdapter):
        raise ValueError("create_generate_image_tool(...) requires an ImageGenerationCapableModelAdapter instance.")

    root = Path(workspace_root).resolve()
    model_config = getattr(model, "config", None)
    configured_timeout = getattr(model_config, "image_timeout", None)
    tool_timeout = 120.0
    if isinstance(configured_timeout, int | float) and configured_timeout > 0:
        tool_timeout = max(float(configured_timeout) + 15.0, 60.0)

    async def generate_image(input: GenerateImageInput):
        if input.output_path:
            target = resolve_workspace_path(root, input.output_path, tool_name=name)
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            target = (root / ".agentorch" / "images" / f"output_image_{timestamp}").resolve()
        result = await model.generate_image(
            input.prompt,
            aspect_ratio=input.aspect_ratio,
            image_size=input.image_size,
            image_model=input.image_model,
            output_path=target,
        )
        return result.model_dump()

    return FunctionTool(
        name=name,
        description="Generate an image file stored inside the workspace.",
        input_model=GenerateImageInput,
        func=generate_image,
        timeout=tool_timeout,
        risk_level="low",
    )


def create_analyze_video_tool(
    model: VideoAnalysisCapableModelAdapter,
    workspace_root: str | Path,
    *,
    name: str = "analyze_video",
) -> FunctionTool:
    if not isinstance(model, VideoAnalysisCapableModelAdapter):
        raise ValueError("create_analyze_video_tool(...) requires a VideoAnalysisCapableModelAdapter instance.")

    root = Path(workspace_root).resolve()

    async def analyze_video(input: AnalyzeVideoInput):
        source = resolve_workspace_path(root, input.video_path, tool_name=name)
        response = await model.analyze_video(
            prompt=input.question,
            video_path=source,
            mime_type=input.mime_type,
            model=input.video_model,
        )
        model_config = getattr(model, "config", None)
        resolved_model = resolve_response_model_name(
            response.raw,
            fallback=input.video_model
            or getattr(model_config, "video_model", None)
            or getattr(model_config, "vision_model", None)
            or getattr(model_config, "model", "unknown"),
        )
        payload: dict[str, Any] = {
            "analysis_text": response.content,
            "model": resolved_model,
            "video_path": str(source),
        }
        if input.save_outputs:
            if input.output_basename:
                base = resolve_workspace_path(root, input.output_basename, tool_name=name)
            else:
                base = (root / build_default_video_output_base_path()).resolve()
            txt_path, json_path = write_video_analysis_outputs(
                analysis_text=response.content,
                question=input.question,
                model=resolved_model,
                video_path=str(source),
                output_basename=base,
            )
            payload["txt_output_path"] = str(txt_path)
            payload["json_output_path"] = str(json_path)
        return payload

    return FunctionTool(
        name=name,
        description="Analyze a local video file and optionally save the text and JSON results.",
        input_model=AnalyzeVideoInput,
        func=analyze_video,
        risk_level="low",
    )


def register_media_tools(registry, *, model, workspace_root: str | Path) -> None:
    registered = False
    if isinstance(model, SpeechCapableModelAdapter):
        registry.register(create_text_to_speech_tool(model, workspace_root))
        registered = True
    if isinstance(model, ImageGenerationCapableModelAdapter):
        registry.register(create_generate_image_tool(model, workspace_root))
        registered = True
    if isinstance(model, VideoAnalysisCapableModelAdapter):
        registry.register(create_analyze_video_tool(model, workspace_root))
        registered = True
    if not registered:
        raise ValueError(
            "register_media_tools(...) requires a model with at least one media capability "
            "(speech, image generation, or video analysis)."
        )
