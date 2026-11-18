"""lecanim.plot.AxesMob（座標軸の共通土台）の最低限の確認."""

import shutil

import numpy as np
import pytest

from lecanim.plot import fmt_num


def test_fmt_num_integers_and_decimals():
    assert fmt_num(2.0) == "2"
    assert fmt_num(-3.0) == "-3"
    assert fmt_num(0.5) == "0.5"
    assert fmt_num(1.0000000001) == "1"  # 浮動小数の誤差は丸めて整数に落ちる


@pytest.mark.skipif(shutil.which("latex") is None, reason="LaTeX が必要（examples ジョブで確認）")
def test_axes_mob_p_matches_underlying_axes():
    from lecanim.plot import AxesMob

    ax = AxesMob(xr=(0, 4, 1), yr=(-1, 1, 0.5), x_label="x", y_label="y")
    assert np.allclose(ax.p(2, 0.5), ax.ax.c2p(2, 0.5))


@pytest.mark.skipif(shutil.which("latex") is None, reason="LaTeX が必要（examples ジョブで確認）")
def test_axes_mob_components_default_to_added_and_overlay_marked():
    from lecanim.plot import AxesMob

    ax = AxesMob(xr=(0, 4, 1), yr=(0, 4, 1))
    before = len(ax.submobjects)
    line = ax.hline(2, label="y=2")
    assert len(ax.submobjects) == before + 1          # add=True（既定）で軸に入る
    assert all(x._qa_overlay for x in line.get_family())  # 重なり検査の対象外


@pytest.mark.skipif(shutil.which("latex") is None, reason="LaTeX が必要（examples ジョブで確認）")
def test_axes_mob_add_false_does_not_attach():
    from lecanim.plot import AxesMob

    ax = AxesMob(xr=(0, 4, 1), yr=(0, 4, 1))
    before = len(ax.submobjects)
    ax.vline(2, add=False)
    assert len(ax.submobjects) == before
