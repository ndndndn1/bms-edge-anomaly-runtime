#!/usr/bin/env python3
"""Validate the repository quality scorecard with the Python standard library."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCORECARD = ROOT / "quality" / "scorecard.json"
REQUIRED_GATES = {"tests", "runtime_smoke", "memory", "security", "docs_examples"}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"scorecard invalid: {message}")


def main() -> None:
    data = json.loads(SCORECARD.read_text())
    require(data.get("schema_version") == "1.0", "schema_version must be 1.0")
    target = data.get("target")
    score = data.get("score")
    require(isinstance(target, int) and not isinstance(target, bool), "target must be an integer")
    require(isinstance(score, int) and not isinstance(score, bool), "score must be an integer")
    require(target == 80, "target must be 80")

    categories = data.get("categories")
    require(isinstance(categories, list) and categories, "categories must be a nonempty list")
    ids: set[str] = set()
    maximum = 0
    earned = 0
    for category in categories:
        require(isinstance(category, dict), "each category must be an object")
        category_id = category.get("id")
        require(isinstance(category_id, str) and category_id.strip(), "category id is required")
        require(category_id not in ids, f"duplicate category id: {category_id}")
        ids.add(category_id)
        category_max = category.get("max")
        category_earned = category.get("earned")
        require(type(category_max) is int and category_max > 0, f"{category_id} max must be positive")
        require(type(category_earned) is int, f"{category_id} earned must be an integer")
        require(0 <= category_earned <= category_max, f"{category_id} earned is out of range")
        evidence = category.get("evidence")
        require(isinstance(evidence, list) and evidence, f"{category_id} evidence is required")
        for item in evidence:
            require(isinstance(item, str) and item.strip(), f"{category_id} evidence must be strings")
            require((ROOT / item).exists(), f"{category_id} evidence does not exist: {item}")
        maximum += category_max
        earned += category_earned

    require(maximum == 100, f"category max total must be 100, got {maximum}")
    require(score == earned, f"score must equal earned total {earned}")
    require(score >= target, f"score {score} is below target {target}")
    gates = data.get("hard_gates")
    require(isinstance(gates, dict), "hard_gates must be an object")
    require(set(gates) == REQUIRED_GATES, "hard_gates keys do not match the contract")
    require(all(value is True for value in gates.values()), "all hard gates must be true")
    print(f"quality scorecard valid: {score}/100 (target {target})")


if __name__ == "__main__":
    main()
