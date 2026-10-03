# お手本：グラフ理論

lecanim で作ったシーンの例。新しいシーンを書くとき（人でも Claude でも）は，まずここを読んで真似る。

| ファイル | シーン | 見どころ |
|---|---|---|
| `ramsey.py` | `R33`（R(3,3)=6） | 実験で動機づけ → 頂点を色で仕分けて囲む → 鳩の巣原理を玉と枠で → 8通りを総当たり → 別の例でも同じ手順 → 5人だと止まる |
| `hamilton.py` | `Ore`（Oreの定理） | ハミルトン閉路＝円周に並べ替えられる → σ₂ を内側から1項ずつ定義 → 辺極大な反例 → ハミルトン道を一直線に → 印と枠 → 切って裏返す |

台本は `narration/`，分野の読み辞書は `yomi.toml`。

```bash
cd examples/graph-theory
uv run lecanim render ramsey --no-voice      # 無音で確認
uv run lecanim voice up && uv run lecanim render ramsey
```
