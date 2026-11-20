# check_week1.py — 작업 25 1주차 연결 점검 중 코드로 확인할 수 있는 항목 (작성: 미리)
#
# 실행:  cd C:\dev\VCC
#        python -X utf8 tools/check_week1.py           # ③ 데이터 연결 + 별칭 대조 + ④ 공개 주소
#        python -X utf8 tools/check_week1.py --live    # ② askBoo 실호출 1건(가상질문 1번, HCX 1~2회)까지
#
# 점검 항목(가이드 v4 블록 7):  ① 로그인→인터BOO mock 답변·보류는 화면에서 사람이 확인
#   ② askBoo 로컬 실호출 1건 (--live)   ③ data/ 변환 오류 0건   ④ 공개 주소 휴대폰 접속(여기서는 HTTP 200까지)
# 실제 학생 정보는 다루지 않는다(가상 데이터만). 끝에 항목별 통과/실패 요약, 하나라도 실패면 종료 코드 1.
import csv
import json
import subprocess
import sys
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PAGES = "https://hufsiei.github.io/VCC/"
PAGE_FILES = ["screens/login/", "common/style.css", "common/data.js", "common/mock-data.json"]


def load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def check_data():
    """③ 시트 사이 연결: 학번·프로그램명·칸·id가 서로 맞는지."""
    errs = []
    students = {s["colreg_no"] for s in load("students.json")}
    programs = {p["프로그램명"] for p in load("programs.json")}
    frames = load("frames.json")
    ev = load("evidence.json")

    dup = [k for k, n in Counter(e["id"] for e in ev).items() if n > 1]
    errs += [f"evidence id 중복: {k}" for k in dup]
    allowed = {"귀국보고서": set(frames["교환"]["칸"]) | set(frames["파견"]["칸"]),
               "현장실습후기": set(frames["인턴"]["칸"]) | {""},  # 빈 칸 = 작업 50 분류 전
               "인터뷰": {c for f in frames.values() for c in f["칸"]}}
    for e in ev:
        if e.get("학번") not in students:
            errs.append(f"evidence {e['id']}: 학번 {e.get('학번')} 없음")
        if e.get("프로그램명") not in programs:
            errs.append(f"evidence {e['id']}: 프로그램명 '{e.get('프로그램명')}'이 programs.json에 없음")
        if e.get("칸", "") not in allowed.get(e.get("docType"), set()):
            errs.append(f"evidence {e['id']}: {e.get('docType')}에 없는 칸 '{e.get('칸')}'")
        if not str(e.get("text", "")).strip():
            errs.append(f"evidence {e['id']}: text 비어 있음")
    for name, sid in [("reports.json", "학번"), ("internships.json", "학번"), ("extracurricular.json", "가상학번")]:
        for i, r in enumerate(load(name)):
            if r.get(sid) not in students:
                errs.append(f"{name} {i}행: 학번 {r.get(sid)} 없음")
    for i, r in enumerate(load("extracurricular.json")):
        if r.get("프로그램명") not in programs:
            errs.append(f"extracurricular.json {i}행: 프로그램명 '{r.get('프로그램명')}' 없음")
    q = list(csv.DictReader(open(DATA / "eval-questions.csv", encoding="utf-8-sig")))
    for r in q:
        p = r.get("관련 프로그램", "")
        if p and p not in programs:
            errs.append(f"eval-questions {r['번호']}번: 관련 프로그램 '{p}' 없음")
    for sid in ("H0143", "H0469", "H0745", "staff01", "staff02"):  # 시연 인물·직원 계정
        if sid not in students:
            errs.append(f"시연 계정 {sid} 없음")
    return errs, f"evidence {len(ev)} · 학생 {len(students)} · 프로그램 {len(programs)} · 질문 {len(q)}"


def check_alias():
    """③-보충: 원우의 별칭 대조 점검(tools/check_alias_match.py)."""
    r = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "tools" / "check_alias_match.py")],
                       capture_output=True, text=True, encoding="utf-8")
    last = (r.stdout.strip().splitlines() or ["(출력 없음)"])[-1]
    return ([] if r.returncode == 0 else [last]), last


def check_pages():
    """④ 공개 주소에서 화면 파일이 받아지는지(HTTP 200). 휴대폰 접속은 사람이 따로 확인."""
    errs = []
    for f in PAGE_FILES:
        try:
            with urllib.request.urlopen(PAGES + f, timeout=15) as res:
                if res.status != 200:
                    errs.append(f"{f}: HTTP {res.status}")
        except Exception as e:
            errs.append(f"{f}: {type(e).__name__} {e}")
    return errs, f"{len(PAGE_FILES) - len(errs)}/{len(PAGE_FILES)} 파일 200"


def check_live():
    """② askBoo 로컬 실호출 1건(가상질문 1번). HCX 키(.env CLOVA_KEY)가 필요하다."""
    sys.path.insert(0, str(ROOT / "functions"))
    import askboo  # noqa: E402
    q = list(csv.DictReader(open(DATA / "eval-questions.csv", encoding="utf-8-sig")))[0]
    out = askboo.askBoo("check", {"question": q["질문"]}, save=False)  # eval_askboo.py와 같은 호출, 질문함 저장 안 함
    status = out.get("status") if isinstance(out, dict) else None
    want = {"답변": "ok", "보류": "hold", "공식안내": "official"}.get(q.get("기대결과"), "?")
    errs = [] if status == want else [f"1번 기대 {want} / 결과 {status}"]
    return errs, f"1번 「{q['질문'][:30]}」 → {status}"


def main():
    checks = [("③ 데이터 연결", check_data), ("③ 별칭 대조", check_alias), ("④ 공개 주소", check_pages)]
    if "--live" in sys.argv:
        checks.insert(0, ("② askBoo 실호출", check_live))
    failed = 0
    for name, fn in checks:
        try:
            errs, memo = fn()
        except Exception as e:
            errs, memo = [f"{type(e).__name__}: {e}"], ""
        failed += bool(errs)
        print(f"{'통과' if not errs else '실패'}  {name}  {memo}")
        for e in errs[:15]:
            print(f"      - {e}")
        if len(errs) > 15:
            print(f"      … 외 {len(errs) - 15}건")
    print("\n① 로그인→인터BOO mock 답변·보류, ④ 휴대폰 접속, ⑤ 밀린 일은 사람이 확인해 작업일지에 적는다.")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
