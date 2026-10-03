"""グラフ分野: データ構造の判定関数（お手本の assert が頼る部分）."""

from lecanim.domains.graph import EdgeColoring, Graph, crossings, near_misses
from lecanim.layout import Box, fit, layout_circle


def test_complete_and_degrees():
    k5 = Graph.complete(5)
    assert len(k5.edges) == 10 and k5.min_degree() == 4 and k5.sigma2() is None


def test_hamiltonian():
    bowtie = Graph(range(5), [(0, 1), (1, 2), (0, 2), (2, 3), (3, 4), (2, 4)])
    assert bowtie.hamiltonian_cycle() is None and bowtie.sigma2() == 4
    assert Graph.cycle(6).is_hamiltonian_cycle(Graph.cycle(6).hamiltonian_cycle())


def test_r33_pentagon_coloring_has_no_mono_triangle():
    k5 = Graph.complete(5)
    col = EdgeColoring(k5, {e: ("r" if (e[1] - e[0]) % 5 in (1, 4) else "b") for e in k5.edges})
    assert col.mono_cliques(3) == []
    k6 = Graph.complete(6)
    for seed in range(20):   # K6 はどう塗っても単色三角形がある
        assert EdgeColoring.random(k6, seed=seed).mono_cliques(3)


def test_directed_degrees():
    d = Graph(range(3), [(0, 1), (1, 2), (2, 0)], directed=True)
    assert d.out_degree(0) == 1 and d.in_degree(0) == 1 and d.is_cycle([0, 1, 2])


def test_component_and_coloring():
    g = Graph.path(4)
    assert g.component(0, allowed=[0, 1, 3]) == [0, 1]
    assert g.is_proper_coloring(g.greedy_coloring())


def test_crossings_and_fit():
    k4 = Graph.complete(4)
    pos = layout_circle(range(4))
    assert len(crossings(k4, pos)) == 1                         # 対角線どうし
    cube_like = Graph.cycle(4)
    assert crossings(cube_like, pos) == [] and near_misses(cube_like, pos) == []
    box = Box.from_lrbt(-1, 1, -1, 1)
    p = fit(pos, box, margin=0.1)
    assert all(-1 <= v[0] <= 1 and -1 <= v[1] <= 1 for v in p.values())
