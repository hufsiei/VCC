# board.py — 창 상태판 (11/23 미리 개인용 · 11/25 드라이브 공용 + 대기 작업·결정요망·HTML · 11/25 사람별 파일)
#
# Claude 대화창을 여러 개 띄워 작업할 때, 어느 폴더(worktree)에서 무슨 작업이 어디까지 갔고
# 누구에게 무엇을 전해야 하는지를 한 파일에 둔다. 파일은 사람마다 따로: 드라이브 「@VCC\총괄\board-<이름>.md」
# (그 사람의 두 PC 공용, 커밋 안 함). 남의 파일은 읽지 않는다 — list·check·html 모두 내 파일만(팀 대시보드 없음, 11/25).
#   「나」(<이름>): git config vcc.me(원우|민지|미리) → 없으면 git user.name·email로 짐작(session_start.py와 같은 규칙).
#     못 정하면 종료코드 1 + 「git config vcc.me 원우」 안내. 한 번만 하면 된다: git config vcc.me <이름>
#   찾는 순서: 환경변수 VCC_BOARD(폴더면 그 안의 board-<이름>.md, .md면 그 파일) → C:~Z: 중 「<X>:\내 드라이브\@VCC」
#     → 없으면 이 PC의 C:\dev\VCC-board-<이름>.md (stderr에 「드라이브 없음, 이 PC 상태판 사용」).
#   잠금(board-<이름>.lock)과 HTML(board-<이름>.html)도 상태판과 같은 폴더·같은 이름.
#   이전: 드라이브에 사람 이름 없는 board.md(11/25 #249, 미리 것)가 있으면 미리가 처음 실행할 때 board-미리.md로 이름을 바꾼다
#     (다른 사람은 건드리지 않는다). 새 파일이 없고 옛 C:\dev\VCC-board.md가 있으면 옮기고 옛 파일은 VCC-board-이전.md로.
# 파일 모양: 맨 위 「총괄: <세션이름> (<PC>, MM/DD HH:MM)」 → 창 표 → 「## 대기 작업」 표 → 「## 결정요망」 표.
# 드라이브 동기화가 늦으니 두 PC가 같은 시각에 쓰면 한쪽이 질 수 있다(한 PC씩 쓰는 전제).
#
# 쓰는 법 (항상 python -X utf8 C:/dev/VCC/.claude/skills/milwork/board.py …):
#   list                                            창 표 + 이 PC의 폴더 없는 줄·상태판에 없는 worktree 표시(다른 PC 줄은 보여만 줌)
#   add <폴더> --branch B --who W --task T [--files a,b]   (PC는 자동 기록)
#   set <폴더> [--status S] [--files a,b] [--files-set a,b] [--handoff H] [--sent] [--task T]
#                                                   (--files는 추가, --files-set은 통째로 바꿈, --handoff는 덮어씀=안 보냄,
#                                                    --sent는 지금 답장을 「보냄 MM/DD HH:MM」으로 표시)
#   pending                                         아직 안 보낸 답장만(밀종료·밀시작이 본다)
#   check <파일...> [--me <폴더>]                    다른 줄이 같은 파일(또는 그 폴더)을 건드리는지. 겹치면 종료코드 2
#   remove <폴더>                                    안 보낸 답장이 있으면 지우지 않는다(--force로 무시)
#   prune                                           이 PC에서 폴더가 없어진 줄을 지운다
#   chief                                           머리의 총괄 세션 이름 출력(없으면 빈 줄, 종료코드 1)
#   chief --set <세션이름|–>                         총괄 세션 이름 쓰기(–면 비움)
#   html                                            같은 폴더에 board-<이름>.html 생성(상태판을 바꾸는 명령 뒤 자동 실행)
#   queue                                           대기 작업 표 출력
#   queue add --task "<작업번호 또는 –> <제목>" --files a,b --from milstart|파생|PR|직접 [--session <이름>] [--note "…"]
#                                                   → 「Q-n 제안」(--from 직접은 「Q-n 승인」. 옛 값 「미리」도 직접과 같게 받음)
#   queue approve Q-n                               겹침 없으면 승인, 겹치면 종료코드 2 + 겹친 줄
#   queue reject Q-n --why "…"                      반려(이유 기록)
#   queue take Q-n --folder VCC-<슬러그> [--session <이름>]   승인만 시작됨으로 + 폴더 기록. 제안·반려면 종료코드 2
#   decide                                          결정요망 표 출력(답 없는 것 위)
#   decide add --folder VCC-x --session <이름> --q "질문" --options "A(추천) …; B …"   → 「D-n」, 그 폴더 줄 결정요망에 D-n
#   decide answer D-n --a "A"                       답·시각 기록, 그 폴더 줄에서 D-n 제거. 출력 첫 줄은 그 D-n의 세션 이름
#   selftest                                        임시 폴더에서 위 명령 왕복, 틀리면 종료코드 1
# <폴더>는 "VCC-xxx" 또는 "C:\dev\VCC-xxx" 어느 쪽이든 된다.
import argparse
import html as H
import json
import os
import re
import socket
import string
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

DEV = Path(r"C:\dev")
REPO = Path(os.environ.get("VCC_REPO") or DEV / "VCC")   # VCC_REPO는 selftest가 임시 저장소를 쓸 때만
OLD_BOARD = DEV / "VCC-board.md"
TEAM = {"미리": ("미리", "mirikang"), "민지": ("민지", "minji"), "원우": ("원우", "wwk")}  # session_start.py와 같게
OLD_COLS = ["폴더", "브랜치", "요청", "작업", "파일", "상태", "갱신", "전달 대기"]
COLS = ["폴더", "브랜치", "요청", "작업", "파일", "상태", "갱신", "PC", "결정요망", "전달 대기"]
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
        r = subprocess.run(["git", "-C", str(REPO), "config", key], capture_output=True, text=True,
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


def parse(text):
    st = {"chief": None, "rows": [], "queue": [], "decide": []}
    tables = {tuple(OLD_COLS): "rows", tuple(COLS): "rows", tuple(QCOLS): "queue", tuple(DCOLS): "decide"}
    cur = None
    for line in text.splitlines():
        m = re.match(r"^총괄: (.*)$", line)
        if m and st["chief"] is None:
            body = m.group(1).strip()
            if body not in EMPTY:
                mm = re.match(r"^(.*) \((.*), (\d\d/\d\d \d\d:\d\d)\)$", body)
                st["chief"] = ({"name": mm.group(1), "pc": mm.group(2), "at": mm.group(3)} if mm
                               else {"name": body, "pc": "", "at": ""})
            continue
        if not line.startswith("|"):
            cur = None
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if tuple(cells) in tables:
            cur = (tables[tuple(cells)], cells)
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
        st[key].append(d)
    return st


def load(path=None):
    p = Path(path or BOARD)
    if not p.exists():
        return {"chief": None, "rows": [], "queue": [], "decide": []}
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
    lines = [chief_line(st), "", f"# VCC 상태판 — {ME or p.stem} (두 PC 공용 · 갱신 {now()} {HOST})", "",
             "작업 대화창은 `milwork`로 줄을 만들고 진행에 따라 「상태」「파일」「전달 대기」를 고친다. "
             "팀원 답장은 그 대화창이 바로 쓰고 「전달 대기」에 요점을 적는다. 미리가 보내면 `--sent`로 「보냄」 표시. "
             "총괄 대화창은 대기 작업을 승인하고 결정요망에 답한다. 병합된 줄과 폴더는 `milend`가 지운다.", ""]
    lines += table(COLS, st["rows"])
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
        r = subprocess.run(["git", "-C", str(REPO), "worktree", "list", "--porcelain"],
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


def next_id(items, prefix):
    ns = [int(m.group(1)) for x in items if (m := re.match(rf"^{prefix}-(\d+)$", x["번호"]))]
    return f"{prefix}-{max(ns, default=0) + 1}"


def overlap(a, b):
    a, b = a.strip("/"), b.strip("/")
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


def mine(r):
    return r.get("PC", "") in EMPTY or r.get("PC") == HOST


# ---------- 창 표 명령 ----------
def cmd_list(args):
    st, wts = load(), worktrees()
    rows = st["rows"]
    if not rows and not wts:
        print("상태판 비어 있음 · 작업 폴더 없음")
    for r in rows:
        if mine(r):
            flag = "" if (DEV / r["폴더"]).is_dir() else "  ← 폴더 없음(병합·삭제됐으면 remove/prune)"
        else:
            flag = f"  (다른 PC: {r['PC']})"
        print(f"[{r['폴더']}] {r['브랜치']} · {r['요청']} · {r['작업']}{flag}")
        print(f"    상태: {r['상태']} ({r['갱신']}) · 파일: {r['파일']}"
              + (f" · 결정요망: {r['결정요망']}" if r.get("결정요망", "–") not in EMPTY else ""))
        if unsent(r):
            print(f"    전달 대기(안 보냄): {r['전달 대기']}")
        elif r["전달 대기"] not in EMPTY:
            print(f"    전달: {r['전달 대기']}")
    for name, br in wts.items():
        if not find(rows, name):
            print(f"[{name}] {br}  ← 상태판에 없음(milwork 전에 만든 폴더. add로 적거나 지운다)")
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
                           "갱신": now(), "PC": HOST, "결정요망": "–", "전달 대기": "–"})
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
    """files와 겹치는 창 줄·승인/시작된 대기 작업을 문장으로."""
    hits = []
    rows = st["rows"]
    for f in [x.replace("\\", "/") for x in files]:
        for r in rows:
            if r["폴더"] == me:
                continue
            for g in split_files(r["파일"]):
                if overlap(f, g):
                    hits.append(f"겹침: {f} ↔ [{r['폴더']}] {r['브랜치']} ({r['요청']} · {r['작업']} · {r['상태']})")
        for q in st["queue"]:
            if q["번호"] == skip_q or q["상태"] not in ("승인", "시작됨"):
                continue
            if q["상태"] == "시작됨" and find(rows, q["폴더"]):
                continue            # 창 줄로 이미 셌다
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
        save(st)
    print(f"지움: {name}")


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
        i = next_id(st["queue"], "Q")
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
        i = next_id(st["decide"], "D")
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


# ---------- HTML ----------
def open_prs():
    if os.environ.get("VCC_BOARD_NOGH"):
        return None
    try:
        r = subprocess.run(["gh", "pr", "list", "-R", "hufsiei/VCC", "--state", "open",
                            "--json", "number,title,author,headRefName"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20)
        if r.returncode != 0:
            return None
        return json.loads(r.stdout or "[]")
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None


CSS = """
body{margin:0;padding:24px;font:14px/1.5 Pretendard,"Malgun Gothic",sans-serif;color:#222;background:#f4f5f7}
h1{font-size:20px;color:#002B5C;margin:0 0 4px}
h2{font-size:16px;color:#002B5C;margin:28px 0 8px}
.meta{font-size:12px;color:#666}
.tiles{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:16px 0}
.tile{background:#fff;border:1px solid #d8dce2;border-radius:8px;padding:12px 16px}
.tile b{display:block;font-size:28px;color:#002B5C}
.tile span{font-size:13px;color:#555}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:12px}
.card{background:#fff;border:1px solid #d8dce2;border-left:4px solid #002B5C;border-radius:8px;padding:12px 16px}
.card.other{border-left-color:#999}
.card h3{font-size:15px;margin:0 0 6px;color:#002B5C}
.card dl{display:grid;grid-template-columns:72px 1fr;gap:2px 8px;margin:0;font-size:13px}
.card dt{color:#666}.card dd{margin:0;word-break:break-all}
.warn{color:#002B5C;font-weight:700}
table{width:100%;border-collapse:collapse;background:#fff;font-size:13px}
th,td{border:1px solid #d8dce2;padding:6px 8px;text-align:left;vertical-align:top}
th{background:#e9ecf0;color:#333}
tr.done td{color:#888}
.none{color:#888;font-size:13px}
"""


def e(s):
    return H.escape(str(s if s not in (None, "") else "–"))


def html_table(cols, rows, cls=None):
    if not rows:
        return '<p class="none">–</p>'
    out = ["<table><tr>" + "".join(f"<th>{e(c)}</th>" for c in cols) + "</tr>"]
    for r in rows:
        c = f' class="{cls(r)}"' if cls and cls(r) else ""
        out.append(f"<tr{c}>" + "".join(f"<td>{e(r.get(k, ''))}</td>" for k in cols) + "</tr>")
    return "\n".join(out) + "</table>"


def make_html(st, path=None):
    path = Path(path or html_path())
    rows = st["rows"]
    waitq = [x for x in st["queue"] if x["상태"] in ("제안", "승인")]
    opend = [x for x in st["decide"] if x["답"] in EMPTY]
    tiles = [("진행 중 창", len(rows)), ("대기 작업", len(waitq)), ("결정요망", len(opend)),
             ("안 보낸 전달", sum(1 for r in rows if unsent(r)))]
    c = st.get("chief")
    chief = f"총괄: {c['name']} ({c['pc']}, {c['at']})" if c else "총괄: –"
    cards = []
    for r in rows:
        items = [("폴더", r["폴더"]), ("브랜치", r["브랜치"]), ("요청", r["요청"]), ("작업", r["작업"]),
                 ("파일", r["파일"]), ("상태", r["상태"]), ("갱신", r["갱신"]), ("PC", r.get("PC", "–")),
                 ("결정요망", r.get("결정요망", "–")), ("전달 대기", r["전달 대기"])]
        dl = "".join(f"<dt>{e(k)}</dt><dd{' class=warn' if (k == '전달 대기' and unsent(r)) or (k == '결정요망' and v not in EMPTY) else ''}>{e(v)}</dd>"
                     for k, v in items)
        cards.append(f'<div class="card{"" if mine(r) else " other"}"><h3>{e(r["폴더"])}</h3><dl>{dl}</dl></div>')
    prs = open_prs()
    if prs is None:
        pr_html = '<p class="none">–</p>'
    else:
        pr_rows = [{"#": p.get("number"), "제목": p.get("title"), "작성자": (p.get("author") or {}).get("login", "–"),
                    "브랜치": p.get("headRefName")} for p in prs]
        pr_html = html_table(["#", "제목", "작성자", "브랜치"], pr_rows)
    dec = sorted(st["decide"], key=lambda x: x["답"] not in EMPTY)
    doc = f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta http-equiv="refresh" content="60">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>VCC 상태판 · {e(ME or path.stem)}</title><style>{CSS}</style></head><body>
<h1>VCC 상태판 · {e(ME or path.stem)}</h1>
<div class="meta">{e(chief)} · 만든 때 {e(now())} ({e(HOST)}) · 60초마다 새로 읽음</div>
<div class="tiles">{"".join(f'<div class="tile"><b>{n}</b><span>{e(t)}</span></div>' for t, n in tiles)}</div>
<h2>창</h2>
{'<div class="cards">' + "".join(cards) + '</div>' if cards else '<p class="none">–</p>'}
<h2>대기 작업</h2>
{html_table(QCOLS, st["queue"], lambda x: "done" if x["상태"] in ("시작됨", "반려") else "")}
<h2>결정요망</h2>
{html_table(DCOLS, dec, lambda x: "done" if x["답"] not in EMPTY else "")}
<h2>열린 PR</h2>
{pr_html}
</body></html>
"""
    tmp = path.with_suffix(".tmp.html")
    tmp.write_text(doc, encoding="utf-8")
    os.replace(tmp, path)
    return path


def cmd_html(args):
    p = make_html(load())
    print(f"만듦: {p}")


# ---------- 자체 시험 ----------
def cmd_selftest(args):
    tmp = Path(tempfile.mkdtemp(prefix="vcc-board-"))
    repo = tmp / "repo"          # 「나」를 바꿔 보는 임시 저장소(본 저장소 설정은 건드리지 않는다)
    subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True)

    def gitc(key, val):
        subprocess.run(["git", "-C", str(repo), "config", key, val], check=True, capture_output=True)

    gitc("vcc.me", "미리"); gitc("user.name", "nobody"); gitc("user.email", "n@example.invalid")
    env = dict(os.environ, VCC_BOARD=str(tmp), VCC_BOARD_NOGH="1", PYTHONUTF8="1", VCC_REPO=str(repo))
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
    q = {x["번호"]: x for x in board()["queue"]}
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
    h = (tmp / "board-미리.html").read_text(encoding="utf-8")
    for need in ('http-equiv="refresh" content="60"', "총괄: 총괄창", "D-2", "Q-3", "<h2>열린 PR</h2>", "상태판 · 미리"):
        if need not in h:
            fails.append(f"board.html에 {need!r} 없음")
    if re.search(r"<script|fetch\(|https?://", h, re.I):
        fails.append("board.html에 스크립트·바깥 자원")
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
    a.set_defaults(fn=cmd_add)
    s = sp.add_parser("set")
    s.add_argument("folder"); s.add_argument("--status"); s.add_argument("--files"); s.add_argument("--handoff")
    s.add_argument("--files-set", help="파일 목록을 통째로 바꿈(잘못 적은 것 고칠 때)")
    s.add_argument("--task"); s.add_argument("--branch")
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
