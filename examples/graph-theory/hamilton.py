"""お手本：Ore の定理（ハミルトン閉路の十分条件）.

証明を「ハミルトン道を一直線に伸ばす → 印と枠 → 切って裏返す」というグラフの操作で見せる例.
"""

import itertools

from lecanim import *
from lecanim.domains.graph import *

LEC = "ハミルトン閉路"


def xs(n):
    return [f"x{i}" for i in range(1, n + 1)]


def xlab(keys):
    return {k: f"x_{{{k[1:]}}}" for k in keys}


# ---- 具体例の検証 ------------------------------------------------------
# 三角柱 (K6 から 6-閉路を除いたグラフ): σ2 = 6 = n
PRISM = Graph(range(6), [(0, 1), (1, 2), (0, 2), (3, 4), (4, 5), (3, 5), (0, 3), (1, 4), (2, 5)])
assert PRISM.sigma2() >= PRISM.n
PRISM_HC = PRISM.hamiltonian_cycle()
assert PRISM_HC is not None

# 蝶ネクタイ (三角形2つが1点を共有): σ2 = 4 = n-1 でハミルトン閉路なし → 定理の n は最良
BOWTIE = Graph(range(5), [(0, 1), (1, 2), (0, 2), (2, 3), (3, 4), (2, 4)])
assert BOWTIE.sigma2() == BOWTIE.n - 1 and BOWTIE.hamiltonian_cycle() is None

# 証明で使う「反例の候補」: ハミルトン道 x1..x8 に u=x1, v=x8 からの弦を足したもの
ORE_N = 8
ORE_U_NB = ["x2", "x3", "x4"]
ORE_V_NB = ["x5", "x6", "x7"]
ORE_G = Graph.path(xs(ORE_N))
for z in ORE_U_NB[1:]:
    ORE_G.add_edge("x1", z)
for z in ORE_V_NB[:-1]:
    ORE_G.add_edge(z, "x8")
assert ORE_G.hamiltonian_cycle() is None


def plus(z):
    return f"x{int(z[1:]) + 1}"


assert not set(ORE_U_NB) & {plus(z) for z in ORE_V_NB}


# =====================================================================
# ---- Ore の具体例 (探索で選んだもの: σ2 ≥ n, ハミルトン道の衝突がちょうど1か所) ----
ORE2 = Graph(range(8), [(0, 3), (0, 4), (0, 5), (0, 7), (1, 2), (1, 3), (1, 4), (1, 5), (1, 6), (1, 7), (2, 3),
                        (2, 4), (2, 6), (2, 7), (3, 4), (3, 5), (3, 6), (4, 6), (4, 7), (6, 7)])
PATH = (2, 3, 0, 4, 6, 7, 1, 5)
OU, OV = PATH[0], PATH[-1]
assert ORE2.sigma2() >= ORE2.n and ORE2.is_path(PATH) and not ORE2.has_edge(OU, OV)
_marks_u = {i for i, z in enumerate(PATH) if ORE2.has_edge(OU, z)}
_marks_v = {i + 1 for i, z in enumerate(PATH) if ORE2.has_edge(OV, z)}
COLL = sorted(_marks_u & _marks_v)
assert COLL == [3]
OZ, OZM = PATH[3], PATH[2]
CYC = list(PATH[:3]) + list(PATH[3:][::-1])
assert ORE2.is_hamiltonian_cycle(CYC)


# ---- 辺極大な「反例」の手順の実演用（本物の反例は存在しないので，閉路をもたない実在のグラフで仕組みを見せる）
MAXI = Graph(range(6), [*[(a, b) for a in range(5) for b in range(a + 1, 5)], (0, 5)])   # K5 + ぶら下がり
MAXI_ADDS = [(1, 3), (2, 4), (1, 4)]
MAXI0 = MAXI.copy()
for _e in MAXI_ADDS:
    MAXI0.remove_edge(*_e)
assert MAXI.hamiltonian_cycle() is None
MAXI_MISSING = [(5, x) for x in range(1, 5)]
assert all(not MAXI.has_edge(*e) for e in MAXI_MISSING)
MAXI_HC = {}
for _e in MAXI_MISSING:
    _H = MAXI.copy()
    _H.add_edge(*_e)
    _c = _H.hamiltonian_cycle()
    assert _c is not None and _H.has_edge(*_e)
    MAXI_HC[_e] = _c
_seq, _H = [MAXI0.sigma2()], MAXI0.copy()
for _e in MAXI_ADDS:
    _H.add_edge(*_e)
    assert _H.hamiltonian_cycle() is None
    _seq.append(_H.sigma2())
MAXI_SIGMA = _seq
assert all(a <= b for a, b in zip(_seq, _seq[1:]))          # σ2 は辺を足しても下がらない
MU, MV = 5, 2
_c = MAXI_HC[(MU, MV)]
_i = _c.index(MU)
_c = _c[_i:] + _c[:_i]                                     # u から始める
MAXI_PATH = _c if _c[-1] == MV else [MU] + _c[1:][::-1]
assert MAXI_PATH[0] == MU and MAXI_PATH[-1] == MV and MAXI.is_path(MAXI_PATH) and len(MAXI_PATH) == 6


class Ore(LectureScene):
    """Ore の定理: 道を「回転」させて閉路にする."""
    lecture, topic = LEC, "Oreの定理"

    def construct(self):
        box = Box.from_lrbt(-4.2, 4.2, -2.7, 2.5)

        # ================= モチベ ===================
        self.title_card("Oreの定理", "ハミルトン道を「回転」させて閉路にする")
        self.phase("motivation", "ハミルトン閉路 ＝ 円周に並べ替えられる")
        g = GraphMob(ORE2, layout_nx(ORE2, "spring", seed=3), box=box, labels=False, edge_width=3)
        self.play(g.create())
        self.note("このグラフに「全ての頂点を1回ずつ通って，出発点に戻る一周」はあるだろうか？")
        hc = ORE2.hamiltonian_cycle()
        walker = Dot(g.point(hc[0]), radius=0.17, color=YELLOW_E).set_z_index(5)
        self.overlay(walker)
        trail = g.path_mob(hc, YELLOW_E, width=7, close=True)
        self.play(FadeIn(walker))
        for i in range(len(hc)):
            a, b = hc[i], hc[(i + 1) % len(hc)]
            self.play(walker.animate.move_to(g.point(b)), Create(trail[i]), run_time=0.35)
        self.play(FadeOut(walker))
        self.define("ハミルトン閉路", "全ての頂点をちょうど1回ずつ通って，出発点に戻る閉路（黄色）",
                    target=trail, math=False)
        self.note("あった．閉路の順に頂点を円周へ並べ替えると…")
        self.play(*g.layout_to(fit(layout_circle(hc), box)), run_time=2)
        self.note("閉路はちょうど外周になる．「円周に並べられる」＝ハミルトン閉路がある", wait=2)
        self.clear_body()

        # 蝶ネクタイ: できない
        bt = GraphMob(BOWTIE, {0: [-2, 1], 1: [-2, -1], 2: [0, 0], 3: [2, 1], 4: [2, -1]}, box=box, labels=False)
        self.play(bt.create())
        walker = Dot(bt.point(0), radius=0.17, color=YELLOW_E).set_z_index(5)
        self.overlay(walker)
        self.play(FadeIn(walker))
        for b in [1, 2, 3, 4]:
            self.play(walker.animate.move_to(bt.point(b)), run_time=0.4)
        miss = DashedLine(bt.point(4), bt.point(0), color=RED_E)
        self.overlay(miss)
        self.play(Create(miss))
        self.note("蝶ネクタイ型：右の三角形から左へ戻るには，真ん中をもう一度通るしかない → ない", wait=2)
        self.note("辺が少ないと失敗する．では「どれくらい辺が多ければ」必ずある？")
        self.clear_body()

        # ================= 定義・定理 ===================
        self.phase("definition", "$\\sigma_2$ という数を計算してみる")
        g = GraphMob(ORE2, fit(layout_circle(hc), box), labels=False, edge_width=2.5)
        self.play(g.create(run_time=1))
        self.define("n", "グラフの頂点の数", target=g)
        nums = self.count_up([g[v] for v in hc], run_time_each=0.25)
        self.note("このグラフでは $n=8$")
        self.play(FadeOut(nums))
        x0 = hc[0]
        self.define("d(x)", "頂点 $x$ の次数（$x$ から出ている辺の数）", target=g[x0])
        nums = self.count_up([g[(x0, y)] for y in ORE2.neighbors(x0)], run_time_each=0.3)
        self.note(f"この頂点では $d(x)={ORE2.degree(x0)}$")
        self.play(FadeOut(nums))
        cen = box.center
        degs = VGroup(*[g.annotate(v, str(ORE2.degree(v)), color=YELLOW_E, size=28, buff=0.42,
                                   direction=(g.point(v) - cen) / np.linalg.norm(g.point(v) - cen))
                        for v in ORE2.vertices])
        self.overlay(degs)
        self.play(FadeIn(degs))
        self.note("全ての頂点の次数を黄色で書き込んでおく")
        self.play(*g.layout_to(fit(layout_circle(hc), Box.from_lrbt(-6.6, -1.4, -2.7, 2.2))), run_time=1.2)
        non = [(x, y) for x, y in itertools.combinations(ORE2.vertices, 2) if not ORE2.has_edge(x, y)]
        sx, sy = non[0]
        sample = DashedLine(g.point(sx), g.point(sy), color=PURPLE_E, stroke_width=5)
        self.overlay(sample)
        self.play(Create(sample))
        self.define("非隣接", "2つの頂点の間に辺がないこと（紫の点線のペア）", target=sample, math=False)
        mn = min(ORE2.degree(x) + ORE2.degree(y) for x, y in non)
        sums = VGroup()

        def show_pair():
            self.play(Indicate(sample, color=PURPLE_E), g[sx].animate.scale(1.4), g[sy].animate.scale(1.4))
            self.play(g[sx].animate.scale(1 / 1.4), g[sy].animate.scale(1 / 1.4))

        def show_sum():
            self.play(*[Indicate(d, color=YELLOW_E, scale_factor=1.6) for d, v in zip(degs, ORE2.vertices)
                        if v in (sx, sy)])

        def scan_min():
            for x, y in non:
                dl = DashedLine(g.point(x), g.point(y), color=PURPLE_E, stroke_width=4)
                self.overlay(dl)
                t = mt(f"{ORE2.degree(x)}+{ORE2.degree(y)}={ORE2.degree(x) + ORE2.degree(y)}", size=28,
                       color=PURPLE_E)
                sums.add(t)
                sums.arrange_in_grid(cols=4, buff=(0.35, 0.15)).move_to(RIGHT * 3.0 + DOWN * 1.3)
                self.overlay(t)
                self.play(Create(dl), FadeIn(t), run_time=0.35)
                self.play(FadeOut(dl), run_time=0.12)
            self.play(*[Indicate(t, color=YELLOW_E, scale_factor=1.4) for t, (x, y) in zip(sums, non)
                        if ORE2.degree(x) + ORE2.degree(y) == mn])

        self.play(FadeOut(sample))
        sample = DashedLine(g.point(sx), g.point(sy), color=PURPLE_E, stroke_width=5)
        self.overlay(sample)
        self.play(Create(sample))
        f = self.explain([(r"\sigma_2(G)", "このグラフ $G$ で決まる1つの数", YELLOW_E),
                          ("=",),
                          (r"\min", f"全部の中で一番小さい値（= {mn}）", GREEN_E, scan_min),
                          (r"\{",),
                          ("d(x)+d(y)", "$x$ の次数と $y$ の次数の和", YELLOW_E, show_sum),
                          (":",),
                          (r"xy\notin E(G)", "$x$ と $y$ が非隣接（辺がない）", PURPLE_E, show_pair),
                          (r"\}",)],
                         at=RIGHT * 3.0 + UP * 1.6, size=34, order=[6, 4, 2, 0])
        self.play(FadeOut(sample))
        s2 = mt(rf"\sigma_2(G)={mn}\ \ge\ n=8", size=40, color=YELLOW_E).next_to(f, DOWN, buff=0.35)
        self.show(s2)
        self.define(r"\sigma_2(G)", "非隣接な2頂点の次数和のうち最小のもの", target=s2)
        self.play(FadeOut(sums))
        thm = theorem("定理 [Ore]", row("$n\\ge 3$", "，", "$\\sigma_2(G)\\ge n$"),
                      row("$\\Rightarrow$", "ハミルトン閉路がある"), color=PURPLE_E).next_to(s2, DOWN, buff=0.5)
        self.show(thm)
        self.note("「つながっていないペアは，どれも次数の合計が $n$ 以上」── これが条件", wait=2)
        self.clear_body()

        # ================= 証明 ===================
        self.phase("proof", "① 反例を「辺を足せるだけ足したもの」にとる")
        self.define("反例", "$\\sigma_2(G)\\ge n$ を満たすのに，ハミルトン閉路をもたないグラフ", math=False,
                    short="条件を満たすのに閉路なし")
        self.note("実際には反例は存在しない（それが定理）．以下は手順の仕組みを，閉路をもたない実在のグラフで見せる")
        mbox = Box.from_lrbt(-6.4, -0.8, -2.7, 2.2)
        mpos = {**layout_circle(range(5), radius=1.6), 5: np.array([0.0, 2.9, 0])}
        g = GraphMob(MAXI0, mpos, box=mbox, labels=False, vertex_radius=0.14, edge_width=3.5)
        self.play(g.create())
        sig = mt(f"\\sigma_2={MAXI_SIGMA[0]}", size=40, color=YELLOW_E).move_to(RIGHT * 2.2 + UP * 1.4)
        ok = row("ハミルトン閉路：なし", size=26, color=GREEN_E).next_to(sig, DOWN, buff=0.35)
        self.show(sig, ok)
        self.note("反例に辺を1本ずつ足していく．閉路ができない限り足し続ける", block=False)
        for i, e in enumerate(MAXI_ADDS):
            self.play(*g.add_edge(*e, color=GREEN_E, width=5), run_time=0.8)
            new_sig = mt(f"\\sigma_2={MAXI_SIGMA[i + 1]}", size=40, color=YELLOW_E).move_to(sig)
            self.play(Transform(sig, new_sig), Indicate(ok, color=GREEN_E), run_time=0.6)
        self.wait_voice()
        self.clear_caption()
        self.explain([("\\sigma_2(G+e)", "辺 $e$ を足した後", GREEN_E), ("\\ge",),
                      ("\\sigma_2(G)", "足す前", YELLOW_E)],
                     at=RIGHT * 3.0 + DOWN * 0.5, size=38, keep=False)
        self.note("次数は増えるだけ，非隣接なペアは減るだけ → 最小値 $\\sigma_2$ は下がらない → 条件 $\\sigma_2\\ge n$ は保たれる")
        self.note("足し続ければいつか完全グラフ $K_n$（明らかに閉路あり）になる → その手前で必ず止まる")
        self.play(*[a for e in MAXI_ADDS for a in g.edge_style(g[e], color=DIM, width=3.5)])
        whole = g.blob(list(MAXI.vertices), YELLOW_E, pad=0.45, opacity=0.06)
        self.play(FadeIn(whole))
        self.define("辺極大な反例", "反例のままで，どの辺を足してもハミルトン閉路ができてしまうグラフ", target=whole[0],
                    math=False, short="あと1本でどれも閉路になる反例")
        self.play(FadeOut(whole))

        self.phase("proof", "② 1本足すと閉路 → その辺を外すとハミルトン道")
        self.play(FadeOut(sig), FadeOut(ok))
        self.note("足りない辺を1本足してみる．どれを足しても，ハミルトン閉路ができる", block=False)
        for e in MAXI_MISSING:
            dl = DashedLine(g.point(e[0]), g.point(e[1]), color=YELLOW_E, stroke_width=4)
            self.overlay(dl)
            hc_m = g.path_mob(MAXI_HC[e], YELLOW_E, width=6, close=True)
            self.play(Create(dl), run_time=0.4)
            self.play(Create(hc_m), run_time=0.9)
            self.play(FadeOut(hc_m), FadeOut(dl), run_time=0.3)
        self.wait_voice()
        lu = g.annotate(MU, "u", color=RED_E, size=34, direction=UP, buff=0.42)
        lv = g.annotate(MV, "v", color=BLUE_E, size=34, direction=DOWN, buff=0.42)
        self.play(FadeIn(lu), FadeIn(lv))
        self.note("非隣接な $u, v$ を1組とり，辺 $uv$ を足す")
        self.play(*g.add_edge(MU, MV, color=RED_E, width=6))
        cyc_m = g.path_mob(MAXI_HC[(MU, MV)], YELLOW_E, width=7, close=True)
        self.play(Create(cyc_m), run_time=1.5)
        self.note("できた閉路は必ず辺 $uv$ を通る．通らないなら，足す前からハミルトン閉路があったことになる")
        self.play(Indicate(g[(MU, MV)], color=RED_E, scale_factor=1.3))
        self.note("そこで辺 $uv$ を外すと，$u$ から $v$ まで全頂点を1回ずつ通る道が残る")
        self.play(FadeOut(cyc_m), *g.remove_edge(MU, MV))
        pm0 = g.path_mob(MAXI_PATH, YELLOW_E, width=7)
        self.play(Create(pm0), run_time=1.5)
        self.define("ハミルトン道", "全ての頂点をちょうど1回ずつ通る道（閉じていない）", target=pm0, math=False)
        lp = fit(layout_line(MAXI_PATH), Box.from_lrbt(-6.4, 6.4, -1.0, 0.2), margin=0.1)
        g.set_arcs({e: (0 if abs(MAXI_PATH.index(e[0]) - MAXI_PATH.index(e[1])) == 1 else -1.0)
                    for e in g.graph.edges})
        self.play(*g.layout_to(lp), run_time=2)
        self.note("こうして，両端 $u, v$ が非隣接なハミルトン道が手に入る．しかも $d(u)+d(v)\\ge\\sigma_2\\ge n$")
        self.note("ここからは，条件 $\\sigma_2\\ge n$ を満たすグラフで同じ状況を作り，この道から閉路が作れてしまうことを見る")
        self.clear_body()

        self.phase("proof", "③ $u$ から $v$ へのハミルトン道をまっすぐ伸ばす")
        g = GraphMob(ORE2, fit(layout_circle(hc), box), labels=False, edge_width=3)
        self.play(g.create(run_time=1))
        pm = g.path_mob(PATH, YELLOW_E, width=7)
        self.play(Create(pm), run_time=1.5)
        self.recall("ハミルトン道")
        self.note("条件 $\\sigma_2\\ge n$ を満たすグラフで，両端 $u, v$ が非隣接なハミルトン道をとる")
        line_box = Box.from_lrbt(-6.2, 6.2, -1.2, 0.4)
        line_pos = fit(layout_line(PATH), line_box, margin=0.1)
        chords_u = [(OU, z) for z in ORE2.neighbors(OU) if z != PATH[1]]
        chords_v = [(z, OV) for z in ORE2.neighbors(OV) if z != PATH[-2]]
        arcs = {}
        for a, b in ORE2.edges:
            ia, ib = PATH.index(a), PATH.index(b)
            l, r = (a, b) if ia < ib else (b, a)
            arcs[(l, r)] = 1.3 if OV in (a, b) else -1.3 if OU in (a, b) else -0.9
            if abs(ia - ib) == 1:
                arcs[(l, r)] = 0
        g.set_arcs(arcs)
        self.play(*g.layout_to(line_pos), run_time=2)
        path_edges = GraphMob.pairs_of(PATH)
        others = [e for e in ORE2.edges if OU not in e and OV not in e and
                  e not in path_edges and e[::-1] not in path_edges]
        self.play(FadeOut(pm), *[a for e in others for a in g.edge_style(g[e], opacity=0.06)],
                  *[a for e in path_edges for a in g.edge_style(g[e], color=FG, width=5)])
        lu = g.annotate(OU, "u", color=RED_E, size=34, direction=LEFT, buff=0.4)
        lv = g.annotate(OV, "v", color=BLUE_E, size=34, direction=RIGHT, buff=0.4)
        self.play(FadeIn(lu), FadeIn(lv))
        self.define("u,\\ v", "ハミルトン道の左端と右端（$u$ と $v$ は非隣接）", target=lu)
        self.play(*[a for z in ORE2.neighbors(OU) for a in g.edge_style(g[(OU, z)], color=RED_E, width=5)],
                  *[a for z in ORE2.neighbors(OV) for a in g.edge_style(g[(z, OV)], color=BLUE_E, width=5)])
        du, dv = ORE2.degree(OU), ORE2.degree(OV)
        u_edges = [g[(OU, z)] for z in sorted(ORE2.neighbors(OU), key=PATH.index)]
        v_edges = [g[(z, OV)] for z in sorted(ORE2.neighbors(OV), key=PATH.index)]

        def cnt(es, col):
            def act():
                nums = self.count_up(es, color=col, run_time_each=0.3)
                self.wait(0.5)
                self.play(FadeOut(nums))
            return act

        def cnt_v():
            nums = self.count_up([g[x] for x in PATH], color=GREEN_E, run_time_each=0.2)
            self.wait(0.4)
            self.play(FadeOut(nums))

        self.explain([("d(u)", "$u$ から出る辺（赤）の数", RED_E, cnt(u_edges, RED_E)),
                      ("+",),
                      ("d(v)", "$v$ から出る辺（青）の数", BLUE_E, cnt(v_edges, BLUE_E)),
                      (r"\ge", "$u, v$ は非隣接なペアだから $\\sigma_2(G)$ 以上", YELLOW_E, lambda: self.recall(r"\sigma_2(G)")),
                      (r"\sigma_2(G)", "非隣接ペアの次数和の最小値", PURPLE_E),
                      (r"\ge",),
                      ("n", "頂点の数（$=8$）", GREEN_E, cnt_v)],
                     at=UP * 1.85, size=40, keep=False)
        self.note(f"この例では $d(u)+d(v)={du}+{dv}={du + dv}\\ge 8$", wait=2)

        self.phase("proof", "④ 印をつけて，青を1つ右へずらす")
        sp = line_pos[PATH[1]][0] - line_pos[PATH[0]][0]
        ymark_u = line_box.center[1] + 1.55
        ymark_v = line_box.center[1] - 1.55
        rmarks = VGroup(*[Triangle(color=RED_E, fill_opacity=1).scale(0.13).rotate(PI)
                          .move_to([line_pos[z][0], ymark_u, 0]) for z in ORE2.neighbors(OU)])
        bmarks = VGroup(*[Triangle(color=BLUE_E, fill_opacity=1).scale(0.13)
                          .move_to([line_pos[z][0], ymark_v, 0]) for z in ORE2.neighbors(OV)])
        self.overlay(rmarks, bmarks)
        self.play(LaggedStart(*[GrowFromCenter(m) for m in rmarks], lag_ratio=0.1))
        self.play(LaggedStart(*[GrowFromCenter(m) for m in bmarks], lag_ratio=0.1))
        self.define("▼ / ▲", "▼：$u$ とつながる頂点の上の印 ／ ▲：$v$ とつながる頂点の下の印",
                    target=rmarks, math=False, short="▼ $u$ の隣 ／ ▲ $v$ の隣")
        self.note("青い印▲を，全部「1つ右」の頂点へずらす")
        self.play(bmarks.animate.shift(RIGHT * sp), run_time=1.2)
        slots = VGroup(*[RoundedRectangle(corner_radius=0.1, width=sp * 0.8, height=3.6, color=DIM, stroke_width=1.5)
                         .move_to([line_pos[z][0], line_box.center[1], 0]) for z in PATH[1:]])
        self.overlay(slots)
        self.play(Create(slots))
        self.define("枠", "$u$ 以外の各頂点の場所（灰色の縦長の箱）", target=slots, math=False)

        def cnt_marks():
            nums = self.count_up(list(rmarks) + list(bmarks), run_time_each=0.25)
            self.wait(0.4)
            self.play(FadeOut(nums))

        def cnt_slots():
            nums = self.count_up(list(slots), color=GREEN_E, run_time_each=0.25,
                                 at=lambda m: m.get_top() + DOWN * 0.25)
            self.wait(0.4)
            self.play(FadeOut(nums))

        cnt = self.explain([("d(u)+d(v)", "印（▼と▲）の総数", YELLOW_E, cnt_marks),
                            (r"\ge 8",),
                            (">",),
                            ("7", "枠の数（$=n-1$）", GREEN_E, cnt_slots)],
                           at=UP * 1.95, size=40)
        self.recall("鳩の巣原理") if "鳩の巣原理" in self._gloss_map else None
        k = COLL[0]
        self.play(slots[k - 1].animate.set_stroke(YELLOW_E, width=5).set_fill(YELLOW_E, 0.15))
        self.note("印が8個，枠が7個 → どこかの枠には印が2つ入る（鳩の巣原理）", wait=2)

        self.phase("proof", "⑤ 重なった所で道を切って，裏返してつなぐ")
        zl = g.annotate(OZ, "z", color=YELLOW_E, size=30, direction=DOWN + RIGHT * 0.3, buff=0.45)
        zml = g.annotate(OZM, "z^-", color=YELLOW_E, size=30, direction=DOWN + LEFT * 0.3, buff=0.45)
        self.play(FadeIn(zl), FadeOut(cnt))
        self.define("z", "▼と▲が重なった枠の頂点", target=zl)
        self.play(FadeIn(zml))
        self.define("z^-", "$z$ の1つ左の頂点", target=zml)
        self.note("▼がある → $u$ は $z$ とつながる．▲は1つ右へずらしたもの → $v$ は $z^-$ とつながる", wait=2.5)
        self.play(FadeOut(rmarks), FadeOut(bmarks), FadeOut(slots))
        keep = [(OU, OZ), (OZM, OV)]
        fade = [e for e in ORE2.edges if (OU in e or OV in e) and e not in keep and e[::-1] not in keep
                and e not in path_edges and e[::-1] not in path_edges]
        self.play(*[a for e in fade for a in g.edge_style(g[e], opacity=0.06)],
                  *[a for e in keep for a in g.edge_style(g[e], width=8)])
        self.note("$z^-$ と $z$ の間を切る")
        cut = g[(OZM, OZ)]
        self.play(*g.edge_style(cut, color=RED_E, width=8))
        self.play(*g.edge_style(cut, opacity=0.0))
        self.note("右の部分（$z$ から $v$ まで）を裏返すと，$v$ が $z^-$ の隣に来る")
        right = list(PATH[3:])
        flip = {x: line_pos[right[::-1][i]] for i, x in enumerate(right)}
        flip = {x: line_pos[PATH[3 + i]] for i, x in enumerate(right[::-1])}
        arcs2 = {}
        order = list(PATH[:3]) + right[::-1]
        for a, b in ORE2.edges:
            ia, ib = order.index(a), order.index(b)
            l, r = (a, b) if ia < ib else (b, a)
            arcs2[(l, r)] = 0 if abs(ia - ib) == 1 else (-1.3 if (l, r) == (OU, OZ) or (r, l) == (OU, OZ) else 1.0)
        g.set_arcs(arcs2)
        self.play(*g.layout_to(flip), run_time=2.5)
        self.note("すると $u\\to\\cdots\\to z^-\\to v\\to\\cdots\\to z\\to u$ と一周できる！")
        walker = Dot(g.point(CYC[0]), radius=0.17, color=YELLOW_E).set_z_index(5)
        self.overlay(walker)
        trail = g.path_mob(CYC, YELLOW_E, width=7, close=True)
        self.play(FadeIn(walker))
        for i in range(len(CYC)):
            self.play(walker.animate.move_to(g.point(CYC[(i + 1) % len(CYC)])), Create(trail[i]), run_time=0.35)
        self.play(FadeOut(walker))
        g.set_arcs({})
        self.play(*g.layout_to(fit(layout_circle(CYC), box)), run_time=2)
        self.note("円周に並ぶ ＝ ハミルトン閉路の完成", wait=2)
        self.clear_body()

        self.phase("proof", "⑥ 背理法として書くと")
        texts = ["① 反例 $G$ を「辺を足せるだけ足したもの」にとる",
                 "② 非隣接な $u, v$ に辺を足すとハミルトン閉路 → その辺を外すと $u$-$v$ ハミルトン道",
                 "③ 印は $d(u)+d(v)\\ge n$ 個，枠は $n-1$ 個 → 必ず重なる",
                 "④ 重なった所で裏返す → $G$ 自身にハミルトン閉路 → 反例のはずが矛盾 □"]
        st = lines(*[row(t, color=(GREEN_E if i == 3 else FG)) for i, t in enumerate(texts)]).move_to(UP * 0.3)
        for r_, t in zip(st, texts):
            self.wait_voice(0.1)
            self.speak(t)
            self.show(r_)
            self.wait_voice(0.3) if VOICE_ON else self.wait(1)
        self.note("証明の中身は「印が枠より多いから必ず裏返せる」というだけ", wait=2.5)
        self.clear_body()

        self.phase("example", "条件が足りないと，重ならないことがある")
        bpath = [0, 1, 2, 3, 4]
        assert BOWTIE.is_path(bpath)
        bt = GraphMob(BOWTIE, {0: [-2, 1], 1: [-2, -1], 2: [0, 0], 3: [2, 1], 4: [2, -1]}, box=box, labels=False)
        self.play(bt.create(run_time=1))
        bl = fit(layout_line(bpath), Box.from_lrbt(-5, 5, -1.2, 0.4), margin=0.1)
        bt.set_arcs({(a, b): (0 if abs(bpath.index(a) - bpath.index(b)) == 1 else -1.2) for a, b in BOWTIE.edges})
        self.play(*bt.layout_to(bl), run_time=1.5)
        sp = bl[1][0] - bl[0][0]
        rm = VGroup(*[Triangle(color=RED_E, fill_opacity=1).scale(0.13).rotate(PI).move_to([bl[z][0], 0.9, 0])
                      for z in BOWTIE.neighbors(0)])
        bm = VGroup(*[Triangle(color=BLUE_E, fill_opacity=1).scale(0.13).move_to([bl[z][0] + sp, -1.9, 0])
                      for z in BOWTIE.neighbors(4)])
        self.overlay(rm, bm)
        self.play(FadeIn(rm), FadeIn(bm))
        self.note("蝶ネクタイ（$\\sigma_2=4<5$）：印 4 個，枠 4 個 → 重ならずに収まってしまう", wait=2.5)

        self.end_card("反例を辺極大にとる（$\\sigma_2$ は下がらず，$K_n$ には閉路があるので必ず止まる）",
                      "非隣接な $u, v$ に辺を足すと閉路 → その辺を外すと $u$-$v$ ハミルトン道",
                      "$v$ の印を1つ右へずらすと，印 $\\ge n$ 個・枠 $n-1$ 個 → 重なる",
                      "重なった所で裏返すと $G$ 自身に閉路 → 反例であることに矛盾")
