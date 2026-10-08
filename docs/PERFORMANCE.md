# レンダリングの高速化

ナレーション付き 1080p60 の書き出しを速くするための仕組みと設定。実測は nk（RTX 5060 Ti，WSL）。

## 結論（既定の構成）

| 構成（Schur，約4分のシーン） | 時間 |
|---|---|
| manim 既定（libx264 medium） | 204 秒 |
| NVENC のみ | 124 秒 |
| NVENC ＋ 静止区間 VFR | 69 秒 |
| **x264 veryfast ＋ 静止区間 VFR（既定）** | **50 秒** |

全16シーン（合計約78分の動画）は nk で約 9分47秒（並列 3）。

## 仕組み1：静止区間の可変フレームレート（`[render] vfr_still = true`）

- manim は `wait()` の間，同じ絵を毎秒60回 `from_ndarray` ＋エンコードし直す。ナレーション付きは大半が静止区間なので，ここが最大の無駄。
- `encode.py` が `_PartialMovieEncodeJob._encode_and_write_frame` を差し替え，静止区間は「最初と最後の2フレーム＋ pts の飛び」で書く。見た目と長さは同じ。
- **B フレームを使わない（`bf=0`）こと。** MP4 の長さは dts ベースなので，B フレームがあると pts の飛びが長さに反映されず短くなる。
- 検証：普通に書いた動画と長さが完全一致，フレーム比較で PSNR 40〜47 dB。

## 仕組み2：エンコーダーの差し替え（`[render] encoder`）

- manim は libx264（preset medium）決め打ち。`encode.py` が `av.open` を代理して `add_stream("libx264")` だけ別のエンコーダーに替える。
- `auto`（既定）は libx264 veryfast（crf 23）。図形アニメはフレームが単純で x264 が軽い。
- `nvenc`：明示指定のときだけ。**非推奨**。x264 より遅く，`play` が短く連続するシーン（run_time 0.05〜0.08 秒の FadeIn/FadeOut の繰り返し）で segfault する。
  - 原因の見立て：play ごとに別スレッドで NVENC セッションを開閉するため，終了と開始が重なる。ロックで直列化しても直らなかった。
  - Mac の VideoToolbox（`videotoolbox`）も M3 では x264 veryfast より遅い。
- `x264`：manim 既定のまま（比較用）。環境変数 `LECANIM_ENCODER` / `LECANIM_VFR=0` で一時的に上書きできる。

## 仕組み3：並列とキャッシュ

- 並列数は「空きメモリ ÷ `mem_per_job_gb`（4GB）」以下に自動で絞る。1シーン 2.4〜3GB まで育つので，起動時の空きだけ見ると OOM になる。
- シーンごとに TeX / テキストのキャッシュ dir を分け，共有キャッシュからハードリンクで種をまく（並列でも壊れない）。
- 失敗したシーンは単独で1回だけ再実行する。

## 計測の注意

- **同じ条件で測る。** 一度「29 秒」と出たが，再現しなかった（キャッシュ等の差）。必ず同じシーン・同じ負荷で，基準（`LECANIM_VFR=0 LECANIM_ENCODER=x264`）と並べて測る。
- リモートで前回の実行が残っていると，VOICEVOX の転送ポート 50021 が塞がって数秒で「完了」する。測る前に `ps` で古い `lecanim render` / `manim` が残っていないか確認する。
- 計測コマンド例（nk 側）：
  ```bash
  cd ~/lecanim-remote/projects/<proj>
  /usr/bin/time -f "elapsed=%e" .venv/bin/manim -qh --disable_caching \
    --config_file logs/<Scene>.manim.cfg lectureN.py <Scene>
  ```
- 全体：`uv run lecanim render -q h --remote`（`lecanim.toml` の `[remote] host`）。

## 残っている時間

Cairo の描画（CPU），LaTeX の呼び出し，`deepcopy`，`from_ndarray` が中心。OpenGL レンダラーで GPU に回せるが，見た目が変わるリスクがあるので入れていない。
試す余地：`mem_per_job_gb` を下げて並列を増やす，manim 0.21 の `max_inflight_encoders`，シーンを範囲分割して並列化。
