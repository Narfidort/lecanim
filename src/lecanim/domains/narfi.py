"""証明のスコープ（Narfi 風）：束縛変数のスコープ・依存関係を検査して，入れ子の枠で見せる.

Narfi（自然演繹に基づく証明記述言語）の構文を参考に，証明を Python のデータとして書く:

    thm = Thm("収束列の和", goal=Forall(r"\\varepsilon", Exists("N", Forall("n", ..., bound=r"\\ge N")), bound=">0"),
              hyps=[("h_a", A), ("h_b", B)], params=["a_n", "b_n", r"\\alpha", r"\\beta"],
              body=[Fix(r"\\varepsilon", "h_\\varepsilon", body=[
                        Obtain("N_1", "h_1", "h_a", args=[r"\\tfrac{\\varepsilon}{2}"]),
                        ...])])
    tr = check(thm)            # 検査（スコープ外の参照・名前の衝突・goal の形の不一致）と各行の状態
    assert tr.ok, tr.errors

* 論理式は小さな構文木（Forall / Exists / Imp / And / Or / Not / Bot / Atom）．中身は TeX の文字列.
* Fix（∀導入）/ assume（→導入）/ by_contra（背理法）/ Case はスコープを開く．スコープを出ると変数は消える.
* Obtain（∃除去）で取り出した変数は，そのとき文脈にある変数のうち「引数に現れたもの」に依存する
  （例：Fix ε の中で Obtain N : h(ε/2) → N = N(ε)）．各点収束と一様収束の違いはこの依存関係の違い.
* choose（∃導入）の項は，そのとき文脈にある名前しか使えない（Fix z の前に N(z) は選べない）.
* 正しさ（各 have の根拠が本当に正しいか）は検査しない．検査するのはスコープと goal の形だけ.

描画：`ProofMob`（証明の行と入れ子のスコープ枠）と `ContextPanel`（文脈 Γ と goal）.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np
from manim import (DOWN, LEFT, RIGHT, UP, Arrow, Create, CurvedArrow, FadeIn, FadeOut, Indicate, Line, MathTex,
                   Rectangle, Transform, Triangle, VGroup, Write)

from .. import voice as _voice
from ..style import BG, BLUE_E, CORNER, DIM, FG, GREEN_E, ORANGE_E, PURPLE_E, RED_E, YELLOW_E, jp, row
from ..units import LiveGroup, mark_overlay

__all__ = ["walk", "scope_bars", "Formula", "Exit", "Atom", "Forall", "Exists", "Imp", "And", "Or", "Not", "Bot", "Iff",
           "Fix", "Assume", "Obtain", "Choose", "Have", "Let", "ByContra", "Contradiction", "Just", "Chain",
           "Cases", "Case", "Thm", "check", "Trace", "ProofMob", "ContextPanel", "KIND_COLOR", "mentions",
           "subst", "as_formula"]

YOMI = [("Narfi", "ナーフィ"), ("Fix", "フィックス"), ("Obtain", "オブテイン"), ("アシューム", "アシュウム"), ("assume", "アシュウム"),
        ("choose", "チューズ"), ("by_contra", "バイコントラ"), ("goal", "ゴール"), ("束縛", "そくばく"),
        ("全称", "ぜんしょう"), ("存在記号", "そんざいきごう"), ("量化子", "りょうかし"), ("文脈", "ぶんみゃく")]
_voice.register_words(YOMI)

# 種類ごとの色：未定の対象（Fix / Obtain / Case）は大文字のキーワード（Narfi の命名規則 §10.2）
KIND_COLOR = {"fix": BLUE_E, "obtain": ORANGE_E, "assume": GREEN_E, "have": FG, "let": PURPLE_E,
              "contra": RED_E, "choose": YELLOW_E, "just": DIM, "case": BLUE_E, "param": DIM, "hyp": GREEN_E}
KIND_TAG = {"fix": "任意", "obtain": "存在", "assume": "仮定", "have": "既知", "let": "定義", "contra": "仮定",
            "case": "場合", "param": "前提", "hyp": "仮定"}


# ================================================================ TeX の名前
_SKIP = r"\\(?:mathbb|mathrm|text|operatorname|mathcal|mathbf|textrm)\{[^{}]*\}"
_SUB = r"(?:_\{(?:[^{}]|\{[^{}]*\})*\}|_[A-Za-z0-9])?"
_TOK = re.compile(rf"(?P<skip>{_SKIP})|(?P<id>(?:\\[A-Za-z]+|[A-Za-z]){_SUB}'*)")


def norm(name: str) -> str:
    return name.replace("{", "").replace("}", "").replace(" ", "")


def _split(tok: str):
    m = re.match(r"(\\[A-Za-z]+|[A-Za-z])(?:_\{(.*)\}|_([A-Za-z0-9]))?('*)$", tok)
    if not m:
        return tok, None, ""
    return m.group(1), (m.group(2) if m.group(2) is not None else m.group(3)), m.group(4)


def mentions(tex: str) -> set[str]:
    """TeX に現れる名前（添字の中も見る）．`f_n` は {f_n, n}，`n_0` は {n_0, 0}．\\mathbb{N} などは除く."""
    out: set[str] = set()
    for m in _TOK.finditer(tex or ""):
        if m.group("skip"):
            continue
        tok = m.group("id")
        out.add(norm(tok))
        base, sub, _ = _split(tok)
        if sub:
            out |= mentions(sub)
    return out


def subst(tex: str, name: str, repl: str) -> str:
    """TeX 中の名前 name（添字の中も含む）を repl に置き換える."""
    key = norm(name)

    def f(m):
        if m.group("skip"):
            return m.group(0)
        tok = m.group("id")
        if norm(tok) == key:
            return repl
        base, sub, pr = _split(tok)
        if sub:
            new = subst(sub, name, repl)
            if new != sub:
                return f"{base}_{{{new}}}{pr}"
        return tok
    return _TOK.sub(f, tex or "")


# ================================================================ 論理式
class Formula:
    def tex(self, top: bool = True) -> str: ...
    def subst(self, name: str, repl: str) -> "Formula": ...

    def names(self) -> set[str]:
        """自由に現れる名前（量化子で束縛された名前は除く）."""
        return mentions(self.tex())

    def __str__(self):
        return self.tex()


@dataclass(frozen=True)
class Atom(Formula):
    s: str

    def tex(self, top=True):
        return self.s

    def subst(self, name, repl):
        return Atom(subst(self.s, name, repl))


def as_formula(x) -> Formula:
    return x if isinstance(x, Formula) else Atom(str(x))


def _bound_is_type(bound: str | None) -> bool:
    return bool(bound) and bound.strip().startswith(r"\in")


@dataclass(frozen=True)
class _Q(Formula):
    x: tuple          # 束縛する名前（複数可：∀n, m）
    body: Formula
    bound: str | None = None    # "\in E"（型）や "> 0"，"\ge N"（条件）
    sym = ""

    def __init__(self, x, body, bound=None):
        object.__setattr__(self, "x", tuple(x) if isinstance(x, (list, tuple)) else (x,))
        object.__setattr__(self, "body", as_formula(body))
        object.__setattr__(self, "bound", bound)

    def head(self) -> str:
        xs = ", ".join(self.x)
        return f"{self.sym} {xs}" + (f" {self.bound}" if self.bound else "")

    def tex(self, top=True):
        return f"{self.head()},\\ {self.body.tex(False)}"

    def subst(self, name, repl):
        if norm(name) in {norm(v) for v in self.x}:
            return self
        b = subst(self.bound, name, repl) if self.bound else self.bound
        return type(self)(self.x, self.body.subst(name, repl), b)

    def names(self) -> set[str]:
        return (self.body.names() - {norm(v) for v in self.x}) | mentions(self.bound or "")

    def cond(self, x_now: str | None = None) -> str | None:
        """束縛条件の命題（型 \\in ... は条件ではない）."""
        if not self.bound or _bound_is_type(self.bound):
            return None
        xs = ", ".join(self.x) if x_now is None else x_now
        return f"{xs} {self.bound}"


class Forall(_Q):
    sym = r"\forall"


class Exists(_Q):
    sym = r"\exists"


@dataclass(frozen=True)
class _Bin(Formula):
    a: Formula
    b: Formula
    op = ""

    def __init__(self, a, b):
        object.__setattr__(self, "a", as_formula(a))
        object.__setattr__(self, "b", as_formula(b))

    def tex(self, top=True):
        def w(x):
            return f"({x.tex(False)})" if isinstance(x, (_Bin, _Q)) else x.tex(False)
        return f"{w(self.a)} {self.op} {w(self.b)}"

    def subst(self, name, repl):
        return type(self)(self.a.subst(name, repl), self.b.subst(name, repl))

    def names(self):
        return self.a.names() | self.b.names()


class Imp(_Bin):
    op = r"\Rightarrow"


class And(_Bin):
    op = r"\wedge"


class Or(_Bin):
    op = r"\vee"


class Iff(_Bin):
    op = r"\Leftrightarrow"


@dataclass(frozen=True)
class Not(Formula):
    a: Formula

    def __init__(self, a):
        object.__setattr__(self, "a", as_formula(a))

    def tex(self, top=True):
        inner = self.a.tex(False)
        return rf"\neg ({inner})" if isinstance(self.a, (_Bin, _Q)) else rf"\neg {inner}"

    def subst(self, name, repl):
        return Not(self.a.subst(name, repl))


@dataclass(frozen=True)
class Bot(Formula):
    def tex(self, top=True):
        return r"\bot"

    def subst(self, name, repl):
        return self


# ================================================================ 証明のステップ
class Step:
    """証明の1行（スコープを開く行は body に中身を持つ）. note は行の右に出す短い説明（$...$ で数式）."""
    kind = ""
    body: list = []
    note = ""

    def opens(self) -> bool:
        return False


@dataclass
class Fix(Step):
    """∀導入：Fix x（| h : 条件）. goal ∀x … の x を「任意の x」として取り出す．スコープを出ると ∀x … が結論."""
    x: str | tuple = ""
    h: str | None = None
    body: list = field(default_factory=list)
    note: str = ""
    kind = "fix"

    def opens(self):
        return True


@dataclass
class Assume(Step):
    """→導入：assume h : φ. goal φ ⇒ ψ の φ を仮定する．スコープを出ると φ ⇒ ψ が結論."""
    h: str = ""
    prop: object = None
    body: list = field(default_factory=list)
    note: str = ""
    kind = "assume"

    def opens(self):
        return True


@dataclass
class ByContra(Step):
    """背理法：by_contra h : ¬φ. goal は ⊥ になる."""
    h: str = ""
    prop: object = None
    body: list = field(default_factory=list)
    note: str = ""
    kind = "contra"

    def opens(self):
        return True


@dataclass
class Obtain(Step):
    """∃除去：Obtain x, h : src(args). src の先頭の ∀ に args を順に入れ，残った ∃x の x と性質 h を取り出す."""
    x: str = ""
    h: str = ""
    src: str = ""
    args: list = field(default_factory=list)
    note: str = ""
    short: str | None = None     # 性質 h の表示用の短い形
    kind = "obtain"


@dataclass
class Choose(Step):
    """∃導入：choose t. goal ∃x φ(x) を φ(t) にする（t はいま文脈にある名前だけで書く）."""
    t: str = ""
    note: str = ""
    kind = "choose"


@dataclass
class Have(Step):
    """前向きの1歩：have h : φ := 根拠. close=True なら goal を閉じる."""
    h: str = ""
    prop: object = None
    by: str = ""
    close: bool = False
    note: str = ""
    kind = "have"


@dataclass
class Let(Step):
    """定義：let x := t（論理の状態は変えない）."""
    x: str = ""
    t: str = ""
    note: str = ""
    kind = "let"


@dataclass
class Contradiction(Step):
    """矛盾：h1 : φ と h2 : ¬φ から ⊥."""
    h1: str = ""
    h2: str = ""
    note: str = ""
    kind = "just"


@dataclass
class Just(Step):
    """根拠で goal を直接閉じる."""
    by: str = ""
    note: str = ""
    kind = "just"


@dataclass
class Chain(Step):
    """不等式の連鎖：t0 rel1 t1 (by j1) rel2 t2 (by j2) …．close=True なら goal を閉じる."""
    start: str = ""
    steps: list = field(default_factory=list)     # [(rel, 項, 根拠), ...]
    h: str | None = None
    close: bool = True
    note: str = ""
    kind = "have"


@dataclass
class Case(Step):
    pattern: str = ""
    binds: list = field(default_factory=list)     # [(名前, 種類 "fix"/"assume", 命題 or None)]
    body: list = field(default_factory=list)
    note: str = ""
    kind = "case"

    def opens(self):
        return True


@dataclass
class Cases(Step):
    on: str = ""
    cases: list = field(default_factory=list)
    note: str = ""
    kind = "just"


@dataclass
class Exit(Step):
    """スコープを出た所（Narfi には書かない．何が示されたかを ∴ で表示するための行）."""
    concl: str = ""
    note: str = ""
    kind = "exit"


@dataclass
class Thm:
    name: str
    goal: object
    body: list
    hyps: list = field(default_factory=list)      # [(名前, 論理式[, 表示用の短い形])]
    params: list = field(default_factory=list)    # 前提として固定された記号（f, D, …）
    lemmas: dict = field(default_factory=dict)    # 名前 → 論理式（Obtain の src に使える既知の定理）


# ================================================================ 検査
@dataclass
class Entry:
    name: str
    kind: str                 # fix / obtain / assume / have / let / contra / param / hyp
    tex: str = ""             # 仮定・性質の命題（変数なら空）
    deps: tuple = ()          # 依存する変数（Obtain / let）
    formula: Formula | None = None
    short: str | None = None  # 文脈の表示用の短い形（例 a_n \to \alpha）

    def show(self) -> str:
        if self.short:
            return f"{self.name} : {self.short}"
        if self.tex:
            return f"{self.name} : {self.tex}"
        if self.deps:
            return f"{self.name}({', '.join(self.deps)})"
        return self.name


@dataclass
class ProofLine:
    step: Step
    depth: int
    text: list                 # row() に渡す部品
    ctx: list                  # この行を実行した後の文脈
    goal: str | None           # この行を実行した後の goal（閉じたら None）
    goal_before: str | None
    scope_end: int = -1        # スコープを開く行なら，その最後の行（スコープを出る ∴ の行の直前）
    closes: list = field(default_factory=list)  # 互換用（使わない）
    head: tuple | None = None  # goal の先頭で消費される部分 (頭の TeX, 残りの TeX)：Fix / assume / choose
    uses: list = field(default_factory=list)    # 根拠として使う文脈の名前
    intro: list = field(default_factory=list)   # この行で文脈に入る名前


@dataclass
class Trace:
    thm: Thm
    lines: list
    errors: list               # [(行番号, メッセージ)]

    @property
    def ok(self) -> bool:
        return not self.errors

    def deps(self, name: str) -> tuple:
        for ln in self.lines:
            for e in ln.ctx:
                if norm(e.name) == norm(name):
                    return e.deps
        return ()


def _is_var(e: Entry) -> bool:
    return e.kind in ("fix", "obtain", "let", "param", "case")


class _Checker:
    def __init__(self, thm: Thm):
        self.thm = thm
        self.lines: list[ProofLine] = []
        self.errors: list[tuple[int, str]] = []
        self.bound_names: set[str] = set()
        self._ctx_now: list[Entry] = []
        self._collect(thm.body)

    def _collect(self, steps):
        for s in steps:
            for nm in self._intro_names(s):
                self.bound_names.add(norm(nm))
            for c in getattr(s, "cases", []):
                self._collect([c])
            self._collect(getattr(s, "body", []))

    @staticmethod
    def _intro_names(s) -> list[str]:
        if isinstance(s, Fix):
            xs = list(s.x) if isinstance(s.x, tuple) else [s.x]
            return xs + ([s.h] if s.h else [])
        if isinstance(s, Obtain):
            return [s.x, s.h]
        if isinstance(s, Let):
            return [s.x]
        if isinstance(s, (Assume, ByContra)):
            return [s.h]
        if isinstance(s, Have):
            return [s.h] if s.h else []
        if isinstance(s, Case):
            return [b[0] for b in s.binds]
        return []

    def err(self, msg):
        self.errors.append((len(self.lines), msg))

    # --- 名前の検査
    def scope_check(self, texts: list[str], ctx: list[Entry]):
        here = {norm(e.name) for e in ctx}
        for t in texts:
            for nm in mentions(t):
                if nm in self.bound_names and nm not in here:
                    self.err(f"スコープ外の名前 {nm}")

    def fresh(self, name: str, ctx: list[Entry]):
        if norm(name) in {norm(e.name) for e in ctx}:
            self.err(f"名前 {name} はすでに文脈にある（別の名前にする）")

    def deps_of(self, texts: list[str], ctx: list[Entry]) -> tuple:
        """texts に現れる，文脈中の変数（とその依存先）."""
        by = {norm(e.name): e for e in ctx}
        out: list[str] = []
        for t in texts:
            for nm in mentions(t):
                e = by.get(nm)
                if e is None or not _is_var(e) or e.kind == "param":
                    continue
                for d in (*e.deps, e.name) if e.kind in ("obtain", "let") else (e.name,):
                    if d not in out:
                        out.append(d)
        # Obtain / let の変数そのものではなく，最終的に依存する「任意の変数」まで展開
        flat: list[str] = []
        for d in out:
            e = by.get(norm(d))
            if e is not None and e.kind in ("obtain", "let"):
                continue
            if d not in flat:
                flat.append(d)
        return tuple(flat)

    # --- 1行を記録
    def emit(self, step, depth, text, ctx, goal_before, goal_after, head=None, uses_in=(), before=None) -> int:
        before = before if before is not None else self._ctx_now
        names_before = {norm(e.name) for e in before}
        intro = [e.name for e in ctx if norm(e.name) not in names_before]
        used = set()
        for t in uses_in:      # 添字の中（h_n の n）は数えない
            used |= {norm(m.group("id")) for m in _TOK.finditer(t or "") if m.group("id")}
        uses = [e.name for e in before if norm(e.name) in used and e.kind != "param"]
        self.lines.append(ProofLine(step, depth, text, list(ctx), _t(goal_after), _t(goal_before), head=head,
                                    uses=uses, intro=intro))
        self._ctx_now = list(ctx)
        return len(self.lines) - 1

    def exit(self, depth, ctx, concl):
        self.emit(Exit(concl=_t(concl)), depth, ["∴", f"${_t(concl)}$"], ctx, None, None, before=self._ctx_now)

    def block(self, steps, depth, ctx: list[Entry], goal: Formula | None) -> Formula | None:
        """steps を実行して残った goal（閉じたら None）を返す."""
        for s in steps:
            if goal is None and not isinstance(s, (Have, Let, Obtain)):
                self.err("goal はもう閉じている（余分な行）")
            goal, ctx = self.step(s, depth, ctx, goal)
        return goal

    def step(self, s, depth, ctx, goal):
        g0 = goal
        if isinstance(s, Fix):
            xs = list(s.x) if isinstance(s.x, tuple) else [s.x]
            new = list(ctx)
            if not isinstance(goal, Forall):
                self.err(f"Fix {', '.join(xs)}：goal が ∀ の形ではない")
                inner, cond = goal, None
            else:
                inner = goal.body
                if len(goal.x) != len(xs):
                    self.err(f"Fix の変数の数が goal の ∀ と合わない")
                for old, nw in zip(goal.x, xs):
                    if norm(old) != norm(nw):
                        inner = inner.subst(old, nw)
                cond = goal.cond(", ".join(xs))
                if goal.bound and _bound_is_type(goal.bound):
                    pass
            for x in xs:
                self.fresh(x, new)
                new.append(Entry(x, "fix"))
            h = None
            if cond:
                h = s.h or f"h_{{{xs[0]}}}"
                new.append(Entry(h, "assume", cond, formula=Atom(cond)))
            typ = goal.bound.strip()[3:].strip() if isinstance(goal, Forall) and _bound_is_type(goal.bound) else None
            txt = ["Fix", f"${', '.join(xs)}$"] + ([r"$\mid$", f"${h} : {cond}$"] if cond else
                                                    ([f"$: {typ}$"] if typ else []))
            head = (goal.head(), goal.body.tex()) if isinstance(goal, Forall) else None
            i = self.emit(s, depth, txt, new, g0, inner, head=head)
            rest = self.block(s.body, depth + 1, new, inner)
            self.lines[i].scope_end = len(self.lines) - 1
            if rest is not None:
                self.err(f"Fix {', '.join(xs)} のスコープの最後で goal が閉じていない")
            self.exit(depth, ctx, g0)
            return None, ctx
        if isinstance(s, (Assume, ByContra)):
            new = list(ctx)
            if isinstance(s, Assume):
                if not isinstance(goal, Imp):
                    self.err(f"assume {s.h}：goal が ⇒ の形ではない")
                    prop, inner = as_formula(s.prop), goal
                else:
                    prop, inner = (as_formula(s.prop) if s.prop is not None else goal.a), goal.b
                kw, kind = "assume", "assume"
            else:
                prop = as_formula(s.prop) if s.prop is not None else Not(goal)
                inner, kw, kind = Bot(), "by_contra", "contra"
            self.scope_check([prop.tex()], ctx)
            self.fresh(s.h, new)
            new.append(Entry(s.h, kind, prop.tex(), formula=prop))
            head = None
            if isinstance(s, Assume) and isinstance(goal, Imp):
                a = goal.a.tex(False)
                head = ((f"({a})" if isinstance(goal.a, (_Bin, _Q)) else a) + r" \Rightarrow", goal.b.tex(False))
            i = self.emit(s, depth, [kw, f"${s.h} : {prop.tex()}$"], new, g0, inner, head=head)
            rest = self.block(s.body, depth + 1, new, inner)
            self.lines[i].scope_end = len(self.lines) - 1
            if rest is not None:
                self.err(f"{kw} {s.h} のスコープの最後で goal が閉じていない")
            self.exit(depth, ctx, g0)
            return None, ctx
        if isinstance(s, Case):
            new = list(ctx)
            for nm, kind, prop in s.binds:
                self.fresh(nm, new)
                new.append(Entry(nm, kind, _t(prop) or "", formula=as_formula(prop) if prop else None))
            i = self.emit(s, depth, ["Case", s.pattern], new, g0, goal)
            rest = self.block(s.body, depth + 1, new, goal)
            self.lines[i].scope_end = len(self.lines) - 1
            if rest is not None:
                self.err(f"Case {s.pattern} の最後で goal が閉じていない")
            self.exit(depth, ctx, goal)
            return goal, ctx
        if isinstance(s, Cases):
            self.scope_check([s.on], ctx)
            self.emit(s, depth, ["cases", f"${s.on}$"], ctx, g0, goal)
            for c in s.cases:
                self.step(c, depth, ctx, goal)
            return None, ctx
        if isinstance(s, Obtain):
            src = self._lookup(s.src, ctx)
            self.scope_check([*s.args, s.src], ctx)
            f = src
            for a in s.args:
                if not isinstance(f, Forall):
                    self.err(f"Obtain {s.x}：{s.src} に引数 {a} を入れられない（∀ の形ではない）")
                    break
                xs = list(f.x)
                f = Forall(xs[1:], f.body, f.bound) if len(xs) > 1 else f.body
                f = f.subst(xs[0], a)
            if f is not None and not isinstance(f, Exists):
                if f is not None:
                    self.err(f"Obtain {s.x}：{s.src}({', '.join(s.args)}) は ∃ の形ではない")
                prop_t = f.tex() if f is not None else ""
            else:
                body = f.body
                cond = f.cond(s.x)
                if len(f.x) > 1:
                    self.err("Obtain は最外の ∃ の1変数ずつ")
                if norm(f.x[0]) != norm(s.x):
                    body = body.subst(f.x[0], s.x)
                prop = And(Atom(cond), body) if cond else body
                prop_t = prop.tex()
            new = list(ctx)
            self.fresh(s.x, new)
            deps = self.deps_of(list(s.args) + [s.src], ctx)
            new.append(Entry(s.x, "obtain", deps=deps))
            new.append(Entry(s.h, "have", prop_t, formula=Atom(prop_t), short=s.short))
            if goal is not None and norm(s.x) in goal.names():
                self.err(f"Obtain {s.x}：{s.x} が goal に現れている")
            call = s.src + (f"({', '.join(s.args)})" if s.args else "")
            self.emit(s, depth, ["Obtain", f"${s.x}, {s.h}$", ":", f"${call}$"], new, g0, goal,
                      uses_in=[s.src, *s.args])
            return goal, new
        if isinstance(s, Choose):
            self.scope_check([s.t], ctx)
            if not isinstance(goal, Exists):
                self.err(f"choose {s.t}：goal が ∃ の形ではない")
                inner = goal
            else:
                xs = list(goal.x)
                body = Exists(xs[1:], goal.body, goal.bound) if len(xs) > 1 else goal.body
                body = body.subst(xs[0], s.t)
                cond = goal.cond(s.t) if len(xs) == 1 else None
                inner = And(Atom(cond), body) if cond else body
            head = (goal.head(), goal.body.tex()) if isinstance(goal, Exists) else None
            self.emit(s, depth, ["choose", f"${s.t}$"], ctx, g0, inner, head=head, uses_in=[s.t])
            return inner, ctx
        if isinstance(s, Have):
            prop = as_formula(s.prop)
            self.scope_check([prop.tex(), s.by], ctx)
            new = list(ctx)
            if s.h:
                self.fresh(s.h, new)
                new.append(Entry(s.h, "have", prop.tex(), formula=prop))
            txt = ["have", f"${s.h + ' : ' if s.h else ''}{prop.tex()}$"] + ([":=", s.by] if s.by else [])
            after = None if s.close else goal
            self.emit(s, depth, txt, new, g0, after, uses_in=[s.by])
            return after, new
        if isinstance(s, Let):
            self.scope_check([s.t], ctx)
            new = list(ctx)
            self.fresh(s.x, new)
            new.append(Entry(s.x, "let", s.t if False else "", deps=self.deps_of([s.t], ctx)))
            self.emit(s, depth, ["let", f"${s.x} := {s.t}$"], new, g0, goal)
            return goal, new
        if isinstance(s, Chain):
            texts = [s.start] + [t for _, t, _ in s.steps] + [b for _, _, b in s.steps]
            self.scope_check(texts, ctx)
            new = list(ctx)
            after = None if s.close else goal
            self.emit(s, depth, [f"${s.start}$"], new, g0, goal)
            for k, (rel, t, by) in enumerate(s.steps):
                last = k == len(s.steps) - 1
                if last and s.h:
                    self.fresh(s.h, new)
                    new.append(Entry(s.h, "have", f"{s.start} {self._rel(s)} {s.steps[-1][1]}"))
                self.emit(s, depth + 1, [f"${rel} {t}$"] + (["by", by] if by else []), new, g0,
                          after if last else goal, uses_in=[by])
            return after, new
        if isinstance(s, Contradiction):
            self.scope_check([s.h1, s.h2], ctx)
            if not isinstance(goal, Bot):
                self.err("contradiction：goal が ⊥ ではない（by_contra の中で使う）")
            self.emit(s, depth, ["contradiction", f"${s.h1}\\ {s.h2}$"], ctx, g0, None, uses_in=[s.h1, s.h2])
            return None, ctx
        if isinstance(s, Just):
            self.scope_check([s.by], ctx)
            self.emit(s, depth, [s.by], ctx, g0, None, uses_in=[s.by])
            return None, ctx
        raise TypeError(f"未知のステップ {s!r}")

    @staticmethod
    def _rel(s: Chain) -> str:
        rels = [r for r, _, _ in s.steps]
        if any(r in ("<", ">") for r in rels):
            return "<" if any(r in ("<", r"\le", "=") for r in rels) else ">"
        return rels[-1]

    def _lookup(self, name, ctx) -> Formula | None:
        for e in reversed(ctx):
            if norm(e.name) == norm(name):
                return e.formula
        if name in self.thm.lemmas:
            return as_formula(self.thm.lemmas[name])
        self.err(f"{name} は文脈にも既知の定理にもない")
        return None


def _t(f) -> str | None:
    if f is None:
        return None
    return f.tex() if isinstance(f, Formula) else str(f)


def check(thm: Thm) -> Trace:
    """スコープ・名前・goal の形を検査し，各行の後の文脈と goal を記録する."""
    c = _Checker(thm)
    ctx = [Entry(p, "param") for p in thm.params]
    for h, f, *sh in thm.hyps:
        f = as_formula(f)
        ctx.append(Entry(h, "hyp", f.tex(), formula=f, short=sh[0] if sh else None))
    goal = as_formula(thm.goal)
    c._ctx_now = list(ctx)
    rest = c.block(thm.body, 0, ctx, goal)
    if rest is not None:
        c.errors.append((len(c.lines), "証明の最後で goal が閉じていない"))
    return Trace(thm, c.lines, c.errors)


# ================================================================ 描画
_KW_COLOR = {"Fix": BLUE_E, "Obtain": ORANGE_E, "assume": GREEN_E, "by_contra": RED_E, "choose": YELLOW_E,
             "have": FG, "let": PURPLE_E, "Case": BLUE_E, "cases": DIM, "contradiction": RED_E, "▸": DIM,
             "by": DIM, ":=": DIM, ":": DIM}


class ProofMob(LiveGroup):
    """証明の行を並べ，スコープを開く行（Fix / assume / by_contra / Case）からその終わりまでを枠で囲む.

    pm.reveal(i)：i 行目を書く（スコープを開く行なら枠も出す）
    pm.cursor(i)：カーソル（▶）を i 行目へ
    pm.mark(i, color)：i 行目を強調
    """

    def __init__(self, trace: Trace, width: float = 7.6, size: float = 22, line_buff: float = 0.16,
                 indent: float = 0.42, top_left=(-6.8, 2.2), max_height: float = 5.0, title: bool = True):
        super().__init__()
        self.trace = trace
        self.indent = indent
        rows_ = []
        for ln in trace.lines:
            if ln.step.kind == "exit":      # スコープを出た所：字下げを戻し，示されたことを緑で
                r = row("∴", ln.text[1], size=size * 0.85, color=GREEN_E, buff=0.12)
                rows_.append(r)
                continue
            parts = []
            for k, p in enumerate(ln.text):
                if isinstance(p, str) and p in _KW_COLOR and k == 0 or p in ("by", ":=", ":"):
                    parts.append(jp(p, size=size, color=_KW_COLOR[p], weight="BOLD" if k == 0 else "NORMAL"))
                else:
                    parts.append(p)
            r = row(*parts, size=size, buff=0.12)
            if ln.step.note:
                r = VGroup(r, row("— " + ln.step.note, size=size * 0.8, color=DIM)).arrange(RIGHT, buff=0.3)
            rows_.append(r)
        self.rows = VGroup(*rows_)
        self.rows.arrange(DOWN, buff=line_buff, aligned_edge=LEFT)
        for r, ln in zip(self.rows, trace.lines):
            r.shift(RIGHT * ln.depth * indent)
        head = VGroup()
        if title:
            head = row("thm", f"{trace.thm.name}", size=size, color=DIM)
            head[0].set_color(PURPLE_E)
            goal_line = row(r"$\vdash$", f"${_t(as_formula(trace.thm.goal))}$", size=size)
            head = VGroup(head, goal_line).arrange(DOWN, aligned_edge=LEFT, buff=0.1)
            if head.width > width:
                head.scale_to_fit_width(width)
        self.head = head
        body = VGroup(self.head, self.rows).arrange(DOWN, aligned_edge=LEFT, buff=0.3) if title else self.rows
        if body.width > width:
            body.scale_to_fit_width(width)
        if body.height > max_height:
            body.scale_to_fit_height(max_height)
        body.move_to(np.array([top_left[0], top_left[1], 0]), aligned_edge=UP + LEFT)
        self.body = body
        # スコープ枠
        self.boxes: dict[int, Rectangle] = {}
        for i, ln in enumerate(trace.lines):
            if ln.step.opens() and ln.scope_end >= i:
                col = KIND_COLOR.get(ln.step.kind, FG)
                top = self.rows[i].get_top()[1] + 0.07
                bot = self.rows[ln.scope_end].get_bottom()[1] - 0.07
                left = self.rows[i].get_left()[0] - 0.12
                right = body.get_right()[0] + 0.12
                rect = Rectangle(width=right - left, height=top - bot, stroke_color=col, stroke_width=2,
                                 fill_color=col, fill_opacity=0.06)
                rect.move_to([(left + right) / 2, (top + bot) / 2, 0])
                self.boxes[i] = rect
        self.add(*self.boxes.values(), self.body)
        self.arrow = Triangle(color=YELLOW_E, fill_opacity=1, stroke_width=0).rotate(-np.pi / 2).scale(0.1)
        mark_overlay(self.arrow)
        self._shown: set[int] = set()

    # --- 操作（Animation のリスト）
    def show_head(self) -> list:
        return [FadeIn(self.head)] if len(self.head) else []

    def faint(self, opacity: float = 0.18):
        """全体を薄く置いておき（証明の地図），reveal で1行ずつはっきりさせる．scene に add する前に呼ぶ."""
        for r in self.rows:
            r.set_opacity(opacity)
        for b in self.boxes.values():
            b.set_stroke(opacity=opacity).set_fill(opacity=0.0)
        self._dimmed = True
        return self

    def to_faint(self, opacity: float = 0.18) -> list:
        """表示済みの証明を薄くして，reveal で1行ずつ追い直す状態にする（Animation のリスト）."""
        self._dimmed = True
        self._shown = set()
        return [*[r.animate.set_opacity(opacity) for r in self.rows],
                *[b.animate.set_stroke(opacity=opacity).set_fill(opacity=0.0) for b in self.boxes.values()]]

    def reveal(self, i: int) -> list:
        if i in self._shown:
            return []
        self._shown.add(i)
        anims = []
        if getattr(self, "_dimmed", False):
            if i in self.boxes:
                anims.append(self.boxes[i].animate.set_stroke(opacity=1).set_fill(opacity=0.06))
            anims.append(self.rows[i].animate.set_opacity(1))
            return anims
        if i in self.boxes:
            anims.append(FadeIn(self.boxes[i]))
        anims.append(FadeIn(self.rows[i], shift=RIGHT * 0.15))
        return anims

    def reveal_all(self) -> list:
        return [FadeIn(self)]

    def cursor(self, i: int) -> list:
        p = self.rows[i].get_left() + LEFT * 0.18
        if self.arrow not in self.submobjects:
            self.arrow.move_to(p)
            self.add(self.arrow)
            return [FadeIn(self.arrow)]
        return [self.arrow.animate.move_to(p)]

    def mark(self, i: int, color=YELLOW_E) -> list:
        return [self.rows[i].animate.set_color(color)]

    def box(self, i: int):
        return self.boxes.get(i)

    def line_of(self, name: str) -> int | None:
        """名前 name を導入した行."""
        for i, ln in enumerate(self.trace.lines):
            if norm(name) in {norm(n) for n in _Checker._intro_names(ln.step)}:
                return i
        return None

    def dep_arrows(self, name: str, color=ORANGE_E) -> VGroup:
        """name を導入した行から，依存する変数を導入した行への矢印（左の余白を通る）."""
        i = self.line_of(name)
        arrows = VGroup()
        if i is None:
            return arrows
        for d in self.trace.lines[i].ctx[-2].deps if self.trace.lines[i].ctx else ():
            j = self.line_of(d)
            if j is None:
                continue
            a = CurvedArrow(self.rows[i].get_left() + LEFT * 0.08, self.rows[j].get_left() + LEFT * 0.08,
                            angle=-np.pi / 2.2, color=color, stroke_width=3, tip_length=0.15)
            arrows.add(a)
        return mark_overlay(arrows)


class ContextPanel(LiveGroup):
    """文脈 Γ（いま使える変数・仮定）と goal（いま示すこと）の表示. state(i) で i 行目を実行した後の状態へ."""

    def __init__(self, trace: Trace, left: float = 1.4, right: float = 6.9, top: float = 2.2, bottom: float = -2.7,
                 size: float = 20, show_params: bool = False):
        super().__init__()
        self.trace = trace
        self.size = size
        self.show_params = show_params
        self.l, self.r, self.t, self.b = left, right, top, bottom
        w = right - left
        self.gamma_title = row(r"文脈 $\Gamma$（いま使えるもの）", size=size, color=DIM)
        self.goal_title = row("goal（いま示すこと）", size=size, color=DIM)
        self.gamma_title.move_to([left, top, 0], aligned_edge=UP + LEFT)
        self.frame = Rectangle(width=w, height=top - bottom, stroke_color=DIM, stroke_width=1.2)
        self.frame.move_to([(left + right) / 2, (top + bottom) / 2, 0]).shift(UP * 0.05)
        self.frame.stretch_to_fit_height(top - bottom + 0.2)
        self.goal_y = bottom + 1.25
        self.sep = Line([left, self.goal_y + 0.2, 0], [right, self.goal_y + 0.2, 0], color=DIM, stroke_width=1)
        self.goal_title.move_to([left + 0.1, self.goal_y, 0], aligned_edge=UP + LEFT)
        self.gamma_title.shift(RIGHT * 0.1 + DOWN * 0.1)
        self.entries = VGroup()
        self.goal = VGroup()
        self.add(self.frame, self.gamma_title, self.sep, self.goal_title, self.entries, self.goal)
        self._keys: list[str] = []
        self._names: list[str] = []
        self._base: dict[str, float] = {}

    def entry_mob(self, name: str):
        for n, m in zip(self._names, self.entries):
            if norm(n) == norm(name):
                return m
        return None

    def highlight(self, names, color=YELLOW_E) -> list:
        """根拠として使う文脈の項目を囲んで光らせる（囲みは返り値の 2 番目．後で FadeOut）."""
        anims, boxes = [], VGroup()
        for n in names:
            m = self.entry_mob(n)
            if m is None:
                continue
            b = Rectangle(width=m.width + 0.16, height=m.height + 0.1, stroke_color=color, stroke_width=3)
            b.move_to(m)
            boxes.add(b)
            anims.append(Create(b))
        mark_overlay(boxes)
        return anims, boxes

    def split_goal(self, head: str, rest: str, kind: str = "fix"):
        """いまの goal を「消費される先頭」と「残り」の2つに分けた表示に差し替え，先頭の mobject を返す."""
        sep = r",\ " if not head.rstrip().endswith(r"\Rightarrow") else r"\ "
        m = MathTex(head + sep, rest, font_size=self.size * 1.05 * 1.25, color=YELLOW_E)
        maxw = self.r - self.l - 0.3
        if m.width > maxw:
            m.scale_to_fit_width(maxw)
        m.move_to([self.l + 0.15, self.goal_y - 0.45, 0], aligned_edge=UP + LEFT)
        self.remove(self.goal)
        self.goal = VGroup(m)
        self.add(self.goal)
        return m[0]

    def _entry(self, e: Entry) -> VGroup:
        col = KIND_COLOR.get(e.kind, FG)
        tag = jp(KIND_TAG.get(e.kind, ""), size=self.size * 0.75, color=BG, weight="BOLD")
        chip = Rectangle(width=tag.width + 0.16, height=tag.height + 0.1, fill_color=col, fill_opacity=1,
                         stroke_width=0)
        tag.move_to(chip)
        if e.short and ("$" in e.short or not e.short.isascii()):
            body = row(f"${e.name} :$", e.short, size=self.size, color=FG)     # 日本語まじりの短い表示
        else:
            body = row(f"${e.show()}$", size=self.size, color=col if e.kind in ("fix", "obtain", "let") else FG)
        g = VGroup(VGroup(chip, tag), body).arrange(RIGHT, buff=0.14)
        maxw = self.r - self.l - 0.3
        if g.width > maxw:
            g.scale_to_fit_width(maxw)
        return g

    def _layout(self, ents: list[VGroup], base_h: list[float], is_var: list[bool] | None = None):
        """変数（任意・存在・定義）は上に横並び（折り返し），仮定・性質はその下に縦並び.
        全体が入らなければ同じ倍率で縮める．base_h は各項目の元の高さ."""
        is_var = is_var or [False] * len(ents)
        y0 = self.gamma_title.get_bottom()[1] - 0.15
        room = y0 - (self.goal_y + 0.3)
        width = self.r - self.l - 0.3
        gap = 0.1
        for s in (1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.42, 0.35):
            for e, h in zip(ents, base_h):
                e.scale(s * h / e.height)
            # 変数の行
            x, y, line_h, used = 0.0, y0, 0.0, 0.0
            for e, v in zip(ents, is_var):
                if not v:
                    continue
                if x > 0 and x + e.width > width:
                    y -= line_h + gap * s
                    x, line_h = 0.0, 0.0
                e.move_to([self.l + 0.15 + x, y, 0], aligned_edge=UP + LEFT)
                x += e.width + 0.3 * s
                line_h = max(line_h, e.height)
            if any(is_var):
                y -= line_h + gap * 2 * s
            for e, v in zip(ents, is_var):
                if v:
                    continue
                e.move_to([self.l + 0.15, y, 0], aligned_edge=UP + LEFT)
                y -= e.height + gap * s
            if y0 - y <= room + 1e-6:
                break

    def _goal(self, tex: str | None, done: bool = False) -> VGroup:
        if tex is None:
            g = row("✓ 示せた", size=self.size * 1.1, color=GREEN_E)
        elif done:
            g = row("✓", f"${tex}$", size=self.size * 1.05, color=GREEN_E)
        else:
            g = row(f"${tex}$", size=self.size * 1.05, color=YELLOW_E)
        maxw = self.r - self.l - 0.3
        if g.width > maxw:
            g.scale_to_fit_width(maxw)
        g.move_to([self.l + 0.15, self.goal_y - 0.45, 0], aligned_edge=UP + LEFT)
        return g

    def _visible(self, ctx):
        return [e for e in ctx if self.show_params or e.kind != "param"]

    def initial(self, goal: str | None = None, ctx=None) -> list:
        """証明を始める前（thm の仮定と goal）."""
        tr = self.trace
        if ctx is None:
            ctx = [Entry(p, "param") for p in tr.thm.params]
            ctx += [Entry(h, "hyp", as_formula(f).tex(), short=sh[0] if sh else None) for h, f, *sh in tr.thm.hyps]
        return self._to(self._visible(ctx), goal if goal is not None else _t(as_formula(tr.thm.goal)))

    def state(self, i: int, before: bool = False, source=None) -> list:
        """i 行目を実行した後の文脈と goal へ．source を与えると，新しく入る項目はそこから出てくる."""
        ln = self.trace.lines[i]
        if before:
            return self._to(self._visible(self._ctx_before(i)), ln.goal_before)
        if ln.step.kind == "exit":
            return self._to(self._visible(ln.ctx), ln.step.concl, done=True)
        return self._to(self._visible(ln.ctx), ln.goal, source=source)

    def _ctx_before(self, i):
        if i == 0:
            tr = self.trace
            return [Entry(p, "param") for p in tr.thm.params] + [
                Entry(h, "hyp", as_formula(f).tex(), short=sh[0] if sh else None) for h, f, *sh in tr.thm.hyps]
        return self.trace.lines[i - 1].ctx

    def _openers(self, i: int) -> list[int]:
        return [j for j in range(i, -1, -1)
                if self.trace.lines[j].step.opens() and self.trace.lines[j].scope_end == i]

    def exits(self, i: int) -> list:
        """i 行目で終わるスコープを内側から順に出る．スコープごとに「呼ぶと Animation のリストを返す関数」を返す
        （出るたびに，その中で導入した変数・仮定が消え，goal の位置に結論が ✓ 付きで出る）."""
        def make(j):
            l2 = self.trace.lines[j]
            return lambda: self._to(self._visible(self._ctx_before(j)), l2.goal_before, done=True)
        return [make(j) for j in self._openers(i)]

    def _to(self, ctx: list[Entry], goal: str | None, done: bool = False, source=None) -> list:
        keys = [e.show() + e.kind for e in ctx]
        old = {k: m for k, m in zip(self._keys, self.entries)}
        new_ms = [old.get(k) if k in old else self._entry(e) for k, e in zip(keys, ctx)]
        for k, m in zip(keys, new_ms):
            self._base.setdefault(k, m.height)
        targets = [m.copy() for m in new_ms]
        self._layout(targets, [self._base[k] for k in keys],
                     [e.kind in ("fix", "obtain", "let") and not e.tex for e in ctx])
        anims = []
        for k, m, t in zip(keys, new_ms, targets):
            if k in old:
                anims.append(m.animate.move_to(t.get_center()).scale(t.width / m.width if m.width else 1))
            else:
                m.move_to(t.get_center())
                if source is not None:
                    anims.append(FadeIn(m, target_position=source.get_center(), scale=0.6))
                else:
                    anims.append(FadeIn(m, shift=LEFT * 0.2))
        for k, m in old.items():
            if k not in keys:
                anims.append(FadeOut(m, shift=RIGHT * 0.2))
        g = self._goal(goal, done=done)
        if len(self.goal):
            anims.append(Transform(self.goal, g))
        else:
            self.goal.become(g)
            anims.append(FadeIn(self.goal))
        self.remove(self.entries)
        self.entries = VGroup(*new_ms)
        self.add(self.entries)
        self._keys = keys
        self._names = [e.name for e in ctx]
        return anims


def walk(scene, pm: ProofMob, cp: ContextPanel | None, i: int, text: str | None = None, extra=(),
         run_time: float = 0.7, **_):
    """証明の i 行目を実行して見せる.

    1. 行をはっきりさせ，カーソルを移す．字幕（台本）を読み始める
    2. Fix / assume / choose：goal の先頭（消費される量化子・仮定）を色付きで分けて光らせる
       根拠を使う行（Obtain / have / 連鎖 / 根拠だけの行）：使う文脈の項目を黄色で囲む
    3. 文脈と goal を更新（Fix・assume で取り外した先頭は文脈に移る）
    4. スコープを出る ∴ の行：枠を光らせ，中で導入した名前を消し，示されたことを ✓ で出す
    """
    ln = pm.trace.lines[i]
    scene.play(*pm.reveal(i), *pm.cursor(i), *extra, run_time=run_time)
    if text:
        scene.note(text, block=False)
    if cp is None:
        scene.wait_voice()
        return
    if ln.step.kind == "exit":
        j = next((j for j in range(i - 1, -1, -1) if pm.trace.lines[j].step.opens()
                  and pm.trace.lines[j].scope_end == i - 1 and pm.trace.lines[j].depth == ln.depth), None)
        box = pm.box(j) if j is not None else None
        if box is not None:
            scene.play(box.animate.set_stroke(width=5), run_time=0.5)
        scene.play(*cp.state(i), run_time=1.0)
        if box is not None:
            scene.play(box.animate.set_stroke(width=2), run_time=0.3)
        scene.wait_voice()
        return
    src = None
    col = KIND_COLOR.get(ln.step.kind, YELLOW_E)
    if ln.head and ln.goal_before is not None:
        src = cp.split_goal(*ln.head)
        scene.play(src.animate.set_color(col).scale(1.12), run_time=0.6)
        scene.play(Indicate(src, color=col), run_time=0.8)
        for g in cp.goal:                    # 先頭を goal から切り離して単独で動かす
            if src in g.submobjects:
                g.remove(src)
        scene.add(mark_overlay(src))
    boxes = VGroup()
    if ln.uses:
        anims, boxes = cp.highlight(ln.uses)
        if anims:
            scene.play(*anims, Indicate(pm.rows[i], color=YELLOW_E, scale_factor=1.03), run_time=0.8)
    anims = cp.state(i, source=src if ln.step.kind in ("fix", "assume", "contra") else None)
    if src is not None:
        anims.append(FadeOut(src, scale=0.6))
    scene.play(*anims, *([FadeOut(boxes)] if len(boxes) else []), run_time=1.0)
    scene.wait_voice()


def scope_bars(tex, spans, buff: float = 0.14, gap: float = 0.16, size: float = 20, width: float = 4) -> VGroup:
    """量化子の作用域（スコープ）を式の下の帯で示す.
    tex は部品に分けた MathTex．spans = [(i, j, 色, ラベル)]：部品 i（量化子）から部品 j-1 までがスコープ.
    内側のスコープほど下に描く（外側の帯が内側を含むことが見える）."""
    bars = VGroup()
    base = tex.get_bottom()[1] - buff
    for k, (i, j, col, lab) in enumerate(spans):
        l = tex[i].get_left()[0]
        r = tex[j - 1].get_right()[0]
        y = base - k * gap
        bar = Line([l, y, 0], [r, y, 0], color=col, stroke_width=width)
        tick = Line([l, y, 0], [l, y + 0.1, 0], color=col, stroke_width=width)
        g = VGroup(bar, tick)
        if lab:
            t = row(lab, size=size, color=col)
            t.next_to(bar, LEFT, buff=0.12)
            g.add(t)
        bars.add(g)
    return mark_overlay(bars)
