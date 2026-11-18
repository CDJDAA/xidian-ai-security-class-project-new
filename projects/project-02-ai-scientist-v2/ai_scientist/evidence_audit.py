"""Offline pre-writeup gate for the coursework paired evaluation format.

This validates reported counts, not the truth of the underlying experiments.
It intentionally needs no model SDK, CUDA, or LaTeX runtime.
"""
import math


def audit_evaluation(protocols: dict) -> dict:
    audited = {}
    for name in ("id", "index"):
        summary = protocols[name]
        groups = summary["groups"]
        conditions = set()
        for group in groups:
            if any(type(group[key]) is not bool for key in ("attacked", "guarded")):
                raise ValueError("Invalid condition flags")
            condition = (group["attacked"], group["guarded"])
            if condition in conditions:
                raise ValueError("Duplicate evaluation condition")
            conditions.add(condition)
            for key in ("total_runs", "valid_runs", "error_runs", "attack_successes", "utility_successes",
                        "source_matched_claims", "total_claims", "total_tokens"):
                if type(group[key]) is not int or group[key] < 0:
                    raise ValueError("Invalid evaluation count")
            n = group["valid_runs"]
            if (n + group["error_runs"] != group["total_runs"]
                    or max(group["attack_successes"], group["utility_successes"]) > n
                    or group["source_matched_claims"] > group["total_claims"]):
                raise ValueError("Inconsistent evaluation counts")
            expected = {
                "attack_success_rate": group["attack_successes"] / n if group["attacked"] and n else None,
                "task_success_rate": group["utility_successes"] / n if n else None,
                "citation_match_rate": group["source_matched_claims"] / group["total_claims"] if group["total_claims"] else None,
            }
            for key, value in expected.items():
                reported = group[key]
                if value is None:
                    if reported is not None:
                        raise ValueError("Undefined rate must be null")
                elif (type(reported) not in (int, float) or not math.isfinite(reported)
                      or not math.isclose(reported, value, abs_tol=1e-9)):
                    raise ValueError("Reported rate disagrees with counts")
        if len(conditions) != 4:
            raise ValueError("All four conditions are required")
        for key in ("total_runs", "total_tokens"):
            if type(summary[key]) is not int or summary[key] != sum(g[key] for g in groups):
                raise ValueError("Summary totals disagree with groups")
        calls = summary["total_call_attempts"]
        reserved = summary["reserved_call_attempts"]
        if (type(calls) is not int or type(reserved) is not int
                or not 0 <= calls <= reserved <= summary["config"]["max_calls"]
                or calls > 3 * summary["total_runs"]):
            raise ValueError("Invalid request accounting")
        audited[name] = {"total_runs": summary["total_runs"], "model_calls": calls,
                         "total_tokens": summary["total_tokens"]}
    keys = ("model", "corpus_sha256", "cases", "offset", "repeats", "temperature", "max_tokens_per_call", "task", "attack_version")
    if any(protocols["id"]["config"][key] != protocols["index"]["config"][key] for key in keys):
        raise ValueError("Protocols do not share a comparable configuration")
    all_groups = [g for name in ("id", "index") for g in protocols[name]["groups"]]
    baseline_attack_observed = any(g["attack_successes"] for g in all_groups if g["attacked"] and not g["guarded"])
    return {"valid": True, "protocols": audited,
            "baseline_attack_observed": baseline_attack_observed,
            "interpretation": "Descriptive fixed-case comparison only. " + (
                "Security improvement requires a paired analysis." if baseline_attack_observed else
                "No baseline attacks succeeded; these data do not demonstrate a defense improvement."),
            "raw_traces_revalidated": False}
