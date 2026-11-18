"""lecanim.domains.stats の数値ヘルパー（具体例の assert 用）を確かめる."""

import math
import shutil

import numpy as np
import pytest

from lecanim.domains.stats import (annihilator_matrix, chi2_pdf, f_pdf, f_stat, gls, is_idempotent, is_symmetric,
                                   normal_pdf, ols, projection_matrix, t_pdf)


def _toy(n=30, k=2, seed=0):
    rng = np.random.default_rng(seed)
    X = np.column_stack([np.ones(n)] + [rng.normal(size=n) for _ in range(k)])
    beta = np.arange(1, k + 2, dtype=float)
    Y = X @ beta + rng.normal(scale=0.5, size=n)
    return X, Y, beta


def test_ols_and_projection_matrices():
    X, Y, _ = _toy()
    beta_hat, resid = ols(X, Y)
    P, M = projection_matrix(X), annihilator_matrix(X)
    assert is_idempotent(P) and is_idempotent(M)
    assert is_symmetric(P) and is_symmetric(M)
    assert np.allclose(P + M, np.eye(X.shape[0]), atol=1e-8)
    assert np.allclose(M @ X, 0, atol=1e-8)
    assert np.allclose(X.T @ resid, 0, atol=1e-6)                 # 残差二乗和最小化の一階条件
    assert abs(np.trace(M) - (X.shape[0] - X.shape[1])) < 1e-6    # trace[M] = N-(K+1)


def test_gls_reduces_to_ols_when_omega_is_identity():
    X, Y, _ = _toy()
    beta_ols, _ = ols(X, Y)
    beta_gls = gls(X, Y, np.eye(X.shape[0]))
    assert np.allclose(beta_ols, beta_gls, atol=1e-8)


def test_f_stat_is_positive_and_scales_with_restriction_violation():
    X, Y, _ = _toy()
    R, c = np.array([[0.0, 1.0, 0.0]]), np.array([0.0])
    F = f_stat(X, Y, R, c)
    assert F > 0
    far = f_stat(X, Y, R, np.array([100.0]))     # 制約を大きく外すほど F は大きくなる
    assert far > F


def test_pdfs_match_known_values_and_integrate_to_one():
    assert abs(normal_pdf(0.0) - 1 / math.sqrt(2 * math.pi)) < 1e-9
    assert abs(t_pdf(0.0, 500) - normal_pdf(0.0)) < 1e-3          # 自由度が大きい t は正規に近づく
    xs = np.linspace(1e-6, 60, 200_000)
    assert abs(np.trapezoid([chi2_pdf(x, 4) for x in xs], xs) - 1.0) < 1e-2
    assert abs(np.trapezoid([f_pdf(x, 3, 20) for x in xs], xs) - 1.0) < 1e-2
    xs_big = np.linspace(1e-6, 600, 200_000)      # 自由度300の χ² は平均300付近に質量がある
    assert abs(np.trapezoid([chi2_pdf(x, 300) for x in xs_big], xs_big) - 1.0) < 1e-2   # 大きい自由度でもオーバーフローしない


@pytest.mark.skipif(shutil.which("latex") is None, reason="LaTeX が必要（examples ジョブで確認）")
def test_block_matrix_mob_matches_conformable_dimensions():
    """X の列数と β の行数に同じ値を渡すと，矩形の幅・高さが一致する（行列の次元の整合性）."""
    from lecanim.domains.stats import BlockMatrixMob
    from lecanim.style import FG

    bm = BlockMatrixMob()
    Xb = bm.col_blocks([("X", 6, 4, FG)])
    bb = bm.col_blocks([(r"\beta", 4, 1, FG)])
    x_rect, b_rect = Xb[0][0], bb[0][0]
    assert math.isclose(x_rect.width, b_rect.height, rel_tol=1e-9)
    assert not math.isclose(x_rect.width, x_rect.height)  # N(6) と K+1(4) は違う値なので縦横比も変わる
