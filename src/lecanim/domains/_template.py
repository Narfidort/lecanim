"""分野モジュールの雛形（例: 数直線）. コピーして <分野名>.py にし, 中身を書き換える.

設計の約束（CONTRIBUTING.md も参照）
* データ構造（純粋な Python）と描画クラス（LiveGroup の子）を分ける．データ構造には，
  お手本の具体例が主張どおりかを assert で検証するための判定関数を持たせる．
* 描画クラスの操作メソッドは「Animation のリスト」を返す（self.play(*obj.op(...)) で使う）．
* 部品が動いたら付属物（ラベル・囲み・強調線）が追従するよう updater を付ける．
* 意図的な重ね描き（強調・囲み・注記）は mark_overlay() で自動レイアウト検査の対象外にする．
* 分野の用語・人名で VOICEVOX が誤読するものは YOMI に入れて register_words() で登録する．
* __all__ で公開する名前を明示する（star import の名前衝突を防ぐ）．
"""

from __future__ import annotations

import numpy as np
from manim import DOWN, Dot, FadeIn, Line, MathTex, VGroup

from .. import voice as _voice
from ..style import FG, YELLOW_E
from ..units import LiveGroup, mark_overlay

__all__ = ["NumberLineMob"]

YOMI: list[tuple[str, str]] = []      # 例: [("数直線", "すうちょくせん")]
SUSPECT: list[str] = []
_voice.register_words(YOMI, SUSPECT)


class NumberLineMob(LiveGroup):
    """整数の点を並べた数直線. 例: 点を動かす・区間を囲む操作を持たせる."""

    def __init__(self, lo: int, hi: int, unit: float = 1.0, y: float = 0.0):
        super().__init__()
        self.unit = unit
        self.axis = Line([lo * unit, y, 0], [hi * unit, y, 0], color=FG, stroke_width=2)
        self.pts = {k: Dot([k * unit, y, 0], radius=0.08, color=FG) for k in range(lo, hi + 1)}
        self.labels = {k: MathTex(str(k), font_size=26, color=FG).next_to(d, DOWN, buff=0.15)
                       for k, d in self.pts.items()}
        self.add(self.axis, *self.pts.values(), *self.labels.values())

    def mark(self, k: int, color=YELLOW_E) -> list:
        """点 k を強調する（Animation のリストを返す）."""
        ring = mark_overlay(Dot(self.pts[k].get_center(), radius=0.16, color=color, fill_opacity=0.35))
        ring.add_updater(lambda m: m.move_to(self.pts[k].get_center()))
        return [FadeIn(ring)]

    def point(self, k: int) -> np.ndarray:
        return self.pts[k].get_center()


def _demo_group() -> VGroup:
    """テスト用の最小例."""
    return NumberLineMob(0, 5)
