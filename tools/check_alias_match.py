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


def build_terms(programs):
    terms = []
    for p in programs:
        terms.append((norm(p["프로그램명"]), p["프로그램명"]))
        for a in p.get("별칭", []):
            terms.append((norm(a), p["프로그램명"]))
    return terms


def match(question, terms):
    q = norm(question)
    hits = [(t, prog) for t, prog in terms if t and t in q]
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
