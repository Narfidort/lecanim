# API リファレンス

```python
from lecanim import *                  # コア：manim，色・文字，配置（Box, fit, layout_*），LectureScene
from lecanim.domains.graph import *    # 分野の部品（グラフ理論）
```

manim 自身の `Graph` / `DiGraph` は名前がぶつかるので `from lecanim import *` では出さない。

## LectureScene（`lecanim.scene`）

```python
class MyScene(LectureScene):
    lecture, topic = "第6回 ○○", "定理6-1 ○○"   # 右上のパンくず
    chapter = "○○の定理"                         # YouTube チャプター名（省略時 topic）
```

| メソッド | 役割 | 台本のキー |
|---|---|---|
| `title_card(title, subtitle)` | 冒頭のタイトル | `title:` |
| `phase(kind, title)` | 見出し切替．kind = motivation / definition / example / proof，実験の回は observe / question / experiment / result / claim（言えること） | `phase:<title>` |
| `note(text, block=True)` | 画面下の字幕．`block=False` で読み上げ中に次へ（後で `wait_voice()`） | `note:<text>` |
| `define(sym, meaning, target=, math=True, short=)` | 記号・用語を指し示して記号メモへ．`short` はメモ用の短い説明 | `def:<sym>` |
| `recall(sym)` | 記号メモの該当項目を光らせる | — |
| `explain(parts, at=, size=, order=, keep=)` | 式を1項ずつ説明．parts = `[(tex, 説明, 色, action), ...]`．説明なしの項は `("=",)` | `ex:<説明>` |
| `count_up(mobs, color=)` | 番号を振って数える（番号の VGroup を返す．後で FadeOut） | — |
| `speak(text, kind="say")` / `wait_voice()` | 任意の場面での読み上げ／待ち | `say:<text>` |
| `show(*mobs, overlay=False)` | 表示（横はみ出しは自動縮小） | — |
| `steps_at(...)`, `step(*parts)` | 箇条書きを積む（溢れたら自動スクロール） | — |
| `overlay(*mobs)` | 重なり検査の対象外にする（ハイライト等） | — |
| `unit(vgroup)` | 部品ごとにアニメした図を1まとまりとして扱う | — |
| `clear_body(keep=())` | ヘッダ・記号メモ以外を消す | — |
| `agenda(items, current=, done=)` | 問いの一覧．`current=None` で全項目を順に並べ，`current=i` で i 番目を強調（ブロックの冒頭） | `agenda:`, `q:<項目>` |
| `end_card(*points)` | まとめ（各項目を読み上げ，クレジット表示） | `summary:`, `end:<point>`, `outro:` |

テーマ：`lecanim.toml` の `[style] theme`。`"classic"`（既定．丸い色付きチップ）／`"sharp"`（無彩色の地＋青・琥珀・赤・緑の4色，
角を立てた見出し・吹き出し，左寄せのタイトル）。色の名前（`BLUE_E` など）はテーマごとに値が変わる。
テーマの値：`ACCENT`（強調色），`CAPTION`（字幕の色），`LINE`（罫線），`CORNER`（角の丸み）。

テキスト部品（`lecanim.style`）：`row("日本語 $x^2$ 混在", size=, color=, weight=)`，`lines(...)`，`theorem(title, *rows)`，
`boxed(m, title)`，`jp`, `mt`。色：`FG, DIM, RED_E, BLUE_E, GREEN_E, YELLOW_E, PURPLE_E, ORANGE_E, ECOL`。

## 配置（`lecanim.layout`，コア）

`Box.left(frac)/right(frac)/full()/from_lrbt(l, r, b, t)`，`fit(pos, box, margin=)`，
`layout_circle / layout_line / layout_bipartite / layout_groups`（キー → 座標 の dict を返す）。

## 部品の共通の仕組み（`lecanim.units`，コア）

`LiveGroup`（分野の描画クラスの基底．部品ごとにアニメしても play 後に1つのまとまりに戻る），
`mark_overlay(m)`（自動レイアウト検査の対象外にする）。

## グラフ（`lecanim.domains.graph`）

- `Graph(vertices, edges, directed=False)`，`Graph.complete/cycle/path/complete_bipartite`
  - `neighbors, in_neighbors, degree, out_degree, in_degree, min_degree, sigma2, induced, component(v, allowed)`
  - `cliques(k), is_path, is_cycle, hamiltonian_cycle(), longest_path(), is_proper_coloring(c), greedy_coloring()`
- `EdgeColoring(graph, {edge: "r"/"b"/...})`：`mono_cliques(k, color)`, `color_degree(v, c)`, `color_graph(c)`, `random(...)`
- 配置：コアの `layout_*` に加えて `layout_nx(graph, kind)`（networkx の配置）
- 検証：`crossings(graph, pos)`（交差する辺の組），`near_misses(graph, pos)`
- `GraphMob(graph, pos, box=, labels=, edge_colors=, vertex_colors=, arcs={(u,v): 角度}, ...)`
  - `g[v]`（頂点），`g[u, v]`（辺），`g.label[v]`，`g.point(v)`
  - アニメーションのリストを返す：`create(), layout_to(pos), add_vertex, remove_vertex, add_edge, remove_edge,
    color_edges, color_vertices, highlight_path, fade_others, unfade, edge_style(m, color, opacity, width)`
  - 頂点に追従する重ね描き：`face(seq)`（面の塗り），`blob(vs, color, label=)`（囲み），`path_mob(seq)`（経路の太線），
    `annotate(v, text)`（注記）．頂点を `layout_to` で動かすと辺・ラベル・囲みが自動でついてくる
  - `set_arcs({...})`（曲線の辺を設定し直す），`to_scene(p)`（元座標→画面座標）
- `colored_graph_mob(coloring, pos, box=)`：EdgeColoring をそのまま色付きで描く
- 読み辞書：閉路・次数・彩色・出次数・強連結…，人名（Ramsey, Ore, Kempe…）を import 時に登録

## 推論サービング（`lecanim.domains.serving`）

LLM 推論の GPU 配置・P/D 分離・遅延の内訳・性能曲線。お手本は `examples/serving/topology.py`。

- データ構造（すべて assert で検証できる）
  - `Worker(name, role, gpus, tp, ep, dp_attention)`：role は `"P"`（Prefill）/ `"D"`（Decode）/ `"A"`（両方）
  - `Deployment(workers, nodes=2, gpus_per_node=8)`：`check()`（重複・範囲外・TP と GPU 数の不一致），`ok`, `free()`,
    `of(role)`, `gpus_of(role)`, `label`（`"4P2D"`）．`Deployment.pack([("P", 2, 2)] * 4 + [("D", 4, 4)] * 2)` で前から詰めて割り当て
  - `SLO(ttft_ms=3000, itl_ms=20, min_rate=0.9)`，`Measurement(c, good_tok_s, good_rate, itl_ms=, ttft_ms=, total_tok_s=)`，
    `Sweep(name, points)`：`best(slo)`, `first_fail(slo)`
  - `Breakdown([(名前, 値), ...], unit="µs")`：`total`, `share(name)`, `replace(**値)`（0 で区間が消える）
- 描画（操作は Animation のリスト）
  - `ClusterMob(dep, box=)`：ノード × GPU の四角と担当の枠．`cm.gpu[(n, i)]`, `cm.wbox[name]`．
    `create()`, `reassign(new_dep)`（同名の担当は変形），`highlight(names, color)`, `unhighlight()`,
    `tag(name, text)`（枠に追従する注記），`role_legend()`
  - `StackBarMob(bd, length=, ref_total=)`：横向き積み上げ棒．長さは `ref_total` に対する比率なので，
    `morph_to(new_bd)` で短くなったことが見える．`highlight(name)`, `unhighlight()`
  - `ChartMob(x_range, y_range, x_label=, y_label=, box=)`：`plot(key, pts, color, label=, fail=[番号])`（不合格点は中抜き），
    `hline(key, y, label)`（上限線），`vline`, `ring(key, i)`（点を丸で囲む重ね描き）
  - `TimelineMob(lanes, t_max, box=, ticks=)`：ガント図．`bar(lane, t0, t1, color, label)` で棒を作り `grow(bars)` で伸ばす
- 色：`ROLE_COLOR`（P＝オレンジ，D＝青，A＝紫）．読み辞書：Prefill, Decode, TTFT, ITL, GPU, MoE, GEMM, AllReduce, 律速…

`end_card(*points, title=)` で，まとめの見出しを「証明の構造まとめ」以外にできる（実験の動画では「観察のまとめ」など）。

## 新しい分野

`src/lecanim/domains/_template.py` をコピーして作る。約束は [CONTRIBUTING.md](../CONTRIBUTING.md)。

## 音声（`lecanim.voice`）

- `yomi(text)`：読み上げ文 → エンジンに渡す文（`$...$` の TeX を読みに，辞書置換，空白除去）
- `synth(spoken)` → WAV（キャッシュ），`kana(spoken)` → エンジンの解釈したカナ，`credit()`
- 辞書の適用順：プロジェクトの `yomi.toml` → 分野モジュールの `register_words()` → 汎用の `BASE_WORDS`

## プロジェクトの構成

```
anim/
  lecanim.toml       設定（シリーズ名，動画ごとの YouTube タイトル・概要，話者）
  yomi.toml          読みの追加辞書
  lectureN.py        シーン（1ファイル＝1回）
  narration/lectureN.py   台本（SCRIPTS = {シーン名: [(キー, 読み上げ文), ...]}）
  materials/         ノートのテキスト・ページ一覧（lecanim pdf）
  transcripts/       読み上げ場面一覧・読んだ文とカナ・チャプター情報（自動生成）
  qa_reports/        レイアウト・台本の警告（自動生成）
  media/videos/lectureN/{480p15,1080p60}/Scene.mp4, lectureN_1080p60.mp4（結合版）
  youtube/lectureN.txt    説明文
```

## はまりどころ

- `Mobject` の属性名（`dim` など）とメソッド名を衝突させない。
- 曲線の辺は `set_color` すると塗りが付く → `edge_style()` を使う。
- `\xLeftrightarrow` は使えない（`\overset{..}{\Longleftrightarrow}`）。`MathTex` に日本語を入れない。
- Python 文字列で `\t`（`\times`, `\to`）がタブにならないよう raw string か `\\`。
- 並列レンダリングは 3 程度まで（Pango のキャッシュ競合）。
