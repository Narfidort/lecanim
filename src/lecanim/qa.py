"""自動レイアウト検査（幾何だけで判定する．描画は要らない）.

人が動画を見て指摘していた不具合を，書き出しの前に機械で見つけるための検査：
  * 文字どうしの重なり（Text / MathTex の外接矩形．ハイライトとして除外してよいのは図形だけで，文字は除外しない）
  * 吹き出しなどの不透明な板が，別の文字を覆っている
  * 矢印が，指す対象（`_qa_target`）や近くの物に届いていない／途中で文字を横切っている
  * 画面外

`LectureScene` が各 play の終わりと（QA モードでは）play の途中の数点で呼ぶ．
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from manim import (Arrow, BackgroundRectangle, CurvedArrow, CurvedDoubleArrow, DoubleArrow, MathTex, Rectangle,
                   SingleStringMathTex, Tex, Text, VMobject)

TEXT_TYPES = (Text, SingleStringMathTex, MathTex, Tex)
ARROW_TYPES = (Arrow, DoubleArrow, CurvedArrow, CurvedDoubleArrow)
PLATE_TYPES = (Rectangle, BackgroundRectangle)

MIN_TEXT_OPACITY = 0.3      # これより薄い文字（薄く置いた地図など）は数えない


@dataclass
class Item:
    kind: str                    # text / arrow / plate / shape
    name: str
    l: float
    r: float
    b: float
    t: float
    op: float
    obj: object
    owner: int | None = None     # 同じ組（吹き出しの板と中身の文字など）を表す番号
    modal: bool = False          # 意図的に他を覆う（作業台など）
    allow: bool = False          # 文字の重なりを許す（遷移中など）
    z: tuple = (0, 0)            # 描かれる順（z_index，上から順の通し番号）．後のものが上に描かれる
    top: str = ""                # 上位の部品の型（デバッグ用）

    @property
    def area(self) -> float:
        return max(self.r - self.l, 0) * max(self.t - self.b, 0)

    def label(self) -> str:
        return self.name


def _opacity(m, text: bool) -> float:
    ops = []
    for x in m.family_members_with_points():
        try:
            f = float(x.get_fill_opacity())
            s = float(x.get_stroke_opacity()) if (not text and x.get_stroke_width() > 0) else 0.0
        except Exception:                                    # noqa: BLE001
            continue
        ops.append(max(f if (text or f > 0) else 0.0, s))
    return max(ops) if ops else 0.0


def _bbox(m, min_op: float = 0.05):
    pts = []
    for x in m.family_members_with_points():
        try:
            if max(float(x.get_fill_opacity()), float(x.get_stroke_opacity())) <= min_op:
                continue
        except Exception:                                    # noqa: BLE001
            pass
        if len(x.points):
            pts.append(x.points[:, :2])
    if not pts:
        return None
    p = np.concatenate(pts)
    return float(p[:, 0].min()), float(p[:, 0].max()), float(p[:, 1].min()), float(p[:, 1].max())


def _text_of(m) -> str:
    if isinstance(m, Text):
        return m.text[:16]
    try:
        return "$" + m.get_tex_string()[:18] + "$"
    except Exception:                                        # noqa: BLE001
        return type(m).__name__


def collect(scene, skip_ids=()) -> list[Item]:
    """シーン上の見えている部品を，文字・矢印・板・図形に分けて集める."""
    items: list[Item] = []
    skip = set(skip_ids)
    seq = [0]
    seen: set[int] = set()          # 同じ部品が2か所（シーン直下と，ある VGroup の中）から届くことがある

    def z_of(m):
        seq[0] += 1
        return (getattr(m, "z_index", 0), seq[0])

    def visit(m, owner, modal, allow):
        if id(m) in skip or id(m) in seen:
            return
        seen.add(id(m))
        modal = modal or getattr(m, "_qa_modal", False)
        allow = allow or getattr(m, "_qa_allow", False)
        if isinstance(m, TEXT_TYPES) or type(m).__name__ == "MathTexPart":
            op = _opacity(m, True)
            bb = _bbox(m) if op > 0.05 else None
            if bb:
                items.append(Item("text", _text_of(m), *bb, op, m, owner, modal, allow, z_of(m)))
            return
        if isinstance(m, ARROW_TYPES):
            op = _opacity(m, False)
            bb = _bbox(m) if op > 0.05 else None
            if bb:
                items.append(Item("arrow", type(m).__name__, *bb, op, m, owner, modal, allow, z_of(m)))
            return
        if isinstance(m, PLATE_TYPES) and not m.submobjects:
            try:
                fo = float(m.get_fill_opacity())
            except Exception:                                # noqa: BLE001
                fo = 0.0
            bb = _bbox(m) if fo > 0.05 else None
            if bb and fo >= 0.5:
                items.append(Item("plate", type(m).__name__, *bb, fo, m, owner, modal, allow, z_of(m)))
            return
        if m.submobjects:
            for c in m.submobjects:
                # 板と中身が同じ VGroup に入っていれば「組」（吹き出し）．組の番号は親の id
                visit(c, id(m), modal, allow)
            return
        if len(m.points):
            op = _opacity(m, False)
            bb = _bbox(m) if op > 0.05 else None
            if bb:
                items.append(Item("shape", type(m).__name__, *bb, op, m, owner, modal, allow, z_of(m)))

    for m in scene.mobjects:
        n0 = len(items)
        visit(m, None, False, False)
        for it in items[n0:]:
            it.top = type(m).__name__
    return items


def _overlap(a: Item, b: Item):
    ox = min(a.r, b.r) - max(a.l, b.l)
    oy = min(a.t, b.t) - max(a.b, b.b)
    return ox, oy


@dataclass
class Issue:
    kind: str            # text / plate / arrow / dangling / offscreen
    msg: str
    boxes: list = field(default_factory=list)   # [(l, r, b, t)] 問題の場所（画像に赤枠を描く）

    @property
    def key(self) -> str:
        return self.msg


def check_text_overlap(items: list[Item]) -> list[Issue]:
    out = []
    texts = [i for i in items if i.kind == "text" and i.op >= MIN_TEXT_OPACITY and not i.allow]
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            a, b = texts[i], texts[j]
            if a.owner is not None and a.owner == b.owner and a.kind == b.kind and False:
                continue
            ox, oy = _overlap(a, b)
            if ox > 0.05 and oy > 0.05:
                ratio = ox * oy / max(min(a.area, b.area), 1e-6)
                if ratio > 0.15:
                    dbg = f" [{a.top}/{b.top}]" if __import__("os").environ.get("LECANIM_QA_DEBUG") else ""
                    out.append(Issue("text", f"文字の重なり: {a.label()} × {b.label()}{dbg}",
                                     [(a.l, a.r, a.b, a.t), (b.l, b.r, b.b, b.t)]))
    return out


def check_plates(items: list[Item]) -> list[Issue]:
    """不透明な板（吹き出しの背景など）が，その組以外の文字を覆っていないか."""
    out = []
    plates = [i for i in items if i.kind == "plate" and not i.modal and i.op >= 0.6]
    texts = [i for i in items if i.kind == "text" and i.op >= MIN_TEXT_OPACITY]
    for p in plates:
        for t in texts:
            if (t.owner is not None and t.owner == p.owner) or t.modal or not (p.z > t.z):
                continue                                   # 板より上に描かれる文字は覆われない
            ox, oy = _overlap(p, t)
            if ox > 0.05 and oy > 0.05 and ox * oy / max(t.area, 1e-6) > 0.25:
                out.append(Issue("plate", f"板が文字を覆っている: {t.label()}", [(p.l, p.r, p.b, p.t),
                                                                          (t.l, t.r, t.b, t.t)]))
    return out


def _path(arrow, n=24) -> np.ndarray:
    try:
        return np.array([arrow.point_from_proportion(a)[:2] for a in np.linspace(0, 1, n)])
    except Exception:                                        # noqa: BLE001
        return np.array([arrow.get_start()[:2], arrow.get_end()[:2]])


def _dist_to_box(p, l, r, b, t) -> float:
    dx = max(l - p[0], 0, p[0] - r)
    dy = max(b - p[1], 0, p[1] - t)
    return float(np.hypot(dx, dy))


def check_arrows(items: list[Item]) -> list[Issue]:
    out = []
    arrows = [i for i in items if i.kind == "arrow" and i.op >= 0.5]
    others = [i for i in items if i.kind in ("text", "shape", "plate") and i.op >= MIN_TEXT_OPACITY]
    texts = [i for i in items if i.kind == "text" and i.op >= MIN_TEXT_OPACITY]
    for a in arrows:
        m = a.obj
        try:
            tip, start = m.get_end()[:2], m.get_start()[:2]
        except Exception:                                    # noqa: BLE001
            continue
        # 1. 先端が対象に届いているか
        tgt = getattr(m, "_qa_target", None)
        if tgt is not None:
            bb = _bbox(tgt, 0.0)
            if bb and _dist_to_box(tip, *bb) > 0.4:
                out.append(Issue("dangling", f"矢印の先が指す対象から離れている（{_dist_to_box(tip, *bb):.2f}）",
                                 [(a.l, a.r, a.b, a.t), bb]))
        else:
            near = [o for o in others if o.owner != a.owner and _dist_to_box(tip, o.l, o.r, o.b, o.t) <= 0.5]
            if not near:
                out.append(Issue("dangling", "矢印の先に何もない", [(a.l, a.r, a.b, a.t)]))
        # 2. 途中で文字を横切っていないか（端の近くは除く）
        path = _path(m)
        for t in texts:
            if a.owner is not None and t.owner == a.owner:
                continue
            # 対象のすぐ近く（同じ行の隣など）を通るのは避けられないので数えない
            if _dist_to_box(tip, t.l, t.r, t.b, t.t) <= 0.9 or _dist_to_box(start, t.l, t.r, t.b, t.t) <= 0.35:
                continue
            inside = ((path[:, 0] > t.l + 0.04) & (path[:, 0] < t.r - 0.04) & (path[:, 1] > t.b + 0.04)
                      & (path[:, 1] < t.t - 0.04)).sum()
            if inside >= 2:
                out.append(Issue("arrow", f"矢印が文字を横切っている: {t.label()}", [(a.l, a.r, a.b, a.t),
                                                                              (t.l, t.r, t.b, t.t)]))
    return out


def check_all(scene, skip_ids=()) -> list[Issue]:
    items = collect(scene, skip_ids)
    return [*check_text_overlap(items), *check_plates(items), *check_arrows(items)]


# ---------------------------------------------------------------- 画像
def _font(size: int):
    from PIL import ImageFont
    for p in ("/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc", "/System/Library/Fonts/Hiragino Sans GB.ttc",
              "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
              "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"):
        try:
            return ImageFont.truetype(p, size)
        except Exception:                                    # noqa: BLE001
            continue
    return ImageFont.load_default()


def save_annotated(img: np.ndarray, boxes, path) -> None:
    """画面の画像に，問題の場所を赤枠で描いて保存する（boxes は場面の座標 (l, r, b, t)）."""
    from manim import config
    from PIL import Image, ImageDraw
    im = Image.fromarray(img)
    dr = ImageDraw.Draw(im)
    H, W = img.shape[:2]
    fw, fh = config.frame_width, config.frame_height
    for l, r, b, t in boxes:
        x0, x1 = (l + fw / 2) / fw * W, (r + fw / 2) / fw * W
        y0, y1 = (fh / 2 - t) / fh * H, (fh / 2 - b) / fh * H
        dr.rectangle([x0 - 2, y0 - 2, x1 + 2, y1 + 2], outline=(255, 40, 40), width=2)
    im.save(path)


def contact_sheet(frames, prefix, cols: int = 4, per_page: int = 24) -> list:
    """[(時刻, 台本, 画像)] → 台本つきのコンタクトシート（ページ分け）．書き出し前に全体を一覧するためのもの."""
    from PIL import Image, ImageDraw
    if not frames:
        return []
    h, w = frames[0][2].shape[:2]
    lab_h = 34
    font = _font(14)
    paths = []
    for pg in range(0, len(frames), per_page):
        chunk = frames[pg:pg + per_page]
        rows_ = (len(chunk) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * w, rows_ * (h + lab_h)), (20, 20, 24))
        dr = ImageDraw.Draw(sheet)
        for k, (t, text, img) in enumerate(chunk):
            x, y = (k % cols) * w, (k // cols) * (h + lab_h)
            sheet.paste(Image.fromarray(img), (x, y + lab_h))
            dr.text((x + 4, y + 2), f"{t:6.1f}s {text[:30]}", fill=(255, 209, 102), font=font)
            if len(text) > 30:
                dr.text((x + 4, y + 18), text[30:62], fill=(200, 200, 200), font=font)
        p = f"{prefix}_{pg // per_page + 1}.png"
        sheet.save(p)
        paths.append(p)
    return paths
