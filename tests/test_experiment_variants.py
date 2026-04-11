from experiments.common.config import ExperimentConfig
from experiments.common.runtime_variants import build_runtime_variant


def test_variant_flags_disable_expected_mechanisms(tmp_path):
    config = ExperimentConfig.for_variant(
        experiment_name="rq1_long_horizon_tasks",
        variant_name="multi_agent_no_elephant",
        model_name="mock:tool",
        judge_model_name=None,
        prompt_budget=12000,
        task_limit=1,
        repeat_count=1,
        output_dir=tmp_path,
        enable_live_web_search=False,
        seed=7,
    )
    runtime, metadata = build_runtime_variant(config, workspace_root=tmp_path, output_dir=tmp_path / "out1")
    assert runtime.config.context_strategy.salience_mode == "off"
    assert metadata["method_flags"]["elephant_attention"] is False

    plain_logs = ExperimentConfig.for_variant(
        experiment_name="rq5_observability",
        variant_name="multi_agent_plain_logs",
        model_name="mock:tool",
        judge_model_name=None,
        prompt_budget=12000,
        task_limit=1,
        repeat_count=1,
        output_dir=tmp_path,
        enable_live_web_search=False,
        seed=7,
    )
    runtime_plain, metadata_plain = build_runtime_variant(plain_logs, workspace_root=tmp_path, output_dir=tmp_path / "out2")
    assert runtime_plain.observability.enabled is False
    assert metadata_plain["sqlite_path"] is None
