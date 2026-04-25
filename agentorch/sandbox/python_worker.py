from __future__ import annotations

import ast
import contextlib
import io
import json
import os
import sys
import traceback
from typing import Any


def _initial_state() -> dict[str, Any]:
    return {
        "__name__": "__agentorch_python_session__",
        "__package__": None,
        "__builtins__": __builtins__,
    }


def _execute(code: str, state: dict[str, Any]) -> dict[str, Any]:
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    result_repr: str | None = None
    exit_code = 0
    try:
        module = ast.parse(code, mode="exec")
        body = list(module.body)
        with contextlib.redirect_stdout(stdout_buffer), contextlib.redirect_stderr(stderr_buffer):
            if body and isinstance(body[-1], ast.Expr):
                prefix = ast.Module(body=body[:-1], type_ignores=[])
                expression = ast.Expression(body[-1].value)
                if prefix.body:
                    exec(compile(prefix, "<agentorch-session>", "exec"), state)
                value = eval(compile(expression, "<agentorch-session>", "eval"), state)
                if value is not None:
                    result_repr = repr(value)
                    print(result_repr)
            else:
                exec(compile(module, "<agentorch-session>", "exec"), state)
    except BaseException:
        exit_code = 1
        traceback.print_exc(file=stderr_buffer)
    return {
        "stdout": stdout_buffer.getvalue(),
        "stderr": stderr_buffer.getvalue(),
        "exit_code": exit_code,
        "result_repr": result_repr,
    }


def main() -> int:
    state = _initial_state()
    initial_workdir = os.getcwd()
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            response = {
                "ok": False,
                "exit_code": 1,
                "stdout": "",
                "stderr": f"Invalid worker request: {exc}",
                "result_repr": None,
                "workdir": os.getcwd(),
            }
            print(json.dumps(response, ensure_ascii=False), flush=True)
            continue

        action = str(request.get("action") or "exec")
        if action == "close":
            response = {
                "ok": True,
                "exit_code": 0,
                "stdout": "",
                "stderr": "",
                "result_repr": None,
                "workdir": os.getcwd(),
            }
            print(json.dumps(response, ensure_ascii=False), flush=True)
            break
        if action == "reset":
            state = _initial_state()
            target_workdir = request.get("workdir") or initial_workdir
            try:
                os.chdir(target_workdir)
                response = {
                    "ok": True,
                    "exit_code": 0,
                    "stdout": "",
                    "stderr": "",
                    "result_repr": None,
                    "workdir": os.getcwd(),
                }
            except BaseException:
                response = {
                    "ok": False,
                    "exit_code": 1,
                    "stdout": "",
                    "stderr": traceback.format_exc(),
                    "result_repr": None,
                    "workdir": os.getcwd(),
                }
            print(json.dumps(response, ensure_ascii=False), flush=True)
            continue
        if action != "exec":
            response = {
                "ok": False,
                "exit_code": 1,
                "stdout": "",
                "stderr": f"Unsupported worker action: {action}",
                "result_repr": None,
                "workdir": os.getcwd(),
            }
            print(json.dumps(response, ensure_ascii=False), flush=True)
            continue

        try:
            target_workdir = request.get("workdir")
            if target_workdir:
                os.chdir(target_workdir)
            response = {
                "ok": True,
                **_execute(str(request.get("code") or ""), state),
                "workdir": os.getcwd(),
            }
        except BaseException:
            response = {
                "ok": False,
                "exit_code": 1,
                "stdout": "",
                "stderr": traceback.format_exc(),
                "result_repr": None,
                "workdir": os.getcwd(),
            }
        print(json.dumps(response, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
