"""台本の読み込みとキーの照合."""

from lecanim import narration
from lecanim.cli import _narr_hits


def test_load_scripts(tmp_path, monkeypatch):
    (tmp_path / "narration").mkdir()
    (tmp_path / "narration" / "a.py").write_text('SCRIPTS = {"S": [("note:こんにちは", "やあ")]}')
    (tmp_path / "narration" / "_todo_a.py").write_text("raise RuntimeError('読み込まれてはいけない')")
    monkeypatch.setattr(narration, "ROOT", tmp_path)
    assert narration.load_scripts() == {"S": [("note:こんにちは", "やあ")]}


def test_key_prefix_match():
    script = [("note:15本の辺を", "x"), ("phase:①", "y"), ("note:", "z")]
    assert _narr_hits(script, "note", "15本の辺を赤・青で塗る") == [0, 2]
    assert _narr_hits(script, "phase", "① 1人に注目") == [1]
    assert _narr_hits(script, "def", "u") == []
