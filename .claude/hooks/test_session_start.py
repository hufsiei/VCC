# test_session_start.py — session_start.py(pull만 하는 hook) 시험 (11/25)
# 실행: python -X utf8 .claude/hooks/test_session_start.py
# 임시 저장소(원격 + 복제본)에서만 돈다. 실제 저장소·네트워크·알림을 건드리지 않는다.
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK_SRC = Path(__file__).resolve().parent / "session_start.py"
fails = []


def expect(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
       "GIT_COMMITTER_EMAIL": "t@t", "VCC_NO_NOTIFY": "1"}


def git(cwd, *args):
    r = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, encoding="utf-8", env=ENV)
    if r.returncode != 0:
        raise RuntimeError(f"git {args}: {r.stderr}")
    return r.stdout.strip()


tmp = Path(tempfile.mkdtemp())
origin, seed, repo, backup = tmp / "origin.git", tmp / "seed", tmp / "repo", tmp / "backup"
try:
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
    subprocess.run(["git", "clone", "-q", str(origin), str(seed)], check=True, capture_output=True)
    (seed / ".claude" / "hooks").mkdir(parents=True)
    shutil.copy(HOOK_SRC, seed / ".claude" / "hooks" / "session_start.py")
    (seed / "a.txt").write_text("1\n", encoding="utf-8")
    git(seed, "checkout", "-q", "-b", "main")
    git(seed, "add", "-A")
    git(seed, "commit", "-q", "-m", "init")
    git(seed, "push", "-q", "origin", "main")
    subprocess.run(["git", "clone", "-q", str(origin), str(repo)], check=True, capture_output=True)

    def run_hook():
        e = {**ENV, "CLAUDE_PROJECT_DIR": str(repo), "VCC_BACKUP_ROOT": str(backup)}
        r = subprocess.run([sys.executable, "-X", "utf8", str(repo / ".claude" / "hooks" / "session_start.py")],
                           capture_output=True, text=True, encoding="utf-8", env=e, stdin=subprocess.DEVNULL)
        return r.returncode, r.stdout.strip()

    def push_seed(name, text):
        (seed / name).write_text(text, encoding="utf-8")
        git(seed, "add", "-A")
        git(seed, "commit", "-q", "-m", f"add {name}")
        git(seed, "push", "-q", "origin", "main")

    # (a) 최신
    code, out = run_hook()
    expect("(a) 최신: 출력 없음", code == 0 and out == "")
    expect("core.hooksPath가 .githooks", git(repo, "config", "--local", "core.hooksPath") == ".githooks")

    # (b) 새 커밋
    push_seed("b.txt", "b\n")
    code, out = run_hook()
    expect("(b) 새 커밋: 출력 없음", code == 0 and out == "")
    expect("(b) 실제로 pull됨", (repo / "b.txt").exists())

    # (c) 미추적 충돌 → 백업 뒤 pull
    (repo / "shot.png").write_text("내 캡처", encoding="utf-8")
    push_seed("shot.png", "원격 파일")
    code, out = run_hook()
    saved = list(backup.rglob("shot.png"))
    expect("(c) 미추적 충돌: 출력 없음", code == 0 and out == "")
    expect("(c) 백업 폴더에 옮겨짐", len(saved) == 1 and saved[0].read_text(encoding="utf-8") == "내 캡처")
    expect("(c) 원격 파일이 들어옴", (repo / "shot.png").read_text(encoding="utf-8") == "원격 파일")

    # (d) 다른 브랜치
    git(repo, "checkout", "-q", "-b", "other")
    code, out = run_hook()
    msg = json.loads(out)["systemMessage"] if out else ""
    expect("(d) 다른 브랜치: 한 줄", code == 0 and msg.startswith("[VCC] pull 안 됨 — ") and "직접 pull하세요" in msg and "other" in msg)
    expect("(d) additionalContext에 지시", "첫 답변 맨 위" in (json.loads(out)["hookSpecificOutput"]["additionalContext"] if out else ""))
    git(repo, "checkout", "-q", "main")

    # (e) 고친 파일
    (repo / "a.txt").write_text("고침\n", encoding="utf-8")
    code, out = run_hook()
    msg = json.loads(out)["systemMessage"] if out else ""
    expect("(e) 고친 파일: 한 줄", code == 0 and msg.startswith("[VCC] pull 안 됨 — ") and "고친 파일" in msg and "직접 pull하세요" in msg)
    git(repo, "checkout", "-q", "--", "a.txt")

    # (f) 원격이 사라짐(네트워크 실패 대신)
    git(repo, "remote", "set-url", "origin", str(tmp / "없는 원격"))
    code, out = run_hook()
    expect("(f) pull 실패: 한 줄", code == 0 and "직접 pull하세요" in out)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print(f"\n{len(fails)} fail" if fails else "\nall ok")
sys.exit(1 if fails else 0)
