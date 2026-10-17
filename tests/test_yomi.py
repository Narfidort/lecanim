"""読みの辞書の層・UniDic との突き合わせ."""

import pytest

from lecanim import yomi as Y


def test_norm_kana_long_vowels():
    assert Y.norm_kana("ショーメー") == Y.norm_kana("ショウメイ") == Y.norm_kana("ショオメエ")
    assert Y.norm_kana("コ'オ_ゴ/ニ") == "コオゴニ"


def test_scan_finds_known_misreadings():
    pytest.importorskip("fugashi")
    # OpenJTalk が誤読しやすい語（行→くだり，負→まけ，辺→あたり）
    got = {f["surface"]: f for f in Y.scan_sentence("字下げされた行が負の辺です。",
                                                    "ジサゲ'/サレタ'/クダリガ'/マ'ケノ/アタリデ_ス")}
    assert {"行", "負", "辺"} <= set(got)
    assert got["行"]["voicevox"] == "クダリ"


def test_scan_quiet_when_readings_agree():
    pytest.importorskip("fugashi")
    assert Y.scan_sentence("証明を始めます。", "ショオメエオ/ハジメマ'_ス") == []


def test_katakana_words_are_compared_as_written():
    pytest.importorskip("fugashi")
    assert Y.scan_sentence("エーエヌがアルファに収束する。", "エ'エエヌガ/ア'ルファニ/シュウソ_ク'/スル") == []


def test_add_word_replaces_and_keeps_comments(tmp_path):
    p = tmp_path / "yomi.toml"
    p.write_text("# コメント\nwords = [\n  # [\"a\", \"b\"],\n  [\"辺\", \"へん\"],\n]\n")
    import tomllib

    from lecanim.yomi import add_word
    import lecanim.yomi as mod
    mod.scope_path = lambda scope, root=None: p       # テスト用に保存先を差し替え
    add_word("行", "ぎょう", "project", "字下げされた行が")
    add_word("辺", "へん", "project")                  # 既存は置き換え
    txt = p.read_text()
    assert "# コメント" in txt and txt.count("辺") == 1
    ws = tomllib.loads(txt)["words"]
    assert ["行", "ぎょう", "字下げされた行が"] in ws and ["辺", "へん"] in ws


def test_user_words_take_precedence_over_base(monkeypatch):
    from lecanim import voice as V
    monkeypatch.setattr(Y, "user_words", lambda: [("値", "ち")])
    ws = V.words()
    assert ws.index(("値", "ち")) < ws.index(("値", "あたい"))
