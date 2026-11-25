# session_start.py — Claude Code SessionStart hook (11/21 미리 개인용 → 11/24 팀 공용 → 11/25 pull만 남김)
#
# 저장소 .claude/settings.json에 등록돼 있어 저장소 폴더에서 Claude Code를 열 때 돈다:
#   "command": "python -X utf8 \"$CLAUDE_PROJECT_DIR/.claude/hooks/session_start.py\""
# 미리처럼 C:\dev에서 여는 PC는 ~/.claude/settings.json에도 같은 hook을 둔다(.claude/미리-PC설정.md 1절).
# 두 곳에 다 걸려도 같은 세션에서는 한 번만 돈다(session_id 기록).
#
# 하는 일은 둘뿐이다.
#   1) 본 저장소 pull (main이고 고친 파일이 없을 때만, --ff-only)
#      · 성공·최신: 출력 없음
#      · 「untracked working tree files would be overwritten」: 그 파일을 ~/.claude/vcc-pull-backup/<YYYYMMDD>/로
#        옮기고 다시 pull. 성공하면 출력 없음.
#      · 그 밖의 실패(다른 브랜치·고친 파일·네트워크·재시도 실패): 아래 한 줄을 띄운다(Windows 풍선 알림도).
#          [VCC] pull 안 됨 — <이유> · 직접 pull하세요: git -C C:/dev/VCC pull
#        VS Code 패널은 systemMessage를 화면에 띄우지 않으므로(11/21 확인) Claude에게 첫 답변 맨 위에 보여 주라고 함께 전한다.
#   2) push 전 검사 켜기: git config core.hooksPath .githooks (없을 때만. .githooks/pre-push 참고)
# 상태 한 줄·AI 사용액·팀원 메시지는 더 이상 여기서 하지 않는다(사용액은 /token, 팀원 메시지는 /mchk).
# 본 저장소: $CLAUDE_PROJECT_DIR(없으면 이 파일 위치)에서 찾고, worktree(VCC-*)면 그 본 저장소(paths.py와 같은 방식).
# 시험용 환경변수: VCC_BACKUP_ROOT(백업 폴더 위치) · VCC_NO_NOTIFY=1(풍선 알림 끄기)
# 실패해도 세션을 막지 않는다(항상 종료코드 0).
import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path


def _project_dir():
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env and (Path(env) / ".claude" / "hooks").is_dir():
        return Path(env)
    return Path(__file__).resolve().parent.parent.parent


def _main_root(root):
    """worktree면 .git 파일의 gitdir를 따라 본 저장소로(functions/paths.py와 같은 규칙)."""
    git = root / ".git"
    try:
        if git.is_file():
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


PROJECT = _project_dir()
REPO = _main_root(PROJECT)
SEEN = Path.home() / ".claude" / "vcc-hook-session.txt"    # 마지막으로 처리한 session_id (두 번 등록돼도 한 번만)
BACKUP_ROOT = Path(os.environ.get("VCC_BACKUP_ROOT") or Path.home() / ".claude" / "vcc-pull-backup")
OVERWRITE = "untracked working tree files would be overwritten"


def git(*args, timeout=20):
    r = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def _last_line(err):
    lines = [l.strip() for l in err.splitlines() if l.strip()]
    return lines[-1] if lines else "알 수 없는 오류"


def backup_untracked(err):
    """pull 오류 글에서 덮어써질 미추적 파일 목록을 읽어 백업 폴더로 옮긴다. 옮긴 개수(0이면 실패)."""
    files, collecting = [], False
    for line in err.splitlines():
        if OVERWRITE in line:
            collecting = True
        elif collecting and line.startswith(("\t", "    ")) and line.strip():
            files.append(line.strip())
        elif collecting and files:
            break
    dest_root = BACKUP_ROOT / date.today().strftime("%Y%m%d")
    moved = 0
    for rel in files:
        src, dst = REPO / rel, dest_root / rel
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists():
                dst = dst.with_name(f"{dst.name}.{moved}")
            src.replace(dst)
            moved += 1
        except OSError:
            pass
    return moved if moved == len(files) else 0


def pull():
    """성공·최신이면 None, 안 되면 이유 한 줄."""
    code, branch, _ = git("rev-parse", "--abbrev-ref", "HEAD")
    if code != 0:
        return "저장소를 읽지 못함"
    if branch != "main":
        return f"본 폴더가 main이 아니라 {branch} 브랜치"
    _, dirty, _ = git("status", "--porcelain", "--untracked-files=no")
    if dirty:
        return "본 폴더에 고친 파일이 있음"
    code, _, err = git("pull", "--ff-only", "-q", timeout=25)
    if code == 0:
        return None
    if OVERWRITE in err and backup_untracked(err):
        code, _, err = git("pull", "--ff-only", "-q", timeout=25)
        if code == 0:
            return None
        return f"백업 뒤 다시 pull했지만 실패: {_last_line(err)}"
    return f"pull 오류: {_last_line(err)}"


def ensure_hooks_path():
    """push 전 검사(.githooks/pre-push)를 이 PC에서 켠다. 이미 켜져 있으면 아무것도 안 함."""
    _, cur, _ = git("config", "--local", "core.hooksPath")
    if cur != ".githooks":
        git("config", "--local", "core.hooksPath", ".githooks")


def notify(text):
    """Windows 알림(풍선). 기다리지 않도록 별도 PowerShell을 띄우고 바로 돌아온다. 실패해도 무시."""
    if not sys.platform.startswith("win") or os.environ.get("VCC_NO_NOTIFY"):
        return
    safe = text.replace("'", "''")
    ps = ("Add-Type -AssemblyName System.Windows.Forms; Add-Type -AssemblyName System.Drawing; "
          "$n = New-Object System.Windows.Forms.NotifyIcon; $n.Icon = [System.Drawing.SystemIcons]::Information; "
          f"$n.Visible = $true; $n.BalloonTipTitle = 'VCC'; $n.BalloonTipText = '{safe}'; "
          "$n.ShowBalloonTip(10000); Start-Sleep -Seconds 10; $n.Dispose()")
    try:
        subprocess.Popen(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps],
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass


def already_ran():
    """같은 세션에서 hook이 두 번 불리면(사용자 설정 + 저장소 설정) 두 번째는 건너뛴다."""
    try:
        data = json.loads(sys.stdin.read() or "{}") if not sys.stdin.isatty() else {}
    except (ValueError, OSError):
        return False
    sid = str(data.get("session_id") or "") if isinstance(data, dict) else ""
    if not sid:
        return False
    try:
        if SEEN.exists() and SEEN.read_text(encoding="utf-8").strip() == sid:
            return True
        SEEN.parent.mkdir(parents=True, exist_ok=True)
        SEEN.write_text(sid, encoding="utf-8")
    except OSError:
        pass
    return False


def main():
    if not (REPO / ".git").exists():
        return                                   # 이 PC에 저장소가 없으면 아무것도 안 함
    if already_ran():
        return
    try:
        reason = pull()
    except (OSError, subprocess.TimeoutExpired) as e:
        reason = f"pull 중 오류({type(e).__name__})"
    try:
        ensure_hooks_path()
    except (OSError, subprocess.TimeoutExpired):
        pass
    if reason is None:
        return                                   # 성공·최신: 조용히
    line = f"[VCC] pull 안 됨 — {reason} · 직접 pull하세요: git -C {REPO.as_posix()} pull"
    notify(line[6:])
    context = f"{line}\n(SessionStart hook 결과. VS Code 패널에는 이 줄이 보이지 않으니, 첫 답변 맨 위에 이 줄을 그대로 보여 줄 것.)"
    print(json.dumps({"systemMessage": line,
                      "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": context}},
                     ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
