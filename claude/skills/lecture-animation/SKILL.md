---
name: lecture-animation
description: 自分のノートにある数学の定義・定理・証明を Manim アニメーション＋VOICEVOX ナレーションの解説動画にする（lecanim 基盤）。「証明をアニメーションにして」「manim で定理を可視化」「lecanim」などの依頼で使う。新しい動画の作成，既存シーンの修正，台本・読みの修正，YouTube 説明文の作成を含む。
---

# 数学の解説アニメーション（lecanim）

`lecanim` は Python パッケージ＋CLI。プロジェクト内では `uv run lecanim …` で使う。
`uv run lecanim info` でドキュメントの場所が分かる。

作業を始める前に次の3つを必ず読むこと（STYLE.md は品質基準）：
- `docs/WORKFLOW.md` — 手順と各ステップの完了条件
- `docs/STYLE.md` — 演出・説明・台本の原則
- `docs/API.md` — LectureScene / GraphMob などの API

プロジェクトに既存のシーン（lectureN.py）があれば，新しいシーンを書く前に似た証明のシーンを読んで真似る。

最低限の流れ：
1. プロジェクトがなければ `uv run --project <lecanim のパス> lecanim new <dir> --course ... --series ...`
2. `uv run lecanim voice up`，ノートが PDF なら `uv run lecanim pdf <ノート>` で読む
3. シーンを書く（モチベ→定義・定理→具体例→証明→まとめ．証明はグラフの操作で．例は assert で検証）
   → `uv run lecanim render <file> --no-voice` → `uv run lecanim sheet <file> <Scene>` で目視
4. `uv run lecanim beats <file>` → narration/_todo_*.py を元に発表原稿を書く
5. `uv run lecanim render <file>` → `uv run lecanim check <file>`（誤読は yomi.toml）
6. `uv run lecanim render <file> -q h`（`--remote` も可）→ `uv run lecanim youtube`

レンダリングは時間がかかるので長いものはバックグラウンドで実行し，ユーザーには進捗と完了見込みを伝える。
