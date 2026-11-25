# session_start.py — Claude Code SessionStart hook (11/21 미리 개인용 → 11/24 팀 공용)
#
# 11/24부터 저장소 .claude/settings.json에 등록돼 있어 팀원 PC에서도 돈다(저장소 폴더에서 Claude Code를 열 때):
#   "command": "python -X utf8 \"$CLAUDE_PROJECT_DIR/.claude/hooks/session_start.py\""
# 미리처럼 C:\dev에서 여는 PC는 ~/.claude/settings.json에도 같은 hook을 둔다(.claude/미리-PC설정.md 1절).
# 두 곳에 다 걸려도 같은 세션에서는 한 번만 돈다(session_id 기록).
#
# 하는 일
#   1) 세션을 열 때마다 본 저장소를 pull — main이고 고친 파일이 없을 때만(--ff-only). 아니면 건너뛰고 이유만 알린다.
#   1-1) push 전 검사 켜기: git config core.hooksPath .githooks (없을 때만. .githooks/pre-push 참고)
#   2) 그날 첫 세션에만 상태: main 최신 여부 · 남은 작업 폴더(VCC-*) · 열린 PR · .env 키 개수(값은 읽어도 출력 안 함)
#   3) 매 세션: 오늘 내 AI 사용액 한 줄(functions/ai_usage.py — 이 PC 로그 × 단가). 팀원별 키에 한도가 없어서(11/24)
#   4) 매 세션: 나에게 온 팀원 메시지(11/24 안). PR 본문 「## 팀원에게」 절의 `[to나]` 묶음을 gh로 읽어,
#      아직 안 본 것만 보여 준다(열린 PR 전부 + 7일 안에 병합·닫힌 PR). pull과 상관없이 PR이 올라온 순간부터 보인다.
#      '나'는 git config vcc.me(원우|민지|미리) → 없으면 git user.name·email로 짐작. 본 기록: ~/.claude/vcc-pr-msgs-seen.json
#      (본문을 고쳐 묶음 내용이 바뀌면 다시 보인다). --force면 본 기록을 무시하고 7일 치를 다시 보여 준다.
# 본 저장소: $CLAUDE_PROJECT_DIR(없으면 이 파일 위치)에서 찾고, worktree(VCC-*)면 그 본 저장소(paths.py와 같은 방식).
# 출력: {"systemMessage": 사람에게 보일 한 줄, "hookSpecificOutput": {"additionalContext": Claude에게 줄 같은 내용}}
#   VS Code 패널은 systemMessage를 화면에 띄우지 않으므로(11/21 확인) Windows 알림(풍선)으로도 띄우고,
#   Claude에게는 "첫 답변 맨 위에 이 줄을 보여 주라"고 함께 전한다.
# 다시 보기: python -X utf8 .claude/hooks/session_start.py --force  (그날 이미 봤어도 상태 한 줄)
# 실패해도 세션을 막지 않는다(항상 종료코드 0).
import hashlib
import json
import os
import re
import subprocess
import sys as _sys
import sys
from datetime import date, datetime, timedelta, timezone
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
STAMP = Path.home() / ".claude" / "vcc-status-day.txt"     # PC마다 따로. 그날 상태 한 줄을 보여 줬는지
SEEN = Path.home() / ".claude" / "vcc-hook-session.txt"    # 마지막으로 처리한 session_id (두 번 등록돼도 한 번만)
ENV_KEYS = ("CLOVA_KEY", "ANTHROPIC_API_KEY", "VCC_LOGIN_PW")
MSG_SEEN = Path.home() / ".claude" / "vcc-pr-msgs-seen.json"  # 이미 보여 준 팀원 메시지 {"PR번호": [묶음 해시, …]}
MSG_DAYS = 7                                                  # 병합·닫힌 PR은 이 기간 안의 것만 읽는다
TEAM = {"미리": ("미리", "mirikang"), "민지": ("민지", "minji"), "원우": ("원우", "wwk")}  # 이름·아이디에 들어 있는 글자


def git(*args, timeout=20):
    r = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def pull():
    code, branch, _ = git("rev-parse", "--abbrev-ref", "HEAD")
    if code != 0:
        return "pull 건너뜀(저장소를 읽지 못함)", False
    if branch != "main":
        return f"pull 건너뜀({REPO}가 {branch} 브랜치)", False
    _, dirty, _ = git("status", "--porcelain", "--untracked-files=no")
    if dirty:
        return f"pull 건너뜀({REPO}에 고친 파일 있음)", False
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


def ensure_hooks_path():
    """push 전 검사(.githooks/pre-push)를 이 PC에서 켠다. 이미 켜져 있으면 아무것도 안 함."""
    _, cur, _ = git("config", "--local", "core.hooksPath")
    if cur != ".githooks":
        git("config", "--local", "core.hooksPath", ".githooks")


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


def notify(text):
    """Windows 알림(풍선). 기다리지 않도록 별도 PowerShell을 띄우고 바로 돌아온다. 실패해도 무시."""
    if not _sys.platform.startswith("win"):
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


def ai_usage_line():
    """오늘 내 AI $x.xx (Claude n회) · HCX m회 k토큰 — 로그가 없으면 $0.00. 실패하면 None."""
    sys.path.insert(0, str(PROJECT / "functions"))
    try:
        import ai_usage
        return ai_usage.today_line()
    except Exception:
        return None
    finally:
        sys.path.pop(0)


def who_am_i():
    """원우|민지|미리. git config vcc.me가 있으면 그것, 없으면 user.name·email에 든 글자로 짐작. 모르면 None."""
    _, me, _ = git("config", "vcc.me")
    if me in TEAM:
        return me
    _, name, _ = git("config", "user.name")
    _, mail, _ = git("config", "user.email")
    hay = f"{name} {mail}".lower()
    hits = [k for k, words in TEAM.items() if any(w in hay for w in words)]
    return hits[0] if len(hits) == 1 else None


def _to_names(header):
    """`[to원우·민지] …` → {"원우", "민지"}. 전원이면 셋 다."""
    m = re.match(r"\s*\[to([^\]]+)\]", header)
    if not m:
        return set()
    names = {n for n in re.split(r"[·,/\s]+", m.group(1)) if n}
    return set(TEAM) if "전원" in names else names


def message_blocks(body):
    """PR 본문의 「## 팀원에게」 절에서 `[to…]`로 시작하는 묶음들을 꺼낸다. 코드 블록 표시(```)는 뺀다."""
    lines, inside, blocks, cur = (body or "").replace("\r\n", "\n").split("\n"), False, [], None
    for line in lines:
        if re.match(r"^#{1,3}\s", line):
            inside = line.lstrip("#").strip().startswith("팀원에게")
            cur = None
            continue
        if not inside or line.strip().startswith("```") or line.startswith("🤖"):
            continue
        if re.match(r"\s*\[to[^\]]+\]", line):
            cur = [line.strip()]
            blocks.append(cur)
        elif cur is not None and line.strip():
            cur.append(line.rstrip())
    return ["\n".join(b) for b in blocks]


def team_messages(me, force=False):
    """나에게 온, 아직 안 본 묶음들 → (보여 줄 글 목록, PR 번호 목록). gh가 없거나 실패하면 ([], [])."""
    r = subprocess.run(["gh", "pr", "list", "-R", "hufsiei/VCC", "--state", "all", "--limit", "100",
                        "--json", "number,state,isDraft,updatedAt,body"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15)
    if r.returncode != 0:
        return [], []
    try:
        seen = json.loads(MSG_SEEN.read_text(encoding="utf-8")) if MSG_SEEN.exists() and not force else {}
    except (ValueError, OSError):
        seen = {}
    since = (datetime.now(timezone.utc) - timedelta(days=MSG_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    out, nums, new_seen = [], [], dict(seen)
    for pr in sorted(json.loads(r.stdout or "[]"), key=lambda p: p["number"]):
        if pr["state"] != "OPEN" and pr["updatedAt"] < since:
            continue
        num = str(pr["number"])
        state = "draft" if pr.get("isDraft") else pr["state"].lower()
        for block in message_blocks(pr.get("body")):
            if me not in _to_names(block):
                continue
            h = hashlib.sha1(block.encode("utf-8")).hexdigest()[:12]
            if h in seen.get(num, []):
                continue
            out.append(f"(PR #{num} {state})\n{block}")
            new_seen.setdefault(num, []).append(h)
            if num not in nums:
                nums.append(num)
    if out and not force:
        MSG_SEEN.parent.mkdir(parents=True, exist_ok=True)
        MSG_SEEN.write_text(json.dumps(new_seen, ensure_ascii=False), encoding="utf-8")
    return out, nums


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
    if "--force" not in _sys.argv and already_ran():
        return
    try:
        msg, changed = pull()
    except (OSError, subprocess.TimeoutExpired) as e:
        msg, changed = f"pull 건너뜀({type(e).__name__})", False
    try:
        ensure_hooks_path()
    except (OSError, subprocess.TimeoutExpired):
        pass

    today = date.today().isoformat()
    force = "--force" in _sys.argv
    first = force or not STAMP.exists() or STAMP.read_text(encoding="utf-8").strip() != today
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
    alert = bool(parts)                          # 풍선 알림은 예전처럼 첫 세션·바뀐 게 있을 때만
    usage = ai_usage_line()                      # 사용액은 매 세션
    if usage:
        parts.append(usage)
    msgs, nums, me = [], [], None
    try:
        me = who_am_i()
        if me:
            msgs, nums = team_messages(me, force)  # 팀원 메시지는 매 세션(안 본 것만)
    except Exception:
        pass
    if msgs:
        parts.append(f"팀원 메시지 {len(msgs)}건(PR #{', #'.join(nums)})")
        alert = True
    if not parts:
        return
    line = "[VCC] " + " · ".join(parts)
    if alert and not force:
        notify(line[6:])
    context = (f"{line}\n(SessionStart hook 결과. VS Code 패널에는 이 줄이 보이지 않으니, 이번 세션의 첫 답변 맨 위에 "
               f"이 줄을 그대로 한 번 보여 줄 것.)")
    if msgs:
        context += (f"\n\n[{me}에게 온 팀원 메시지 — PR 본문 「## 팀원에게」에서 읽음. 다음 세션에는 다시 안 뜬다]\n"
                    + "\n\n".join(msgs)
                    + "\n(첫 답변에서 위 메시지를 그대로 보여 주고, (요청)·(결정요망)이 있으면 무엇부터 할지 한 줄로 제안한 뒤 "
                      "사용자가 하라고 할 때 시작할 것. 묻지 않고 파일을 고치지 말 것.)")
    print(json.dumps({"systemMessage": line,
                      "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": context}},
                     ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
