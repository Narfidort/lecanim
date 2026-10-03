"""配置の部品（分野によらない）: 描画領域 Box, 座標を領域に収める fit, よく使う配置."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

@dataclass
class Box:
    """描画領域 (中心と幅・高さ)."""
    center: np.ndarray
    width: float
    height: float

    @classmethod
    def from_lrbt(cls, l, r, b, t):
        return cls(np.array([(l + r) / 2, (b + t) / 2, 0.0]), r - l, t - b)

    # 本文領域 (ヘッダ ~2.85, 字幕 ~-2.9 の間) の既定分割
    @classmethod
    def full(cls):
        return cls.from_lrbt(-6.7, 6.7, -2.75, 2.3)

    @classmethod
    def left(cls, frac=0.45):
        return cls.from_lrbt(-6.7, -6.7 + 13.4 * frac, -2.75, 2.3)

    @classmethod
    def right(cls, frac=0.55):
        return cls.from_lrbt(6.7 - 13.4 * frac, 6.7, -2.75, 2.3)

    def shrink(self, m: float) -> "Box":
        return Box(self.center, self.width - 2 * m, self.height - 2 * m)

    @property
    def lrbt(self):
        c, w, h = self.center, self.width, self.height
        return c[0] - w / 2, c[0] + w / 2, c[1] - h / 2, c[1] + h / 2


def fit(pos: dict, box: Box, margin: float = 0.45, keep_aspect: bool = True) -> dict:
    """座標 dict を box (余白 margin: ラベル分) に収まるよう平行移動・拡大縮小."""
    P = np.array([np.asarray(p, float)[:2] for p in pos.values()])
    lo, hi = P.min(axis=0), P.max(axis=0)
    span = hi - lo
    W = max(box.width - 2 * margin, 0.1)
    H = max(box.height - 2 * margin, 0.1)
    sx = W / span[0] if span[0] > 1e-6 else None
    sy = H / span[1] if span[1] > 1e-6 else None
    if sx is None and sy is None:
        sx = sy = 1.0
    elif sx is None:
        sx = sy
    elif sy is None:
        sy = sx
    if keep_aspect:
        sx = sy = min(sx, sy)
    mid = (lo + hi) / 2
    out = {}
    for k, p in pos.items():
        q = (np.asarray(p, float)[:2] - mid) * [sx, sy]
        out[k] = np.array([q[0], q[1], 0.0]) + box.center
    return out


def layout_circle(keys, start=90, clockwise=True, radius=1.0) -> dict:
    keys = list(keys)
    s = -1 if clockwise else 1
    return {k: radius * np.array([math.cos(math.radians(start + s * 360 * i / len(keys))),
                                  math.sin(math.radians(start + s * 360 * i / len(keys))), 0])
            for i, k in enumerate(keys)}


def layout_line(keys, spacing=1.0, y=0.0) -> dict:
    keys = list(keys)
    return {k: np.array([i * spacing, y, 0.0]) for i, k in enumerate(keys)}


def layout_bipartite(X, Y, gap=2.0, spacing=1.0, horizontal=False) -> dict:
    pos = {}
    for side, part in ((0, list(X)), (1, list(Y))):
        off = (len(part) - 1) / 2
        for i, k in enumerate(part):
            a, b = side * gap, (off - i) * spacing
            pos[k] = np.array([b, -a, 0.0]) if horizontal else np.array([a, b, 0.0])
    return pos


def layout_groups(groups: list[list], radius=0.6, gap=2.2, inner="circle") -> dict:
    """グループごとに小さな円を作り横に並べる."""
    pos = {}
    for gi, grp in enumerate(groups):
        c = np.array([gi * gap, 0, 0.0])
        sub = layout_circle(grp, radius=radius) if len(grp) > 1 else {grp[0]: np.zeros(3)}
        for k, p in sub.items():
            pos[k] = c + p
    return pos


