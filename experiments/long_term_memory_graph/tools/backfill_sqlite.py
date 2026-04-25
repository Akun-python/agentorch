from __future__ import annotations

import argparse
import os

from .. import GraphMemoryConfig, LongTermMemoryGraphPlugin


def backfill_sqlite(
    *,
    records_db_path: str,
    uri: str,
    username: str,
    password: str,
    database: str,
) -> dict[str, object]:
    plugin = LongTermMemoryGraphPlugin(
        GraphMemoryConfig(
            neo4j_uri=uri,
            neo4j_username=username,
            neo4j_password=password,
            neo4j_database=database,
        )
    )
    try:
        return plugin.backfill_from_sqlite(records_db_path).model_dump()
    finally:
        plugin.close()


def build_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("backfill-sqlite", help="Backfill an existing records.db into Neo4j.")
    parser.add_argument("records_db_path")
    parser.add_argument("--uri", default=os.getenv("NEO4J_URI", "bolt://127.0.0.1:7787"))
    parser.add_argument("--username", default=os.getenv("NEO4J_USERNAME", "neo4j"))
    parser.add_argument("--password", default=os.getenv("NEO4J_PASSWORD"))
    parser.add_argument("--database", default=os.getenv("NEO4J_DATABASE", "neo4j"))
    parser.set_defaults(handler=run_from_args)


def run_from_args(args: argparse.Namespace) -> dict[str, object]:
    if bool(args.username) != bool(args.password):
        raise SystemExit("Provide both Neo4j username and password, or leave both empty for an auth-disabled sandbox.")
    return backfill_sqlite(
        records_db_path=args.records_db_path,
        uri=args.uri,
        username=args.username,
        password=args.password,
        database=args.database,
    )


__all__ = ["backfill_sqlite", "build_parser", "run_from_args"]
