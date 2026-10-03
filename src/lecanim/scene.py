"""LectureScene: モチベ → 定義・定理 → 具体例 → 証明 → まとめ の解説シーンの基底クラス.

* phase()  見出しの切り替え          * note()    字幕
* define() 記号を指し示して記号メモへ  * explain() 式を1項ずつ説明
* count_up() 番号を振って数える        * end_card() まとめ
* 自動レイアウト検査 (qa_reports/), 台本 (narration/) による VOICEVOX ナレーション,
  読み上げ記録 (transcripts/)
"""

from __future__ import annotations

import itertools  # noqa: F401
import math  # noqa: F401

import numpy as np
from manim import *  # noqa: F401,F403

from . import voice as _voice
from .config import ROOT
from .narration import SCRIPTS as _SCRIPTS
from .style import *  # noqa: F401,F403
from .units import LiveGroup, mark_overlay  # noqa: F401
from . import encode as _encode

_encode.install()   # 部分動画のエンコードをハードウェア（VideoToolbox / NVENC）に
from .style import BG, BODY_TOP, DIM, FG, GLOSS_Y, PHASES, YELLOW_E, jp, mt, row

# エンジンの有無は起動時に判定しない（混雑時に誤って無音になるため）．合成済みはキャッシュ，未合成は合成時に接続する
VOICE_ON = _voice.ENABLED


# ---------------------------------------------------------------- scene base
class LectureScene(Scene):
    lecture = ""      # 例 "第2回 Ramsey理論"（パンくず表示）
    chapter = ""      # YouTube チャプター名（空なら topic）
    topic = ""        # 例 "R(3,3)=6"

    def setup(self):
        self._qa_msgs: dict[str, float] = {}
        self._voice_end = 0.0
        self._beats: list[str] = []          # 読み上げ場面の一覧 (台本作成用)
        self._said: list[str] = []           # 実際に読んだ台本
        self._narr_used: set[int] = set()
        self.gloss = VGroup()          # 画面上部の「記号メモ」
        self._gloss_map: dict = {}
        self._units: list = []
        self._overlay_ids: set[int] = set()
        self._steps = VGroup()
        self.header = VGroup()
        self.caption = VGroup()
        self.body = VGroup()
        crumb = row(f"{self.lecture}  ▸  {self.topic}", size=15, color=DIM)
        crumb.to_corner(UR, buff=0.06)
        self.crumb = crumb
        self.add(crumb)

    # --- header -----------------------------------------------------------
    def phase(self, key: str, title: str = "", wait=0.4):
        label, color = PHASES[key]
        chip_t = jp(label, size=24, color=BG, weight=BOLD)
        chip = RoundedRectangle(corner_radius=0.15, width=chip_t.width + 0.4,
                                height=chip_t.height + 0.25, fill_color=color,
                                fill_opacity=1, stroke_width=0)
        chip_t.move_to(chip)
        chip_g = VGroup(chip, chip_t).to_corner(UL, buff=0.32)
        ttl = row(title, size=32).next_to(chip_g, RIGHT, buff=0.3)
        bar = Line(LEFT * 7, RIGHT * 7, color=color, stroke_width=2).next_to(
            chip_g, DOWN, buff=0.15).set_x(0)
        lim = 6.9
        if ttl.get_right()[0] > lim:
            ttl.scale_to_fit_width(lim - ttl.get_left()[0]).align_to(chip_g.get_right() + RIGHT * 0.3, LEFT)
            import sys
            print(f"[QA] {type(self).__name__}: 見出し縮小『{title}』", file=sys.stderr)
        new = VGroup(chip_g, ttl, bar)
        old, self.header = self.header, new
        anims = [FadeOut(old, shift=UP * 0.2)] if len(old) else []
        self.wait_voice(0.1)
        self.speak(title if key != "summary" else "まとめ", kind="phase" if key != "summary" else "summary")
        self.play(*anims, FadeIn(new, shift=DOWN * 0.2), run_time=0.7)
        self.wait_voice(0.2)
        self.wait(wait)

    # --- caption ----------------------------------------------------------
    # --- ナレーション (VOICEVOX) ---------------------------------------
    def narr(self, kind: str, text: str):
        """場面 (kind, 画面の文言) に対応する台本を narration.py から探す.
        台本のキーは "kind:文言の先頭部分"．同じキーが複数あれば順に使う．
        台本がないシーンは画面の文言をそのまま返す．台本があるのに該当行がなければ None (無音) + QA 警告."""
        key = f"{kind}:{text}"
        self._beats.append(key)
        script = _SCRIPTS.get(type(self).__name__)
        if script is None:
            return text
        hits = [i for i, (k, _) in enumerate(script)
                if k.partition(":")[0] == kind and text.startswith(k.partition(":")[2])]
        fresh = [i for i in hits if i not in self._narr_used]
        if fresh or hits:
            i = (fresh or hits)[-1 if not fresh else 0]
            self._narr_used.add(i)
            return script[i][1]
        if kind not in ("outro",):
            self._qa_msgs.setdefault(f"台本なし: {key[:40]}", self.renderer.time)
        return None

    def speak(self, text: str, kind: str = "say") -> float:
        """場面 kind の台本を読み上げ始める (前の音声が終わるまで待つ). 音声の長さを返す.
        kind=None なら text をそのまま読む."""
        if kind is not None:
            text = self.narr(kind, text)
        if not text:
            return 0.0
        self._said.append(text)
        if not VOICE_ON:
            return 0.0
        t = self.renderer.time
        if t < self._voice_end:
            self.wait(self._voice_end - t)
            t = self.renderer.time
        path = _voice.synth(_voice.yomi(text))
        d = _voice.duration(path)
        self.add_sound(str(path))
        self._voice_end = t + d
        return d

    def wait_voice(self, pad: float = 0.35):
        """読み上げが終わるまで待つ."""
        if VOICE_ON:
            rest = self._voice_end + pad - self.renderer.time
            if rest > 0.02:
                self.wait(rest)

    def note(self, text: str, wait: float | None = None, color=YELLOW_E, say: str | None = None,
             block: bool = True):
        """字幕＋ナレーション. say を与えると読み上げだけ別の文にできる."""
        new = row(text, size=24, color=color)
        if new.width > 13:
            new.scale_to_fit_width(13)
        bg = BackgroundRectangle(new, color=BG, fill_opacity=0.85, buff=0.12)
        g = VGroup(bg, new).to_edge(DOWN, buff=0.25)
        old, self.caption = self.caption, g
        anims = [FadeOut(old)] if len(old) else []
        if VOICE_ON:
            self.wait_voice(0.1)
            self.speak(say, kind=None) if say is not None else self.speak(text, kind="note")
            self.play(*anims, FadeIn(g), run_time=0.5)
            if not block:      # 読み上げ中に次のアニメーションへ (後で wait_voice)
                return
            self.wait_voice()
            if wait:
                self.wait(min(wait, 1.0))
        else:
            self.speak(say, kind=None) if say is not None else self.speak(text, kind="note")
            self.play(*anims, FadeIn(g), run_time=0.5)
            self.wait(wait if wait is not None else 1.3 + 0.1 * len(text))

    def clear_caption(self):
        if len(self.caption):
            self.play(FadeOut(self.caption), run_time=0.3)
            self.caption = VGroup()

    # --- body -------------------------------------------------------------
    # --- 自動レイアウト検査 (QA) -------------------------------------
    def unit(self, m: Mobject, overlay: bool = False) -> Mobject:
        """部品ごとにアニメーションしても, play 後は m 1つとしてシーンに置き直す.
        (LiveGroup を継承した描画クラス (GraphMob など) は自動で unit 扱い). 部品の一部だけ先に見せたい場合は使わないこと."""
        self._units.append(m)
        if overlay:
            self.overlay(m)
        return m

    def _regroup(self):
        for u in [*self._units, *LiveGroup.instances]:
            fam = {id(x) for x in u.get_family()[1:]}
            parts = [m for m in self.mobjects if id(m) in fam]
            if parts:
                for m in parts:
                    self.mobjects.remove(m)
                if u not in self.mobjects:
                    self.mobjects.append(u)
        # アニメーションが作ったコンテナ (LaggedStart の Group 等) で,
        # 中身が全て他のトップレベルの部品になっているものは取り除く
        fixed = {id(self.header), id(self.crumb), id(self.caption)}
        for m in list(self.mobjects):
            if id(m) in fixed or not m.submobjects:
                continue
            others = set()
            for o in self.mobjects:
                if o is not m:
                    others.update(id(x) for x in o.get_family())
            if all(id(x) in others for x in m.submobjects):
                self.mobjects.remove(m)

    def overlay(self, *mobs):
        """重なり検査の対象外にする (グラフ上のハイライト, 矢印, 吹き出しなど)."""
        for m in mobs:
            for x in m.get_family():
                self._overlay_ids.add(id(x))
                x._qa_overlay = True
        return mobs[0] if len(mobs) == 1 else mobs

    @staticmethod
    def _bbox(m):
        return m.get_left()[0], m.get_right()[0], m.get_bottom()[1], m.get_top()[1]

    def _visible(self, m):
        try:
            return max(m.get_fill_opacity(), m.get_stroke_opacity()) > 0.05 or any(
                max(s.get_fill_opacity(), s.get_stroke_opacity()) > 0.05 for s in m.family_members_with_points())
        except Exception:
            return True

    def _qa_check(self):
        t = self.renderer.time
        fixed = {id(self.header), id(self.crumb), id(self.caption), id(self.gloss)}
        tops = [m for m in self.mobjects if id(m) not in fixed]
        # Create() などで既存グループの部品がトップレベルに再登録されたものは除外
        nested = set()
        for m in tops:
            nested.update(id(x) for x in m.get_family()[1:])
        items = [m for m in tops if id(m) not in nested
                 and m.family_members_with_points() and self._visible(m)]

        def warn(msg):
            if msg not in self._qa_msgs:
                self._qa_msgs[msg] = t

        def name(m):
            if isinstance(m, Text):
                return f"Text『{m.text[:14]}』"
            txt = [x for x in m.get_family() if isinstance(x, Text)]
            if txt:
                return f"{type(m).__name__}『{txt[0].text[:14]}…』"
            tex = [x for x in m.get_family() if isinstance(x, MathTex)]
            if tex:
                return f"{type(m).__name__}『${tex[0].get_tex_string()[:20]}$』"
            return f"{type(m).__name__}({len(m.submobjects)})"

        for m in items:
            l, r, b, tp = self._bbox(m)
            if l < -7.1 or r > 7.1 or b < -4.0 or tp > 4.0:
                warn(f"画面外: {name(m)} x=[{l:.2f},{r:.2f}] y=[{b:.2f},{tp:.2f}]")
            if id(m) in self._overlay_ids or getattr(m, "_qa_overlay", False):
                continue
            top_lim = (GLOSS_Y - 0.25) if len(self.gloss) else BODY_TOP
            if tp > top_lim + 0.08 and len(self.header):
                warn(f"ヘッダと重なり: {name(m)} top={tp:.2f}")
            if len(self.caption) and b < self.caption.get_top()[1] - 0.02:
                warn(f"字幕と重なり: {name(m)} bottom={b:.2f}")
        body = [m for m in items if id(m) not in self._overlay_ids
                and not getattr(m, "_qa_overlay", False)]
        for i in range(len(body)):
            for j in range(i + 1, len(body)):
                a, c = self._bbox(body[i]), self._bbox(body[j])
                ox = min(a[1], c[1]) - max(a[0], c[0])
                oy = min(a[3], c[3]) - max(a[2], c[2])
                if ox > 0.08 and oy > 0.08:
                    warn(f"重なり: {name(body[i])} × {name(body[j])} ({ox:.2f}×{oy:.2f})")

    def play(self, *args, **kwargs):
        super().play(*args, **kwargs)
        self._regroup()
        self._qa_check()

    def tear_down(self):
        super().tear_down()
        name = type(self).__name__
        sd = ROOT / "transcripts"
        sd.mkdir(exist_ok=True)
        (sd / f"{name}.beats.txt").write_text("\n".join(self._beats) + "\n")
        import json as _json
        (sd / f"{name}.meta.json").write_text(_json.dumps(
            {"lecture": self.lecture, "topic": self.topic, "chapter": self.chapter or self.topic},
            ensure_ascii=False))
        script = _SCRIPTS.get(name)
        if script is not None:
            for i, (k, _) in enumerate(script):
                if i not in self._narr_used and not k.startswith("outro"):
                    self._qa_msgs.setdefault(f"台本の未使用行: {k[:40]}", 0.0)
        lines_t = []
        for t in self._said:
            y = _voice.yomi(t)
            lines_t.append(t)
            if VOICE_ON:
                try:
                    lines_t.append("    ⤷ " + _voice.kana(y))
                except Exception:
                    pass
        (sd / f"{name}.txt").write_text("\n".join(lines_t) + "\n")
        d = ROOT / "qa_reports"
        d.mkdir(exist_ok=True)
        f = d / f"{type(self).__name__}.txt"
        lines_ = [f"{t:7.1f}s  {m}" for m, t in sorted(self._qa_msgs.items(), key=lambda x: x[1])]
        f.write_text("\n".join(lines_) + ("\n" if lines_ else ""))
        import sys
        print(f"[QA] {type(self).__name__}: {len(lines_)} warning(s) -> {f}", file=sys.stderr)

    def show(self, *mobs, anim=FadeIn, run_time=0.8, overlay=False, **kw):
        for m in mobs:  # 横にはみ出すものは自動で縮小して画面内へ
            if m.width > 13.3:
                m.scale_to_fit_width(13.3)
            if m.get_left()[0] < -6.9:
                m.shift(RIGHT * (-6.9 - m.get_left()[0]))
            if m.get_right()[0] > 6.9:
                m.shift(LEFT * (m.get_right()[0] - 6.9))
        if overlay:
            self.overlay(*mobs)
        self.play(*[anim(m, **kw) for m in mobs], run_time=run_time)
        self.body.add(*mobs)

    def clear_body(self, keep=()):
        """ヘッダ・パンくず・keep 以外の全オブジェクトをフェードアウト."""
        keep_ids = {id(self.header), id(self.crumb), id(self.gloss), *map(id, keep)}
        rm = [m for m in self.mobjects if id(m) not in keep_ids]
        if rm:
            self.play(*[FadeOut(m) for m in rm], run_time=0.6)
        self.body = VGroup(*keep)
        self.caption = VGroup()
        self._steps = VGroup()

    # --- 証明ステップの箇条書き(右側など) ------------------------------
    def steps_at(self, left_x: float = 0.6, top_y: float = 2.2, size: float = 26,
                 max_width: float | None = None):
        self._steps = VGroup()
        self._steps_anchor = (left_x, top_y)
        self._steps_size = size
        self._steps_maxw = max_width if max_width else 6.9 - left_x

    def step(self, *parts, color=FG, size=None, wait=0.6):
        r_ = row(*parts, size=size or self._steps_size, color=color)
        if r_.width > self._steps_maxw:
            r_.scale_to_fit_width(self._steps_maxw)
        if len(self._steps):
            r_.next_to(self._steps, DOWN, buff=0.28, aligned_edge=LEFT)
        else:
            r_.move_to([0, self._steps_anchor[1], 0], aligned_edge=UP)
            r_.align_to([self._steps_anchor[0], 0, 0], LEFT)
        # はみ出したら古い行を消して上に詰める
        while r_.get_bottom()[1] < BODY_BOTTOM + 0.15 and len(self._steps):
            old = self._steps[0]
            dy = old.height + 0.28
            self.play(FadeOut(old), *[m.animate.shift(UP * dy) for m in self._steps[1:]],
                      r_.animate.shift(UP * dy), run_time=0.4)
            self._steps.remove(old)
            self.body.remove(old)
        self._steps.add(r_)
        self.show(r_, run_time=0.6)
        self.wait(wait)
        return r_

    # --- 記号・用語の導入（指し示してから記号メモへ）------------------
    def define(self, sym: str, meaning: str, target: Mobject | None = None, math: bool = True,
               color=YELLOW_E, hold: float | None = None, short: str | None = None):
        """記号/用語を初出で導入する: 大きな吹き出しで対象を矢印で指し → 上部の記号メモに収納."""
        s_ = f"${sym}$" if math else sym
        big = row(s_, "：", meaning, size=30, color=color)
        if target is not None and big.width > 6.4:   # 図の横の空きに収まるよう「記号：」と意味の2行に折り返す
            parts = [meaning]
            if row(meaning, size=28).width > 6.4:  # 意味も長ければ，真ん中に近い読点で2行に分ける
                cuts = [i + 1 for i, ch in enumerate(meaning)
                        if ch in "，、" and meaning[:i].count("$") % 2 == 0]   # 数式 $...$ の中では切らない
                if cuts:
                    c = min(cuts, key=lambda i: abs(i - len(meaning) / 2))
                    parts = [meaning[:c], meaning[c:]]
            big = VGroup(row(s_, "：", size=30, color=color), *[row(m_, size=28, color=color) for m_ in parts]
                         ).arrange(DOWN, buff=0.14, aligned_edge=LEFT)
            if big.width > 6.4:
                big.scale_to_fit_width(6.4)
        bg = SurroundingRectangle(big, color=color, buff=0.18, corner_radius=0.12, stroke_width=2)
        bg.set_fill(BG, opacity=0.92)
        call = VGroup(bg, big)
        if call.width > 12.5:
            call.scale_to_fit_width(12.5)
        arrow = None
        if target is not None:
            tc = target.get_center()
            self._place_free(call, target)
            arrow = Arrow(call.get_center(), tc, buff=0, color=color, stroke_width=4,
                          max_tip_length_to_length_ratio=0.15)
            # 吹き出しの縁から対象の手前まで
            start = call.get_boundary_point(normalize(tc - call.get_center()))
            end = tc - normalize(tc - start) * (0.15 + max(target.width, target.height) / 2 * 0.6)
            arrow = Arrow(start, end, buff=0.05, color=color, stroke_width=4, max_tip_length_to_length_ratio=0.2)
        else:
            self._place_anywhere(call)
        self.overlay(call)
        anims = [FadeIn(call, scale=0.9)]
        if arrow is not None:
            self.overlay(arrow)
            anims.append(GrowArrow(arrow))
        self.wait_voice(0.1)
        self.speak(sym, kind="def")
        self.play(*anims, run_time=0.8)
        if target is not None:
            self.play(Indicate(target, color=color, scale_factor=1.15), run_time=0.9)
        if VOICE_ON:
            self.wait_voice(0.3)
        else:
            self.wait(hold if hold is not None else 1.5 + 0.08 * len(meaning))
        # 記号メモへ (入りきらなければ古いものから外す)
        if short is None:  # 記号メモ用の短い説明 (括弧・補足を落とす)
            short = meaning
            for sep in ("（", "．", "／", " ＝ ", "，"):
                if sep in short and short.index(sep) >= (10 if sep == "，" else 4):
                    short = short[:short.index(sep)]
            if len(short.replace("$", "")) > 22 and "$" not in short:
                short = short[:21] + "…"
            if short.count("$") % 2:
                short = short[:short.rindex("$")]
        chip = row(s_, "：", short, size=20, color=FG)
        chip[0].set_color(color)
        for x in chip.get_family():
            x._qa_overlay = True
        chips = [*self.gloss.submobjects, chip]
        while True:
            layout = VGroup(*[c.copy() for c in chips]).arrange(RIGHT, buff=0.45)
            if layout.width <= 13.4 or len(chips) == 1:
                break
            chips = chips[1:]
        layout.move_to([0, GLOSS_Y, 0]).align_to([-6.8, 0, 0], LEFT)
        outs = [FadeOut(c) for c in self.gloss if not any(c is x for x in chips)]
        moves = [c.animate.move_to(t.get_center()) for c, t in zip(chips[:-1], layout[:-1])]
        chip.move_to(layout[-1].get_center())
        self.play(*outs, *moves, ReplacementTransform(call, chip),
                  *([FadeOut(arrow)] if arrow is not None else []), run_time=0.8)
        self.remove(self.gloss, *self.gloss.submobjects, chip, call)
        self.gloss = VGroup(*chips)
        self.add(self.gloss)
        self._gloss_map[sym] = chip
        return chip

    def _occupied(self, exclude=()):
        ex = {id(self.header), id(self.crumb), id(self.gloss), *map(id, exclude)}
        return [m for m in self.mobjects if id(m) not in ex and m.family_members_with_points()]

    def _place_free(self, m: Mobject, target: Mobject, buff=0.9):
        """target の周り (上下左右・斜め) のうち, 他の要素と最も重ならない位置に m を置く."""
        occ = self._occupied(exclude=(m,))
        best, best_score = None, None
        dirs = [UP, DOWN, LEFT, RIGHT, UR, UL, DR, DL]
        for d in dirs:
            c = m.copy().next_to(target, d, buff=buff)
            c.set_x(np.clip(c.get_x(), -6.9 + c.width / 2, 6.9 - c.width / 2))
            c.set_y(np.clip(c.get_y(), -2.85 + c.height / 2, 2.3 - c.height / 2))
            l, r, b, t = c.get_left()[0], c.get_right()[0], c.get_bottom()[1], c.get_top()[1]
            score = 0.0
            for o in occ:
                ol, or_, ob, ot = o.get_left()[0], o.get_right()[0], o.get_bottom()[1], o.get_top()[1]
                # 点の多い GraphMob などは, 実際の点との重なりで評価
                pts = np.concatenate([x.points for x in o.family_members_with_points()])
                inside = ((pts[:, 0] > l) & (pts[:, 0] < r) & (pts[:, 1] > b) & (pts[:, 1] < t)).mean()
                ox = max(0, min(r, or_) - max(l, ol))
                oy = max(0, min(t, ot) - max(b, ob))
                score += inside * 10 + ox * oy * 0.2
            score += 0.05 * np.linalg.norm(c.get_center() - target.get_center())
            if best_score is None or score < best_score:
                best, best_score = c.get_center(), score
        m.move_to(best)

    def _place_anywhere(self, m: Mobject):
        """対象なしの吹き出し: 本文領域の候補位置のうち, 既存要素と最も重ならない所へ."""
        occ = self._occupied(exclude=(m,))
        best, best_score = None, None
        for y in (1.6, 0.6, -0.6, -1.8, 2.0, -2.3):
            for x in (0.0, -3.3, 3.3):
                c = m.copy().move_to([x, y, 0])
                c.set_x(np.clip(c.get_x(), -6.9 + c.width / 2, 6.9 - c.width / 2))
                c.set_y(np.clip(c.get_y(), -2.85 + c.height / 2, 2.3 - c.height / 2))
                l, r, b, t = c.get_left()[0], c.get_right()[0], c.get_bottom()[1], c.get_top()[1]
                score = 0.0
                for o in occ:
                    ol, or_, ob, ot = o.get_left()[0], o.get_right()[0], o.get_bottom()[1], o.get_top()[1]
                    ox = max(0, min(r, or_) - max(l, ol))
                    oy = max(0, min(t, ot) - max(b, ob))
                    score += ox * oy
                score += 0.02 * abs(y - 1.2) + 0.01 * abs(x)
                if best_score is None or score < best_score:
                    best, best_score = c.get_center(), score
        m.move_to(best)

    def recall(self, sym: str):
        """記号メモの該当項目を光らせる."""
        c = self._gloss_map.get(sym)
        if c is not None and any(c is x for x in self.gloss):
            self.play(Indicate(c, color=YELLOW_E, scale_factor=1.3), run_time=0.7)

    # --- 式を1項ずつ説明 ----------------------------------------------
    def explain(self, parts, at=UP * 1.7, size=44, note_size=24, keep=True, order=None):
        """parts: [(tex, 説明 or None, 色 or None, action or None), ...]
        式を薄く出し, 1項ずつ「色付け＋括弧＋説明＋(グラフ上の対応する操作)」を行う.
        action は引数なしの関数 (中で self.play してよい)."""
        parts = [tuple(p) + (None,) * (4 - len(p)) for p in parts]
        self.clear_caption()
        tex = MathTex(*[p[0] for p in parts], font_size=size, color=FG).move_to(at)
        if tex.width > 13:
            tex.scale_to_fit_width(13)
        tex.set_opacity(0.25)
        self.play(FadeIn(tex), run_time=0.6)
        idx = order if order is not None else range(len(parts))
        for i in [j for j in range(len(parts)) if j not in idx]:
            tex[i].set_opacity(1)
        for i in idx:
            t, note, col, action = parts[i]
            sub = tex[i]
            col = col or YELLOW_E
            if not note:
                self.play(sub.animate.set_opacity(1), run_time=0.2)
                continue
            br = Brace(sub, DOWN, color=col, buff=0.08)
            txt = row(note, size=note_size, color=col)
            lab = VGroup(BackgroundRectangle(txt, color=BG, fill_opacity=0.9, buff=0.08), txt)
            lab.next_to(br, DOWN, buff=0.08)
            lab.set_x(np.clip(lab.get_x(), -6.9 + lab.width / 2, 6.9 - lab.width / 2))
            self.overlay(br, lab)
            self.wait_voice(0.1)
            self.speak(note, kind="ex")
            self.play(sub.animate.set_opacity(1).set_color(col), GrowFromCenter(br), FadeIn(lab), run_time=0.6)
            if action:
                action()
            if VOICE_ON:
                self.wait_voice(0.4)
            else:
                self.wait(1.2 + 0.07 * len(note))
            self.play(FadeOut(br), FadeOut(lab), run_time=0.4)
        if not keep:
            self.play(FadeOut(tex))
        return tex

    def count_up(self, mobs, color=YELLOW_E, size=26, run_time_each=0.35, at=None):
        """対象に 1, 2, 3, … と番号を振って数える. 番号の VGroup を返す (後で FadeOut)."""
        nums = VGroup()
        for i, m in enumerate(mobs):
            if at:
                p = at(m)
            elif isinstance(m, (Line, Arc, ArcBetweenPoints, CurvedArrow, Arrow)) and not isinstance(m, DashedLine):
                p = m.point_from_proportion(0.5)
            else:
                p = m.get_center()
            t = mt(str(i + 1), size=size, color=color)
            bg = BackgroundRectangle(t, color=BG, fill_opacity=0.85, buff=0.04)
            g = VGroup(bg, t).move_to(p)
            if isinstance(m, Dot):
                g.next_to(m, UP, buff=0.08)
            nums.add(g)
            self.overlay(g)
            self.play(FadeIn(g, scale=1.5), Indicate(m, color=color, scale_factor=1.2), run_time=run_time_each)
        return nums

    def flash_edges(self, mobs, color, width=7, run_time=0.8):
        self.play(*[m.animate.set_color(color).set_stroke(width=width) for m in mobs],
                  run_time=run_time)

    def title_card(self, title: str, subtitle: str = ""):
        t = row(title, size=48)
        g = VGroup(t)
        if subtitle:
            g.add(row(subtitle, size=28, color=DIM))
        g.arrange(DOWN, buff=0.35)
        self.speak(title, kind="title")
        self.play(FadeIn(g, shift=UP * 0.3), run_time=1)
        self.wait_voice(0.2) if VOICE_ON else self.wait(1.2)
        self.play(FadeOut(g), run_time=0.6)

    def end_card(self, *points: str):
        self.clear_body()
        self.phase("summary", "証明の構造まとめ")
        items = VGroup(*[row(p) if isinstance(p, str) else p for p in points])
        items = VGroup(*[VGroup(jp(f"{i + 1}.", size=28, color=YELLOW_E), it).arrange(RIGHT, buff=0.2)
                         for i, it in enumerate(items)])
        items.arrange(DOWN, buff=0.35, aligned_edge=LEFT).move_to(ORIGIN + DOWN * 0.1)
        if items.width > 13:
            items.scale_to_fit_width(13)
        for it, p in zip(items, points):
            self.wait_voice(0.1)
            self.speak(p if isinstance(p, str) else "", kind="end")
            self.play(FadeIn(it, shift=RIGHT * 0.2), run_time=0.6)
            self.wait_voice(0.3) if VOICE_ON else self.wait(0.9)
        self.body.add(items)
        if VOICE_ON:
            cr = jp(_voice.credit(), size=18, color=DIM).to_corner(DR, buff=0.3)
            self.add(cr)
        self.speak("", kind="outro")
        self.wait_voice(0.3)
        self.wait(2.5)
