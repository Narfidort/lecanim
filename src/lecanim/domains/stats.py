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
from manim import (DL, DOWN, DR, LEFT, RIGHT, UL, UP, UR, Arrow, Axes, DashedLine, DashedVMobject, Dot, Line,
                   Polygon, Rectangle, VGroup)

from .. import voice as _voice
from ..layout import Box
from ..style import ACCENT, DIM, FG, MAIN, ORANGE_E, PURPLE_E, mt, row
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
class ScatterFitMob(LiveGroup):
    """2変数の散布図＋回帰直線＋残差（K=1 の最小二乗の直感）."""

    def __init__(self, box: Box | None = None, xr=(0, 1, 0.5), yr=(0, 1, 0.5), x_label="x", y_label="y"):
        super().__init__()
        box = box or Box.full()
        bl, br, bb, bt = box.lrbt
        self.ax = Axes(x_range=list(xr), y_range=list(yr), x_length=br - bl, y_length=bt - bb,
                       tips=False, axis_config={"color": DIM, "stroke_width": 2, "include_numbers": False})
        self.ax.move_to([(bl + br) / 2, (bb + bt) / 2, 0])
        self.add(self.ax)
        if x_label:
            self.add(mt(x_label, size=24, color=DIM).next_to(self.ax.x_axis.get_end(), DR, buff=0.08))
        if y_label:
            self.add(mt(y_label, size=24, color=DIM).next_to(self.ax.y_axis.get_end(), UL, buff=0.08))
        self.xr, self.yr = xr, yr

    def p(self, x, y) -> np.ndarray:
        return self.ax.c2p(x, y)

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
            lbl = mt(label, size=28, color=color)
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
    """行列・ベクトルを矩形として並べる（Y=Xβ+ε の次元，X=[X1|X2]，2×2 の分割行列）."""

    def __init__(self):
        super().__init__()

    def col_blocks(self, specs, h: float = 2.2, gap: float = 0.0):
        """specs = [(label, width, color), ...] を横に並べた1つの行列として描く（境界に細い線）."""
        g = VGroup()
        for label, w, color in specs:
            r = Rectangle(width=w, height=h, color=color, stroke_width=2, fill_color=color, fill_opacity=0.08)
            lbl = mt(label, size=28, color=FG)
            g.add(VGroup(r, lbl))
        g.arrange(RIGHT, buff=gap)
        for cell in g:
            cell[1].move_to(cell[0])
        self.add(g)
        return mark_overlay(g)

    def grid2x2(self, w1: float, w2: float, h1: float, h2: float, labels, colors=None):
        """2×2 のブロック行列 [[A11,A12],[A21,A22]]．labels は4要素（左上→右上→左下→右下）."""
        colors = colors or [MAIN] * 4
        specs = [(w1, h1), (w2, h1), (w1, h2), (w2, h2)]
        cells = []
        for (w, h), label, color in zip(specs, labels, colors):
            r = Rectangle(width=w, height=h, color=color, stroke_width=2, fill_color=color, fill_opacity=0.08)
            lbl = mt(label, size=26, color=FG).move_to(r)
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
        items = [p if not isinstance(p, str) else mt(p, size=op_size, color=DIM) for p in parts]
        g = VGroup(*items).arrange(RIGHT, buff=buff)
        if g.width > box.width:
            g.scale_to_fit_width(box.width)
        if g.height > box.height:
            g.scale_to_fit_height(box.height)
        g.move_to(box.center)
        self.add(g)
        return mark_overlay(g)


# ============================================================ 分布・棄却域
class DistMob(LiveGroup):
    """検定統計量の分布（正規・χ²・F・t）と棄却域．"""

    def __init__(self, box: Box | None = None, xr=(-4, 4, 1), yr=(0, 0.5, 0.1), x_label="z"):
        super().__init__()
        box = box or Box.full()
        bl, br, bb, bt = box.lrbt
        self.ax = Axes(x_range=list(xr), y_range=list(yr), x_length=br - bl, y_length=bt - bb,
                       tips=False, axis_config={"color": DIM, "stroke_width": 2, "include_numbers": False})
        self.ax.move_to([(bl + br) / 2, (bb + bt) / 2, 0])
        self.add(self.ax)
        nums = VGroup()
        for v in np.arange(xr[0], xr[1] + 1e-9, xr[2]):
            if abs(v) > 1e-9:
                nums.add(mt(_num(v), size=20, color=DIM).next_to(self.ax.c2p(v, yr[0]), DOWN, buff=0.1))
        self.add(nums)
        if x_label:
            self.add(mt(x_label, size=24, color=DIM).next_to(self.ax.x_axis.get_end(), DR, buff=0.08))
        self.xr, self.yr = xr, yr

    def p(self, x, y) -> np.ndarray:
        return self.ax.c2p(x, y)

    def density(self, pdf, color=MAIN, x0=None, x1=None, width=3.5, n=240, add=True):
        x0 = self.xr[0] if x0 is None else x0
        x1 = self.xr[1] if x1 is None else x1
        g = self.ax.plot(pdf, x_range=[x0, x1, (x1 - x0) / n], color=color, stroke_width=width,
                         use_smoothing=False)
        if add:
            self.add(g)
        return mark_overlay(g)

    def hline(self, y: float, color=DIM, label: str | None = None, add=True):
        """水平の参照線（label は row() と同じ規則）．"""
        L = DashedLine(self.p(self.xr[0], y), self.p(self.xr[1], y), color=color, stroke_width=2)
        g = VGroup(L)
        if label:
            g.add(row(label, size=24, color=color).next_to(L, LEFT, buff=0.08))
        if add:
            self.add(g)
        return mark_overlay(g)

    def tail(self, pdf, x0: float, x1: float, color=ORANGE_E, opacity=0.35, n=120, add=True):
        """棄却域：x0 から x1 の下の面積を塗る."""
        xs = np.linspace(x0, x1, n)
        top = [self.p(x, pdf(x)) for x in xs]
        bot = [self.p(x, 0) for x in reversed(xs)]
        poly = Polygon(*top, *bot, stroke_width=0, fill_color=color, fill_opacity=opacity)
        if add:
            self.add(poly)
        return mark_overlay(poly)

    def stat_mark(self, x0: float, label: str | None = None, color=ACCENT, add=True):
        """label は row() と同じ規則（日本語と混ぜてよい．数式は $...$ で囲む）."""
        L = DashedLine(self.p(x0, self.yr[0]), self.p(x0, self.yr[1]), color=color, stroke_width=2.5)
        g = VGroup(L)
        if label:
            g.add(row(label, size=26, color=color).next_to(L, UP, buff=0.08))
        if add:
            self.add(g)
        return mark_overlay(g)


def _num(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else f"{v:g}"


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
            lbl = row(name, size=24, color=FG).move_to([bl + label_w / 2, y, 0])
            whisker = Line([xpos(v - z * s), y, 0], [xpos(v + z * s), y, 0], color=MAIN, stroke_width=3)
            dot = Dot([xpos(v), y, 0], radius=0.075, color=MAIN)
            g = VGroup(lbl, whisker, dot)
            self.rows[name] = g
            self._y_of[name] = y
            self.add(g)
        self._xpos = xpos

    def star(self, name: str, text: str = "*", color=ACCENT, buff: float = 0.1, add=True):
        dot = self.rows[name][2]
        s = row(text, size=26, color=color).next_to(dot, UP, buff=buff)
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
