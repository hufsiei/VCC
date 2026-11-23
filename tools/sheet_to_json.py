# 시트 -> data/ JSON 변환 (원우 담당, 작업 16)
# 사용: python tools/sheet_to_json.py [가상데이터_1000명.xlsx 경로]
#   경로를 안 주면 저장소 바로 위 폴더의 가상데이터_1000명.xlsx를 읽는다.
#   원본 엑셀은 저장소에 올리지 않는다(.gitignore 대상 아님 — 저장소 밖에 둘 것).
# 규칙: docs/spec-v1.md 9장, data/README.md
#   - JSON 키는 시트 헤더 글자 그대로. 분포요약·생성기준 시트는 변환하지 않음
#   - students.json에서 studt_na_kr·sex·나이(만)·비번 제외
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

DROP_STUDENT = {"studt_na_kr", "sex", "나이(만)", "비번"}   # 비번은 서버 환경변수 VCC_LOGIN_PW에만 둔다(작업 73)


def split_sentences(text):
    """후기 문단 → 문장. 마침표·물음표·느낌표(연달아 쓴 것 포함) 뒤 공백에서 나눈다. '3.5'처럼 공백 없는 점은 나누지 않는다."""
    parts = re.split(r"(?<=[.!?])\s+", (text or "").strip())
    return [p.strip() for p in parts if p.strip()]
# ── 프로그램 별칭 사전 (작업 82) ──
# 줄임말·옛 이름·오타 → 프로그램명. 시연·개발 질문에 쓰는 것만 넣는다.
# 넣지 않는 것: "리옹"(리옹2·리옹3 둘 다), "소르본"(파리 제4·제13 둘 다), "KOTRA"·"코트라"만 단독(권역 3곳),
#   가짜 이름(하이델베르크·리스본신대학교·KOTRA 아시아 — 함정 질문용).
# 대조 규칙(check_alias_match.py와 같음): 띄어쓰기를 지우고 영문은 소문자로 바꾼 뒤 질문 안에 들어 있으면 일치,
#   여러 개가 걸리면 긴 이름이 짧은 이름을 덮는다(긴 이름 우선).
ALIASES = {
    "마르부르크필립스대학교": ["마르부르크", "마르부르크대", "마부르크"],
    "밀라노대학교": ["밀라노", "밀라노대"],
    "국립동양언어문화대학교 (이날코)": ["이날코", "국립동양언어문화대학교", "국립동양언어문화대"],
    "쟝 물랑 리옹 3 대학": ["리옹3", "리옹 제3대학", "장 물랑 리옹3", "쟝 물랑"],
    "뤼미에르 리옹 2대학": ["리옹2", "리옹 제2대학", "뤼미에르 리옹"],
    "파리시테대학교(구 파리7 디드로)": ["파리 제7대학교", "파리7", "파리 디드로", "파리시테대학교", "파리시테"],
    "㈜트랜스허브코리아": ["트랜스허브코리아", "트랜스허브"],
    "K-컬처랩(온라인)": ["K-컬처랩", "K컬처랩", "케이컬처랩"],
    "KOTRA 해외무역관(중남미 권역)": ["KOTRA 중남미 무역관", "KOTRA 중남미", "코트라 중남미"],
    "㈜한백인터내셔널 해외영업팀": ["한백인터내셔널"],   # 11/20 개발 질문 57
    "그렌버그코리아㈜": ["그렌버그코리아"],               # 11/20 개발 질문 70
    # 11/22 작업 81: 나머지 KOTRA 권역도 중남미와 같은 모양으로
    "KOTRA 해외무역관(유럽 권역)": ["KOTRA 유럽 무역관", "KOTRA 유럽", "코트라 유럽"],
    "KOTRA 해외무역관(CIS 권역)": ["KOTRA CIS 무역관", "KOTRA CIS", "코트라 CIS"],
}
# 11/22 작업 81: 현장실습 업체는 ㈜·(유)·(온라인)·'해외영업팀'·'한국/서울사무소'를 뗀 이름도 별칭으로 자동 추가
#   예) ㈜글로벌랭스 → 글로벌랭스, 두레텍스㈜ 해외영업팀 → 두레텍스, 국제청년교류기구 한국사무소 → 국제청년교류기구
SHORT_DROP = re.compile(r"㈜|\(유\)|\(온라인\)")
SHORT_TAIL = re.compile(r"\s*(?:해외영업팀|한국사무소|서울사무소)$")


def short_name(name):
    s = SHORT_TAIL.sub("", SHORT_DROP.sub("", name)).strip()
    return s if s != name and len(s.replace(" ", "")) >= 3 else None


# 11/23 미리 요청: 국제교류 학교는 끝의 「대학교·대학」(과 괄호)을 뗀 앞부분도 별칭으로(「레이던 다녀온 선배」가 보류되던 문제).
#   ALIASES에 손으로 넣은 학교(마르부르크·밀라노 등 6곳)는 건드리지 않는다 — 별칭 첫 항목이 화면의 짧은 이름이라.
#   예) 레이던 대학교 → 레이던, 흐로닝언대학교 → 흐로닝언, 토리노대학 → 토리노
EXCHANGE_TAIL = re.compile(r"\s*(?:\([^)]*\))?\s*(?:종합대학교|대학교|대학)\s*(?:\([^)]*\))?$")
EXCHANGE_SKIP = {
    "리스본종합대학교",   # 「리스본」은 함정 「리스본신대학교」(가짜 학교)와 인턴 업체 「리스본 협력기관」에 걸림
    "본대학교",           # 「본」 한 글자 — 다른 이름(리스본·소르본) 안에도 들어 있음
}
EXCHANGE_RENAME = {     # 규칙으로 뗀 이름보다 실제로 부르는 이름
    "상트페테르부르크국립대학교": ["상트페테르부르크", "상트페테르부르크국립"],   # 「…국립대」도(국립은 학교 종류 말)
    "미나스제라이스연방대학교": ["미나스제라이스"],
    # 11/23 미리 메모: 도시 이름만 남기면 같은 도시의 다른 학교·캠퍼스까지 잡힌다 → 그 학교만 가리키는 이름으로
    "폴발레리 몽펠리에 제3대학교": ["폴발레리", "몽펠리에 제3", "몽펠리에 3"],   # 「몽펠리에 대학교」는 다른 학교
    "외국인을 위한 시에나대학교": ["시에나 외국인", "외국인을 위한 시에나"],      # 「시에나대학교」는 다른 학교
    "캘리포니아주립대학교(샌프란시스코)": ["샌프란시스코주립", "캘리포니아주립대 샌프란시스코",
                                         "캘리포니아주립대학교 샌프란시스코"],   # 「캘리포니아주립대 LA」 등 다른 캠퍼스
    "나가사키외국어대학교": ["나가사키외국어", "나가사키외대"],                 # 「나가사키대학교」는 다른 학교
}
EXCHANGE_EXTRA = {      # 규칙 이름에 더해 자주 부르는 이름
    "그르노블 알프스 대학교": ["그르노블"],
    "뒤스부르크-에센대학교": ["뒤스부르크"],      # 하이픈 없이 「뒤스부르크 에센」으로 물어도
}


# 11/23 비교과: 앞의 [꾸밈]과 뒤의 (괄호)를 뗀 이름도 별칭으로 — 학생은 「[특교원] 이탈리아어과 탄뎀」을 「이탈리아어과 탄뎀」으로 묻는다.
#   못 찾으면 콘솔의 프로그램별 수요 집계에서 빠진다(사용 로그 73건이 이 꼴). 확실한 것만: 줄임 이름이 하나뿐이고(기업만 다른
#   「해외영업(사업) 현직자 온라인 직무 특강」 3개 등은 제외), 다른 프로그램 이름·별칭과 서로 포함 관계가 없고, 4글자 이상일 때.
EXTRA_HEAD = re.compile(r"^\s*(?:\[[^\]]*\]\s*)+")
EXTRA_TAIL = re.compile(r"\s*\([^)]*\)\s*$")


def extra_short_all(programs, aliases):
    def nrm(x):
        return re.sub(r"\s+", "", x or "").lower()
    cand = {}
    for p in programs:
        if p["분야"] != "비교과" or p["프로그램명"] in aliases:
            continue
        s = EXTRA_TAIL.sub("", EXTRA_TAIL.sub("", EXTRA_HEAD.sub("", p["프로그램명"])).strip()).strip()
        if s != p["프로그램명"] and len(nrm(s)) >= 4:
            cand[p["프로그램명"]] = s
    counts = {}
    for s in cand.values():
        counts[nrm(s)] = counts.get(nrm(s), 0) + 1
    others = [(nrm(p["프로그램명"]), p["프로그램명"]) for p in programs]
    others += [(nrm(a), k) for k, v in aliases.items() for a in v]
    others += [(nrm(s), k) for k, s in cand.items()]
    out = {}
    for name, s in cand.items():
        t = nrm(s)
        if counts[t] > 1:
            continue
        if any(owner != name and (t in o or o in t) for o, owner in others):
            continue
        out[name] = [s]
    return out


def exchange_short(name):
    if name in EXCHANGE_SKIP:
        return []
    if name in EXCHANGE_RENAME:
        base = list(EXCHANGE_RENAME[name])
    else:
        b = EXCHANGE_TAIL.sub("", name).strip()
        base = [b] if b != name and len(b.replace(" ", "")) >= 2 else []
    return base + EXCHANGE_EXTRA.get(name, []) if base else []
# 긴 이름 우선으로 풀리는 겹침(의도한 것만). (별칭, 겹치는 다른 프로그램명)
ALIAS_OVERLAP_OK = {
    ("밀라노", "밀라노 협력기관(온라인)"),  # "밀라노 협력기관"이 있으면 긴 이름이 이김. "밀라노"만 쓰면 교환(대학교)
    ("스톡홀름", "스톡홀름 협력기관(온라인)"),  # 11/23 같은 모양. "스톡홀름"만 쓰면 스톡홀름대학교
}
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


def check_aliases(programs):
    """한 별칭이 두 프로그램에 걸리면 오류(작업 82)."""
    from check_alias_match import norm
    names = {p["프로그램명"] for p in programs}
    for k in ALIASES:
        if k not in names:
            errors.append(f"별칭: 목록에 없는 프로그램 {k}")
    terms = [(norm(p["프로그램명"]), p["프로그램명"], p["프로그램명"]) for p in programs]
    terms += [(norm(a), a, k) for k, al in ALIASES.items() for a in al]
    found = []
    for t, a, k in terms:
        if a == k:
            continue  # 프로그램명 자체는 검사 대상 아님(시트 원본)
        for t2, a2, k2 in terms:
            if k2 == k:
                continue
            if t == t2:
                found.append(f"별칭 중복: '{a}'가 {k}·{k2} 둘 다에 걸림")
            elif t in t2 and (a, k2) not in ALIAS_OVERLAP_OK:
                found.append(f"별칭 겹침: '{a}'({k})가 '{a2}'({k2}) 안에 들어 있음")
    errors.extend(dict.fromkeys(found))


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
        short = short_name(p["프로그램명"]) if p["분야"] == "현장실습" else None
        if short and short not in ALIASES.get(p["프로그램명"], []):
            ALIASES.setdefault(p["프로그램명"], []).append(short)
    for p in programs:   # 11/23 국제교류 줄임 이름 — 손으로 넣은 별칭이 없는 학교만
        if p["분야"] == "국제교류" and p["프로그램명"] not in ALIASES:
            short = exchange_short(p["프로그램명"])
            if short:
                ALIASES[p["프로그램명"]] = short
    ALIASES.update(extra_short_all(programs, ALIASES))   # 11/23 비교과 줄임 이름
    for p in programs:
        if p["프로그램명"] in ALIASES:
            p["별칭"] = ALIASES[p["프로그램명"]]
    check_aliases(programs)

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
    # [11/20 작업 50] 현장실습후기는 문장 단위: 한 문장 = 근거 한 건, id = I{후기 번호}-{후기 안 문장 순번}.
    #   한 문단에 업무·배운점이 섞여 있어 문단 단위로는 칸 하나로 나눌 수 없다(spec 9장). '문단'은 원래 문단 번호(추적용).
    # [11/20] 작업 50 자동 분류 결과는 data/intern-sections.json({sourceId: 칸})에 따로 두고 변환할 때마다 다시 입힌다.
    #   evidence.json에만 써 두면 이 스크립트를 다시 돌릴 때 칸이 빈 값으로 돌아가 분류 결과가 사라지기 때문.
    sec_path = DATA / "intern-sections.json"
    sections = json.loads(sec_path.read_text(encoding="utf-8")) if sec_path.exists() else {}
    frames = json.loads((DATA / "frames.json").read_text(encoding="utf-8"))
    allowed = [s for s in frames["인턴"]["칸"] if s not in frames["인턴"]["인터뷰로만"]]
    for sid, s in sections.items():
        if s not in allowed:
            errors.append(f"intern-sections.json: {sid}의 칸 '{s}'은 인턴 틀의 사전 생성 칸({'·'.join(allowed)})이 아님")
    intern_ids = set()
    for i, r in enumerate(interns, 1):
        paras = [p.strip() for p in re.split(r"\n\s*\n", r.get("후기") or "") if p.strip()]
        k = 0
        for j, p in enumerate(paras, 1):
            for s in split_sentences(p):
                k += 1
                sid = f"I{i:03d}-{k}"
                intern_ids.add(sid)
                row = {"id": sid, "docType": "현장실습후기", "학번": r["학번"],
                       "학년도": r["학년도"], "학기": r["학기"], "semester": r["semester"], "프로그램명": r["업체명"],
                       "문항": "후기", "문단": j, "칸": sections.get(sid, ""), "text": s}
                if sid in sections:
                    row["autoClassified"] = True
                evidence.append(row)
    stray = sorted(set(sections) - intern_ids)
    if stray:
        errors.append(f"intern-sections.json: 근거에 없는 id {len(stray)}개(예: {stray[:3]}) — 후기 문장이 바뀌었으면 분류를 다시 해야 함")

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
