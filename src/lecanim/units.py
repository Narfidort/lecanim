"""部品の共通の仕組み（分野によらない）.

* LiveGroup: 部品（頂点・辺・ラベルなど）を個別にアニメーションしても, play() の後に
  シーン上で1つのまとまりに戻される VGroup. 分野の描画クラスはこれを継承する.
* mark_overlay: 自動レイアウト検査の対象外にする（ハイライト・囲み・注記など意図的な重ね描き）.
"""

from __future__ import annotations

import weakref

from manim import Mobject, VGroup


class LiveGroup(VGroup):
    instances: "weakref.WeakSet[LiveGroup]" = weakref.WeakSet()

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        LiveGroup.instances.add(self)


def mark_overlay(m: Mobject) -> Mobject:
    for x in m.get_family():
        x._qa_overlay = True
    return m
