# paths.py — 저장소 경로 한 곳 (11/21)
#
# 같은 PC에서 worktree(C:\dev\VCC-<작업>)로 작업하면 그 폴더에는 .env가 없고(커밋 안 함),
# 거기서 쌓인 로그·캐시는 폴더를 지울 때 함께 사라진다(11/21 작업 67·50의 AI 호출 기록이 그렇게 없어짐).
# 그래서 .env와 functions/logs는 항상 본 저장소(MAIN_ROOT, 보통 C:\dev\VCC)를 쓴다.
#   ROOT       이 코드가 있는 저장소(worktree일 수도 있음)
#   MAIN_ROOT  본 저장소. worktree면 .git 파일의 gitdir를 따라가 찾고, 아니면 ROOT와 같다.
#              NCP Cloud Functions처럼 .git이 없으면 ROOT.
#   LOGS       MAIN_ROOT/functions/logs (.gitignore 대상)
#   load_env() .env를 ROOT → MAIN_ROOT 순서로 읽어 환경변수에 넣는다. 이미 있는 환경변수는 덮지 않는다. 값은 출력하지 않는다.
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _main_root(root):
    git = root / ".git"
    try:
        if git.is_file():   # worktree: "gitdir: C:/dev/VCC/.git/worktrees/VCC-xx"
            text = git.read_text(encoding="utf-8").strip()
            if text.startswith("gitdir:"):
                gitdir = Path(text.split(":", 1)[1].strip())
                if gitdir.parent.name == "worktrees" and gitdir.parent.parent.name == ".git":
                    main = gitdir.parent.parent.parent
                    if main.is_dir():
                        return main
    except OSError:
        pass
    return root


MAIN_ROOT = _main_root(ROOT)
# Cloud Functions(작업 58)는 /tmp만 쓸 수 있어 진입점(functions/cloud/main.py)이 VCC_LOGS=/tmp/vcc-logs를 넣는다.
# 로컬·worktree는 VCC_LOGS가 없으므로 그대로 본 저장소의 functions/logs.
LOGS = Path(os.environ["VCC_LOGS"]) if os.environ.get("VCC_LOGS") else MAIN_ROOT / "functions" / "logs"


def env_files():
    files = [ROOT / ".env"]
    if MAIN_ROOT != ROOT:
        files.append(MAIN_ROOT / ".env")
    return files


def load_env():
    for path in env_files():
        try:
            lines = path.read_text(encoding="utf-8-sig").splitlines()
        except OSError:
            continue
        for line in lines:
            k, sep, v = line.strip().partition("=")
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if sep and k and v and not k.startswith("#") and k not in os.environ:
                os.environ[k] = v
