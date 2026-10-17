"""自動レイアウト検査：文字の重なり・板が文字を覆う・矢印."""

from types import SimpleNamespace

import numpy as np
import pytest
from manim import Arrow, DOWN, Dot, RIGHT, Rectangle, Text, UP, VGroup

from lecanim import qa


def scene(*mobs):
    return SimpleNamespace(mobjects=list(mobs))


def t(s, x=0.0, y=0.0):
    m = Text(s, font_size=24)
    m.move_to([x, y, 0])
    return m


def test_text_overlap_found_and_clear():
    a, b = t("あいうえお", 0, 0), t("かきくけこ", 0.2, 0.05)
    assert any(i.kind == "text" for i in qa.check_all(scene(a, b)))
    far = t("かきくけこ", 0, -2)
    assert not qa.check_all(scene(a, far))


def test_faint_text_ignored():
    a, b = t("あいうえお", 0, 0), t("かきくけこ", 0.1, 0)
    b.set_opacity(0.15)
    assert not qa.check_all(scene(a, b))


def test_plate_covers_text_only_if_drawn_above():
    txt = t("かくれる文字", 0, 0)
    plate = Rectangle(width=3, height=1, fill_color="#000000", fill_opacity=1, stroke_width=0)
    assert any(i.kind == "plate" for i in qa.check_all(scene(txt, plate)))      # 板が後 → 文字を覆う
    assert not any(i.kind == "plate" for i in qa.check_all(scene(plate, txt)))  # 文字が後 → 見える
    own = VGroup(Rectangle(width=3, height=1, fill_color="#000000", fill_opacity=1), t("板の中身"))
    assert not qa.check_all(scene(own))                                          # 組になっていれば問題なし


def test_modal_plate_is_allowed():
    txt = t("かくれる文字")
    plate = Rectangle(width=3, height=1, fill_color="#000000", fill_opacity=1, stroke_width=0)
    plate._qa_modal = True
    assert not qa.check_all(scene(txt, plate))


def test_arrow_target_and_crossing():
    target = Dot([3, 0, 0])
    ok = Arrow([-1, 0, 0], [2.8, 0, 0], buff=0)
    ok._qa_target = target
    assert not [i for i in qa.check_all(scene(target, ok)) if i.kind == "dangling"]
    far = Arrow([-1, 2, 0], [0, 2, 0], buff=0)
    far._qa_target = target
    assert any(i.kind == "dangling" for i in qa.check_all(scene(target, far)))
    wall = t("あいうえおかきくけこさしすせそ", -1.5, 0)
    cross = Arrow([-6, 0, 0], [3, 0, 0], buff=0)
    cross._qa_target = target
    assert any(i.kind == "arrow" for i in qa.check_all(scene(target, wall, cross)))


def test_same_mobject_reachable_twice_is_counted_once():
    a = t("ひとつだけ")
    g = VGroup(a)
    assert not qa.check_all(scene(a, g))
