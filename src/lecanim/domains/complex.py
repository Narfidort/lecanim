"""複素関数論・解析学の基礎：複素平面（点・円板・曲線・点列）と実関数のグラフ（ε の帯・関数列）.

* `PlaneMob(box, xr, yr)`：複素平面．`p(z)` で複素数 → 画面座標．部品はすべて平面に追従する
  （平面を動かす・縮めると点や円板も一緒に動く）.
    dot(z, label) / vec(z) / disk(c, r, closed=) / ring(c, r) / curve(f, t0, t1) / seq(zs) / square(c, side)
    polar(z)（絶対値と偏角の印）/ conj(z)（実軸での折り返し）/ region(pred)（条件をみたす点を塗る）
* `PlotMob(box, xr, yr)`：実関数のグラフ．graph(f) / band(f, eps)（ε の帯）/ hband(y, eps) / vline(x) /
  dots(pts)（数列）．関数列 f_n を順に描いて「帯に入るか」を見せる.
* 数値の検証：`radius_cauchy_hadamard(coef, n)`，`series_sum(f, n)` など（具体例の assert 用）.
"""

from __future__ import annotations

import cmath
import math

import numpy as np
from manim import (DL, DOWN, DR, LEFT, RIGHT, UL, UP, UR, Arc, Arrow, Axes, Circle, DashedLine, DashedVMobject, Dot, FadeIn,
                   Line, Polygon, Rectangle, Square, VGroup, VMobject)

from .. import voice as _voice
from ..layout import Box
from ..style import BG, BLUE_E, DIM, FG, GREEN_E, ORANGE_E, PURPLE_E, RED_E, YELLOW_E, mt, row
from ..units import LiveGroup, mark_overlay

__all__ = ["PlaneMob", "PlotMob", "radius_cauchy_hadamard", "partial_sums", "sup_dist"]

YOMI = [
    ("複素数", "ふくそすう"), ("複素", "ふくそ"), ("正則", "せいそく"), ("共役", "きょうやく"), ("偏角", "へんかく"),
    ("整級数", "せいきゅうすう"), ("級数", "きゅうすう"), ("収束半径", "しゅうそくはんけい"),
    ("一様収束", "いちようしゅうそく"), ("一様連続", "いちようれんぞく"), ("広義一様", "こうぎいちよう"),
    ("各点収束", "かくてんしゅうそく"), ("優級数", "ゆうきゅうすう"), ("有界", "ゆうかい"), ("閉包", "へいほう"),
    ("被覆", "ひふく"), ("弧状連結", "こじょうれんけつ"), ("主枝", "しゅし"), ("分枝", "ぶんし"), ("零点", "れいてん"),
    ("集積点", "しゅうせきてん"), ("解析接続", "かいせきせつぞく"), ("項別微分", "こうべつびぶん"),
    ("部分和", "ぶぶんわ"), ("公比", "こうひ"), ("交代級数", "こうたいきゅうすう"), ("部分列", "ぶぶんれつ"), ("内点", "ないてん"), ("外点", "がいてん"),
    ("境界点", "きょうかいてん"), ("閉円板", "へいえんばん"), ("開円板", "かいえんばん"), ("円板", "えんばん"),
    ("近傍", "きんぼう"), ("極形式", "きょくけいしき"), ("虚部", "きょぶ"), ("実部", "じつぶ"), ("虚数", "きょすう"),
    ("正則弧", "せいそくこ"), ("優関数", "ゆうかんすう"), ("極限関数", "きょくげんかんすう"),
    ("Cauchy-Riemann", "コーシーリーマン"), ("Cauchy-Hadamard", "コーシーアダマール"), ("Cauchy", "コーシー"),
    ("Riemann", "リーマン"), ("Weierstrass", "ワイエルシュトラス"), ("Bolzano", "ボルツァーノ"),
    ("Heine-Borel", "ハイネボレル"), ("Heine", "ハイネ"), ("Borel", "ボレル"), ("Hadamard", "アダマール"),
    ("Wirtinger", "ヴィルティンガー"), ("Jordan", "ジョルダン"), ("Laplace", "ラプラス"), ("Euler", "オイラー"),
    ("Maclaurin", "マクローリン"), ("Gauss", "ガウス"), ("ド・モアブル", "ドモアブル"),
    ("sup", "スープ"), ("inf", "インフ"), ("lim", "リミット"),
]
_voice.register_words(YOMI)


def _c(z) -> complex:
    return complex(z)


class PlaneMob(LiveGroup):
    """複素平面. 軸（実軸・虚軸），目盛り，部品．部品は平面の座標に追従する."""

    def __init__(self, box: Box | None = None, xr=(-2, 2), yr=(-2, 2), ticks: float | None = 1.0,
                 labels: bool = True, grid: bool = False, axis_color=DIM, tick_labels: bool = True):
        super().__init__()
        box = box or Box.full()
        self.xr, self.yr = xr, yr
        bl, br, bb, bt = box.lrbt
        sx = (br - bl) / (xr[1] - xr[0])
        sy = (bt - bb) / (yr[1] - yr[0])
        self.unit = min(sx, sy)
        cx = (bl + br) / 2 - self.unit * (xr[0] + xr[1]) / 2
        cy = (bb + bt) / 2 - self.unit * (yr[0] + yr[1]) / 2
        self.origin = Dot([cx, cy, 0], radius=0.001, fill_opacity=0)   # 平面の位置の基準（動かすと部品も動く）
        self.ex = Dot([cx + self.unit, cy, 0], radius=0.001, fill_opacity=0)
        self.add(self.origin, self.ex)
        self.axes = VGroup()
        xa = Arrow(self.p(xr[0]), self.p(xr[1]), buff=0, color=axis_color, stroke_width=2, tip_length=0.15,
                   max_tip_length_to_length_ratio=0.05)
        ya = Arrow(self.p(1j * yr[0]), self.p(1j * yr[1]), buff=0, color=axis_color, stroke_width=2,
                   tip_length=0.15, max_tip_length_to_length_ratio=0.05)
        self.axes.add(xa, ya)
        if grid:
            for k in range(math.ceil(xr[0]), math.floor(xr[1]) + 1):
                self.axes.add(Line(self.p(k + 1j * yr[0]), self.p(k + 1j * yr[1]), color=DIM, stroke_width=0.6,
                                   stroke_opacity=0.35))
            for k in range(math.ceil(yr[0]), math.floor(yr[1]) + 1):
                self.axes.add(Line(self.p(xr[0] + 1j * k), self.p(xr[1] + 1j * k), color=DIM, stroke_width=0.6,
                                   stroke_opacity=0.35))
        if labels:
            self.axes.add(mt(r"\mathrm{Re}", size=24, color=axis_color).next_to(xa.get_end(), DOWN, buff=0.1))
            self.axes.add(mt(r"\mathrm{Im}", size=24, color=axis_color).next_to(ya.get_end(), LEFT, buff=0.1))
        if ticks:
            k = ticks
            while k < xr[1] - 1e-9:
                for v in (k, -k):
                    if xr[0] < v < xr[1]:
                        self.axes.add(Line(self.p(v) + UP * 0.06, self.p(v) + DOWN * 0.06, color=axis_color,
                                           stroke_width=2))
                        if tick_labels:
                            self.axes.add(mt(_num(v), size=20, color=axis_color).next_to(self.p(v), DOWN, buff=0.1))
                k += ticks
            k = ticks
            while k < yr[1] - 1e-9:
                for v in (k, -k):
                    if yr[0] < v < yr[1]:
                        self.axes.add(Line(self.p(1j * v) + LEFT * 0.06, self.p(1j * v) + RIGHT * 0.06,
                                           color=axis_color, stroke_width=2))
                        if tick_labels:
                            self.axes.add(mt(_num(v) + "i" if v not in (1, -1) else ("i" if v > 0 else "-i"),
                                             size=20, color=axis_color).next_to(self.p(1j * v), LEFT, buff=0.1))
                k += ticks
            self.axes.add(mt("O", size=20, color=axis_color).next_to(self.p(0), DL, buff=0.06))
        self.add(self.axes)

    # --- 座標
    def p(self, z) -> np.ndarray:
        z = _c(z)
        o = self.origin.get_center()
        u = np.linalg.norm(self.ex.get_center() - o)
        return o + np.array([z.real * u, z.imag * u, 0])

    def scale_len(self, r: float) -> float:
        return r * np.linalg.norm(self.ex.get_center() - self.origin.get_center())

    def z_of(self, point) -> complex:
        o = self.origin.get_center()
        u = np.linalg.norm(self.ex.get_center() - o)
        return complex((point[0] - o[0]) / u, (point[1] - o[1]) / u)

    def _attach(self, m, add=True):
        if add:
            self.add(m)
        return mark_overlay(m)     # 平面の上に描く部品（重なり検査の対象外）

    # --- 部品（作った mobject を返す．add=False なら平面に入れない）
    def dot(self, z, label: str | None = None, color=YELLOW_E, direction=UR, size=26, radius=0.07, add=True):
        d = Dot(self.p(z), radius=radius, color=color).set_z_index(3)
        g = VGroup(d)
        if label:
            g.add(mt(label, size=size, color=color).next_to(d, direction, buff=0.08))
        return self._attach(g, add)

    def vec(self, z, color=YELLOW_E, start=0, width=4, add=True):
        a = Arrow(self.p(start), self.p(z), buff=0, color=color, stroke_width=width, tip_length=0.18,
                  max_tip_length_to_length_ratio=0.25)
        return self._attach(a, add)

    def seg(self, z1, z2, color=FG, width=3, dashed=False, add=True):
        L = (DashedLine if dashed else Line)(self.p(z1), self.p(z2), color=color, stroke_width=width)
        return self._attach(L, add)

    def disk(self, c, r, closed: bool = False, color=BLUE_E, opacity=0.15, width=2.5, add=True):
        """円板 B(c; r)．開円板は境界を点線，閉円板は実線で描く."""
        circ = Circle(radius=self.scale_len(r), color=color, stroke_width=width).move_to(self.p(c))
        circ.set_fill(color, opacity=opacity)
        if not closed:
            edge = DashedVMobject(circ.copy().set_fill(opacity=0), num_dashes=max(18, int(40 * r)))
            fill = circ.copy().set_stroke(width=0)
            g = VGroup(fill, edge)
        else:
            g = VGroup(circ)
        return self._attach(g, add)

    def ring(self, c, r, color=FG, width=2, dashed=False, add=True):
        circ = Circle(radius=self.scale_len(r), color=color, stroke_width=width).move_to(self.p(c))
        if dashed:
            circ = DashedVMobject(circ, num_dashes=40)
        return self._attach(circ, add)

    def curve(self, f, t0: float, t1: float, color=YELLOW_E, width=4, n=200, add=True):
        """パラメータ曲線 z = f(t) (t0 ≤ t ≤ t1)."""
        ts = np.linspace(t0, t1, n)
        pts = [self.p(f(t)) for t in ts]
        m = VMobject(color=color, stroke_width=width).set_points_smoothly(pts) if n < 400 else \
            VMobject(color=color, stroke_width=width).set_points_as_corners(pts)
        return self._attach(m, add)

    def polyline(self, zs, color=YELLOW_E, width=3, close=False, add=True):
        pts = [self.p(z) for z in zs]
        if close:
            m = Polygon(*pts, color=color, stroke_width=width)
        else:
            m = VMobject(color=color, stroke_width=width).set_points_as_corners(pts)
        return self._attach(m, add)

    def seq(self, zs, color=YELLOW_E, radius=0.05, labels: list[str] | None = None, size=20, add=True):
        """点列（番号が進むほど少し薄く）."""
        g = VGroup()
        for k, z in enumerate(zs):
            d = Dot(self.p(z), radius=radius, color=color).set_z_index(3)
            if labels and k < len(labels) and labels[k]:
                g.add(VGroup(d, mt(labels[k], size=size, color=color).next_to(d, UR, buff=0.04)))
            else:
                g.add(d)
        return self._attach(g, add)

    def square(self, c, side: float, color=BLUE_E, opacity=0.08, width=2, add=True):
        s = Square(side_length=self.scale_len(side), color=color, stroke_width=width).move_to(self.p(c))
        s.set_fill(color, opacity=opacity)
        return self._attach(s, add)

    def polar(self, z, color=ORANGE_E, r_label=r"r", th_label=r"\theta", add=True):
        """原点から z への線分（長さ r）と，実軸からの角（θ）の弧."""
        z = _c(z)
        th = cmath.phase(z)
        seg = Line(self.p(0), self.p(z), color=color, stroke_width=3)
        rad = min(0.6, self.scale_len(abs(z)) * 0.35)
        arc = Arc(radius=rad, start_angle=0, angle=th, color=color, stroke_width=3).move_arc_center_to(self.p(0))
        g = VGroup(seg, arc)
        if r_label:
            g.add(mt(r_label, size=24, color=color).move_to(seg.get_center() + rotate_left(seg) * 0.25))
        if th_label:
            mid = th / 2
            g.add(mt(th_label, size=22, color=color).move_to(self.p(0) + (rad + 0.22) * np.array(
                [math.cos(mid), math.sin(mid), 0])))
        return self._attach(g, add)

    def region(self, pred, color=BLUE_E, opacity=0.25, res: float = 0.06, add=True):
        """条件 pred(z) をみたす点を小さな正方形で塗る（集合の図示用．境界は別に描く）."""
        g = VGroup()
        h = res
        xs = np.arange(self.xr[0] + h / 2, self.xr[1], h)
        ys = np.arange(self.yr[0] + h / 2, self.yr[1], h)
        side = self.scale_len(h)
        for y in ys:
            run = None
            for x in [*xs, None]:
                ok = x is not None and pred(complex(x, y))
                if ok and run is None:
                    run = x
                if not ok and run is not None:
                    x_end = (x if x is not None else xs[-1] + h) - h
                    w = self.scale_len(x_end - run + h)
                    r = Rectangle(width=w, height=side * 1.02, stroke_width=0, fill_color=color, fill_opacity=opacity)
                    r.move_to(self.p(complex((run + x_end) / 2, y)))
                    g.add(r)
                    run = None
        return self._attach(g, add)


def rotate_left(seg: Line) -> np.ndarray:
    d = seg.get_end() - seg.get_start()
    n = np.array([-d[1], d[0], 0])
    return n / (np.linalg.norm(n) + 1e-9)


def _num(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else f"{v:g}"




class PlotMob(LiveGroup):
    """実関数のグラフ（解析学の基礎：数列の収束・関数列の一様収束）."""

    def __init__(self, box: Box | None = None, xr=(0, 1, 0.5), yr=(0, 1, 0.5), x_label="x", y_label="y",
                 tips=False, numbers=True):
        super().__init__()
        box = box or Box.full()
        bl, br, bb, bt = box.lrbt
        self.ax = Axes(x_range=list(xr), y_range=list(yr), x_length=br - bl, y_length=bt - bb,
                       tips=tips, axis_config={"color": DIM, "stroke_width": 2, "include_numbers": False})
        self.ax.move_to([(bl + br) / 2, (bb + bt) / 2, 0])
        self.add(self.ax)
        if numbers:
            nums = VGroup()
            for v in np.arange(xr[0], xr[1] + 1e-9, xr[2]):
                if abs(v) > 1e-9:
                    nums.add(mt(_num(round(v, 6)), size=20, color=DIM).next_to(self.ax.c2p(v, yr[0]), DOWN, 0.1))
            for v in np.arange(yr[0], yr[1] + 1e-9, yr[2]):
                if abs(v) > 1e-9:
                    nums.add(mt(_num(round(v, 6)), size=20, color=DIM).next_to(self.ax.c2p(xr[0], v), LEFT, 0.1))
            self.add(nums)
        if x_label:
            self.add(mt(x_label, size=24, color=DIM).next_to(self.ax.x_axis.get_end(), DR, buff=0.08))
        if y_label:
            self.add(mt(y_label, size=24, color=DIM).next_to(self.ax.y_axis.get_end(), UL, buff=0.08))
        self.xr, self.yr = xr, yr

    def p(self, x, y) -> np.ndarray:
        return self.ax.c2p(x, y)

    def graph(self, f, color=YELLOW_E, x0=None, x1=None, width=3, add=True):
        x0 = self.xr[0] if x0 is None else x0
        x1 = self.xr[1] if x1 is None else x1
        g = self.ax.plot(f, x_range=[x0, x1, (x1 - x0) / 300], color=color, stroke_width=width,
                         use_smoothing=False)
        if add:
            self.add(g)
        return mark_overlay(g)

    def band(self, f, eps, color=GREEN_E, x0=None, x1=None, opacity=0.18, add=True):
        """関数 f のまわりの幅 ε の帯 {(x, y) : |y − f(x)| < ε}."""
        x0 = self.xr[0] if x0 is None else x0
        x1 = self.xr[1] if x1 is None else x1
        xs = np.linspace(x0, x1, 200)
        up = [self.p(x, f(x) + eps) for x in xs]
        dn = [self.p(x, f(x) - eps) for x in xs[::-1]]
        poly = Polygon(*up, *dn, stroke_width=0, fill_color=color, fill_opacity=opacity)
        e1 = VMobject(color=color, stroke_width=1.5).set_points_as_corners(up)
        e2 = VMobject(color=color, stroke_width=1.5).set_points_as_corners(dn)
        g = VGroup(poly, DashedVMobject(e1, num_dashes=40), DashedVMobject(e2, num_dashes=40))
        if add:
            self.add(g)
        return mark_overlay(g)

    def hband(self, y, eps, color=GREEN_E, opacity=0.18, add=True):
        return self.band(lambda x: y, eps, color=color, opacity=opacity, add=add)

    def vline(self, x, color=ORANGE_E, label: str | None = None, add=True):
        L = DashedLine(self.p(x, self.yr[0]), self.p(x, self.yr[1]), color=color, stroke_width=2.5)
        g = VGroup(L)
        if label:
            g.add(mt(label, size=24, color=color).next_to(L, DOWN, buff=0.08))
        if add:
            self.add(g)
        return mark_overlay(g)

    def hline(self, y, color=DIM, label: str | None = None, add=True):
        L = DashedLine(self.p(self.xr[0], y), self.p(self.xr[1], y), color=color, stroke_width=2)
        g = VGroup(L)
        if label:
            g.add(mt(label, size=24, color=color).next_to(L, LEFT, buff=0.08))
        if add:
            self.add(g)
        return mark_overlay(g)

    def dots(self, pts, color=YELLOW_E, radius=0.05, add=True):
        g = VGroup(*[Dot(self.p(x, y), radius=radius, color=color) for x, y in pts])
        if add:
            self.add(g)
        return mark_overlay(g)




# ---------------------------------------------------------------- 数値の検証（具体例の assert 用）
def radius_cauchy_hadamard(coef, n: int = 400) -> float:
    """1/R = limsup |a_n|^{1/n} の数値近似（後半の最大値）."""
    vals = []
    for k in range(n // 2, n):
        a = abs(coef(k))
        vals.append(a ** (1 / k) if a > 0 else 0.0)
    s = max(vals)
    return math.inf if s == 0 else 1 / s


def partial_sums(term, n: int, start: int = 0) -> list:
    out, s = [], 0
    for k in range(start, start + n):
        s += term(k)
        out.append(s)
    return out


def sup_dist(f, g, xs) -> float:
    """sup_x |f(x) − g(x)| を点 xs で近似."""
    return max(abs(f(x) - g(x)) for x in xs)
