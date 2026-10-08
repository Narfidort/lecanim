"""lecanim コマンド.

  lecanim new PATH --course 題名 --series シリーズ名     プロジェクトの雛形を作る
  lecanim voice up|status                              VOICEVOX エンジン (Docker) の起動・確認
  lecanim pdf PDF...                                   ノートの PDF → テキスト + ページ一覧画像 (materials/)
  lecanim scenes [FILE...]                             シーン一覧
  lecanim beats [TARGET...]                            読み上げ場面を書き出し, 台本の不足分の雛形を作る
  lecanim render [TARGET...] [-q l|m|h]                レンダリング → QA 要約 → ファイルごとに結合
  lecanim check [TARGET...] [-q l|m|h]                 台本の過不足・誤読の疑い・長い無音・レイアウト警告
  lecanim sheet FILE SCENE [-n 24]                     フレームを並べた確認用画像
  lecanim youtube [-q h]                               タイトル・説明文・チャプター (youtube/)
  lecanim remote setup|status                          リモート（SSH で入れる Linux マシン）の準備・確認
  lecanim info                                         インストール場所・ドキュメントの場所
  lecanim render ... --remote                          リモートでレンダリングして結果を取り込む

TARGET は "lecture2"（ファイル内の全シーン）, "lecture2:R33,Parsons"（指定シーン）, "all"（省略時と同じ）.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .config import find_root, load

QDIR = {"l": "480p15", "m": "720p30", "h": "1080p60"}
REPO_URL = "https://github.com/Narfidort/lecanim"   # 公開リポジトリ（git からインストールしたときの依存先）
# 名前が _ で始まるクラスは共通の基底クラスとみなし，シーンにしない
SCENE_RE = re.compile(r"^class\s+(?!_)([A-Za-z0-9_]+)\((?:[A-Za-z0-9_.]*Scene)\)", re.M)
TEMPLATES = Path(__file__).parent / "templates"


# ---------------------------------------------------------------- helpers
def root() -> Path:
    r = find_root()
    if not (r / "lecanim.toml").exists():
        sys.exit("lecanim.toml が見つかりません．プロジェクトのディレクトリで実行してください（lecanim new で作成）")
    return r


def lecture_files(r: Path) -> list[Path]:
    fs = [p for p in r.glob("*.py") if SCENE_RE.search(p.read_text())]
    return sorted(fs, key=lambda p: [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", p.stem)])


def scenes_of(f: Path) -> list[str]:
    return SCENE_RE.findall(f.read_text())


def targets(r: Path, args: list[str]) -> list[tuple[Path, list[str]]]:
    files = lecture_files(r)
    if not args or args == ["all"]:
        return [(f, scenes_of(f)) for f in files]
    out = []
    for a in args:
        name, _, sc = a.partition(":")
        f = r / (name if name.endswith(".py") else name + ".py")
        if not f.exists():
            sys.exit(f"ファイルがありません: {f.name}")
        all_sc = scenes_of(f)
        want = sc.split(",") if sc else all_sc
        bad = [s for s in want if s not in all_sc]
        if bad:
            sys.exit(f"{f.name} にシーンがありません: {bad}（あるのは {all_sc}）")
        out.append((f, want))
    return out


def avail_mem_gb() -> float | None:
    """使える空きメモリ (GB). 取れなければ None."""
    try:
        if sys.platform.startswith("linux"):
            for l in open("/proc/meminfo"):
                if l.startswith("MemAvailable:"):
                    return int(l.split()[1]) / 2**20
        elif sys.platform == "darwin":
            out = subprocess.run(["vm_stat"], capture_output=True, text=True).stdout
            page = int(re.search(r"page size of (\d+)", out).group(1))
            free = sum(int(re.search(rf"{k}:\s+(\d+)", out).group(1)) for k in ("Pages free", "Pages inactive"))
            return free * page / 2**30
    except Exception:
        return None
    return None


def run_manim(r: Path, f: Path, scene: str, q: str, dry: bool, voice: bool) -> tuple[str, int, str]:
    env = dict(os.environ, LECANIM_ROOT=str(r))
    if not voice:
        env["VOICE"] = "0"
    logd = r / "logs"
    logd.mkdir(exist_ok=True)
    # 並列実行で同じ数式・文字を同じファイルに同時に書いて壊れるのを防ぐため，シーンごとにキャッシュを分ける
    cfg = logd / f"{scene}.manim.cfg"
    cfg.write_text(f"[CLI]\ntex_dir = {{media_dir}}/Tex/{scene}\ntext_dir = {{media_dir}}/texts/{scene}\n")
    # シーン別のキャッシュは共有キャッシュからハードリンクで種をまき，終了後に新しいファイルだけ共有へ戻す
    # （完成したファイルだけをやり取りするので並列でも壊れない．同じ数式を何度も LaTeX にかけずに済む）
    shared = [(r / "media" / "Tex" / "_shared", r / "media" / "Tex" / scene),
              (r / "media" / "texts" / "_shared", r / "media" / "texts" / scene)]
    for sh, own in shared:
        if own.is_dir():   # 中断などで残った空のファイルは作り直させる（共有へ戻すと全シーンが ParseError になる）
            for c in own.iterdir():
                if c.is_file() and c.stat().st_size == 0:
                    c.unlink()
        _link_missing(sh, own)
    cmd = [sys.executable, "-m", "manim", f"-q{q}", "--disable_caching", "--config_file", str(cfg)]
    if dry:
        cmd.append("--dry_run")
    cmd += [f.name, scene]
    p = subprocess.run(cmd, cwd=r, env=env, capture_output=True, text=True)
    log = p.stdout + p.stderr
    if p.returncode in (-9, 137):
        log += "\n[lecanim] プロセスが強制終了されました（メモリ不足の可能性．[render] min_free_gb を上げるか並列数を下げる）\n"
    (logd / f"{scene}.{'dry' if dry else q}.log").write_text(log)
    if p.returncode == 0:
        for sh, own in shared:
            _link_missing(own, sh)
    return scene, p.returncode, log


def _link_missing(src: Path, dst: Path) -> None:
    if not src.is_dir():
        return
    dst.mkdir(parents=True, exist_ok=True)
    for f in src.iterdir():
        t = dst / f.name
        if f.is_file() and f.stat().st_size > 0 and not t.exists():
            try:
                os.link(f, t)
            except OSError:
                try:
                    shutil.copy2(f, t)
                except OSError:
                    pass


def run_many(r: Path, jobs_list, q, dry, voice, jobs):
    """最大 jobs 並列．ただし空きメモリが [render] min_free_gb 未満の間は次のシーンを起動しない."""
    import threading
    import time
    rcfg = load(r)["render"]
    min_free = float(rcfg.get("min_free_gb", 0 if dry else 4.0))
    if not dry:
        # レンダリングは起動直後は小さく，数分かけて 1 本あたり数 GB まで育つ．起動時の空きだけ見ると
        # 一斉に起動して後から OOM になるので，1 本あたりの見込み (mem_per_job_gb) で並列数を先に絞る
        per_job = float(rcfg.get("mem_per_job_gb", 4.0))
        mem0 = avail_mem_gb()
        if mem0 is not None and per_job > 0:
            cap = max(1, int(mem0 // per_job))
            if cap < jobs:
                print(f"  並列数を {jobs} → {cap} に制限（空きメモリ {mem0:.1f}GB ÷ 1本あたり {per_job:.1f}GB）")
                jobs = cap
    results: dict[int, tuple[str, int, str]] = {}
    running: dict[int, threading.Thread] = {}

    def work(i, f, s):
        results[i] = run_manim(r, f, s, q, dry, voice)

    for i, (f, s) in enumerate(jobs_list):
        while True:
            running = {k: t for k, t in running.items() if t.is_alive()}
            mem = avail_mem_gb()
            if len(running) < jobs and (not running or mem is None or mem >= min_free):
                break
            time.sleep(2)
        t = threading.Thread(target=work, args=(i, f, s))
        t.start()
        running[i] = t
        time.sleep(3 if not dry else 0)   # 起動直後はメモリを食う前なので，少し待ってから次を判断する
    for t in running.values():
        t.join()
    out = []
    for i, (f, s) in enumerate(jobs_list):
        scene, code, log = results[i]
        if code != 0 and jobs > 1:
            # 並列時の一時的な失敗（キャッシュ競合・メモリ不足）に備えて，1回だけ単独で再実行
            scene, code, log = run_manim(r, f, s, q, dry, voice)
        qa = [l for l in log.splitlines() if l.startswith("[QA]")]
        mark = "ok " if code == 0 else "ERR"
        print(f"  {mark} {scene}  " + " / ".join(x.split(": ", 1)[-1] for x in qa))
        if code != 0:
            err = [l for l in log.splitlines() if re.search(r"Error|error:|強制終了|Unavailable", l)]
            print("      " + "\n      ".join(err[-4:]))
            print(f"      → logs/{scene}.{'dry' if dry else q}.log")
        out.append((scene, code))
    return out


def duration(p: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                         capture_output=True, text=True).stdout.strip()
    return float(out or 0)


def combine(r: Path, f: Path, q: str) -> Path | None:
    vdir = r / "media" / "videos" / f.stem / QDIR[q]
    parts = [vdir / f"{s}.mp4" for s in scenes_of(f) if (vdir / f"{s}.mp4").exists()]
    if not parts:
        return None
    lst = r / "logs" / f"{f.stem}.concat.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts))
    out = r / "media" / "videos" / f.stem / f"{f.stem}_{QDIR[q]}.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy",
                    str(out)], check=True)
    return out


# ---------------------------------------------------------------- commands
def cmd_new(a):
    dst = Path(a.path).resolve()
    if (dst / "lecanim.toml").exists():
        sys.exit(f"既にプロジェクトがあります: {dst}")
    dst.mkdir(parents=True, exist_ok=True)
    lib = Path(__file__).resolve().parents[2]
    if (lib / "pyproject.toml").exists():   # clone したソースから使っている → そのソースを editable で参照
        dep = f'lecanim = {{ path = "{lib}", editable = true }}'
        docs = str(lib / "docs")
    else:                                    # git からインストールした → 同じリポジトリを参照
        dep = f'lecanim = {{ git = "{REPO_URL}" }}'
        docs = f"{REPO_URL}/tree/main/docs"
    subs = {"{{COURSE}}": a.course, "{{SERIES}}": a.series or a.course, "{{LECANIM_DEP}}": dep, "{{DOCS}}": docs,
            "{{NAME}}": re.sub(r"[^a-z0-9-]", "-", dst.name.lower()) or "lecture-anim",
            "{{LECANIM_PATH}}": str(lib)}
    for src in TEMPLATES.rglob("*"):
        if src.is_dir() or src.name.endswith(".pyc"):
            continue
        rel = src.relative_to(TEMPLATES)
        out = dst / str(rel).replace("_dot_", ".")
        out.parent.mkdir(parents=True, exist_ok=True)
        t = src.read_text()
        for k, v in subs.items():
            t = t.replace(k, v)
        out.write_text(t)
    for d in ["materials", "youtube"]:
        (dst / d).mkdir(exist_ok=True)
    print(f"作成しました: {dst}")
    if shutil.which("uv"):
        subprocess.run(["uv", "sync"], cwd=dst)
    print("次: cd してから `uv run lecanim pdf <ノート.pdf>` → lecture1.py を書く → `uv run lecanim beats`")


def cmd_info(a):
    lib = Path(__file__).resolve().parents[2]
    src = lib if (lib / "pyproject.toml").exists() else None
    print(f"lecanim パッケージ: {Path(__file__).resolve().parent}")
    print(f"ドキュメント: {src / 'docs' if src else REPO_URL + '/tree/main/docs'}")
    print("  WORKFLOW.md（手順）, STYLE.md（演出・説明・台本の原則）, API.md（API）")


def cmd_voice(a):
    cfg = load(find_root())
    url = cfg["voice"]["url"]
    if a.action == "up":
        if not shutil.which("docker"):
            sys.exit("docker がありません")
        if subprocess.run(["docker", "info"], capture_output=True).returncode != 0 and sys.platform == "darwin":
            subprocess.run(["open", "-a", "Docker"])
            print("Docker Desktop を起動中…")
            import time
            for _ in range(60):
                if subprocess.run(["docker", "info"], capture_output=True).returncode == 0:
                    break
                time.sleep(2)
        names = subprocess.run(["docker", "ps", "-a", "--format", "{{.Names}}"], capture_output=True, text=True).stdout
        if "voicevox" in names.split():
            subprocess.run(["docker", "start", "voicevox"])
        else:
            subprocess.run(["docker", "run", "-d", "--name", "voicevox", "--restart", "unless-stopped", "-p",
                            "127.0.0.1:50021:50021", "voicevox/voicevox_engine:cpu-latest"], check=True)
    import time
    import urllib.request
    for _ in range(30 if a.action == "up" else 1):
        try:
            with urllib.request.urlopen(f"{url}/version", timeout=2) as res:
                print(f"VOICEVOX OK: {url}  version {res.read().decode()}")
                return
        except Exception:
            time.sleep(2)
    sys.exit(f"VOICEVOX に接続できません: {url}（`lecanim voice up` で起動）")


def cmd_pdf(a):
    r = find_root()
    out = r / "materials"
    out.mkdir(exist_ok=True)
    for pdf in a.pdfs:
        pdf = Path(pdf).resolve()
        stem = pdf.stem.replace(" ", "_")
        subprocess.run(["pdftotext", "-layout", str(pdf), str(out / f"{stem}.txt")], check=True)
        tmp = out / f".{stem}_pages"
        tmp.mkdir(exist_ok=True)
        subprocess.run(["pdftoppm", "-r", "40", "-png", str(pdf), str(tmp / "p")], check=True)
        from PIL import Image
        ims = [Image.open(p) for p in sorted(tmp.glob("p-*.png"))]
        w, h = ims[0].size
        cols = 6
        sheet = Image.new("RGB", (w * cols, h * ((len(ims) + cols - 1) // cols)), "white")
        for i, im in enumerate(ims):
            sheet.paste(im, ((i % cols) * w, (i // cols) * h))
        sheet.save(out / f"{stem}_sheet.png")
        shutil.rmtree(tmp)
        print(f"{pdf.name}: {len(ims)} ページ → materials/{stem}.txt, materials/{stem}_sheet.png")


def cmd_scenes(a):
    r = root()
    for f, sc in targets(r, a.targets):
        print(f"{f.name}: {' '.join(sc)}")


def _narr_hits(script, kind, text):
    return [i for i, (k, _) in enumerate(script)
            if k.partition(":")[0] == kind and text.startswith(k.partition(":")[2])]


def cmd_beats(a):
    r = root()
    tl = targets(r, a.targets)
    jobs = [(f, s) for f, ss in tl for s in ss]
    print(f"場面を書き出し中（{len(jobs)} シーン, 音声なし）")
    for f_ in (r / "transcripts").glob("*.beats.txt") if (r / "transcripts").exists() else []:
        if any(f_.name == f"{s}.beats.txt" for _, s in jobs):
            f_.unlink()
    res = dict(run_many(r, jobs, "l", True, False, a.jobs))
    failed = [s for s, c in res.items() if c]
    # 台本の不足分
    os.environ["LECANIM_ROOT"] = str(r)
    from importlib import reload

    from . import narration
    reload(narration)
    scripts = narration.load_scripts()
    n_missing = 0
    for f, ss in tl:
        todo = []
        for s in ss:
            bf = r / "transcripts" / f"{s}.beats.txt"
            if not bf.exists():
                continue  # 失敗したシーン (最後にまとめて報告)
            beats = [b for b in bf.read_text().splitlines() if b]
            script = scripts.get(s)
            missing = []
            for b in beats:
                kind, _, text = b.partition(":")
                if script is None or not _narr_hits(script, kind, text):
                    missing.append((kind, text))
            if missing:
                todo.append((s, script is None, missing))
        tf = r / "narration" / f"_todo_{f.stem}.py"
        bad = [s for s in ss if s in failed]
        if bad:
            print(f"{f.name}: エラーで場面を取れなかったシーン {bad}（logs/ を確認）")
        if not todo:
            if tf.exists():
                tf.unlink()
            if not bad:
                print(f"{f.name}: 台本はすべての場面をカバーしています")
            continue
        lines = ['"""台本の不足分（lecanim beats が生成）. 読み上げ文を書いて narration/'
                 f'{f.stem}.py の該当シーンへ移す. このファイル自体は読み込まれない."""', "", "TODO = {"]
        for s, new, miss in todo:
            lines.append(f'    "{s}": [  # {"台本なし（新規シーン）" if new else f"{len(miss)} 場面が未対応"}')
            for kind, text in miss:
                key = f"{kind}:{text[:20]}" if text else f"{kind}:"
                lines.append(f"        ({json.dumps(key, ensure_ascii=False)}, \"\"),  # 画面: {text}")
            lines.append("    ],")
        lines.append("}")
        tf.parent.mkdir(exist_ok=True)
        tf.write_text("\n".join(lines) + "\n")
        n = sum(len(m) for _, _, m in todo)
        print(f"{f.name}: 台本の不足 {n} 場面 → narration/{tf.name}")
        n_missing += n
    qa_n = 0
    for _, ss in tl:
        for s in ss:
            q = r / "qa_reports" / f"{s}.txt"
            if q.exists() and q.read_text().strip():
                qa_n += len(q.read_text().strip().splitlines())
                if a.strict:
                    print(f"  QA {s}:\n    " + q.read_text().strip().replace("\n", "\n    "))
    if failed or (a.strict and (n_missing or qa_n)):
        if a.strict:
            print(f"strict: 失敗 {len(failed)} シーン / 台本の不足 {n_missing} 場面 / レイアウト警告 {qa_n} 件")
        sys.exit(1)


def cmd_render(a):
    r = root()
    if a.remote:
        return render_remote(r, a)
    tl = targets(r, a.targets)
    voice = not a.no_voice
    if voice:
        from . import voice as v
        if not v.available():
            print("※ VOICEVOX に接続できません．合成済み（キャッシュ）の台本はそのまま使えますが，"
                  "未合成の台本があるシーンは失敗します（`lecanim voice up`．無音でよければ --no-voice）")
    jobs = [(f, s) for f, ss in tl for s in ss]
    print(f"レンダリング（{len(jobs)} シーン, -q{a.q}, 並列 {a.jobs}）")
    res = run_many(r, jobs, a.q, False, voice, a.jobs)
    for f, _ in tl:
        out = combine(r, f, a.q)
        if out:
            d = duration(out)
            print(f"  → {out.relative_to(r)}  ({int(d // 60)}分{int(d % 60):02d}秒)")
    if any(c for _, c in res):
        sys.exit(1)


def cmd_check(a):
    r = root()
    os.environ["LECANIM_ROOT"] = str(r)
    from . import voice as v
    tl = targets(r, a.targets)
    bad = 0
    for f, ss in tl:
        for s in ss:
            msgs = []
            qa = r / "qa_reports" / f"{s}.txt"
            if qa.exists():
                msgs += [f"QA  {l.strip()}" for l in qa.read_text().splitlines() if l.strip()]
            tr = r / "transcripts" / f"{s}.txt"
            if tr.exists():
                lines = tr.read_text().splitlines()
                for i, l in enumerate(lines):
                    if l.strip().startswith("⤷"):
                        for pat in v.SUSPECT:
                            if pat in l:
                                msgs.append(f"読み  『{pat}』 in: {lines[i - 1][:40]}")
            vid = r / "media" / "videos" / f.stem / QDIR[a.q] / f"{s}.mp4"
            if vid.exists():
                out = subprocess.run(["ffmpeg", "-i", str(vid), "-af", f"silencedetect=n=-40dB:d={a.silence}", "-f",
                                      "null", "-"], capture_output=True, text=True).stderr
                for m in re.finditer(r"silence_end: ([\d.]+) \| silence_duration: ([\d.]+)", out):
                    end, dur = float(m.group(1)), float(m.group(2))
                    msgs.append(f"無音  {end - dur:6.1f}s から {dur:.1f} 秒")
            status = "ok" if not msgs else f"{len(msgs)} 件"
            print(f"{f.stem}:{s}  {status}")
            for m in msgs:
                print("    " + m)
            bad += len(msgs)
    print(f"\n合計 {bad} 件（無音は字幕なしの演出区間なら問題なし．読みの誤りは yomi.toml に追加）")


def cmd_sheet(a):
    r = root()
    f = r / (a.file if a.file.endswith(".py") else a.file + ".py")
    vid = r / "media" / "videos" / f.stem / QDIR[a.q] / f"{a.scene}.mp4"
    if not vid.exists():
        sys.exit(f"動画がありません: {vid}")
    d = duration(vid)
    out = r / "qa_frames" / a.scene
    out.mkdir(parents=True, exist_ok=True)
    for p in out.glob("*.png"):
        p.unlink()
    for i in range(a.n):
        t = d * (i + 0.5) / a.n
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{t:.2f}", "-i", str(vid), "-frames:v", "1",
                        "-vf", "scale=640:-1", str(out / f"{i:02d}.png")], check=True)
    sheet = r / "qa_frames" / f"{a.scene}_sheet.png"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-pattern_type", "glob", "-i", str(out / "*.png"), "-vf",
                    f"tile=3x{(a.n + 2) // 3}", "-frames:v", "1", str(sheet)], check=True)
    print(sheet.relative_to(r))


def cmd_youtube(a):
    r = root()
    cfg = load(r)
    yt = r / "youtube"
    yt.mkdir(exist_ok=True)
    lec_cfg = cfg["project"].get("lectures", {})
    footer = cfg["youtube"].get("footer", "")
    from . import voice as v
    for f in lecture_files(r):
        info = lec_cfg.get(f.stem, {})
        t = 0.0
        ch = []
        for s in scenes_of(f):
            vid = r / "media" / "videos" / f.stem / QDIR[a.q] / f"{s}.mp4"
            if not vid.exists():
                continue
            meta = r / "transcripts" / f"{s}.meta.json"
            name = json.loads(meta.read_text()).get("chapter", s) if meta.exists() else s
            ch.append((t, name.replace("$", "")))
            t += duration(vid)
        if not ch:
            continue
        stamp = lambda x: f"{int(x // 3600)}:{int(x % 3600 // 60):02d}:{int(x % 60):02d}" if x >= 3600 \
            else f"{int(x // 60)}:{int(x % 60):02d}"
        title = info.get("title", f"{f.stem}【{cfg['project']['series']}】")
        body = [title, "", info.get("summary", "").strip(), ""]
        if len(ch) >= 3:
            body += [f"{stamp(x)} {n}" for x, n in ch] + [""]
        body += [f"【音声】{v.credit()}"]
        if footer:
            body += [footer.strip()]
        (yt / f"{f.stem}.txt").write_text("\n".join(body) + "\n")
        print(f"youtube/{f.stem}.txt  ({len(ch)} チャプター{'．3未満なので省略' if len(ch) < 3 else ''})")


# ---------------------------------------------------------------- remote
APT = ("sudo apt-get update && sudo apt-get install -y ffmpeg dvisvgm texlive texlive-latex-extra "
       "texlive-latex-recommended texlive-fonts-extra texlive-science tipa cm-super "
       "libcairo2-dev libpango1.0-dev pkg-config python3-dev build-essential fonts-noto-cjk rsync")


def _rcfg(r: Path) -> dict:
    c = load(r)["remote"]
    if not c.get("host"):
        sys.exit("lecanim.toml の [remote] host が未設定です（~/.ssh/config のホスト名を書く．docs/WORKFLOW.md 参照）")
    return {"host": c["host"], "root": c["root"].removeprefix("~/").rstrip("/"), "jobs": int(c["jobs"])}


def _ssh(host: str, cmd: str, tunnel: str | None = None, capture=False) -> subprocess.CompletedProcess:
    args = ["ssh", "-o", "ConnectTimeout=10", "-o", "ServerAliveInterval=30"]
    if tunnel:
        args += ["-o", "ExitOnForwardFailure=yes", "-R", tunnel]
    args += [host, f"export PATH=$HOME/.local/bin:$PATH; {cmd}"]
    return subprocess.run(args, capture_output=capture, text=True)


def _rsync(src: str, dst: str, excludes=(), delete=False) -> None:
    args = ["rsync", "-az", "--human-readable"]
    if delete:
        args.append("--delete")
    for e in excludes:
        args += ["--exclude", e]
    subprocess.run(args + [src, dst], check=True)


def _effective_font(r: Path) -> str:
    return load(r)["style"]["jp_font"]


def _remote_missing(host: str, font: str) -> list[str]:
    chk = ("for c in ffmpeg latex dvisvgm pkg-config rsync uv; do command -v $c >/dev/null || echo MISSING:$c; done; "
           "pkg-config --exists cairo pangocairo 2>/dev/null || echo MISSING:cairo-dev; "
           f"fc-list | grep -qi '{font or 'Noto Sans CJK JP'}' || echo MISSING:font")
    out = _ssh(host, chk, capture=True)
    if out.returncode != 0:
        sys.exit(f"{host} に接続できません: {out.stderr.strip()}")
    return [l.split(":", 1)[1] for l in out.stdout.split() if l.startswith("MISSING:")]


def _sync_up(r: Path, rc: dict) -> str:
    host, root_ = rc["host"], rc["root"]
    lib = Path(__file__).resolve().parents[2]
    name = "-".join(r.parts[-3:])
    rproj = f"{root_}/projects/{name}"
    _ssh(host, f"mkdir -p {root_}/projects/{name} .cache/lecanim/voice")
    if (lib / "pyproject.toml").exists():   # ソースから使っている → そのソースを送って editable で入れる
        _rsync(f"{lib}/", f"{host}:{root_}/lecanim/", excludes=[".venv", "__pycache__", "*.pyc", "uv.lock"],
               delete=True)
        spec = f"-e $HOME/{root_}/lecanim"
    else:                                   # git などから入れている → 同じ版をリモートでも入れる
        spec = f"'{_installed_spec()}'"
    _rsync(f"{r}/", f"{host}:{rproj}/", delete=True,
           excludes=[".venv", "__pycache__", "media", "logs", "qa_frames", "qa_reports", "transcripts", "youtube",
                     "materials", "uv.lock"])
    voice = Path(os.environ.get("LECANIM_CACHE", Path.home() / ".cache" / "lecanim")) / "voice"
    if voice.exists():
        _rsync(f"{voice}/", f"{host}:.cache/lecanim/voice/")
    p = _ssh(host, f"cd {rproj} && (test -x .venv/bin/python || uv venv -q --python 3.13 .venv) && "
                   f"uv pip install -q --python .venv/bin/python {spec}")
    if p.returncode != 0:
        sys.exit("リモートの環境構築に失敗しました（lecanim remote setup で確認）")
    return rproj


def _installed_spec() -> str:
    """手元に入っている lecanim と同じ版を指す pip の指定（git の固定 commit など）."""
    import importlib.metadata as md
    info = json.loads(md.distribution("lecanim").read_text("direct_url.json") or "{}")
    vcs = info.get("vcs_info", {})
    if vcs.get("vcs") == "git":
        return f"lecanim @ git+{info['url']}@{vcs['commit_id']}"
    sys.exit("lecanim の入手元が分かりません（ソースの clone か git から入れてください）")


def _sync_down(r: Path, rc: dict, rproj: str) -> None:
    host = rc["host"]
    (r / "media" / "videos").mkdir(parents=True, exist_ok=True)
    _rsync(f"{host}:{rproj}/media/videos/", f"{r}/media/videos/", excludes=["partial_movie_files"])
    for d in ["qa_reports", "transcripts", "logs"]:
        (r / d).mkdir(exist_ok=True)
        _rsync(f"{host}:{rproj}/{d}/", f"{r}/{d}/")
    voice = Path(os.environ.get("LECANIM_CACHE", Path.home() / ".cache" / "lecanim")) / "voice"
    voice.mkdir(parents=True, exist_ok=True)
    _rsync(f"{host}:.cache/lecanim/voice/", f"{voice}/")


def cmd_remote(a):
    r = root()
    rc = _rcfg(r)
    font = _effective_font(r)
    miss = _remote_missing(rc["host"], font)
    print(f"リモート: {rc['host']}  (~/{rc['root']}, 並列 {rc['jobs']})")
    if not font:
        print("※ lecanim.toml の [style] jp_font が未設定です．macOS（Hiragino）と Linux（Noto）で字形が変わるため，"
              "--remote には両方にあるフォント（例: Noto Sans CJK JP）の指定が必要です")
    sysmiss = [m for m in miss if m not in ("uv",)]
    if sysmiss:
        print(f"足りないもの: {', '.join(sysmiss)}")
        print(f"リモートで次を実行してください（sudo のパスワードが必要）:\n  ssh -t {rc['host']} '{APT}'")
        if "font" in sysmiss and font and "noto" not in font.lower():
            print(f"  フォント『{font}』もリモートに入れてください")
    if "uv" in miss:
        print(f"uv がありません: ssh {rc['host']} 'curl -LsSf https://astral.sh/uv/install.sh | sh'")
    if a.action == "status" or miss:
        if not miss:
            print("準備 OK")
        return
    rproj = _sync_up(r, rc)
    p = _ssh(rc["host"], f"cd {rproj} && .venv/bin/python -c 'import lecanim, manim; print(\"lecanim OK\", manim.__version__)'",
             capture=True)
    print(p.stdout.strip() or p.stderr.strip()[-400:])


def render_remote(r: Path, a) -> None:
    rc = _rcfg(r)
    font = _effective_font(r)
    if not font and not a.allow_font_mismatch:
        sys.exit("lecanim.toml の [style] jp_font をローカルとリモートの両方にあるフォント（例: Noto Sans CJK JP）に"
                 "設定してください（字形の違いでレイアウトが変わるため）．無視するなら --allow-font-mismatch")
    miss = _remote_missing(rc["host"], font)
    if miss:
        sys.exit(f"リモートの準備が足りません: {miss}（lecanim remote setup）")
    voice_on = not a.no_voice
    tunnel = None
    if voice_on:
        from . import voice as v
        if not v.available():
            print("※ ローカルの VOICEVOX に接続できません．合成済みの台本はキャッシュを使います（未合成があると失敗）")
        port = load(r)["voice"]["url"].rsplit(":", 1)[-1].strip("/")
        tunnel = f"{port}:127.0.0.1:{port}"     # リモートからもローカルの VOICEVOX を使う
    print(f"同期中 → {rc['host']}")
    rproj = _sync_up(r, rc)
    tg = " ".join(a.targets) or "all"
    jobs = a.jobs_remote or rc["jobs"]
    print(f"リモートでレンダリング（-q{a.q}, 並列 {jobs}）")
    cmd = f"cd {rproj} && .venv/bin/lecanim render {tg} -q {a.q} -j {jobs}" + (" --no-voice" if not voice_on else "")
    p = _ssh(rc["host"], cmd, tunnel=tunnel)
    print("結果を取り込み中")
    _sync_down(r, rc, rproj)
    for f, _ in targets(r, a.targets):
        out = combine(r, f, a.q)
        if out:
            d = duration(out)
            print(f"  → {out.relative_to(r)}  ({int(d // 60)}分{int(d % 60):02d}秒)")
    if p.returncode != 0:
        sys.exit(1)


def main(argv=None):
    p = argparse.ArgumentParser(prog="lecanim", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("new")
    s.add_argument("path")
    s.add_argument("--course", required=True)
    s.add_argument("--series", default="")
    s.set_defaults(fn=cmd_new)
    s = sp.add_parser("info")
    s.set_defaults(fn=cmd_info)
    s = sp.add_parser("voice")
    s.add_argument("action", choices=["up", "status"])
    s.set_defaults(fn=cmd_voice)
    s = sp.add_parser("pdf")
    s.add_argument("pdfs", nargs="+")
    s.set_defaults(fn=cmd_pdf)
    s = sp.add_parser("scenes")
    s.add_argument("targets", nargs="*")
    s.set_defaults(fn=cmd_scenes)
    s = sp.add_parser("beats")
    s.add_argument("targets", nargs="*")
    s.add_argument("--strict", action="store_true", help="台本の不足・レイアウト警告があれば失敗（CI 用）")
    s.add_argument("-j", "--jobs", type=int, default=load(find_root())["render"]["jobs"])
    s.set_defaults(fn=cmd_beats)
    s = sp.add_parser("render")
    s.add_argument("targets", nargs="*")
    s.add_argument("-q", choices=list(QDIR), default="l")
    s.add_argument("-j", "--jobs", type=int, default=load(find_root())["render"]["jobs"])
    s.add_argument("--no-voice", action="store_true")
    s.add_argument("--remote", action="store_true", help="lecanim.toml の [remote] のホストでレンダリング")
    s.add_argument("--jobs-remote", type=int, default=0, help="リモートの並列数（既定は [remote] jobs）")
    s.add_argument("--allow-font-mismatch", action="store_true")
    s.set_defaults(fn=cmd_render)
    s = sp.add_parser("check")
    s.add_argument("targets", nargs="*")
    s.add_argument("-q", choices=list(QDIR), default="l")
    s.add_argument("--silence", type=float, default=8.0, help="これ以上の無音を報告（秒）")
    s.set_defaults(fn=cmd_check)
    s = sp.add_parser("sheet")
    s.add_argument("file")
    s.add_argument("scene")
    s.add_argument("-n", type=int, default=24)
    s.add_argument("-q", choices=list(QDIR), default="l")
    s.set_defaults(fn=cmd_sheet)
    s = sp.add_parser("remote")
    s.add_argument("action", choices=["setup", "status"])
    s.set_defaults(fn=cmd_remote)
    s = sp.add_parser("youtube")
    s.add_argument("-q", choices=list(QDIR), default="h")
    s.set_defaults(fn=cmd_youtube)
    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
