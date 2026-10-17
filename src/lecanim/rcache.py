"""書き出しの差分実行：シーンごとに「何から出来た動画か」の指紋を残し，変わっていないシーンは書き出さない.

指紋の材料（どれが変わっても作り直す）：
  * シーンのクラスのソース／ファイルの共通部分（クラス以外の部分）
  * そのシーンの台本を読み上げ用に変換した文（読みの辞書の変更も反映される）
  * 話者・話速・フォント・テーマ・品質・音声の有無
  * lecanim 本体のうち描画・音声に関わるソース（cli・qa・yomi・data は除く）
`lecanim render --force` で無視できる．保存先は <プロジェクト>/.lecanim/render_cache.json.
"""

from __future__ import annotations

import ast
import hashlib
import json
from functools import lru_cache
from pathlib import Path

_FRAMEWORK_SKIP = {"cli.py", "qa.py", "yomi.py", "rcache.py", "__init__.py"}


@lru_cache(maxsize=1)
def framework_hash() -> str:
    h = hashlib.sha1()
    base = Path(__file__).parent
    for p in sorted(base.rglob("*.py")):
        if p.name in _FRAMEWORK_SKIP or "__pycache__" in p.parts:
            continue
        h.update(p.relative_to(base).as_posix().encode())
        h.update(p.read_bytes())
    return h.hexdigest()[:16]


def _split_source(f: Path, scenes: list[str]) -> tuple[str, dict[str, str]]:
    """ファイル → (シーンのクラス以外の部分, {シーン名: クラスのソース})."""
    src = f.read_text()
    tree = ast.parse(src)
    pre, cls = [], {}
    for node in tree.body:
        seg = ast.get_source_segment(src, node) or ""
        if isinstance(node, ast.ClassDef) and node.name in scenes:
            cls[node.name] = seg
        else:
            pre.append(seg)
    return "\n".join(pre), cls


def scene_key(r: Path, f: Path, scene: str, q: str, voice: bool) -> str:
    from . import voice as v
    from .config import load
    from .narration import SCRIPTS
    from .yomi import _import_domains
    _import_domains()
    cfg = load(r)
    scenes = [scene]
    try:
        from .cli import scenes_of
        scenes = scenes_of(f)
    except Exception:                                        # noqa: BLE001
        pass
    pre, cls = _split_source(f, scenes)
    spoken = [[k, v.yomi(t)] for k, t in SCRIPTS.get(scene, [])]
    material = {"pre": pre, "cls": cls.get(scene, ""), "spoken": spoken, "q": q, "voice": voice,
                "speaker": cfg["voice"]["speaker"], "speed": cfg["voice"]["speed"],
                "font": cfg["style"].get("jp_font", ""), "theme": cfg["style"].get("theme", ""),
                "render": {k: cfg["render"].get(k) for k in ("encoder", "vfr_still")},
                "framework": framework_hash()}
    return hashlib.sha1(json.dumps(material, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:20]


def _file(r: Path) -> Path:
    return r / ".lecanim" / "render_cache.json"


def _load(r: Path) -> dict:
    p = _file(r)
    return json.loads(p.read_text()) if p.exists() else {}


def _out(r: Path, f: Path, scene: str, q: str) -> Path:
    from .cli import QDIR
    return r / "media" / "videos" / f.stem / QDIR[q] / f"{scene}.mp4"


def fresh(r: Path, f: Path, scene: str, q: str, voice: bool) -> bool:
    """この品質の動画があり，指紋が前回の書き出しと同じなら True."""
    if not _out(r, f, scene, q).exists():
        return False
    return _load(r).get(f"{f.stem}:{scene}:{q}:{int(voice)}") == scene_key(r, f, scene, q, voice)


def mark(r: Path, f: Path, scene: str, q: str, voice: bool) -> None:
    c = _load(r)
    c[f"{f.stem}:{scene}:{q}:{int(voice)}"] = scene_key(r, f, scene, q, voice)
    p = _file(r)
    p.parent.mkdir(exist_ok=True)
    p.write_text(json.dumps(c, ensure_ascii=False, indent=1))
