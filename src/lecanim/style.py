"""色・文字の部品 (日本語と TeX の混在行など)."""

from __future__ import annotations

from manim import *  # noqa: F401,F403


# ---------------------------------------------------------------- style
import sys as _sys

from .config import CFG as _CFG

JP_FONT = _CFG["style"]["jp_font"] or ("Hiragino Sans" if _sys.platform == "darwin" else "Noto Sans CJK JP")
BG = "#15161c"
FG = "#ECEFF4"
DIM = "#7b8394"
RED_E = "#ff5d6c"
BLUE_E = "#4ea8ff"
GREEN_E = "#5fd38d"
YELLOW_E = "#ffd166"
PURPLE_E = "#c77dff"
ORANGE_E = "#ff9f43"
PALETTE = [RED_E, BLUE_E, GREEN_E, YELLOW_E, PURPLE_E, ORANGE_E]

PHASES = {
    "motivation": ("モチベ", "#ff9f43"),
    "definition": ("定義・定理", "#4ea8ff"),
    "example": ("具体例", "#5fd38d"),
    "proof": ("証明", "#c77dff"),
    "summary": ("まとめ", "#ffd166"),
}

config.background_color = BG

MathTex.set_default(color=FG)
Tex.set_default(color=FG)

BODY_TOP = 2.85     # ヘッダの下端
GLOSS_Y = 2.62      # 記号メモの帯の y (帯があるとき本文の上端は約 2.35)
BODY_BOTTOM = -2.9  # 字幕の上端


def jp(s: str, size: float = 28, color=FG, weight=NORMAL, **kw) -> Text:
    """日本語テキスト(Pango). size はポイント相当."""
    return Text(s, font=JP_FONT, font_size=size, color=color, weight=weight, **kw)


def mt(s: str, size: float = 36, color=FG, **kw) -> MathTex:
    return MathTex(s, font_size=size, color=color, **kw)


def row(*parts, size: float = 28, color=FG, buff=0.08) -> VGroup:
    """日本語と数式の混在行.  "$...$" で囲んだ要素は MathTex, それ以外は Text."""
    mobs = []
    flat = []
    for p in parts:  # 文字列中の $...$ は数式として分割する
        if isinstance(p, str) and "$" in p and not (p.startswith("$") and p.endswith("$") and p.count("$") == 2):
            for i, seg in enumerate(p.split("$")):
                if seg.strip():
                    flat.append(f"${seg}$" if i % 2 == 1 else seg)
        else:
            flat.append(p)
    for p in flat:
        if isinstance(p, Mobject):
            mobs.append(p)
        elif p.startswith("$") and p.endswith("$"):
            mobs.append(mt(p[1:-1], size=size * 1.25, color=color))
        elif p.strip():
            mobs.append(jp(p, size=size, color=color))
    g = VGroup(*mobs).arrange(RIGHT, buff=buff)
    for m in g:
        m.set_y(g.get_y())
    return g


def lines(*rows_, buff=0.22, aligned=LEFT) -> VGroup:
    """row()/jp() の縦並び. 文字列は row() に通す."""
    ms = []
    for r in rows_:
        if isinstance(r, Mobject):
            ms.append(r)
        elif isinstance(r, (list, tuple)):
            ms.append(row(*r))
        else:
            ms.append(row(r))
    return VGroup(*ms).arrange(DOWN, buff=buff, aligned_edge=aligned)


def boxed(m: Mobject, title: str | None = None, color=BLUE_E, buff=0.3) -> VGroup:
    """定理などを枠で囲む."""
    rect = SurroundingRectangle(m, buff=buff, color=color, corner_radius=0.12,
                                stroke_width=2.5)
    rect.set_fill(color, opacity=0.08)
    g = VGroup(rect, m)
    if title:
        t = jp(title, size=22, color=color, weight=BOLD)
        t.next_to(rect, UP, buff=0.08, aligned_edge=LEFT)
        g.add(t)
    return g


def theorem(title: str, *rows_, color=BLUE_E) -> VGroup:
    return boxed(lines(*rows_), title=title, color=color)


ECOL = {"r": RED_E, "b": BLUE_E, "g": GREEN_E, "y": YELLOW_E, "p": PURPLE_E, "o": ORANGE_E}
