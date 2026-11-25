# build.py — Cloud Functions 배포 묶음(zip) 만들기 (작업 58 ①, 작성: 미리)
#
# 실행(저장소 맨 위에서):  python -X utf8 functions/cloud/build.py
#   1. origin/main을 받아(fetch) 지금 코드가 main 최신을 포함하는지 본다. 아니면 멈춘다(--skip-git-check로 건너뜀).
#      다른 대화창의 기능 수정이 병합되면 main을 받고 다시 묶어 배포해야 한다.
#   2. zip 내용: functions/cloud/main.py → __main__.py, functions/*.py(test_·eval_ 제외), data/*.json(data/runtime 제외),
#      docs/prompts/*.txt, lib/(functions/requirements.txt를 리눅스 x86_64 · Python 3.13용 wheel로 설치)
#   3. 검사: .env·logs·data/runtime·*.jsonl이 들어가지 않았는지, .env와 환경변수의 키·비번 값이 zip 안 어떤 파일에도 없는지.
#      걸리면 zip을 지우고 멈춘다(값은 출력하지 않는다).
#   결과: 다운로드 폴더의 vcc-functions.zip (저장소 밖 — 커밋되지 않게). 경로를 출력한다.
#   업로드: NCP 콘솔 > Cloud Functions > 액션 > 코드 > 파일 업로드(zip), 런타임 python:3.13.
#
# 옵션: --python 3.13  --skip-git-check  --fresh(lib 다시 설치)  --out <zip 경로>
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import paths  # noqa: E402

ROOT = paths.ROOT
FORBIDDEN = (".env", "/logs/", "data/runtime", ".jsonl", "settings.local.json")
SECRET_NAMES = ("KEY", "PW", "SECRET", "TOKEN", "PASSWORD")


def git(*a):
    return subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True, encoding="utf-8")


def check_git():
    if git("fetch", "-q", "origin").returncode != 0:
        sys.exit("멈춤: git fetch 실패 — 네트워크를 확인하세요")
    if git("merge-base", "--is-ancestor", "origin/main", "HEAD").returncode != 0:
        sys.exit("멈춤: 지금 코드에 origin/main 최신이 없습니다. main을 받고(git pull 또는 merge origin/main) 다시 실행하세요")
    dirty = git("status", "--porcelain", "--", "functions", "data", "docs/prompts").stdout.strip()
    if dirty:
        print("주의: 커밋하지 않은 변경이 묶음에 들어갑니다:\n" + dirty)


def pinned_requirements():
    """requirements.txt의 패키지를 이 PC에 설치된 버전으로 고정한다(로컬에서 시험한 버전 그대로 배포)."""
    from importlib.metadata import PackageNotFoundError, version
    out = []
    for line in (ROOT / "functions" / "requirements.txt").read_text(encoding="utf-8").splitlines():
        name = line.split("#")[0].strip()
        if not name:
            continue
        if re.fullmatch(r"[A-Za-z0-9_.\-]+", name):
            try:
                name = f"{name}=={version(name)}"
            except PackageNotFoundError:
                pass
        out.append(name)
    return out


def install_lib(lib, py, fresh):
    mark = lib / ".python-version"
    want = py + " " + " ".join(pinned_requirements())
    if not fresh and mark.exists() and mark.read_text() == want:
        print(f"의존성: 이전에 받은 것 사용 ({lib})")
        return
    shutil.rmtree(lib, ignore_errors=True)
    cmd = [sys.executable, "-m", "pip", "install", "-q", "--target", str(lib),
           "--platform", "manylinux2014_x86_64", "--implementation", "cp", "--python-version", py,
           "--only-binary=:all:", *pinned_requirements()]
    print("의존성 받는 중: " + " ".join(cmd[3:]))
    if subprocess.run(cmd).returncode != 0:
        sys.exit("멈춤: pip install 실패")
    mark.write_text(want)


def members(lib):
    """(zip 안 경로, 원본 파일) 목록."""
    out = [("__main__.py", HERE / "main.py")]
    for p in sorted((ROOT / "functions").glob("*.py")):
        if not p.name.startswith(("test_", "eval_")):
            out.append((f"functions/{p.name}", p))
    for p in sorted((ROOT / "data").glob("*.json")):   # 맨 위만 — data/runtime/은 하위 폴더라 들어가지 않는다
        out.append((f"data/{p.name}", p))
    for p in sorted((ROOT / "docs" / "prompts").glob("*.txt")):
        out.append((f"docs/prompts/{p.name}", p))
    for p in sorted(lib.rglob("*")):
        rel = p.relative_to(lib).as_posix()
        if p.is_file() and "__pycache__" not in rel and not rel.startswith("bin/") and rel != ".python-version":
            out.append((f"lib/{rel}", p))
    return out


def _is_secret_name(k):
    """CLAUDE_KEY·VCC_LOGIN_PW·NCP_OS_SECRET_KEY처럼 밑줄로 나뉜 낱말이 KEY·PW 등인 이름(OLDPWD 같은 셸 변수는 제외)."""
    return any(w in SECRET_NAMES for w in re.split(r"[_\W]+", k.upper()))


def _add(vals, v):
    if len(v) >= 8:
        vals.add(v)
    try:   # VCC_LOGIN_PW는 {학번: 비번} JSON — 안의 비번 하나하나도 본다
        inner = json.loads(v)
    except ValueError:
        return
    if isinstance(inner, dict):
        for x in inner.values():
            if isinstance(x, str) and len(x) >= 4:
                vals.add(x)


def secret_values():
    """.env와 환경변수에서 키·비번 값. 값은 출력하지 않고 비교에만 쓴다."""
    vals = set()
    for path in paths.env_files():
        try:
            lines = path.read_text(encoding="utf-8-sig").splitlines()
        except OSError:
            continue
        for line in lines:
            k, sep, v = line.strip().partition("=")
            v = v.strip().strip('"').strip("'")
            if sep and _is_secret_name(k.strip()):
                _add(vals, v)
    for k, v in os.environ.items():
        if _is_secret_name(k):
            _add(vals, v)
    return [v.encode("utf-8") for v in vals]


def check(items):
    bad = [name for name, _ in items if any(f in "/" + name for f in FORBIDDEN)]
    if bad:
        return "들어가면 안 되는 파일: " + ", ".join(bad[:5])
    secrets = secret_values()
    for name, src in items:
        if name.startswith("lib/"):
            continue   # 받은 패키지는 우리 키를 담을 수 없다(검사 시간 절약)
        data = src.read_bytes()
        if any(s in data for s in secrets):
            return f"키·비번 값이 들어 있는 파일: {name} (값은 표시하지 않음)"
    return None


def main():
    ap = argparse.ArgumentParser(description="Cloud Functions 배포 zip 만들기")
    ap.add_argument("--python", default="3.13")
    ap.add_argument("--skip-git-check", action="store_true")
    ap.add_argument("--fresh", action="store_true")
    ap.add_argument("--out", default=str(Path.home() / "Downloads" / "vcc-functions.zip"))   # 콘솔 「파일 업로드」에서 찾기 쉽게
    a = ap.parse_args()

    if not a.skip_git_check:
        check_git()
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    lib = Path(tempfile.gettempdir()) / "vcc-cloud" / f"lib-py{a.python}"   # 받은 패키지는 임시 폴더에(다시 받지 않게)
    lib.parent.mkdir(parents=True, exist_ok=True)
    install_lib(lib, a.python, a.fresh)
    items = members(lib)
    problem = check(items)
    if problem:
        sys.exit("멈춤: " + problem)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for name, src in items:
            z.write(src, name)
    with zipfile.ZipFile(out) as z:   # 만든 뒤 한 번 더 이름 검사
        names = z.namelist()
    if any(any(f in "/" + n for f in FORBIDDEN) for n in names):
        out.unlink()
        sys.exit("멈춤: zip 안에 금지 파일 — 지웠습니다")
    own = sum(1 for n in names if not n.startswith("lib/"))
    print(f"완료: {out}  ({out.stat().st_size / 1e6:.1f}MB · 파일 {len(names)}개 중 우리 코드·데이터 {own}개)")
    print(f"HEAD {git('rev-parse', '--short', 'HEAD').stdout.strip()} · 런타임 python:{a.python}")


if __name__ == "__main__":
    main()
