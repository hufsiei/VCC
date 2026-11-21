# test_paths.py — 본 저장소 찾기·.env 읽기 순서 (paths.py, 11/21)
# 실행: cd functions && python test_paths.py
# 임시 폴더에 가짜 저장소·worktree를 만들어 시험한다. 실제 .env 값은 읽지도 출력하지도 않는다.
import os
import sys
import tempfile
from pathlib import Path

import paths

fails = []


def expect(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


tmp = Path(tempfile.mkdtemp())
main = tmp / "VCC"
(main / ".git" / "worktrees" / "VCC-x").mkdir(parents=True)
wt = tmp / "VCC-x"
wt.mkdir()
(wt / ".git").write_text(f"gitdir: {main.as_posix()}/.git/worktrees/VCC-x\n", encoding="utf-8")

expect("worktree → 본 저장소", paths._main_root(wt) == main)
expect("본 저장소(.git 폴더) → 자기 자신", paths._main_root(main) == main)
nogit = tmp / "cloud"
nogit.mkdir()
expect(".git 없음(NCP) → 자기 자신", paths._main_root(nogit) == nogit)
(tmp / "odd").mkdir()
(tmp / "odd" / ".git").write_text("gitdir: /없는/경로/.git/worktrees/z\n", encoding="utf-8")
expect("gitdir가 가리키는 곳이 없으면 → 자기 자신", paths._main_root(tmp / "odd") == tmp / "odd")

# .env 순서: worktree 것이 먼저, 없는 키만 본 저장소에서. 이미 있는 환경변수는 덮지 않는다
(wt / ".env").write_text("T_PATHS_A=wt\n", encoding="utf-8")
(main / ".env").write_text("T_PATHS_A=main\nT_PATHS_B=main\nT_PATHS_C=main\n", encoding="utf-8")
os.environ["T_PATHS_C"] = "already"
old = paths.ROOT, paths.MAIN_ROOT
paths.ROOT, paths.MAIN_ROOT = wt, main
paths.load_env()
paths.ROOT, paths.MAIN_ROOT = old
expect("같은 키는 worktree .env가 먼저", os.environ.get("T_PATHS_A") == "wt")
expect("worktree에 없는 키는 본 저장소 .env에서", os.environ.get("T_PATHS_B") == "main")
expect("이미 있는 환경변수는 덮지 않음", os.environ.get("T_PATHS_C") == "already")
expect("로그 폴더는 본 저장소 functions/logs", paths.LOGS == paths.MAIN_ROOT / "functions" / "logs")

print()
if fails:
    print(f"틀림 {len(fails)}건")
    sys.exit(1)
print("모두 통과")
