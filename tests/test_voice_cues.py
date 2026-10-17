"""台本の合図〔名前〕と発音時刻の予測."""

import pytest

from lecanim import voice as V


def test_prepare_splits_cues_and_strips_them():
    spoken, cues = V.prepare("まず、〔a〕ゴールの先頭を、〔b〕取り外します。")
    assert spoken == "まず、ゴールの先頭を、取り外します。"
    assert [n for n, _ in cues] == ["a", "b"]
    assert cues[0][1] == len("まず、") and cues[1][1] == len("まず、ゴールの先頭を、")
    assert V.yomi("〔a〕こんにちは") == V.yomi("こんにちは")


def test_sentence_cues_are_automatic():
    spoken = "一つ目です。二つ目です。三つ目です。"
    names = [n for n, _ in V._sentence_cues(spoken)]
    assert names == ["s0", "s1", "s2"]


@pytest.mark.skipif(not V.available(2), reason="VOICEVOX が起動していない")
def test_timeline_matches_actual_audio():
    t = "まず、フィックスで、〔head〕ゴールの先頭の、任意の正のイプシロンを、取り外します。〔state〕すると、文脈にイプシロンが入ります。"
    tl = V.timeline(t)
    d = V.duration(V.synth(V.yomi(t)))
    assert abs(tl["duration"] - d) < 0.15                     # 実測の誤差は 0.01〜0.08 秒
    assert 0 < tl["cues"]["head"] < tl["cues"]["state"] < d
    assert not tl["approx"]
