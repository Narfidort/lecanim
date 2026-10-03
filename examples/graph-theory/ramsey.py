"""お手本：R(3,3)=6（6人のパーティー問題）.

頂点を色で仕分ける・鳩の巣原理を玉で見せる・8通りを総当たりする・5人では止まることを見せる例.
"""

import itertools

from lecanim import *
from lecanim.domains.graph import *

LEC = "Ramsey理論"

# 具体例で使う K6 の着色 (単色三角形を含む一般的な例)
K6 = Graph.complete(6)
K6_COL = EdgeColoring(K6, {(0, 1): "r", (0, 2): "b", (0, 3): "r", (0, 4): "b", (0, 5): "b",
                           (1, 2): "r", (1, 3): "b", (1, 4): "b", (1, 5): "r",
                           (2, 3): "b", (2, 4): "r", (2, 5): "b",
                           (3, 4): "r", (3, 5): "b", (4, 5): "r"})
assert len(K6_COL) == 15

# K5 の五角形(赤)+五芒星(青): 単色三角形なし
K5 = Graph.complete(5)
K5_COL = EdgeColoring(K5, {e: ("r" if (e[1] - e[0]) % 5 in (1, 4) else "b") for e in K5.edges})
assert K5_COL.mono_cliques(3) == [], "K5 の例に単色三角形がある"


# =====================================================================
class R33(LectureScene):
    """R(3,3)=6 ── 頂点を仕分けて, 総当たりで見せる."""
    lecture, topic = LEC, "$R(3,3)=6$"

    # ---- 小道具 ------------------------------------------------------
    def recolor(self, g, col, run_time=0.8):
        self.play(*[a for e in col.graph.edges for a in g.edge_style(g[e], color=ECOL[col[e]])],
                  run_time=run_time)

    def flash_tri(self, g, tri, color, hold=0.6):
        f = g.face(tri, color, 0.45)
        self.play(FadeIn(f), *[Indicate(g[v], color=color, scale_factor=1.6) for v in tri], run_time=0.6)
        self.wait(hold)
        return f

    def construct(self):
        K = Graph.complete(6)
        center_box = Box.from_lrbt(-3.2, 3.2, -2.7, 2.25)
        circ = fit(layout_circle(K.vertices), center_box)

        # ================= モチベ：何度塗っても三角形 ===================
        self.title_card("6人いれば，必ず…", "$R(3,3)=6$")
        self.phase("motivation", "どう塗っても単色の三角形が現れる？")
        col = EdgeColoring.random(K, seed=11)
        g = colored_graph_mob(col, circ, labels=False, width=5)
        self.play(g.create())
        self.define("K_6", "6個の頂点（6人）の，どの2つも辺で結んだグラフ", target=g, short="6頂点の完全グラフ")
        e0 = g[(0, 1)]
        self.define("赤 / 青", "辺の色．赤＝知り合い，青＝知らない（各辺どちらか一方）", target=e0, math=False, short="赤＝知り合い，青＝知らない")
        self.note("15本の辺を赤・青で適当に塗る．同じ色だけでできた三角形を探すと…")
        count = VGroup()
        for i, seed in enumerate([11, 23, 37, 41, 58]):
            if i:
                col = EdgeColoring.random(K, seed=seed)
                self.recolor(g, col, run_time=0.6)
            tri = col.mono_cliques(3)[0]
            if i == 0:
                f0 = g.face(tri, ECOL[col[(tri[0], tri[1])]], 0.45)
                self.play(FadeIn(f0))
                self.define("単色三角形", "3本の辺が全部同じ色の三角形（3人とも互いに知り合い／知らない）",
                            target=f0, math=False)
                self.play(FadeOut(f0))
            f = self.flash_tri(g, tri, ECOL[col[(tri[0], tri[1])]], hold=0.3)
            mark = jp("✓", size=36, color=GREEN_E)
            count.add(mark)
            count.arrange(RIGHT, buff=0.2).move_to([5.2, 1.6, 0])
            self.play(FadeOut(f), FadeIn(mark), run_time=0.4)
        self.overlay(count)
        self.note("何度塗り直しても見つかる．たまたま？　それとも必ず？", wait=2)

        # 1人減らすと
        self.note("では5人なら？　1人帰ってもらう")
        self.play(*g.remove_vertex(5), FadeOut(count))
        K5g = Graph.complete(5)
        pent = fit(layout_circle(K5g.vertices), center_box)
        self.play(*g.layout_to({k: pent[k] for k in range(5)}), run_time=1.2)
        self.define("K_5", "5頂点の，どの2つも辺で結んだグラフ", target=g, short="5頂点の完全グラフ")
        self.recolor(g, K5_COL)
        self.note("外周を赤，星形を青に塗ると…　10個の三角形を全部調べる")
        tally = VGroup()
        for tri in itertools.combinations(range(5), 3):
            cs = {K5_COL[(a, b)] for a, b in itertools.combinations(tri, 2)}
            assert len(cs) == 2
            f = g.face(tri, YELLOW_E, 0.25)
            x = jp("✗", size=30, color=RED_E)
            tally.add(x)
            tally.arrange(RIGHT, buff=0.12).move_to([5.2, 1.6, 0])
            self.play(FadeIn(f), FadeIn(x), run_time=0.25)
            self.play(FadeOut(f), run_time=0.15)
        self.overlay(tally)
        self.note("10個とも2色が混ざっている → 5人だと「必ず」とは言えない", wait=2)
        self.clear_body()

        # ================= 定理 ===================
        self.phase("definition", "定理：$R(3,3)=6$")
        thm = theorem("定理", row("$K_6$", "の辺をどう赤青で塗っても，単色の三角形がある"),
                      row("（", "$K_5$", "では避けられる → 6 は最良）"))
        self.show(thm.move_to(UP * 0.3))
        self.note("さっきの実験：6人では毎回見つかり，5人では避けられた．これを「必ず」にする", wait=2)
        self.clear_body()

        # ================= 証明：仕分け ===================
        self.phase("proof", "① 1人に注目し，相手を色で仕分ける")
        col = EdgeColoring.random(K, seed=0)
        g = colored_graph_mob(col, circ, labels={0: "u"}, width=5)
        self.play(g.create())
        u = 0
        reds = [x for x in K.neighbors(u) if col[(u, x)] == "r"]
        blues = [x for x in K.neighbors(u) if col[(u, x)] == "b"]
        assert len(reds) == 2 and len(blues) == 3
        self.define("u", "注目する1人（どの頂点を選んでもよい）", target=g[u])
        self.note("$u$ から出る5本だけを見る（他の辺は一旦うすくする）")
        others = [e for e in K.edges if u not in e]
        self.play(*[a for e in others for a in g.edge_style(g[e], opacity=0.08)])
        self.note("$u$ とのつながりの色で，相手を左右に仕分ける")
        tri_spots = [np.array([1.0, 1.45, 0]), np.array([3.4, 1.45, 0]), np.array([2.2, 0.15, 0])]
        pair_spots = [np.array([1.2, -1.9, 0]), np.array([3.2, -1.9, 0])]
        target = {u: np.array([-4.6, 0.1, 0])}
        for x, p in zip(blues, tri_spots):
            target[x] = p
        for x, p in zip(reds, pair_spots):
            target[x] = p
        self.play(*g.layout_to(target), run_time=2)
        bb = g.blob(blues, BLUE_E, label=row("$u$ と青でつながる", size=21, color=BLUE_E), label_size=26)
        rb = g.blob(reds, RED_E, label=row("$u$ と赤でつながる", size=21, color=RED_E), label_dir=DOWN, label_size=26)
        self.play(FadeIn(bb), FadeIn(rb))

        self.phase("proof", "② 鳩の巣原理：どちらかは3人以上")
        self.define("鳩の巣原理", "5個を2つの箱に分けると，どちらかの箱には3個以上入る", math=False,
                    short="5個を2箱に → どちらかに3個以上")
        u_edges = [g[(u, x)] for x in reds + blues]

        def count_edges():
            nums = self.count_up(u_edges, run_time_each=0.4)
            self.wait(0.6)
            self.play(FadeOut(nums))

        self.explain([("5", "$u$ から出る辺の本数", YELLOW_E, count_edges),
                      (r"\le",),
                      ("2", "赤が2本以下だとすると", RED_E,
                       lambda: self.play(*[Indicate(g[(u, x)], color=RED_E) for x in reds])),
                      ("+",),
                      ("2", "青も2本以下だとすると", BLUE_E,
                       lambda: self.play(*[Indicate(g[(u, x)], color=BLUE_E) for x in blues])),
                      ("=4", "合計4本以下 → 5本と合わない（矛盾）", PURPLE_E)],
                     at=LEFT * 4.2 + UP * 1.7, size=40, keep=False)
        self.note("だから「赤が3本以上」か「青が3本以上」のどちらかは必ず起きる")
        bins = VGroup()
        splits = [(r, 5 - r) for r in range(6)]
        for r, b in splits:
            t = VGroup(*[Dot(radius=0.13, color=RED_E) for _ in range(r)],
                       *[Dot(radius=0.13, color=BLUE_E) for _ in range(b)]).arrange(RIGHT, buff=0.12)
            lab = mt(f"{r}+{b}", size=34)
            line = VGroup(lab, t).arrange(RIGHT, buff=0.25)
            bins.add(line)
        bins.arrange(DOWN, buff=0.16, aligned_edge=LEFT).move_to(LEFT * 4.9 + DOWN * 1.65)
        self.note("5本を赤・青に分ける分け方は6通り．どれも，どちらかの色が3本以上")
        self.overlay(bins)
        self.play(LaggedStart(*[FadeIn(b) for b in bins], lag_ratio=0.15))
        boxes = VGroup()
        for (r, b), line in zip(splits, bins):
            dots = line[1]
            sel = dots[:r] if r >= 3 else dots[r:]
            boxes.add(SurroundingRectangle(VGroup(*sel), color=YELLOW_E, buff=0.05, stroke_width=2))
        self.overlay(boxes)
        self.play(LaggedStart(*[Create(b) for b in boxes], lag_ratio=0.15))
        self.note("黄色の枠：どの分け方でも，同じ色が3本以上ある", wait=1.5)
        self.play(FadeOut(boxes))
        self.wait(1)
        self.play(FadeOut(bins))

        self.phase("proof", "③ 色の入れ替え：多い方を「赤」と呼んでよい")
        self.note("いまは青が3人．赤と青を全部入れ替えても問題は変わらない（単色三角形の有無は同じ）")
        swapped = EdgeColoring(K, {e: ("b" if c == "r" else "r") for e, c in col.items()})
        self.play(*[a for e in K.edges for a in g.edge_style(g[e], color=ECOL[swapped[e]])],
                  bb[0].animate.set_color(RED_E), rb[0].animate.set_color(BLUE_E), run_time=1.2)
        nb1 = row("$u$ と赤でつながる", size=21, color=RED_E).move_to(bb[1])
        nr1 = row("$u$ と青でつながる", size=21, color=BLUE_E).move_to(rb[1])
        bb[1].clear_updaters()
        rb[1].clear_updaters()
        self.play(Transform(bb[1], nb1), Transform(rb[1], nr1))
        col = swapped
        A = blues  # 3人のグループ (u と赤でつながる)
        self.wait(1)

        self.phase("proof", "④ 3人 $a, b, c$ の間の3本は何色？")
        names = dict(zip(A, "abc"))
        cA = np.mean([g.point(x) for x in A], axis=0)
        labs = self.overlay(VGroup(*[g.annotate(x, names[x], color=FG, size=30, buff=0.62,
                                   direction=(g.point(x) - cA) / np.linalg.norm(g.point(x) - cA)) for x in A]))
        self.play(FadeIn(labs), FadeOut(rb), *[a for x in reds for a in [g[x].animate.set_opacity(0.15)]],
                  *[a for x in reds for a in g.edge_style(g[(u, x)], opacity=0.08)])
        self.define("a, b, c", "$u$ と赤でつながる3人", target=bb[0])
        inner = list(itertools.combinations(A, 2))
        self.play(*[a for e in inner for a in g.edge_style(g[e], color=DIM, opacity=1, width=5)])
        self.note("残る謎は $a, b, c$ の間の3本（灰色）の色だけ")

        def try_edge(e):
            def act():
                self.play(*g.edge_style(g[e], color=RED_E, width=8), run_time=0.4)
                self.play(*g.edge_style(g[e], color=BLUE_E), run_time=0.4)
                self.play(*g.edge_style(g[e], color=DIM, width=5), run_time=0.3)
            return act

        en = {e: names[e[0]] + names[e[1]] for e in inner}
        self.explain([("2", f"辺 ${en[inner[0]]}$ の色：赤か青の2通り", YELLOW_E, try_edge(inner[0])),
                      (r"\times",),
                      ("2", f"辺 ${en[inner[1]]}$ の色：2通り", YELLOW_E, try_edge(inner[1])),
                      (r"\times",),
                      ("2", f"辺 ${en[inner[2]]}$ の色：2通り", YELLOW_E, try_edge(inner[2])),
                      ("=8", "3本の塗り方は全部で8通り", GREEN_E)],
                     at=LEFT * 4.2 + UP * 1.7, size=40, keep=False)
        self.note("8通りしかないので，全部試してみる")

        # 8 通りのサムネイル
        thumbs = VGroup()
        for i in range(8):
            box = RoundedRectangle(corner_radius=0.08, width=1.05, height=0.95, color=DIM, stroke_width=1.5)
            thumbs.add(box)
        thumbs.arrange_in_grid(2, 4, buff=0.15).move_to(LEFT * 4.3 + DOWN * 2.15).scale(0.95)
        self.overlay(thumbs)
        self.play(FadeIn(thumbs))
        tp = [np.array([-0.3, 0.25, 0]), np.array([0.3, 0.25, 0]), np.array([0, -0.25, 0])]
        for i, bits in enumerate(itertools.product("rb", repeat=3)):
            cs = dict(zip(inner, bits))
            self.play(*[a for e in inner for a in g.edge_style(g[e], color=ECOL[cs[e]])], run_time=0.35)
            red_inner = [e for e in inner if cs[e] == "r"]
            if red_inner:
                tri, color = (u, *red_inner[0]), RED_E
            else:
                tri, color = tuple(A), BLUE_E
            f = g.face(tri, color, 0.45)
            # サムネイル
            mini = VGroup(*[Line(tp[A.index(a)], tp[A.index(b)], color=ECOL[cs[(a, b)]], stroke_width=3)
                            for a, b in inner]).move_to(thumbs[i]).shift(UP * 0.05)
            ok = jp("✓", size=20, color=GREEN_E).next_to(thumbs[i].get_corner(DR), UL, buff=0.03)
            self.overlay(mini, ok)
            self.play(FadeIn(f), FadeIn(mini), FadeIn(ok), run_time=0.35)
            self.wait(0.25 if i else 1.0)
            if i == 0:
                self.note("赤い辺が1本でもあれば，$u$ と合わせて赤い三角形")
            if i == 7:
                self.note("全部青なら，$a, b, c$ 自身が青い三角形")
                self.wait(1.2)
            self.play(FadeOut(f), run_time=0.2)
        self.note("8通りすべてで単色三角形が見つかった．つまり $K_6$ なら必ずある □", wait=2.5)
        self.clear_body()

        # ================= 繰り返し：別の塗り方でも同じ手順 ===================
        self.phase("example", "別の塗り方でも，同じ手順で必ず見つかる")
        for it, seed in enumerate((5, 17)):
            col = EdgeColoring.random(K, seed=seed)
            g = colored_graph_mob(col, circ, labels={0: "u"}, width=5)
            self.speak("別の塗り方でも，$u$ を選んで，色で仕分けて，3人組の中を見るだけ。" if it == 0
                       else "もう一度。手順はまったく同じ。")
            self.play(g.create(run_time=1))
            r_ = [x for x in K.neighbors(0) if col[(0, x)] == "r"]
            b_ = [x for x in K.neighbors(0) if col[(0, x)] == "b"]
            big, small, bc = (r_, b_, "r") if len(r_) >= 3 else (b_, r_, "b")
            self.play(*[a for e in K.edges if 0 not in e for a in g.edge_style(g[e], opacity=0.08)], run_time=0.5)
            target = {0: np.array([-4.6, 0.1, 0])}
            spots = tri_spots + [np.array([4.4, 0.9, 0]), np.array([4.4, -0.3, 0])]
            for x, p in zip(big, spots):
                target[x] = p
            for x, p in zip(small, pair_spots):
                target[x] = p
            self.play(*g.layout_to(target), run_time=1.2)
            blob = g.blob(big, ECOL[bc])
            self.play(FadeIn(blob), run_time=0.4)
            inner = list(itertools.combinations(big, 2))
            self.play(*[a for e in inner for a in g.edge_style(g[e], opacity=1)], run_time=0.5)
            same = [e for e in inner if col[e] == bc]
            if same:
                tri, color = (0, *same[0]), ECOL[bc]
            else:
                cl = Graph(big, [e for e in inner if col[e] != bc]).cliques(3)
                tri, color = cl[0], ECOL["b" if bc == "r" else "r"]
            assert len({col[e] for e in itertools.combinations(tri, 2)}) == 1
            f = self.flash_tri(g, tri, color, hold=1.0)
            self.wait_voice()
            self.clear_body()

        # ================= 5人だと止まる ===================
        self.phase("example", "5人だと，どこで止まるか")
        g = colored_graph_mob(K5_COL, fit(layout_circle(K5.vertices), center_box), labels={0: "u"}, width=5)
        self.play(g.create(run_time=1))
        self.play(*[a for e in K5.edges if 0 not in e for a in g.edge_style(g[e], opacity=0.08)])
        r_ = [x for x in K5.neighbors(0) if K5_COL[(0, x)] == "r"]
        b_ = [x for x in K5.neighbors(0) if K5_COL[(0, x)] == "b"]
        target = {0: np.array([-4.6, 0.1, 0])}
        for x, p in zip(r_, pair_spots):
            target[x] = p
        for x, p in zip(b_, [np.array([1.2, 1.7, 0]), np.array([3.2, 1.7, 0])]):
            target[x] = p
        self.play(*g.layout_to(target), run_time=1.5)
        self.play(FadeIn(g.blob(r_, RED_E)), FadeIn(g.blob(b_, BLUE_E)))
        self.note("$u$ から4本しかない → 2人と2人に分かれてしまい，「3人のグループ」が作れない", wait=2.5)
        self.play(*g.unfade())
        self.note("実際，この塗り方には単色三角形がない．6人目がいることが証明の要", wait=2.5)

        self.end_card("1人 $u$ に注目し，相手を「$u$ と赤」「$u$ と青」に仕分ける",
                      "5人を2組に分ければ，どちらかは3人以上（鳩の巣）",
                      "色を入れ替えて，3人組を「赤」としてよい",
                      "3人の間の3本は8通り：赤があれば $u$ と赤三角形，なければ3人で青三角形",
                      "4本（5人）だと $2+2$ に分かれて止まる → 6 が最良")
