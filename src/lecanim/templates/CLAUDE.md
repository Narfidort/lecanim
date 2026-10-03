# {{COURSE}} — 解説アニメーション

このディレクトリは lecanim のプロジェクト。数学の定義・定理・証明を，
Manim のアニメーション＋VOICEVOX のナレーションで動画にする。

作業前に必ず読む：
- 手順：{{DOCS}}/WORKFLOW.md
- 演出・説明・台本の原則：{{DOCS}}/STYLE.md（品質基準．最重要）
- API：{{DOCS}}/API.md

要点：
- 構成は モチベ → 定義・定理 → 具体例 → 証明 → まとめ。証明はグラフの操作で見せる（スライド的な文字の羅列は不可）。
- 記号は `define()` で指してから使い，数式は `explain()` で1項ずつ。具体例は `assert` で検証。
- 台本は narration/ に，春日部つむぎのアカデミックな発表口調で1本の原稿として書く（字幕の読み上げは不可）。
- コマンドは `uv run lecanim <beats|render|check|sheet|youtube>`。完了条件は WORKFLOW.md の各ステップ参照。
