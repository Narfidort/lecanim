"""静止区間の可変フレームレート（vfr_still）で，動画の長さが変わらないこと."""

import shutil
import subprocess

import pytest


@pytest.mark.skipif(shutil.which("ffprobe") is None, reason="ffprobe が必要")
@pytest.mark.parametrize("quality,fps", [("low_quality", 15), ("high_quality", 60)])
def test_vfr_keeps_duration(tmp_path, monkeypatch, quality, fps):
    monkeypatch.setenv("LECANIM_VFR", "1")
    import lecanim  # noqa: F401  （エンコードの差し替えを入れる）
    from manim import FadeOut, Scene, Square, tempconfig

    class W(Scene):
        def construct(self):
            sq = Square()
            self.add(sq)
            self.wait(3)
            self.play(FadeOut(sq), run_time=0.5)
            self.wait(2)

    with tempconfig({"quality": quality, "disable_caching": True, "media_dir": str(tmp_path),
                     "verbosity": "ERROR", "progress_bar": "none"}):
        W().render()
    out = next(tmp_path.rglob("W.mp4"))
    d = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                              str(out)], capture_output=True, text=True).stdout)
    assert abs(d - 5.5) <= 1.5 / fps
