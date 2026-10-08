"""分野モジュール: LLM 推論サービング（GPU 配置・P/D 分離・遅延の内訳・性能曲線）.

    from lecanim import *
    from lecanim.domains.serving import *

設計方針
--------
* ``Worker`` / ``Deployment`` : GPU を P（Prefill）/ D（Decode）の担当へ割り当てた配置．
                                 GPU の重複・範囲外・TP と GPU 数の不一致を ``check()`` で検証する．
* ``SLO`` / ``Measurement`` / ``Sweep`` : 速度条件と計測点．条件を満たす最良点を ``Sweep.best()`` で選ぶ．
* ``Breakdown`` : 1ステップ（や1要求）の時間の内訳．割合・合計を持つ．
* 描画クラス（``…Mob``）の操作は Animation のリストを返す（``self.play(*m.op(...))``）．

    dep = Deployment.pack([("P", 2, 2)] * 4 + [("D", 4, 4)] * 2)
    cm = ClusterMob(dep, box=Box.left(0.5))
    self.play(cm.create())
    self.play(*cm.reassign(Deployment.pack([("P", 2, 2)] * 6 + [("D", 4, 4)])))
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence

import numpy as np
from manim import (DOWN, LEFT, RIGHT, UP, AnimationGroup, Axes, Create, DashedLine, Dot, FadeIn, FadeOut,
                   MoveAlongPath, GrowFromEdge, LaggedStart, Line, Rectangle, Succession, SurroundingRectangle, Text,
                   Transform, VGroup)

from .. import voice as _voice
from ..layout import Box
from ..style import BLUE_E, CORNER, DIM, FG, GREEN_E, JP_FONT, LINE, ORANGE_E, PALETTE, PURPLE_E, RED_E, YELLOW_E
from ..units import LiveGroup, mark_overlay

__all__ = ["Worker", "Deployment", "SLO", "Measurement", "Sweep", "Breakdown", "MoEModel",
           "ExpertGridMob", "LayerStackMob",
           "ClusterMob", "StackBarMob", "ChartMob", "TimelineMob", "ROLE_COLOR"]

YOMI = [("Prefill", "プリフィル"), ("Decode", "デコード"), ("TTFT", "ティーティーエフティー"),
        ("ITL", "アイティーエル"), ("GPU", "ジーピーユー"), ("H200", "エイチにひゃく"), ("MoE", "エムオーイー"),
        ("GEMM", "ジェム"), ("AllReduce", "オールリデュース"), ("All-Reduce", "オールリデュース"),
        ("NVLink", "エヌブイリンク"), ("FP8", "エフピーエイト"), ("BF16", "ビーエフじゅうろく"),
        ("CUDA Graph", "クーダグラフ"), ("CUDA", "クーダ"), ("KV", "ケーブイ"), ("tok/s", "トークン毎秒"),
        ("TensorRT-LLM", "テンソルアールティー エルエルエム"), ("Dynamo", "ダイナモ"), ("SGLang", "エスジーラング"),
        ("vLLM", "ブイエルエルエム"), ("EAGLE", "イーグル"), ("Qwen", "クウェン"), ("律速", "りっそく"),
        ("投機デコード", "とうきデコード"), ("良率", "りょうりつ")]
SUSPECT: list[str] = []
_voice.register_words(YOMI, SUSPECT)

ROLE_COLOR = {"P": ORANGE_E, "D": BLUE_E, "A": PURPLE_E}   # A = aggregate（P と D を同じ担当で）


# =====================================================================
#   データ構造
# =====================================================================
GPU = tuple[int, int]   # (node, index)


@dataclass(frozen=True)
class Worker:
    """1つの担当（推論エンジンの1プロセス群）. gpus の数＝TP 幅."""
    name: str
    role: str                     # "P" / "D" / "A"
    gpus: tuple[GPU, ...]
    tp: int
    ep: int = 1
    dp_attention: bool = False

    @property
    def size(self) -> int:
        return len(self.gpus)

    @property
    def spec(self) -> str:
        s = f"TP{self.tp}/EP{self.ep}"
        return s + ("・DP-attn" if self.dp_attention else "")


@dataclass
class Deployment:
    """GPU の担当への割り当て. nodes × gpus_per_node の GPU を使う."""
    workers: list[Worker]
    nodes: int = 2
    gpus_per_node: int = 8

    def check(self) -> list[str]:
        """問題点の一覧（空なら正しい配置）."""
        errs, seen = [], {}
        for w in self.workers:
            if w.role not in ROLE_COLOR:
                errs.append(f"{w.name}: 役割 {w.role}")
            if w.tp != w.size:
                errs.append(f"{w.name}: TP{w.tp} だが GPU は {w.size} 枚")
            if w.ep < 1 or w.tp % w.ep:
                errs.append(f"{w.name}: EP{w.ep} は TP{w.tp} を割り切らない")
            for g in w.gpus:
                n, i = g
                if not (0 <= n < self.nodes and 0 <= i < self.gpus_per_node):
                    errs.append(f"{w.name}: GPU {g} は範囲外")
                if g in seen:
                    errs.append(f"{w.name}: GPU {g} は {seen[g]} と重複")
                seen[g] = w.name
        names = [w.name for w in self.workers]
        if len(set(names)) != len(names):
            errs.append("担当名が重複")
        return errs

    @property
    def ok(self) -> bool:
        return not self.check()

    def all_gpus(self) -> list[GPU]:
        return [(n, i) for n in range(self.nodes) for i in range(self.gpus_per_node)]

    def used(self) -> set[GPU]:
        return {g for w in self.workers for g in w.gpus}

    def free(self) -> list[GPU]:
        u = self.used()
        return [g for g in self.all_gpus() if g not in u]

    def of(self, role: str) -> list[Worker]:
        return [w for w in self.workers if w.role == role]

    def gpus_of(self, role: str) -> int:
        return sum(w.size for w in self.of(role))

    def worker(self, name: str) -> Worker:
        return next(w for w in self.workers if w.name == name)

    @property
    def label(self) -> str:
        """例: 4P2D, 1A."""
        out = ""
        for r in ("P", "D", "A"):
            k = len(self.of(r))
            if k:
                out += f"{k}{r}"
        return out

    @classmethod
    def pack(cls, spec: Sequence[tuple], nodes: int = 2, gpus_per_node: int = 8,
             names: Sequence[str] | None = None) -> "Deployment":
        """[(役割, TP, EP[, dp_attention]), ...] を前から詰めて割り当てる.
        ノードに収まる担当はノードをまたがない. 名前は P0, P1, D0, … を自動で付ける."""
        cursor = [0] * nodes
        counters: dict[str, int] = {}
        workers = []
        for j, s in enumerate(spec):
            role, tp, ep = s[0], s[1], s[2]
            dpa = bool(s[3]) if len(s) > 3 else False
            gpus: list[GPU] = []
            if tp <= gpus_per_node:
                n = next((n for n in range(nodes) if cursor[n] + tp <= gpus_per_node), None)
                assert n is not None, f"GPU が足りない: {s}"
                gpus = [(n, cursor[n] + i) for i in range(tp)]
                cursor[n] += tp
            else:
                need = tp
                for n in range(nodes):
                    while cursor[n] < gpus_per_node and need:
                        gpus.append((n, cursor[n]))
                        cursor[n] += 1
                        need -= 1
                assert not need, f"GPU が足りない: {s}"
            k = counters.get(role, 0)
            counters[role] = k + 1
            name = names[j] if names else f"{role}{k}"
            workers.append(Worker(name, role, tuple(gpus), tp, ep, dpa))
        dep = cls(workers, nodes, gpus_per_node)
        assert dep.ok, dep.check()
        return dep


@dataclass(frozen=True)
class SLO:
    """速度条件. 要求ごとに TTFT ≤ ttft_ms かつ 平均ITL ≤ itl_ms を good とし, good率 ≥ min_rate を合格とする."""
    ttft_ms: float = 3000.0
    itl_ms: float = 20.0
    min_rate: float = 0.90

    def good(self, ttft_ms: float, itl_ms: float) -> bool:
        return ttft_ms <= self.ttft_ms and itl_ms <= self.itl_ms


@dataclass(frozen=True)
class Measurement:
    """1回の計測（1つの同時実行数 C）. good_tok_s は SLO を満たした要求の出力 token/s."""
    c: int
    good_tok_s: float
    good_rate: float
    itl_ms: float | None = None
    ttft_ms: float | None = None
    total_tok_s: float | None = None
    source: str = ""

    def passes(self, slo: SLO = SLO()) -> bool:
        return self.good_rate >= slo.min_rate


@dataclass
class Sweep:
    """同じ構成で C を変えた計測の列."""
    name: str
    points: list[Measurement] = field(default_factory=list)

    def sorted(self) -> list[Measurement]:
        return sorted(self.points, key=lambda m: m.c)

    def best(self, slo: SLO = SLO()) -> Measurement | None:
        ok = [m for m in self.points if m.passes(slo)]
        return max(ok, key=lambda m: m.good_tok_s) if ok else None

    def first_fail(self, slo: SLO = SLO()) -> Measurement | None:
        """C を上げていって初めて不合格になる点."""
        return next((m for m in self.sorted() if not m.passes(slo)), None)


@dataclass
class Breakdown:
    """時間の内訳. parts = [(名前, 値), ...]（値の単位は unit）."""
    parts: list[tuple[str, float]]
    unit: str = "µs"

    @property
    def total(self) -> float:
        return sum(v for _, v in self.parts)

    def value(self, name: str) -> float:
        return dict(self.parts)[name]

    def share(self, name: str) -> float:
        return self.value(name) / self.total

    def names(self) -> list[str]:
        return [n for n, _ in self.parts]

    def replace(self, **vals) -> "Breakdown":
        """一部の値だけ変えた内訳（キーワードは名前. 0 で消える）."""
        return Breakdown([(n, vals.get(n, v)) for n, v in self.parts if vals.get(n, v) > 0], self.unit)


@dataclass(frozen=True)
class MoEModel:
    """MoE Transformer の形（Hugging Face の config.json の値）. パラメータ数・KV の大きさなどを計算する."""
    layers: int
    hidden: int
    q_heads: int
    kv_heads: int
    head_dim: int
    experts: int
    top_k: int
    expert_inter: int
    vocab: int

    @property
    def attn_params_per_layer(self) -> int:
        q = self.hidden * self.q_heads * self.head_dim
        kv = 2 * self.hidden * self.kv_heads * self.head_dim
        o = self.q_heads * self.head_dim * self.hidden
        return q + kv + o

    @property
    def expert_params(self) -> int:
        """1 expert（gate・up・down の3つの行列）."""
        return 3 * self.hidden * self.expert_inter

    @property
    def embed_params(self) -> int:
        return 2 * self.vocab * self.hidden     # 入力の埋め込み＋出力の lm_head

    @property
    def total_params(self) -> int:
        return self.layers * (self.attn_params_per_layer + self.experts * self.expert_params) + self.embed_params

    @property
    def active_params(self) -> int:
        """1 token が通るパラメータ（attention 全部＋選ばれた top_k 個の expert＋埋め込み）."""
        return self.layers * (self.attn_params_per_layer + self.top_k * self.expert_params) + self.embed_params

    def kv_bytes_per_token(self, dtype_bytes: int = 1) -> int:
        return self.layers * 2 * self.kv_heads * self.head_dim * dtype_bytes

    def expected_active_experts(self, tokens: int) -> float:
        """tokens 個の token がそれぞれ top_k 個を一様に選ぶとき，1 層で使われる expert の数の期待値."""
        return self.experts * (1 - (1 - self.top_k / self.experts) ** tokens)


# =====================================================================
#   描画
# =====================================================================
def _txt(s: str, size: float = 20, color=FG, weight="NORMAL") -> Text:
    return Text(s, font=JP_FONT, font_size=size, color=color, weight=weight)


def _place_in_box(m, box: Box | None, margin: float = 0.25, grow: bool = False):
    """box に収める. grow=True なら box いっぱいまで拡大もする（縦横比は保つ）."""
    if box is None:
        return m
    W, H = box.width - 2 * margin, box.height - 2 * margin
    k = min(W / m.width, H / m.height)
    if k < 1 or grow:
        m.scale(k)
    m.move_to(box.center)
    return m


class ClusterMob(LiveGroup):
    """ノード × GPU の配置図. 担当（Worker）を色付きの角丸枠で囲み, 名前と TP/EP を添える.

    cm.gpu[(n, i)]   -> GPU の四角
    cm.wbox[name]    -> 担当の枠（VGroup: 枠, 名前, 仕様）
    """

    def __init__(self, dep: Deployment, box: Box | None = None, gpu_size: float = 0.5, gap: float = 0.12,
                 node_gap: float = 0.55, show_spec: bool = True, node_labels: bool = True, grow: bool = False):
        super().__init__()
        self.dep = dep
        self.show_spec = show_spec
        self.gs = gpu_size
        self.gpu: dict[GPU, Rectangle] = {}
        self.nodes_g = VGroup()
        self.gpus_g = VGroup()
        self.workers_g = VGroup()
        self.wbox: dict[str, VGroup] = {}
        step = gpu_size + gap
        row_h = gpu_size + node_gap + (0.42 if show_spec else 0.2)
        for n in range(dep.nodes):
            y = -n * row_h
            row = VGroup()
            for i in range(dep.gpus_per_node):
                sq = Rectangle(width=gpu_size, height=gpu_size, stroke_color=DIM, stroke_width=1.5,
                               fill_color=DIM, fill_opacity=0.18)
                sq.move_to([i * step, y, 0])
                self.gpu[(n, i)] = sq
                row.add(sq)
            frame = SurroundingRectangle(row, buff=0.14, color=LINE, stroke_width=1.2, corner_radius=min(CORNER, 0.06))
            self.nodes_g.add(frame)
            if node_labels:
                lab = _txt(f"ノード{n}", 16, DIM).next_to(frame, LEFT, buff=0.12)
                self.nodes_g.add(lab)
            self.gpus_g.add(row)
        self.add(self.nodes_g, self.gpus_g, self.workers_g)
        for w in dep.workers:
            self._add_worker_box(w)
        _place_in_box(self, box, grow=grow)

    # ---- 部品 --------------------------------------------------------
    def _worker_box(self, w: Worker) -> VGroup:
        sq = [self.gpu[g] for g in w.gpus]
        col = ROLE_COLOR[w.role]
        rows: dict[int, list] = {}
        for g, m in zip(w.gpus, sq):
            rows.setdefault(g[0], []).append(m)
        frames = VGroup()
        for ms in rows.values():
            r = SurroundingRectangle(VGroup(*ms), buff=0.045, color=col, stroke_width=3,
                                     corner_radius=min(CORNER, 0.08))
            r.set_fill(col, opacity=0.38)
            frames.add(r)
        name = _txt(w.name, 26, FG, weight="BOLD")
        if name.width > frames[0].width * 0.9:
            name.scale_to_fit_width(frames[0].width * 0.9)
        name.move_to(frames[0])
        g = VGroup(frames, name)
        if self.show_spec:
            spec = _txt(w.spec, 17, col)
            if spec.width > frames[0].width + 0.2:
                spec.scale_to_fit_width(frames[0].width + 0.2)
            spec.next_to(frames[0], DOWN, buff=0.06)
            g.add(spec)
        return g

    def _add_worker_box(self, w: Worker) -> VGroup:
        g = self._worker_box(w)
        self.wbox[w.name] = g
        self.workers_g.add(g)
        return g

    # ---- 操作 --------------------------------------------------------
    def create(self, run_time=1.6):
        return AnimationGroup(FadeIn(self.nodes_g), LaggedStart(*[FadeIn(s, scale=0.6) for s in self.gpus_g],
                                                               lag_ratio=0.15),
                              LaggedStart(*[FadeIn(b) for b in self.workers_g], lag_ratio=0.15),
                              lag_ratio=0.4, run_time=run_time)

    def reassign(self, new: Deployment) -> list:
        """配置を組み替える. 同じ名前の担当は枠が変形し, 消える担当はフェードアウト, 新しい担当はフェードイン."""
        assert new.ok, new.check()
        assert (new.nodes, new.gpus_per_node) == (self.dep.nodes, self.dep.gpus_per_node)
        anims = []
        old_names = {w.name for w in self.dep.workers}
        new_names = {w.name for w in new.workers}
        for name in old_names - new_names:
            m = self.wbox.pop(name)
            self.workers_g.remove(m)
            anims.append(FadeOut(m))
        for w in new.workers:
            target = self._worker_box(w)
            if w.name in self.wbox:
                old = self.wbox[w.name]
                if len(old[0]) != len(target[0]) or len(old) != len(target):
                    self.workers_g.remove(old)
                    anims.append(FadeOut(old))
                    self.wbox[w.name] = target
                    self.workers_g.add(target)
                    anims.append(FadeIn(target))
                else:
                    anims.append(Transform(old, target))
            else:
                self.wbox[w.name] = target
                self.workers_g.add(target)
                anims.append(FadeIn(target))
        self.dep = new
        return anims

    def highlight(self, names: Iterable[str], color=YELLOW_E, width=6) -> list:
        """担当の枠を強調する（他は薄く）. unhighlight() で戻す."""
        names = set(names)
        anims = []
        for n, g in self.wbox.items():
            if n in names:
                anims.append(g[0].animate.set_stroke(color, width=width))
            else:
                anims.append(g.animate.set_opacity(0.25))
        return anims

    def unhighlight(self) -> list:
        anims = []
        for w in self.dep.workers:
            g = self.wbox[w.name]
            col = ROLE_COLOR[w.role]
            anims.append(g.animate.set_opacity(1))
            anims.append(g[0].animate.set_stroke(col, width=3).set_fill(col, opacity=0.38))
        return anims

    def tag(self, name: str, text: str, color=YELLOW_E, size=20, direction=UP) -> Text:
        """担当の脇に小さな注記（例：『律速』『ITL 21 ms』）. 枠が動くとついてくる."""
        t = mark_overlay(_txt(text, size, color, weight="BOLD"))
        frame = self.wbox[name][0]
        t.add_updater(lambda m: m.next_to(frame, direction, buff=0.08))
        t.update()
        return t

    def worker_center(self, name: str) -> np.ndarray:
        return self.wbox[name][0].get_center()

    def role_legend(self, roles=("P", "D"), size=18) -> VGroup:
        names = {"P": "Prefill（入力処理）", "D": "Decode（生成処理）", "A": "P と D を同じ担当で"}
        items = VGroup()
        for r in roles:
            sw = Rectangle(width=0.3, height=0.22, stroke_color=ROLE_COLOR[r], fill_color=ROLE_COLOR[r],
                           fill_opacity=0.45, stroke_width=2)
            items.add(VGroup(sw, _txt(names[r], size, FG).next_to(sw, RIGHT, buff=0.1)))
        return items.arrange(RIGHT, buff=0.4)


class StackBarMob(LiveGroup):
    """内訳（Breakdown）の横向き積み上げ棒. 長さは ref_total に対する比率で決まるので,
    morph_to() で別の内訳に変えると「短くなった」ことがそのまま見える.

    sb.seg[name] -> 区間の四角,  sb.lab[name] -> 区間のラベル
    """

    def __init__(self, bd: Breakdown, length: float = 9.0, height: float = 0.7, ref_total: float | None = None,
                 colors: dict | None = None, label_size: float = 18, show_values: bool = True,
                 title: str | None = None):
        super().__init__()
        self.L, self.h = length, height
        self.ref = ref_total or bd.total
        self.label_size = label_size
        self.show_values = show_values
        self.colors = dict(colors or {})
        for i, n in enumerate(bd.names()):
            self.colors.setdefault(n, PALETTE[i % len(PALETTE)])
        self.bd = bd
        self.seg: dict[str, Rectangle] = {}
        self.lab: dict[str, VGroup] = {}
        self.segs_g, self.labs_g = VGroup(), VGroup()
        self.origin = np.array([-length / 2, 0, 0])
        self.axis = Line(self.origin + DOWN * height * 0.75, self.origin + UP * height * 0.75,
                         color=DIM, stroke_width=2)
        self.add(self.axis, self.segs_g, self.labs_g)
        if title:
            self.title = _txt(title, label_size + 2, FG).next_to(self.axis, UP, buff=0.12, aligned_edge=LEFT)
            self.add(self.title)
        built = self._build(bd)
        for n, (r, l) in built.items():
            self.seg[n], self.lab[n] = r, l
            self.segs_g.add(r)
            self.labs_g.add(l)
        self.total_lab = self._total_label(bd)
        self.add(self.total_lab)

    def _w(self, v: float) -> float:
        return self.L * v / self.ref

    def _build(self, bd: Breakdown) -> dict:
        out = {}
        x = self.origin[0]
        left = self.axis.get_center()
        below = 0
        for n, v in bd.parts:
            w = max(self._w(v), 1e-3)
            r = Rectangle(width=w, height=self.h, stroke_color=self.colors[n], stroke_width=2,
                          fill_color=self.colors[n], fill_opacity=0.55)
            r.move_to([x + w / 2, left[1], 0])
            txt = n + (f"\n{v:g} {bd.unit}" if self.show_values else "")
            lab = _txt(txt, self.label_size, FG)
            if lab.width <= w - 0.1 and lab.height <= self.h - 0.06:
                lab.move_to(r)
                lab = VGroup(lab)
            else:   # 狭い区間は下に出して引き出し線を付ける
                lab.set_color(self.colors[n])
                lab.next_to(r, DOWN, buff=0.25 + 0.5 * (below % 2))
                lab.set_x(max(lab.get_x(), self.origin[0] + lab.width / 2))
                lead = Line(r.get_bottom(), lab.get_top(), color=self.colors[n], stroke_width=1.5)
                lab = VGroup(lab, lead)
                below += 1
            out[n] = (r, lab)
            x += w
        return out

    def _total_label(self, bd: Breakdown) -> Text:
        end = self.origin[0] + self._w(bd.total)
        t = _txt(f"計 {bd.total:g} {bd.unit}", self.label_size, YELLOW_E)
        t.move_to([end + 0.15 + t.width / 2, self.axis.get_center()[1], 0])
        return t

    def create(self, run_time=1.5):
        return Succession(Create(self.axis, run_time=0.3 * run_time),
                          LaggedStart(*[GrowFromEdge(self.seg[n], LEFT) for n in self.bd.names()],
                                      lag_ratio=0.25, run_time=0.5 * run_time),
                          AnimationGroup(FadeIn(self.labs_g), FadeIn(self.total_lab), run_time=0.3 * run_time))

    def highlight(self, name: str, color=YELLOW_E) -> list:
        return [self.seg[name].animate.set_stroke(color, width=6),
                *[self.seg[n].animate.set_fill(opacity=0.15) for n in self.seg if n != name]]

    def unhighlight(self) -> list:
        return [self.seg[n].animate.set_stroke(self.colors[n], width=2).set_fill(opacity=0.55) for n in self.seg]

    def morph_to(self, bd: Breakdown) -> list:
        """別の内訳へ変形する（名前で対応. 消える区間はフェードアウト）."""
        built = self._build(bd)
        anims = []
        for n in list(self.seg):
            if n not in built:
                r, l = self.seg.pop(n), self.lab.pop(n)
                self.segs_g.remove(r)
                self.labs_g.remove(l)
                anims += [FadeOut(r), FadeOut(l)]
        for n, (r, l) in built.items():
            if n in self.seg:
                anims.append(Transform(self.seg[n], r))
                old = self.lab[n]
                self.labs_g.remove(old)
                anims.append(FadeOut(old))
                self.lab[n] = l
                self.labs_g.add(l)
                anims.append(FadeIn(l))
            else:
                self.colors.setdefault(n, PALETTE[len(self.colors) % len(PALETTE)])
                self.seg[n], self.lab[n] = r, l
                self.segs_g.add(r)
                self.labs_g.add(l)
                anims += [GrowFromEdge(r, LEFT), FadeIn(l)]
        new_total = self._total_label(bd)
        anims.append(Transform(self.total_lab, new_total))
        self.bd = bd
        return anims


class ChartMob(LiveGroup):
    """折れ線・散布図（x: 同時実行数 C など, y: good output など）. 系列を後から足していく.

    ch.series[key] -> VGroup(点, 線),  ch.axes -> manim の Axes
    """

    def __init__(self, x_range: Sequence[float], y_range: Sequence[float], x_label: str = "", y_label: str = "",
                 box: Box | None = None, x_length: float = 6.0, y_length: float = 3.6, number_size: float = 20):
        super().__init__()
        self.axes = Axes(x_range=list(x_range), y_range=list(y_range), x_length=x_length, y_length=y_length,
                         axis_config={"color": DIM, "include_numbers": True, "font_size": number_size,
                                      "include_tip": False},
                         )
        self.add(self.axes)
        if x_label:
            self.xl = _txt(x_label, 18, DIM).next_to(self.axes.x_axis, DOWN, buff=0.45)
            self.add(self.xl)
        if y_label:
            self.yl = _txt(y_label, 18, DIM).next_to(self.axes.y_axis, UP, buff=0.12).align_to(self.axes, LEFT)
            self.add(self.yl)
        self.series: dict[str, VGroup] = {}
        self.marks: dict[str, VGroup] = {}
        _place_in_box(self, box, grow=True)

    def p(self, x: float, y: float) -> np.ndarray:
        return self.axes.c2p(x, y)

    def create(self, run_time=1.0):
        return FadeIn(VGroup(*[m for m in self.submobjects]), run_time=run_time)

    def plot(self, key: str, pts: Sequence[tuple[float, float]], color=BLUE_E, label: str | None = None,
             dot_r: float = 0.07, fail: Iterable[int] = ()) -> list:
        """系列を描く. fail に入れた番号の点は ✕ 風（中抜き）で描く."""
        fail = set(fail)
        dots = VGroup()
        for i, (x, y) in enumerate(pts):
            d = Dot(self.p(x, y), radius=dot_r, color=color)
            if i in fail:
                d.set_fill(opacity=0).set_stroke(color, width=2.5)
            dots.add(d)
        line = VGroup(*[Line(self.p(*a), self.p(*b), color=color, stroke_width=3)
                        for a, b in zip(pts, pts[1:])])
        g = VGroup(line, dots)
        if label:
            lab = _txt(label, 18, color).next_to(dots[-1], RIGHT, buff=0.12)
            g.add(lab)
        self.series[key] = g
        self.add(g)
        # 点の数によらず約 1.5 秒で出し切る（92 点を 0.2 ずつずらすと 19 秒かかった）
        lag = min(0.2, 0.5 / max(len(dots) - 1, 1))
        return [Create(line, run_time=1.5), LaggedStart(*[FadeIn(d, scale=0.5) for d in dots], lag_ratio=lag,
                                                        run_time=1.5),
                *([FadeIn(g[2])] if label else [])]

    def hline(self, key: str, y: float, label: str = "", color=RED_E) -> list:
        x0, x1 = self.axes.x_range[0], self.axes.x_range[1]
        ln = DashedLine(self.p(x0, y), self.p(x1, y), color=color, stroke_width=2.5)
        g = VGroup(ln)
        if label:
            g.add(_txt(label, 16, color).next_to(ln, UP, buff=0.05).align_to(ln, RIGHT))
        self.marks[key] = g
        self.add(g)
        return [Create(ln), *([FadeIn(g[1])] if label else [])]

    def vline(self, key: str, x: float, label: str = "", color=YELLOW_E) -> list:
        y0, y1 = self.axes.y_range[0], self.axes.y_range[1]
        ln = DashedLine(self.p(x, y0), self.p(x, y1), color=color, stroke_width=2.5)
        g = VGroup(ln)
        if label:
            g.add(_txt(label, 16, color).next_to(ln, UP, buff=0.05))
        self.marks[key] = g
        self.add(g)
        return [Create(ln), *([FadeIn(g[1])] if label else [])]

    def ring(self, key: str, i: int, color=YELLOW_E) -> Dot:
        """系列 key の i 番目の点を丸で囲む（重ね描き扱い）."""
        d = self.series[key][1][i]
        r = mark_overlay(Dot(d.get_center(), radius=0.17, color=color, fill_opacity=0).set_stroke(color, width=3))
        return r


class TimelineMob(LiveGroup):
    """時間軸（ガント図）. レーン（担当や GPU）ごとに区間の棒を置く.

    tl.lane_y(name) -> レーンの y,  tl.x(t) -> 時刻 t の x
    """

    def __init__(self, lanes: Sequence[str], t_max: float, box: Box | None = None, width: float = 9.0,
                 lane_h: float = 0.55, unit: str = "ms", ticks: Sequence[float] = (), label_size: float = 18,
                 lane_colors: dict | None = None):
        super().__init__()
        self.lanes = list(lanes)
        self.t_max, self.W, self.lh = t_max, width, lane_h
        self.lane_lab = VGroup()
        self.rails = VGroup()
        self.bars = VGroup()
        lane_colors = lane_colors or {}
        for k, name in enumerate(self.lanes):
            y = -k * (lane_h + 0.18)
            rail = Line([0, y, 0], [width, y, 0], color=DIM, stroke_width=1, stroke_opacity=0.5)
            self.rails.add(rail)
            self.lane_lab.add(_txt(name, label_size, lane_colors.get(name, FG)).next_to(rail, LEFT, buff=0.15))
        bottom = -(len(self.lanes) - 1) * (lane_h + 0.18) - lane_h / 2 - 0.1
        self.axis = Line([0, bottom, 0], [width, bottom, 0], color=DIM, stroke_width=2)
        self.tick_g = VGroup()
        for t in ticks:
            x = self.x(t)
            self.tick_g.add(Line([x, bottom, 0], [x, bottom - 0.08, 0], color=DIM, stroke_width=2),
                            _txt(f"{t:g}", 14, DIM).move_to([x, bottom - 0.25, 0]))
        self.unit_lab = _txt(unit, 14, DIM).next_to(self.axis, RIGHT, buff=0.12)
        self.add(self.rails, self.lane_lab, self.axis, self.tick_g, self.unit_lab, self.bars)
        _place_in_box(self, box, grow=True)

    def x(self, t: float) -> float:
        return self.rails[0].get_start()[0] + (self.rails[0].get_end()[0] - self.rails[0].get_start()[0]) * t / self.t_max

    def lane_y(self, name: str) -> float:
        return self.rails[self.lanes.index(name)].get_center()[1]

    def _scale(self) -> float:
        return (self.rails[0].get_end()[0] - self.rails[0].get_start()[0]) / self.W

    def bar(self, lane: str, t0: float, t1: float, color=BLUE_E, label: str = "", size: float = 14) -> VGroup:
        """区間 [t0, t1] の棒を作って登録する（表示は create_bars などで）."""
        x0, x1 = self.x(t0), self.x(t1)
        h = self.lh * self._scale()
        r = Rectangle(width=max(x1 - x0, 1e-3), height=h, stroke_color=color, stroke_width=1.5,
                      fill_color=color, fill_opacity=0.55)
        r.move_to([(x0 + x1) / 2, self.lane_y(lane), 0])
        g = VGroup(r)
        if label:
            t = _txt(label, size, FG)
            if t.width <= r.width - 0.06:
                g.add(t.move_to(r))
        self.bars.add(g)
        return g

    def create(self, run_time=1.0):
        return AnimationGroup(FadeIn(self.rails), FadeIn(self.lane_lab), Create(self.axis), FadeIn(self.tick_g),
                              FadeIn(self.unit_lab), lag_ratio=0.2, run_time=run_time)

    def grow(self, bars: Sequence[VGroup], lag: float = 0.1) -> list:
        return [LaggedStart(*[AnimationGroup(GrowFromEdge(b[0], LEFT), *[FadeIn(x) for x in b[1:]])
                              for b in bars], lag_ratio=lag)]


class ExpertGridMob(LiveGroup):
    """expert を格子に並べたもの. 選ばれた expert を光らせ，GPU ごとの持ち分を色で分ける.

    eg.cell[i] -> i 番の expert の四角
    """

    def __init__(self, n: int = 128, cols: int = 16, size: float = 0.3, gap: float = 0.06,
                 box: Box | None = None, color=DIM):
        super().__init__()
        self.n, self.cols, self.base = n, cols, color
        self.cell: list[Rectangle] = []
        for i in range(n):
            r = Rectangle(width=size, height=size, stroke_color=color, stroke_width=1.2, fill_color=color,
                          fill_opacity=0.15)
            r.move_to([(i % cols) * (size + gap), -(i // cols) * (size + gap), 0])
            self.cell.append(r)
        self.cells_g = VGroup(*self.cell)
        self.add(self.cells_g)
        _place_in_box(self, box, grow=box is not None)

    def create(self, run_time=1.2):
        return LaggedStart(*[FadeIn(c, scale=0.6) for c in self.cell], lag_ratio=min(0.05, 1.0 / self.n),
                           run_time=run_time)

    def route(self, ids: Iterable[int], color=YELLOW_E, opacity=0.85) -> list:
        """ids の expert を光らせる（Animation のリスト）."""
        return [self.cell[i].animate.set_fill(color, opacity=opacity).set_stroke(color, width=2.5) for i in ids]

    def reset(self) -> list:
        return [c.animate.set_fill(self.base, opacity=0.15).set_stroke(self.base, width=1.2) for c in self.cell]

    def partition(self, groups: int, colors: Sequence | None = None) -> list:
        """expert を前から groups 個に等分し，GPU ごとの持ち分として枠の色を変える."""
        colors = list(colors or PALETTE)
        per = self.n // groups
        return [self.cell[i].animate.set_stroke(colors[(i // per) % len(colors)], width=2.5)
                for i in range(self.n)]

    def group_frame(self, ids: Sequence[int], color, label: str = "", size: float = 18) -> VGroup:
        """ids の expert をまとめて囲む枠（重ね描き扱い）."""
        rect = SurroundingRectangle(VGroup(*[self.cell[i] for i in ids]), buff=0.05, color=color,
                                    stroke_width=3, corner_radius=min(CORNER, 0.06))
        g = VGroup(rect)
        if label:
            g.add(_txt(label, size, color).next_to(rect, LEFT, buff=0.12))
        return mark_overlay(g)


class LayerStackMob(LiveGroup):
    """Transformer の層の積み重ね. 各層を「Attention｜MoE」の2つの箱で描き，代表の数層だけ見せる.

    ls.attn[k], ls.moe[k] -> 下から k 番目に見せている層の箱
    """

    def __init__(self, shown: Sequence[int] = (1, 2, 3, 94), total: int = 94, width: float = 4.2,
                 height: float = 0.5, gap: float = 0.22, box: Box | None = None):
        super().__init__()
        self.attn, self.moe, self.labels = [], [], []
        self.layers_g = VGroup()
        y = 0.0
        prev = None
        for k, li in enumerate(shown):
            if prev is not None and li - prev > 1:
                dots = _txt("⋮", 26, DIM).move_to([width / 2, y + height / 2, 0])
                self.layers_g.add(dots)
                y += height + gap
            a = Rectangle(width=width * 0.45, height=height, stroke_color=GREEN_E, fill_color=GREEN_E,
                          fill_opacity=0.35, stroke_width=2).move_to([width * 0.225, y, 0])
            m = Rectangle(width=width * 0.5, height=height, stroke_color=BLUE_E, fill_color=BLUE_E,
                          fill_opacity=0.35, stroke_width=2).move_to([width * 0.75, y, 0])
            ta = _txt("Attention", 16, FG).move_to(a)
            tm = _txt("MoE", 16, FG).move_to(m)
            lab = _txt(f"層 {li}", 16, DIM).next_to(a, LEFT, buff=0.15)
            self.attn.append(a)
            self.moe.append(m)
            self.labels.append(lab)
            self.layers_g.add(VGroup(a, m, ta, tm, lab))
            y += height + gap
            prev = li
        self.inp = _txt("入力の語", 18, DIM).move_to([width / 2, -height - 0.1, 0])
        self.out = _txt("次の語の確率", 18, DIM).move_to([width / 2, y + 0.05, 0])
        self.total = total
        self.add(self.layers_g, self.inp, self.out)
        _place_in_box(self, box, grow=box is not None)

    def create(self, run_time=1.4):
        return AnimationGroup(FadeIn(self.inp), LaggedStart(*[FadeIn(g, shift=UP * 0.1) for g in self.layers_g],
                                                            lag_ratio=0.2), FadeIn(self.out),
                              lag_ratio=0.3, run_time=run_time)

    def token_path(self) -> Line:
        """入力から出力まで，各層の Attention → MoE を順に通る折れ線."""
        pts = [self.inp.get_top()]
        for a, m in zip(self.attn, self.moe):
            pts += [a.get_center(), m.get_center()]
        pts.append(self.out.get_bottom())
        line = Line(pts[0], pts[1])
        line.set_points_as_corners(pts)
        return line

    def pass_token(self, color=YELLOW_E, run_time=3.0, trail: bool = True) -> list:
        """1 つの語（点）が層を下から上へ通り抜ける. trail=True なら通った道筋を線で残す（self.trail）."""
        path = self.token_path()
        dot = mark_overlay(Dot(self.inp.get_top(), radius=0.13, color=color))
        dot.set_z_index(5)
        anims = [Succession(FadeIn(dot, run_time=0.2), MoveAlongPath(dot, path, run_time=run_time),
                            FadeOut(dot, run_time=0.3))]
        if trail:
            self.trail = mark_overlay(path.copy().set_stroke(color, width=3, opacity=0.6))
            self.trail.set_z_index(4)
            anims.append(Create(self.trail, run_time=run_time + 0.2))
        return anims
