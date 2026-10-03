"""VOICEVOX によるナレーション合成.

* エンジン: Docker の voicevox/voicevox_engine (`lecanim voice up` で起動, 既定 http://127.0.0.1:50021)
* POST /audio_query → POST /synthesis の2段階で WAV を作り, ~/.cache/lecanim/voice/<hash>.wav にキャッシュ
  (全プロジェクト共通. キーは 読み上げ文・話者・話速).
* 読み上げ文中の $...$ (TeX) は yomi() で読みに変換してから合成する.
* 読みの辞書 = 汎用の BASE_WORDS + プロジェクトの yomi.toml の words (先に適用).
* 設定: lecanim.toml の [voice] (speaker, speed, url). 環境変数で上書き可:
    VOICE=0  無音（高速プレビュー） / VOICEVOX_URL / VOICE_SPEAKER / VOICE_SPEED
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.parse
import urllib.request
import wave
from pathlib import Path

import tomllib

from .config import CFG, ROOT

URL = os.environ.get("VOICEVOX_URL", CFG["voice"]["url"])
SPEAKER = int(os.environ.get("VOICE_SPEAKER", CFG["voice"]["speaker"]))
SPEED = float(os.environ.get("VOICE_SPEED", CFG["voice"]["speed"]))
ENABLED = os.environ.get("VOICE", "1") != "0"
CACHE = Path(os.environ.get("LECANIM_CACHE", Path.home() / ".cache" / "lecanim")) / "voice"

_SPEAKER_NAMES = {2: "四国めたん", 3: "ずんだもん", 8: "春日部つむぎ", 13: "青山龍星", 14: "冥鳴ひまり",
                  16: "九州そら", 11: "玄野武宏"}


def credit() -> str:
    return f"VOICEVOX:{_SPEAKER_NAMES.get(SPEAKER, '（話者）')}"


# ---------------------------------------------------------------- 読み (TeX → 日本語)
_LETTER = {
    "a": "エー", "b": "ビー", "c": "シー", "d": "ディー", "e": "イー", "f": "エフ", "g": "ジー", "h": "エイチ",
    "i": "アイ", "j": "ジェー", "k": "ケー", "l": "エル", "m": "エム", "n": "エヌ", "o": "オー", "p": "ピー",
    "q": "キュー", "r": "アール", "s": "エス", "t": "ティー", "u": "ユー", "v": "ブイ", "w": "ダブリュー",
    "x": "エックス", "y": "ワイ", "z": "ゼット",
}
_CMD = {
    r"\sigma": "シグマ", r"\delta": "デルタ", r"\Delta": "デルタ", r"\varphi": "ファイ", r"\phi": "ファイ",
    r"\pi": "パイ", r"\lambda": "ラムダ", r"\alpha": "アルファ", r"\beta": "ベータ",
    r"\ge": "、以上、", r"\geq": "、以上、", r"\le": "、以下、", r"\leq": "、以下、", r"\neq": "ノットイコール",
    r"\times": "かける", r"\cdot": "かける", r"\to": "から", r"\Rightarrow": "、ならば、",
    r"\Leftrightarrow": "、同値、", r"\Longleftrightarrow": "、同値、", r"\iff": "、同値、", r"\in": "の元",
    r"\notin": "に含まれない",
    r"\min": "ミニマム", r"\max": "マックス", r"\sum": "シグマ", r"\equiv": "合同", r"\pmod": "モッド",
    r"\cup": "和集合", r"\cap": "共通部分", r"\emptyset": "空集合", r"\infty": "無限大",
    r"\lceil": "", r"\rceil": "", r"\lfloor": "", r"\rfloor": "", r"\left": "", r"\right": "",
    r"\{": "", r"\}": "", r"\,": "", r"\ ": "", r"\quad": "、", r"\mathbb": "", r"\text": "",
    r"\tfrac": "", r"\frac": "", r"\binom": "コンビネーション",
}
_NUM_JA = {"0": "ゼロ", "1": "いち", "2": "に", "3": "さん", "4": "よん", "5": "ご", "6": "ろく", "7": "なな",
           "8": "はち", "9": "きゅう"}


def _tex_to_yomi(tex: str) -> str:
    s = tex
    # 分数 \frac{a}{b} → b ぶんの a
    s = re.sub(r"\\t?frac\{([^{}]*)\}\{([^{}]*)\}", lambda m: f"{m.group(2)}ぶんの{m.group(1)}", s)
    s = re.sub(r"\\binom\{([^{}]*)\}\{([^{}]*)\}", lambda m: f"コンビネーション{m.group(1)}{m.group(2)}", s)
    s = re.sub(r"\\text\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"\\mathbb\{(\w)\}", r"\1", s)
    s = s.replace("^-", "マイナス").replace("^+", "プラス").replace("^{-}", "マイナス").replace("^{+}", "プラス")
    s = re.sub(r"\^\{?2\}?", "の2乗", s)
    s = s.replace(r"\sigma_2", "シグマツー")
    s = re.sub(r"_\{([^{}]*)\}", lambda m: "".join(_NUM_JA.get(c, c) for c in m.group(1)), s)
    s = re.sub(r"_(\w)", lambda m: _NUM_JA.get(m.group(1), m.group(1)), s)
    for k in sorted(_CMD, key=len, reverse=True):
        s = s.replace(k, _CMD[k])
    s = re.sub(r"\\[a-zA-Z]+", " ", s)
    rep = {"+": "プラス", "-": "マイナス", "=": "イコール", ">": "、大なり、", "<": "、小なり、", "(": "", ")": "",
           "{": "", "}": "", "|": "", ",": "、", ":": "", "'": "プライム", "^": ""}
    out = []
    for ch in s:
        if ch in rep:
            out.append(rep[ch])
        elif ch.isascii() and ch.isalpha():
            out.append(_LETTER.get(ch.lower(), ch))
        else:
            out.append(ch)
    s = "".join(out)
    s = re.sub(r"\s+", "", s)            # 空白は「間」になるので詰める
    s = re.sub(r"、+", "、", s).strip("、")
    return s


# 汎用の読み (VOICEVOX が誤読しやすいもの). 分野固有の語はプロジェクトの yomi.toml に書く.
BASE_WORDS = [("括弧", "かっこ"), ("弧", "こ"), ("黄色", "きいろ"),
              ("最小値", "サイショウチ"), ("最大値", "サイダイチ"), ("絶対値", "ゼッタイチ"), ("値", "あたい"),
              ("左辺", "さへん"), ("右辺", "うへん"), ("両辺", "りょうへん"), ("辺", "へん"),
              ("鳩の巣", "はとのす"), ("頂点", "ちょうてん")]
# transcripts のカナにこれが現れたら誤読の疑い (lecanim check)
BASE_SUSPECT = ["アタリ", "バトノ", "オオショク", "ノ/ネ", "カツ'コ"]


def _project_yomi() -> dict:
    f = ROOT / "yomi.toml"
    return tomllib.loads(f.read_text()) if f.exists() else {}


_PY = _project_yomi()
_DOMAIN_WORDS: list[tuple[str, str]] = []
SUSPECT = list(_PY.get("suspect", [])) + BASE_SUSPECT


def register_words(words, suspect=()) -> None:
    """分野モジュールが自分の読み辞書を登録する（プロジェクトの yomi.toml より後，汎用辞書より先に適用）."""
    for w in words:
        if tuple(w) not in _DOMAIN_WORDS:
            _DOMAIN_WORDS.append(tuple(w))
    for p in suspect:
        if p not in SUSPECT:
            SUSPECT.append(p)


def words() -> list[tuple[str, str]]:
    """適用順の読み辞書: プロジェクト → 分野 → 汎用. 長い語を先に置換したいので, 同じ層の中では長い順."""
    proj = [tuple(w) for w in _PY.get("words", [])]
    dom = sorted(_DOMAIN_WORDS, key=lambda w: -len(w[0]))
    base = sorted(BASE_WORDS, key=lambda w: -len(w[0]))
    return proj + dom + base

_PLAIN = [("→", "、"), ("⇒", "ならば"), ("⇔", "同値"), ("／", "、"), ("…", "、"), ("□", ""), ("✓", ""),
          ("✗", ""), ("──", "、"), ("—", "、"), ("「", ""), ("」", ""), ("≥", "以上"), ("≤", "以下"),
          ("①", "ステップ1、"), ("②", "ステップ2、"), ("③", "ステップ3、"), ("④", "ステップ4、"),
          ("⑤", "ステップ5、"), ("▼", "下向きの印"), ("▲", "上向きの印"), ("×", "かける"), ("＝", "は"),
          ("＋", "プラス"), ("π", "パイ")]


def yomi(text: str) -> str:
    """字幕テキスト ($...$ を含む) → 読み上げ用テキスト."""
    segs = text.split("$")
    out = []
    for i, seg in enumerate(segs):
        out.append(_tex_to_yomi(seg) if i % 2 == 1 else seg)
    s = "".join(out)
    s = re.sub(r"(定理|補題|課題|提出課題|発展課題)(\d+)-(\d+)", r"\1\2の\3", s)
    for a, b in words():
        s = s.replace(a, b)
    for a, b in _PLAIN:
        s = s.replace(a, b)
    s = re.sub(r"[ 　]+", "", s)          # 空白は「間」になるので除く
    s = re.sub(r"、+", "、", s)
    return s.strip()


# ---------------------------------------------------------------- 合成
class VoiceUnavailable(RuntimeError):
    pass


def _post(path: str, params: dict, body: bytes | None = None, timeout=60, tries: int = 5) -> bytes:
    """VOICEVOX への POST. 混雑・トンネル越しの一時的な失敗に備えて再試行する."""
    import time
    q = urllib.parse.urlencode(params)
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(f"{URL}{path}?{q}", data=body if body is not None else b"", method="POST",
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                if r.status != 200:
                    raise RuntimeError(f"HTTP {r.status}")
                return r.read()
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 * (i + 1))
    raise VoiceUnavailable(f"VOICEVOX（{URL}{path}）に接続できません: {last}．"
                           "`lecanim voice up` で起動するか，無音でよければ --no-voice（VOICE=0）")


def available(timeout: float = 5) -> bool:
    try:
        with urllib.request.urlopen(f"{URL}/version", timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def cache_path(spoken: str, speaker: int = SPEAKER, speed: float = SPEED) -> Path:
    key = hashlib.sha1(json.dumps([spoken, speaker, speed]).encode()).hexdigest()[:16]
    return CACHE / f"{key}.wav"


def synth(spoken: str, speaker: int = SPEAKER, speed: float = SPEED) -> Path:
    """読み上げテキスト → WAV. 合成済みならエンジンに触れずキャッシュを返す. spoken は yomi() 済みのもの.
    未合成でエンジンに届かなければ VoiceUnavailable（黙って無音にはしない）."""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = cache_path(spoken, speaker, speed)
    if path.exists():
        return path
    q = json.loads(_post("/audio_query", {"text": spoken, "speaker": speaker}, timeout=20))
    q["speedScale"] = speed
    q["prePhonemeLength"] = 0.05
    q["postPhonemeLength"] = 0.15
    wav = _post("/synthesis", {"speaker": speaker}, json.dumps(q).encode(), timeout=90)
    path.write_bytes(wav)
    return path


_ENGINE_OK: bool | None = None


def kana(spoken: str, speaker: int = SPEAKER) -> str:
    """エンジンが解釈した読み (AquesTalk 風記法). 誤読チェック用. 1文1ファイルでキャッシュ (並列実行で安全)."""
    d = CACHE / "kana"
    d.mkdir(parents=True, exist_ok=True)
    f = d / (hashlib.sha1(json.dumps([spoken, speaker]).encode()).hexdigest()[:16] + ".txt")
    if not f.exists():
        global _ENGINE_OK
        if _ENGINE_OK is None:
            _ENGINE_OK = available(timeout=2)
        if not _ENGINE_OK:
            return ""          # 読みの確認用なので, エンジンがなければ空（動画には影響しない）
        try:
            q = json.loads(_post("/audio_query", {"text": spoken, "speaker": speaker}, timeout=20, tries=2))
        except VoiceUnavailable:
            _ENGINE_OK = False
            return ""
        f.write_text(q.get("kana", ""))
    return f.read_text()


def duration(path: Path) -> float:
    with wave.open(str(path)) as w:
        return w.getnframes() / w.getframerate()
