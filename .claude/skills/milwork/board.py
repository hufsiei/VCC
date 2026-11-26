# board.py — 창 상태판 (11/23 미리 개인용 · 11/25 드라이브 공용 + 대기 작업·결정요망·HTML · 11/25 사람별 파일)
#
# Claude 대화창을 여러 개 띄워 작업할 때, 어느 폴더(worktree)에서 무슨 작업이 어디까지 갔고
# 누구에게 무엇을 전해야 하는지를 한 파일에 둔다. 파일은 사람마다 따로: 드라이브 「@VCC\총괄\board-<이름>.md」
# (그 사람의 두 PC 공용, 커밋 안 함). 남의 파일은 읽지 않는다 — list·check·html 모두 내 파일만(팀 대시보드 없음, 11/25).
#   「나」(<이름>): git config vcc.me(원우|민지|미리) → 없으면 git user.name·email로 짐작(11/25까지 session_start.py에 있던 규칙, 이제 여기가 원본).
#     못 정하면 종료코드 1 + 「git config vcc.me 원우」 안내. 한 번만 하면 된다: git config vcc.me <이름>
#   찾는 순서: 환경변수 VCC_BOARD(폴더면 그 안의 board-<이름>.md, .md면 그 파일) → C:~Z: 중 「<X>:\내 드라이브\@VCC」
#     → 없으면 이 PC의 C:\dev\VCC-board-<이름>.md (stderr에 「드라이브 없음, 이 PC 상태판 사용」).
#   잠금(board-<이름>.lock)과 HTML(board-<이름>.html, 탭 파일 board-<이름>-queue|decide|pr.html)도 상태판과 같은 폴더·같은 이름.
#   이전: 드라이브에 사람 이름 없는 board.md(11/25 #249, 미리 것)가 있으면 미리가 처음 실행할 때 board-미리.md로 이름을 바꾼다
#     (다른 사람은 건드리지 않는다). 새 파일이 없고 옛 C:\dev\VCC-board.md가 있으면 옮기고 옛 파일은 VCC-board-이전.md로.
# 파일 모양: 맨 위 「총괄: <세션이름> (<PC>, MM/DD HH:MM)」 → 「마지막 번호: Q-n · D-n」(줄을 지워도 번호를 이어 가려고) → 창 표(10칸 고정)
#   → 「## 창 덧칸」 표(폴더·창 제목·세션 — 옛 board.py가 창 표를 읽게 따로) → 「## 대기 작업」 표 → 「## 결정요망」 표.
# 드라이브 동기화가 늦으니 두 PC가 같은 시각에 쓰면 한쪽이 질 수 있다(한 PC씩 쓰는 전제).
#
# 쓰는 법 (항상 python -X utf8 C:/dev/VCC/.claude/skills/milwork/board.py …):
#   list                                            창 표(진행 중 → 검토 대기 → 닫아도 돼요 순) + 이 PC의 폴더 없는 줄·상태판에 없는 worktree 표시
#                                                   「PR #n」은 gh 한 번으로 병합·닫힘·열림을 대조해 보여 준다(파일은 안 바꿈, gh 안 되면 그대로)
#   add <폴더> --branch B --who W --task T [--files a,b] [--title 창 제목] [--session 세션이름]   (PC는 자동 기록)
#   set <폴더> [--status S] [--files a,b] [--files-set a,b] [--handoff H] [--sent] [--task T] [--title 창 제목] [--session 세션이름]
#                                                   (--files는 추가, --files-set은 통째로 바꿈, --handoff는 덮어씀=안 보냄,
#                                                    --sent는 지금 답장을 「보냄 MM/DD HH:MM」으로 표시)
#   pending                                         아직 안 보낸 답장만(밀종료·밀시작이 본다)
#   check <파일...> [--me <폴더>]                    다른 줄이 같은 파일(또는 그 폴더)을 건드리는지. 겹치면 종료코드 2
#                                                   (끝난 창 줄 — 「완료…」, 병합·닫힌 PR — 은 세지 않는다. queue approve도 같음)
#   remove <폴더>                                    안 보낸 답장이 있으면 지우지 않는다(--force로 무시)
#   prune                                           이 PC에서 폴더가 없어진 줄을 지운다
#   chief                                           머리의 총괄 세션 이름 출력(없으면 빈 줄, 종료코드 1)
#   chief --set <세션이름|–>                         총괄 세션 이름 쓰기(–면 비움)
#   html                                            같은 폴더에 board-<이름>.html 생성(상태판을 바꾸는 명령 뒤 자동 실행)
#                                                   탭 4개 = 파일 4개(board-<이름>.html 창 · -queue · -decide · -pr .html), 스크립트는 묵은 경고 하나
#                                                   끝난 창은 이 PC에서 그 세션이 열려 있을 때만 카드, 나머지는 접힌 「지난 창」(11/26 Q-61)
#   schedule [--install [--every 2] | --remove]     작업 스케줄러로 html 자동 새로 만들기(등록은 미리 승인 뒤) · watch [--every 120] 백그라운드 대안
#   serve [--port 8765]                             상태판 로컬 서버(127.0.0.1만). 새로고침할 때마다 html을 새로 만들어 돌려줌(11/26 Q-62, milstart가 백그라운드로 켬)
#   queue                                           대기 작업 표 출력
#   queue add --task "<작업번호 또는 –> <제목>" --files a,b --from milstart|파생|PR|직접 [--session <이름>] [--note "…"]
#                                                   → 「Q-n 제안」(--from 직접은 「Q-n 승인」. 옛 값 「미리」도 직접과 같게 받음)
#   queue approve Q-n                               겹침 없으면 승인, 겹치면 종료코드 2 + 겹친 줄
#   queue reject Q-n --why "…"                      반려(이유 기록)
#   queue done Q-n [--pr N] [--force]                        병합이 끝난 줄을 완료로(시작됨·승인에서만). 겹침 검사에서 빠짐
#   queue take Q-n --folder VCC-<슬러그> [--session <이름>]   승인만 시작됨으로 + 폴더 기록. 제안·반려면 종료코드 2
#   decide                                          결정요망 표 출력(답 없는 것 위)
#   decide add --folder VCC-x --session <이름> --q "질문" --options "A(추천) …; B …"   → 「D-n」, 그 폴더 줄 결정요망에 D-n
#   decide answer D-n --a "A"                       답·시각 기록, 그 폴더 줄에서 D-n 제거. 출력 첫 줄은 그 D-n의 세션 이름
#   clean [--days 1]                                「갱신」이 N일 넘게 지난 완료·반려 대기 작업 줄 + 「답한 때」가 N일 넘게 지나고 작업이 끝난(폴더 줄 없음) 결정요망 줄을 지운다(밀종료). Q·D 가장 큰 번호 줄은 남긴다
#   selftest                                        임시 폴더에서 위 명령 왕복, 틀리면 종료코드 1
# <폴더>는 "VCC-xxx" 또는 "C:\dev\VCC-xxx" 어느 쪽이든 된다.
import argparse
import html as H
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import quote
import json
import os
import re
import socket
import string
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

DEV = Path(r"C:\dev")
REPO = Path(os.environ.get("VCC_REPO") or DEV / "VCC")   # VCC_REPO는 selftest가 임시 저장소를 쓸 때만
OLD_BOARD = DEV / "VCC-board.md"
TEAM = {"미리": ("미리", "mirikang"), "민지": ("민지", "minji"), "원우": ("원우", "wwk")}  # 「나」 짐작의 원본(스킬 문서들이 이것을 가리킨다)
OLD_COLS = ["폴더", "브랜치", "요청", "작업", "파일", "상태", "갱신", "전달 대기"]
BASE_COLS = ["폴더", "브랜치", "요청", "작업", "파일", "상태", "갱신", "PC", "결정요망", "전달 대기"]
COLS = BASE_COLS                        # 창 표는 이 10칸 그대로 쓴다 — #349 이전 board.py는 머리 줄이 정확히 같아야 읽는다
# 새 칸은 창 표 뒤 「## 창 덧칸」 표에 둔다(11/26 Q-61). #349(11칸 창 표)가 만든 파일도 읽는다.
# 옛 board.py는 덧칸 표를 모르는 표로 건너뛰고, 저장하면 덧칸만 잃는다(창 줄은 남는다). 칸을 더하면 XCOLS 끝에.
XCOLS = ["폴더", "창 제목", "세션"]
XKEYS = XCOLS[1:]
QCOLS = ["번호", "작업", "파일", "출처", "상태", "세션", "폴더", "메모", "갱신"]
DCOLS = ["번호", "폴더", "세션", "질문", "선택지", "답", "답한 때", "올린 때"]
SEP = "; "
SENT = "보냄 "          # 「전달 대기」 칸이 이 말로 시작하면 이미 보낸 답장
EMPTY = ("", "–")
HOST = socket.gethostname()
BOARD = None            # main()에서 정한다
LOCK = None
ME = ""


# ---------- 나 ----------
def _git_config(key):
    try:
        r = subprocess.run(["git", "-C", str(REPO), "config", key], capture_output=True, text=True, **NOWIN,
                           encoding="utf-8", errors="replace", timeout=15)
        return r.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def who_am_i():
    """원우|민지|미리. git config vcc.me가 있으면 그것, 없으면 user.name·email에 든 글자로 짐작. 모르면 None."""
    me = _git_config("vcc.me")
    if me in TEAM:
        return me
    hay = f"{_git_config('user.name')} {_git_config('user.email')}".lower()
    hits = [k for k, words in TEAM.items() if any(w in hay for w in words)]
    return hits[0] if len(hits) == 1 else None


# ---------- 위치 ----------
def find_drive():
    for L in string.ascii_uppercase[2:]:
        p = Path(f"{L}:\\") / "내 드라이브" / "@VCC"
        try:
            if p.is_dir():
                return p
        except OSError:
            pass
    return None


def resolve(me):
    """(board-<me>.md 경로, 옛 파일을 옮겨도 되는지)"""
    env = os.environ.get("VCC_BOARD", "").strip()
    if env:
        p = Path(env)
        return (p if p.suffix.lower() == ".md" else p / f"board-{me}.md"), False
    d = find_drive()
    if d:
        return d / "총괄" / f"board-{me}.md", True
    print("드라이브 없음, 이 PC 상태판 사용", file=sys.stderr)
    return DEV / f"VCC-board-{me}.md", True


def set_board(path):
    global BOARD, LOCK
    BOARD = Path(path)
    LOCK = BOARD.with_suffix(".lock")


def html_path(board=None):
    return Path(board or BOARD).with_suffix(".html")


def rename_unnamed(new, me):
    """같은 폴더의 이름 없는 board.md(#249, 미리 것)를 board-미리.md로. 다른 사람은 건드리지 않는다. 바꿨으면 True."""
    new = Path(new)
    old = new.with_name("board.md")
    if me != "미리" or new.exists() or not old.exists() or old == new:
        return False
    old.rename(new)
    oh = old.with_suffix(".html")
    if oh.exists() and not html_path(new).exists():
        oh.rename(html_path(new))
    print(f"상태판 이름 바꿈: {old.name} → {new.name}", file=sys.stderr)
    return True


def migrate(old, new):
    """옛 상태판을 새 위치로 옮긴다(PC·결정요망 열 추가). 옮겼으면 True."""
    old, new = Path(old), Path(new)
    if new.exists() or not old.exists() or old.resolve() == new.resolve():
        return False
    st = parse(old.read_text(encoding="utf-8"))
    new.parent.mkdir(parents=True, exist_ok=True)
    save(st, new, html=False)
    old.rename(old.with_name(old.stem + "-이전.md"))
    print(f"상태판 이전: {old} → {new} (줄 {len(st['rows'])}개, 옛 파일은 {old.stem}-이전.md)", file=sys.stderr)
    return True


# ---------- 읽기·쓰기 ----------
def now():
    return datetime.now().strftime("%m/%d %H:%M")


def age(stamp, at=None):
    """「MM/DD HH:MM」이 지난 시간(timedelta). 연도가 없으니 올해로 본다. 하루 넘게 미래거나 못 읽으면 None(지우지 않음)."""
    at = at or datetime.now()
    m = re.match(r"^(\d\d)/(\d\d) (\d\d):(\d\d)$", stamp.strip())
    if not m:
        return None
    try:
        t = datetime(at.year, *map(int, m.groups()))
    except ValueError:          # 02/29가 없는 해, 잘못 적은 값
        return None
    return at - t if t <= at + timedelta(days=1) else None     # 두 PC 시계 차이만큼의 미래는 봐준다


def folder_name(s):
    s = s.strip().rstrip("\\/")
    return Path(s).name if ("\\" in s or "/" in s) else s


def clean(cell):
    return str(cell).replace("|", "／").replace("\n", " ").strip()


def split_files(s):
    return [f.strip().replace("\\", "/") for f in re.split(r"[;,]", s or "") if f.strip() and f.strip() not in EMPTY]


def split_ids(s):
    return [x.strip() for x in re.split(r"[;,]", s or "") if x.strip() and x.strip() not in EMPTY]


def unsent(r):
    h = r.get("전달 대기", "")
    return h not in EMPTY and not h.startswith(SENT)


def header_key(cells):
    """표 머리 줄이면 rows|queue|decide. 알려진 열 뒤에 칸이 더 붙어도(나중 버전이 끝에 추가) 읽는다."""
    t = tuple(cells)
    if t == tuple(OLD_COLS):
        return "rows"
    for cols, key in ((BASE_COLS, "rows"), (QCOLS, "queue"), (DCOLS, "decide"), (XCOLS[:2], "extra")):
        if t[:len(cols)] == tuple(cols):
            return key
    return None


def parse(text):
    st = {"chief": None, "rows": [], "queue": [], "decide": [], "last": {"Q": 0, "D": 0}}
    cur, extra = None, []
    for line in text.splitlines():
        m = re.match(r"^총괄: (.*)$", line)
        if m and st["chief"] is None:
            body = m.group(1).strip()
            if body not in EMPTY:
                mm = re.match(r"^(.*) \((.*), (\d\d/\d\d \d\d:\d\d)\)$", body)
                st["chief"] = ({"name": mm.group(1), "pc": mm.group(2), "at": mm.group(3)} if mm
                               else {"name": body, "pc": "", "at": ""})
            continue
        n = re.match(r"^마지막 번호: Q-(\d+) · D-(\d+)", line)
        if n:
            st["last"] = {"Q": int(n.group(1)), "D": int(n.group(2))}
            continue
        if not line.startswith("|"):
            cur = None
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        key = header_key(cells)
        if key:
            cur = (key, cells)
            continue
        if cur is None or set("".join(cells)) <= set("-: "):
            continue
        key, head = cur
        if len(cells) != len(head) or cells[0] in EMPTY:
            continue
        d = dict(zip(head, cells))
        if key == "rows":
            d.setdefault("PC", HOST)
            d.setdefault("결정요망", "–")
            for k in XKEYS:
                d.setdefault(k, "–")
        if key == "extra":
            extra.append(d)
            continue
        st[key].append(d)
    for x in extra:                     # 덧칸은 창 표 뒤에 있으니 다 읽은 다음 폴더로 붙인다
        r = find(st["rows"], x["폴더"])
        if r:
            for k in XKEYS:
                if x.get(k, "–") not in EMPTY:
                    r[k] = x[k]
    bump_last(st)
    return st


def load(path=None):
    p = Path(path or BOARD)
    if not p.exists():
        return parse("")
    return parse(p.read_text(encoding="utf-8"))


def table(cols, rows):
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    out += ["| " + " | ".join(clean(r.get(c, "")) or "–" for c in cols) + " |" for r in rows]
    return out


def chief_line(st):
    c = st.get("chief")
    return f"총괄: {c['name']} ({c['pc']}, {c['at']})" if c else "총괄: –"


def save(st, path=None, html=True):
    p = Path(path or BOARD)
    p.parent.mkdir(parents=True, exist_ok=True)
    bump_last(st)
    last = f"마지막 번호: Q-{st['last']['Q']} · D-{st['last']['D']}"
    lines = [chief_line(st), "", last, "", f"# VCC 상태판 — {ME or p.stem} (두 PC 공용 · 갱신 {now()} {HOST})", "",
             "작업 대화창은 `milwork`로 줄을 만들고 진행에 따라 「상태」「파일」「전달 대기」를 고친다. "
             "팀원 답장은 그 대화창이 바로 쓰고 「전달 대기」에 요점을 적는다. 미리가 보내면 `--sent`로 「보냄」 표시. "
             "총괄 대화창은 대기 작업을 승인하고 결정요망에 답한다. 병합된 줄과 폴더, 완료·반려 하루 지난 줄과, 답한 지 하루 지나고 작업이 끝난 결정요망은 `milend`가 지운다(가장 큰 번호 줄은 남김).", ""]
    lines += table(COLS, st["rows"])
    lines += ["", "## 창 덧칸", "", "창 표와 폴더로 짝짓는 칸(창 제목·세션). 옛 board.py가 창 표를 읽게 따로 둔다.", ""]
    lines += table(XCOLS, st["rows"])
    lines += ["", "## 대기 작업", ""] + table(QCOLS, st["queue"])
    lines += ["", "## 결정요망", ""] + table(DCOLS, st["decide"])
    tmp = p.with_suffix(".tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.replace(tmp, p)
    if html:
        try:
            make_html(st, html_path(p))
        except Exception as e:      # HTML이 실패해도 상태판 쓰기는 살린다
            print(f"{html_path(p).name} 못 만듦: {e}", file=sys.stderr)


class locked:
    def __enter__(self):
        LOCK.parent.mkdir(parents=True, exist_ok=True)
        for _ in range(50):
            try:
                self.fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                return self
            except FileExistsError:
                try:
                    if time.time() - LOCK.stat().st_mtime > 10:   # 죽은 잠금
                        LOCK.unlink()
                        continue
                except OSError:
                    pass
                time.sleep(0.1)
        raise SystemExit(f"상태판 잠금을 얻지 못했습니다({LOCK} 을 지우고 다시).")

    def __exit__(self, *a):
        os.close(self.fd)
        try:
            LOCK.unlink()
        except OSError:
            pass


def worktrees():
    try:
        r = subprocess.run(["git", "-C", str(REPO), "worktree", "list", "--porcelain"], **NOWIN,
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return {}
    out, cur = {}, None
    for line in r.stdout.splitlines():
        if line.startswith("worktree "):
            cur = Path(line[9:]).name
        elif line.startswith("branch ") and cur:
            out[cur] = line.split("/", 2)[-1]
    out.pop("VCC", None)
    return out


def find(rows, folder):
    name = folder_name(folder)
    for r in rows:
        if r["폴더"] == name:
            return r
    return None


def by_id(items, i):
    for x in items:
        if x["번호"] == i.strip():
            return x
    return None


def max_num(items, prefix):
    return max((int(m.group(1)) for x in items if (m := re.match(rf"^{prefix}-(\d+)$", x["번호"]))), default=0)


def bump_last(st):
    """마지막 번호 = 머리에 적힌 값과 남은 줄 중 큰 쪽."""
    for prefix, key in (("Q", "queue"), ("D", "decide")):
        st["last"][prefix] = max(st["last"][prefix], max_num(st[key], prefix))


def next_id(st, prefix):
    bump_last(st)
    return f"{prefix}-{st['last'][prefix] + 1}"


def overlap(a, b):
    a, b = a.strip("/"), b.strip("/")
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


def mine(r):
    return r.get("PC", "") in EMPTY or r.get("PC") == HOST


# ---------- PR 대조(진행상황 자동 갱신, 11/26) ----------
# 창 줄 「상태」의 「PR #n」을 gh 한 번으로 대조한다. 상태판 파일은 바꾸지 않고 보일 때(list·html)와 겹침 검사에만 쓴다.
# gh가 안 되면(없음·로그인 안 됨·VCC_BOARD_NOGH) None → 예전처럼 「PR #n 올림」 그대로, 겹침도 예전처럼 센다.
# VCC_BOARD_PRS=<json 파일>이면 gh 대신 그 파일(selftest용).
PR_RE = re.compile(r"PR #(\d+)")
PR_FIELDS = "number,state,mergedAt,title,author,createdAt,headRefName"
_PRS = []                   # [] = 아직 안 읽음, 그 뒤로는 list 또는 None
GH_NOTE = ""                # 서버가 gh를 못 읽어 지난 결과를 보일 때 한 줄(Q-62). 평소엔 빈 글


def all_prs():
    if _PRS == []:
        _PRS.append(_read_prs())
    return _PRS[0]


def _read_prs():
    fake = os.environ.get("VCC_BOARD_PRS", "").strip()
    if fake:
        try:
            return json.loads(Path(fake).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
    if os.environ.get("VCC_BOARD_NOGH"):
        return None
    try:
        r = subprocess.run(["gh", "pr", "list", "-R", "hufsiei/VCC", "--state", "all", "--limit", "100",
                            "--json", PR_FIELDS], **NOWIN,
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20)
        if r.returncode != 0:
            return None
        return json.loads(r.stdout or "[]")
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None


def pr_states(rows=None):
    """{PR 번호: OPEN|MERGED|CLOSED}. rows를 주면 그 줄에 「PR #n」이 없을 때 gh를 부르지 않는다. 못 읽으면 None."""
    if rows is not None and not any(PR_RE.search(r.get("상태", "")) for r in rows):
        return {}
    prs = all_prs()
    if prs is None:
        return None
    return {p.get("number"): str(p.get("state", "")).upper() for p in prs}


PHASES = ("run", "review", "done")      # 창 탭 순서: 진행 중 → 검토 대기 → 닫아도 돼요
BADGE = {"run": "● 진행 중", "review": "◐ 검토 대기", "done": "✓ 닫아도 돼요"}


def phase(r, states):
    """(run|review|done, 보일 상태 글). 「완료…」·병합·닫힌 PR = done, 열린 PR = review."""
    s = r.get("상태", "")
    if s.startswith("완료"):
        return "done", s
    m = PR_RE.search(s)
    if not m:
        return "run", s
    n = int(m.group(1))
    got = (states or {}).get(n)
    if got == "MERGED":
        return "done", f"PR #{n} 병합됨"
    if got == "CLOSED":
        return "done", f"PR #{n} 닫힘(병합 안 함)"
    if got == "OPEN":
        return "review", f"PR #{n} 열림"
    return "review", s                  # gh 못 읽음·100건 밖 — 그대로


def ended(r, states):
    return phase(r, states)[0] == "done"


def by_phase(rows, states):
    return sorted(rows, key=lambda r: PHASES.index(phase(r, states)[0]))      # 같은 단계 안은 파일 순서


def title_of(r):
    """창 제목: 「창 제목」 칸, 없으면 「작업」에서 앞의 슬러그를 뺀 글(VS Code 탭 「milwork …」에서 찾는 글)."""
    t = r.get("창 제목", "")
    if t not in EMPTY:
        return t
    task = r.get("작업", "")
    parts = task.split(None, 1)
    if len(parts) == 2:
        slug = re.sub(r"-\d+$", "", r.get("폴더", "").removeprefix("VCC-"))
        if parts[0] == slug or re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)+", parts[0]):
            return parts[1]
    return task or r.get("폴더", "")


def row_of_q(st, x):
    """큐 줄이 가리키는 창 줄: 폴더가 같은 줄, 폴더가 비었으면 세션이 같은 줄 하나(둘 이상이면 모름)."""
    if x.get("폴더", "–") not in EMPTY:
        return find(st["rows"], x["폴더"])
    s = x.get("세션", "–")
    hit = [r for r in st["rows"] if s not in EMPTY and r.get("세션") == s]
    return hit[0] if len(hit) == 1 else None


def q_of_row(st, r):
    """창 줄을 맡은 큐 줄(폴더가 같은 것 중 마지막)."""
    hit = [x for x in st["queue"] if x.get("폴더") == r["폴더"]]
    return hit[-1] if hit else None


def queue_view(st, states):
    """보일 때만(파일은 그대로, queue done이 닫는다): 맡은 창 줄이 끝났으면(병합·닫힘·완료) 「시작됨」 큐 줄을 「완료」로,
    PR이 열려 있으면 「검토 대기」로. 11/26 Q-50이 시작됨에 남은 것은 PR 병합 뒤 HTML을 다시 만들지 않아서였다(4번 자동 새로 만들기)."""
    out = []
    for x in st["queue"]:
        y = dict(x)
        r = row_of_q(st, x) if x["상태"] == "시작됨" else None
        if r:
            ph, shown = phase(r, states)
            memo = f" · {x['메모']}" if x.get("메모", "–") not in EMPTY else ""
            if ph == "done":
                y["상태"] = "완료"
                y["메모"] = f"{shown}(보기만 완료 — queue done으로 닫기){memo}"
            elif ph == "review":
                y["상태"] = "검토 대기"
                y["메모"] = f"{shown}{memo}"
        out.append(y)
    return out


# ---------- 창이 살아 있나(11/26 Q-61) ----------
# Claude Code는 열린 세션마다 ~/.claude/sessions/<pid>.json(name·pid·procStart·pidDomain "win32:<PC>")을 두고 닫으면 지운다.
# 이 PC 것(pidDomain의 PC = HOST)만, 그 pid의 프로세스가 지금 있고 시작 시각(FILETIME)이 procStart와 같을 때 살아 있다고 본다
# (pid가 다른 프로그램에 다시 쓰인 경우를 거른다). 창 줄의 세션 = 「세션」 칸, 없으면 그 폴더를 맡은 큐 줄의 세션.
# 판별을 못 하면(Windows 아님·기록 폴더 없음) None → 대안: 이 PC 줄 + 작업 폴더 있음 + 갱신 12시간 이내.
# VCC_BOARD_LIVE="a,b"면 그 이름만 살아 있다고 본다(selftest, "?"면 판별 못 함).
NOWIN = {"creationflags": 0x08000000} if os.name == "nt" else {}     # pythonw(작업 스케줄러)에서 gh·git 콘솔 창이 안 뜨게
FALLBACK_HOURS = 12
_LIVE = []


def _proc_start(pid):
    """살아 있는 프로세스의 시작 시각(FILETIME 정수), 없거나 끝났으면 None."""
    import ctypes
    from ctypes import wintypes
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.OpenProcess.restype = wintypes.HANDLE
    k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    k.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    k.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    k.CloseHandle.argtypes = [wintypes.HANDLE]
    h = k.OpenProcess(0x1000, False, int(pid))      # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return None
    try:
        code = wintypes.DWORD()
        if not k.GetExitCodeProcess(h, ctypes.byref(code)) or code.value != 259:     # STILL_ACTIVE
            return None
        t = [wintypes.FILETIME() for _ in range(4)]
        if not k.GetProcessTimes(h, *[ctypes.byref(x) for x in t]):
            return None
        return (t[0].dwHighDateTime << 32) | t[0].dwLowDateTime
    finally:
        k.CloseHandle(h)


def live_sessions():
    """이 PC에서 지금 열린 Claude Code 세션 이름 집합. 판별 못 하면 None."""
    if _LIVE == []:
        _LIVE.append(_read_live())
    return _LIVE[0]


def _read_live():
    if "VCC_BOARD_LIVE" in os.environ:
        v = os.environ["VCC_BOARD_LIVE"].strip()
        return None if v == "?" else set(split_ids(v))
    d = Path.home() / ".claude" / "sessions"
    if os.name != "nt" or not d.is_dir():
        return None
    out = set()
    try:
        files = list(d.glob("*.json"))
    except OSError:
        return None
    for f in files:
        try:
            j = json.loads(f.read_text(encoding="utf-8"))
            if str(j.get("pidDomain", "")).split(":", 1)[-1].lower() != HOST.lower() or not j.get("name"):
                continue
            got = _proc_start(j["pid"])
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            continue
        if got is not None and str(got) == str(j.get("procStart", got)):
            out.add(j["name"])
    return out


def session_of(st, r):
    s = r.get("세션", "–")
    if s not in EMPTY:
        return s
    x = q_of_row(st, r)
    return x.get("세션", "–") if x else "–"


def window_open(st, r, live=None, at=None):
    """끝난 창을 창 탭에 보일지: 이 PC에서 그 세션이 살아 있을 때만. 판별 못 하면 대안(폴더 있음 + 12시간 이내)."""
    if not mine(r):
        return False
    live = live_sessions() if live is None else live
    if live is not None:
        return session_of(st, r) in live
    a = age(r.get("갱신", ""), at)
    return (DEV / r["폴더"]).is_dir() and a is not None and a < timedelta(hours=FALLBACK_HOURS)


def shown_rows(st, states):
    """창 탭: (보일 줄 by_phase 순서, 지난 창 줄). 진행 중·검토 대기는 다 보이고, 끝난 창은 열린 것만."""
    keep, past = [], []
    for r in by_phase(st["rows"], states):
        (keep if phase(r, states)[0] != "done" or window_open(st, r) else past).append(r)
    return keep, past


# ---------- 창 표 명령 ----------
def cmd_list(args):
    st, wts = load(), worktrees()
    rows = st["rows"]
    states = pr_states(rows)
    if not rows and not wts:
        print("상태판 비어 있음 · 작업 폴더 없음")
    for r in by_phase(rows, states):
        if mine(r):
            flag = "" if (DEV / r["폴더"]).is_dir() else "  ← 폴더 없음(병합·삭제됐으면 remove/prune)"
        else:
            flag = f"  (다른 PC: {r['PC']})"
        ph, shown = phase(r, states)
        close = "닫아도 돼요" if window_open(st, r) else ("지난 창(창 닫힘)" if mine(r) else "지난 창")
        mark = {"run": "", "review": f" → {shown} · 검토 대기", "done": f" → {shown} · {close}"}[ph]
        if ph == "done" and shown == r["상태"]:
            mark = f" → {close}"
        print(f"[{r['폴더']}] {r['브랜치']} · {r['요청']} · {r['작업']}{flag}")
        print(f"    상태: {r['상태']}{mark} ({r['갱신']}) · 파일: {r['파일']}"
              + (f" · 결정요망: {r['결정요망']}" if r.get("결정요망", "–") not in EMPTY else ""))
        if unsent(r):
            print(f"    전달 대기(안 보냄): {r['전달 대기']}")
        elif r["전달 대기"] not in EMPTY:
            print(f"    전달: {r['전달 대기']}")
    for name, br in wts.items():
        if not find(rows, name):
            print(f"[{name}] {br}  ← 상태판에 없음(milwork 전에 만든 폴더. add로 적거나 지운다)")
    if rows:
        n = {k: sum(1 for r in rows if phase(r, states)[0] == k) for k in PHASES}
        past = len(shown_rows(st, states)[1])
        print(f"창: 진행 중 {n['run']} · 검토 대기 {n['review']} · 닫아도 돼요 {n['done'] - past} · 지난 창 {past}"
              + ("" if states is not None else " (gh 못 읽음 — PR 병합 여부 모름)")
              + ("" if live_sessions() is not None else f" (창 생존 판별 못 함 — 폴더 있음 + {FALLBACK_HOURS}시간 이내로 봄)"))
    q = sum(1 for x in st["queue"] if x["상태"] in ("제안", "승인"))
    d = sum(1 for x in st["decide"] if x["답"] in EMPTY)
    if q or d:
        print(f"대기 작업 {q} · 결정요망 {d} (board.py queue / decide)")


def cmd_add(args):
    with locked():
        st = load()
        name = folder_name(args.folder)
        if find(st["rows"], name):
            raise SystemExit(f"이미 있음: {name} (set으로 고치세요)")
        st["rows"].append({"폴더": name, "브랜치": args.branch, "요청": args.who, "작업": args.task,
                           "파일": SEP.join(split_files(args.files)) or "–", "상태": args.status or "시작",
                           "갱신": now(), "PC": HOST, "결정요망": "–", "전달 대기": "–",
                           "창 제목": clean(args.title or "") or "–", "세션": clean(args.session or "") or "–"})
        save(st)
    print(f"추가: {name} ({args.branch})")
    cmd_check(argparse.Namespace(files=split_files(args.files), me=name))


def cmd_set(args):
    with locked():
        st = load()
        r = find(st["rows"], args.folder)
        if not r:
            raise SystemExit(f"없음: {folder_name(args.folder)} (add 먼저)")
        if args.status:
            r["상태"] = args.status
        if args.task:
            r["작업"] = args.task
        if args.title is not None:
            r["창 제목"] = clean(args.title) or "–"
        if args.session is not None:
            r["세션"] = clean(args.session) or "–"
        if args.branch:
            r["브랜치"] = args.branch
        if args.files_set is not None:
            r["파일"] = SEP.join(split_files(args.files_set)) or "–"
        if args.files:
            have = split_files(r["파일"])
            for f in split_files(args.files):
                if f not in have:
                    have.append(f)
            r["파일"] = SEP.join(have) or "–"
        if args.handoff is not None:
            r["전달 대기"] = args.handoff or "–"
        if args.sent:
            h = r["전달 대기"]
            if h in EMPTY:
                raise SystemExit(f"보낼 답장이 없음: {r['폴더']} (--handoff로 먼저 적기)")
            if not h.startswith(SENT):
                r["전달 대기"] = f"{SENT}{now()} · {h}"
        r["갱신"] = now()
        save(st)
    print(f"갱신: {r['폴더']} · 상태 {r['상태']} · 파일 {r['파일']}" +
          (f" · 전달 대기 {r['전달 대기']}" if r["전달 대기"] != "–" else ""))
    if args.files:
        cmd_check(argparse.Namespace(files=split_files(args.files), me=r["폴더"]))


def overlaps(st, files, me=None, skip_q=None):
    """files와 겹치는 창 줄·승인된 대기 작업을 문장으로. 끝난 창 줄(완료·병합·닫힌 PR)은 세지 않는다."""
    hits = []
    others = [r for r in st["rows"] if r["폴더"] != me]
    states = pr_states(others) if files else {}
    rows = [r for r in others if not ended(r, states)]
    for f in [x.replace("\\", "/") for x in files]:
        for r in rows:
            for g in split_files(r["파일"]):
                if overlap(f, g):
                    hits.append(f"겹침: {f} ↔ [{r['폴더']}] {r['브랜치']} ({r['요청']} · {r['작업']} · {r['상태']})")
        for q in st["queue"]:
            if q["번호"] == skip_q or q["상태"] not in ("승인", "시작됨"):
                continue            # 완료·반려·제안은 세지 않는다
            if q["상태"] == "시작됨":
                continue            # 창 줄이 있으면 위에서 셌고, 없으면(remove됨) 고치는 중이 아니다
            for g in split_files(q["파일"]):
                if overlap(f, g):
                    hits.append(f"겹침: {f} ↔ [{q['번호']}] {q['작업']} ({q['상태']})")
    return list(dict.fromkeys(hits))


def cmd_check(args):
    st = load()
    me = folder_name(args.me) if args.me else None
    hits = [h for h in overlaps(st, args.files, me) if "↔ [Q-" not in h]
    if hits:
        print("\n".join(hits))
        print("→ 다른 대화창이 같은 파일을 쓰고 있다. 고치기 전에 미리에게 알린다(같은 날 같은 파일 금지).")
        sys.exit(2)
    if args.files:
        print("겹치는 파일 없음")


def cmd_pending(args):
    rows = [r for r in load()["rows"] if unsent(r)]
    if not rows:
        print("안 보낸 답장 없음")
        return
    for r in rows:
        print(f"[{r['폴더']}] {r['요청']} · {r['작업']} ({r['갱신']})")
        print(f"    {r['전달 대기']}")
    print(f"→ 안 보낸 답장 {len(rows)}건. 보냈으면 board.py set <폴더> --sent")


def cmd_remove(args):
    with locked():
        st = load()
        name = folder_name(args.folder)
        r = find(st["rows"], name)
        if not r:
            raise SystemExit(f"없음: {name}")
        if unsent(r) and not args.force:
            raise SystemExit(f"안 보낸 답장이 있음: {name} — {r['전달 대기']}\n"
                             "보냈으면 set --sent 뒤 다시, 버려도 되면 --force")
        st["rows"] = [x for x in st["rows"] if x["폴더"] != name]
        closed = [x for x in st["queue"] if x["폴더"] == name and x["상태"] == "시작됨"]
        for x in closed:
            x["상태"], x["갱신"] = "완료", now()
        save(st)
    print(f"지움: {name}")
    for x in closed:
        print(f"{x['번호']} 시작됨 → 완료 (PR 번호를 남기려면 queue done {x['번호']} --pr N)")


def cmd_prune(args):
    with locked():
        st = load()
        missing = [r for r in st["rows"] if mine(r) and not (DEV / r["폴더"]).is_dir()]
        gone = [r["폴더"] for r in missing if not unsent(r)]
        kept = [r["폴더"] for r in missing if unsent(r)]
        st["rows"] = [r for r in st["rows"] if not (mine(r) and r["폴더"] in gone)]
        save(st)
    print("지운 줄: " + (", ".join(gone) if gone else "없음"))
    if kept:
        print("남긴 줄(안 보낸 답장 있음): " + ", ".join(kept) + " — 보냈으면 set --sent 뒤 다시 prune")


# ---------- 총괄 ----------
def cmd_chief(args):
    if args.set is None:
        c = load()["chief"]
        print(c["name"] if c else "")
        if not c:
            sys.exit(1)
        return
    with locked():
        st = load()
        name = args.set.strip()
        st["chief"] = None if name in EMPTY else {"name": name, "pc": HOST, "at": now()}
        save(st)
    print(chief_line(st))


# ---------- 대기 작업 ----------
def cmd_queue(args):
    q = load()["queue"]
    if not q:
        print("대기 작업 없음")
        return
    for x in q:
        extra = " · ".join(f"{k} {x[k]}" for k in ("세션", "폴더", "메모") if x.get(k, "–") not in EMPTY)
        print(f"{x['번호']} {x['상태']} · {x['작업']} · 파일: {x['파일']} · 출처: {x['출처']} ({x['갱신']})"
              + (f" · {extra}" if extra else ""))


def cmd_queue_add(args):
    with locked():
        st = load()
        i = next_id(st, "Q")
        state = "승인" if args.source in ("직접", "미리") else "제안"
        st["queue"].append({"번호": i, "작업": args.task, "파일": SEP.join(split_files(args.files)) or "–",
                            "출처": args.source, "상태": state, "세션": args.session or "–", "폴더": "–",
                            "메모": args.note or "–", "갱신": now()})
        save(st)
    print(f"{i} {state}")


def _q(st, i):
    x = by_id(st["queue"], i)
    if not x:
        raise SystemExit(f"없음: {i}")
    return x


def cmd_queue_approve(args):
    with locked():
        st = load()
        x = _q(st, args.id)
        if x["상태"] == "시작됨":
            raise SystemExit(f"{x['번호']} 이미 시작됨({x['폴더']})")
        hits = overlaps(st, split_files(x["파일"]), skip_q=x["번호"])
        if hits:
            print("\n".join(hits))
            print(f"→ {x['번호']} 승인 안 함(상태 {x['상태']} 그대로). 겹친 작업이 끝난 뒤 다시.")
            sys.exit(2)
        x["상태"], x["갱신"] = "승인", now()
        save(st)
    print(f"{x['번호']} 승인")


def cmd_queue_reject(args):
    with locked():
        st = load()
        x = _q(st, args.id)
        x["상태"], x["갱신"] = "반려", now()
        x["메모"] = f"반려: {args.why}" + (f" · {x['메모']}" if x["메모"] not in EMPTY else "")
        save(st)
    print(f"{x['번호']} 반려")


def cmd_queue_done(args):
    with locked():
        st = load()
        x = _q(st, args.id)
        if x["상태"] not in ("시작됨", "승인", "완료") and not (args.force and x["상태"] == "반려"):
            print(f"{x['번호']} 상태 {x['상태']} — 시작됨·승인만 완료로 바꿀 수 있음(반려로 잘못 닫은 줄은 --force)")
            sys.exit(2)
        pr = f" PR #{str(args.pr).lstrip('#')} 병합" if args.pr else ""
        note = f"완료{pr} ({now()})"
        base = x["메모"] if x["메모"] not in EMPTY and not x["메모"].startswith(("완료", "반려")) else ""
        x["상태"], x["갱신"] = "완료", now()
        x["메모"] = note + (f" · {base}" if base else "")
        save(st)
    print(f"{x['번호']} 완료")


def cmd_queue_take(args):
    with locked():
        st = load()
        x = _q(st, args.id)
        if x["상태"] != "승인":
            print(f"{x['번호']} 상태 {x['상태']} — 승인된 것만 시작할 수 있음")
            sys.exit(2)
        x["상태"], x["폴더"], x["갱신"] = "시작됨", folder_name(args.folder), now()
        if args.session:
            x["세션"] = args.session
        save(st)
    print(f"{x['번호']} 시작됨 → {x['폴더']}")


# ---------- 결정요망 ----------
def cmd_decide(args):
    d = load()["decide"]
    if not d:
        print("결정요망 없음")
        return
    for x in sorted(d, key=lambda x: x["답"] not in EMPTY):
        a = f"답 {x['답']} ({x['답한 때']})" if x["답"] not in EMPTY else "답 없음"
        print(f"{x['번호']} [{x['폴더']}] {x['세션']} · {x['질문']} — {x['선택지']} · {a}")


def cmd_decide_add(args):
    with locked():
        st = load()
        i = next_id(st, "D")
        name = folder_name(args.folder)
        st["decide"].append({"번호": i, "폴더": name, "세션": args.session, "질문": args.q,
                             "선택지": args.options, "답": "–", "답한 때": "–", "올린 때": now()})
        r = find(st["rows"], name)
        if r:
            ids = split_ids(r.get("결정요망"))
            r["결정요망"] = SEP.join(ids + [i])
        else:
            print(f"(주의) 창 표에 {name} 줄이 없음 — 결정요망 표에만 적음", file=sys.stderr)
        save(st)
    print(i)


def cmd_decide_answer(args):
    with locked():
        st = load()
        x = by_id(st["decide"], args.id)
        if not x:
            raise SystemExit(f"없음: {args.id}")
        x["답"], x["답한 때"] = args.a, now()
        r = find(st["rows"], x["폴더"])
        if r:
            r["결정요망"] = SEP.join(i for i in split_ids(r.get("결정요망")) if i != x["번호"]) or "–"
        save(st)
    print(x["세션"])
    print(f"{x['번호']} 답: {x['답']}")


# ---------- 지난 줄 정리 ----------
def cmd_clean(args):
    limit = timedelta(days=args.days)

    def old(stamp):
        a = age(stamp)
        return a is not None and a > limit

    with locked():
        st = load()
        # 가장 큰 번호 줄은 남긴다 — 옛 board.py가 저장해 「마지막 번호」 머리가 빠져도 번호가 다시 쓰이지 않게
        top = {f"Q-{max_num(st['queue'], 'Q')}", f"D-{max_num(st['decide'], 'D')}"}
        q = [x["번호"] for x in st["queue"]
             if x["번호"] not in top and x["상태"] in ("완료", "반려") and old(x["갱신"])]
        d = [x["번호"] for x in st["decide"]
             if x["번호"] not in top and x["답"] not in EMPTY and old(x["답한 때"])
             and not find(st["rows"], x["폴더"])]          # 폴더 줄이 있으면 작업 중
        if q or d:
            st["queue"] = [x for x in st["queue"] if x["번호"] not in q]
            st["decide"] = [x for x in st["decide"] if x["번호"] not in d]
            save(st)
    print(f"정리: 대기 작업 {len(q)}줄 · 결정요망 {len(d)}줄" + (f" ({', '.join(q + d)})" if q or d else ""))


# ---------- HTML ----------
# 탭 4개(창 · 대기 작업 · 결정요망 · 열린 PR)는 탭마다 파일 하나: board-<이름>.html(창) · board-<이름>-queue.html ·
# -decide.html · -pr.html. 스크립트 없이 링크로 옮겨 다니고, 60초 새로 읽기(meta refresh)는 그 파일을 다시 읽으니 고른 탭이 남는다.
# (#주소 + :target은 Chrome의 meta refresh가 #을 버리고 다시 읽어 창 탭으로 돌아가서 버림, 11/26 확인)
TABS = (("win", "창"), ("queue", "대기 작업"), ("decide", "결정요망"), ("pr", "열린 PR"))


def tab_path(path, k):
    path = Path(path)
    return path if k == "win" else path.with_name(f"{path.stem}-{k}.html")

CSS = """
body{margin:0;padding:24px;font:14px/1.5 Pretendard,"Malgun Gothic",sans-serif;color:#222;background:#f4f5f7}
h1{font-size:20px;color:#002B5C;margin:0 0 4px}
h2{font-size:16px;color:#002B5C;margin:24px 0 8px}
.meta{font-size:12px;color:#666}
.tabs{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:16px 0}
.tab{display:block;min-height:44px;background:#fff;border:2px solid #d8dce2;border-radius:8px;padding:10px 16px;color:inherit;text-decoration:none}
.tab:hover{border-color:#8a9bb3}
.tab b{display:block;font-size:28px;line-height:1.2;color:#002B5C}
.tab span{display:block;font-size:14px;font-weight:700;color:#002B5C}
.tab small{display:block;font-size:12px;color:#555}
.tab.on{border-color:#002B5C;background:#eef2f8}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:12px}
.card{background:#fff;border:1px solid #d8dce2;border-left:6px solid #002B5C;border-radius:8px;padding:12px 16px}
.card.review{border-left-color:#B7791F}
.card.done{border-left-color:#2F7D4F;background:#f4f8f5}
.card.done dl{color:#666}
.card h3{font-size:18px;line-height:1.35;margin:0 0 6px;color:#002B5C}
.card.done h3{color:#3d4a5a}
.ids{margin:0 0 6px;font-size:13px;color:#555}
.st{margin:0 0 6px;font-size:13px;font-weight:700}
.st.run{color:#002B5C}
.st.review{color:#7a4d00}
.ok{color:#1f6a40;font-weight:700}
.stale{margin:12px 0 0;padding:10px 14px;border:2px solid #B7791F;border-radius:8px;background:#fff;color:#7a4d00;font-weight:700}
.card dl{display:grid;grid-template-columns:72px 1fr;gap:2px 8px;margin:0;font-size:13px}
.card dt{color:#666}.card dd{margin:0;word-break:break-all}
.warn{color:#002B5C;font-weight:700}
table{width:100%;border-collapse:collapse;background:#fff;font-size:13px}
th,td{border:1px solid #d8dce2;padding:6px 8px;text-align:left;vertical-align:top}
th{background:#e9ecf0;color:#333}
tr.done td{color:#777}
td.n{white-space:nowrap}
details{margin-top:16px}
summary{cursor:pointer;min-height:44px;line-height:44px;font-size:14px;color:#002B5C;font-weight:700}
.none{color:#777;font-size:13px}
"""


# 묵은 경고(11/26 Q-61): 정적 HTML은 지금 시각을 모르고, 60초 새로 읽기는 같은 파일을 다시 읽어 CSS 타이머도 매번 처음부터라
# 브라우저 시계로 「만든 때」와 비교하는 짧은 인라인 스크립트 하나만 둔다(바깥 자원·fetch·innerHTML 없음, 문구는 textContent).
STALE_MIN = 5
STALE_JS = ("(function(){var p=document.getElementById('stale');if(!p)return;var t=+p.getAttribute('data-made');"
            "function f(){var m=Math.floor((Date.now()-t)/60000);if(m>=" + str(STALE_MIN) + "){p.hidden=false;"
            "p.textContent='⚠ '+m+'분 전 내용 — 자동 새로 만들기가 멈췄어요. "
            "board.py html로 다시 만들거나 작업 스케줄러(board.py schedule)를 확인하세요';}}"
            "f();setInterval(f,30000);})();")


def e(s):
    return H.escape(str(s if s not in (None, "") else "–"))


NOWRAP = {"번호", "상태", "출처", "세션", "갱신", "#", "작성자", "만든 때", "답", "답한 때", "올린 때"}


def html_table(cols, rows, cls=None):
    if not rows:
        return '<p class="none">–</p>'
    out = ["<table><tr>" + "".join(f"<th>{e(c)}</th>" for c in cols) + "</tr>"]
    for r in rows:
        c = f' class="{cls(r)}"' if cls and cls(r) else ""
        out.append(f"<tr{c}>" + "".join(f"<td{' class=n' if k in NOWRAP else ''}>{e(r.get(k, ''))}</td>"
                                        for k in cols) + "</tr>")
    return "\n".join(out) + "</table>"


def stamp(iso):
    """gh의 createdAt(UTC ISO) → 이 PC 시각 「MM/DD HH:MM」."""
    try:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).astimezone().strftime("%m/%d %H:%M")
    except ValueError:
        return str(iso or "–")


def ids_line(st, r):
    """창 제목 밑 한 줄: 「PR #345 · VCC-login-limit · Q-53」(없는 것은 뺌)."""
    m = PR_RE.search(r.get("상태", ""))
    q = q_of_row(st, r)
    return " · ".join(x for x in (f"PR #{m.group(1)}" if m else "", r["폴더"], q["번호"] if q else "") if x)


def card_html(st, r, states):
    """카드 = 제목 + 한 줄(PR·폴더·Q). 끝난 창은 그 한 줄 앞에 「✓ 병합됨」만(왼쪽 초록 띠 + ✓ + 글 — 색만으로 가르지 않음).
    진행 중·검토 대기는 상태 한 줄 + 파일, 남은 할 일(결정요망·안 보낸 전달)이 있을 때만 그 칸."""
    ph, shown = phase(r, states)
    ids = e(ids_line(st, r))
    alerts = [(k, r.get(k, "–")) for k in ("결정요망", "전달 대기")
              if (k == "결정요망" and r.get(k, "–") not in EMPTY) or (k == "전달 대기" and unsent(r))]
    if ph == "done":
        word = "병합됨" if "병합됨" in shown else ("닫힘(병합 안 함)" if "닫힘" in shown else "완료")
        body = f'<p class="ids"><span class="ok">✓ {e(word)}</span> · {ids}</p>'
        items = alerts
    else:
        where = "" if mine(r) else f" · {r.get('PC', '–')}"
        st_txt = f"{BADGE[ph]} · {shown if ph == 'review' else r['상태']} · {r['갱신']}{where}"
        body = f'<p class="ids">{ids}</p><p class="st {ph}">{e(st_txt)}</p>'
        items = [("파일", r["파일"])] + alerts
    dl = "".join(f"<dt>{e(k)}</dt><dd{' class=warn' if k != '파일' else ''}>{e(v)}</dd>" for k, v in items)
    return (f'<div class="card {ph}" data-folder="{e(r["폴더"])}"><h3>{e(title_of(r))}</h3>{body}'
            + (f"<dl>{dl}</dl>" if dl else "") + "</div>")


def make_html(st, path=None, pages=None):
    """탭 파일 4개를 쓴다. pages(dict)를 주면 같은 내용을 서버용(탭 주소 /·/queue…, 자동 새로 읽기·묵은 경고 없음)으로 담는다."""
    path = Path(path or html_path())
    rows = st["rows"]
    states = pr_states(rows)
    prs = all_prs()
    keep, past = shown_rows(st, states)
    groups = {k: [r for r in keep if phase(r, states)[0] == k] for k in PHASES}
    view = queue_view(st, states)
    qorder = {"시작됨": 0, "승인": 1, "제안": 2}
    qtop = sorted([x for x in view if x["상태"] in qorder], key=lambda x: qorder[x["상태"]])
    qrev = [x for x in view if x["상태"] == "검토 대기"]
    qend = [x for x in view if x["상태"] not in qorder and x["상태"] != "검토 대기"]
    waitq = [x for x in view if x["상태"] in ("제안", "승인")]
    opend = [x for x in st["decide"] if x["답"] in EMPTY]
    answered = [x for x in st["decide"] if x["답"] not in EMPTY]
    open_list = None if prs is None else [p for p in prs if str(p.get("state", "")).upper() == "OPEN"]
    c = st.get("chief")
    chief = f"총괄: {c['name']} ({c['pc']}, {c['at']})" if c else "총괄: –"
    unsent_n = sum(1 for r in rows if unsent(r))

    tab_n = {"win": len(groups["run"]), "queue": len(waitq), "decide": len(opend),
             "pr": "–" if open_list is None else len(open_list)}
    tab_sub = {"win": f"진행 중 · 검토 대기 {len(groups['review'])} · 닫아도 돼요 {len(groups['done'])}",
               "queue": f"제안·승인 · 시작됨 {sum(1 for x in view if x['상태'] == '시작됨')} · 검토 대기 {len(qrev)}",
               "decide": f"답 기다림 · 답함 {len(answered)}",
               "pr": "팀 전체" if open_list is not None else "gh 못 읽음"}
    live = live_sessions()
    done_head = ("닫아도 돼요 — 이 PC에서 열린 창 · 병합·닫힘·완료" if live is not None
                 else f"닫아도 돼요 — 병합·닫힘·완료 (창 생존 판별 못 함: 폴더 있음 + {FALLBACK_HOURS}시간 이내)")
    win = []
    for k, head in (("run", "진행 중"), ("review", "검토 대기 — PR 열림"), ("done", done_head)):
        win.append(f"<h2>{e(head)} {len(groups[k])}</h2>")
        win.append('<div class="cards">' + "".join(card_html(st, r, states) for r in groups[k]) + "</div>"
                   if groups[k] else '<p class="none">–</p>')
    if past:
        prow = [{"창 제목": title_of(r), "한 줄": ids_line(st, r), "상태": phase(r, states)[1], "갱신": r["갱신"],
                 "PC": r.get("PC", "–")} for r in past]
        win.append(f"<details><summary>지난 창 {len(past)}개 — 이미 닫혔거나 다른 PC 창(정리는 milend)</summary>"
                   f"{html_table(['창 제목', '한 줄', '상태', '갱신', 'PC'], prow, lambda x: 'done')}</details>")
    if states is None and any(PR_RE.search(r["상태"]) for r in rows):
        win.insert(0, '<p class="none">gh를 못 읽어 PR 병합 여부를 대조하지 못했어요(「PR #n 올림」은 검토 대기로 둠).</p>')

    qrev_html = (f"<h2>검토 대기 — PR 열림 {len(qrev)}</h2>\n{html_table(QCOLS, qrev, lambda x: '')}" if qrev else "")
    qend_html =(f"<details><summary>완료·반려 {len(qend)}줄 보기</summary>{html_table(QCOLS, qend, lambda x: 'done')}</details>"
                 if qend else "")
    dec_html = html_table(DCOLS, opend) + (
        f"<details><summary>답한 것 {len(answered)}줄 보기</summary>{html_table(DCOLS, answered, lambda x: 'done')}</details>"
        if answered else "")
    if open_list is None:
        pr_html = '<p class="none">gh를 못 읽음(gh auth status 확인) — 열린 PR 모름</p>'
    else:
        def board_of(p):
            for r in rows:
                m = PR_RE.search(r["상태"])
                if r["브랜치"] == p.get("headRefName") or (m and int(m.group(1)) == p.get("number")):
                    return r["폴더"]
            return "–"
        pr_rows = [{"#": p.get("number"), "제목": p.get("title"), "작성자": (p.get("author") or {}).get("login", "–"),
                    "만든 때": stamp(p.get("createdAt")), "상태판 창": board_of(p)}
                   for p in sorted(open_list, key=lambda p: p.get("number") or 0)]
        pr_html = html_table(["#", "제목", "작성자", "만든 때", "상태판 창"], pr_rows)

    panels = {
        "win": "".join(win),
        "queue": f"<h2>대기 작업 — 시작됨 · 승인 · 제안</h2>\n{html_table(QCOLS, qtop, lambda x: '')}\n{qrev_html}\n{qend_html}",
        "decide": f"<h2>결정요망 — 답 기다림</h2>\n{dec_html}",
        "pr": f"<h2>열린 PR</h2>\n{pr_html}",
    }
    made = int(time.time() * 1000)

    def page(k, label, serving):
        tabs = "".join(
            f'<a class="tab{" on" if j == k else ""}" href="{SERVE_PATH[j] if serving else quote(tab_path(path, j).name)}" data-tab="{j}">'
            f'<b>{e(tab_n[j])}</b><span>{e(t)}</span><small>{e(tab_sub[j])}</small></a>' for j, t in TABS)
        if serving:       # 서버: 새로고침이 곧 갱신이라 자동 새로 읽기·묵은 경고는 뺀다
            refresh, stale, how = "", "", "새로고침하면 최신 · 이 PC 서버"
        else:
            refresh = '<meta http-equiv="refresh" content="60">\n'
            stale = (f'<p class="stale" id="stale" data-made="{made}" hidden>⚠ 만든 지 {STALE_MIN}분 넘음 — 자동 새로 만들기가 멈췄을 수 있어요(board.py html로 다시 만들기)</p>\n'
                     f'<script>{STALE_JS}</script>\n')
            how = "60초마다 새로 읽음(고른 탭 그대로)"
        gh = f" · {GH_NOTE}" if GH_NOTE else ""
        return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
{refresh}<meta name="viewport" content="width=device-width,initial-scale=1">
<title>VCC 상태판 · {e(ME or path.stem)} · {e(label)}</title><style>{CSS}</style></head><body>
<h1>VCC 상태판 · {e(ME or path.stem)}</h1>
<div class="meta">{e(chief)} · 만든 때 {e(now())} ({e(HOST)}) · {how}{f" · 안 보낸 전달 {unsent_n}건" if unsent_n else ""}{gh}</div>
{stale}<nav class="tabs">{tabs}</nav>
<section class="panel" id="{k}">
{panels[k]}</section>
</body></html>
"""

    for k, label in TABS:
        out = tab_path(path, k)
        tmp = out.with_suffix(".tmp.html")
        tmp.write_text(page(k, label, False), encoding="utf-8")
        os.replace(tmp, out)
        if pages is not None:
            pages[k] = page(k, label, True)
    return path


def cmd_html(args):
    p = make_html(load())
    print(f"만듦: {p}")


# ---------- 자동 새로 만들기(11/26 Q-61) ----------
# 상태판 md는 명령이 돌 때만 바뀌지만 PR 병합·창 닫힘은 그 밖에서 일어나니, html을 주기적으로 다시 만든다.
#   schedule --install [--every 2]  Windows 작업 스케줄러에 「VCC-board-html」(N분마다 pythonw board.py html, gh 1번) 등록
#   schedule --remove / schedule    지우기 / 등록 상태와 등록 명령 보기     (등록은 시스템 설정 — 미리 승인 뒤에만)
#   watch [--every 120]            작업 스케줄러 없이 이 창(백그라운드)에서 N초마다 html. 창을 닫으면 멈춘다
TASK_NAME = "VCC-board-html"


def schedule_cmd(every):
    pyw = Path(sys.executable).with_name("pythonw.exe")
    exe = pyw if pyw.exists() else Path(sys.executable)
    me = REPO / ".claude" / "skills" / "milwork" / "board.py"     # worktree가 아니라 본 저장소 것(병합되면 저절로 새 판)
    return ["schtasks", "/create", "/f", "/tn", TASK_NAME, "/sc", "minute", "/mo", str(every),
            "/tr", f'"{exe}" -X utf8 "{me}" html']


def cmd_schedule(args):
    if os.name != "nt":
        raise SystemExit("작업 스케줄러는 Windows에서만 — 다른 OS는 board.py watch를 쓴다")
    if args.install:
        r = subprocess.run(schedule_cmd(args.every), capture_output=True, text=True, errors="replace", **NOWIN)
        print((r.stdout or r.stderr).strip())
        sys.exit(0 if r.returncode == 0 else 1)
    if args.remove:
        r = subprocess.run(["schtasks", "/delete", "/f", "/tn", TASK_NAME], capture_output=True, text=True,
                           errors="replace", **NOWIN)
        print((r.stdout or r.stderr).strip())
        sys.exit(0 if r.returncode == 0 else 1)
    r = subprocess.run(["schtasks", "/query", "/tn", TASK_NAME, "/fo", "list"], capture_output=True, text=True,
                       errors="replace", **NOWIN)
    print(f"{TASK_NAME}: " + ("등록됨" if r.returncode == 0 else "등록 안 됨"))
    print("등록 명령: board.py schedule --install --every 2   (내부: " + " ".join(schedule_cmd(2)) + ")")


def cmd_watch(args):
    every = max(30, args.every)
    print(f"{every}초마다 html 새로 만들기 (멈추려면 이 창의 백그라운드 작업을 끈다)", flush=True)
    while True:
        _PRS.clear()
        _LIVE.clear()
        try:
            make_html(load())
        except Exception as ex:          # 드라이브·gh가 잠깐 안 돼도 다음 차례에 다시
            print(f"{now()} 못 만듦: {ex}", flush=True)
        if args.once:
            return
        time.sleep(every)


# ---------- 상태판 서버(11/26 Q-62) ----------
# milstart가 백그라운드로 켠다(작업 스케줄러·방화벽 설정 없음). 127.0.0.1에서만 열린다(바깥 기기 접근 없음, functions/serve_screens.py와 같은 원칙).
# 요청마다 상태판을 새로 읽어 html을 만들고(드라이브 html 파일도 함께 갱신) 그 탭을 돌려준다. gh 결과만 SERVE_GH_SEC초 캐시한다.
# gh가 안 되면 지난 결과를 보이고 「gh 못 읽음」 한 줄을 적는다. 같은 포트에 board 서버가 이미 있으면 새로 띄우지 않는다.
SERVE_PORT = 8765
SERVE_GH_SEC = 25
SERVE_PATH = {"win": "/", "queue": "/queue", "decide": "/decide", "pr": "/pr"}
SERVE_PING = "VCC-board"
_serve_lock = threading.Lock()
_serve_last = [0.0]          # 마지막 gh 읽기 시각(time.time)
_GOOD_PRS = []               # 마지막으로 gh가 잘 읽은 결과(없으면 빈 목록)


def serve_refresh():
    """gh 결과를 SERVE_GH_SEC마다 한 번만 새로 읽는다. 못 읽으면 지난 결과로 대신하고 GH_NOTE에 적는다. _serve_lock 안에서 부른다."""
    global GH_NOTE
    if time.time() - _serve_last[0] < SERVE_GH_SEC:
        return
    _serve_last[0] = time.time()
    _PRS.clear(); _LIVE.clear()
    prs = all_prs()
    if prs is not None:
        _GOOD_PRS[:] = [prs]
        GH_NOTE = ""
    elif _GOOD_PRS:
        _PRS[0] = _GOOD_PRS[0]
        GH_NOTE = f"gh 못 읽음 — {now()} 기준 지난 PR 결과 보여 줌"
    else:
        GH_NOTE = "gh 못 읽음"


class _ServeHandler(BaseHTTPRequestHandler):
    server_version = "VCC-board"

    def log_message(self, *a):          # 콘솔을 요청마다 어지럽히지 않는다
        pass

    def do_GET(self):
        route = self.path.split("?", 1)[0]
        if route == "/__board":
            return self._send(200, SERVE_PING, "text/plain")
        key = next((k for k, p in SERVE_PATH.items() if p == route), None)
        if key is None:
            return self._send(404, "없는 주소 — / · /queue · /decide · /pr", "text/plain")
        try:
            with _serve_lock:
                serve_refresh()
                pages = {}
                make_html(load(), pages=pages)
        except Exception as ex:          # 드라이브가 잠깐 안 되면 이 요청만 실패(다음 새로고침에 다시)
            return self._send(500, f"상태판을 만들지 못함: {ex}", "text/plain")
        self._send(200, pages[key], "text/html")

    def _send(self, code, body, ctype):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", f"{ctype}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)


class _Server(ThreadingHTTPServer):
    allow_reuse_address = False        # Windows의 SO_REUSEADDR은 이미 듣는 포트도 잡게 두므로 끈다(중복 서버 방지)


def make_server(port):
    """127.0.0.1에만 묶는다. port 0이면 빈 포트."""
    return _Server(("127.0.0.1", port), _ServeHandler)


def _fetch(port, route):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))      # 시스템 프록시를 거치지 않는다
    with opener.open(f"http://127.0.0.1:{port}{route}", timeout=10) as r:
        return r.read().decode("utf-8", "replace")


def _is_board(port):
    try:
        return _fetch(port, "/__board").strip() == SERVE_PING
    except (OSError, ValueError):
        return False


def cmd_serve(args):
    url = f"http://localhost:{args.port}/"
    if _is_board(args.port):
        print(f"이미 켜져 있음: {url} (새로고침하면 최신)")
        return
    try:
        srv = make_server(args.port)
    except OSError:
        if _is_board(args.port):                   # 그사이 다른 창이 먼저 켰다
            print(f"이미 켜져 있음: {url} (새로고침하면 최신)")
            return
        print(f"포트 {args.port}은 다른 프로그램이 쓰는 중 — board.py serve --port <다른 번호>", file=sys.stderr)
        sys.exit(1)
    print(f"상태판 서버: {url} (127.0.0.1만, 새로고침하면 최신)", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


# ---------- 자체 시험 ----------
def cmd_selftest(args):
    tmp = Path(tempfile.mkdtemp(prefix="vcc-board-"))
    repo = tmp / "repo"          # 「나」를 바꿔 보는 임시 저장소(본 저장소 설정은 건드리지 않는다)
    subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True)

    def gitc(key, val):
        subprocess.run(["git", "-C", str(repo), "config", key, val], check=True, capture_output=True)

    gitc("vcc.me", "미리"); gitc("user.name", "nobody"); gitc("user.email", "n@example.invalid")
    env = dict(os.environ, VCC_BOARD=str(tmp), VCC_BOARD_NOGH="1", PYTHONUTF8="1", VCC_REPO=str(repo), VCC_BOARD_LIVE="")
    me = [sys.executable, "-X", "utf8", str(Path(__file__).resolve())]
    fails = []

    def run(*a, code=0, first=None, has=None, err=None):
        r = subprocess.run(me + list(a), capture_output=True, text=True, encoding="utf-8", env=env)
        out = r.stdout.strip()
        ok = r.returncode == code
        if first is not None and (out.splitlines() or [""])[0] != first:
            ok = False
        if has is not None and has not in out:
            ok = False
        if err is not None and err not in r.stderr:
            ok = False
        print(("통과 " if ok else "실패 ") + " ".join(a) + f"  → {r.returncode} {out.splitlines()[:1]}")
        if not ok:
            fails.append(f"{' '.join(a)}: 코드 {r.returncode}(기대 {code}) · {out!r} · {r.stderr.strip()!r}")
        return out

    def board(who="미리"):
        return load(tmp / f"board-{who}.md")

    a, gone = "VCC-selftest-a", "VCC-selftest-zzz-없음"
    run("add", a, "--branch", "miri/st", "--who", "미리", "--task", "시험", "--files", "x/a.py")
    run("add", gone, "--branch", "miri/zz", "--who", "미리", "--task", "없는 폴더", "--files", "z.py")
    run("queue", "add", "--task", "– 겹치는 일", "--files", "x/a.py", "--from", "milstart", "--session", "s1",
        first="Q-1 제안")
    run("queue", "add", "--task", "58 안 겹치는 일", "--files", "y.py", "--from", "파생", first="Q-2 제안")
    run("queue", "add", "--task", "– 미리 직접(옛 값)", "--files", "w.py", "--from", "미리", first="Q-3 승인")
    run("queue", "add", "--task", "– 직접", "--files", "v.py", "--from", "직접", first="Q-4 승인")
    run("queue", "approve", "Q-1", code=2, has="겹침: x/a.py")
    run("queue", "take", "Q-1", "--folder", "VCC-q1", code=2)
    run("queue", "approve", "Q-2", first="Q-2 승인")
    run("queue", "take", "Q-2", "--folder", "VCC-q2", "--session", "s2", first="Q-2 시작됨 → VCC-q2")
    run("queue", "reject", "Q-1", "--why", "겹침", first="Q-1 반려")
    run("queue", "take", "Q-1", "--folder", "VCC-q1", code=2)
    run("queue", has="Q-2 시작됨")
    # 완료: 시작됨·승인에서만, 반려는 안 바뀜, 겹침에서 빠짐
    run("queue", "done", "Q-1", code=2)                      # 반려 → 완료 불가(--force만)
    run("queue", "add", "--task", "– 겹침 시험", "--files", "q2/f.py", "--from", "직접", first="Q-5 승인")
    run("queue", "take", "Q-5", "--folder", "VCC-q5", first="Q-5 시작됨 → VCC-q5")   # 창 줄 없는 시작됨
    run("queue", "add", "--task", "– 겹침 시험2", "--files", "q2/f.py", "--from", "milstart", first="Q-6 제안")
    run("queue", "approve", "Q-6", first="Q-6 승인")         # 창 줄 없는 시작됨은 세지 않음
    run("queue", "done", "Q-2", "--pr", "258", first="Q-2 완료")
    run("queue", "done", "Q-6", first="Q-6 완료")             # 승인 → 완료
    run("queue", "add", "--task", "– 겹침 시험3", "--files", "w.py", "--from", "milstart", first="Q-7 제안")
    run("queue", "approve", "Q-7", code=2, has="[Q-3]")      # 승인 상태는 아직 센다
    run("queue", "done", "Q-3", first="Q-3 완료")
    run("queue", "approve", "Q-7", first="Q-7 승인")         # 완료는 세지 않음
    run("add", "VCC-q5", "--branch", "miri/q5", "--who", "미리", "--task", "q5", "--files", "q5.py")
    run("remove", "VCC-q5", has="Q-5 시작됨 → 완료")          # remove하면 맡은 큐 줄이 완료로
    if {x["번호"]: x for x in board()["queue"]}["Q-5"]["상태"] != "완료":
        fails.append("remove 뒤 Q-5가 완료가 아님")
    q = {x["번호"]: x for x in board()["queue"]}
    if not (q["Q-2"]["상태"] == "완료" and "PR #258 병합" in q["Q-2"]["메모"]):
        fails.append(f"queue done 표 내용: {q['Q-2']}")
    if not (q["Q-1"]["메모"].startswith("반려: 겹침") and q["Q-2"]["폴더"] == "VCC-q2" and q["Q-2"]["세션"] == "s2"):
        fails.append(f"queue 표 내용: {q}")
    run("decide", "add", "--folder", a, "--session", "작업창A", "--q", "어느 쪽?", "--options", "A(추천) 하나; B 둘",
        first="D-1")
    run("decide", "add", "--folder", a, "--session", "작업창A", "--q", "또?", "--options", "A; B", first="D-2")
    if find(board()["rows"], a)["결정요망"] != "D-1; D-2":
        fails.append(f"결정요망 열: {find(board()['rows'], a)}")
    run("decide", "answer", "D-1", "--a", "A", first="작업창A")
    if find(board()["rows"], a)["결정요망"] != "D-2":
        fails.append(f"answer 뒤 결정요망 열: {find(board()['rows'], a)}")
    run("decide", first="D-2 [VCC-selftest-a] 작업창A · 또? — A; B · 답 없음")
    run("chief", code=1)
    run("chief", "--set", "총괄창", has="총괄: 총괄창 (")
    run("chief", first="총괄창")
    run("check", "x/a.py", code=2)
    run("check", "x/a.py", "--me", a, first="겹치는 파일 없음")
    run("html", has="board-미리.html")
    h = "".join(tab_path(tmp / "board-미리.html", k).read_text(encoding="utf-8") for k, _ in TABS)
    for need in ('http-equiv="refresh" content="60"', "총괄: 총괄창", "D-2", "Q-3", "<h2>열린 PR</h2>", "상태판 · 미리",
                 "gh를 못 읽음"):
        if need not in h:
            fails.append(f"board.html에 {need!r} 없음")
    if re.search(r"<script|fetch\(|https?://", h.replace(f"<script>{STALE_JS}</script>", ""), re.I):
        fails.append("board.html에 묵은 경고 밖의 스크립트·바깥 자원")
    if re.search(r"font(-size)?:[^;}]*\b([0-9]|1[01])px", h):
        fails.append("board.html에 12px 미만 글자")
    run("chief", "--set", "–")
    run("chief", code=1)
    run("set", a, "--handoff", "원우에게: 시험")
    run("remove", a, code=1)
    run("set", a, "--sent")
    run("remove", a, first=f"지움: {a}")
    run("prune", first=f"지운 줄: {gone}")
    if board()["rows"]:
        fails.append(f"remove·prune 뒤 줄 남음: {board()['rows']}")
    for x in ("board.md", "board.html", "board.lock", "board-미리.lock"):
        if (tmp / x).exists():
            fails.append(f"이름 없는 파일·남은 잠금: {x}")
    # vcc.me를 바꾸면 파일 이름이 따라간다 — 남의 파일은 읽지 않는다
    run("add", "VCC-st-m", "--branch", "miri/st", "--who", "미리", "--task", "미리 줄", "--files", "m.py")
    gitc("vcc.me", "원우")
    run("add", "VCC-st-w", "--branch", "wonwoo/st", "--who", "원우", "--task", "원우 줄", "--files", "x/a.py")
    run("check", "m.py", first="겹치는 파일 없음")   # 미리 파일의 m.py 줄은 안 봄
    run("list", has="[VCC-st-w]")
    if not find(board("원우")["rows"], "VCC-st-w") or find(board()["rows"], "VCC-st-w"):
        fails.append("vcc.me 원우: board-원우.md에 줄이 없거나 board-미리.md에 들어감")
    if not (tmp / "board-원우.html").exists():
        fails.append("vcc.me 원우: board-원우.html 없음")
    if "원우 줄" in (tmp / "board-미리.html").read_text(encoding="utf-8"):
        fails.append("vcc.me 원우: board-미리.html에 원우 줄")
    gitc("vcc.me", "모름")      # 모르는 값 + 이름·메일로도 못 정함 → 종료코드 1 + 안내
    run("list", code=1, err="git config vcc.me 원우")
    gitc("vcc.me", "")
    gitc("user.email", "mirikang@example.invalid")   # vcc.me 없으면 메일로 짐작
    run("list", first="[VCC-st-m] miri/st · 미리 · 미리 줄  ← 폴더 없음(병합·삭제됐으면 remove/prune)")
    # 이름 없는 board.md → board-미리.md (미리만)
    ren = tmp / "ren"
    ren.mkdir()
    (ren / "board.md").write_text("총괄: –\n", encoding="utf-8")
    (ren / "board.html").write_text("<p>옛</p>", encoding="utf-8")
    if rename_unnamed(ren / "board-원우.md", "원우") or not (ren / "board.md").exists():
        fails.append("이름 바꿈: 원우가 board.md를 건드림")
    if not rename_unnamed(ren / "board-미리.md", "미리") or (ren / "board.md").exists() \
            or not (ren / "board-미리.md").exists() or not (ren / "board-미리.html").exists():
        fails.append("이름 바꿈: board.md → board-미리.md 실패")
    # 옛 상태판 이전(8열 → 10열)
    old, new = tmp / "old" / "VCC-board.md", tmp / "new" / "board.md"
    old.parent.mkdir()
    old.write_text("# 옛\n\n| " + " | ".join(OLD_COLS) + " |\n|" + "---|" * 8 +
                   "\n| VCC-old | miri/old | 미리 | 옛 줄 | a.py | PR 올림 | 11/25 11:57 | – |\n", encoding="utf-8")
    if not migrate(old, new) or not (tmp / "old" / "VCC-board-이전.md").exists() or old.exists():
        fails.append("이전: 파일 이동 실패")
    r = find(load(new)["rows"], "VCC-old")
    if not r or r["PC"] != HOST or r["결정요망"] != "–" or r["상태"] != "PR 올림":
        fails.append(f"이전: 줄 내용 {r}")
    if migrate(old, new):
        fails.append("이전: 두 번 옮김")
    # 지난 줄 정리: 미래 도장, 오래된 완료·반려만, 답한 결정요망, 번호 이어 가기
    at = datetime(2027, 1, 1, 9, 0)
    for stamp, want in (("12/31 08:00", None), ("01/01 08:00", timedelta(hours=1)),
                        ("01/01 10:00", timedelta(hours=-1)), ("–", None), ("13/40 00:00", None)):
        if age(stamp, at) != want:
            fails.append(f"age({stamp!r}) = {age(stamp, at)} (기대 {want})")
    cl = tmp / "clean"
    cl.mkdir()
    env["VCC_BOARD"] = str(cl)
    gitc("vcc.me", "미리")
    f = cl / "board-미리.md"
    past = (datetime.now() - timedelta(days=3)).strftime("%m/%d %H:%M")
    for n in range(1, 6):
        run("queue", "add", "--task", f"– 정리 {n}", "--files", f"c{n}.py", "--from", "직접", first=f"Q-{n} 승인")
    run("queue", "done", "Q-1", first="Q-1 완료")          # 오래된 완료
    run("queue", "reject", "Q-2", "--why", "x", first="Q-2 반려")   # 오래된 반려
    run("queue", "done", "Q-5", first="Q-5 완료")          # 방금 완료 → 남김
    run("decide", "add", "--folder", a, "--session", "s", "--q", "1?", "--options", "A; B", first="D-1")
    run("decide", "add", "--folder", a, "--session", "s", "--q", "2?", "--options", "A; B", first="D-2")
    run("decide", "answer", "D-2", "--a", "A", first="s")
    run("decide", "add", "--folder", a, "--session", "s", "--q", "방금?", "--options", "A; B", first="D-3")
    run("decide", "answer", "D-3", "--a", "A", first="s")      # 방금 답함 → 남김
    st = load(f)
    by_id(st["decide"], "D-2")["답한 때"] = past
    for x in st["queue"]:
        if x["번호"] != "Q-5":              # Q-3·Q-4는 오래됐어도 승인 상태라 남김
            x["갱신"] = past
    save(st, f, html=False)
    run("clean", "--days", "1", first="정리: 대기 작업 2줄 · 결정요망 1줄 (Q-1, Q-2, D-2)")
    left = [x["번호"] for x in load(f)["queue"] + load(f)["decide"]]
    if left != ["Q-3", "Q-4", "Q-5", "D-1", "D-3"]:
        fails.append(f"clean 뒤 남은 줄: {left}")
    run("clean", first="정리: 대기 작업 0줄 · 결정요망 0줄")
    for i in ("Q-3", "Q-4"):
        run("queue", "done", i, first=f"{i} 완료")
    run("decide", "answer", "D-1", "--a", "B", first="s")
    def age_all():
        st = load(f)
        for x in st["queue"]:
            x["갱신"] = past
        for x in st["decide"]:
            x["답한 때"] = past
        save(st, f, html=False)

    # 폴더 줄이 남아 있으면 답한 지 오래돼도 결정요망을 남긴다
    run("add", a, "--branch", "miri/st", "--who", "미리", "--task", "진행 중")
    age_all()
    run("clean", first="정리: 대기 작업 2줄 · 결정요망 0줄 (Q-3, Q-4)")
    run("remove", a, first=f"지움: {a}")
    run("clean", first="정리: 대기 작업 0줄 · 결정요망 1줄 (D-1)")      # 가장 큰 번호 D-3은 남김
    left = [x["번호"] for x in load(f)["queue"] + load(f)["decide"]]
    if left != ["Q-5", "D-3"]:
        fails.append(f"clean: 가장 큰 번호 줄만 남아야 함: {left}")
    # 머리 줄을 지워도(옛 board.py 저장) 남은 줄에서 번호가 이어진다
    text = f.read_text(encoding="utf-8")
    f.write_text(re.sub(r"(?m)^마지막 번호: .*\n", "", text), encoding="utf-8")
    run("queue", "add", "--task", "– 이어서", "--from", "직접", first="Q-6 승인")
    run("decide", "add", "--folder", a, "--session", "s", "--q", "4?", "--options", "A; B", first="D-4")
    # 진행상황 자동 갱신·창 제목·닫아도 돼요·탭 4개 (11/26)
    tb = tmp / "tabs"
    tb.mkdir()
    env["VCC_BOARD"] = str(tb)
    fake = tmp / "prs.json"
    fake.write_text(json.dumps([
        {"number": 10, "state": "MERGED", "mergedAt": "2026-11-26T01:00:00Z", "title": "병합된 일",
         "author": {"login": "hufsiei"}, "createdAt": "2026-11-26T00:00:00Z", "headRefName": "miri/t-mrg"},
        {"number": 11, "state": "OPEN", "mergedAt": None, "title": "열린 일 제목",
         "author": {"login": "wwk"}, "createdAt": "2026-11-26T02:00:00Z", "headRefName": "miri/t-rev"},
        {"number": 12, "state": "CLOSED", "mergedAt": None, "title": "닫힌 일",
         "author": {"login": "hufsiei"}, "createdAt": "2026-11-26T03:00:00Z", "headRefName": "miri/t-cls"},
        {"number": 13, "state": "OPEN", "mergedAt": None, "title": "상태판에 없는 PR",
         "author": {"login": "minji"}, "createdAt": "2026-11-26T04:00:00Z", "headRefName": "minji/x"}],
        ensure_ascii=False), encoding="utf-8")
    env["VCC_BOARD_PRS"] = str(fake)
    for fo, status, fl, extra in (("VCC-t-mrg", "PR #10 올림", "m.py", []),
                                  ("VCC-t-rev", "PR #11 올림", "v.py", []),
                                  ("VCC-t-cls", "PR #12 올림", "c.py", []),
                                  ("VCC-t-fin", "완료: 재배포 abc(PR 없음)", "f.py", []),
                                  ("VCC-t-run", "고치는 중", "r.py", ["--title", "진행 창 제목"]),
                                  ("VCC-t-off", "PR #10 올림", "o.py", ["--session", "s-off"])):
        run("add", fo, "--branch", "miri/" + fo[4:], "--who", "미리", "--task", f"{fo[4:]} {fo[6:]} 작업 글",
            "--files", fl, "--status", status, *extra)
    run("set", "VCC-t-rev", "--title", "검토 창 제목")
    run("set", "VCC-t-mrg", "--session", "s-mrg")             # 세션 칸(덧칸 표)
    st = load(tb / "board-미리.md")
    find(st["rows"], "VCC-t-off")["PC"] = "사무실"             # 다른 PC의 끝난 창
    save(st, tb / "board-미리.md", html=False)
    # 세션이 살아 있는 끝난 창만 보인다: s-mrg(창 줄 세션), s-fin(큐 줄 세션), s-off는 다른 PC라 살아 있어도 안 보임
    env["VCC_BOARD_LIVE"] = "s-mrg,s-fin,s-off,s-rev"
    for fl in ("m.py", "c.py", "f.py"):
        run("check", fl, first="겹치는 파일 없음")          # 끝난 창 줄은 겹침 아님
    run("check", "v.py", code=2)                              # 열린 PR은 아직 겹침
    run("check", "r.py", code=2)
    run("queue", "add", "--task", "– 병합된 파일", "--files", "m.py", "--from", "milstart", first="Q-1 제안")
    run("queue", "approve", "Q-1", first="Q-1 승인")         # #303처럼 병합된 줄이 막지 않음
    run("queue", "add", "--task", "– 병합될 일", "--files", "-", "--from", "직접", first="Q-2 승인")
    run("queue", "take", "Q-2", "--folder", "VCC-t-mrg", first="Q-2 시작됨 → VCC-t-mrg")
    run("queue", "add", "--task", "– 끝난 재배포", "--files", "-", "--from", "직접", first="Q-3 승인")
    run("queue", "take", "Q-3", "--folder", "VCC-t-fin", "--session", "s-fin", first="Q-3 시작됨 → VCC-t-fin")
    run("queue", "add", "--task", "– 검토 중인 일", "--files", "-", "--from", "직접", first="Q-4 승인")
    run("queue", "take", "Q-4", "--folder", "VCC-t-rev", first="Q-4 시작됨 → VCC-t-rev")
    run("queue", "add", "--task", "– 진행 중인 일", "--files", "-", "--from", "직접", first="Q-5 승인")
    run("queue", "take", "Q-5", "--folder", "VCC-t-run", first="Q-5 시작됨 → VCC-t-run")
    lst = run("list")
    if "PR #10 올림 → PR #10 병합됨 · 닫아도 돼요" not in lst or "→ PR #11 열림 · 검토 대기" not in lst \
            or "창: 진행 중 1 · 검토 대기 1 · 닫아도 돼요 2 · 지난 창 2" not in lst \
            or "PR #12 닫힘(병합 안 함) · 지난 창(창 닫힘)" not in lst:
        fails.append(f"list 진행상황: {lst}")
    if lst.index("[VCC-t-run]") > lst.index("[VCC-t-rev]") or lst.index("[VCC-t-rev]") > lst.index("[VCC-t-mrg]"):
        fails.append("list 순서: 진행 중 → 검토 대기 → 끝남 아님")
    run("html")
    h = (tb / "board-미리.html").read_text(encoding="utf-8")
    cards = {m.group(1): m.group(0) for m in re.finditer(r'<div class="card [^"]*" data-folder="([^"]+)">.*?</div>', h)}
    # 닫힌 창은 안 보인다: 세션 없는 cls, 다른 PC의 off → 카드 없음, 접힌 「지난 창 2개」에만
    if "VCC-t-cls" in cards or "VCC-t-off" in cards or "지난 창 2개" not in h \
            or h.index("지난 창 2개") > h.index("VCC-t-cls") or h.index("VCC-t-cls") < h.index("<details>"):
        fails.append(f"닫힌 창·다른 PC 끝난 창이 카드로 보이거나 「지난 창 2개」 아래에 없음: {sorted(cards)}")
    # 카드 한 줄: 제목 밑 「PR #n · 폴더 · Q-n」, 끝난 창은 「✓ 병합됨」 한 줄, 풍선(badge)·「닫아도 돼요」 글 없음
    for fo, line in (("VCC-t-mrg", "✓ 병합됨</span> · PR #10 · VCC-t-mrg · Q-2"),
                     ("VCC-t-fin", "✓ 완료</span> · VCC-t-fin · Q-3")):
        cd = cards.get(fo, "")
        if not (line in cd and 'class="card done' in cd and "badge" not in cd and "닫아도" not in cd
                and "<dl>" not in cd and cd.count("<p ") == 1):
            fails.append(f"끝난 창 {fo}: 한 줄 카드 아님 {cd!r}")
    if "badge" in h:
        fails.append("html에 풍선(badge)이 남음")
    rv = cards.get("VCC-t-rev", "")
    if "◐ 검토 대기 · PR #11 열림" not in rv or '<p class="ids">PR #11 · VCC-t-rev · Q-4</p>' not in rv or "닫아도" in rv:
        fails.append(f"열린 PR 창: 「검토 대기」·한 줄 틀림 {rv!r}")
    rn = cards.get("VCC-t-run", "")
    if "닫아도" in rn or "<h3>진행 창 제목</h3>" not in rn or '<p class="ids">VCC-t-run · Q-5</p>' not in rn:
        fails.append(f"진행 중 창: 제목·한 줄 틀림 {rn!r}")
    if "<h3>검토 창 제목</h3>" not in rv or "<h3>mrg 작업 글</h3>" not in cards.get("VCC-t-mrg", ""):
        fails.append("창 제목: --title 또는 옛 줄 대신 글(슬러그 뺌) 틀림")
    if not (h.index('data-folder="VCC-t-run"') < h.index('data-folder="VCC-t-rev"') < h.index('data-folder="VCC-t-mrg"')):
        fails.append("html 창 순서: 진행 중 → 검토 대기 → 끝남 아님")
    # 탭 4개 = 파일 4개. 각 파일은 탭 링크 4개(자기 탭은 on)와 자기 패널 하나, 새로 읽어도 자기 파일
    pages = {k: tab_path(tb / "board-미리.html", k) for k, _ in TABS}
    for k, p in pages.items():
        if not p.exists():
            fails.append(f"탭 파일 없음: {p.name}")
            continue
        hp = p.read_text(encoding="utf-8")
        links = re.findall(r'<a class="tab( on)?" href="([^"]+)" data-tab="(\w+)">', hp)
        if [x[2] for x in links] != ["win", "queue", "decide", "pr"] \
                or [x[2] for x in links if x[0]] != [k] \
                or [x[1] for x in links] != [quote(q.name) for q in pages.values()]:
            fails.append(f"{p.name}: 탭 링크 4개·켜진 탭 틀림 {links}")
        if re.findall(r'<section class="panel" id="(\w+)">', hp) != [k]:
            fails.append(f"{p.name}: 패널이 자기 탭 하나가 아님")
        if 'http-equiv="refresh" content="60">' not in hp:
            fails.append(f"{p.name}: 60초 새로 읽기 없음(자기 파일을 다시 읽어야 탭 유지)")
        scripts = re.findall(r"<script([^>]*)>(.*?)</script>", hp, re.S | re.I)
        if len(scripts) != 1 or scripts[0][0].strip() or scripts[0][1] != STALE_JS \
                or re.search(r"\bon\w+=|fetch\(|https?://|innerHTML|insertAdjacentHTML", hp, re.I):
            fails.append(f"{p.name}: 묵은 경고 스크립트 하나 밖의 스크립트·바깥 자원")
        # 묵은 경고: 처음엔 숨김, 만든 때(밀리초)가 지금과 같고, 5분 기준
        mm = re.search(r'<p class="stale" id="stale" data-made="(\d+)" hidden>', hp)
        if not mm or abs(int(mm.group(1)) / 1000 - time.time()) > 120 or f"if(m>={STALE_MIN})" not in hp \
                or STALE_MIN != 5 or "textContent" not in hp:
            fails.append(f"{p.name}: 묵은 경고(만든 때·5분·textContent) 틀림")
        if re.search(r"font(-size)?:[^;}]*\b([0-9]|1[01])px", hp):
            fails.append(f"{p.name}: 12px 미만 글자")
    pr_part = pages["pr"].read_text(encoding="utf-8")
    if "열린 일 제목" not in pr_part or "VCC-t-rev" not in pr_part or "상태판에 없는 PR" not in pr_part \
            or "병합된 일" in pr_part:
        fails.append("열린 PR 탭 내용 틀림")
    q_part = pages["queue"].read_text(encoding="utf-8")
    top, _, rest = q_part.partition("<h2>검토 대기 — PR 열림")
    if "보기만 완료" not in q_part or ">Q-1<" not in top:
        fails.append("대기 작업 탭: 병합된 시작됨 줄이 완료(아래)로 안 보이거나 승인 줄이 위가 아님")
    # 큐 연동: 병합 PR(Q-2)·완료 창(Q-3) → 완료(접힌 곳), 열린 PR(Q-4) → 「검토 대기」(위 목록에서 빠짐), 진행 중(Q-5)은 위
    done_part = rest.partition("<details>")[2]
    if not rest or "Q-4" in top or "Q-4" not in rest.partition("<details>")[0] or "검토 대기</td>" not in rest \
            or "Q-5" not in top or any(f">{i}<" in top for i in ("Q-2", "Q-3")) \
            or not all(f">{i}<" in done_part for i in ("Q-2", "Q-3")):
        fails.append("대기 작업 탭: 병합·완료 → 완료, 열린 PR → 검토 대기(위 목록 밖), 진행 중 → 위 가 아님")
    qs = {x["번호"]: x["상태"] for x in load(tb / "board-미리.md")["queue"]}
    if [qs[i] for i in ("Q-2", "Q-3", "Q-4")] != ["시작됨"] * 3:
        fails.append(f"큐 연동은 보이기만이어야 하는데 파일이 바뀜: {qs}")
    # md 호환: 창 표 머리 줄은 #349 이전 10칸 그대로(옛 board.py가 읽음), 새 칸은 덧칸 표에
    text = (tb / "board-미리.md").read_text(encoding="utf-8")
    heads = [ln for ln in text.splitlines() if ln.startswith("| 폴더 |")]
    if heads != ["| " + " | ".join(BASE_COLS) + " |", "| " + " | ".join(XCOLS) + " |"]:
        fails.append(f"md 머리 줄: 창 표 10칸 + 덧칸 표가 아님 {heads}")
    old_tables = {tuple(OLD_COLS), tuple(BASE_COLS), tuple(QCOLS), tuple(DCOLS)}     # #349 이전 board.py가 아는 머리 줄
    if sum(1 for ln in text.splitlines() if ln.startswith("| ")
           and tuple(c.strip() for c in ln.strip().strip("|").split("|")) in old_tables) != 3:
        fails.append("옛 board.py가 창·대기 작업·결정요망 표를 못 알아봄")
    back = load(tb / "board-미리.md")
    if find(back["rows"], "VCC-t-mrg")["세션"] != "s-mrg" or find(back["rows"], "VCC-t-rev")["창 제목"] != "검토 창 제목":
        fails.append("덧칸 표(세션·창 제목)를 다시 못 읽음")
    ten = parse("| " + " | ".join(BASE_COLS) + " |\n|" + "---|" * 10 +
                "\n| VCC-ten | miri/ten | 미리 | ten-slug 열 칸 줄 | a.py | 시작 | 11/26 10:00 | PC | – | – |\n")
    if not ten["rows"] or ten["rows"][0]["창 제목"] != "–" or title_of(ten["rows"][0]) != "열 칸 줄":
        fails.append(f"옛 10열 파일 읽기: {ten['rows']}")
    more = parse("| " + " | ".join(BASE_COLS + ["창 제목", "나중 칸"]) + " |\n|" + "---|" * 12 +
                 "\n| VCC-m | b | 미리 | 작업 | a.py | 시작 | 11/26 10:00 | PC | – | – | 제목 | x |\n")
    if not more["rows"] or title_of(more["rows"][0]) != "제목":
        fails.append("#349가 만든 11칸 창 표(끝에 칸이 더 붙은 파일) 읽기 실패")
    # 창 생존 판별: 진짜 판별기는 이 프로세스를 살아 있다고 본다(Windows), 판별 못 하면 대안(폴더 있음 + 12시간 이내)
    if os.name == "nt" and _proc_start(os.getpid()) is None:
        fails.append("_proc_start: 이 프로세스를 못 찾음")
    if os.name == "nt" and _proc_start(2 ** 31 - 2) is not None:
        fails.append("_proc_start: 없는 pid를 살아 있다고 봄")
    fb = {"폴더": str(tmp), "PC": HOST, "갱신": now(), "세션": "–"}
    old_fb = dict(fb, 갱신=(datetime.now() - timedelta(hours=13)).strftime("%m/%d %H:%M"))
    gone_fb = dict(fb, 폴더=str(tmp / "없음"))
    nost = {"rows": [], "queue": []}
    saved = os.environ.get("VCC_BOARD_LIVE")
    os.environ["VCC_BOARD_LIVE"] = "?"
    _LIVE.clear()
    if not window_open(nost, fb) or window_open(nost, old_fb) or window_open(nost, gone_fb):
        fails.append("판별 못 할 때 대안(폴더 있음 + 12시간 이내) 틀림")
    _LIVE.clear()
    if saved is None:
        os.environ.pop("VCC_BOARD_LIVE")
    else:
        os.environ["VCC_BOARD_LIVE"] = saved
    if "/sc minute /mo 2" not in " ".join(schedule_cmd(2)) or "board.py\" html" not in schedule_cmd(2)[-1]:
        fails.append(f"schedule 등록 명령 틀림: {schedule_cmd(2)}")
    run("watch", "--once", has="초마다 html")
    # gh를 못 읽으면 예전처럼: 「PR #n 올림」은 겹침으로 세고, 오류로 멈추지 않는다
    env.pop("VCC_BOARD_PRS")
    run("check", "m.py", code=2)
    run("check", "f.py", first="겹치는 파일 없음")          # 「완료…」는 gh 없이도 끝남
    run("list", has="gh 못 읽음")
    # 상태판 서버(Q-62): 127.0.0.1만 묶임 · 요청마다 새로 만듦 · 두 번째 serve는 중복으로 안 띄움
    srv = make_server(0)
    if srv.server_address[0] != "127.0.0.1":
        fails.append(f"serve가 127.0.0.1이 아닌 주소에 묶임: {srv.server_address}")
    srv.server_close()
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        sport = s.getsockname()[1]
    sv = subprocess.Popen(me + ["serve", "--port", str(sport)], env=env,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        t0 = time.time()
        while not _is_board(sport) and time.time() - t0 < 15 and sv.poll() is None:
            time.sleep(0.2)
        if not _is_board(sport):
            fails.append("serve가 켜지지 않음")
        else:
            first_pg = _fetch(sport, "/queue")
            if 'href="/queue"' not in first_pg or 'http-equiv="refresh"' in first_pg:
                fails.append("serve 페이지: 탭 주소가 /queue가 아니거나 자동 새로 읽기가 남음")
            if "새 큐 시험" in first_pg:
                fails.append("serve 시험 전에 없는 큐 줄이 보임")
            run("queue", "add", "--task", "– 새 큐 시험", "--files", "r.py", "--from", "직접", has="승인")
            if "새 큐 시험" not in _fetch(sport, "/queue"):
                fails.append("serve가 큐 변경을 새로고침 뒤에 안 보여 줌")
            if "http-equiv" in _fetch(sport, "/"):
                fails.append("serve 페이지에 자동 새로 읽기(meta refresh)가 있음")
            r2 = subprocess.run(me + ["serve", "--port", str(sport)], env=env, capture_output=True,
                                text=True, encoding="utf-8", timeout=30)
            if r2.returncode != 0 or "이미 켜져 있음" not in r2.stdout:
                fails.append(f"두 번째 serve가 중복 확인 없이 뜸: {r2.returncode} {r2.stdout!r} {r2.stderr!r}")
            print(f"통과 serve 127.0.0.1:{sport} · 새로고침·중복 확인")
    finally:
        sv.kill()
        sv.wait()
    print(f"임시 폴더: {tmp}")
    if fails:
        print("\n실패 " + str(len(fails)) + "건:\n" + "\n".join(fails))
        sys.exit(1)
    print("selftest 통과")


def main():
    p = argparse.ArgumentParser(description="VCC 창 상태판 (드라이브 @VCC\\총괄\\board-<이름>.md, 이름은 git config vcc.me)")
    sp = p.add_subparsers(dest="cmd", required=True)
    sp.add_parser("list").set_defaults(fn=cmd_list)
    a = sp.add_parser("add")
    a.add_argument("folder"); a.add_argument("--branch", required=True); a.add_argument("--who", required=True)
    a.add_argument("--task", required=True); a.add_argument("--files", default=""); a.add_argument("--status")
    a.add_argument("--title", help="창 제목: 지시문 첫 줄에서 슬러그 뒤 글(VS Code 탭 「milwork …」에 보이는 글)")
    a.add_argument("--session", help="이 창의 세션 이름(ListAgents 첫 줄 「This session is <이름>」). 끝난 창이 열려 있는지 보는 데 쓴다")
    a.set_defaults(fn=cmd_add)
    s = sp.add_parser("set")
    s.add_argument("folder"); s.add_argument("--status"); s.add_argument("--files"); s.add_argument("--handoff")
    s.add_argument("--files-set", help="파일 목록을 통째로 바꿈(잘못 적은 것 고칠 때)")
    s.add_argument("--task"); s.add_argument("--branch"); s.add_argument("--title"); s.add_argument("--session")
    s.add_argument("--sent", action="store_true", help="지금 「전달 대기」 답장을 보냄으로 표시")
    s.set_defaults(fn=cmd_set)
    sp.add_parser("pending").set_defaults(fn=cmd_pending)
    c = sp.add_parser("check")
    c.add_argument("files", nargs="+"); c.add_argument("--me")
    c.set_defaults(fn=cmd_check)
    r = sp.add_parser("remove"); r.add_argument("folder")
    r.add_argument("--force", action="store_true", help="안 보낸 답장이 있어도 지움")
    r.set_defaults(fn=cmd_remove)
    sp.add_parser("prune").set_defaults(fn=cmd_prune)
    ch = sp.add_parser("chief"); ch.add_argument("--set", help="총괄 세션 이름(–면 비움)")
    ch.set_defaults(fn=cmd_chief)
    sp.add_parser("html").set_defaults(fn=cmd_html)
    sc = sp.add_parser("schedule", help="작업 스케줄러로 html 자동 새로 만들기(등록은 미리 승인 뒤)")
    sc.add_argument("--install", action="store_true"); sc.add_argument("--remove", action="store_true")
    sc.add_argument("--every", type=int, default=2, help="분")
    sc.set_defaults(fn=cmd_schedule)
    w = sp.add_parser("watch", help="N초마다 html(작업 스케줄러 없이, 백그라운드로)")
    w.add_argument("--every", type=int, default=120, help="초(30 이상)"); w.add_argument("--once", action="store_true")
    w.set_defaults(fn=cmd_watch)
    sv = sp.add_parser("serve", help="상태판 로컬 서버(127.0.0.1만, 새로고침마다 최신) — milstart가 백그라운드로 켬")
    sv.add_argument("--port", type=int, default=SERVE_PORT)
    sv.set_defaults(fn=cmd_serve)

    q = sp.add_parser("queue"); q.set_defaults(fn=cmd_queue)
    qs = q.add_subparsers(dest="qcmd")
    qa = qs.add_parser("add")
    qa.add_argument("--task", required=True); qa.add_argument("--files", default="")
    qa.add_argument("--from", dest="source", required=True, choices=["milstart", "파생", "PR", "직접", "미리"],
                    help="직접(옛 값 미리)은 바로 승인")
    qa.add_argument("--session"); qa.add_argument("--note")
    qa.set_defaults(fn=cmd_queue_add)
    qp = qs.add_parser("approve"); qp.add_argument("id"); qp.set_defaults(fn=cmd_queue_approve)
    qr = qs.add_parser("reject"); qr.add_argument("id"); qr.add_argument("--why", required=True)
    qr.set_defaults(fn=cmd_queue_reject)
    qd = qs.add_parser("done"); qd.add_argument("id"); qd.add_argument("--pr")
    qd.add_argument("--force", action="store_true", help="반려로 잘못 닫은 줄을 완료로 고침")
    qd.set_defaults(fn=cmd_queue_done)
    qt = qs.add_parser("take"); qt.add_argument("id"); qt.add_argument("--folder", required=True)
    qt.add_argument("--session"); qt.set_defaults(fn=cmd_queue_take)

    d = sp.add_parser("decide"); d.set_defaults(fn=cmd_decide)
    ds = d.add_subparsers(dest="dcmd")
    da = ds.add_parser("add")
    da.add_argument("--folder", required=True); da.add_argument("--session", required=True)
    da.add_argument("--q", required=True); da.add_argument("--options", required=True)
    da.set_defaults(fn=cmd_decide_add)
    dn = ds.add_parser("answer"); dn.add_argument("id"); dn.add_argument("--a", required=True)
    dn.set_defaults(fn=cmd_decide_answer)

    cn = sp.add_parser("clean")
    cn.add_argument("--days", type=int, default=1, help="완료·반려 N일 넘은 대기 작업 + 답한 지 N일 넘고 폴더 줄 없는 결정요망 삭제")
    cn.set_defaults(fn=cmd_clean)

    sp.add_parser("selftest").set_defaults(fn=cmd_selftest)
    args = p.parse_args()
    if args.cmd != "selftest":
        global ME
        env = os.environ.get("VCC_BOARD", "").strip()
        ME = who_am_i() or ""
        if not ME and not env.lower().endswith(".md"):
            print("「나」를 정하지 못함 — 한 번만: git config vcc.me 원우   (원우·민지·미리 중 하나)", file=sys.stderr)
            sys.exit(1)
        path, may_migrate = resolve(ME)
        set_board(path)
        if may_migrate:
            rename_unnamed(BOARD, ME)
            migrate(OLD_BOARD, BOARD)
    args.fn(args)


if __name__ == "__main__":
    main()
