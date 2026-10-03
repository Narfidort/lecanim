"""分野モジュール: グラフ理論.

    from lecanim import *
    from lecanim.domains.graph import *

設計方針
--------
* ``Graph``      : 純粋な組合せ構造 (頂点・辺・向き). 描画とは無関係.
                   次数・近傍・クリーク探索・彩色チェックなどを持ち,
                   アニメ内の「具体例」が本当に主張どおりかを assert で検証できる.
* 配置は lecanim.layout（layout_circle など. ``fit`` で任意の箱に収める）. ``layout_nx`` はここ.
* ``GraphMob``   : Graph を manim で描く VGroup. 頂点/辺/ラベルをキーで引け,
                   よく使う操作 (色変更・強調・減光・辺の追加削除・面の塗り)
                   を「アニメーションのリスト」として返す.

    g = Graph.complete(6)
    gm = GraphMob(g, layout_circle(g.vertices), box=Box.left())
    self.play(gm.create())
    self.play(*gm.color_edges([(0, 1), (1, 2)], RED_E))
    self.play(*gm.fade_others(keep_vertices=[0, 1, 2]))
"""

from __future__ import annotations

import itertools
import math
from typing import Hashable, Iterable

import numpy as np
from manim import (DOWN, LEFT, ORIGIN, PI, RIGHT, UP, AnimationGroup, ArcBetweenPoints, Arrow,
                   CurvedArrow,
                   Create, Dot, FadeIn, FadeOut, LaggedStart, Line, MathTex,
                   Polygon, Text, VGroup)

from .. import voice as _voice
from ..layout import Box, fit, layout_bipartite, layout_circle, layout_groups, layout_line  # noqa: F401
from ..style import DIM as _DIM
from ..style import ECOL
from ..style import FG as _FG
from ..units import LiveGroup

V = Hashable

__all__ = ["Graph", "EdgeColoring", "GraphMob", "colored_graph_mob", "crossings", "near_misses", "layout_nx"]

# この分野の読み（VOICEVOX が誤読しやすい用語・人名）. import 時に登録される.
YOMI = [("出次数", "しゅつじすう"), ("入次数", "にゅうじすう"), ("強連結", "きょうれんけつ"),
        ("偶三角形", "ぐうさんかくけい"), ("偶角形", "ぐうかくけい"), ("偶数角形", "ぐうすうかくけい"),
        ("偶閉路", "ぐうへいろ"), ("閉路", "へいろ"), ("次数", "じすう"), ("彩色", "さいしょく"), ("可約", "かやく"),
        ("Ramsey", "ラムゼー"), ("Euler", "オイラー"), ("Hamilton", "ハミルトン"), ("Kempe", "ケンペ"),
        ("Dirac", "ディラック"), ("Ore", "オア"), ("Erdős", "エルデシュ")]
SUSPECT = ["デ'/ジス", "ツヨ'", "タマ'/"]
_voice.register_words(YOMI, SUSPECT)


# =====================================================================
#   組合せ構造
# =====================================================================
class Graph:
    """単純グラフ / 単純有向グラフ."""

    def __init__(self, vertices: Iterable[V] = (), edges: Iterable[tuple] = (),
                 directed: bool = False):
        self.directed = directed
        self.vertices: list[V] = []
        self._adj: dict[V, set] = {}
        self._in: dict[V, set] = {}
        for v in vertices:
            self.add_vertex(v)
        for e in edges:
            self.add_edge(*e)

    # ---- 基本操作 ----------------------------------------------------
    def key(self, u: V, v: V) -> tuple:
        """辺の正規化キー. 無向なら頂点リストでの順序に揃える."""
        if self.directed:
            return (u, v)
        iu, iv = self.vertices.index(u), self.vertices.index(v)
        return (u, v) if iu <= iv else (v, u)

    def add_vertex(self, v: V):
        if v not in self._adj:
            self.vertices.append(v)
            self._adj[v] = set()
            self._in[v] = set()

    def add_edge(self, u: V, v: V):
        assert u != v, f"ループは扱わない: {u}"
        self.add_vertex(u)
        self.add_vertex(v)
        self._adj[u].add(v)
        if self.directed:
            self._in[v].add(u)
        else:
            self._adj[v].add(u)

    def remove_edge(self, u: V, v: V):
        self._adj[u].discard(v)
        if self.directed:
            self._in[v].discard(u)
        else:
            self._adj[v].discard(u)

    def has_edge(self, u: V, v: V) -> bool:
        return v in self._adj.get(u, ())

    @property
    def edges(self) -> list[tuple]:
        out = []
        for u in self.vertices:
            for v in self.vertices:
                if self.has_edge(u, v) and (self.directed or self.key(u, v) == (u, v)):
                    out.append((u, v))
        return out

    @property
    def n(self) -> int:
        return len(self.vertices)

    # ---- 次数・近傍 --------------------------------------------------
    def neighbors(self, v: V) -> list[V]:
        """無向: 近傍. 有向: 外近傍."""
        return [u for u in self.vertices if u in self._adj[v]]

    def in_neighbors(self, v: V) -> list[V]:
        return [u for u in self.vertices if u in self._in[v]]

    def degree(self, v: V) -> int:
        return len(self._adj[v])

    def out_degree(self, v: V) -> int:
        return len(self._adj[v])

    def in_degree(self, v: V) -> int:
        return len(self._in[v])

    def min_degree(self) -> int:
        return min(self.degree(v) for v in self.vertices)

    def sigma2(self) -> int | None:
        """σ2(G) = 非隣接2頂点の次数和の最小値 (非隣接対がなければ None)."""
        vals = [self.degree(x) + self.degree(y)
                for x, y in itertools.combinations(self.vertices, 2) if not self.has_edge(x, y)]
        return min(vals) if vals else None

    # ---- 構成 --------------------------------------------------------
    @classmethod
    def complete(cls, n_or_keys) -> "Graph":
        keys = list(range(n_or_keys)) if isinstance(n_or_keys, int) else list(n_or_keys)
        return cls(keys, itertools.combinations(keys, 2))

    @classmethod
    def cycle(cls, n_or_keys) -> "Graph":
        keys = list(range(n_or_keys)) if isinstance(n_or_keys, int) else list(n_or_keys)
        return cls(keys, [(keys[i], keys[(i + 1) % len(keys)]) for i in range(len(keys))])

    @classmethod
    def path(cls, n_or_keys) -> "Graph":
        keys = list(range(n_or_keys)) if isinstance(n_or_keys, int) else list(n_or_keys)
        return cls(keys, zip(keys, keys[1:]))

    @classmethod
    def complete_bipartite(cls, X, Y) -> "Graph":
        return cls(list(X) + list(Y), [(x, y) for x in X for y in Y])

    def copy(self) -> "Graph":
        return Graph(self.vertices, self.edges, self.directed)

    def induced(self, W: Iterable[V]) -> "Graph":
        W = [w for w in self.vertices if w in set(W)]
        return Graph(W, [(u, v) for u, v in self.edges if u in W and v in W], self.directed)

    # ---- 判定・探索 --------------------------------------------------
    def is_clique(self, S) -> bool:
        return all(self.has_edge(a, b) for a, b in itertools.combinations(S, 2))

    def cliques(self, k: int) -> list[tuple]:
        return [S for S in itertools.combinations(self.vertices, k) if self.is_clique(S)]

    def is_path(self, seq) -> bool:
        return len(set(seq)) == len(seq) and all(self.has_edge(a, b) for a, b in zip(seq, seq[1:]))

    def is_cycle(self, seq) -> bool:
        return len(seq) >= 3 and self.is_path(seq) and self.has_edge(seq[-1], seq[0])

    def is_hamiltonian_cycle(self, seq) -> bool:
        return self.is_cycle(seq) and set(seq) == set(self.vertices)

    def hamiltonian_cycle(self):
        """小さいグラフ用の全探索. 見つからなければ None."""
        vs = self.vertices
        if len(vs) < 3:
            return None
        first = vs[0]
        for perm in itertools.permutations(vs[1:]):
            seq = (first, *perm)
            if self.is_hamiltonian_cycle(seq):
                return list(seq)
        return None

    def longest_path(self):
        best = []
        for perm_len in range(len(self.vertices), 0, -1):
            for seq in itertools.permutations(self.vertices, perm_len):
                if self.is_path(seq):
                    return list(seq)
        return best

    def is_connected(self) -> bool:
        if not self.vertices:
            return True
        seen, stack = {self.vertices[0]}, [self.vertices[0]]
        while stack:
            x = stack.pop()
            nb = set(self._adj[x]) | (self._in[x] if self.directed else set())
            for y in nb:
                if y not in seen:
                    seen.add(y)
                    stack.append(y)
        return len(seen) == self.n

    def component(self, v: V, allowed: Iterable[V] | None = None) -> list[V]:
        """allowed (頂点集合) で誘導される部分グラフでの v の連結成分."""
        allowed = set(self.vertices if allowed is None else allowed)
        seen, stack = {v}, [v]
        while stack:
            x = stack.pop()
            for y in self._adj[x]:
                if y in allowed and y not in seen:
                    seen.add(y)
                    stack.append(y)
        return [u for u in self.vertices if u in seen]

    def is_proper_coloring(self, c: dict) -> bool:
        return all(c[u] != c[v] for u, v in self.edges)

    def greedy_coloring(self, order=None) -> dict:
        c = {}
        for v in order or self.vertices:
            used = {c[u] for u in self.neighbors(v) if u in c}
            c[v] = next(i for i in itertools.count() if i not in used)
        return c


class EdgeColoring(dict):
    """辺 -> 色名 の dict. キーは Graph.key で正規化."""

    def __init__(self, graph: Graph, mapping: dict | None = None, default=None):
        super().__init__()
        self.graph = graph
        if default is not None:
            for e in graph.edges:
                self[e] = default
        for (u, v), c in (mapping or {}).items():
            self[graph.key(u, v)] = c

    def __getitem__(self, e):
        return super().__getitem__(self.graph.key(*e))

    def __setitem__(self, e, c):
        super().__setitem__(self.graph.key(*e), c)

    def color_graph(self, color) -> Graph:
        return Graph(self.graph.vertices, [e for e, c in self.items() if c == color])

    def mono_cliques(self, k: int, color=None) -> list[tuple]:
        cols = [color] if color is not None else sorted(set(self.values()))
        out = []
        for c in cols:
            out += self.color_graph(c).cliques(k)
        return out

    def color_degree(self, v, color) -> int:
        return sum(1 for u in self.graph.neighbors(v) if self[(u, v)] == color)

    @classmethod
    def random(cls, graph: Graph, colors=("r", "b"), seed=0):
        rng = np.random.default_rng(seed)
        return cls(graph, {e: colors[rng.integers(len(colors))] for e in graph.edges})


# =====================================================================
#   配置
# =====================================================================
def layout_nx(graph: Graph, kind="kamada_kawai", seed=1) -> dict:
    """networkx の配置 (planar / spring / kamada_kawai)."""
    import networkx as nx
    G = nx.DiGraph() if graph.directed else nx.Graph()
    G.add_nodes_from(graph.vertices)
    G.add_edges_from(graph.edges)
    if kind == "planar":
        p = nx.planar_layout(G)
    elif kind == "spring":
        p = nx.spring_layout(G, seed=seed)
    else:
        p = nx.kamada_kawai_layout(G)
    return {k: np.array([v[0], v[1], 0.0]) for k, v in p.items()}


def crossings(graph: Graph, pos: dict, tol: float = 1e-9) -> list[tuple]:
    """直線で描いたときに交差する辺の組 (端点共有は除く). 平面描画の検証用."""
    def P(v):
        return np.asarray(pos[v], float)[:2]

    def orient(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    out = []
    E = graph.edges
    for i in range(len(E)):
        for j in range(i + 1, len(E)):
            (a, b), (c, d) = E[i], E[j]
            if len({a, b, c, d}) < 4:
                continue
            A, B, C, D = P(a), P(b), P(c), P(d)
            o1, o2, o3, o4 = orient(A, B, C), orient(A, B, D), orient(C, D, A), orient(C, D, B)
            if o1 * o2 < -tol and o3 * o4 < -tol:
                out.append((E[i], E[j]))
    return out


def near_misses(graph: Graph, pos: dict, min_dist: float = 0.25) -> list[tuple]:
    """辺が(端点以外の)頂点のすぐ近くを通る箇所. 見た目の誤読を防ぐ."""
    out = []
    for (a, b) in graph.edges:
        A, B = np.asarray(pos[a], float)[:2], np.asarray(pos[b], float)[:2]
        for v in graph.vertices:
            if v in (a, b):
                continue
            Pv = np.asarray(pos[v], float)[:2]
            t = np.clip(np.dot(Pv - A, B - A) / np.dot(B - A, B - A), 0, 1)
            if np.linalg.norm(A + t * (B - A) - Pv) < min_dist:
                out.append(((a, b), v))
    return out


# =====================================================================
#   描画
# =====================================================================
def _convex_hull(pts):
    P = sorted({(round(p[0], 6), round(p[1], 6)) for p in pts})
    if len(P) < 3:
        return [np.array([x, y, 0.0]) for x, y in P]

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, hi = [], []
    for p in P:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(P):
        while len(hi) >= 2 and cross(hi[-2], hi[-1], p) <= 0:
            hi.pop()
        hi.append(p)
    return [np.array([x, y, 0.0]) for x, y in lo[:-1] + hi[:-1]]


def _tex(s: str, size: float, color=_FG):
    return MathTex(s, font_size=size, color=color)


class GraphMob(LiveGroup):
    """Graph を描画する VGroup.

    gm[v]       -> 頂点の Dot
    gm[u, v]    -> 辺の Line / Arrow
    gm.label[v] -> ラベル
    操作系メソッドはすべて「Animation のリスト」を返すので ``self.play(*...)`` で使う.
    """

    def __init__(self, graph: Graph, pos: dict | None = None, box: Box | None = None,
                 labels=True, vertex_radius=0.12, vertex_color=_FG, edge_color=_DIM,
                 edge_width=3.5, label_size=30, label_offset=0.32, label_dirs: dict | None = None,
                 edge_colors: dict | None = None, vertex_colors: dict | None = None,
                 margin: float = 0.45, arcs: dict | None = None):
        super().__init__()
        self.graph = graph.copy()  # 描画側の追加・削除が元のグラフを壊さないように
        graph = self.graph
        pos = pos if pos is not None else layout_circle(graph.vertices, radius=2)
        self._raw = dict(pos)
        if box is not None:
            pos = fit(pos, box, margin=margin)
        self.pos = {k: np.array([*np.asarray(p, float)[:2], 0.0]) for k, p in pos.items()}
        self.r = vertex_radius
        self.edge_width = edge_width
        self.edge_color = edge_color
        self.label_size = label_size
        self.label_offset = label_offset
        # 曲線で描く辺: {(u, w): 角度(rad, 正=反時計回りに膨らむ)}
        self.arcs = {graph.key(*e): (a if graph.key(*e) == tuple(e) else -a)
                     for e, a in (arcs or {}).items()}

        self.vertices_g = VGroup()
        self.edges_g = VGroup()
        self.labels_g = VGroup()
        self.overlays = VGroup()
        self.v: dict = {}
        self.e: dict = {}
        self.label: dict = {}

        vertex_colors = vertex_colors or {}
        for k in graph.vertices:
            d = Dot(self.pos[k], radius=vertex_radius, color=vertex_colors.get(k, vertex_color))
            d.set_z_index(2)
            self.v[k] = d
            self.vertices_g.add(d)
        ec = {}
        for (u, w), c in (edge_colors or {}).items():
            ec[graph.key(u, w)] = c
        for (u, w) in graph.edges:
            self._make_edge(u, w, ec.get(graph.key(u, w), edge_color), edge_width)
        if labels:
            for k in graph.vertices:
                txt = labels.get(k) if isinstance(labels, dict) else str(k)
                if txt:
                    self.relabel(k, txt, direction=(label_dirs or {}).get(k))
        self.add(self.overlays, self.edges_g, self.vertices_g, self.labels_g)

    # ---- アクセス ----------------------------------------------------
    def __getitem__(self, k):
        if isinstance(k, tuple) and len(k) == 2 and k[0] in self.v and k[1] in self.v:
            return self.e[self.graph.key(*k)]
        if k in self.v:
            return self.v[k]
        return super().__getitem__(k)

    def edges_of(self, pairs) -> list:
        return [self[p] for p in pairs]

    def point(self, v):
        return self.v[v].get_center()

    # ---- 内部 --------------------------------------------------------
    def _line(self, u, w, color, width):
        pu, pw = self.point(u), self.point(w)
        ang = self.arcs.get(self.graph.key(u, w))
        if ang is not None and self.graph.key(u, w) != (u, w):
            ang = -ang  # 正規化キーの向きで保存しているので, 逆向きに描くときは反転
        if ang:
            if self.graph.directed:
                m = CurvedArrow(pu, pw, angle=ang, color=color, stroke_width=width, tip_length=0.2)
                # 頂点の円にかぶらないように少し縮める
                m.scale(1 - 2 * (self.r + 0.03) / max(np.linalg.norm(pw - pu), 1e-6), about_point=(pu + pw) / 2)
            else:
                m = ArcBetweenPoints(pu, pw, angle=ang, color=color, stroke_width=width)
            m.set_fill(opacity=0)
            m.set_z_index(0)
            return m
        if self.graph.directed:
            m = Arrow(pu, pw, buff=self.r + 0.03, color=color, stroke_width=width,
                      tip_length=0.2, max_tip_length_to_length_ratio=0.3,
                      max_stroke_width_to_length_ratio=20)
        else:
            m = Line(pu, pw, color=color, stroke_width=width)
        m.set_z_index(0)
        return m

    def _make_edge(self, u, w, color, width):
        m = self._line(u, w, color, width)
        self.e[self.graph.key(u, w)] = m
        self.edges_g.add(m)
        self._follow_edge(m, u, w)
        return m

    def _follow_overlay(self, m, u, w):
        """重ね描きの線 (path_mob など) も頂点・曲線設定に追従させる."""
        state = {"p": (self.point(u).copy(), self.point(w).copy()), "arc": self.arcs.get(self.graph.key(u, w))}

        def upd(mob):
            pu, pw = self.v[u].get_center(), self.v[w].get_center()
            arc = self.arcs.get(self.graph.key(u, w))
            if np.allclose(pu, state["p"][0]) and np.allclose(pw, state["p"][1]) and arc == state["arc"]:
                return
            state["p"], state["arc"] = (pu.copy(), pw.copy()), arc
            op = mob.get_stroke_opacity()
            mob.become(self._line(u, w, mob.get_stroke_color(), mob.get_stroke_width()).set_stroke(opacity=op))
            mob.set_z_index(1)
        m.add_updater(upd)

    def _follow_edge(self, m, u, w):
        """頂点が動くと辺が自動でついてくる updater."""
        last = {"p": (self.point(u).copy(), self.point(w).copy())}

        def upd(mob):
            pu, pw = self.v[u].get_center(), self.v[w].get_center()
            if np.allclose(pu, last["p"][0]) and np.allclose(pw, last["p"][1]):
                return
            last["p"] = (pu.copy(), pw.copy())
            self.pos[u], self.pos[w] = pu.copy(), pw.copy()
            new = self._line(u, w, mob.get_stroke_color(), mob.get_stroke_width())
            if isinstance(mob, Line) and not hasattr(mob, "tip") and not self.arcs.get(self.graph.key(u, w)):
                mob.put_start_and_end_on(pu, pw)
            else:
                op = mob.get_stroke_opacity()
                mob.become(new.set_stroke(opacity=op))
                tip = getattr(mob, "tip", None)
                if tip is not None:
                    tip.set_fill(mob.get_stroke_color(), opacity=op)
        m.add_updater(upd)

    def _label_pos(self, k, direction=None):
        p = self.point(k)
        if direction is None:
            # 隣接辺を避ける向き: 近傍方向の平均の逆, 無ければ重心から外向き
            nbs = [u for u in self.graph.vertices
                   if self.graph.has_edge(k, u) or self.graph.has_edge(u, k)]
            if nbs:
                vecs = [self.point(u) - p for u in nbs]
                vecs = [vv / (np.linalg.norm(vv) + 1e-9) for vv in vecs]
                d = -np.sum(vecs, axis=0)
            else:
                d = np.zeros(3)
            if np.linalg.norm(d) < 0.3:
                c = np.mean([self.point(u) for u in self.graph.vertices], axis=0)
                d = p - c if np.linalg.norm(p - c) > 1e-6 else UP
            direction = d / np.linalg.norm(d)
        return p + np.asarray(direction, float) * (self.r + self.label_offset)

    def relabel(self, k, txt: str, direction=None, color=_FG):
        lab = _tex(txt, self.label_size, color)
        lab.move_to(self._label_pos(k, direction))
        lab.set_z_index(3)
        off = lab.get_center() - self.point(k)
        lab.add_updater(lambda l, k=k, off=off: l.move_to(self.v[k].get_center() + off))
        if k in self.label:
            self.labels_g.remove(self.label[k])
        self.label[k] = lab
        self.labels_g.add(lab)
        return lab

    # ---- 生成 --------------------------------------------------------
    def create(self, lag=0.05, run_time=1.6):
        parts = [LaggedStart(*[FadeIn(d, scale=0.5) for d in self.vertices_g], lag_ratio=lag)]
        if len(self.edges_g):
            parts.append(LaggedStart(*[Create(e) for e in self.edges_g], lag_ratio=lag))
        if len(self.labels_g):
            parts.append(FadeIn(self.labels_g))
        return AnimationGroup(*parts, lag_ratio=0.3, run_time=run_time)

    # ---- 頂点の追加 --------------------------------------------------
    def add_vertex(self, k, point, color=_FG, label: str | None = None) -> list:
        """描画座標 point に頂点を追加 (fit 済みの座標系で指定)."""
        self.graph.add_vertex(k)
        self.pos[k] = np.asarray(point, float)
        d = Dot(self.pos[k], radius=self.r, color=color)
        d.set_z_index(2)
        self.v[k] = d
        self.vertices_g.add(d)
        anims = [FadeIn(d, scale=0.5)]
        if label:
            anims.append(FadeIn(self.relabel(k, label)))
        return anims

    def to_scene(self, p) -> np.ndarray:
        """元の(fit 前の)座標 → 描画座標. 頂点2つ以上の配置から相似変換を推定."""
        ks = [k for k in self._raw if k in self.pos][:2]
        a0, b0 = (np.asarray(self._raw[k], float)[:2] for k in ks)
        a1, b1 = (self.pos[k][:2] for k in ks)
        sc = np.linalg.norm(b1 - a1) / np.linalg.norm(b0 - a0)
        q = a1 + (np.asarray(p, float)[:2] - a0) * sc
        return np.array([q[0], q[1], 0.0])

    def remove_vertex(self, k) -> list:
        """頂点と接続辺・ラベルを構造ごと取り除く (FadeOut のリストを返す)."""
        out = []
        for key in [e for e in self.e if k in e]:
            m = self.e.pop(key)
            m.clear_updaters()
            self.edges_g.remove(m)
            out.append(FadeOut(m))
        d = self.v.pop(k)
        self.vertices_g.remove(d)
        out.append(FadeOut(d))
        if k in self.label:
            lab = self.label.pop(k)
            lab.clear_updaters()
            self.labels_g.remove(lab)
            out.append(FadeOut(lab))
        nbrs = list(self.graph.neighbors(k))
        for u in nbrs:
            self.graph.remove_edge(k, u)
            if self.graph.directed:
                self.graph.remove_edge(u, k)
        self.graph.vertices.remove(k)
        del self.graph._adj[k]
        del self.graph._in[k]
        for u in self.graph.vertices:
            self.graph._adj[u].discard(k)
            self.graph._in[u].discard(k)
        return out

    # ---- 辺の追加・削除 ----------------------------------------------
    def add_edge(self, u, w, color=None, width=None, anim=Create, arc: float | None = None) -> list:
        self.graph.add_edge(u, w)
        if arc is not None:
            self.arcs[self.graph.key(u, w)] = arc if self.graph.key(u, w) == (u, w) else -arc
        m = self._make_edge(u, w, color or self.edge_color, width or self.edge_width)
        return [anim(m)]

    def remove_edge(self, u, w) -> list:
        k = self.graph.key(u, w)
        m = self.e.pop(k)
        m.clear_updaters()
        self.graph.remove_edge(u, w)
        self.edges_g.remove(m)
        return [FadeOut(m)]

    def reverse_edge(self, u, w) -> list:
        """有向辺 (u,w) を (w,u) に."""
        old = self.e.pop((u, w))
        self.graph.remove_edge(u, w)
        self.graph.add_edge(w, u)
        new = self._line(w, u, old.get_color(), old.get_stroke_width())
        self.e[(w, u)] = new
        self.edges_g.remove(old)
        self.edges_g.add(new)
        from manim import ReplacementTransform
        return [ReplacementTransform(old, new)]

    # ---- 色・強調 ----------------------------------------------------
    @staticmethod
    def edge_style(m, color=None, opacity=None, width=None) -> list:
        """辺 (Line/Arc/Arrow) の線だけを変える. 弧に塗りが入らないよう fill は触らない
        (矢印の先端だけは fill で塗る)."""
        from manim import ApplyFunction
        kw = {k: v for k, v in (("color", color), ("opacity", opacity), ("width", width)) if v is not None}
        fk = {k: v for k, v in (("color", color), ("opacity", opacity)) if v is not None}
        if not kw:
            return []

        def f(mob):
            mob.set_stroke(**kw)
            tip = getattr(mob, "tip", None)
            if tip is not None and fk:
                tip.set_fill(**fk)
                tip.set_stroke(**{k: v for k, v in fk.items()})
            return mob
        return [ApplyFunction(f, m)]

    def color_edges(self, pairs, color, width=None, opacity=1.0) -> list:
        return [a for p in pairs for a in self.edge_style(self[p], color, opacity, width)]

    def color_vertices(self, vs, color, scale=None) -> list:
        out = []
        for v in vs:
            a = self.v[v].animate.set_color(color)
            if scale:
                a = a.scale(scale)
            out.append(a)
        return out

    @staticmethod
    def pairs_of(seq, close=False) -> list[tuple]:
        pairs = list(zip(seq, seq[1:]))
        if close:
            pairs.append((seq[-1], seq[0]))
        return pairs

    def highlight_path(self, seq, color, width=8, close=False) -> list:
        return self.color_edges(self.pairs_of(seq, close), color, width)

    def path_mob(self, seq, color, width=9, close=False) -> VGroup:
        """辺の上に重ねる太線 (元の辺の色を変えずに経路を示したいとき)."""
        g = VGroup()
        for a, b in self.pairs_of(seq, close):
            m = self._line(a, b, color, width)
            m.set_z_index(1)
            self._follow_overlay(m, a, b)
            g.add(m)
        for x in g.get_family():
            x._qa_overlay = True
        return g

    def fade_others(self, keep_vertices=(), keep_edges=(), opacity=0.15) -> list:
        kv = set(keep_vertices)
        ke = {self.graph.key(*e) for e in keep_edges}
        out = []
        for k, d in self.v.items():
            if k not in kv:
                out.append(d.animate.set_opacity(opacity))
                if k in self.label:
                    out.append(self.label[k].animate.set_opacity(opacity))
        for k, m in self.e.items():
            if k not in ke:
                out += self.edge_style(m, opacity=opacity)
        return out

    def unfade(self) -> list:
        out = [m.animate.set_opacity(1) for m in [*self.v.values(), *self.label.values()]]
        for m in self.e.values():
            out += self.edge_style(m, opacity=1)
        return out

    def face(self, seq, color, opacity=0.3) -> Polygon:
        """頂点列で囲まれた多角形 (独立した Mobject. 頂点が動くとついてくる)."""
        seq = list(seq)
        poly = Polygon(*[self.point(v) for v in seq], stroke_width=0, fill_color=color,
                       fill_opacity=opacity)
        poly.set_z_index(-1)
        poly._qa_overlay = True
        poly.add_updater(lambda m: m.set_points_as_corners(
            [*[self.v[v].get_center() for v in seq], self.v[seq[0]].get_center()]))
        return poly

    def blob(self, vs, color, pad=0.38, opacity=0.12, width=3, label: str | None = None,
             label_dir=UP, label_size=30) -> VGroup:
        """頂点集合を囲む丸い領域 (凸包を膨らませたもの). 頂点が動くとついてくる.
        「円で囲ってグループ分けする」用."""
        vs = list(vs)

        def shape():
            pts = []
            for v in vs:
                c = self.v[v].get_center()
                pts += [c + pad * np.array([math.cos(t), math.sin(t), 0]) for t in np.linspace(0, 2 * PI, 24, endpoint=False)]
            hull = _convex_hull(pts)
            return hull

        poly = Polygon(*shape(), color=color, stroke_width=width, fill_color=color, fill_opacity=opacity)
        poly.set_z_index(-2)
        poly.add_updater(lambda m: m.set_points_as_corners([*shape(), shape()[0]]))
        g = VGroup(poly)
        if label:
            from manim import Mobject as _M
            if isinstance(label, _M):
                lab = label
            else:
                from ..style import JP_FONT
                lab = (Text(label, font=JP_FONT, font_size=label_size * 0.8, color=color)
                       if any(ord(ch) > 127 for ch in label) else _tex(label, label_size, color))
            lab.add_updater(lambda l: l.next_to(poly, label_dir, buff=0.08))
            g.add(lab)
        g._qa_overlay = True
        for x in g.get_family():
            x._qa_overlay = True
        return g

    def set_arcs(self, arcs: dict):
        """曲線で描く辺を設定し直す (以後の追従で反映. {} なら全て直線)."""
        self.arcs = {self.graph.key(*e): (a if self.graph.key(*e) == tuple(e) else -a) for e, a in arcs.items()}
        for (u, w), m in self.e.items():
            new = self._line(u, w, m.get_stroke_color(), m.get_stroke_width())
            op = m.get_stroke_opacity()
            m.become(new.set_stroke(opacity=op))

    def layout_to(self, new_pos: dict, **kw) -> list:
        """頂点を新しい位置へ動かす (辺・ラベル・面・囲みは自動追従). アニメーションのリスト."""
        return [self.v[k].animate(**kw).move_to(np.array([*np.asarray(p, float)[:2], 0.0]))
                for k, p in new_pos.items()]

    def annotate(self, v, txt: str, color="#ffd166", size=24, direction=None, buff=0.5) -> MathTex:
        """頂点の脇に小さな注記 (次数など). ラベルの反対側に置く."""
        m = _tex(txt, size, color)
        if direction is None:
            lab = self.label.get(v)
            p = self.point(v)
            d = (p - lab.get_center()) if lab is not None else UP
            direction = d / (np.linalg.norm(d) + 1e-9)
        m.move_to(self.point(v) + np.asarray(direction) * buff)
        m.set_z_index(3)
        m._qa_overlay = True
        off = m.get_center() - self.point(v)
        m.add_updater(lambda mob: mob.move_to(self.v[v].get_center() + off))
        return m

    # ---- 移動 --------------------------------------------------------
    def move_vertices(self, new_pos: dict) -> list:
        return self.layout_to(new_pos)


def colored_graph_mob(coloring: EdgeColoring, pos=None, box=None, width=4.5, **kw) -> GraphMob:
    """EdgeColoring ('r','b',...) をそのまま色付きで描く."""
    return GraphMob(coloring.graph, pos, box=box, edge_width=width,
                    edge_colors={e: ECOL.get(c, c) for e, c in coloring.items()}, **kw)
