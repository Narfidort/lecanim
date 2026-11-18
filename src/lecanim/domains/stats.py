"""数理統計・計量経済の基礎：回帰の幾何，散布図と回帰直線，分布と棄却域，係数の信頼区間，行列の分割.

* `ScatterFitMob(box, xr, yr)`：2変数の散布図＋回帰直線＋残差（最小二乗の直感）．
    scatter(xs, ys) / line(b0, b1) / residuals(xs, ys, b0, b1)
* `ProjectionMob(box)`：N次元空間の中の最小二乗の模式図（平面＝列空間 col(X)，Y の足が Ŷ，
    真上の高さが ε̂）．足 `foot` を動かすと関連する矢印が追従する（残差回帰・過剰定式化などに使う）．
    vec(frm, to, label) / right_angle()
* `BlockMatrixMob()`：行列・ベクトルを矩形として並べる（X=[X1|X2]，Y=Xβ+ε，2×2 の分割行列）．
    col_blocks(specs) / grid2x2(...) / eq(*parts)
* `DistMob(box, xr, yr)`：密度関数のグラフ＋棄却域の塗り＋検定統計量の位置（t/F/χ² 検定の図）．
    density(pdf) / tail(pdf, x0, x1)（棄却域）/ stat_mark(x0, label) / hline(y, label)（水平の参照線）
* `CoefBarMob(box, names, values, se)`：回帰係数の推定値＋信頼区間のバー（実データの表を読む用）．
    star(name) / highlight(name)
* 数値（具体例の assert 用）：ols, projection_matrix, annihilator_matrix, is_idempotent, is_symmetric,
    gls, f_stat, normal_pdf, chi2_pdf, t_pdf, f_pdf
"""

from __future__ import annotations

import math

import numpy as np
from manim import DOWN, RIGHT, UP, UR, Arrow, DashedLine, Dot, Line, Polygon, Rectangle, VGroup

from .. import voice as _voice
from ..layout import Box
from ..plot import AxesMob
from ..style import ACCENT, DIM, FG, MAIN, ORANGE_E, mt
from ..style import label as _label
from ..units import LiveGroup, mark_overlay

__all__ = [
    "ScatterFitMob", "ProjectionMob", "BlockMatrixMob", "DistMob", "CoefBarMob",
    "ols", "projection_matrix", "annihilator_matrix", "is_idempotent", "is_symmetric", "gls", "f_stat",
    "normal_pdf", "chi2_pdf", "t_pdf", "f_pdf",
]

YOMI = [
    ("最小二乗", "さいしょうにじょう"), ("不偏", "ふへん"), ("ガウス・マルコフ", "ガウスマルコフ"),
    ("最良線形不偏推定量", "さいりょうせんけいふへんすいていりょう"), ("一般化最小二乗", "いっぱんかさいしょうにじょう"),
    ("異分散", "いぶんさん"), ("系列相関", "けいれつそうかん"), ("尤度", "ゆうど"), ("対数尤度", "たいすうゆうど"),
    ("スコア関数", "スコアかんすう"), ("ヘッセ行列", "ヘッセぎょうれつ"), ("正定値", "せいていち"),
    ("半正定値", "はんせいていち"), ("負定値", "ふていち"), ("直交対角化", "ちょっこうたいかくか"),
    ("射影行列", "しゃえいぎょうれつ"), ("消去行列", "しょうきょぎょうれつ"), ("べき等", "べきとう"),
    ("漸近", "ぜんきん"), ("一致性", "いっちせい"), ("確率収束", "かくりつしゅうそく"), ("概収束", "がいしゅうそく"),
    ("平均二乗収束", "へいきんにじょうしゅうそく"), ("大数の法則", "たいすうのほうそく"),
    ("中心極限定理", "ちゅうしんきょくげんていり"), ("デルタ法", "デルタほう"), ("スルツキー", "スルツキー"),
    ("クラメール・ウォルド", "クラメールウォルド"), ("リンデベルグ・レヴィ", "リンデベルグレヴィ"),
    ("ラグランジュ乗数", "ラグランジュじょうすう"), ("制約付き", "せいやくつき"), ("過剰定式化", "かじょうていしきか"),
    ("脱落変数", "だつらくへんすう"), ("残差回帰", "ざんさかいき"), ("分割回帰", "ぶんかつかいき"),
    ("決定係数", "けっていけいすう"), ("非中心化", "ひちゅうしんか"), ("骨格", "こっかく"),
    ("小野", "おの"), ("茂木", "もてぎ"),
]
_voice.register_words(YOMI)


# ============================================================ 散布図＋回帰直線
class ScatterFitMob(AxesMob):
    """2変数の散布図＋回帰直線＋残差（K=1 の最小二乗の直感）．軸自体は AxesMob（コア）が作る．"""

    def __init__(self, box: Box | None = None, xr=(0, 1, 0.5), yr=(0, 1, 0.5), x_label="x", y_label="y"):
        super().__init__(box, xr, yr, x_label=x_label, y_label=y_label, numbers="")

    def scatter(self, xs, ys, color=FG, radius=0.06, add=True):
        g = VGroup(*[Dot(self.p(x, y), radius=radius, color=color) for x, y in zip(xs, ys)])
        if add:
            self.add(g)
        return mark_overlay(g)

    def line(self, b0: float, b1: float, color=MAIN, width=3.5, add=True):
        x0, x1 = self.xr[0], self.xr[1]
        L = Line(self.p(x0, b0 + b1 * x0), self.p(x1, b0 + b1 * x1), color=color, stroke_width=width)
        if add:
            self.add(L)
        return mark_overlay(L)

    def residuals(self, xs, ys, b0: float, b1: float, color=ACCENT, width=2.5, add=True):
        g = VGroup(*[DashedLine(self.p(x, y), self.p(x, b0 + b1 * x), color=color, stroke_width=width,
                                dash_length=0.08) for x, y in zip(xs, ys)])
        if add:
            self.add(g)
        return mark_overlay(g)


# ============================================================ 射影の幾何（模式図）
class ProjectionMob(LiveGroup):
    """最小二乗の幾何の模式図：平面＝列空間 col(X)，その上の点が Ŷ＝Xβ̂，真上の高さが ε̂＝Y−Ŷ．
    実際の直交射影ではなく教科書的な模式図（lift 方向を「列空間と直角」とみなす）．
    `foot` を動かすと `vec()` で作った矢印が追従する（分割回帰・過剰定式化などの変化を見せる）．"""

    def __init__(self, box: Box | None = None, w=3.6, depth=2.0, skew=0.7, lift=2.1, foot=(0.35, 0.25)):
        super().__init__()
        box = box or Box.full()
        c = box.center
        self.lift_vec = np.array([0.0, lift, 0.0])
        O = c + np.array([-w / 2, -depth / 2, 0.0])
        p2 = O + np.array([w, 0.0, 0.0])
        p4 = O + np.array([skew, depth, 0.0])
        p3 = p2 + (p4 - O)
        self._O0, self._p2, self._p4 = O, p2, p4
        self.plane = Polygon(O, p2, p3, p4, color=DIM, stroke_width=1.5, fill_color=MAIN, fill_opacity=0.07)
        self.O = Dot(O, radius=0.001, fill_opacity=0)
        self.foot = Dot(self._corner(*foot), radius=0.001, fill_opacity=0)
        self.add(self.plane, self.O, self.foot)

    def _corner(self, fx: float, fy: float) -> np.ndarray:
        return self._O0 + fx * (self._p2 - self._O0) + fy * (self._p4 - self._O0)

    def pO(self) -> np.ndarray:
        return self.O.get_center()

    def pfoot(self) -> np.ndarray:
        return self.foot.get_center()

    def pY(self) -> np.ndarray:
        return self.foot.get_center() + self.lift_vec

    def set_foot(self, fx: float, fy: float):
        """足（Ŷ の位置）を動かすアニメーション．追従する矢印・直角の印も一緒に動く."""
        return self.foot.animate.move_to(self._corner(fx, fy))

    def vec(self, frm, to, color=MAIN, label: str | None = None, direction=UR, width=4.5, add=True):
        """frm, to は pO/pfoot/pY のいずれか（呼ぶと現在位置を返す関数）．"""
        a = Arrow(frm(), to(), buff=0, color=color, stroke_width=width, tip_length=0.22,
                  max_tip_length_to_length_ratio=0.3)
        a.add_updater(lambda m: m.put_start_and_end_on(frm(), to()))
        g = VGroup(a)
        if label:
            lbl = _label(label, size=28, color=color)
            lbl.add_updater(lambda m: m.next_to(a.get_end(), direction, buff=0.12))
            g.add(lbl)
            a._qa_target = lbl    # 矢印の先はラベルのすぐそば（QAの「矢印の先に何もない」対策）
        if add:
            self.add(g)
        return mark_overlay(g)

    def right_angle(self, size=0.2, color=DIM, add=True):
        """足のところにある直角の印（平面の方向と lift 方向）."""
        h = (self._p2 - self._O0) / np.linalg.norm(self._p2 - self._O0) * size
        v = self.lift_vec / np.linalg.norm(self.lift_vec) * size
        def pts():
            f = self.pfoot()
            return [f + v, f + v + h, f + h]
        mk = Line(np.zeros(3), np.zeros(3), color=color, stroke_width=2)
        mk.set_points_as_corners(pts())
        mk.add_updater(lambda m: m.set_points_as_corners(pts()))
        if add:
            self.add(mk)
        return mark_overlay(mk)


# ============================================================ 行列・ベクトルの分割
class BlockMatrixMob(LiveGroup):
    """行列・ベクトルを矩形として並べる（Y=Xβ+ε の次元，X=[X1|X2]，2×2 の分割行列）．
    矩形の幅・高さは呼び出し側が決める任意の数値ではなく，実際の行数・列数から unit で計算する．
    対応する次元（X の列数と β の行数など）に同じ数を渡せば，矩形の大きさが自動的に揃う．
    N のような大きい次元は見た目用の小さい代表値でよいが，対応する辺同士は必ず同じ値にする．"""

    def __init__(self, unit: float = 0.55, min_size: float = 0.85):
        super().__init__()
        self.unit, self.min = unit, min_size

    def _len(self, n: float) -> float:
        return max(self.min, n * self.unit)

    @staticmethod
    def _fit(lbl, box, pad: float = 0.12):
        """ラベルが矩形からはみ出す（列数1本のような細い箱に長い式）ときだけ縮める．"""
        if lbl.width > box.width - 2 * pad:
            lbl.scale_to_fit_width(box.width - 2 * pad)
        if lbl.height > box.height - 2 * pad:
            lbl.scale_to_fit_height(box.height - 2 * pad)
        return lbl

    def col_blocks(self, specs, gap: float = 0.0):
        """specs = [(label, rows, cols, color), ...] を横に並べた1つの行列として描く（境界に細い線）．"""
        g = VGroup()
        for lab, rows, cols, color in specs:
            r = Rectangle(width=self._len(cols), height=self._len(rows), color=color, stroke_width=2,
                          fill_color=color, fill_opacity=0.08)
            lbl = self._fit(_label(lab, size=28, color=FG), r)
            g.add(VGroup(r, lbl))
        g.arrange(RIGHT, buff=gap)
        for cell in g:
            cell[1].move_to(cell[0])
        self.add(g)
        return mark_overlay(g)

    def grid2x2(self, rows, cols, labels, colors=None):
        """2×2 のブロック行列 [[A11,A12],[A21,A22]]．rows=(行数1,行数2), cols=(列数1,列数2)．
        labels は4要素（左上→右上→左下→右下）．"""
        colors = colors or [MAIN] * 4
        r1, r2 = rows
        c1, c2 = cols
        dims = [(r1, c1), (r1, c2), (r2, c1), (r2, c2)]
        cells = []
        for (rn, cn), lab, color in zip(dims, labels, colors):
            r = Rectangle(width=self._len(cn), height=self._len(rn), color=color, stroke_width=2,
                          fill_color=color, fill_opacity=0.08)
            lbl = self._fit(_label(lab, size=26, color=FG), r).move_to(r)
            cells.append(VGroup(r, lbl))
        top = VGroup(cells[0], cells[1]).arrange(RIGHT, buff=0)
        bot = VGroup(cells[2], cells[3]).arrange(RIGHT, buff=0)
        g = VGroup(top, bot).arrange(DOWN, buff=0)
        self.add(g)
        return mark_overlay(g)

    def eq(self, *parts, box: Box | None = None, op_size=34, buff=0.35):
        """parts：col_blocks/grid2x2 が返した VGroup か，"=","+" のような演算子の文字列．
        1つの式として横に並べ，box に収める."""
        box = box or Box.full()
        items = [p if not isinstance(p, str) else _label(p, size=op_size, color=DIM) for p in parts]
        g = VGroup(*items).arrange(RIGHT, buff=buff)
        if g.width > box.width:
            g.scale_to_fit_width(box.width)
        if g.height > box.height:
            g.scale_to_fit_height(box.height)
        g.move_to(box.center)
        self.add(g)
        return mark_overlay(g)


# ============================================================ 分布・棄却域
class DistMob(AxesMob):
    """検定統計量の分布（正規・χ²・F・t）と棄却域．軸自体は AxesMob（コア）が作る．"""

    def __init__(self, box: Box | None = None, xr=(-4, 4, 1), yr=(0, 0.5, 0.1), x_label="z"):
        super().__init__(box, xr, yr, x_label=x_label, y_label=None, numbers="x")

    def density(self, pdf, color=MAIN, x0=None, x1=None, width=3.5, n=240, add=True):
        return self.curve(pdf, color=color, x0=x0, x1=x1, width=width, n=n, add=add)

    def tail(self, pdf, x0: float, x1: float, color=ORANGE_E, opacity=0.35, n=120, add=True):
        """棄却域：x0 から x1 の下の面積を塗る."""
        return self.area(pdf, x0, x1, color=color, opacity=opacity, n=n, add=add)

    def stat_mark(self, x0: float, label: str | None = None, color=ACCENT, add=True):
        """検定統計量の実現値の縦線．label は style.label() と同じ規則（日本語と混ぜてよい．数式は $...$ で囲む）."""
        return self.vline(x0, color=color, label=label, label_dir=UP, size=26, width=2.5, add=add)


# ============================================================ 係数の推定値と信頼区間
class CoefBarMob(LiveGroup):
    """回帰係数の推定値＋信頼区間のバー（実データの回帰表を読む用）．0 の位置に破線."""

    def __init__(self, box: Box | None = None, names=(), values=(), se=(), z: float = 1.96, row_h: float = 0.6,
                label_w: float = 2.3):
        super().__init__()
        box = box or Box.full()
        bl, br, bb, bt = box.lrbt
        lo = min(v - z * s for v, s in zip(values, se))
        hi = max(v + z * s for v, s in zip(values, se))
        pad = (hi - lo) * 0.2 or 1.0
        lo, hi = lo - pad, hi + pad
        x0, x1 = bl + label_w, br
        y_top = bt - 0.3

        def xpos(v):
            return x0 + (x1 - x0) * (v - lo) / (hi - lo)

        axis = Line([x0, bb + 0.2, 0], [x1, bb + 0.2, 0], color=DIM, stroke_width=2)
        zero = DashedLine([xpos(0), bb + 0.1, 0], [xpos(0), y_top, 0], color=DIM, stroke_width=1.5)
        self.add(axis, zero, mt("0", size=20, color=DIM).next_to([xpos(0), bb + 0.1, 0], DOWN, buff=0.08))
        self.rows = {}
        self._y_of = {}
        for i, (name, v, s) in enumerate(zip(names, values, se)):
            y = y_top - i * row_h
            lbl = _label(name, size=24, color=FG).move_to([bl + label_w / 2, y, 0])
            whisker = Line([xpos(v - z * s), y, 0], [xpos(v + z * s), y, 0], color=MAIN, stroke_width=3)
            dot = Dot([xpos(v), y, 0], radius=0.075, color=MAIN)
            g = VGroup(lbl, whisker, dot)
            self.rows[name] = g
            self._y_of[name] = y
            self.add(g)
        self._xpos = xpos

    def star(self, name: str, text: str = "*", color=ACCENT, buff: float = 0.1, add=True):
        dot = self.rows[name][2]
        s = _label(text, size=26, color=color).next_to(dot, UP, buff=buff)
        if add:
            self.add(s)
        return mark_overlay(s)

    def highlight(self, name: str, color=ACCENT) -> list:
        return [self.rows[name].animate.set_color(color)]


# ============================================================ 数値（具体例の assert 用）
def ols(X: np.ndarray, Y: np.ndarray):
    """β̂=(X'X)⁻¹X'Y と残差 ε̂=Y−Xβ̂."""
    beta = np.linalg.solve(X.T @ X, X.T @ Y)
    return beta, Y - X @ beta


def projection_matrix(X: np.ndarray) -> np.ndarray:
    """P_X = X(X'X)⁻¹X'."""
    return X @ np.linalg.solve(X.T @ X, X.T)


def annihilator_matrix(X: np.ndarray) -> np.ndarray:
    """M = I − P_X."""
    return np.eye(X.shape[0]) - projection_matrix(X)


def is_idempotent(M: np.ndarray, tol: float = 1e-8) -> bool:
    return np.allclose(M @ M, M, atol=tol)


def is_symmetric(M: np.ndarray, tol: float = 1e-8) -> bool:
    return np.allclose(M, M.T, atol=tol)


def gls(X: np.ndarray, Y: np.ndarray, Omega: np.ndarray):
    """Ω⁻¹ を使った一般化最小二乗推定量（P'P=Ω⁻¹ を満たす P による変換と同値）."""
    Om_inv = np.linalg.inv(Omega)
    return np.linalg.solve(X.T @ Om_inv @ X, X.T @ Om_inv @ Y)


def f_stat(X: np.ndarray, Y: np.ndarray, R: np.ndarray, c: np.ndarray) -> float:
    """線形制約 Rβ=c の F 検定統計量."""
    N, K1 = X.shape
    r = R.shape[0]
    beta_hat, resid = ols(X, Y)
    s2 = float(resid @ resid) / (N - K1)
    Rb_c = R @ beta_hat - c
    mid = np.linalg.inv(R @ np.linalg.inv(X.T @ X) @ R.T)
    return float(Rb_c @ mid @ Rb_c) / r / s2


def normal_pdf(x: float, mu: float = 0.0, sigma: float = 1.0) -> float:
    return math.exp(-0.5 * ((x - mu) / sigma) ** 2) / (sigma * math.sqrt(2 * math.pi))


def chi2_pdf(x: float, k: float) -> float:
    """対数で計算し指数を取る（k が大きくても math.gamma のオーバーフローを避ける）."""
    if x <= 0:
        return 0.0
    log_p = (k / 2 - 1) * math.log(x) - x / 2 - (k / 2) * math.log(2) - math.lgamma(k / 2)
    return math.exp(log_p)


def t_pdf(x: float, nu: float) -> float:
    log_c = math.lgamma((nu + 1) / 2) - math.lgamma(nu / 2) - 0.5 * math.log(nu * math.pi)
    return math.exp(log_c) * (1 + x ** 2 / nu) ** (-(nu + 1) / 2)


def f_pdf(x: float, d1: float, d2: float) -> float:
    if x <= 0:
        return 0.0
    log_beta = math.lgamma(d1 / 2) + math.lgamma(d2 / 2) - math.lgamma(d1 / 2 + d2 / 2)
    log_f = ((d1 / 2) * math.log(d1 / d2) + (d1 / 2 - 1) * math.log(x)
             - (d1 + d2) / 2 * math.log(1 + d1 * x / d2) - log_beta)
    return math.exp(log_f)
