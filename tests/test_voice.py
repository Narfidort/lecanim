"""読み変換: 実際に見つかった誤読の再発防止."""

import lecanim.domains.graph  # noqa: F401  分野の辞書を登録
from lecanim import voice


def test_tex_and_symbols():
    assert voice.yomi("$K_6$ の辺") == "ケーろくのへん"
    assert voice.yomi("$d(u)+d(v) \\ge n$") == "ディーユープラスディーブイ、以上、エヌ"
    assert "かける" in voice.yomi("$2\\times 2$")


def test_known_misreadings():
    assert voice.yomi("定理2-1") == "定理2の1"
    assert voice.yomi("ハミルトン閉路 ＝ 円周") == "ハミルトンへいろは円周"      # 非形式的な ＝ は「は」
    assert voice.yomi("値と最小値") == "あたいとサイショウチ"
    assert voice.yomi("黄色の括弧") == "きいろのかっこ"
    assert voice.yomi("出次数と次数") == "しゅつじすうとじすう"              # 長い語を先に
    assert voice.yomi("鳩の巣原理") == "はとのす原理"


def test_no_spaces_left():
    assert " " not in voice.yomi("$a + b$ と $c$")


def test_register_words_order():
    voice.register_words([("固有値", "こゆうち")])
    assert voice.yomi("固有値") == "こゆうち"          # 汎用の「値→あたい」より分野の語が先
