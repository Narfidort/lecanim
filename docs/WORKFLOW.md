# 制作ワークフロー（ノート → 解説動画）

所要の目安：1本（3〜5シーン）で，シーン作成 → 台本 → 確認まで。各ステップの「完了条件」を満たしてから次へ。

## 0. 準備（初回のみ）

必要なもの：uv，LaTeX（MacTeX / TeX Live），ffmpeg，poppler（pdftotext / pdftoppm），Docker（VOICEVOX 用），
日本語フォント（Noto Sans CJK JP 推奨）。Linux では Manim のビルドに libcairo2-dev, libpango1.0-dev, pkg-config も必要。

```bash
git clone <このリポジトリ> lecanim
uv run --project lecanim lecanim new <ノートのフォルダ>/anim --course "シリーズ名" --series "シリーズ名"
cd <ノートのフォルダ>/anim
uv run lecanim voice up        # VOICEVOX エンジン（Docker）を起動
```

以後のコマンドはプロジェクト内で `uv run lecanim …`。

## 1. 題材を整理する

ノートから扱う定理と証明を選ぶ。ノートが PDF なら：

```bash
uv run lecanim pdf ../my-notes.pdf
```

`materials/<名前>.txt`（本文）と `materials/<名前>_sheet.png`（全ページの縮小一覧．図の確認用）ができる。

**完了条件**：「区切りのいい単位」（1つの定理とその証明，目安 3〜7 分）のシーン一覧を決めた。

## 2. シーンを書く（`lectureN.py`）

構成は **モチベ → 定義・定理 → 具体例 → 証明 → まとめ**（`phase()` で切り替え）。
冒頭で `from lecanim import *` と，使う分野の `from lecanim.domains.<分野> import *` を書く。
演出の原則は `STYLE.md`。API は `API.md`。

1. 具体例のデータ（グラフ・塗り方）をモジュール先頭に置き，`assert` で主張どおりか検証する
   （単色三角形がない，ハミルトン閉路がある，`crossings()` が空＝平面描画，…）。
   都合のよい例は探索して選ぶ（例：「重なりがちょうど1か所」になるグラフをランダム探索）。
2. 証明の各ステップを「グラフに対する操作」として書く。文字は字幕1行と，式の1項ずつの説明だけ。
3. 記号・用語は初出で `define()`，式は `explain()`，個数は `count_up()`。

```bash
uv run lecanim render lecture6 --no-voice     # 無音で素早く確認
uv run lecanim sheet lecture6 SceneName       # qa_frames/SceneName_sheet.png を目視
```

**完了条件**：`qa_reports/` の警告 0（意図的な重ね描きは `overlay()` で除外），コンタクトシートで
はみ出し・重なり・誤った指し示し（矢印が別の物を指している等）がない。

## 3. 台本を書く（`narration/lectureN.py`）

```bash
uv run lecanim beats lecture6
```

`transcripts/<Scene>.beats.txt`（読み上げ場面の一覧）と，不足分の雛形 `narration/_todo_lecture6.py` ができる。
雛形のキーをコピーして読み上げ文を書き，`narration/lecture6.py` の `SCRIPTS["SceneName"]` に入れる。

台本の書き方（`STYLE.md` の「ナレーション」）：
春日部つむぎのアカデミックな発表口調。字幕を読むのではなく，**1本の発表原稿**として，接続詞・主語・助詞を省かずに書く。
見出し（phase）は次に何をするかの導入文，まとめ（end）は完全な文で。

再度 `lecanim beats` を実行して「台本はすべての場面をカバーしています」になれば完了。

## 4. 音声つきで確認

```bash
uv run lecanim render lecture6        # 480p・音声つき（合成は ~/.cache/lecanim/voice にキャッシュ）
uv run lecanim check lecture6
```

`check` が報告するもの：レイアウト警告，**誤読の疑い**（`yomi.toml` の suspect と汎用リスト），長い無音。
読みは `transcripts/<Scene>.txt` の `⤷` 行（エンジンが解釈したカナ）で確認する。
誤読は `yomi.toml` の `words` に追加して再レンダリング（変わった文だけ再合成される）。

**完了条件**：`check` の読み・QA が 0 件。無音は「演出中で字幕もない区間」なら許容。

## 4.5 リモートでレンダリング（任意）

時間のかかる本番レンダリングは，SSH で入れる Linux マシン（コア数の多いデスクトップ，WSL2 など）に任せられる。
Manim（Cairo）の描画は CPU 処理なので，効くのはコア数による並列化（GPU は使わない）。
`lecanim.toml` の `[remote] host` に `~/.ssh/config` のホスト名を書く。

```bash
uv run lecanim remote setup                 # 初回：足りないものの確認，コードの同期，リモート環境の構築
uv run lecanim render lecture6 -q h --remote
```

- コード・台本・音声キャッシュを rsync で送り，リモートで `lecanim render` を並列実行し，動画・QA・transcripts を取り込む。
- 音声は SSH の逆ポート転送で **ローカルの VOICEVOX** を使う（リモートに VOICEVOX は不要．合成済みはキャッシュを同期）。
- 条件：`lecanim.toml` の `[style] jp_font` が両方にあるフォント（既定の雛形は Noto Sans CJK JP）。
  未設定（macOS は Hiragino）だと字形が変わるので拒否する（`--allow-font-mismatch` で無視）。
- 初回だけリモートでシステムパッケージのインストールが必要（`lecanim remote setup` が sudo のコマンドを表示する）。
- 速度：NVIDIA GPU があれば NVENC でエンコードし，静止区間は可変フレームレートで書く（`[render] encoder` / `vfr_still`）。
  実測（RTX 5060 Ti，ナレーション付き 1080p60・約4分のシーン）：manim 既定 221 秒 → NVENC 57 秒 → ＋静止区間 VFR 29 秒。

## 5. 仕上げ

```bash
uv run lecanim render lecture6 -q h   # 1080p60
uv run lecanim youtube                # youtube/lecture6.txt（タイトル・概要・チャプター・クレジット）
```

`lecanim.toml` の `[project.lectures.lecture6]` に title / summary を書いておく。
チャプター名は各シーンの `chapter`（なければ `topic`）。
VOICEVOX のクレジット（`VOICEVOX:春日部つむぎ`）は説明欄と動画末尾に自動で入る。消さないこと。
