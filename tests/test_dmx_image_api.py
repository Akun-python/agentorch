from __future__ import annotations

import importlib
from pathlib import Path

from api接口 import (
    analyze_dmx_image_text,
    configure_dmx_image_understanding,
    get_dmx_image_understanding_defaults,
)


def test_package_level_config_can_override_dmx_image_model(monkeypatch):
    monkeypatch.setenv("DMX_API_KEY", "test-key")
    monkeypatch.delenv("DMX_IMAGE_MODEL", raising=False)
    configure_dmx_image_understanding(model="gemini-2.5-flash")

    defaults = get_dmx_image_understanding_defaults()

    assert defaults["model"] == "gemini-2.5-flash"

    configure_dmx_image_understanding(model=None)


def test_analyze_dmx_image_text_uses_package_default_model(monkeypatch, tmp_path: Path):
    image_path = tmp_path / "sample.png"
    image_path.write_bytes(
        bytes.fromhex(
            "89504E470D0A1A0A"
            "0000000D49484452000000010000000108060000001F15C489"
            "0000000A49444154789C6360000002000154A24F5D00000000"
            "49454E44AE426082"
        )
    )

    monkeypatch.setenv("DMX_API_KEY", "test-key")
    configure_dmx_image_understanding(model="vision-test-model")

    captured: dict[str, object] = {}

    class DummyResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"choices": [{"message": {"content": "ok"}}]}

    def fake_post(url: str, *, headers: dict[str, str], json: dict[str, object], timeout: float):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return DummyResponse()

    module = importlib.import_module("api接口.图片理解dmxapi")
    monkeypatch.setattr(module.requests, "post", fake_post)

    result = analyze_dmx_image_text(image_path)

    assert result == "ok"
    assert captured["json"]["model"] == "vision-test-model"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert isinstance(captured["json"]["messages"], list)

    configure_dmx_image_understanding(model=None)
