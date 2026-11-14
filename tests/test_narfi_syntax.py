"""Narfi 表示（現行の書き方）・帰納法・カメラ方式のテスト."""

from lecanim.domains.narfi import (Atom, Case, Cases, Fix, Forall, Have, Imp, Induction, Just, Obtain, Exists,
                                   Thm, check)
from lecanim.domains.narfi_src import ascii2tex


def test_obtain_row_uses_current_syntax():
    E = r"\varepsilon"
    arch = Forall(E, Exists("N", Atom(rf"\tfrac1N<{E}"), bound=r"\in\mathbb{N}"), bound=">0")
    thm = Thm("t", goal=Forall(E, Exists("N", Atom(rf"\tfrac1N<{E}"), bound=r"\in\mathbb{N}"), bound=">0"),
              lemmas={"arch": arch},
              body=[Fix(E, "h", body=[Obtain("N", "hN", "arch", args=[E]),
                                      __import__("lecanim.domains.narfi", fromlist=["Choose"]).Choose("N"),
                                      Just("hN")])])
    tr = check(thm)
    ob = next(ln for ln in tr.lines if ln.step.kind == "obtain")
    assert ob.text[0] == "Obtain" and "|" in ob.text and "by" in ob.text       # Obtain x | h by src
    assert not any(isinstance(p, str) and p == "have" for ln in tr.lines for p in ln.text)


def test_have_row_is_fact_by_justification():
    thm = Thm("t", goal=Atom("P"), hyps=[("h", Atom("P"), "")],
              body=[Have("k", Atom("P"), by="h"), Just("k")])
    tr = check(thm)
    assert tr.ok, tr.errors
    assert "by" in tr.lines[0].text and "have" not in tr.lines[0].text


def test_induction_checks_cases():
    thm = Thm("ind", goal=Forall("n", Atom("S(n)=T(n)"), bound=r"\in\mathbb{N}"), params=["S", "T"],
              hyps=[("hz", Atom("S(0)=T(0)"), ""), ("hs", Atom("hs"), "")],
              body=[Fix("n", body=[Induction("n", zero=[Just("hz")], k="k", ih="IH", succ=[Just("hs")])])])
    tr = check(thm)
    assert tr.ok, tr.errors
    kinds = [ln.step.kind for ln in tr.lines]
    assert kinds.count("case") == 2
    goals = [ln.goal for ln in tr.lines if ln.step.kind == "case"]
    assert goals == ["S(0)=T(0)", "S(k+1)=T(k+1)"]


def test_ascii2tex_common_forms():
    assert ascii2tex("h_{eps} : eps > 0") == r"h_{\varepsilon} : \varepsilon > 0"
    assert ascii2tex("abs(a(n)-alpha)") == r"\left|a(n)-\alpha\right|"
    assert r"\max\{N_1, N_2\}" in ascii2tex("N := max{N_1, N_2}")
    assert r"\mathrm{pos\_half}" in ascii2tex("pos_half(x)")
