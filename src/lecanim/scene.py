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
import os
import re
import sys

import numpy as np
from manim import *  # noqa: F401,F403
from tqdm import tqdm

from . import qa as _qa
from . import voice as _voice
from .config import ROOT
from .narration import SCRIPTS as _SCRIPTS
from .style import *  # noqa: F401,F403
from .units import LiveGroup, mark_overlay  # noqa: F401
from . import encode as _encode

_encode.install()   # 部分動画のエンコードをハードウェア（VideoToolbox / NVENC）に
from .style import (ACCENT, BG, BODY_TOP, CAPTION, CORNER, DIM, FG, GLOSS_Y, LINE, PHASES, THEME, YELLOW_E,
                    jp, mt, row)

# エンジンの有無は起動時に判定しない（混雑時に誤って無音になるため）．合成済みはキャッシュ，未合成は合成時に接続する
VOICE_ON = _voice.ENABLED
# QA モード（lecanim qa）：動画は書かず，play の途中の数点で検査し，要所の画像を残す．音声は長さと合図の時刻だけ求める
QA_MODE = os.environ.get("LECANIM_QA") == "1"


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
        self._cues: dict[str, float] = {}      # いまの台本の合図 → 場面の時刻
        self._cue_names: set[str] = set()      # いまの台本にある（自動でない）合図
        self._cue_used: set[str] = set()
        self._speech_t0 = 0.0
        self._busy: list[tuple[float, float]] = []      # 画面が動いていた区間
        self._plays: list[tuple[float, float, list]] = []
        self._speeches: list[tuple[float, float, str]] = []
        self._sync_log: list[tuple[str, float, float]] = []
        self._issue_prev: set[str] = set()
        self._issue_frames: list = []
        self._story: list = []
        self._story_pending: str | None = None
        self._overlay_ids: set[int] = set()
        self._steps = VGroup()
        self.header = VGroup()
        self.caption = VGroup()
        self.body = VGroup()
        crumb = row(f"{self.lecture}  ▸  {self.topic}", size=15, color=DIM)
        crumb.to_corner(UR, buff=0.06)
        self.crumb = crumb
        self.add(crumb)
        if QA_MODE:                       # 描かずに最後の状態だけ進める（play の途中は get_time_progression で数点見る）
            self.renderer._original_skipping_status = True
            self.renderer.skip_animations = True

    # --- header -----------------------------------------------------------
    def phase(self, key: str, title: str = "", wait=0.4):
        label, color = PHASES[key]
        if THEME == "sharp":
            lab = jp(label, size=20, color=color, weight=BOLD)
            tick = Line(UP * 0.2, DOWN * 0.2, color=color, stroke_width=3)
            chip_g = VGroup(lab, tick).arrange(RIGHT, buff=0.22).to_corner(UL, buff=0.36)
            ttl = row(title, size=30).next_to(chip_g, RIGHT, buff=0.24)
            rule = Line(LEFT * 7, RIGHT * 7, color=LINE, stroke_width=1.5).next_to(chip_g, DOWN, buff=0.2).set_x(0)
            seg = Line(rule.get_left(), rule.get_left() + RIGHT * (chip_g.get_right()[0] + 7.0), color=color,
                       stroke_width=3)
            bar = VGroup(rule, seg)
        else:
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
        kind=None なら text をそのまま読む. 台本の〔名前〕は合図：その位置を読み始める時刻が cue(名前) で取れる
        （合図がなくても，文の頭が s0, s1, …，終わりが end で取れる）."""
        if kind is not None:
            text = self.narr(kind, text)
        self._flush_cue_report()
        if not text:
            self._cues = {}
            return 0.0
        self._said.append(_voice.strip_cues(text))
        self._cues = {}
        if not VOICE_ON:
            return 0.0
        t = self.renderer.time
        if t < self._voice_end:
            self.wait(self._voice_end - t)
            t = self.renderer.time
        if QA_MODE:
            self._story_capture()
        tl = self._timeline(text)
        if QA_MODE:
            d = tl["duration"]
        else:
            path = _voice.synth(_voice.yomi(text))
            d = _voice.duration(path)
            self.add_sound(str(path))
        self._cues = {k: t + v for k, v in tl["cues"].items()}
        self._cues["end"] = t + d
        self._cue_names = {n for n, _ in _voice.prepare(text)[1]}
        self._cue_used = set()
        self._speech_t0 = t
        self._voice_end = t + d
        self._speeches.append((t, t + d, _voice.strip_cues(text)[:28]))
        self._story_pending = _voice.strip_cues(text)
        return d

    def _timeline(self, text: str) -> dict:
        try:
            return _voice.timeline(text)
        except Exception:                                      # noqa: BLE001  エンジンに届かない：文字数から概算
            spoken, cues = _voice.prepare(text)
            d = 0.145 * len(spoken) + 0.2
            allc = [*cues, *_voice._sentence_cues(spoken)]
            return {"duration": d, "approx": [n for n, _ in allc],
                    "cues": {n: 0.05 + d * p / max(len(spoken), 1) for n, p in allc}}

    def cue(self, name: str, lead: float = 0.0) -> bool:
        """いまの台本の合図 name を読み始める時刻まで待つ（過ぎていれば待たずに進み，遅れを記録する）.
        lead 秒だけ早く動き出す．合図がなければ何もしない（False）."""
        tt = self._cues.get(name)
        if tt is None:
            return False
        self._cue_used.add(name)
        target = tt - lead
        dt = target - self.renderer.time
        if dt > 0.03:
            self.wait(dt)
        self._sync_log.append((name, target, self.renderer.time))
        return True

    def pulse(self, *mobs, color=None, scale: float = 1.06) -> None:
        """音声が続くあいだ，文の頭ごとに mobs を光らせる（説明が続く場面で画面が止まらないように）."""
        names = sorted((n for n in self._cues if re.fullmatch(r"s[1-9]\d*", n)), key=self._cues.get)
        for n in names:
            if self._cues[n] - self.renderer.time > 0.8 and self._cues.get("end", 0) - self._cues[n] > 1.0:
                self.cue(n)
                self.play(*[Indicate(m, color=color or YELLOW_E, scale_factor=scale) for m in mobs], run_time=0.7)

    def plan_cues(self, names: list[str], seconds: dict | None = None) -> None:
        """台本にない合図を，前後の合図の間に等間隔で補う（合図を書かなくても，動きが音声全体に散る）.
        names は動きの順．先頭は音声の頭，末尾の次は音声の 85% を終点とする.
        seconds = {動きの名前（番号を除く）: かかる時間の目安}：補った合図は，前の動きが終わる時刻より早くしない."""
        if not self._cues or not names:
            return
        t0, t1 = self._speech_t0, self._cues.get("end", self._speech_t0)
        known = [n in self._cues for n in names]
        i = 0
        while i < len(names):
            if known[i]:
                i += 1
                continue
            j = i
            while j < len(names) and not known[j]:
                j += 1
            left = self._cues[names[i - 1]] if i > 0 else None
            right = self._cues[names[j]] if j < len(names) else None
            k = j - i
            if left is None:
                a, bnd = t0, (right if right is not None else t0 + 0.85 * (t1 - t0))
                ts = [a + (bnd - a) * q / k for q in range(k)]
            else:
                a = left
                bnd = right if right is not None else max(t0 + 0.85 * (t1 - t0), left + 0.5)
                ts = [a + (bnd - a) * q / (k + 1) for q in range(1, k + 1)]
            for n, tt in zip(names[i:j], ts):
                self._cues[n] = tt
            i = j
        if seconds:                       # 前の動きが終わる前に次の合図が来ないように（補った合図だけを後ろへ）
            prev_end = None
            for n, kn in zip(names, known):
                base = n.rstrip("0123456789")
                if not kn and prev_end is not None and self._cues[n] < prev_end:
                    self._cues[n] = prev_end
                prev_end = self._cues[n] + seconds.get(base, 1.0)

    def _flush_cue_report(self):
        unused = sorted(self._cue_names - self._cue_used)
        if unused and self._speeches:
            self._qa_msgs.setdefault(f"[W] 台本の合図をコードで使っていない: {', '.join(unused)}", self._speeches[-1][0])
        self._cue_names, self._cue_used = set(), set()

    def wait_voice(self, pad: float = 0.35):
        """読み上げが終わるまで待つ."""
        if VOICE_ON:
            rest = self._voice_end + pad - self.renderer.time
            if rest > 0.02:
                self.wait(rest)

    def note(self, text: str, wait: float | None = None, color=None, say: str | None = None,
             block: bool = True):
        """字幕＋ナレーション. say を与えると読み上げだけ別の文にできる."""
        new = row(text, size=24, color=color or CAPTION)
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
        """見えている部品だけの外接矩形（スクロールで窓の外に出して透明にした部品などは数えない）."""
        pts = [x.points for x in m.family_members_with_points()
               if max(x.get_fill_opacity(), x.get_stroke_opacity()) > 0.05 and len(x.points)]
        if not pts:
            return m.get_left()[0], m.get_right()[0], m.get_bottom()[1], m.get_top()[1]
        p = np.concatenate(pts)
        return p[:, 0].min(), p[:, 0].max(), p[:, 1].min(), p[:, 1].max()

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

    def _qa_geometry(self, final: bool = True):
        """文字の重なり・板が文字を覆う・矢印の検査. play の途中では 2 回続けて出たものだけ，終わりでは出たものを報告する."""
        skip = {id(self.header), id(self.crumb)}
        if not final:                      # 動いている最中の部品（変形・出入りの途中）は見ない．終わりの状態で見る
            for m in getattr(self, "moving_mobjects", []) or []:
                skip.update(id(x) for x in m.get_family())
        issues = _qa.check_all(self, skip)
        keys = set()
        for iss in issues:
            keys.add(iss.key)
            if iss.key in self._issue_prev or final:
                msg = f"[E] {iss.key}"
                if msg not in self._qa_msgs:
                    self._qa_msgs[msg] = self.renderer.time
                    if QA_MODE:
                        self._issue_frames.append((self.renderer.time, iss.msg, self._grab(), iss.boxes))
        self._issue_prev = keys

    def _grab(self):
        """いまの画面を画像（numpy）で取る."""
        self.renderer.update_frame(self)
        return np.array(self.renderer.get_frame())[:, :, :3].copy()

    def _story_capture(self):
        """直前の場面の終わりの画面を，コンタクトシート用に残す（QA モード）."""
        if self._story_pending is not None:
            self._story.append((self.renderer.time, self._story_pending, self._grab()[::2, ::2]))
            self._story_pending = None

    def play(self, *args, **kwargs):
        t0 = self.renderer.time
        super().play(*args, **kwargs)
        t1 = self.renderer.time
        if not (len(args) == 1 and isinstance(args[0], Wait)) and t1 > t0:
            self._busy.append((t0, t1))
            self._plays.append((t0, t1, [type(a).__name__ for a in args][:4]))
        self._regroup()
        self._qa_check()
        self._qa_geometry(final=True)
        self._issue_prev = set()

    def get_time_progression(self, run_time, description, n_iterations=None, override_skip_animations=False):
        # QA モード：描かずに，play の途中の数点（25% 刻み）で止めて検査する
        if QA_MODE and self.renderer.skip_animations and not override_skip_animations and run_time > 0.4:
            return tqdm([run_time * f for f in (0.25, 0.5, 0.75, 1.0)], desc=description, disable=True, leave=False)
        return super().get_time_progression(run_time, description, n_iterations, override_skip_animations)

    def update_to_time(self, t):
        super().update_to_time(t)
        if QA_MODE:
            self._qa_geometry(final=abs(t - self.duration) < 1e-6)

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
        self._flush_cue_report()
        self._sync_report()
        if QA_MODE:
            self._story_capture()
            self._story.append((self.renderer.time, "（終わり）", self._grab()[::2, ::2]))
        d = ROOT / "qa_reports"
        d.mkdir(exist_ok=True)
        f = d / f"{type(self).__name__}.txt"
        frames_note = {}
        if QA_MODE:
            frames_note = self._save_qa_images(name)
            self._sync_timeline(name)
        lines_ = [f"{t:7.1f}s  {m}" + (f"  → {frames_note[m]}" if m in frames_note else "")
                  for m, t in sorted(self._qa_msgs.items(), key=lambda x: x[1])]
        f.write_text("\n".join(lines_) + ("\n" if lines_ else ""))
        import sys
        print(f"[QA] {type(self).__name__}: {len(lines_)} warning(s) -> {f}", file=sys.stderr)

    def _sync_report(self):
        """音声と画面の動きのずれ：合図に遅れた／音声の間ずっと画面が動かない."""
        for name, target, actual in self._sync_log:
            late = actual - target
            if late > 0.5:
                self._qa_msgs.setdefault(f"[{'E' if late > 1.5 else 'W'}] 合図 {name} に {late:.1f} 秒遅れた"
                                         f"（その前の動きが長すぎる）", target)
        for t0, t1, label in self._speeches:
            if t1 - t0 < 8:
                continue
            cur, gap = t0, 0.0
            for a, b in sorted(self._busy):
                if b <= t0 or a >= t1:
                    continue
                gap = max(gap, max(a, t0) - cur)
                cur = max(cur, min(b, t1))
            gap = max(gap, t1 - cur)
            if gap > 7:
                self._qa_msgs.setdefault(f"[W] 音声が続く {gap:.0f} 秒のあいだ画面が動かない: {label}", t0)

    def _sync_timeline(self, name: str):
        """音声と画面の動きの対応表（qa_reports/<シーン>.sync.txt）：台本の合図の時刻と，その時刻に始まった動き."""
        out = []
        sync = sorted(self._sync_log, key=lambda x: x[1])
        for t0, t1, label in self._speeches:
            out.append(f"■ {t0:6.1f}–{t1:6.1f}s  {label}")
            for a, b, names in self._plays:
                if t0 - 0.05 <= a < t1:
                    cues = [c for c, tt, act in sync if abs(act - a) < 0.08 and t0 - 0.05 <= tt < t1]
                    out.append(f"    {a - t0:5.1f}s  ▶ {','.join(names)} ({b - a:.1f}s)" + (f"   合図 {','.join(cues)}" if cues else ""))
        d = ROOT / "qa_reports"
        d.mkdir(exist_ok=True)
        (d / f"{name}.sync.txt").write_text("\n".join(out) + "\n")

    def _save_qa_images(self, name: str) -> dict:
        """問題の画面（赤枠つき）とコンタクトシートを qa_frames/ に保存する."""
        out = {}
        d = ROOT / "qa_frames"
        (d / "issues").mkdir(parents=True, exist_ok=True)
        for k, (t, msg, img, boxes) in enumerate(self._issue_frames[:30]):
            f = d / "issues" / f"{name}_{k:02d}.png"
            _qa.save_annotated(img, boxes, f)
            out[f"[E] {msg}"] = str(f.relative_to(ROOT))
        _qa.contact_sheet(self._story, d / f"{name}_story", cols=3, per_page=18)
        return out

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
               color=None, hold: float | None = None, short: str | None = None):
        """記号/用語を初出で導入する: 大きな吹き出しで対象を矢印で指し → 上部の記号メモに収納."""
        color = color or ACCENT
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
        bg = SurroundingRectangle(big, color=color, buff=0.18, corner_radius=CORNER, stroke_width=2)
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
            end = self._arrow_tip(start, target, tc)
            arrow = Arrow(start, end, buff=0.05, color=color, stroke_width=4, max_tip_length_to_length_ratio=0.2)
            arrow._qa_target = target
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
            # 長い説明では，文の頭ごとに対象をもう一度光らせる（音声が続くあいだ画面が止まらないように）
            for n in sorted((n for n in self._cues if re.fullmatch(r"s[1-9]\d*", n)), key=self._cues.get):
                if self._cues[n] - self.renderer.time > 0.8 and self._cues["end"] - self._cues[n] > 1.0:
                    self.cue(n)
                    self.play(Indicate(target, color=color, scale_factor=1.12), run_time=0.7)
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

    @staticmethod
    def _arrow_tip(start, target: Mobject, tc) -> np.ndarray:
        """矢印の先端：start から対象の中心へ向かう線が，対象の外接矩形（少し広げる）に入る点の手前."""
        bb = _qa._bbox(target, 0.0)
        if bb is None:
            return tc - normalize(tc - start) * 0.3
        l, r, b, t = bb[0] - 0.08, bb[1] + 0.08, bb[2] - 0.08, bb[3] + 0.08
        d = tc[:2] - start[:2]
        n = np.linalg.norm(d)
        if n < 1e-6:
            return tc
        u = d / n
        lo, hi = 0.0, n
        for k in range(2):                                         # 光線と矩形の交差（スラブ法）
            lo_k, hi_k = ((l, r) if k == 0 else (b, t))
            if abs(u[k]) < 1e-9:
                if not (lo_k <= start[k] <= hi_k):
                    return tc
                continue
            t1, t2 = (lo_k - start[k]) / u[k], (hi_k - start[k]) / u[k]
            lo, hi = max(lo, min(t1, t2)), min(hi, max(t1, t2))
        enter = lo if lo <= hi else n
        p = start[:2] + u * max(enter - 0.04, 0.05)
        return np.array([p[0], p[1], 0.0])

    def _occupied(self, exclude=()):
        ex = {id(self.header), id(self.crumb), id(self.gloss), *map(id, exclude)}
        return [m for m in self.mobjects if id(m) not in ex and m.family_members_with_points()]

    def _place_free(self, m: Mobject, target: Mobject, buff=0.9):
        """吹き出し m を置く場所を探す．候補は target の周りの格子．費用は，文字との重なり（正確な外接矩形）・
        図形の点との重なり・対象そのものを覆うこと・矢印が文字を横切ること・対象からの距離."""
        items = _qa.collect(self, skip_ids={id(m), id(self.header), id(self.crumb), id(self.gloss)})
        texts = [i for i in items if i.kind == "text" and i.op >= _qa.MIN_TEXT_OPACITY]
        pts = [i.obj for i in items if i.kind in ("shape", "arrow") and i.op >= 0.3]
        allp = [np.concatenate([x.points[:, :2] for x in o.family_members_with_points()]) for o in pts]
        tb = _qa._bbox(target, 0.0) or (target.get_left()[0], target.get_right()[0], target.get_bottom()[1],
                                         target.get_top()[1])
        tc = np.array([(tb[0] + tb[1]) / 2, (tb[2] + tb[3]) / 2])
        w, h = m.width, m.height
        best, best_cost = None, None
        xs = np.arange(-6.9 + w / 2, 6.9 - w / 2 + 1e-6, 0.4)
        ys = np.arange(-2.85 + h / 2, 2.3 - h / 2 + 1e-6, 0.3)
        if not len(xs):
            xs = np.array([0.0])
        if not len(ys):
            ys = np.array([0.0])
        cands = [(cx, cy) for cx in xs for cy in ys]
        # 矢印が文字を横切りにくいよう，対象の真上・真下・真横の候補も加える
        for cy in ys:
            cands.append((float(np.clip(tc[0], xs[0], xs[-1])), float(cy)))
        for cx in xs:
            cands.append((float(cx), float(np.clip(tc[1], ys[0], ys[-1]))))
        for cx, cy in cands:
            if True:
                l, r, b_, t_ = cx - w / 2, cx + w / 2, cy - h / 2, cy + h / 2
                cost = 0.0
                for it in texts:
                    ox, oy = min(r, it.r) - max(l, it.l), min(t_, it.t) - max(b_, it.b)
                    if ox > 0 and oy > 0:
                        cost += 25 * ox * oy / max(it.area, 1e-6) * min(it.area, 1.0) + 2
                for p in allp:
                    cost += 6 * ((p[:, 0] > l) & (p[:, 0] < r) & (p[:, 1] > b_) & (p[:, 1] < t_)).mean()
                ox, oy = min(r, tb[1]) - max(l, tb[0]), min(t_, tb[3]) - max(b_, tb[2])
                if ox > 0 and oy > 0:
                    cost += 40                                         # 対象そのものを覆う
                # 矢印（吹き出しの中心 → 対象の中心）が文字を横切る
                for f_ in np.linspace(0.15, 0.85, 10):
                    px, py = cx + (tc[0] - cx) * f_, cy + (tc[1] - cy) * f_
                    if tb[0] - 0.2 <= px <= tb[1] + 0.2 and tb[2] - 0.2 <= py <= tb[3] + 0.2:
                        continue
                    if l <= px <= r and b_ <= py <= t_:
                        continue
                    for it in texts:
                        if it.l <= px <= it.r and it.b <= py <= it.t:
                            cost += 1.5
                            break
                cost += 0.35 * float(np.hypot(cx - tc[0], cy - tc[1]))
                if best_cost is None or cost < best_cost:
                    best, best_cost = np.array([cx, cy, 0.0]), cost
        m.move_to(best if best is not None else target.get_center())

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
            self.cue("hl")                       # 台本の〔hl〕：項を色付けして括弧と説明を出す（既定は読み始め）
            self.play(sub.animate.set_opacity(1).set_color(col), GrowFromCenter(br), FadeIn(lab), run_time=0.6)
            if action:
                self.cue("act")                  # 台本の〔act〕：図の上での動き（既定は読み始め）
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
        if THEME == "sharp":
            g = VGroup(row(title, size=46, weight=BOLD))
            if subtitle:
                g.add(row(subtitle, size=26, color=DIM))
            g.arrange(DOWN, buff=0.3, aligned_edge=LEFT)
            series = jp(self.lecture, size=20, color=ACCENT, weight=BOLD) if self.lecture else None
            if series is not None:
                g = VGroup(series, *g).arrange(DOWN, buff=0.3, aligned_edge=LEFT)
            if g.width > 11.4:
                g.scale_to_fit_width(11.4)
            g.move_to(ORIGIN).to_edge(LEFT, buff=1.4)
            bar = Line(g.get_corner(UL) + LEFT * 0.35 + UP * 0.1, g.get_corner(DL) + LEFT * 0.35 + DOWN * 0.1,
                       color=ACCENT, stroke_width=4)
            g = VGroup(bar, g)
        else:
            t = row(title, size=48)
            g = VGroup(t)
            if subtitle:
                g.add(row(subtitle, size=28, color=DIM))
            g.arrange(DOWN, buff=0.35)
        self.speak(title, kind="title")
        self.play(FadeIn(g, shift=UP * 0.3), run_time=1)
        self.wait_voice(0.2) if VOICE_ON else self.wait(1.2)
        self.play(FadeOut(g), run_time=0.6)

    def agenda(self, items: list[str], current: int | None = None, done=(), title: str = "問い", prefix: str = "Q"):
        """問いの一覧. current=None なら全項目を順に読み上げて並べる（台本キー q:<項目>）.
        current=i なら一覧を出して i 番目だけを強調し, その項目を読み上げてから消す（各ブロックの冒頭用）."""
        done = set(done)
        rows_ = VGroup()
        for i, it in enumerate(items):
            on = current is None or i == current
            col = ACCENT if i == current else (DIM if (i in done or not on) else FG)
            num = jp(f"{prefix}{i + 1}", size=34, color=ACCENT if on else DIM, weight=BOLD)
            body = row(it, size=34, color=col)
            mark = jp("✓", size=30, color=DIM) if i in done else VGroup()
            rows_.add(VGroup(num, body, mark).arrange(RIGHT, buff=0.3))
        rows_.arrange(DOWN, buff=0.55, aligned_edge=LEFT)
        if rows_.width > 12.5:
            rows_.scale_to_fit_width(12.5)
        top = (GLOSS_Y - 0.35) if len(self.gloss) else BODY_TOP - 0.25
        room = top - (-2.6)
        if rows_.height > room:
            rows_.scale_to_fit_height(room)
        rows_.move_to([0, (top - 2.6) / 2, 0]).to_edge(LEFT, buff=1.2)
        if current is None:
            self.speak(title, kind="agenda")
            for r, it in zip(rows_, items):
                self.wait_voice(0.1)
                self.speak(it, kind="q")
                self.play(FadeIn(r, shift=RIGHT * 0.2), run_time=0.5)
                self.wait_voice(0.2) if VOICE_ON else self.wait(1.0)
            self.wait(0.8)
            self.play(FadeOut(rows_), run_time=0.5)
            return rows_
        self.play(FadeIn(rows_), run_time=0.5)
        bar = Line(rows_[current].get_corner(UL) + LEFT * 0.25, rows_[current].get_corner(DL) + LEFT * 0.25,
                   color=ACCENT, stroke_width=4)
        self.overlay(bar)
        self.wait_voice(0.1)
        self.speak(items[current], kind="q")
        self.play(Create(bar), Indicate(rows_[current][1], color=ACCENT, scale_factor=1.05), run_time=0.7)
        self.wait_voice(0.3) if VOICE_ON else self.wait(1.4)
        self.play(FadeOut(rows_), FadeOut(bar), run_time=0.5)
        return rows_

    def end_card(self, *points: str, title: str = "証明の構造まとめ"):
        self.clear_body()
        self.phase("summary", title)
        items = VGroup(*[row(p) if isinstance(p, str) else p for p in points])
        items = VGroup(*[VGroup(jp(f"{i + 1:02d}" if THEME == "sharp" else f"{i + 1}.", size=28, color=ACCENT,
                                   weight=BOLD if THEME == "sharp" else NORMAL), it).arrange(RIGHT, buff=0.25 if THEME == "sharp" else 0.2)
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
