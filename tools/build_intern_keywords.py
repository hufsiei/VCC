# 인턴 직군·기관유형 사전 만들기 + 점검 (원우 담당, 작업 81)
# 사용: python tools/build_intern_keywords.py          → data/intern-keywords.json 생성 + 점검
#       python tools/build_intern_keywords.py --check  → 파일은 그대로 두고 점검만
#
# 목적: 후배는 "무역 쪽 인턴", "번역 직무"처럼 업체 이름 없이 묻는다. askBoo 1단계에서 프로그램명·별칭 대조가
#   0건이면 이 사전으로 후보 업체 1~3개를 고른다(functions/askboo.py match_programs, 미리).
# 파일 모양: askboo.py가 읽는 평평한 모양 {"키워드": ["업체명", ...]} — 값은 programs.json 프로그램명과 글자 그대로 같다.
#   (spec 7장 예시의 {"직군":{}, "기관유형":{}, "약칭":{}} 묶음은 이 스크립트의 KEYWORDS 표에서 나눠 관리한다.
#    업체 약칭(㈜ 등을 뗀 이름)은 사전 대신 programs.json 별칭으로 넣었다 — sheet_to_json.py short_name)
# 업체 순서: 걸린 업체를 기관 유형별로 후기 많은 순으로 줄 세운 뒤 유형을 번갈아 뽑아 3곳(한 유형만 나오지 않게).
# 키워드 순서: 긴 키워드 먼저(askboo는 걸린 키워드를 사전 순서대로 합쳐 3곳에서 자른다).
#
# 점검(하나라도 틀리면 종료코드 1)
#   1) 사전 값이 모두 programs.json의 현장실습 프로그램명인지
#   2) 직군 질문 시험 14개 중 12개 이상에서 기대한 업체만 나오는지(완료 기준 10개 중 8개보다 엄격하게)
#   3) 개발 질문 70개(eval-questions.csv)의 대조 결과가 사전 없을 때와 같은지 — 특히 함정·보류·공식안내가 답변으로 바뀌면 안 됨
#   봉인 질문은 쓰지 않는다.
import csv, json, re, sys
from collections import Counter, defaultdict
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
OUT = DATA / "intern-keywords.json"
LIMIT = 3


def norm(s):
    return re.sub(r"\s+", "", s or "").lower()


# 키워드 → 고를 업체 조건. 직군(internships.json 직군)이나 기관유형(programs.json 세부)으로 적는다.
# 넣지 않는 말: 'KOTRA'·'코트라'·'무역관' 단독(권역 3곳 — 함정 33 'KOTRA 아시아 권역'이 보류돼야 함),
#   '재단'·'진흥'(함정 52 '국제언어교류진흥재단'), '수입'(돈 얘기와 헷갈림), '온라인' 단독, 'cs'.
TRADE = {"기관유형": ["KOTRA 해외무역관", "중소 무역회사"]}
TRANSLATE = {"직군": ["번역 검수 지원", "번역 프로젝트 지원", "자료조사·번역 지원"]}
KEYWORDS = {
    # 무역
    "무역회사": {"기관유형": ["중소 무역회사"]}, "무역상사": {"기관유형": ["중소 무역회사"]},
    "무역쪽": TRADE, "무역인턴": TRADE, "무역직무": TRADE, "무역업무": TRADE, "무역관련": TRADE, "무역업": TRADE,
    "수출입": {"직군": ["수출입 사무 지원"]}, "수출": {"직군": ["수출입 사무 지원", "해외영업 지원"]},
    # 번역
    "통번역": TRANSLATE, "번역": TRANSLATE, "검수": {"직군": ["번역 검수 지원"]}, "교정": {"직군": ["번역 검수 지원"]},
    # 영업·마케팅
    "해외영업": {"직군": ["해외영업 지원"]}, "영업": {"직군": ["해외영업 지원"]},
    "해외마케팅": {"직군": ["해외마케팅 지원"]},
    "마케팅": {"직군": ["마케팅 지원", "해외마케팅 지원", "콘텐츠 마케팅"]},
    # 조사·행사
    "시장조사": {"직군": ["시장조사 지원"]}, "시장분석": {"직군": ["시장조사 지원"]},
    "자료조사": {"직군": ["자료조사·콘텐츠 지원", "자료조사·번역 지원"]},
    "박람회": {"직군": ["전시·행사 지원"]}, "전시회": {"직군": ["전시·행사 지원"]},
    "행사": {"직군": ["전시·행사 지원", "행사 운영 지원"]},
    # 사무
    "경영지원": {"직군": ["경영지원"]}, "사무직": {"직군": ["경영지원", "행정지원", "수출입 사무 지원"]},
    "행정": {"직군": ["행정지원"]}, "사업운영": {"직군": ["사업 운영 지원", "사업지원"]},
    # 언론·콘텐츠
    "언론": {"기관유형": ["언론사"]}, "신문사": {"기관유형": ["언론사"]}, "기자": {"기관유형": ["언론사"]},
    "편집": {"직군": ["편집 보조"]},
    "콘텐츠": {"직군": ["콘텐츠 제작 지원", "자료조사·콘텐츠 지원", "콘텐츠 마케팅"]},
    # 여행
    "여행": {"기관유형": ["여행·관광 기업"]}, "관광": {"기관유형": ["여행·관광 기업"]},
    "고객응대": {"직군": ["고객지원"]}, "고객지원": {"직군": ["고객지원"]}, "상품기획": {"직군": ["상품기획 지원"]},
    # 기관 유형
    "스타트업": {"기관유형": ["스타트업"]}, "벤처": {"기관유형": ["스타트업"]},
    "서비스운영": {"직군": ["서비스 운영 지원"]},
    "외국계": {"기관유형": ["외국계 기업 한국지사"]}, "글로벌기업": {"기관유형": ["외국계 기업 한국지사"]},
    "공공기관": {"기관유형": ["공공기관"]}, "공기업": {"기관유형": ["공공기관"]},
    "국제기구": {"기관유형": ["국제기구 한국사무소"]}, "ngo": {"기관유형": ["국제기구 한국사무소"]},
    "중견기업": {"기관유형": ["중견기업", "중견기업 해외영업팀"]}, "제조업": {"기관유형": ["중견기업"]},
    "온라인현장실습": {"기관유형": ["온라인 현장실습(국내 기관)", "현지 협력기관(온라인)"]},
    "온라인인턴": {"기관유형": ["온라인 현장실습(국내 기관)", "현지 협력기관(온라인)"]},
    "온라인으로하는": {"기관유형": ["온라인 현장실습(국내 기관)", "현지 협력기관(온라인)"]},
    "재택": {"기관유형": ["온라인 현장실습(국내 기관)", "현지 협력기관(온라인)"]},
    "비대면": {"기관유형": ["온라인 현장실습(국내 기관)", "현지 협력기관(온라인)"]},
    "해외협력기관": {"기관유형": ["현지 협력기관(온라인)"]}, "현지협력기관": {"기관유형": ["현지 협력기관(온라인)"]},
}

# 직군 질문 시험: (질문, 기대 조건) — 나온 업체가 모두 조건에 맞아야 통과. 개발·봉인 질문과 겹치지 않게 새로 씀.
TESTS = [
    ("무역 쪽 인턴 해 본 선배 있어요?", TRADE),
    ("번역 직무 현장실습은 어때요?", TRANSLATE),
    ("해외영업 인턴은 주로 무슨 일 해요?", {"직군": ["해외영업 지원"]}),
    ("언론사 인턴 해 보고 싶은데 후기 있어요?", {"기관유형": ["언론사"]}),
    ("여행사 현장실습 후기 있나요?", {"기관유형": ["여행·관광 기업"]}),
    ("국제기구 인턴 경험 있는 선배 있어요?", {"기관유형": ["국제기구 한국사무소"]}),
    ("마케팅 직무 인턴 어땠어요?", KEYWORDS["마케팅"]),
    ("시장조사 업무 하는 인턴 있어요?", {"직군": ["시장조사 지원"]}),
    ("공공기관 현장실습 분위기 어때요?", {"기관유형": ["공공기관"]}),
    ("온라인으로 하는 현장실습도 있어요?", KEYWORDS["재택"]),
    ("외국계 회사 인턴 해 보니 어때요?", {"기관유형": ["외국계 기업 한국지사"]}),
    ("스타트업 인턴 해 본 선배 있어요?", {"기관유형": ["스타트업"]}),
    ("박람회 통역 보조 같은 인턴 있어요?", {"직군": ["전시·행사 지원"]}),
    ("글로벌랭스 인턴 어때요?", {"업체": ["㈜글로벌랭스"]}),
]


def load():
    programs = json.loads((DATA / "programs.json").read_text(encoding="utf-8"))
    interns = json.loads((DATA / "internships.json").read_text(encoding="utf-8"))
    return programs, interns


def companies_for(cond, programs, interns):
    kind = {p["프로그램명"]: p["세부"] for p in programs if p["분야"] == "현장실습"}
    if "업체" in cond:
        return list(cond["업체"])
    count = Counter()
    for r in interns:
        if r["업체명"] in kind and (r["직군"] in cond.get("직군", []) or kind[r["업체명"]] in cond.get("기관유형", [])):
            count[r["업체명"]] += 1
    groups = defaultdict(list)   # 기관 유형별 후기 많은 순
    for name, n in sorted(count.items(), key=lambda x: (-x[1], x[0])):
        groups[kind[name]].append(name)
    order = sorted(groups, key=lambda k: -count[groups[k][0]])
    picked = []
    while any(groups.values()):
        for k in order:
            if groups[k]:
                picked.append(groups[k].pop(0))
    return picked


def build(programs, interns):
    out = {}
    for word in sorted(KEYWORDS, key=lambda w: (-len(norm(w)), w)):
        names = companies_for(KEYWORDS[word], programs, interns)[:LIMIT]
        if names:
            out[word] = names
    return out


# askBoo 1단계와 같은 대조(check_alias_match 규칙 + askboo.py match_programs의 사전 분기)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_alias_match import build_terms, _alias_ok  # noqa: E402


def match(question, terms, keywords):
    q = norm(question)
    hits = [(t, name) for t, name, is_alias in terms if t in q and (not is_alias or _alias_ok(t, q))]
    keep = [(t, name) for t, name in hits if not any(t != t2 and t in t2 for t2, _ in hits)]
    found = sorted({name for _, name in keep})
    if found:
        return found
    for word, names in keywords.items():
        if norm(word) and norm(word) in q:
            found += [n for n in names if n not in found]
    return found[:LIMIT]


def check(keywords, programs, interns):
    errs = []
    intern_names = {p["프로그램명"] for p in programs if p["분야"] == "현장실습"}
    for w, names in keywords.items():
        for n in names:
            if n not in intern_names:
                errs.append(f"사전 값이 현장실습 프로그램명이 아님: {w} → {n}")
    terms = build_terms(programs)

    ok = 0
    print("[직군 질문 시험]")
    for q, cond in TESTS:
        allowed = set(companies_for(cond, programs, interns))
        got = match(q, terms, keywords)
        good = bool(got) and set(got) <= allowed
        ok += good
        print(f"  {'O' if good else 'X'} {q} → {', '.join(got) or '(없음)'}")
    need = len(TESTS) - 2
    print(f"  {ok}/{len(TESTS)} 통과 (기준 {need})")
    if ok < need:
        errs.append(f"직군 질문 시험 {ok}/{len(TESTS)} — 기준 {need} 미달")

    print("[개발 질문 70개 — 사전 있을 때와 없을 때 비교]")
    changed = 0
    with open(DATA / "eval-questions.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            before, after = match(r["질문"], terms, {}), match(r["질문"], terms, keywords)
            if before != after:
                changed += 1
                print(f"  {r['번호']}({r['기대결과']}/{r['유형']}) {r['질문']} → {after}")
                if r["기대결과"] != "답변" or not r["관련 프로그램"]:
                    errs.append(f"개발 질문 {r['번호']}: 사전 때문에 {after} 걸림(기대 {r['기대결과']})")
                elif r["관련 프로그램"] not in after:
                    errs.append(f"개발 질문 {r['번호']}: 기대 프로그램 대신 {after}")
    print(f"  달라진 질문 {changed}개")
    return errs


def main():
    programs, interns = load()
    if "--check" in sys.argv:
        keywords = json.loads(OUT.read_text(encoding="utf-8"))
    else:
        keywords = build(programs, interns)
        OUT.write_text(json.dumps(keywords, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"{OUT.name}: 키워드 {len(keywords)}개, 업체 {len({n for v in keywords.values() for n in v})}곳")
    errs = check(keywords, programs, interns)
    print(f"\n오류 {len(errs)}건")
    for e in errs:
        print("  -", e)
    sys.exit(1 if errs else 0)


if __name__ == "__main__":
    main()
