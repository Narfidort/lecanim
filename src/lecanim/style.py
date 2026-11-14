"""色・文字の部品 (日本語と TeX の混在行など)．配色の考え方は docs/STYLE.md §0．"""

from __future__ import annotations

import re as _re

from manim import *  # noqa: F401,F403


# ---------------------------------------------------------------- style
import sys as _sys

from .config import CFG as _CFG

JP_FONT = _CFG["style"]["jp_font"] or ("Hiragino Sans" if _sys.platform == "darwin" else "Noto Sans CJK JP")

# 配色（既定は「深海」トーン．[style] の bg/fg/dim/line/main/accent/corner で上書きできる）：
#   地：BG（背景）・FG（本文）・DIM（副次的な文字）・LINE（罫線）
#   構造：MAIN（見出し・枠など，画面のあちこちに出るが「意味」は持たない色）
#   強調：ACCENT（いまいちばん注目してほしい1点だけに使う色．乱用しない）
# 色分けそのものに意味がある場合（Narfi の Fix/Obtain，グラフの彩色，複数系列のグラフなど）だけ，
# 下の6色を凡例として使う．装飾のための塗り分けには使わない．
_S = _CFG["style"]
BG = _S["bg"]
FG = _S["fg"]
DIM = _S["dim"]
LINE = _S["line"]
MAIN = _S["main"]
ACCENT = _S["accent"]
CORNER = _S["corner"]
CAPTION = FG

# 凡例専用の6色．地と同じ「黒・白・青」の家族（濃淡・彩度違い）で揃え，正誤（GREEN_E/RED_E）だけ例外として
# 本物の緑・赤を残す（✓/✗ のような強い慣習を崩すと分かりにくくなるため）．docs/STYLE.md §0．
BLUE_E = MAIN                 # 既定の凡例色（MAIN と同じ青）
ORANGE_E = "#1E4D73"          # 青のもう1段：MAIN より暗く沈んだ青
PURPLE_E = "#6FB4E0"          # 青のもう1段：MAIN より明るい空色
GREEN_E = "#5FA083"           # 正しい・合格（例外）
RED_E = "#B96A61"             # 誤り・警告（例外）
YELLOW_E = ACCENT
PALETTE = [BLUE_E, ORANGE_E, GREEN_E, RED_E, PURPLE_E, DIM]

# phase() の見出しラベル．数学の証明向けの既定のテンプレ（モチベ→定義・定理→具体例→証明→まとめ）だが，
# これは数あるテンプレの1つ．ここに無いキーはそのまま見出しの文字として使われるので，
# 証明以外の動画（要約・実験記録など）は好きな構成で `phase("自分で決めた見出し", ...)` と呼んでよい．
PHASES = {
    "motivation": "モチベ", "definition": "定義・定理", "example": "具体例", "proof": "証明", "summary": "まとめ",
    "observe": "観察", "question": "問い", "experiment": "実験", "result": "結果",
    "claim": "言えること", "model": "モデル", "check": "照合",
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


# row() が，$...$ で囲まなくても自動で数式として組む「裸の変数」．英字1文字，またはここにある
# 記号1つに，_添字（1文字以上の英数字）を付けたものだけ（検証済みの小さい集合．暴走しないよう最小限にしてある）．
# 前後が英数字・アンダースコアでない所でだけ働くので，"Fix"・"QA" のような英単語には反応しない．
# 地の文に書いた記号がそのまま正しい TeX で組まれる：$...$ を書き忘れても崩れない（docs/STYLE.md §0）．
_SYMBOL_TEX = {
    "α": r"\alpha", "β": r"\beta", "γ": r"\gamma", "δ": r"\delta", "ε": r"\varepsilon", "ζ": r"\zeta",
    "η": r"\eta", "θ": r"\theta", "ι": r"\iota", "κ": r"\kappa", "λ": r"\lambda", "μ": r"\mu", "ν": r"\nu",
    "ξ": r"\xi", "π": r"\pi", "ρ": r"\rho", "σ": r"\sigma", "τ": r"\tau", "φ": r"\varphi", "χ": r"\chi",
    "ψ": r"\psi", "ω": r"\omega",
    "Γ": r"\Gamma", "Δ": r"\Delta", "Θ": r"\Theta", "Λ": r"\Lambda", "Ξ": r"\Xi", "Π": r"\Pi", "Σ": r"\Sigma",
    "Φ": r"\Phi", "Ψ": r"\Psi", "Ω": r"\Omega",
}
_VAR_RE = _re.compile(
    "(?<![A-Za-z0-9_])(" + "[A-Za-z" + "".join(_SYMBOL_TEX) + "]" + r"(?:_[A-Za-z0-9]+)?)(?![A-Za-z0-9_])"
)


def _var_tex(token: str) -> str:
    head, _, sub = token.partition("_")
    head = _SYMBOL_TEX.get(head, head)
    return f"{head}_{{{sub}}}" if sub else head


def _autotex(s: str) -> str:
    """地の文の中の裸の変数（N，ε，a_n など）を見つけて $...$ で囲む．$...$ の外側にだけ使うこと."""
    return _VAR_RE.sub(lambda m: f"${_var_tex(m.group(1))}$", s)


def _autotex_outside_dollars(s: str) -> str:
    pieces = _re.split(r"(\$[^$]*\$)", s)
    return "".join(seg if i % 2 else _autotex(seg) for i, seg in enumerate(pieces))


def row(*parts, size: float = 28, color=FG, buff=0.08, weight=NORMAL) -> VGroup:
    """日本語と数式の混在行.  "$...$" で囲んだ要素は MathTex, それ以外は Text．
    地の文の裸の変数（N, ε, a_n, …）は自動で数式として組まれる（_SYMBOL_TEX／_VAR_RE）．"""
    parts = [_autotex_outside_dollars(p) if isinstance(p, str) else p for p in parts]
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
            mobs.append(jp(p, size=size, color=color, weight=weight))
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


def boxed(m: Mobject, title: str | None = None, color=MAIN, buff=0.3) -> VGroup:
    """定理などを枠で囲む（細い罫線＋ごく薄い塗り．角は CORNER）."""
    rect = SurroundingRectangle(m, buff=buff, color=color, corner_radius=CORNER,
                                stroke_width=1.5)
    rect.set_fill(color, opacity=0.06)
    g = VGroup(rect, m)
    if title:
        t = jp(title, size=22, color=color)
        t.next_to(rect, UP, buff=0.08, aligned_edge=LEFT)
        g.add(t)
    return g


def theorem(title: str, *rows_, color=MAIN) -> VGroup:
    return boxed(lines(*rows_), title=title, color=color)


ECOL = {"r": RED_E, "b": BLUE_E, "g": GREEN_E, "y": YELLOW_E, "p": PURPLE_E, "o": ORANGE_E}
