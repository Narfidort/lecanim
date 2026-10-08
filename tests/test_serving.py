import pytest

from lecanim.domains.serving import SLO, Breakdown, Deployment, Measurement, Sweep, Worker


def test_pack_4p2d():
    dep = Deployment.pack([("P", 2, 2)] * 4 + [("D", 4, 4)] * 2)
    assert dep.ok and dep.label == "4P2D"
    assert dep.gpus_of("P") == 8 and dep.gpus_of("D") == 8 and not dep.free()
    assert {g[0] for g in dep.worker("D0").gpus} == {1}     # Decode はノードをまたがない
    assert [w.name for w in dep.workers] == ["P0", "P1", "P2", "P3", "D0", "D1"]


def test_pack_6p1d_uses_all():
    dep = Deployment.pack([("P", 2, 1)] * 6 + [("D", 4, 4)])
    assert dep.label == "6P1D" and not dep.free()
    assert {g[0] for g in dep.worker("D0").gpus} == {1}


def test_pack_tp8_spans_or_fits_node():
    dep = Deployment.pack([("P", 4, 4)] * 2 + [("D", 8, 8)])
    assert dep.ok and {g[0] for g in dep.worker("D0").gpus} == {1}
    big = Deployment.pack([("A", 16, 16)])
    assert big.ok and len(big.worker("A0").gpus) == 16


def test_check_detects_errors():
    w1 = Worker("P0", "P", ((0, 0), (0, 1)), tp=2, ep=2)
    w2 = Worker("D0", "D", ((0, 1), (0, 2), (0, 3)), tp=4, ep=3)
    errs = Deployment([w1, w2]).check()
    assert any("重複" in e for e in errs)
    assert any("TP4 だが" in e for e in errs)
    assert any("割り切らない" in e for e in errs)


def test_pack_overflow():
    with pytest.raises(AssertionError):
        Deployment.pack([("D", 4, 4)] * 5)


def test_sweep_best_and_first_fail():
    # pastrun008（3P1D・Decode TP4）の C 掃引：C32 だけ合格
    s = Sweep("3P1D", [Measurement(32, 1536.96, 1.00, 18.84), Measurement(48, 2000.52, 0.1094, 20.67),
                       Measurement(64, 2415.72, 0.05, 21.91)])
    assert s.best().c == 32 and s.first_fail().c == 48
    assert SLO().good(2999, 19.9) and not SLO().good(500, 20.1)


def test_breakdown():
    bd = Breakdown([("GEMM2", 9.4), ("Finalize", 3.9), ("AllReduce", 10.4)])
    assert abs(bd.total - 23.7) < 1e-9
    assert abs(bd.share("AllReduce") - 10.4 / 23.7) < 1e-9
    fused = bd.replace(Finalize=0)
    assert fused.names() == ["GEMM2", "AllReduce"]
