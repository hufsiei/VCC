# 시트 -> data/ JSON 변환 (원우 담당, 작업 16)
# 사용: python tools/sheet_to_json.py [가상데이터_1000명.xlsx 경로]
#   경로를 안 주면 저장소 바로 위 폴더의 가상데이터_1000명.xlsx를 읽는다.
#   원본 엑셀은 저장소에 올리지 않는다(.gitignore 대상 아님 — 저장소 밖에 둘 것).
# 규칙: docs/spec-v1.md 9장, data/README.md
#   - JSON 키는 시트 헤더 글자 그대로. 분포요약·생성기준 시트는 변환하지 않음
#   - students.json에서 studt_na_kr·sex·나이(만) 제외
#   - 가상질문은 봉인(Y) 행을 빼고 질문이 있는 행만 eval-questions.csv로
#   - 학기 코드(1·2·3·4)로 semester("2024-1"·"2024-여름"·"2024-2"·"2024-겨울")를 만들어
#     extracurricular·reports·internships·evidence 각 행에 덧붙임(시트에 없는 값이라 영어 키)
# 필요: pip install openpyxl
import csv, json, re, sys
from pathlib import Path
import openpyxl

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parent / "가상데이터_1000명.xlsx"

DROP_STUDENT = {"studt_na_kr", "sex", "나이(만)"}
ALIASES = {"마르부르크필립스대학교": ["마르부르크", "마르부르크대", "마부르크"]}
REPORT_SECTIONS = {  # 문항 헤더 -> 칸 (spec 9장)
    "1-1. 입학허가서 신청시 유의사항": "지원", "1-2. 비자 취득, 항공권 및 유학생 보험 구입": "지원",
    "1-3. 기타 유의사항": "지원", "2-2. 수강신청": "학점", "2-3. 수업내용 및 프로그램 과정": "학점",
    "3. 파견대학 취득 성적 본교 학점 인정 관련": "학점", "2-6. 소요 비용": "비용",
    "2-1. 공항에서 학교까지 교통편": "생활", "2-4. 기숙사 정보": "생활", "2-5. 교내 활동": "생활",
    "2-7. 기타 사항": "생활", "4. 후배들에게 남기고픈 한마디": "팁",
}
errors = []
SEM_SUFFIX = {1: "1", 2: "여름", 3: "2", 4: "겨울"}


def semester(year, code, where):
    if year is None or code not in SEM_SUFFIX:
        errors.append(f"{where}: 학기 코드 이상 ({year}, {code})")
        return None
    return f"{year}-{SEM_SUFFIX[code]}"


def clean(v):
    if isinstance(v, str):
        v = v.strip()
        return v or None
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


def read(ws, key):
    """헤더가 있는 열만 읽고, key 열이 빈 행은 버린다."""
    rows = ws.iter_rows(values_only=True)
    head = [h.strip() if isinstance(h, str) else h for h in next(rows)]
    cols = [(i, h) for i, h in enumerate(head) if h]
    out = []
    for r in rows:
        d = {h: clean(r[i]) if i < len(r) else None for i, h in cols}
        if d.get(key) is not None:
            out.append(d)
    return out


def dump(name, obj):
    (DATA / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"  {name}: {len(obj)}건")


def main():
    print("원본:", SRC)
    wb = openpyxl.load_workbook(SRC, read_only=True, data_only=True)

    students = [{k: v for k, v in s.items() if k not in DROP_STUDENT} for s in read(wb["가상학생"], "colreg_no")]
    extra = read(wb["가상비교과"], "가상학번")
    sat = read(wb["가상비교과만족도"], "프로그램명")
    reports = read(wb["가상귀국보고서"], "학번")
    interns = read(wb["가상현장실습후기"], "학번")
    depts = [d for d in read(wb["부서리스트"], "부서코드") if re.fullmatch(r"D\d+", str(d["부서코드"]))]  # 아래 ※ 메모 행 제외
    manual = {r["프로그램명"]: r["수동 지정 부서코드"] for r in read(wb["비교과_부서배정(확인용)"], "프로그램명")
              if r.get("수동 지정 부서코드")}
    questions = read(wb["가상질문"], "질문")

    # ── semester 덧붙이기 ──
    for r in extra:
        r["semester"] = semester(r.get("이수학년도"), r.get("이수학기(1~4)"), f"가상비교과 {r.get('번호')}")
    for name, rows_ in [("가상귀국보고서", reports), ("가상현장실습후기", interns)]:
        for r in rows_:
            r["semester"] = semester(r.get("학년도"), r.get("학기"), f"{name} {r.get('학번')}")

    # ── 학생 열쇠 검사 ──
    ids = {s["colreg_no"] for s in students}
    for name, rows, k in [("가상비교과", extra, "가상학번"), ("가상귀국보고서", reports, "학번"),
                          ("가상현장실습후기", interns, "학번")]:
        for r in rows:
            if r[k] not in ids:
                errors.append(f"{name}: 없는 학번 {r[k]}")

    # ── programs.json ──
    def dept_for(field):
        for d in depts:
            if field in (d.get("담당분야") or ""):
                return d["부서코드"]
        errors.append(f"부서리스트: 담당분야 '{field}' 부서 없음")

    d_intl, d_intern = dept_for("국제교류"), dept_for("현장실습")
    programs, seen = [], set()
    for s in students:
        if s.get("파견대학") and s["파견대학"] not in seen:
            seen.add(s["파견대학"])
            programs.append({"프로그램명": s["파견대학"], "분야": "국제교류", "세부": s.get("파견국가"),
                             "운영부서코드": d_intl})
    intern_type = {s.get("기관명(가상)"): s.get("기관 유형(가상)") for s in students if s.get("기관명(가상)")}
    for r in interns:
        if r["업체명"] not in seen:
            seen.add(r["업체명"])
            programs.append({"프로그램명": r["업체명"], "분야": "현장실습", "세부": intern_type.get(r["업체명"]),
                             "운영부서코드": d_intern})
    for r in sat:
        code = manual.get(r["프로그램명"])
        if not code:
            for d in depts:
                kws = [k.strip() for k in (d.get("비교과 배정 키워드") or "").split(";") if k.strip()]
                if any(k in r["프로그램명"] for k in kws):
                    code = d["부서코드"]; break
        if not code:
            errors.append(f"비교과 부서 미배정: {r['프로그램명']}")
        programs.append({"프로그램명": r["프로그램명"], "분야": "비교과", "세부": r.get("비교과 유형"),
                         "만족도(5점)": r.get("만족도(5점)"), "운영부서코드": code})
    for p in programs:
        if p["프로그램명"] in ALIASES:
            p["별칭"] = ALIASES[p["프로그램명"]]

    # ── 프로그램명 대조 ──
    names = {p["프로그램명"] for p in programs}
    for r in extra:
        if r["프로그램명"] not in names:
            errors.append(f"가상비교과: 목록에 없는 프로그램 {r['프로그램명']}")
    for r in reports:
        if r["대학명"] not in names:
            errors.append(f"가상귀국보고서: 목록에 없는 대학 {r['대학명']}")
    # 만족도 이수 인원 = 가상비교과 행 수
    cnt = {}
    for r in extra:
        cnt[r["프로그램명"]] = cnt.get(r["프로그램명"], 0) + 1
    for r in sat:
        if r.get("이수 인원(가상)") != cnt.get(r["프로그램명"], 0):
            errors.append(f"만족도 이수 인원 불일치: {r['프로그램명']} {r.get('이수 인원(가상)')} vs {cnt.get(r['프로그램명'], 0)}")

    # ── evidence.json ──
    evidence = []
    for i, r in enumerate(reports, 1):
        for q, sec in REPORT_SECTIONS.items():
            if q not in r:
                errors.append(f"가상귀국보고서: 문항 헤더 없음 {q}"); continue
            if r[q]:
                evidence.append({"id": f"R{i:03d}-{q.split('.')[0]}", "docType": "귀국보고서", "학번": r["학번"],
                                 "학년도": r["학년도"], "학기": r["학기"], "semester": r["semester"], "프로그램명": r["대학명"],
                                 "문항": q, "칸": sec, "text": r[q]})
    for i, r in enumerate(interns, 1):
        paras = [p.strip() for p in re.split(r"\n\s*\n", r.get("후기") or "") if p.strip()]
        for j, p in enumerate(paras, 1):
            evidence.append({"id": f"I{i:03d}-{j}", "docType": "현장실습후기", "학번": r["학번"],
                             "학년도": r["학년도"], "학기": r["학기"], "semester": r["semester"], "프로그램명": r["업체명"],
                             "문항": "후기", "칸": "", "text": p})

    # ── 저장 ──
    print("저장:")
    dump("students.json", students)
    dump("extracurricular.json", extra)
    dump("extracurricular-satisfaction.json", sat)
    dump("reports.json", reports)
    dump("internships.json", interns)
    dump("departments.json", depts)
    dump("programs.json", programs)
    dump("evidence.json", evidence)
    qhead = ["번호", "질문", "정답", "기대결과", "관련 프로그램", "관련 칸", "기대 근거ID", "유형", "봉인", "질문자 학번", "비고"]
    open_q = [q for q in questions if str(q.get("봉인") or "").upper() != "Y" and q.get("기대결과")]  # 작성 중(기대결과 빈칸) 행 제외
    with open(DATA / "eval-questions.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, qhead, extrasaction="ignore"); w.writeheader(); w.writerows(open_q)
    print(f"  eval-questions.csv: {len(open_q)}건 (봉인·작성 중 {len(questions) - len(open_q)}건 제외)")

    if errors:
        print(f"\n오류 {len(errors)}건:")
        for e in errors:
            print("  -", e)
        sys.exit(1)
    print("\n오류 0건")


if __name__ == "__main__":
    main()
