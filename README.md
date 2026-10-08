# lecanim

自分の勉強ノートにある数学の **定義・定理・証明** を，**Manim のアニメーション＋VOICEVOX のナレーション**で解説動画にするための制作基盤。
Claude Code などの AI エージェントと一緒に使うことを前提に，手順・品質基準・自動チェックをまとめている。

- 構成は **モチベ → 定義・定理 → 具体例 → 証明 → まとめ**。
- 証明は「スライドの文章」ではなく **グラフを動かす・囲む・塗り替える・総当たりする** といった操作で見せる。
- 記号は初出で **図の中の対象を指して** 定義し，数式は **1項ずつ** 説明する。
- ナレーションは字幕の読み上げではなく，**1本の発表原稿**（台本）として書く。
- 具体例は `assert` で検証し，レイアウト・台本の過不足・誤読・長い無音を自動でチェックする。

分野ごとの部品は `lecanim.domains` に置く。今はグラフ理論（`Graph`, `GraphMob` など）が充実している。
他の分野の部品の PR を歓迎します（[CONTRIBUTING.md](CONTRIBUTING.md)）。

## 必要なもの

uv，LaTeX（MacTeX / TeX Live），ffmpeg，poppler（`pdftotext`, `pdftoppm`），Docker（VOICEVOX エンジン），
日本語フォント（Noto Sans CJK JP 推奨）。Linux では `libcairo2-dev libpango1.0-dev pkg-config` も。

音声は VOICEVOX。動画を公開するときはキャラクターのクレジット（例：`VOICEVOX:春日部つむぎ`）が必要で，`lecanim` が説明欄と動画末尾に自動で入れる。

## 使い方

```bash
git clone https://github.com/Narfidort/lecanim
uv run --project lecanim lecanim new my-videos/anim --course "シリーズ名" --series "シリーズ名"
cd my-videos/anim
uv run lecanim voice up                 # VOICEVOX（Docker）を起動
uv run lecanim pdf ../my-notes.pdf      # ノートの PDF → materials/（テキスト・ページ一覧）
# lecture1.py にシーンを書く（Claude に頼むなら下の「Claude Code で使う」）
uv run lecanim beats lecture1           # 読み上げ場面の一覧と，台本の不足分の雛形
# narration/lecture1.py に台本を書く
uv run lecanim render lecture1 && uv run lecanim check lecture1
uv run lecanim render lecture1 -q h     # 1080p60
uv run lecanim youtube                  # 説明文・チャプター
```

コア数の多い Linux マシンに SSH で入れるなら，`lecanim render … --remote` で本番レンダリングを任せられる（[WORKFLOW](docs/WORKFLOW.md) 4.5）。

お手本のシーン（R(3,3)=6，Oreの定理）は [examples/graph-theory](examples/graph-theory)。

## Claude Code で使う

1. スキルを入れる：`cp -r claude/skills/lecture-animation ~/.claude/skills/`
2. `lecanim new` で作ったプロジェクトには `CLAUDE.md` が入っていて，手順書と品質基準を読むよう指示している。
3. あとは「ノート（../my-notes.pdf）の定理3を動画にして」「R(3,3)=6 の証明を動画にして」のように頼む。

## ドキュメント

- [docs/WORKFLOW.md](docs/WORKFLOW.md) — 手順と各ステップの完了条件
- [docs/STYLE.md](docs/STYLE.md) — 演出・説明・台本の原則（品質基準）
- [docs/API.md](docs/API.md) — `LectureScene` / `GraphMob` などの API とはまりどころ
- [docs/PERFORMANCE.md](docs/PERFORMANCE.md) — レンダリングの高速化（VFR・エンコーダー・計測の注意）

## 構成

```
src/lecanim/
  style.py      色，日本語と TeX の混在テキスト（row, lines, theorem）
  layout.py     描画領域と配置（Box, fit, layout_*）
  units.py      分野の描画クラスの基底（LiveGroup）と重ね描きの印（mark_overlay）
  scene.py      LectureScene：見出し・字幕・記号メモ・式の1項ずつの説明・自動レイアウト検査・ナレーション
  voice.py      VOICEVOX 合成（キャッシュ）・TeX → 読み・誤読辞書
  narration.py  台本（narration/*.py）の読み込み
  cli.py        lecanim コマンド
  templates/    lecanim new の雛形（設定・読み辞書・サンプルシーン・台本・CLAUDE.md）
  domains/      分野モジュール：graph.py（グラフ理論），_template.py（新しい分野の雛形）
tests/          単体テスト（CI で実行．お手本の strict な空実行も CI で行う）
claude/skills/lecture-animation/   Claude Code 用スキル
```
