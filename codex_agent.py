"""Run Codex on the original GeneBench-Pro public package."""

import argparse
import json
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path

from reference_grader import evaluate

ROOT = Path(__file__).resolve().parent
DEFAULT_CODEX_ARGS = [
    "-c",
    'default_permissions="genebench"',
    "-c",
    'permissions.genebench.filesystem={":minimal"="read",":workspace_roots"={"."="write"}}',
    "-c",
    "permissions.genebench.network.enabled=false",
]


def run_case(problem: dict, args: argparse.Namespace) -> dict:
    config_path = ROOT / problem["eval_config"]
    config = json.loads(config_path.read_text())
    output = args.output_dir / problem["eval_id"]
    workspace = output / "workspace"
    workspace.mkdir(parents=True)
    for relative in config["data_files"]:
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts or path.parts[0] != "data_files":
            raise ValueError(f"Input must be under data_files/: {relative}")
        target = workspace / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(config_path.parent / path, target)

    inputs = "\n".join(f"- `{relative}`" for relative in config["data_files"])
    prompt = (
        config["task"]
        + "\n\nWork in the current directory. The available input files are:\n"
        + inputs
        + "\nWrite your final JSON object to `eval_answer.json`.\n"
    )
    (output / "prompt.txt").write_text(prompt)
    command = [
        "codex",
        "--no-daemon",
        "exec",
        "--ignore-user-config",
        "--skip-git-repo-check",
        "--json",
        "--enable",
        "unified_exec",
        "-m",
        args.model,
        "-c",
        f'model_reasoning_effort="{args.reasoning_effort}"',
        "-c",
        "project_doc_max_bytes=0",
        *args.codex_args,
        "-",
    ]
    result = {"eval_id": problem["eval_id"], "command": command}
    started = time.monotonic()
    with (
        (output / "codex.jsonl").open("w") as trace,
        (output / "stderr.log").open("w") as errors,
        subprocess.Popen(
            command,
            cwd=workspace,
            stdin=subprocess.PIPE,
            stdout=trace,
            stderr=errors,
            text=True,
            start_new_session=True,
        ) as process,
    ):
        try:
            process.communicate(prompt, timeout=args.timeout_sec)
            result.update(status="completed", returncode=process.returncode)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            result.update(status="timeout", returncode=process.returncode)
    result["duration_sec"] = round(time.monotonic() - started, 3)
    if result["status"] == "completed" and result["returncode"] != 0:
        result["status"] = "agent_error"
    if result["status"] == "completed":
        try:
            submission = json.loads((workspace / "eval_answer.json").read_text())
            if not isinstance(submission, dict):
                raise TypeError("Submission must be a JSON object")
        except (OSError, ValueError, TypeError) as error:
            result.update(status="submission_error", error=str(error))
        else:
            result.update(status="graded", grading=evaluate(config, submission))
    (output / "result.json").write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n"
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--reasoning-effort", default="high")
    parser.add_argument("--task-ids", nargs="+")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--timeout-sec", type=float, default=3600)
    parser.add_argument(
        "--codex-args",
        nargs=argparse.REMAINDER,
        default=DEFAULT_CODEX_ARGS,
        help="Replace the default permissions with native Codex flags; place last",
    )
    args = parser.parse_args()
    problems = sorted(
        json.loads((ROOT / "manifest.json").read_text())["problems"],
        key=lambda problem: problem["release_order"],
    )
    if args.task_ids:
        unknown = set(args.task_ids) - {problem["eval_id"] for problem in problems}
        if unknown:
            parser.error(f"Unknown task IDs: {', '.join(sorted(unknown))}")
        problems = [
            problem for problem in problems if problem["eval_id"] in args.task_ids
        ]
    if args.timeout_sec <= 0:
        parser.error("--timeout-sec must be positive")
    version = subprocess.check_output(["codex", "--version"], text=True).strip()
    revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    args.output_dir = args.output_dir.resolve()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    results = []
    for problem in problems:
        result = run_case(problem, args)
        results.append(result)
        print(f"{result['eval_id']}: {result['status']}", flush=True)
    complete = all(result["status"] == "graded" for result in results)
    summary = {
        "revision": revision,
        "agent": version,
        "model": args.model,
        "reasoning_effort": args.reasoning_effort,
        "timeout_sec": args.timeout_sec,
        "score": sum(result["grading"]["passed"] for result in results) / len(results)
        if complete
        else None,
        "results": results,
    }
    (args.output_dir / "result.json").write_text(
        json.dumps(summary, indent=2, allow_nan=False) + "\n"
    )
    return 0 if complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
