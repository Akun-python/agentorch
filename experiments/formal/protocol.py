from __future__ import annotations

from experiments.common.tasks import load_formal_tasks
from experiments.rq1_long_horizon_tasks.evaluate import annotate as annotate_rq1
from experiments.rq2_elephant_attention.evaluate import annotate as annotate_rq2
from experiments.rq3_seagull_memory.evaluate import annotate as annotate_rq3
from experiments.rq4_budget_robustness.evaluate import annotate as annotate_rq4
from experiments.rq5_observability.evaluate import annotate as annotate_rq5


FORMAL_PROTOCOL = {
    "rq1_long_horizon_tasks": {
        "benchmark_ids": ["gaia", "hotpotqa", "musique", "agentorch_multiturn_suite"],
        "split": "official_subset",
        "annotate": annotate_rq1,
    },
    "rq2_elephant_attention": {
        "benchmark_ids": ["hotpotqa", "musique"],
        "split": "distractor_subset",
        "annotate": annotate_rq2,
    },
    "rq3_seagull_memory": {
        "benchmark_ids": ["locomo", "longmemeval"],
        "split": "official_subset",
        "annotate": annotate_rq3,
    },
    "rq4_budget_robustness": {
        "benchmark_ids": ["longbench", "infinitebench"],
        "split": "official_subset",
        "annotate": annotate_rq4,
    },
    "rq5_observability": {
        "benchmark_ids": ["agentorch_failure_suite"],
        "split": "official_subset",
        "annotate": annotate_rq5,
    },
}


def load_protocol_tasks(experiment_name: str):
    spec = FORMAL_PROTOCOL[experiment_name]
    return load_formal_tasks(spec["benchmark_ids"], split=spec["split"])
