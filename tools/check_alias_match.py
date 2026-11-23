# 별칭 대조 점검 (원우 담당, 작업 82)
# 사용: python tools/check_alias_match.py   (data/programs.json, data/eval-questions.csv를 읽음)
# askBoo 1단계(미리)가 쓸 대조 규칙의 기준 구현이자 시험이다.
#   1) 질문·프로그램명·별칭 모두 띄어쓰기를 지우고 영문은 소문자로 바꾼다(norm).
#   2) 프로그램명이나 별칭이 질문 안에 들어 있으면 그 프로그램이 걸린다.
#   3) 걸린 말이 다른 걸린 말 안에 들어 있으면 짧은 쪽을 버린다(긴 이름 우선).
# 점검: 기대결과 '답변' 질문은 '관련 프로그램' 하나만 걸려야 하고, 유형 '함정' 중 관련 프로그램이 빈 질문은
#   아무것도 걸리면 안 된다. 하나라도 틀리면 종료코드 1.
import csv, json, re, sys
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


def norm(s):
    return re.sub(r"\s+", "", s or "").lower()


#   4) (11/20) 별칭 바로 뒤에 학교 종류 말(공과·예술·음악 등)+대학/대가 붙으면 다른 학교로 보고 걸지 않는다.
#      예) '파리시테예술대학교'는 별칭 '파리시테'가 들어 있어도 파리시테대학교가 아님 → 보류.
#      '밀라노대학교'·'뤼미에르 리옹 2대학'처럼 종류 말 없이 바로 대학이 오면 그대로 건다.
SCHOOL_KIND = ("공과", "공업", "과학기술", "기술", "응용과학", "예술", "음악", "미술", "의과", "약학",
               "경영", "경제", "국립", "주립", "시립", "가톨릭", "카톨릭", "사범", "교육", "외국어", "신학",
               "왕립", "교황청립")   # 11/23 「스톡홀름 왕립공과대학」·「살라망카 교황청립대학교」는 다른 학교
SCHOOL_TAIL = re.compile(r"(?:" + "|".join(SCHOOL_KIND) + r")+(?:대학교|대학|대)")   # 11/23 종류 말이 이어져도(왕립공과대학)


def build_terms(programs):
    # (정규화한 말, 프로그램명, 별칭 여부)
    terms = []
    for p in programs:
        terms.append((norm(p["프로그램명"]), p["프로그램명"], False))
        for a in p.get("별칭", []):
            terms.append((norm(a), p["프로그램명"], True))
    return terms


def _alias_ok(t, q):
    # 별칭이 나오는 자리 중 하나라도 뒤에 다른 학교 꼬리가 없으면 인정
    start = q.find(t)
    while start != -1:
        if not SCHOOL_TAIL.match(q, start + len(t)):
            return True
        start = q.find(t, start + 1)
    return False


def match(question, terms):
    q = norm(question)
    hits = [(t, prog) for t, prog, is_alias in terms
            if t and t in q and (not is_alias or _alias_ok(t, q))]
    keep = [(t, prog) for t, prog in hits
            if not any(t != t2 and t in t2 for t2, _ in hits)]
    return sorted({prog for _, prog in keep})


def main():
    programs = json.loads((DATA / "programs.json").read_text(encoding="utf-8"))
    terms = build_terms(programs)
    rows = list(csv.DictReader(open(DATA / "eval-questions.csv", encoding="utf-8-sig")))
    bad = 0
    for r in rows:
        want_answer = r["기대결과"] == "답변"
        trap = r["유형"] == "함정"
        if not (want_answer or trap):
            continue
        expect = [r["관련 프로그램"]] if r["관련 프로그램"] else []
        got = match(r["질문"], terms)
        ok = got == expect
        bad += not ok
        print(f"{'OK ' if ok else 'XX '} {r['번호']:>3} [{r['기대결과']}/{r['유형']}] {r['질문']}")
        if not ok:
            print(f"       기대 {expect or '없음'} / 결과 {got or '없음'}")
    n = sum(1 for r in rows if r["기대결과"] == "답변" or r["유형"] == "함정")
    print(f"\n대조 점검 {n}건 중 틀림 {bad}건")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
