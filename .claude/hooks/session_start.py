# session_start.py — Claude Code SessionStart hook (미리 개인용, 11/21)
#
# 설정은 저장소가 아니라 각 PC의 ~/.claude/settings.json에 넣는다(팀원 PC에서는 돌지 않게).
#   "hooks": {"SessionStart": [{"hooks": [{"type": "command",
#       "command": "python -X utf8 C:/dev/VCC/.claude/hooks/session_start.py", "timeout": 30}]}]}
#
# 하는 일
#   1) 세션을 열 때마다 C:\dev\VCC를 pull — main이고 고친 파일이 없을 때만(--ff-only). 아니면 건너뛰고 이유만 알린다.
#   2) 그날 첫 세션에만 상태 한 줄: main 최신 여부 · 남은 작업 폴더(VCC-*) · 열린 PR · .env 키 개수(값은 읽어도 출력 안 함)
# 출력: {"systemMessage": 사람에게 보일 한 줄, "hookSpecificOutput": {"additionalContext": Claude에게 줄 같은 내용}}
# 실패해도 세션을 막지 않는다(항상 종료코드 0).
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

REPO = Path(r"C:\dev\VCC")
STAMP = Path.home() / ".claude" / "vcc-status-day.txt"     # PC마다 따로. 그날 상태 한 줄을 보여 줬는지
ENV_KEYS = ("CLOVA_KEY", "ANTHROPIC_API_KEY", "VCC_LOGIN_PW")


def git(*args, timeout=20):
    r = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def pull():
    code, branch, _ = git("rev-parse", "--abbrev-ref", "HEAD")
    if code != 0:
        return "pull 건너뜀(저장소를 읽지 못함)", False
    if branch != "main":
        return f"pull 건너뜀(C:\\dev\\VCC가 {branch} 브랜치)", False
    _, dirty, _ = git("status", "--porcelain", "--untracked-files=no")
    if dirty:
        return "pull 건너뜀(C:\\dev\\VCC에 고친 파일 있음)", False
    _, before, _ = git("rev-parse", "HEAD")
    code, _, err = git("pull", "--ff-only", "-q", timeout=25)
    if code != 0:
        return f"pull 실패: {err.splitlines()[-1] if err else '알 수 없음'}", False
    _, after, _ = git("rev-parse", "HEAD")
    if before == after:
        return "main 최신", False
    _, n, _ = git("rev-list", "--count", f"{before}..{after}")
    _, last, _ = git("log", "-1", "--format=%s")
    return f"pull: 새 커밋 {n}개 (최신: {last[:40]})", True


def status_bits():
    bits = []
    left = sorted(p.name for p in REPO.parent.glob("VCC-*") if p.is_dir())
    bits.append(f"남은 작업 폴더 {len(left)}" + (f"({', '.join(left)})" if left else ""))
    try:
        r = subprocess.run(["gh", "pr", "list", "-R", "hufsiei/VCC", "--json", "number,author", "-q", "length"],
                           capture_output=True, text=True, timeout=15)
        bits.append(f"열린 PR {r.stdout.strip()}" if r.returncode == 0 and r.stdout.strip() else "열린 PR 확인 못 함")
    except (OSError, subprocess.TimeoutExpired):
        bits.append("열린 PR 확인 못 함")
    env = REPO / ".env"
    names = set()
    if env.exists():
        for line in env.read_text(encoding="utf-8-sig").splitlines():
            k, sep, v = line.strip().partition("=")
            if sep and v.strip() and not k.strip().startswith("#"):
                names.add(k.strip())
    have = sum(k in names for k in ENV_KEYS)
    bits.append(f".env 키 {have}/{len(ENV_KEYS)}" + ("" if have == len(ENV_KEYS) else " ← 확인 필요"))
    return bits


def main():
    if not (REPO / ".git").exists():
        return                                   # 이 PC에 저장소가 없으면 아무것도 안 함
    try:
        msg, changed = pull()
    except (OSError, subprocess.TimeoutExpired) as e:
        msg, changed = f"pull 건너뜀({type(e).__name__})", False

    today = date.today().isoformat()
    first = not STAMP.exists() or STAMP.read_text(encoding="utf-8").strip() != today
    parts = []
    if first:
        try:
            parts = [msg] + status_bits()
        except Exception as e:                   # 상태 한 줄이 실패해도 세션은 연다
            parts = [msg, f"상태 확인 실패({type(e).__name__})"]
        STAMP.parent.mkdir(parents=True, exist_ok=True)
        STAMP.write_text(today, encoding="utf-8")
    elif changed or "건너뜀" in msg or "실패" in msg:
        parts = [msg]                            # 그날 두 번째 창부터는 바뀐 게 있을 때만
    if not parts:
        return
    line = "[VCC] " + " · ".join(parts)
    print(json.dumps({"systemMessage": line,
                      "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": line}},
                     ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
