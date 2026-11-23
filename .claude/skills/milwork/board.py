# board.py — 창 상태판 (미리 개인용, 11/23)
#
# 한 PC에서 Claude 대화창을 여러 개 띄워 작업할 때, 어느 폴더(worktree)에서 무슨 작업이 어디까지 갔고
# 누구에게 무엇을 전해야 하는지를 한 표로 둔다. 파일은 저장소 밖 C:\dev\VCC-board.md (PC마다 따로, 커밋 안 함).
# worktree는 PC마다 따로 있으니 상태판도 PC마다 따로가 맞다. PC를 바꾸는 날의 인수인계는 milend의 「내일 리마인드」가 한다.
#
# 쓰는 법 (항상 python -X utf8 로):
#   board.py list                                   표 + 폴더 없는 줄·상태판에 없는 worktree 표시
#   board.py add <폴더> --branch B --who W --task T [--files a,b]
#   board.py set <폴더> [--status S] [--files a,b] [--files-set a,b] [--handoff H] [--task T]
#                                                   (--files는 추가, --files-set은 통째로 바꿈, --handoff는 덮어씀)
#   board.py check <파일...> [--me <폴더>]           다른 줄이 같은 파일(또는 그 폴더)을 건드리는지. 겹치면 종료코드 2
#   board.py remove <폴더>
#   board.py prune                                  폴더가 없어진 줄을 지운다
# <폴더>는 "VCC-xxx" 또는 "C:\dev\VCC-xxx" 어느 쪽이든 된다.
import argparse
import os
import re
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

DEV = Path(r"C:\dev")
REPO = DEV / "VCC"
BOARD = DEV / "VCC-board.md"
LOCK = DEV / "VCC-board.lock"
COLS = ["폴더", "브랜치", "요청", "작업", "파일", "상태", "갱신", "전달 대기"]
SEP = "; "


def now():
    return datetime.now().strftime("%m/%d %H:%M")


def folder_name(s):
    s = s.strip().rstrip("\\/")
    return Path(s).name if ("\\" in s or "/" in s) else s


def clean(cell):
    return str(cell).replace("|", "／").replace("\n", " ").strip()


def split_files(s):
    return [f.strip().replace("\\", "/") for f in re.split(r"[;,]", s or "") if f.strip() and f.strip() != "–"]


def read():
    rows = []
    if not BOARD.exists():
        return rows
    for line in BOARD.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != len(COLS) or cells[0] in (COLS[0], "") or set(cells[0]) <= set("-: "):
            continue
        rows.append(dict(zip(COLS, cells)))
    return rows


def write(rows):
    head = [f"# VCC 상태판 — {socket.gethostname()} (이 PC의 대화창·작업 폴더, 갱신 {now()})", "",
            "작업 대화창은 `milwork`로 줄을 만들고 진행에 따라 「상태」「파일」「전달 대기」를 고친다. "
            "총괄 대화창(`milend`)이 「전달 대기」를 모아 팀원에게 전하고, 병합된 줄과 폴더를 지운다.", "",
            "| " + " | ".join(COLS) + " |", "|" + "---|" * len(COLS)]
    body = ["| " + " | ".join(clean(r.get(c, "")) or "–" for c in COLS) + " |" for r in rows]
    tmp = BOARD.with_suffix(".tmp")
    tmp.write_text("\n".join(head + body) + "\n", encoding="utf-8")
    os.replace(tmp, BOARD)


class locked:
    def __enter__(self):
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
        raise SystemExit("상태판 잠금을 얻지 못했습니다(C:\\dev\\VCC-board.lock 을 지우고 다시).")

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


def overlap(a, b):
    a, b = a.strip("/"), b.strip("/")
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


def cmd_list(args):
    rows, wts = read(), worktrees()
    if not rows and not wts:
        print("상태판 비어 있음 · 작업 폴더 없음")
        return
    for r in rows:
        flag = "" if (DEV / r["폴더"]).is_dir() else "  ← 폴더 없음(병합·삭제됐으면 remove/prune)"
        print(f"[{r['폴더']}] {r['브랜치']} · {r['요청']} · {r['작업']}{flag}")
        print(f"    상태: {r['상태']} ({r['갱신']}) · 파일: {r['파일']}")
        if r["전달 대기"] not in ("", "–"):
            print(f"    전달 대기: {r['전달 대기']}")
    for name, br in wts.items():
        if not find(rows, name):
            print(f"[{name}] {br}  ← 상태판에 없음(milwork 전에 만든 폴더. add로 적거나 지운다)")


def cmd_add(args):
    with locked():
        rows = read()
        name = folder_name(args.folder)
        if find(rows, name):
            raise SystemExit(f"이미 있음: {name} (set으로 고치세요)")
        rows.append({"폴더": name, "브랜치": args.branch, "요청": args.who, "작업": args.task,
                     "파일": SEP.join(split_files(args.files)) or "–", "상태": args.status or "시작",
                     "갱신": now(), "전달 대기": "–"})
        write(rows)
    print(f"추가: {name} ({args.branch})")
    cmd_check(argparse.Namespace(files=split_files(args.files), me=name))


def cmd_set(args):
    with locked():
        rows = read()
        r = find(rows, args.folder)
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
        r["갱신"] = now()
        write(rows)
    print(f"갱신: {r['폴더']} · 상태 {r['상태']} · 파일 {r['파일']}" +
          (f" · 전달 대기 {r['전달 대기']}" if r["전달 대기"] != "–" else ""))
    if args.files:
        cmd_check(argparse.Namespace(files=split_files(args.files), me=r["폴더"]))


def cmd_check(args):
    rows = read()
    me = folder_name(args.me) if args.me else None
    hits = []
    for f in [x.replace("\\", "/") for x in args.files]:
        for r in rows:
            if r["폴더"] == me:
                continue
            for g in split_files(r["파일"]):
                if overlap(f, g):
                    hits.append(f"겹침: {f} ↔ [{r['폴더']}] {r['브랜치']} ({r['요청']} · {r['작업']} · {r['상태']})")
    if hits:
        print("\n".join(dict.fromkeys(hits)))
        print("→ 다른 대화창이 같은 파일을 쓰고 있다. 고치기 전에 미리에게 알린다(같은 날 같은 파일 금지).")
        sys.exit(2)
    if args.files:
        print("겹치는 파일 없음")


def cmd_remove(args):
    with locked():
        rows = read()
        name = folder_name(args.folder)
        new = [r for r in rows if r["폴더"] != name]
        if len(new) == len(rows):
            raise SystemExit(f"없음: {name}")
        write(new)
    print(f"지움: {name}")


def cmd_prune(args):
    with locked():
        rows = read()
        gone = [r["폴더"] for r in rows if not (DEV / r["폴더"]).is_dir()]
        write([r for r in rows if r["폴더"] not in gone])
    print("지운 줄: " + (", ".join(gone) if gone else "없음"))


def main():
    p = argparse.ArgumentParser(description="VCC 창 상태판 (C:\\dev\\VCC-board.md)")
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
    s.set_defaults(fn=cmd_set)
    c = sp.add_parser("check")
    c.add_argument("files", nargs="+"); c.add_argument("--me")
    c.set_defaults(fn=cmd_check)
    r = sp.add_parser("remove"); r.add_argument("folder"); r.set_defaults(fn=cmd_remove)
    sp.add_parser("prune").set_defaults(fn=cmd_prune)
    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
