"""ナレーション台本の読み込み.

プロジェクトの narration/ 以下の *.py (各ファイルに SCRIPTS = {シーン名: [(キー, 読み上げ文), ...]})
と, 互換のため narration.py をまとめて読み込む.
"""

from __future__ import annotations

import importlib.util

from .config import ROOT


def _load(path):
    spec = importlib.util.spec_from_file_location(f"_narr_{path.stem}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, "SCRIPTS", {})


def load_scripts() -> dict:
    out: dict = {}
    files = sorted((ROOT / "narration").glob("*.py")) if (ROOT / "narration").is_dir() else []
    if (ROOT / "narration.py").exists():
        files.append(ROOT / "narration.py")
    for f in files:
        if f.name.startswith("_"):
            continue
        for k, v in _load(f).items():
            if k in out:
                raise ValueError(f"台本のシーン名が重複: {k} ({f})")
            out[k] = v
    return out


SCRIPTS = load_scripts()
