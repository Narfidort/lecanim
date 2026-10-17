"""読み（誤読）の管理：辞書の層・自動検出・蓄積.

辞書は 4 層で，上のものが先に適用される（プロジェクト固有 → 利用者 → 分野 → 汎用）：
  1. プロジェクト   <プロジェクト>/yomi.toml            そのプロジェクトだけの語
  2. 利用者         ~/.config/lecanim/yomi.toml          自分の全プロジェクトで使う（指摘のたびにここへ溜まる）
  3. 分野           lecanim.domains.<分野>.YOMI           分野の用語・人名
  4. 汎用           lecanim.voice.BASE_WORDS と data/yomi/learned.toml（リポジトリに入れて共有する）

誤読の見つけ方（人の耳に頼らない）：
  * `lecanim yomi scan`  形態素解析 UniDic（fugashi）の読みと，VOICEVOX の読みを突き合わせ，食い違う語を列挙する．
    VOICEVOX（OpenJTalk）とは別の辞書なので，OpenJTalk の癖（行→くだり，帯→たい，値→ね…）が拾える．
  * `lecanim yomi verify` 辞書に入れた語の例文を VOICEVOX に読ませ，期待どおりに読まれるか確かめる（回帰テスト）．
追加は `lecanim yomi add 語 読み`．例文をつけると verify の対象になる．
"""

from __future__ import annotations

import difflib
import json
import re
import sys
import tomllib
from pathlib import Path

USER_FILE = Path.home() / ".config" / "lecanim" / "yomi.toml"
DATA_DIR = Path(__file__).parent / "data" / "yomi"
LEARNED = DATA_DIR / "learned.toml"
IGNORE = DATA_DIR / "scan_ignore.toml"

_VOW = {"ア": "アカガサザタダナハバパマヤャラワ", "イ": "イキギシジチヂニヒビピミリ", "ウ": "ウクグスズツヅヌフブプムユュル",
        "エ": "エケゲセゼテデネヘベペメレ", "オ": "オコゴソゾトドノホボポモヨョロヲ"}
_ROW = {c: v for v, cs in _VOW.items() for c in cs}


def to_kata(s: str) -> str:
    return "".join(chr(ord(c) + 0x60) if "ぁ" <= c <= "ゖ" else c for c in s)


def norm_kana(s: str) -> str:
    """読みの比較用の正規化：アクセント記号・区切りを除き，長音を揃える（ー，オ段+ウ，エ段+イ → 前の母音）."""
    s = to_kata(re.sub(r"[’'_/、。？?・ 　]", "", s))
    out = []
    for c in s:
        prev = out[-1] if out else ""
        row = _ROW.get(prev, "")
        if c == "ー" and row:
            out.append({"ア": "ア", "イ": "イ", "ウ": "ウ", "エ": "エ", "オ": "オ"}[row])
        elif c == "ウ" and row == "オ":
            out.append("オ")
        elif c == "イ" and row == "エ":
            out.append("エ")
        elif c == "ヲ":
            out.append("オ")
        else:
            out.append(c)
    return "".join(out)


# ---------------------------------------------------------------- 辞書ファイル
def _load(path: Path) -> dict:
    return tomllib.loads(path.read_text()) if path.exists() else {}


def user_words() -> list[tuple[str, str]]:
    return [tuple(w[:2]) for w in _load(USER_FILE).get("words", [])]


def learned_words() -> list[tuple[str, str]]:
    return [tuple(w[:2]) for w in _load(LEARNED).get("words", [])]


def scope_path(scope: str, root: Path | None = None) -> Path:
    if scope == "user":
        return USER_FILE
    if scope == "repo":
        return LEARNED
    if scope == "project":
        from .config import ROOT
        return (root or ROOT) / "yomi.toml"
    raise ValueError(scope)


def add_word(surface: str, reading: str, scope: str = "user", example: str | None = None,
             root: Path | None = None) -> Path:
    """辞書に語を追加する（同じ語があれば読みを置き換える）. コメントは保つ."""
    p = scope_path(scope, root)
    p.parent.mkdir(parents=True, exist_ok=True)
    entry = json.dumps([surface, reading] + ([example] if example else []), ensure_ascii=False)
    if not p.exists():
        p.write_text(f"# lecanim の読みの辞書（{scope}）．`lecanim yomi add 語 読み` で追加する\nwords = [\n  {entry},\n]\n")
        return p
    txt = p.read_text()
    pat = re.compile(r'^\s*\[\s*"' + re.escape(surface) + r'"\s*,[^\n]*\],?\s*$', re.M)
    if pat.search(txt):
        txt = pat.sub(f"  {entry},", txt, count=1)
    else:
        m = re.search(r"^words\s*=\s*\[", txt, re.M)
        if not m:
            txt += f"\nwords = [\n  {entry},\n]\n"
        else:
            i = txt.index("\n]", m.end()) if "\n]" in txt[m.end():] else None
            j = (m.end() + txt[m.end():].index("\n]")) if i is not None else None
            txt = txt[:j] + f"\n  {entry}," + txt[j:]
    p.write_text(txt)
    return p


def _ignored() -> set[str]:
    return set(_load(IGNORE).get("ok", []))


def mark_ok(surface: str) -> None:
    ok = sorted(_ignored() | {surface})
    IGNORE.parent.mkdir(parents=True, exist_ok=True)
    IGNORE.write_text("# 読みの食い違いを確認して「このままでよい」とした語（lecanim yomi ok）\nok = "
                      + json.dumps(ok, ensure_ascii=False, indent=1) + "\n")


# ---------------------------------------------------------------- 形態素解析との突き合わせ
_TAGGER = None


def tagger():
    global _TAGGER
    if _TAGGER is None:
        try:
            import fugashi
        except ImportError:
            raise SystemExit("読みの自動検出には fugashi と unidic-lite が要ります：uv pip install fugashi unidic-lite"
                             "（または pip install 'lecanim[yomi]'）")
        _TAGGER = fugashi.Tagger()
    return _TAGGER


def analyze(spoken: str) -> list[tuple[str, str]]:
    """読み上げ文 → [(表層, 読み（数字・記号は空）)]．長音の正規化は文全体で行う（語の境目をまたぐため）."""
    raw = []
    for w in tagger()(spoken):
        pron = getattr(w.feature, "pron", None) or getattr(w.feature, "kana", None)
        if (not pron or pron == "*") and re.fullmatch(r"[ァ-ヶー]+", w.surface):
            pron = w.surface                                   # カタカナ語（エーエヌ，イプシロン）は表層が読み
        if not pron or pron == "*" or not re.search(r"[ぁ-んァ-ヶー一-龥]", w.surface):
            raw.append((w.surface, ""))
        else:
            raw.append((w.surface, to_kata(re.sub(r"[’'_/、。？?・ 　]", "", pron))))
    joined = norm_kana("".join(r for _, r in raw))
    out, pos = [], 0
    for sf, r in raw:
        out.append((sf, joined[pos:pos + len(r)]))
        pos += len(r)
    return out


# 表記と発音のゆれ：(表層, UniDic の読み) → VOICEVOX が書く読み．食い違いではない
_EQUIV = {("いう", "ユウ"): "イウ", ("言う", "ユウ"): "イウ", ("という", "トユウ"): "トイウ", ("いわゆる", "イワユル"): "イワユル"}


def scan_sentence(spoken: str, vv_kana: str) -> list[dict]:
    """1文について，UniDic の読みと VOICEVOX の読みが食い違う語を返す
    [{"surface", "unidic", "voicevox", "context"}]．文字列の対応は difflib で取り，語ごとに VOICEVOX 側の区間を求める."""
    toks = analyze(spoken)
    u = "".join(r for _, r in toks)
    v = norm_kana(vv_kana)
    if not u or not v:
        return []
    bounds, pos = [], 0
    for sf, r in toks:
        bounds.append((pos, pos + len(r), sf, r))
        pos += len(r)
    sm = difflib.SequenceMatcher(None, u, v, autojunk=False)
    ops = sm.get_opcodes()
    m = [0] * (len(u) + 1)                 # u の位置 → v の位置
    for op, i1, i2, j1, j2 in ops:
        n = i2 - i1
        for k in range(n):
            m[i1 + k] = j1 + (round(k * (j2 - j1) / n) if op == "replace" else min(k, max(j2 - j1 - 1, 0)))
    m[len(u)] = len(v)
    bad = set()                              # 食い違いのある u の位置
    for op, i1, i2, j1, j2 in ops:
        if op in ("replace", "delete"):
            bad.update(range(i1, i2))
    found = []
    for k, (lo, hi, sf, r) in enumerate(bounds):
        if not r or (sf, r) in _EQUIV and v[m[lo]:m[hi]] == _EQUIV[(sf, r)]:
            continue
        if not any(p in bad for p in range(lo, hi)):
            continue
        vv = v[m[lo]:m[hi]]
        if vv == r:
            continue
        ctx = "".join(bounds[q][2] for q in range(max(0, k - 2), min(len(bounds), k + 3)))
        found.append({"surface": sf, "unidic": r, "voicevox": vv, "context": ctx})
    return found


def _import_domains() -> None:
    """分野モジュールの読み辞書は import 時に登録される．スキャンの前に全部読み込む."""
    import importlib
    import pkgutil

    import lecanim.domains as d
    for m in pkgutil.iter_modules(d.__path__):
        if not m.name.startswith("_"):
            importlib.import_module(f"lecanim.domains.{m.name}")


def scan_texts(items: list[tuple[str, str]], speaker: int | None = None) -> dict[str, dict]:
    """[(場所, 台本の文)] → {語: {"unidic", "voicevox", "where": [場所…], "context"}}（食い違いのある語）."""
    from . import voice as v
    _import_domains()
    sp = v.SPEAKER if speaker is None else speaker
    res: dict[str, dict] = {}
    ign = _ignored()
    for where, text in items:
        for sent in re.split(r"(?<=。)", v.yomi(text)):
            if not sent.strip():
                continue
            kn = v.kana(sent, sp)
            if not kn:
                continue
            for f in scan_sentence(sent, kn):
                if f["surface"] in ign or not re.search(r"[一-龥ぁ-んァ-ヶ]", f["surface"]):
                    continue
                e = res.setdefault(f["surface"], {"unidic": f["unidic"], "voicevox": f["voicevox"], "where": [],
                                                  "context": f["context"]})
                if where not in e["where"]:
                    e["where"].append(where)
    return res


def verify_entries(root: Path | None = None) -> list[tuple[str, str, str, str]]:
    """例文つきの辞書項目を VOICEVOX で読ませ，読みが期待どおりか確かめる. 失敗した [(語, 読み, 例文, 実際の読み)]."""
    from . import voice as v
    bad = []
    for scope in ("repo", "user", "project"):
        for w in _load(scope_path(scope, root)).get("words", []):
            if len(w) < 3:
                continue
            surface, reading, example = w[0], w[1], w[2]
            kn = norm_kana(v.kana(v.yomi(example)))
            if norm_kana(reading) not in kn:
                bad.append((surface, reading, example, kn))
    return bad


# ---------------------------------------------------------------- CLI
def cmd_yomi(a):
    from .config import find_root
    root = find_root()
    sub = a.yomi_cmd
    if sub == "add":
        p = add_word(a.surface, a.reading, a.scope, a.example, root)
        print(f"追加しました（{a.scope}）: {a.surface} → {a.reading}   {p}")
        from . import voice as v
        if a.example and v.available(2):
            print("  例文の読み:", v.kana(v.yomi(a.example)))
    elif sub == "ok":
        mark_ok(a.surface)
        print(f"「{a.surface}」はこのままでよいとして記録しました")
    elif sub == "list":
        for name, ws in (("利用者", user_words()), ("汎用（learned）", learned_words())):
            print(f"[{name}] {len(ws)} 語")
            for s, r in ws:
                print(f"  {s} → {r}")
    elif sub == "scan":
        from .cli import lecture_files
        from .narration import SCRIPTS
        items = []
        for sc, lines in SCRIPTS.items():
            for k, t in lines:
                if t:
                    items.append((f"{sc} {k[:14]}", t))
        res = scan_texts(items)
        if not res:
            print("UniDic と VOICEVOX の読みの食い違いはありません")
            return
        print(f"読みの食い違い {len(res)} 語（UniDic と VOICEVOX が違う．どちらが正しいか確認し，直すなら "
              "`lecanim yomi add 語 読み`，このままなら `lecanim yomi ok 語`）")
        for s, e in sorted(res.items(), key=lambda x: -len(x[1]["where"])):
            print(f"  {s:<10} UniDic: {e['unidic']:<14} VOICEVOX: {e['voicevox']:<14} …{e['context']}…  ({len(e['where'])} 箇所)")
        sys.exit(1 if a.strict else 0)
    elif sub == "verify":
        bad = verify_entries(root)
        if not bad:
            print("辞書の例文はすべて期待どおりに読まれました")
            return
        for s, r, ex, kn in bad:
            print(f"  ✗ {s} → {r} のはずが：{kn[:40]}   （{ex}）")
        sys.exit(1)
