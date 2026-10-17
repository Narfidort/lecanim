"""narfi：スコープ・依存関係・goal の形の検査."""

from lecanim.domains.narfi import (Atom, Chain, Choose, Exists, Fix, Forall, Imp, Assume, Just, Let, Obtain, Thm,
                                   check, mentions, subst)

E = r"\varepsilon"


def conv(a, al):
    return Forall(E, Exists("N", Forall("n", Atom(rf"|{a}-{al}|<{E}"), bound=r"\ge N"), bound=r"\in\mathbb{N}"),
                  bound=">0")


def test_mentions_and_subst():
    assert mentions(r"|f_n(z)-f(z)|<\varepsilon") >= {"f_n", "n", "z", r"\varepsilon"}
    assert "N" not in mentions(r"\exists M\in\mathbb{N}")         # \mathbb{N} は名前ではない
    assert "n" not in mentions("n_0")                               # n_0 は n とは別の名前
    assert subst(r"|a_n-\alpha|", "n", "m") == r"|a_{m}-\alpha|"
    assert subst(r"N_1+N", "N", "M") == "N_1+M"


def test_sum_of_limits_ok_and_dependency():
    thm = Thm("和", goal=conv("(a_n+b_n)", r"(\alpha+\beta)"),
              hyps=[("h_a", conv("a_n", r"\alpha")), ("h_b", conv("b_n", r"\beta"))],
              body=[Fix(E, "h", body=[
                  Obtain("N_1", "h_1", "h_a", args=[r"\tfrac{\varepsilon}{2}"]),
                  Obtain("N_2", "h_2", "h_b", args=[r"\tfrac{\varepsilon}{2}"]),
                  Let("N", r"\max(N_1,N_2)"), Choose("N"),
                  Fix("n", "h_n", body=[Chain("x", [(r"\le", "y", ""), ("<", E, "")])])])])
    tr = check(thm)
    assert tr.ok, tr.errors
    assert tr.deps("N_1") == (E,) and tr.deps("N") == (E,)
    exits = [ln for ln in tr.lines if ln.step.kind == "exit"]
    assert [ln.depth for ln in exits] == [1, 0]          # 内側の n の枠 → 外側の ε の枠の順に出る（字下げが戻る）
    assert exits[-1].step.concl.startswith(r"\forall \varepsilon")
    fix_n = next(ln for ln in tr.lines if ln.text[:2] == ["Fix", "$n$"])
    assert fix_n.head[0].startswith(r"\forall n") and fix_n.intro == ["n", "h_n"]
    obt = next(ln for ln in tr.lines if ln.text[0] == "Obtain")
    assert obt.uses == ["h_a", r"\varepsilon"]


def test_uniform_from_pointwise_fails_by_scope():
    pt = Forall("x", Forall(E, Exists("N", Atom("P(N,x)")), bound=">0"), bound=r"\in I")
    uni = Forall(E, Exists("N", Forall("x", Atom("P(N,x)"), bound=r"\in I")), bound=">0")
    bad = Thm("?", goal=uni, hyps=[("h", pt)],
              body=[Fix(E, body=[Obtain("N", "h_N", "h", args=["x", E]), Choose("N"),
                                 Fix("x", body=[Just("h_N")])])])
    assert [m for _, m in check(bad).errors] == ["スコープ外の名前 x"]
    good = Thm("ok", goal=pt, hyps=[("h", uni)],
               body=[Fix("x", body=[Fix(E, body=[Obtain("N", "h_N", "h", args=[E]), Choose("N"), Just("h_N")])])])
    tr = check(good)
    assert tr.ok, tr.errors
    assert tr.deps("N") == (E,)            # 一様収束から取り出した N は x に依存しない


def test_goal_shape_errors():
    t = Thm("t", goal=Imp("A", "B"), body=[Fix("x", body=[Just("h")])])
    assert any("∀ の形ではない" in m for _, m in check(t).errors)
    t = Thm("t", goal=Imp("A", "B"), body=[Assume("h", body=[Just("h")]), Just("extra")])
    assert any("余分" in m for _, m in check(t).errors)
    t = Thm("t", goal=Forall("x", "P(x)"), body=[Fix("x", body=[Let("y", "x")])])
    assert any("閉じていない" in m for _, m in check(t).errors)
