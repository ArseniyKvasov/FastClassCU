"""Checker registry: one function per objective task_type, each scoring a
student's payload against Content Service's answer-key payload for that task.

This is the single place correctness is computed - Content Service never
computes it (it only stores/serves the key), Assignments Service never
recomputes it (it only aggregates the `answer_scored` events this service
emits). Subjective types (writing_task, voice_recording, file, ...) have no
entry here - SubmitAnswer just stores their payload unchecked.
"""

import re
from dataclasses import dataclass


@dataclass
class CheckResult:
    correct_count: int
    wrong_count: int
    total_count: int


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text).strip().lower())


def check_test(payload: dict, answer_key: dict) -> CheckResult:
    questions = answer_key.get("questions", [])
    answers_by_index = {
        a.get("question_index"): a.get("selected_index") for a in payload.get("answers", [])
    }
    correct = wrong = 0
    for i, question in enumerate(questions):
        selected = answers_by_index.get(i)
        if selected is None:
            continue
        if selected == question.get("correct_index"):
            correct += 1
        else:
            wrong += 1
    return CheckResult(correct, wrong, len(questions))


def check_true_false(payload: dict, answer_key: dict) -> CheckResult:
    statements = answer_key.get("statements", [])
    answers_by_index = {
        a.get("statement_index"): a.get("selected_value") for a in payload.get("answers", [])
    }
    correct = wrong = 0
    for i, statement in enumerate(statements):
        selected = answers_by_index.get(i)
        if selected is None:
            continue
        if bool(selected) == bool(statement.get("is_true")):
            correct += 1
        else:
            wrong += 1
    return CheckResult(correct, wrong, len(statements))


def check_fill_gaps(payload: dict, answer_key: dict) -> CheckResult:
    correct_answers = answer_key.get("answers", [])
    gaps = payload.get("gaps", {})
    correct = wrong = 0
    for gap_id, value in gaps.items():
        try:
            index = int(gap_id)
        except (TypeError, ValueError):
            continue
        if not (0 <= index < len(correct_answers)):
            continue
        if _normalize(value) == _normalize(correct_answers[index]):
            correct += 1
        else:
            wrong += 1
    return CheckResult(correct, wrong, len(correct_answers))


def check_match_cards(payload: dict, answer_key: dict) -> CheckResult:
    cards = answer_key.get("cards", [])
    correct_lookup = {str(c["left"]): str(c["right"]) for c in cards}
    pairs = payload.get("pairs", {})
    correct = wrong = 0
    for left, right_guess in pairs.items():
        expected = correct_lookup.get(str(left))
        if expected is None:
            continue
        if _normalize(right_guess) == _normalize(expected):
            correct += 1
        else:
            wrong += 1
    return CheckResult(correct, wrong, len(cards))


def check_reorder(payload: dict, answer_key: dict) -> CheckResult:
    sentences = answer_key.get("sentences", [])
    submitted = payload.get("sentences", {})
    correct = wrong = 0
    for i, sentence in enumerate(sentences):
        words = submitted.get(str(i))
        if words is None:
            continue
        expected = [_normalize(w) for w in sentence.get("words", [])]
        actual = [_normalize(w) for w in words]
        if actual == expected:
            correct += 1
        else:
            wrong += 1
    return CheckResult(correct, wrong, len(sentences))


def check_sorting(payload: dict, answer_key: dict) -> CheckResult:
    columns = answer_key.get("columns", [])
    correct_lookup: dict[str, int] = {}
    for col_index, column in enumerate(columns):
        for item in column.get("items", []):
            correct_lookup[str(item)] = col_index

    placements = payload.get("placements", {})
    correct = wrong = 0
    for item, column_index in placements.items():
        expected = correct_lookup.get(str(item))
        if expected is None:
            continue
        if int(column_index) == expected:
            correct += 1
        else:
            wrong += 1
    return CheckResult(correct, wrong, len(correct_lookup))


CHECKERS = {
    "test": check_test,
    "true_false": check_true_false,
    "fill_gaps": check_fill_gaps,
    "match_cards": check_match_cards,
    "reorder": check_reorder,
    "sorting": check_sorting,
}


def is_objective(task_type: str) -> bool:
    return task_type in CHECKERS


def check_answer(task_type: str, payload: dict, answer_key: dict) -> CheckResult:
    checker = CHECKERS.get(task_type)
    if checker is None:
        raise ValueError(f"No objective checker for task_type '{task_type}'")
    return checker(payload, answer_key)
