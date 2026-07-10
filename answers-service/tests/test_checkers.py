from app import checkers


def test_check_test_scores_multiple_questions():
    key = {
        "questions": [
            {"question": "2+2?", "options": ["3", "4"], "correct_index": 1},
            {"question": "Capital of France?", "options": ["Paris", "London"], "correct_index": 0},
        ]
    }
    payload = {
        "answers": [
            {"question_index": 0, "selected_index": 1},  # correct
            {"question_index": 1, "selected_index": 1},  # wrong
        ]
    }
    result = checkers.check_test(payload, key)
    assert result.correct_count == 1
    assert result.wrong_count == 1
    assert result.total_count == 2


def test_check_test_unanswered_questions_not_counted():
    key = {"questions": [{"question": "q", "options": ["a", "b"], "correct_index": 0}]}
    result = checkers.check_test({"answers": []}, key)
    assert result.correct_count == 0
    assert result.wrong_count == 0
    assert result.total_count == 1


def test_check_true_false():
    key = {"statements": [{"text": "Sky is blue", "is_true": True}, {"text": "2+2=5", "is_true": False}]}
    payload = {
        "answers": [
            {"statement_index": 0, "selected_value": True},
            {"statement_index": 1, "selected_value": True},
        ]
    }
    result = checkers.check_true_false(payload, key)
    assert result.correct_count == 1
    assert result.wrong_count == 1


def test_check_fill_gaps_normalizes_whitespace_and_case():
    key = {"text": "The {{0}} sat on the {{1}}", "answers": ["cat", "mat"]}
    payload = {"gaps": {"0": "  CAT  ", "1": "dog"}}
    result = checkers.check_fill_gaps(payload, key)
    assert result.correct_count == 1
    assert result.wrong_count == 1
    assert result.total_count == 2


def test_check_match_cards():
    key = {"cards": [{"left": "cat", "right": "meow"}, {"left": "dog", "right": "woof"}]}
    payload = {"pairs": {"cat": "meow", "dog": "meow"}}
    result = checkers.check_match_cards(payload, key)
    assert result.correct_count == 1
    assert result.wrong_count == 1


def test_check_reorder():
    key = {"sentences": [{"words": ["I", "am", "happy"]}]}
    payload = {"sentences": {"0": ["I", "am", "happy"]}}
    result = checkers.check_reorder(payload, key)
    assert result.correct_count == 1
    assert result.wrong_count == 0

    bad_payload = {"sentences": {"0": ["am", "I", "happy"]}}
    result_bad = checkers.check_reorder(bad_payload, key)
    assert result_bad.correct_count == 0
    assert result_bad.wrong_count == 1


def test_check_sorting():
    key = {
        "columns": [
            {"title": "Fruits", "items": ["apple", "banana"]},
            {"title": "Veggies", "items": ["carrot"]},
        ]
    }
    payload = {"placements": {"apple": 0, "banana": 1, "carrot": 1}}
    result = checkers.check_sorting(payload, key)
    assert result.correct_count == 2  # apple and carrot correctly placed
    assert result.wrong_count == 1  # banana misplaced (should be column 0)
    assert result.total_count == 3


def test_is_objective():
    assert checkers.is_objective("test") is True
    assert checkers.is_objective("writing_task") is False
    assert checkers.is_objective("voice_recording") is False
