"""雛形. シーンの書き方の最小例. 題材に合わせて書き換える."""

from lecanim import *
from lecanim.domains.graph import *

LEC = "（シリーズの題）"

# ---- 具体例はモジュール読み込み時に assert で検証する（間違った例はレンダリング前に落ちる）
K5 = Graph.complete(5)
K5_COL = EdgeColoring(K5, {e: ("r" if (e[1] - e[0]) % 5 in (1, 4) else "b") for e in K5.edges})
assert K5_COL.mono_cliques(3) == []


class Example(LectureScene):
    """定理の主張を，グラフの操作で見せる例."""
    lecture, topic = LEC, "例：単色三角形のない塗り方"
    chapter = "単色三角形のない $K_5$"   # YouTube チャプター名（省略時は topic）

    def construct(self):
        self.title_card("単色三角形を避けられるか", "雛形の例")

        self.phase("motivation", "5人なら避けられる？")
        g = colored_graph_mob(K5_COL, layout_circle(K5.vertices), box=Box.left(0.45), labels=False)
        self.play(g.create())
        self.define("K_5", "5頂点の，どの2つも辺で結んだグラフ", target=g, short="5頂点の完全グラフ")
        self.note("外周を赤，星形を青に塗る")

        self.phase("proof", "10個の三角形を全部調べる")
        for tri in itertools.combinations(K5.vertices, 3):
            f = g.face(tri, YELLOW_E, 0.3)
            self.play(FadeIn(f), run_time=0.2)
            self.play(FadeOut(f), run_time=0.1)
        self.note("どれも赤と青が混ざっている")

        self.end_card("外周を赤，星形を青に塗る",
                      "10個の三角形はどれも2色 → 単色三角形はない")
