# pre_push_check.py — push 전 검사 (11/21). .githooks/pre-push가 부른다. 직접 실행: python -X utf8 .githooks/pre_push_check.py
#
# 하는 일 (고치지는 않는다. 통과/실패만 알린다.)
#   1) 저장소에 올라간 .py 파일 전부 문법 검사(py_compile, .pyc는 남기지 않음)
#   2) functions/test_*.py를 하나씩 실행(cd functions). 종료코드 0이 아니면 실패
# 하나라도 실패하면 종료코드 1 → git이 push를 막는다. 전부 통과하면 0.
# 검사 대상은 지금 폴더의 파일이다. 커밋하지 않은 수정이 있으면 그 상태로 검사되므로 경고를 띄운다.
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FUNCTIONS = ROOT / "functions"
TEST_TIMEOUT = 120          # 시험 하나당 초


def git(*args):
    r = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.stdout


def tail(text, n=15):
    lines = [l for l in text.strip().splitlines() if l.strip()]
    return "\n".join("      " + l for l in lines[-n:])


def check_syntax():
    bad = []
    files = [f for f in git("ls-files", "-z", "*.py").split("\0") if f]
    for rel in files:
        path = ROOT / rel
        if not path.exists():
            continue
        try:
            compile(path.read_bytes(), rel, "exec")
        except SyntaxError as e:
            bad.append(f"{rel}:{e.lineno} {e.msg}")
    return len(files), bad


def run_tests():
    results = []
    for test in sorted(FUNCTIONS.glob("test_*.py")):
        start = time.time()
        try:
            r = subprocess.run([sys.executable, "-X", "utf8", test.name], cwd=FUNCTIONS,
                               capture_output=True, text=True, encoding="utf-8", errors="replace",
                               timeout=TEST_TIMEOUT)
            ok, out = r.returncode == 0, (r.stdout or "") + (r.stderr or "")
        except subprocess.TimeoutExpired:
            ok, out = False, f"{TEST_TIMEOUT}초 안에 끝나지 않음"
        results.append((test.name, ok, time.time() - start, out))
    return results


def main():
    print("[pre-push] push 전 검사를 시작합니다.")
    if git("status", "--porcelain", "--untracked-files=no").strip():
        print("[pre-push] 주의: 커밋하지 않은 수정이 있어 그 상태로 검사합니다.")

    n, bad = check_syntax()
    if bad:
        print(f"[pre-push] 문법 오류 {len(bad)}건 / .py {n}개")
        for b in bad:
            print("      " + b)
    else:
        print(f"[pre-push] 문법 검사 통과 (.py {n}개)")

    results = run_tests()
    failed = [r for r in results if not r[1]]
    for name, ok, sec, out in results:
        print(f"      {'통과' if ok else '실패'}  {name}  ({sec:.1f}초)")
        if not ok:
            print(tail(out))

    if bad or failed:
        print(f"[pre-push] push를 막았습니다. 문법 오류 {len(bad)}건 · 시험 실패 {len(failed)}/{len(results)}개.")
        print("[pre-push] 고친 뒤 다시 push하세요. (급할 때만: git push --no-verify)")
        return 1
    print(f"[pre-push] 전부 통과 (시험 {len(results)}개). push합니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
