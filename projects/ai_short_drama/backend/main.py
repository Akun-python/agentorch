import argparse
import json
import sys
from pathlib import Path


# 保证直接运行脚本时可以优先导入当前仓库里的 agentorch
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from projects.ai_short_drama.backend.app.domain.models import DramaProjectRequest
from projects.ai_short_drama.backend.app.services.drama_pipeline_service import DramaPipelineService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI 短剧最小闭环入口")
    parser.add_argument(
        "--config",
        required=True,
        help="项目配置 JSON 路径",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_path = Path(args.config).resolve()
    request = DramaProjectRequest.model_validate_json(config_path.read_text(encoding="utf-8"))

    service = DramaPipelineService(project_root=REPO_ROOT / "projects" / "ai_short_drama")
    result = service.run(request)

    print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
