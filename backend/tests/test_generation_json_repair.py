"""Unit tests for _parse_llm_json (JSON repair used by content generation retry)."""
import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ai_visibility import _parse_llm_json  # noqa: E402


def test_valid_json_simple():
    data = _parse_llm_json('{"title": "Test", "body": "Hello"}')
    assert data["title"] == "Test"
    assert data["body"] == "Hello"


def test_json_with_fences():
    raw = '```json\n{"title": "Fenced", "n": 42}\n```'
    data = _parse_llm_json(raw)
    assert data["title"] == "Fenced"
    assert data["n"] == 42


def test_json_with_fences_no_lang():
    raw = '```\n{"a": 1}\n```'
    data = _parse_llm_json(raw)
    assert data["a"] == 1


def test_json_truncated_in_string():
    # Simulates max_tokens truncation cutting a string open
    raw = '{"title": "Test article", "body_markdown": "Lorem ipsum dol'
    data = _parse_llm_json(raw)
    # Repair must return a usable dict without crashing
    assert isinstance(data, dict)
    assert data.get("title") == "Test article"


def test_json_truncated_after_key():
    # Truncated right after a key/value pair inside a nested list
    raw = '{"title": "T", "faq": [{"question": "Q1", "answer": "A1"}, {"question": "Q2",'
    data = _parse_llm_json(raw)
    assert isinstance(data, dict)
    assert data.get("title") == "T"


def test_text_without_json_raises():
    with pytest.raises((ValueError, Exception)):
        _parse_llm_json("This is just some plain text, no JSON at all.")


def test_json_with_leading_text():
    raw = 'Voici le résultat :\n{"title": "OK", "n": 1}\n'
    data = _parse_llm_json(raw)
    assert data["title"] == "OK"
