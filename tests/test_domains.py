"""分野モジュールの約束（CONTRIBUTING.md）を機械的に確かめる."""

import importlib
import pkgutil
import shutil

import pytest

import lecanim
import lecanim.domains
from lecanim.units import LiveGroup


def _domains():
    for m in pkgutil.iter_modules(lecanim.domains.__path__):
        yield importlib.import_module(f"lecanim.domains.{m.name}")


def test_domains_declare_all_and_yomi():
    for mod in _domains():
        assert hasattr(mod, "__all__"), f"{mod.__name__}: __all__ を定義する"
        assert hasattr(mod, "YOMI"), f"{mod.__name__}: YOMI（空でもよい）を定義する"
        for name in mod.__all__:
            assert hasattr(mod, name), f"{mod.__name__}.__all__ に存在しない名前: {name}"


def test_drawing_classes_are_live_groups():
    for mod in _domains():
        for name in mod.__all__:
            obj = getattr(mod, name)
            if isinstance(obj, type) and name.endswith("Mob"):
                assert issubclass(obj, LiveGroup), f"{mod.__name__}.{name} は LiveGroup を継承する"


def test_core_does_not_export_manim_graph():
    ns = {}
    exec("from lecanim import *", ns)
    assert "Graph" not in ns and "LectureScene" in ns


@pytest.mark.skipif(shutil.which("latex") is None, reason="LaTeX が必要（examples ジョブで確認）")
def test_template_builds():
    from lecanim.domains._template import NumberLineMob
    nl = NumberLineMob(0, 5)
    assert len(nl.mark(2)) == 1 and nl.point(3)[0] == 3.0
