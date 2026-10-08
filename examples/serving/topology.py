"""お手本：16 GPU を Prefill と Decode にどう分けるか（律速が入れ替わる）.

配置図を組み替え（reassign），同じ条件の C 掃引を折れ線で重ね，律速の担当に印を付ける例.
数値は Qwen3-235B-A22B FP8・H200 16 枚・ISL4000/OSL200 の実測（AI-Task-Exp の pastrun007〜010・013〜028・041〜042）.
"""

from lecanim import *
from lecanim.domains.serving import *

LEC = "推論サービング"

SLO_ = SLO()

# ---- 配置（すべて 16 GPU を使い切る） --------------------------------
RECIPE = Deployment.pack([("P", 2, 1)] * 6 + [("D", 4, 4)])          # NVIDIA の Hopper 向けレシピ
TWO_TWO = Deployment.pack([("P", 4, 4)] * 2 + [("D", 4, 4)] * 2)
FOUR_TWO = Deployment.pack([("P", 2, 2)] * 4 + [("D", 4, 4)] * 2)
for d in (RECIPE, TWO_TWO, FOUR_TWO):
    assert d.ok and not d.free()
assert (RECIPE.label, TWO_TWO.label, FOUR_TWO.label) == ("6P1D", "2P2D", "4P2D")

# ---- 同じ探索条件（320 要求）での C 掃引：平均 ITL（ms）と全出力 tok/s ------
SW_RECIPE = Sweep("6P1D", [Measurement(32, 0, 1.00, itl_ms=18.7, total_tok_s=1506),
                           Measurement(48, 0, 0.138, itl_ms=20.5, total_tok_s=1969),
                           Measurement(64, 0, 0.034, itl_ms=21.7, total_tok_s=2410),
                           Measurement(96, 0, 0.025, itl_ms=24.3, total_tok_s=2930)])
SW_22 = Sweep("2P2D", [Measurement(32, 0, 1.00, itl_ms=16.22, ttft_ms=229, total_tok_s=1701.89),
                       Measurement(48, 0, 0.95, itl_ms=17.71, ttft_ms=552, total_tok_s=2085.43),
                       Measurement(64, 0, 0.90, itl_ms=17.79, ttft_ms=1916, total_tok_s=2083.89)])
assert SW_RECIPE.first_fail(SLO_).c == 48 and SW_RECIPE.first_fail(SLO_).itl_ms > SLO_.itl_ms
assert all(m.itl_ms < SLO_.itl_ms for m in SW_22.points)             # 2P2D は ITL に余裕
assert SW_22.points[2].total_tok_s <= SW_22.points[1].total_tok_s    # なのに C を上げても伸びない

# ---- 公式条件（60/120/30 秒）・C64 の good output：2P2D → 4P2D -------------
GOOD_22, GOOD_42 = 2371.08, 2829.96
GAIN = GOOD_42 / GOOD_22 - 1
assert abs(GAIN - 0.194) < 0.001


class Topology(LectureScene):
    """16 GPU の分け方 ── 律速が Decode から Prefill へ移る."""
    lecture, topic = LEC, "16 GPU の分け方"
    chapter = "PとDの配分"

    def construct(self):
        self.title_card("16 GPU をどう分けるか", "Prefill と Decode の律速")

        # ================= モチベ ===================
        self.phase("motivation", "同じ16枚でも，分け方で速さが変わる？")
        cm = ClusterMob(RECIPE, box=Box.left(0.5))
        self.play(cm.create())
        self.define("Prefill", "入力4000 token を一度に読む担当（最初の1語までの時間 TTFT を決める）",
                    target=cm.wbox["P0"][0], math=False, short="入力処理")
        self.define("Decode", "1語ずつ200語を生成する担当（1語あたりの時間 ITL を決める）",
                    target=cm.wbox["D0"][0], math=False, short="生成処理")
        self.note("NVIDIA の推奨は Prefill 6 担当，Decode 1 担当（6P1D）")

        # ================= 例1：Decode が律速 ===================
        self.phase("example", "6P1D：同時要求数 C を増やすと")
        ch = ChartMob([24, 104, 16], [14, 26, 2], x_label="同時要求数 C", y_label="平均 ITL（ms）",
                      box=Box.right(0.5))
        self.play(ch.create())
        pts = [(m.c, m.itl_ms) for m in SW_RECIPE.sorted()]
        self.play(*ch.hline("slo", SLO_.itl_ms, "上限 20 ms"))
        self.play(*ch.plot("recipe", pts, color=BLUE_E, label="6P1D",
                           fail=[i for i, m in enumerate(SW_RECIPE.sorted()) if not m.passes(SLO_)]))
        r = ch.ring("recipe", 1)
        self.play(Create(r))
        self.note("C48 で ITL が 20 ms を超え，good率は 14% に落ちる")
        t1 = cm.tag("D0", "律速", RED_E)
        self.play(*cm.highlight(["D0"], RED_E), FadeIn(t1))
        self.note("Decode 1 担当が全要求を生成している → ここが詰まる", wait=1.5)
        self.play(FadeOut(r), FadeOut(t1), *cm.unhighlight())

        # ================= 例2：Prefill が律速 ===================
        self.phase("example", "2P2D：Decode を2担当に増やす")
        self.play(*cm.reassign(TWO_TWO), run_time=1.6)
        pts2 = [(m.c, m.itl_ms) for m in SW_22.sorted()]
        self.play(*ch.plot("22", pts2, color=GREEN_E, label="2P2D"))
        self.note("ITL は C64 でも 17.8 ms と余裕がある")
        self.note("ところが出力は C48 → C64 で 2085 → 2084 tok/s と伸びない")
        t2 = cm.tag("P0", "律速", RED_E)
        self.play(*cm.highlight(["P0", "P1"], RED_E), FadeIn(t2))
        self.note("最初の1語までの時間（TTFT）が 0.55 s → 1.9 s と伸びる → 今度は Prefill が詰まる", wait=1.5)
        self.play(FadeOut(t2), *cm.unhighlight())

        # ================= 例3：両立 ===================
        self.phase("example", "4P2D：Prefill を細かく分けて台数を増やす")
        self.play(*cm.reassign(FOUR_TWO), run_time=1.6)
        self.note("Prefill を TP4 の2担当から TP2 の4担当へ．Decode は TP4 の2担当のまま")
        gain = row(f"good output（C64）：{GOOD_22:,.0f} → {GOOD_42:,.0f} tok/s", size=24, color=YELLOW_E)
        gain2 = row(f"+{GAIN * 100:.1f}%", size=40, color=YELLOW_E)
        box = VGroup(gain, gain2).arrange(DOWN, buff=0.2).move_to(Box.right(0.5).center + DOWN * 0.2)
        self.play(FadeOut(ch))
        self.show(box)
        self.note("公式条件で 2P2D より 19.4% 速い．以後の基本構成になった", wait=1.5)
        self.clear_body()

        self.end_card("Decode 1 担当では ITL が 20 ms を超える（6P1D）",
                      "Decode を増やすと，今度は Prefill の受付が詰まる（2P2D）",
                      "Prefill TP2 で台数を稼ぎ，Decode TP4 を2担当にした 4P2D が両立点",
                      title="観察のまとめ")
