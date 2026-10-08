"""プロジェクト設定 (lecanim.toml) の読み込み.

プロジェクトのルートは, カレントディレクトリから上へ lecanim.toml を探して決める.
見つからなければカレントディレクトリをルートとし, 既定値を使う.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

DEFAULTS = {
    "project": {"course": "", "series": "", "lectures": {}},
    "voice": {"speaker": 8, "speed": 1.1, "url": "http://127.0.0.1:50021"},
    # min_free_gb: 空きメモリがこれ未満なら次のシーンを起動しない
    # mem_per_job_gb: 1080p のシーン1本が最終的に使うメモリの見込み．並列数 ≦ 空きメモリ ÷ これ
    # encoder: "auto"（macOS は VideoToolbox，NVIDIA GPU があれば NVENC）/ "x264-fast" / "x264"（manim 既定）
    # vfr_still: 静止区間（wait）を2フレーム＋時刻の飛びでエンコード（同じフレームを毎フレーム変換・圧縮しない）
    "render": {"jobs": 3, "min_free_gb": 2.0, "mem_per_job_gb": 4.0, "encoder": "auto", "vfr_still": True},
    # 日本語フォント．空なら macOS は Hiragino Sans，それ以外は Noto Sans CJK JP．
    # ローカルとリモートで同じ見た目にしたいときは両方にあるフォント（Noto Sans CJK JP）を指定する
    # theme: "classic"（丸い色付きチップ）/ "sharp"（無彩色＋4色・角を立てた見出し）
    "style": {"jp_font": "", "theme": "classic"},
    # リモートレンダリング（lecanim render --remote）
    "remote": {"host": "", "root": "~/lecanim-remote", "jobs": 8},
    "youtube": {"footer": ""},
}


def find_root(start: Path | None = None) -> Path:
    p = (start or Path.cwd()).resolve()
    for d in [p, *p.parents]:
        if (d / "lecanim.toml").exists():
            return d
    return p


def _merge(a: dict, b: dict) -> dict:
    out = dict(a)
    for k, v in b.items():
        out[k] = _merge(a[k], v) if isinstance(v, dict) and isinstance(a.get(k), dict) else v
    return out


def load(root: Path | None = None) -> dict:
    root = root or find_root()
    f = root / "lecanim.toml"
    data = tomllib.loads(f.read_text()) if f.exists() else {}
    return _merge(DEFAULTS, data)


ROOT = find_root(Path(os.environ["LECANIM_ROOT"]) if os.environ.get("LECANIM_ROOT") else None)
CFG = load(ROOT)
