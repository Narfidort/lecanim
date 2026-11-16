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
| `phase(kind, title)` | 見出し切替．kind は motivation / definition / example / proof / summary など（`PHASES` にある日本語ラベルになる）だが，これは数ある構成の1つ．登録のないキーはそのまま見出しの文字になるので，証明以外の動画は好きな文字列でよい | `phase:<title>` |
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

配色（既定は「深海」トーン．考え方は docs/STYLE.md §0）：地が `BG`（ほぼ黒）・`FG`（本文）・`DIM`（副次的な文字）・`LINE`（罫線），
構造用が `MAIN`（見出し・枠など，彩度のある青），強調用が `ACCENT`（いま一番注目してほしい1点だけに使う，より明るい青）。
角の丸みは `CORNER`（既定 0）。`lecanim.toml` の `[style]` で `bg`/`fg`/`dim`/`line`/`main`/`accent`/`corner`/`jp_font` を上書きできる。
`BLUE_E`・`ORANGE_E`・`PURPLE_E`・`YELLOW_E` は「黒・白・青」の家族の中で濃淡を変えた凡例用の色（`YELLOW_E` は `ACCENT` と同じ）。
`GREEN_E`（正しい・合格）・`RED_E`（誤り・警告）だけは例外として本物の緑・赤を残している。
色分けに意味がある場合（Narfi の Fix/Obtain，グラフの彩色，複数系列のグラフなど）の凡例（`PALETTE`）にだけ使い，装飾には使わない。

テキスト部品（`lecanim.style`）：`row("日本語 $x^2$ 混在", size=, color=, weight=)`，`lines(...)`，`theorem(title, *rows)`，
`boxed(m, title)`，`jp`, `mt`。色：`FG, DIM, RED_E, BLUE_E, GREEN_E, YELLOW_E, PURPLE_E, ORANGE_E, ECOL`。
`row()` は `$...$` で囲まなくても，地の文に混ざる裸の変数（英字1文字，ギリシャ文字1文字，`a_n`・`x_1` のような
1文字の下付き）を自動で数式として組む（`_SYMBOL_TEX`／`_VAR_RE`，検証済みの小さい記号表だけが対象）。
前後が英数字の単語の内側では働かない（`Fix`・`QA` のような英単語はそのまま）ので，$ を書き忘れても崩れない。
英単語をあえて数式にしたくない所（まれ）は `row()` でなく `jp()` を直接使う。

`label(s, size=, color=)` は，分野モジュールが「呼び出し側から受け取った1つのラベル文字列」を組むときに使う
小さな振り分け関数：`s` に `$` か日本語（CJK）が含まれていれば `row()` に，それ以外（純粋な LaTeX，例えば
`r"\hat Y"` や `"X_1"`）ならそのまま `mt()` に渡す。分野の部品（`ProjectionMob.vec`，`CoefBarMob` の名前，
`DistMob.stat_mark` など）のラベル引数は，これを通すと日本語・数式のどちらを渡しても安全に組まれる
（`mt()` に直接日本語を渡すと LaTeX が Unicode エラーで落ちる：docs の「はまりどころ」参照）。

## 配置（`lecanim.layout`，コア）

`Box.left(frac)/right(frac)/full()/from_lrbt(l, r, b, t)`，`fit(pos, box, margin=)`，
`layout_circle / layout_line / layout_bipartite / layout_groups`（キー → 座標 の dict を返す）。

## 部品の共通の仕組み（`lecanim.units`，コア）

`LiveGroup`（分野の描画クラスの基底．部品ごとにアニメしても play 後に1つのまとまりに戻る），
`mark_overlay(m)`（自動レイアウト検査の対象外にする）。

## 座標軸（`lecanim.plot`，コア）

`AxesMob(box, xr, yr, x_label=, y_label=, numbers="xy")`：座標軸（軸・目盛りの数字・軸ラベル）と，その上に
描く部品．座標軸を使うグラフ（解析の `PlotMob`，統計の `DistMob`・`ScatterFitMob`）はこれを継承し，軸の建て方
そのものは再実装しない（分野の言葉の操作だけを足す）。

- `p(x, y)`（グラフ座標→画面座標），`xr`/`yr`（そのまま保持）
- `curve(f, color=, x0=, x1=, width=, n=, add=)`：y=f(x) のグラフ
- `area(f, x0, x1, color=, opacity=, add=)`：f(x) と x 軸のあいだを塗る
- `hline(y, color=, label=, add=)` / `vline(x, color=, label=, label_dir=, add=)`：破線の参照線（`label` は
  `style.label()` と同じ規則）
- `dots(pts, color=, radius=, add=)`：点の集まり
- どの部品も軸に入り（`add=False` なら返すだけ），自動レイアウト検査の対象外（`mark_overlay`）

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

## 音声と画面の同期（`LectureScene`）

| メソッド | 役割 |
|---|---|
| `cue(name, lead=0)` | 台本の〔name〕を読み始める時刻まで待つ（過ぎていれば待たず，遅れを記録）．自動の合図：`s0, s1, …`（文の頭），`end` |
| `plan_cues(names, seconds=None)` | 台本にない合図を前後の間に等間隔で補う（`seconds` で動きの長さを考慮） |
| `pulse(*mobs)` | 音声が続くあいだ，文の頭ごとに mobs を光らせる |
| `speak(text)` | 台本（合図つき）を読み始める．合図の時刻は `voice.timeline()` が音素長から予測 |

`voice.prepare(text)`（読み上げ文と合図の位置），`voice.timeline(text)`（合図の時刻）．検査：`lecanim.qa`（`check_all(scene)`，`Item/Issue`）．
部品に `_qa_target`（矢印が指す対象）や `_qa_modal = True`（意図して他を覆う板）をつけると検査が正しく判定する．

## 証明のスコープ（`lecanim.domains.narfi`）

Narfi（自然演繹の証明記述言語）風に証明をデータで書き，束縛変数のスコープと依存関係を検査して見せる。
お手本は複素関数論プロジェクトの `lecture0.py`（ε-N 論法，一様収束）。

- 論理式：`Forall(x, body, bound=">0" | r"\in E" | r"\ge N")`，`Exists`，`Imp`，`And`，`Or`，`Not`，`Bot`，`Atom(tex)`
  （`bound` が `\in …` なら型，それ以外は条件．`x` はタプルで複数可）
- 証明の行：`Fix(x, h, body=[…])`（∀導入），`Assume(h, body=)`（⇒導入），`ByContra`，`Obtain(x, h, src, args=[…])`
  （仮定 src の先頭の ∀ に args を入れて ∃ を外す），`Choose(t)`（∃導入），`Have(h, prop, by)`，`Let(x, t)`，
  `Chain(start, [(rel, 項, 根拠), …])`（不等式の連鎖），`Just(根拠)`，`Contradiction`，`Cases/Case`．各行に `note=` で短い説明
- `Thm(名前, goal=, body=, hyps=[(h, 論理式, 表示用の短い形)], params=, lemmas={名前: 論理式})`
- `check(thm)` → `Trace`：`ok`, `errors`（スコープ外の名前・名前の衝突・goal の形の不一致・閉じていない goal），
  `deps(name)`（Obtain/let した変数が依存する任意の変数．例：`N(ε)`），`lines[i].ctx / goal / closes`
- 描画：`ProofMob(trace, size=, width=, fit=, scope_style="line"|"box", minimap=False)`（スコープは既定で左の細い縦線．
  文字の大きさは固定で，長い証明はいまの行が見えるよう自動スクロール・外側のスコープの見出しを上に固定（sticky）．
  ミニマップ・`fold(j)` の畳みは既定では使わない（画面が込み入るため）．`fit=True` は全体を窓に収める（記法の説明用）．
  `faint()` で全体を薄く置き `reveal(i)` で1行ずつ，`unfold_all()` で全体に戻す），
  `ContextPanel(trace, framed=False)`（文脈 Γ：変数は横並び・仮定は縦並び，goal．一度も根拠に使わない事実は薄く．
  根拠に使う事実は `emphasize()` でその場で大きく黄色に，`restore()` で戻す）．
  `walk(scene, pm, cp, i, 字幕)` で1行実行：goal の先頭が外れて文脈へ移る／根拠の事実を文脈の中で大きく表示（`callout=True` で
  行の近くに吹き出し）／Obtain と `Just(根拠, src=, args=)` は事実の中身を展開し（背景を少し明るくした領域），
  ∀ に1つずつ代入して剥がし ∃ の変数を取り出す／∴ 行でスコープを出る（`fold=True` で畳む）．`pm.dep_arrows(name)`（依存の矢印），
  `scope_bars(MathTex, [(i, j, 色, ラベル)])`（量化子のスコープを式の下の帯で示す）
- 色：Fix＝青（任意），Obtain＝橙（存在），assume＝緑（仮定），let＝紫（定義），choose＝黄

## 数理統計・計量経済（`lecanim.domains.stats`）

- `ScatterFitMob(box, xr, yr)`：`AxesMob` を継承．2変数の散布図＋回帰直線＋残差（K=1 の最小二乗の直感）．
  `scatter(xs, ys)`, `line(b0, b1)`, `residuals(xs, ys, b0, b1)`．（`points` は manim の予約属性と衝突するので `scatter`）
- `ProjectionMob(box, foot=(fx, fy))`：最小二乗の幾何の模式図．平面＝列空間 col(X)，平面上の点が `foot`（Ŷ の位置），
  真上に `lift` だけ上げた点が Y．`pO()/pfoot()/pY()` は現在位置を返す関数．`vec(frm, to, label=, direction=)` は
  これらの関数を渡すと `foot` を動かしたときに自動で追従する矢印を作る（`label` は `style.label()` の規則）．
  `right_angle()` は足にある直角の印（追従する）．
  `set_foot(fx, fy)` で足を動かすアニメーションを返す（分割回帰・過剰定式化で Ŷ が変わる様子に使う）．
- `BlockMatrixMob()`：行列・ベクトルを矩形として並べる．`col_blocks([(label, width, color), ...], h=)`（X=[X1|X2] の
  ような横並びの分割），`grid2x2(w1, w2, h1, h2, labels, colors=)`（2×2 の分割行列），
  `eq(*parts, box=)`（col_blocks/grid2x2 の結果と `"="`/`"+"` のような文字列を式として並べ box に収める）．
  いずれの `label` も `style.label()` の規則．
- `DistMob(box, xr, yr, x_label=)`：`AxesMob` を継承．検定統計量の分布のグラフ．`density(pdf)`（`curve` の薄いラッパ），
  `tail(pdf, x0, x1)`（棄却域の塗り，`area` のラッパ），`stat_mark(x0, label=)`（検定統計量の実現値の縦線，`vline`
  のラッパ），`hline(y, label=)` は `AxesMob` からそのまま．`normal_pdf/chi2_pdf/t_pdf/f_pdf` は対数空間で計算する
  ので自由度が大きくても（`math.gamma` のオーバーフローを起こさず）使える．
- `CoefBarMob(box, names, values, se, z=1.96)`：回帰係数の推定値と信頼区間のバー（実データの回帰表を読む用）．
  0 の位置に破線．`star(name)`（有意性の印），`highlight(name, color=)`．`names` は `style.label()` の規則。
- 数値（具体例の assert 用）：`ols(X, Y)` → (β̂, ε̂)，`projection_matrix(X)`，`annihilator_matrix(X)`，
  `is_idempotent(M)`，`is_symmetric(M)`，`gls(X, Y, Omega)`，`f_stat(X, Y, R, c)`．

## 複素平面・関数のグラフ（`lecanim.domains.complex`）

- `PlaneMob(box, xr, yr, ticks=, grid=)`：複素平面．`p(z)`（複素数→画面座標），
  `dot(z, label)`, `vec(z)`, `seg(z1, z2)`, `disk(c, r, closed=)`（開円板は点線），`ring`, `curve(f, t0, t1)`,
  `polyline`, `seq(zs)`, `square(c, side)`, `polar(z)`（r と θ の印），`region(pred)`（条件をみたす点を塗る）．
  部品は平面に入り，平面を動かすと一緒に動く（`add=False` なら返すだけ．どちらも重なり検査の対象外）
- `PlotMob(box, xr=(lo, hi, step), yr=…)`：`AxesMob` を継承．実関数のグラフ．`graph(f)`（`curve` のラッパ），
  `band(f, eps)`（ε の帯），`hband(y, eps)`，`vline`/`dots` は既定の色だけ変えた薄いラッパ，`hline` は `AxesMob` からそのまま
- 数値検証：`radius_cauchy_hadamard(coef)`, `partial_sums(term, n)`, `sup_dist(f, g, xs)`
- 読み辞書：複素・正則・共役・偏角・整級数・一様収束・Cauchy・Weierstrass…

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
- `\xLeftrightarrow` は使えない（`\overset{..}{\Longleftrightarrow}`）。`MathTex`（`mt()`）に日本語を直接渡すと
  LaTeX が Unicode エラーで落ちる。呼び出し側のラベル文字列を組む分野の部品は `mt()` 直書きではなく `style.label()`
  に通すこと（日本語でも純粋な LaTeX でも安全に振り分けられる）。
- Python 文字列で `\t`（`\times`, `\to`）がタブにならないよう raw string か `\\`。
- 並列レンダリングは 3 程度まで（Pango のキャッシュ競合）。

## 追加（2026-10）：Narfi の現行仕様・本物の検査器・カメラ方式

- **表示を現行の書き方に**：`Obtain x(依存) | h by src(args)`，`h : φ by j`（`have` は出さない），`by_contra h`，`k(h)`（`contradiction` は消えた），
  `Induction(x, zero=[…], k=, ih=, succ=[…])`（`induction n` の下に `Case zero` / `Case succ k, IH : φ(k)`）．
- **本物の Narfi で検査した証明を取り込む**：`lecanim.domains.narfi_src.load_narfi("file.narfi")` → `{定理名: Trace}`．
  `narfi web --no-open` を起動して `/api/check` を呼ぶ（各行の文脈・goal が TeX つきで返る）．`narfi` は
  `cargo install --path narfi`（https://github.com/Narfidort/Narfi），または環境変数 `NARFI_BIN`．古い書き方は `narfi migrate --write`．
  Trace は ProofMob / ContextPanel / walk でそのまま使える（Narfi の核が検算した証明を見せられる）．
- **カメラ方式**：`proof_view(scene, tr, camera=True)`．証明の全体を縮小して置き，`walk` が読む行へズームする（スクロール・畳み・ミニマップなし）．
  `pm.overview()` で引く．`focus_rows` で「いまの行まわり何行を読める大きさにするか」．
- `proof_view` / `prove` はライブラリの関数になった（以前は各プロジェクトに写していた）．
- `define()` の区切りは「：」でなく「—」（`:` は Narfi の記法で紛れるため）．
- 根拠の事実の拡大（`emphasize`）は，下の項目を押し下げて重ならない．新しい事実が入る前に元の大きさへ戻す．
