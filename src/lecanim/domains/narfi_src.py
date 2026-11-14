"""本物の Narfi（https://github.com/Narfidort/Narfi ．v2 の検査器）で検査した証明を，lecanim の Trace に取り込む.

`narfi web` が出す `/api/check`（エディタが使うものと同じ）から，各行の文脈と goal（TeX 付き）を受け取り，
ソースの行（字下げ・キーワード）と合わせて `lecanim.domains.narfi.Trace` を作る．
これで ProofMob / ContextPanel / walk がそのまま使え，証明は Narfi の核が検算したものになる．

    from lecanim.domains.narfi_src import load_narfi
    traces = load_narfi("miniature24.narfi")        # {定理名: Trace}
    tr = traces["lemma.det"]

narfi の実行ファイル：環境変数 NARFI_BIN，PATH の narfi，~/.cargo/bin/narfi の順に探す
（`cargo install --path narfi` で入る）．古い書き方のファイルは `narfi migrate --write` で直してから．
"""

from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import time
import urllib.request
from contextlib import contextmanager
from pathlib import Path

from .narfi import (Assume, Atom, ByContra, Case, Cases, Choose, Entry, Exit, Fix, Have, Induction, Just, Let, Obtain,
                    ProofLine, Thm, Trace, norm)

YOMI: list[tuple[str, str]] = []

__all__ = ["load_narfi", "narfi_server", "find_narfi", "ascii2tex", "NarfiError"]


class NarfiError(RuntimeError):
    pass


# ---------------------------------------------------------------- 文字の変換
_GREEK = {"alpha": r"\alpha", "beta": r"\beta", "gamma": r"\gamma", "delta": r"\delta", "eps": r"\varepsilon",
          "epsilon": r"\varepsilon", "zeta": r"\zeta", "eta": r"\eta", "theta": r"\theta", "lambda": r"\lambda",
          "mu": r"\mu", "nu": r"\nu", "xi": r"\xi", "pi": r"\pi", "rho": r"\rho", "sigma": r"\sigma", "tau": r"\tau",
          "phi": r"\varphi", "chi": r"\chi", "psi": r"\psi", "omega": r"\omega", "Gamma": r"\Gamma",
          "Delta": r"\Delta", "Sigma": r"\Sigma", "Omega": r"\Omega", "Pi": r"\Pi"}
_UNI = {"ℕ": r"\mathbb{N}", "ℤ": r"\mathbb{Z}", "ℚ": r"\mathbb{Q}", "ℝ": r"\mathbb{R}", "ℂ": r"\mathbb{C}",
        "→": r"\to", "↦": r"\mapsto", "⇒": r"\Rightarrow", "⇔": r"\Leftrightarrow", "∀": r"\forall ", "∃": r"\exists ",
        "∧": r"\wedge ", "∨": r"\vee ", "¬": r"\neg ", "≤": r"\le ", "≥": r"\ge ", "≠": r"\ne ", "∈": r"\in ",
        "∉": r"\notin ", "⊆": r"\subseteq ", "⊂": r"\subset ", "∪": r"\cup ", "∩": r"\cap ", "∅": r"\emptyset ",
        "×": r"\times ", "·": r"\cdot ", "⊢": r"\vdash ", "⊥": r"\bot ", "∞": r"\infty ", "∑": r"\sum ",
        "α": r"\alpha ", "β": r"\beta ", "γ": r"\gamma ", "δ": r"\delta ", "ε": r"\varepsilon ", "λ": r"\lambda ",
        "μ": r"\mu ", "π": r"\pi ", "σ": r"\sigma ", "φ": r"\varphi ", "∴": r"\therefore ", "′": "'",
        "₀": "_0", "₁": "_1", "₂": "_2", "₃": "_3"}


def sanitize_tex(s: str) -> str:
    """検査器が出す TeX に混ざる Unicode（ℕ → ℝ など）を，MathTex が読める形にする."""
    for k, v in _UNI.items():
        s = s.replace(k, v)
    return s


_REL = [("<=>", r"\Leftrightarrow "), ("|->", r"\mapsto "), ("=>", r"\Rightarrow "), ("->", r"\to "),
        (">=", r"\ge "), ("<=", r"\le "), ("!=", r"\ne ")]


def ascii2tex(e: str) -> str:
    """Narfi の ASCII の式 → TeX（証明の行の表示用．完全ではないが，よく使う形を整える）."""
    e = e.strip()
    for a, b in _REL:
        e = e.replace(a, b)
    e = re.sub(r"\bforall\b", r"\\forall ", e)
    e = re.sub(r"\bexists\b", r"\\exists ", e)
    e = re.sub(r"\band\b", r"\\wedge ", e)
    e = re.sub(r"\bor\b", r"\\vee ", e)
    e = re.sub(r"\bnot\b", r"\\neg ", e)
    e = re.sub(r"\bNat\b", r"\\mathbb{N}", e)
    e = re.sub(r"\bReal\b", r"\\mathbb{R}", e)
    e = re.sub(r"\bInt\b", r"\\mathbb{Z}", e)
    e = re.sub(r"\bRat\b", r"\\mathbb{Q}", e)
    # abs(...) / |x|
    while True:
        m = re.search(r"\babs\(", e)
        if not m:
            break
        i, depth = m.end(), 1
        while i < len(e) and depth:
            depth += {"(": 1, ")": -1}.get(e[i], 0)
            i += 1
        e = e[:m.start()] + r"\left|" + e[m.end():i - 1] + r"\right|" + e[i:]
    e = sanitize_tex(e)
    e = re.sub(r"\b(max|min)\{([^{}]*)\}", lambda m: "\\" + m.group(1) + "\\{" + m.group(2) + "\\}", e)
    # ギリシャ文字の英語名（TeX の命令の中は除く）
    e = re.sub(r"(?<![\\A-Za-z])([A-Za-z]+)(?![A-Za-z])", lambda m: _GREEK.get(m.group(1), m.group(1)), e)
    # 名前の中のアンダースコア（pos_half）は添字ではない：添字は 1 文字か {…}
    e = re.sub(r"(?<![\\A-Za-z])([A-Za-z]{2,})_([A-Za-z]{2,})(?![A-Za-z])", r"\\mathrm{\1\\_\2}", e)
    # 複数文字の名前（仮定名・関数名）は立体に
    e = re.sub(r"(?<![\\A-Za-z{])([A-Za-z][A-Za-z.]{2,})(?![A-Za-z{}])",
               lambda m: r"\mathrm{" + m.group(1) + "}", e)
    return e


def _name_key(n: str) -> str:
    """名前の照合用：h_{eps} と hε を同じにする."""
    n = n.replace("\\varepsilon", "ε").replace("\\", "")
    for w, g in (("epsilon", "ε"), ("eps", "ε"), ("alpha", "α"), ("beta", "β"), ("delta", "δ"), ("lambda", "λ")):
        n = n.replace(w, g)
    return re.sub(r"[_{}\s]", "", n)


# ---------------------------------------------------------------- narfi サーバ
def find_narfi() -> str | None:
    for c in (os.environ.get("NARFI_BIN"), shutil.which("narfi"), str(Path.home() / ".cargo/bin/narfi")):
        if c and Path(c).exists():
            return c
    return None


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@contextmanager
def narfi_server(folder: str | Path = ".", binary: str | None = None):
    """`narfi web --no-open` を起動して，その URL を返す（with を出ると止める）."""
    b = binary or find_narfi()
    if not b:
        raise NarfiError("narfi が見つからない．`cargo install --path narfi`（リポジトリ https://github.com/Narfidort/Narfi）"
                         "か，環境変数 NARFI_BIN を設定する")
    port = _free_port()
    p = subprocess.Popen([b, "web", "--no-open", "--port", str(port), "--dir", str(Path(folder).resolve())],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
                break
            except OSError:
                time.sleep(0.1)
        else:
            raise NarfiError("narfi web が起動しなかった")
        yield f"http://127.0.0.1:{port}"
    finally:
        p.terminate()
        try:
            p.wait(timeout=5)
        except Exception:                                       # noqa: BLE001
            p.kill()


def _api_check(url: str, src: str, path: str) -> dict:
    host = url.split("//", 1)[1]
    req = urllib.request.Request(url + "/api/check", method="POST",
                                 data=json.dumps({"src": src, "path": path, "locale": "ja"}).encode(),
                                 headers={"Content-Type": "application/json", "Host": host, "Origin": url})
    return json.loads(urllib.request.urlopen(req, timeout=60).read())


# ---------------------------------------------------------------- ソースの読み取り
_DECL = re.compile(r"^(thm|axiom|def|const|rec|typedef|import|edition|notation|@|```|#)")
_REL_START = re.compile(r"^(=|<|>|≤|≥|<=|>=|!=|≠)\s")
_KW = ("Fix", "assume", "by_contra", "Obtain", "choose", "let", "left", "right", "cases", "induction", "Case", "sorry")


def _split_top(s: str, sep: str) -> list[str]:
    """括弧の外にある sep で分ける."""
    out, depth, cur, i = [], 0, "", 0
    while i < len(s):
        if s[i] in "([{":
            depth += 1
        elif s[i] in ")]}":
            depth -= 1
        if depth == 0 and s.startswith(sep, i):
            out.append(cur)
            cur = ""
            i += len(sep)
            continue
        cur += s[i]
        i += 1
    out.append(cur)
    return out


def _row_parts(text: str) -> list[str]:
    """ソースの 1 行 → ProofMob の行の部品（キーワードは文字，式は $…$）."""
    t = text.strip()
    kw = next((k for k in _KW if t == k or t.startswith(k + " ")), None)
    parts: list[str] = []
    if kw:
        parts.append(kw)
        t = t[len(kw):].strip()
        if not t:
            return parts
    segs = _split_top(t, " by ")
    head, just = segs[0], (" by ".join(segs[1:]) if len(segs) > 1 else None)
    bars = _split_top(head, " | ")
    for k, b in enumerate(bars):
        if k:
            parts.append("|")
        if kw in ("Case",) and k == 0:
            parts.append(f"${ascii2tex(b.replace(',', r' \, ,'))}$" if False else f"${ascii2tex(b)}$")
        else:
            parts.append(f"${ascii2tex(b)}$")
    if just:
        parts += ["by", f"${ascii2tex(just)}$"]
    return parts


def _kind_of(text: str):
    t = text.strip()
    for k, cls in (("Fix", "fix"), ("assume", "assume"), ("by_contra", "contra"), ("Obtain", "obtain"),
                   ("choose", "choose"), ("left", "choose"), ("right", "choose"), ("let", "let"), ("cases", "cases"),
                   ("induction", "ind"), ("Case", "case")):
        if t == k or t.startswith(k + " "):
            return cls
    if _REL_START.match(t):
        return "chain"
    if re.search(r"\sby\s", t):
        return "have"
    return "just"


def _entry(tex: str, kind: str = "have") -> Entry:
    tex = sanitize_tex(tex)
    m = re.match(r"^(.+?)\s*(:=|:|\\in )\s*(.*)$", tex)
    if not m:
        return Entry(tex, kind)
    name, op, rest = m.group(1).strip(), m.group(2), m.group(3).strip()
    if op == ":=":
        return Entry(name, "let", deps=())
    if op == r"\in ":                           # 変数の宣言（x \in \mathbb{R}）
        return Entry(name, kind if kind in ("fix", "param", "obtain") else "fix")
    return Entry(name, kind, rest)


class _Step:
    """ProofLine.step に入れる軽い物（kind / note / opens だけを使う）."""

    def __init__(self, kind, opens=False, note=""):
        self.kind = kind
        self._opens = opens
        self.note = note
        self.body = []
        self.concl = ""

    def opens(self):
        return self._opens


_KIND2STEP = {"fix": "fix", "assume": "assume", "contra": "contra", "obtain": "obtain", "choose": "choose",
              "let": "let", "cases": "just", "ind": "just", "case": "case", "chain": "have", "have": "have",
              "just": "just"}


def _theorem_lines(src_lines: list[str], d: dict) -> list[tuple[int, int, str]]:
    """定理 d の証明の行：[(行番号, 字下げ, 本文)]."""
    i = d["line"] - 1
    # 見出しの終わり（⊢ か |- を含む行）まで
    while i < len(src_lines) and not re.search(r"(⊢|\|-)", src_lines[i]):
        i += 1
    i += 1
    # 見出しの続きの行（字下げされた行）を飛ばす
    while i < len(src_lines) and src_lines[i].startswith((" ", "\t")) and src_lines[i].strip():
        i += 1
    out = []
    for j in range(i, len(src_lines)):
        raw = src_lines[j]
        s = raw.strip()
        if not s or s.startswith(("--", "//")):
            continue
        ind = len(raw) - len(raw.lstrip(" "))
        if ind == 0 and _DECL.match(s):
            break
        out.append((j + 1, ind, s))
    return out


def _build_trace(d: dict, src_lines: list[str]) -> Trace:
    steps = {st["line"]: st for st in d["steps"][1:]}            # 先頭は thm の行
    first = d["steps"][0] if d["steps"] else None
    plines = _theorem_lines(src_lines, d)
    if not plines:
        raise NarfiError(f"{d['name']}：証明の行がない")
    unit = min((ind for _, ind, _ in plines if ind > 0), default=2)
    n = len(plines)
    depth = [ind // unit for _, ind, _ in plines]
    kinds = [_kind_of(t) for _, _, t in plines]
    for i in range(n - 1):                                   # 式だけの行で，次の行が関係で始まる深い行なら連鎖の開始
        if kinds[i] == "just" and kinds[i + 1] == "chain" and depth[i + 1] > depth[i]:
            kinds[i] = "chain"
    # スコープを開く行（Fix / assume / by_contra / Case）とその終わり
    opens = [kinds[i] in ("fix", "assume", "contra", "case") and i + 1 < n and depth[i + 1] > depth[i] for i in range(n)]
    scope_end = [-1] * n
    for i in range(n):
        if opens[i]:
            j = i + 1
            while j < n and depth[j] > depth[i]:
                j += 1
            scope_end[i] = j - 1
    # 各行の「実行前の状態」（検査器が出した行はそれ，出さなかった行（Case など）は次に出した行のもの）
    st_line = [steps.get(l) for l, _, _ in plines]
    nxt = [None] * n
    cur = None
    for i in range(n - 1, -1, -1):
        if st_line[i] is not None:
            cur = st_line[i]
        nxt[i] = cur
    def ctx_of(st):
        return [sanitize_tex(c) for c in (st["ctx_latex"] if st else [])]

    def goal_of(st):
        return sanitize_tex(st["goal_latex"]) if st and st.get("goal_latex") else None

    hyps_ctx = ctx_of(first) if first else []
    init_entries = []
    params, hyps = [], []
    for c in hyps_ctx:
        e = _entry(c, "param")
        if e.tex:
            hyps.append((e.name, Atom(e.tex), None))
        else:
            params.append(e.name)
    goal_tex = goal_of(first) or ""
    thm = Thm(d.get("display_name") or d["name"], goal=Atom(goal_tex), body=[], hyps=hyps, params=params)
    lines: list[ProofLine] = []
    ctx_before = []
    entries_known: dict[str, Entry] = {}

    def to_entries(strs, introducing_kind):
        out = []
        for c in strs:
            e = _entry(c, "have")
            key = _name_key(e.name)
            if key in entries_known:
                out.append(entries_known[key])
            else:
                e.kind = introducing_kind if e.tex == "" or e.kind == "fix" else e.kind
                entries_known[key] = e
                out.append(e)
        return out

    names0 = [ _name_key(_entry(c).name) for c in hyps_ctx]
    for c in hyps_ctx:
        e = _entry(c, "param")
        e.kind = "hyp" if e.tex else "param"
        entries_known[_name_key(e.name)] = e
    prev_ctx = [entries_known[k] for k in names0]
    for i, (lno, ind, text) in enumerate(plines):
        st = st_line[i]
        look = nxt[i]
        gb = goal_of(st) if st else goal_of(look)
        # 実行後：次の行の「前」の状態（同じ深さ以上のとき）
        following = nxt[i + 1] if i + 1 < n else None
        after_state = following if (i + 1 < n and depth[i + 1] >= depth[i]) else None
        ga = goal_of(after_state) if after_state else None
        if kinds[i] == "case":
            gb = goal_of(look)
        closes = i + 1 >= n or depth[i + 1] < depth[i] or (depth[i + 1] == depth[i] and kinds[i + 1] == "case")
        if kinds[i] in ("fix", "assume", "contra", "case", "choose", "obtain", "let", "have", "ind", "cases") and not closes:
            pass
        if closes and kinds[i] in ("just", "chain", "have") or (closes and kinds[i] == "have"):
            ga = None
        if closes and kinds[i] not in ("just", "chain", "have"):
            ga = goal_of(after_state) if after_state else None
        ctx_after_strs = ctx_of(after_state) if after_state else (ctx_of(look) if look else [])
        cur_entries = to_entries(ctx_after_strs, {"fix": "fix", "obtain": "obtain", "assume": "assume", "contra": "assume",
                                                   "have": "have", "let": "let", "case": "assume"}.get(kinds[i], "have"))
        if after_state is None and not (kinds[i] == "case"):
            cur_entries = list(prev_ctx)
        names_prev = {_name_key(e.name) for e in prev_ctx}
        intro = [e.name for e in cur_entries if _name_key(e.name) not in names_prev]
        # 依存の注釈 N(ε)
        if kinds[i] == "obtain":
            m = re.match(r"Obtain\s+([^|\s(]+)\(([^)]*)\)", text)
            if m:
                deps = tuple(ascii2tex(x.strip()) for x in m.group(2).split(","))
                for e in cur_entries:
                    if _name_key(e.name) == _name_key(ascii2tex(m.group(1))):
                        e.deps = deps
        # 根拠に使う名前
        justification = text.split(" by ", 1)[1] if " by " in text else (text if kinds[i] == "just" else "")
        ids = {_name_key(t) for t in re.findall(r"[A-Za-z_][A-Za-z_0-9{}]*", justification)}
        uses = [e.name for e in prev_ctx if _name_key(e.name) in ids and e.kind != "param"]
        step = _Step(_KIND2STEP[kinds[i]], opens=opens[i])
        pl = ProofLine(step, depth[i], _row_parts(text), list(cur_entries), ga if not closes or kinds[i] not in ("just",) else None,
                       gb, scope_end=scope_end[i], head=_head(gb, kinds[i]), uses=uses, intro=intro)
        lines.append(pl)
        prev_ctx = cur_entries
    # 範囲の相対位置に直す（scope_end は 0 始まりの行番号のままでよい）．∴ の行を挿入
    out: list[ProofLine] = []
    remap: dict[int, int] = {}
    ends: dict[int, list[int]] = {}
    for i in range(n):
        if opens[i]:
            ends.setdefault(scope_end[i], []).append(i)
    ctx_opener = {}
    for i, pl in enumerate(lines):
        remap[i] = len(out)
        out.append(pl)
        for j in sorted(ends.get(i, []), reverse=True):           # 内側のスコープから出る
            op = lines[j]
            ex = ProofLine(Exit(concl=op.goal_before or ""), depth[j], ["∴", f"${op.goal_before or ''}$"],
                           list(ctx_opener.get(j, _ctx_before_line(lines, j, thm, entries_known))), None, None)
            out.append(ex)
    for pl in out:
        if pl.scope_end >= 0:
            pl.scope_end = _exit_index(pl, out, remap)
    return Trace(thm, out, [])


def _ctx_before_line(lines, j, thm, known):
    if j == 0:
        return [e for e in known.values() if e.kind in ("param", "hyp")]
    return lines[j - 1].ctx


def _exit_index(pl, out, remap):
    # 開いた行の scope_end：その中身の最後の行（∴ の直前）．remap は元の行番号 → out の位置
    return remap.get(pl.scope_end, pl.scope_end)


def _head(goal_before: str | None, kind: str):
    """goal の先頭で消費される部分（Fix: ∀x…，assume: φ ⇒，choose: ∃x…）— (頭の TeX, 残りの TeX)."""
    if not goal_before:
        return None
    g = goal_before
    if kind == "fix":
        m = re.match(r"^(\\forall [^,]*,)\\ (.*)$", g)
    elif kind == "choose":
        m = re.match(r"^(\\exists [^,]*,)\\ (.*)$", g)
    else:
        m = None
    return (m.group(1), m.group(2)) if m else None


# ---------------------------------------------------------------- 入口
def load_narfi(path: str | Path, server_url: str | None = None, binary: str | None = None) -> dict[str, Trace]:
    """ファイルを本物の検査器で検査し，証明のある定理を {名前: Trace} で返す（検査が通らない定理は NarfiError）."""
    path = Path(path)
    src = path.read_text()
    src_lines = src.splitlines()

    def go(url):
        r = _api_check(url, src, path.name)
        if r.get("parse_error"):
            pe = r["parse_error"]
            raise NarfiError(f"{path.name}:{pe['line']}: {pe['msg']}")
        out = {}
        for d in r["decls"]:
            if d.get("is_axiom") or not d.get("steps"):
                continue
            if d["status"] not in ("ok",):
                raise NarfiError(f"{path.name}:{d['line']} {d['name']}：{d['status']}"
                                 + (f"（{d['error']['msg']}）" if d.get("error") else ""))
            out[d["name"]] = _build_trace(d, src_lines)
        return out

    if server_url:
        return go(server_url)
    with narfi_server(path.parent, binary) as url:
        return go(url)
