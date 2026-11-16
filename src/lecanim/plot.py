"""座標軸つきのグラフの共通部品（分野によらない）．

`AxesMob(box, xr, yr)`：軸・目盛りの数字・軸ラベルと，その上に描く部品
（curve / area / hline / vline / dots）．分野のグラフ（解析の PlotMob，統計の DistMob・ScatterFitMob）は
これを継承して，分野の言葉の操作（ε の帯，棄却域，残差，…）だけを足す．

* 部品は軸に入り，軸を動かすと一緒に動く（`add=False` なら返すだけ）．
* 軸の上に描いた部品は重なり検査の対象外（`mark_overlay`）．
* ラベルは `style.label()` に通すので，日本語・数式のどちらでもよい．
"""

from __future__ import annotations

import numpy as np
from manim import DOWN, DR, LEFT, UL, Axes, DashedLine, Dot, Polygon, VGroup

from .layout import Box
from .style import DIM, FG, MAIN, mt
from .style import label as _label
from .units import LiveGroup, mark_overlay

__all__ = ["AxesMob", "fmt_num"]


def fmt_num(v: float) -> str:
    """目盛りの数字：整数は整数として，それ以外は短く."""
    v = round(float(v), 6)
    return str(int(v)) if v.is_integer() else f"{v:g}"


class AxesMob(LiveGroup):
    """座標軸．xr, yr = (最小, 最大, 目盛りの間隔)．numbers は数字を振る軸（"xy" / "x" / "y" / ""）."""

    def __init__(self, box: Box | None = None, xr=(0, 1, 0.5), yr=(0, 1, 0.5), x_label: str | None = None,
                 y_label: str | None = None, numbers: str = "xy", tips: bool = False):
        super().__init__()
        box = box or Box.full()
        bl, br, bb, bt = box.lrbt
        self.xr, self.yr = xr, yr
        self.ax = Axes(x_range=list(xr), y_range=list(yr), x_length=br - bl, y_length=bt - bb,
                       tips=tips, axis_config={"color": DIM, "stroke_width": 2, "include_numbers": False})
        self.ax.move_to([(bl + br) / 2, (bb + bt) / 2, 0])
        self.add(self.ax)
        nums = VGroup()
        if "x" in numbers:
            for v in np.arange(xr[0], xr[1] + 1e-9, xr[2]):
                if abs(v) > 1e-9:
                    nums.add(mt(fmt_num(v), size=20, color=DIM).next_to(self.ax.c2p(v, yr[0]), DOWN, 0.1))
        if "y" in numbers:
            for v in np.arange(yr[0], yr[1] + 1e-9, yr[2]):
                if abs(v) > 1e-9:
                    nums.add(mt(fmt_num(v), size=20, color=DIM).next_to(self.ax.c2p(xr[0], v), LEFT, 0.1))
        if len(nums):
            self.add(nums)
        if x_label:
            self.add(_label(x_label, size=24, color=DIM).next_to(self.ax.x_axis.get_end(), DR, buff=0.08))
        if y_label:
            self.add(_label(y_label, size=24, color=DIM).next_to(self.ax.y_axis.get_end(), UL, buff=0.08))

    def p(self, x, y) -> np.ndarray:
        """グラフの座標 → 画面の座標."""
        return self.ax.c2p(x, y)

    def _put(self, m, add: bool):
        if add:
            self.add(m)
        return mark_overlay(m)

    # --- 部品（作った mobject を返す．add=False なら軸に入れない）
    def curve(self, f, color=MAIN, x0=None, x1=None, width=3, n=300, add=True):
        """y = f(x) のグラフ（x0 ≤ x ≤ x1．省略時は軸の範囲いっぱい）."""
        x0 = self.xr[0] if x0 is None else x0
        x1 = self.xr[1] if x1 is None else x1
        g = self.ax.plot(f, x_range=[x0, x1, (x1 - x0) / n], color=color, stroke_width=width, use_smoothing=False)
        return self._put(g, add)

    def area(self, f, x0: float, x1: float, color=MAIN, opacity=0.35, n=120, add=True):
        """x0 ≤ x ≤ x1 で，y = f(x) と x 軸のあいだを塗る."""
        xs = np.linspace(x0, x1, n)
        top = [self.p(x, f(x)) for x in xs]
        bot = [self.p(x, 0) for x in reversed(xs)]
        return self._put(Polygon(*top, *bot, stroke_width=0, fill_color=color, fill_opacity=opacity), add)

    def hline(self, y: float, color=DIM, label: str | None = None, width=2, add=True):
        """水平の破線．ラベルは左端の外側."""
        L = DashedLine(self.p(self.xr[0], y), self.p(self.xr[1], y), color=color, stroke_width=width)
        g = VGroup(L)
        if label:
            g.add(_label(label, 24, color).next_to(L, LEFT, buff=0.08))
        return self._put(g, add)

    def vline(self, x: float, color=DIM, label: str | None = None, label_dir=DOWN, size=24, width=2.5, add=True):
        """垂直の破線．ラベルは label_dir（DOWN＝下端の外，UP＝上端の外）."""
        L = DashedLine(self.p(x, self.yr[0]), self.p(x, self.yr[1]), color=color, stroke_width=width)
        g = VGroup(L)
        if label:
            g.add(_label(label, size, color).next_to(L, label_dir, buff=0.08))
        return self._put(g, add)

    def dots(self, pts, color=FG, radius=0.05, add=True):
        """点の集まり．pts = [(x, y), ...]."""
        return self._put(VGroup(*[Dot(self.p(x, y), radius=radius, color=color) for x, y in pts]), add)
