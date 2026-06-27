#!/usr/bin/env python3
"""Reference grader for GeneBench-Pro public configs."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


def answer_dict(submission: dict[str, Any]) -> dict[str, Any]:
    answer = submission.get("answer", submission)
    return answer if isinstance(answer, dict) else {}


def finite_float(value: Any, field: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field} is not finite")
    return number


def numeric_score(
    agent_value: float,
    true_value: float,
    abs_tol: float | None,
    rel_tol: float | None,
) -> tuple[bool, float, float, float | None]:
    abs_error = abs(agent_value - true_value)
    rel_error = abs_error / abs(true_value) if true_value != 0 else None
    passed_abs = abs_tol is not None and abs_error <= abs_tol
    passed_rel = rel_tol is not None and rel_error is not None and rel_error <= rel_tol
    passed = passed_abs or passed_rel

    if passed_abs and abs_tol:
        score = max(0.0, 1.0 - abs_error / abs_tol)
    elif passed_rel and rel_tol:
        score = max(0.0, 1.0 - rel_error / rel_tol)
    elif abs_tol:
        score = max(0.0, 1.0 - abs_error / abs_tol)
    elif rel_tol and rel_error is not None:
        score = max(0.0, 1.0 - rel_error / rel_tol)
    else:
        score = 1.0 if passed else 0.0
    return passed, score, abs_error, rel_error


def coerce_int(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("boolean is not a valid integer")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value) or not value.is_integer():
            raise ValueError("non-integer float")
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if text.startswith(("+", "-")) and text[1:].isdigit():
            return int(text)
        if text.isdigit():
            return int(text)
        parsed = float(text)
        if not math.isfinite(parsed) or not parsed.is_integer():
            raise ValueError("string is not an integer token")
        return int(parsed)
    raise ValueError(f"unsupported type: {type(value).__name__}")


def evaluate_numeric(
    submission: dict[str, Any],
    ground_truth: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    key = config.get("key", "h2")
    answer = answer_dict(submission)
    details: list[dict[str, Any]] = []
    if key not in answer:
        return result(False, 0.0, [{"key": key, "status": "missing"}])

    try:
        agent_value = finite_float(answer[key], key)
        true_value = finite_float(ground_truth[key], f"{key} ground_truth")
    except Exception as exc:
        return result(False, 0.0, [{"key": key, "status": "invalid_numeric", "error": str(exc)}])

    min_value = config.get("min_value")
    max_value = config.get("max_value")
    if min_value is not None and agent_value < min_value:
        details.append({"key": key, "status": "below_minimum", "agent": agent_value, "minimum": min_value})
        return result(False, 0.0, details)
    if max_value is not None and agent_value > max_value:
        details.append({"key": key, "status": "above_maximum", "agent": agent_value, "maximum": max_value})
        return result(False, 0.0, details)

    passed, score, abs_error, rel_error = numeric_score(
        agent_value,
        true_value,
        config.get("absolute_tolerance"),
        config.get("relative_tolerance"),
    )
    details.append(
        {
            "key": key,
            "status": "pass" if passed else "fail",
            "agent": agent_value,
            "truth": true_value,
            "absolute_error": abs_error,
            "relative_error": rel_error,
        }
    )
    return result(passed, score, details)


def evaluate_multi_numeric(
    submission: dict[str, Any],
    ground_truth: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    answer = answer_dict(submission)
    all_passed = True
    total_score = 0.0
    total_weight = 0.0
    details: list[dict[str, Any]] = []

    for key, key_config in (config.get("keys") or {}).items():
        weight = key_config.get("weight", 1.0)
        if key not in answer:
            all_passed = False
            details.append({"key": key, "status": "missing"})
            continue
        try:
            agent_value = finite_float(answer[key], key)
            true_value = finite_float(ground_truth[key], f"{key} ground_truth")
        except Exception as exc:
            all_passed = False
            details.append({"key": key, "status": "invalid_numeric", "error": str(exc)})
            continue

        min_value = key_config.get("min_value")
        max_value = key_config.get("max_value")
        if min_value is not None and agent_value < min_value:
            all_passed = False
            details.append({"key": key, "status": "below_minimum", "agent": agent_value, "minimum": min_value})
            continue
        if max_value is not None and agent_value > max_value:
            all_passed = False
            details.append({"key": key, "status": "above_maximum", "agent": agent_value, "maximum": max_value})
            continue

        key_passed, key_score, abs_error, rel_error = numeric_score(
            agent_value,
            true_value,
            key_config.get("absolute_tolerance"),
            key_config.get("relative_tolerance"),
        )
        all_passed = all_passed and key_passed
        total_score += key_score * weight
        total_weight += weight
        details.append(
            {
                "key": key,
                "status": "pass" if key_passed else "fail",
                "agent": agent_value,
                "truth": true_value,
                "absolute_error": abs_error,
                "relative_error": rel_error,
            }
        )

    return result(all_passed, total_score / total_weight if total_weight else 0.0, details)


def evaluate_composite(
    submission: dict[str, Any],
    ground_truth: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    numeric_keys = config.get("numeric_keys") or {}
    integer_keys = config.get("integer_keys") or {}
    exact_match_keys = config.get("exact_match_keys") or {}
    expected_keys = set(numeric_keys) | set(integer_keys) | set(exact_match_keys)

    if config.get("strict_answer_schema", False):
        schema_errors: list[str] = []
        if set(submission) != {"answer", "reasoning"}:
            schema_errors.append("top-level keys must be exactly answer and reasoning")
        if not isinstance(submission.get("answer"), dict):
            schema_errors.append("answer field must be a JSON object")
        elif set(submission["answer"]) != expected_keys:
            missing = sorted(expected_keys - set(submission["answer"]))
            extra = sorted(set(submission["answer"]) - expected_keys)
            if missing:
                schema_errors.append("missing answer keys: " + ", ".join(missing))
            if extra:
                schema_errors.append("extra answer keys: " + ", ".join(extra))
        if not isinstance(submission.get("reasoning"), str):
            schema_errors.append("reasoning field must be a string")
        if schema_errors:
            return result(False, 0.0, [{"status": "strict_schema_failed", "errors": schema_errors}])

    answer = answer_dict(submission)
    all_required_passed = True
    total_score = 0.0
    total_weight = 0.0
    details: list[dict[str, Any]] = []

    if config.get("forbid_extra_keys", False):
        extra = sorted(set(answer) - expected_keys)
        if extra:
            all_required_passed = False
            details.append({"status": "extra_keys", "keys": extra})

    for key, key_config in exact_match_keys.items():
        required = key_config.get("required", True)
        weight = key_config.get("weight", 1.0)
        if key not in answer:
            all_required_passed = all_required_passed and not required
            details.append({"key": key, "kind": "exact", "status": "missing"})
            continue
        agent_value = str(answer[key]).strip()
        true_value = str(ground_truth[key]).strip()
        if key_config.get("case_sensitive", False):
            key_passed = agent_value == true_value
        else:
            key_passed = agent_value.lower() == true_value.lower()
        all_required_passed = all_required_passed and (key_passed or not required)
        total_score += (1.0 if key_passed else 0.0) * weight
        total_weight += weight
        details.append({"key": key, "kind": "exact", "status": "pass" if key_passed else "fail"})

    for key, key_config in integer_keys.items():
        required = key_config.get("required", True)
        weight = key_config.get("weight", 1.0)
        if key not in answer:
            all_required_passed = all_required_passed and not required
            details.append({"key": key, "kind": "integer", "status": "missing"})
            continue
        try:
            agent_value = coerce_int(answer[key])
            true_value = int(ground_truth[key])
        except Exception as exc:
            all_required_passed = all_required_passed and not required
            details.append({"key": key, "kind": "integer", "status": "invalid_integer", "error": str(exc)})
            continue
        min_value = key_config.get("min_value")
        max_value = key_config.get("max_value")
        if min_value is not None and agent_value < min_value:
            all_required_passed = all_required_passed and not required
            details.append({"key": key, "kind": "integer", "status": "below_minimum", "agent": agent_value})
            continue
        if max_value is not None and agent_value > max_value:
            all_required_passed = all_required_passed and not required
            details.append({"key": key, "kind": "integer", "status": "above_maximum", "agent": agent_value})
            continue
        key_passed = agent_value == true_value
        all_required_passed = all_required_passed and (key_passed or not required)
        total_score += (1.0 if key_passed else 0.0) * weight
        total_weight += weight
        details.append(
            {
                "key": key,
                "kind": "integer",
                "status": "pass" if key_passed else "fail",
                "agent": agent_value,
                "truth": true_value,
            }
        )

    for key, key_config in numeric_keys.items():
        required = key_config.get("required", True)
        weight = key_config.get("weight", 1.0)
        if key not in answer:
            all_required_passed = all_required_passed and not required
            details.append({"key": key, "kind": "numeric", "status": "missing"})
            continue
        try:
            agent_value = finite_float(answer[key], key)
            true_value = finite_float(ground_truth[key], f"{key} ground_truth")
        except Exception as exc:
            all_required_passed = all_required_passed and not required
            details.append({"key": key, "kind": "numeric", "status": "invalid_numeric", "error": str(exc)})
            continue
        min_value = key_config.get("min_value")
        max_value = key_config.get("max_value")
        if min_value is not None and agent_value < min_value:
            all_required_passed = all_required_passed and not required
            details.append({"key": key, "kind": "numeric", "status": "below_minimum", "agent": agent_value})
            continue
        if max_value is not None and agent_value > max_value:
            all_required_passed = all_required_passed and not required
            details.append({"key": key, "kind": "numeric", "status": "above_maximum", "agent": agent_value})
            continue
        key_passed, key_score, abs_error, rel_error = numeric_score(
            agent_value,
            true_value,
            key_config.get("absolute_tolerance"),
            key_config.get("relative_tolerance"),
        )
        all_required_passed = all_required_passed and (key_passed or not required)
        total_score += key_score * weight
        total_weight += weight
        details.append(
            {
                "key": key,
                "kind": "numeric",
                "status": "pass" if key_passed else "fail",
                "agent": agent_value,
                "truth": true_value,
                "absolute_error": abs_error,
                "relative_error": rel_error,
            }
        )

    return result(all_required_passed, total_score / total_weight if total_weight else 0.0, details)


def result(passed: bool, score: float, details: list[dict[str, Any]]) -> dict[str, Any]:
    return {"passed": bool(passed), "score": float(score), "details": details}


def evaluate(config: dict[str, Any], submission: dict[str, Any]) -> dict[str, Any]:
    grader = config.get("grader") or {}
    grader_type = grader.get("type")
    grader_config = grader.get("config") or {}
    ground_truth = config.get("ground_truth") or {}
    if grader_type == "numeric_tolerance":
        graded = evaluate_numeric(submission, ground_truth, grader_config)
    elif grader_type == "multi_numeric_tolerance":
        graded = evaluate_multi_numeric(submission, ground_truth, grader_config)
    elif grader_type == "composite":
        graded = evaluate_composite(submission, ground_truth, grader_config)
    else:
        raise ValueError(f"unsupported grader type: {grader_type}")
    return {"eval_id": config.get("id"), "grader_type": grader_type, **graded}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("eval_config", type=Path, help="Path to a released eval_config.json")
    parser.add_argument("submission", type=Path, help="Path to eval_answer.json")
    args = parser.parse_args()

    config = json.loads(args.eval_config.read_text())
    submission = json.loads(args.submission.read_text())
    print(json.dumps(evaluate(config, submission), allow_nan=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
