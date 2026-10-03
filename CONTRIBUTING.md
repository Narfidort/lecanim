# コントリビューションの手引き

lecanim は「コア」と「分野モジュール」に分かれている。新しい分野（線形代数・集合・確率・数論…）の部品は
`src/lecanim/domains/` にモジュールを追加する PR で受け付ける。

```
src/lecanim/
  style.py, layout.py, units.py, scene.py, voice.py, narration.py, cli.py   ← コア（分野によらない）
  domains/
    graph.py        グラフ理論（Graph, EdgeColoring, GraphMob, …）
    _template.py    新しい分野の雛形（数直線の最小例）
examples/<分野>/    お手本シーン＋台本
```

シーンでは `from lecanim import *` でコアを，`from lecanim.domains.<分野> import *` で分野の部品を読み込む。

## 分野モジュールの約束

`tests/test_domains.py` が一部を自動で確かめる。

1. **データと描画を分ける**：対象の構造（純粋な Python のクラス）と，それを描く描画クラス（`LiveGroup` を継承，名前は `…Mob`）。
   データ構造には，お手本の具体例を `assert` で検証できる判定関数を持たせる（例：`Graph.hamiltonian_cycle()`, `EdgeColoring.mono_cliques()`）。
2. **操作は Animation のリストを返す**：`self.play(*obj.op(...))` で使える形にする（`GraphMob.layout_to`, `color_edges` など）。
3. **付属物は追従する**：要素を動かしたらラベル・囲み・強調線がついてくるように updater を付ける。
4. **意図的な重ね描きは `mark_overlay()`**：強調・囲み・注記は自動レイアウト検査の対象外にする。
5. **読み辞書**：分野の用語・人名で VOICEVOX が誤読するものは `YOMI` に入れて `voice.register_words(YOMI, SUSPECT)`。
   誤読は `transcripts/<Scene>.txt` のカナ（⤷ の行）で見つける。
6. **`__all__` を定義する**：star import での名前衝突を防ぐ（manim の `Graph` とぶつかって壊れた前例がある）。

## PR に含めるもの

- 分野モジュール本体（`src/lecanim/domains/<分野>.py`）
- **お手本シーン**（`examples/<分野>/`：シーン＋`narration/` の台本＋`lecanim.toml`＋`pyproject.toml`）。
  [docs/STYLE.md](docs/STYLE.md) の原則（操作で見せる，記号を指して定義，式は1項ずつ，発表原稿の台本）を満たすもの。
  部品だけでは使い方が伝わらず，Claude が真似る見本にもならない。
- データ構造の単体テスト（`tests/test_<分野>.py`）
- [docs/API.md](docs/API.md) への追記

## 手元での確認

```bash
uv sync --group dev
uv run pytest -q
cd examples/<分野> && VOICE=0 uv run lecanim beats --strict    # 台本の不足・レイアウト警告ゼロ
uv run lecanim render --no-voice && uv run lecanim sheet <file> <Scene>   # 目視
```

CI（GitHub Actions）は単体テストと，全お手本の `lecanim beats --strict` を実行する。

## コアを変えるとき

`LectureScene` の振る舞い（`define`, `explain`, 自動QA など）を変えると，すべての分野のお手本の見た目が変わる。
変更前後で全お手本の `lecanim beats --strict` とコンタクトシートを確認すること。
