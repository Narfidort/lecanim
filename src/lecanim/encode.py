"""動画エンコーダーの差し替え（GPU / ハードウェアエンコード）.

manim は部分動画（play ごとの mp4）のエンコーダーを libx264（CPU，preset medium）に決め打ちしている．
1080p60 ではエンコードがレンダリング時間の約3割を占めるので，ハードウェアエンコーダーに差し替える．

lecanim.toml の [render] encoder:
  "auto"（既定）  libx264 veryfast
                  （実測：nk RTX 5060 Ti・ナレーション付き 1080p60 の約4分のシーンで，manim 既定 204 秒，NVENC 124 秒，
                   x264 veryfast＋静止区間 VFR 50 秒，NVENC＋VFR 69 秒．図形アニメはフレームが単純で x264 が軽く，
                   NVENC は play ごとにセッションを開くコストが大きい．さらに run_time の短い play が続くシーンで
                   segfault することがあるので，NVENC は明示指定のときだけ使う）
  "videotoolbox" / "nvenc" / "x264-fast" / "x264"（manim 既定のまま）
環境変数 LECANIM_ENCODER で上書きできる．
"""

from __future__ import annotations

import os

import av

from .config import CFG

# 1080p60 の図形アニメーション向けの設定（画質は crf 23 相当を目安に）．"videotoolbox" は明示指定のときだけ使う
PROFILES = {
    "videotoolbox": ("h264_videotoolbox", {"b": "12M", "maxrate": "20M", "allow_sw": "1"}),
    "nvenc": ("h264_nvenc", {"preset": "p4", "tune": "hq", "rc": "vbr", "cq": "23", "b": "0"}),
    "x264-fast": ("libx264", {"crf": "23", "preset": "veryfast"}),
}

_chosen: tuple[str, dict] | None = None


def _works(codec: str, options: dict) -> bool:
    """実際に1フレームエンコードできるか（ライブラリはあっても GPU が使えない環境があるため）."""
    import io

    import numpy as np
    try:
        buf = io.BytesIO()
        c = av.open(buf, mode="w", format="mp4")
        s = c.add_stream(codec, rate=60, options=dict(options))
        s.width, s.height, s.pix_fmt = 256, 144, "yuv420p"
        f = av.VideoFrame.from_ndarray(np.zeros((144, 256, 3), dtype=np.uint8), format="rgb24")
        for p in s.encode(f):
            c.mux(p)
        for p in s.encode():
            c.mux(p)
        c.close()
        return True
    except Exception:
        return False


def choose() -> tuple[str, dict] | None:
    """使うエンコーダー (codec, options)．None なら manim の既定（libx264 medium）."""
    global _chosen
    if _chosen is not None:
        return _chosen or None
    want = os.environ.get("LECANIM_ENCODER") or CFG["render"].get("encoder", "auto")
    cands = []
    if want == "auto":
        cands.append("x264-fast")
    elif want != "x264":
        cands.append(want)
    for name in cands:
        codec, opts = PROFILES[name]
        if codec in av.codecs_available and _works(codec, opts):
            _chosen = (codec, opts)
            return _chosen
    _chosen = ()  # type: ignore[assignment]
    return None


class _ContainerProxy:
    """av の出力コンテナの代理．libx264 の add_stream だけを選んだエンコーダーに差し替える."""

    def __init__(self, c):
        self._c = c

    def add_stream(self, codec_name=None, rate=None, options=None, **kw):
        if codec_name == "libx264":
            ch = choose()
            if ch:
                codec_name, options = ch[0], dict(ch[1])
            if vfr_enabled():
                # 静止区間の時刻の飛びを MP4 の長さに反映させるため B フレームを使わない（dts = pts にする）
                options = {**(options or {}), "bf": "0"}
        return self._c.add_stream(codec_name, rate=rate, options=options, **kw)

    def __getattr__(self, name):
        return getattr(self._c, name)

    def __enter__(self):
        self._c.__enter__()
        return self

    def __exit__(self, *a):
        return self._c.__exit__(*a)


class _AvProxy:
    def __getattr__(self, name):
        return getattr(av, name)

    @staticmethod
    def open(*a, **k):
        c = av.open(*a, **k)
        mode = k.get("mode", a[1] if len(a) > 1 else "r")
        return _ContainerProxy(c) if mode == "w" else c


def _encode_and_write_frame_vfr(self, frame, num_frames: int) -> None:
    """静止区間を「2フレーム＋時刻の飛び」でエンコードする（可変フレームレート）.

    manim は wait() の間，同じフレームを 60fps なら1秒あたり60回変換・エンコードしている．
    ナレーション付きの動画は大半が静止区間なので，最初と最後の2回だけエンコードし，
    間は時刻（pts）を飛ばして表示し続けさせる．見た目と長さは同じ．
    """
    from fractions import Fraction

    tb = self.stream.codec_context.time_base or Fraction(1, 60)
    n0 = getattr(self, "_lc_pts", 0)
    marks = [n0] if num_frames == 1 else [n0, n0 + num_frames - 1]
    for pts in marks:
        av_frame = av.VideoFrame.from_ndarray(frame, format="rgba")
        av_frame.pts = pts
        av_frame.time_base = tb
        for packet in self.stream.encode(av_frame):
            self.container.mux(packet)
    self._lc_pts = n0 + num_frames


def vfr_enabled() -> bool:
    return os.environ.get("LECANIM_VFR", str(CFG["render"].get("vfr_still", True))).lower() not in ("0", "false")


def install() -> None:
    """manim の部分動画エンコードを差し替える.
    * 静止区間の可変フレームレート化（[render] vfr_still = true，既定）
    * エンコーダーの差し替え（[render] encoder，"x264" なら manim 既定のまま）"""
    from manim.scene import scene_file_writer
    vfr = vfr_enabled()
    if vfr and hasattr(scene_file_writer, "_PartialMovieEncodeJob"):
        scene_file_writer._PartialMovieEncodeJob._encode_and_write_frame = _encode_and_write_frame_vfr
    if not vfr and os.environ.get("LECANIM_ENCODER", CFG["render"].get("encoder", "auto")) == "x264":
        return
    if not isinstance(scene_file_writer.av, _AvProxy):
        scene_file_writer.av = _AvProxy()
