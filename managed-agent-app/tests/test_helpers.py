"""
Unit tests for the pure helpers in the client — the parts most likely to regress:
event-content text extraction (dict blocks, model objects, strings, empties) and
VAULT_IDS parsing. No network; these load python/main.py directly.
"""

import importlib.util
import pathlib

import pytest

pytest.importorskip("anthropic")  # python/main.py imports the SDK at module load

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load(relpath, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / relpath)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


main = _load("python/main.py", "ma_main")


class _Block:
    """Stand-in for an SDK model object (attributes, not dict keys)."""

    def __init__(self, **kw):
        self.__dict__.update(kw)


def test_text_blocks_from_string():
    assert list(main._iter_text_blocks("hello")) == ["hello"]


def test_text_blocks_none_is_empty():
    assert list(main._iter_text_blocks(None)) == []


def test_text_blocks_from_dicts():
    content = [{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]
    assert list(main._iter_text_blocks(content)) == ["a", "b"]


def test_text_blocks_skips_empty_and_non_text():
    content = [
        {"type": "text", "text": ""},
        {"type": "image"},
        {"type": "text", "text": "x"},
    ]
    assert list(main._iter_text_blocks(content)) == ["x"]


def test_text_blocks_from_model_objects():
    content = [_Block(type="text", text="o1"), _Block(type="text", text="o2")]
    assert list(main._iter_text_blocks(content)) == ["o1", "o2"]


def test_text_blocks_none_type_is_treated_as_text():
    # a block with no explicit type but text present should still yield
    assert list(main._iter_text_blocks([{"text": "t"}])) == ["t"]


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("", []),
        ("vlt_a", ["vlt_a"]),
        ("vlt_a, vlt_b ,, vlt_c ", ["vlt_a", "vlt_b", "vlt_c"]),
        ("  ", []),
    ],
)
def test_vault_ids_parsing(monkeypatch, raw, expected):
    monkeypatch.setenv("VAULT_IDS", raw)
    mod = _load("python/main.py", f"ma_main_{abs(hash(raw))}")
    assert mod.VAULT_IDS == expected
