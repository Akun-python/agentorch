"""命令行入口：支持 `python -m experiments.long_term_memory_graph` 直接运行。"""

from .tools.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
