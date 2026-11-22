# 인턴 직군·기관유형 사전 만들기 + 점검 (원우 담당, 작업 81)
# 사용: python tools/build_intern_keywords.py          → data/intern-keywords.json 생성 + 점검
#       python tools/build_intern_keywords.py --check  → 파일은 그대로 두고 점검만
#
# 목적: 후배는 "무역 쪽 인턴", "번역 직무"처럼 업체 이름 없이 묻는다. askBoo 1단계에서 프로그램명·별칭 대조가
#   0건이면 이 사전으로 후보 업체 1~3개를 고른다(functions/askboo.py match_programs, 미리).
# 파일 모양(spec 7장 + 문맥): {"문맥": ["인턴", ...], "직군": {"키워드": ["업체명", ...]}, "기관유형": {...}, "약칭": {}}
#   값은 programs.json 현장실습 프로그램명과 글자 그대로 같다. [11/22] 키워드마다 해당 업체를 모두 담는다(3곳 상한은 읽는 쪽에서) — 후기가 적은 업체도 사전에 들어가게(50/50). 업체 약칭(㈜ 등을 뗀 이름)은 사전 대신
#   programs.json 별칭으로 넣었다(sheet_to_json.py short_name) — 그래서 "약칭"은 비어 있다.
# 읽는 규칙(askBoo 1단계, 이 파일의 match()가 기준 구현):
#   1) 프로그램명·별칭 대조가 0건이고 2) 질문에 "문맥" 말이 하나라도 있을 때만
#   3) 세 묶음에서 질문에 든 키워드를 모두 찾고, 다른 걸린 키워드 안에 들어 있는 짧은 키워드는 버린다
#      (긴 키워드 우선 — '여행사' 안의 '행사'). 남은 키워드를 긴 순서로 업체를 합쳐 3곳에서 자른다.
#   문맥 조건이 없으면 "교환 가서 여행 많이 다녀요?"·"행정실 연락처"까지 인턴 업체가 걸린다(11/22 점검에서 30개 중 28개).
# 업체 순서: ① 그 키워드를 후기에서 실제로 쓴 업체 먼저(언급 후기 수 순) ② 나머지는 기관 유형별 후기 많은 순으로 유형을 번갈아(한 유형만 나오지 않게).
#
# 점검(하나라도 틀리면 종료코드 1)
#   1) 사전 값이 모두 programs.json의 현장실습 프로그램명인지
#   2) 직군 질문 시험 14개 중 12개 이상에서 기대한 업체만 나오는지(완료 기준 10개 중 8개보다 엄격하게)
#   2-1) 인턴과 관계없는 질문 30개는 하나도 걸리면 안 됨
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


# 질문에 이 말 중 하나가 있어야 사전을 쓴다. '기관'(공공기관 채용 설명회)·'취업'(취업 특강)·'업무'(행정 업무)는 넣지 않는다.
CONTEXT = ["인턴", "현장실습", "직무", "회사", "기업", "업체", "근무", "일해", "일하", "입사"]

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
    "여행사": {"기관유형": ["여행·관광 기업"]}, "여행": {"기관유형": ["여행·관광 기업"]}, "관광": {"기관유형": ["여행·관광 기업"]},
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
    # [11/22] 후기에 실제로 나오는 업무 말
    "CAT툴": {"직군": ["번역 검수 지원", "번역 프로젝트 지원"]}, "인보이스": {"직군": ["수출입 사무 지원", "해외영업 지원"]},
    "수출서류": {"직군": ["수출입 사무 지원"]}, "바이어": {"직군": ["해외영업 지원", "시장조사 지원", "전시·행사 지원"]},
    "원격": {"기관유형": ["온라인 현장실습(국내 기관)", "현지 협력기관(온라인)"]},
    "엑셀": {"직군": ["경영지원", "마케팅 지원", "행정지원", "수출입 사무 지원", "사업 운영 지원"]},
    "단가": {"직군": ["해외영업 지원", "해외마케팅 지원", "수출입 사무 지원"]},
    "청년교류": {"기관유형": ["국제기구 한국사무소"]}, "참가자": {"직군": ["행사 운영 지원", "사업지원"]},
    "카드뉴스": {"직군": ["콘텐츠 제작 지원", "콘텐츠 마케팅", "자료조사·콘텐츠 지원"]},
    # 현지 협력기관(온라인)은 나라 이름으로도(「네덜란드 쪽 인턴」) — 업체명 별칭(○○ 협력기관)과 겹치지 않는 말만
    "네덜란드": {"업체": ["암스테르담 협력기관(온라인)"]}, "포르투갈": {"업체": ["리스본 협력기관(온라인)"]},
    "스웨덴": {"업체": ["스톡홀름 협력기관(온라인)"]}, "이탈리아": {"업체": ["밀라노 협력기관(온라인)"]},
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


# 인턴과 관계없는 질문 — 하나도 걸리면 안 됨(사전이 없을 때처럼 보류돼야 함)
NEGATIVE = """교환학생 가서 여행 많이 다녀요?|파견 가면 주말에 관광할 시간 있어요?|유럽 교환 가면 학교 행사 많아요?
교내 행사 참여하면 학점 줘요?|번역 수업 들을 만한 학교 있어요?|교환 가서 번역 아르바이트 할 수 있어요?
학사 행정 처리 어디서 해요?|행정실 연락처 알려 주세요|교정 받으러 치과 어디 가요?|기자단 활동 어때요?
학보사 기자 해 본 선배 있어요?|영상 편집 배우는 비교과 있어요?|마케팅 공모전 비교과 있어요?
콘텐츠 만드는 동아리 있어요?|외국계 대학 교환 가능해요?|비대면 수업 많아요?|재택으로 수업 들을 수 있어요?
온라인 강의 있는 파견교 있어요?|수출 관련 수업 있는 대학 있어요?|영업시간 언제예요?|시장조사 방법 배우는 수업 있어요?
국제기구 진출 특강 있어요?|스타트업 창업 비교과 있어요?|공공기관 채용 설명회 언제예요?|고객지원 센터 번호 알려 주세요
벤처 창업 동아리 있어요?|무역학과 이중전공 어때요?|언론정보학 수업 어때요?|제조업 취업 특강 있어요?
기숙사 행정 절차 어때요?""".replace("\n", "|").split("|")


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
    out = {"문맥": CONTEXT, "직군": {}, "기관유형": {}, "약칭": {}}
    for word in sorted(KEYWORDS, key=lambda w: (-len(norm(w)), w)):
        group = "직군" if "직군" in KEYWORDS[word] else "기관유형"
        names = companies_for(KEYWORDS[word], programs, interns)   # 전부(순서 = 답변 우선순위)
        # [11/22] 그 말을 후기에서 실제로 쓴 업체를 앞으로(언급한 후기 수가 많은 순, 같으면 기존 순서) —
        #   후기가 적은 업체도 자기 후기에 나오는 말로 물으면 답 3곳 안에 들게
        mine = {n: [r for r in interns if r["업체명"] == n] for n in names}
        said = {n: sum(norm(word) in norm(r["후기"]) for r in mine[n]) for n in names}
        ratio = {n: said[n] / max(len(mine[n]), 1) for n in names}   # 같은 횟수면 그 말을 쓴 후기 비율이 높은 업체 먼저
        names = sorted(names, key=lambda n: (-said[n], -ratio[n], names.index(n)))
        if names:
            out[group][word] = names
    return out


# askBoo 1단계 기준 구현(check_alias_match 규칙 + 사전 분기). 미리가 askboo.py match_programs에 같은 규칙을 옮긴다.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_alias_match import build_terms, _alias_ok  # noqa: E402


def match(question, terms, keywords):
    q = norm(question)
    hits = [(t, name) for t, name, is_alias in terms if t in q and (not is_alias or _alias_ok(t, q))]
    keep = [(t, name) for t, name in hits if not any(t != t2 and t in t2 for t2, _ in hits)]
    found = sorted({name for _, name in keep})
    if found:
        return found
    if not keywords or not any(norm(c) in q for c in keywords.get("문맥", [])):
        return []
    hits = [(norm(w), names) for g in ("약칭", "직군", "기관유형") for w, names in keywords.get(g, {}).items()
            if norm(w) and norm(w) in q]
    hits = [(t, names) for t, names in hits if not any(t != t2 and t in t2 for t2, _ in hits)]   # 긴 키워드 우선
    for t, names in sorted(hits, key=lambda h: -len(h[0])):
        found += [n for n in names if n not in found]
    return found[:LIMIT]


def check(keywords, programs, interns):
    errs = []
    intern_names = {p["프로그램명"] for p in programs if p["분야"] == "현장실습"}
    for group in ("직군", "기관유형", "약칭"):
        for w, names in keywords.get(group, {}).items():
            for n in names:
                if n not in intern_names:
                    errs.append(f"사전 값이 현장실습 프로그램명이 아님: {group}/{w} → {n}")
    if not keywords.get("문맥"):
        errs.append("문맥 목록이 비어 있음")
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

    covered = {n for g in ("직군", "기관유형", "약칭") for v in keywords.get(g, {}).values() for n in v}
    miss = sorted(intern_names - covered)
    print(f"[업체 포함] 사전에 들어간 업체 {len(covered & intern_names)}/{len(intern_names)}" + (f" — 빠짐 {miss}" if miss else ""))
    if miss:
        errs.append(f"사전에 없는 업체 {len(miss)}곳: {miss}")

    # 후기 문장 샘플: 각 업체 후기에 그 업체를 가리키는 키워드가 실제로 쓰였나(키워드가 후기 말과 맞는지 보는 참고 지표)
    by_word = {norm(w): set(v) for g in ("직군", "기관유형") for w, v in keywords.get(g, {}).items()}
    hit_comp, total_comp = 0, 0
    for name in sorted(intern_names):
        texts = [norm(r["후기"]) for r in interns if r["업체명"] == name]
        if not texts:
            continue
        total_comp += 1
        hit_comp += any(w in t and name in v for t in texts for w, v in by_word.items())
    print(f"[후기 문장 대조] 자기 후기에 자기를 가리키는 키워드가 나오는 업체 {hit_comp}/{total_comp}(참고)")
    top3 = {n for g in ("직군", "기관유형") for v in keywords.get(g, {}).values() for n in v[:LIMIT]}
    print(f"[답 도달] 어느 키워드로든 답 {LIMIT}곳 안에 드는 업체 {len(top3 & intern_names)}/{len(intern_names)}(참고)"
          + (f" — 업체명으로만 찾는 곳 {sorted(intern_names - top3)}" if intern_names - top3 else ""))

    print("[인턴과 관계없는 질문 — 걸리면 안 됨]")
    bad = [(q, match(q, terms, keywords)) for q in NEGATIVE]
    bad = [(q, m) for q, m in bad if m]
    for q, m in bad:
        print(f"  X {q} → {', '.join(m)}")
        errs.append(f"관계없는 질문이 걸림: {q}")
    print(f"  {len(NEGATIVE) - len(bad)}/{len(NEGATIVE)} 걸리지 않음")

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
        words = {**keywords["직군"], **keywords["기관유형"]}
        print(f"{OUT.name}: 직군 {len(keywords['직군'])}·기관유형 {len(keywords['기관유형'])} 키워드, "
              f"업체 {len({n for v in words.values() for n in v})}곳, 문맥 {len(CONTEXT)}개")
    errs = check(keywords, programs, interns)
    print(f"\n오류 {len(errs)}건")
    for e in errs:
        print("  -", e)
    sys.exit(1 if errs else 0)


if __name__ == "__main__":
    main()
