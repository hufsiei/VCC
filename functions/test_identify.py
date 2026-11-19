# test_identify.py — identify.py 시험 (작업 70). 실행: cd functions && python test_identify.py
# 식별 문장은 모두 잡고, 일반 문장과 data/evidence.json 근거 문단은 잡지 않아야 한다. 하나라도 틀리면 종료코드 1.
import json
import sys
from pathlib import Path

from identify import check, mark

IDENTIFYING = [
    "평점 4.3으로 선발됐어요.", "GPA 3.9/4.5였어요.", "토익 950점 받고 지원했어요.", "TestDaF 4점이었어요.",
    "학과 1등으로 졸업했어요.", "교내 공모전에서 최우수상을 받았어요.", "성적 장학금을 받았어요.",
    "김민수 교수님 수업이 제일 좋았어요.", "Prof. Schmidt 세미나를 들었어요.", "박지현 선배가 많이 도와줬어요.",
    "우리 학교에서 유일한 한국인이었어요.", "과대표를 맡고 있어서 바빴어요.", "제 학번은 H0469예요.",
    "궁금하면 010-1234-5678로 연락 주세요.", "메일은 someone@example.com이에요.",
]
ORDINARY = [
    "출국 3학기 전부터 어학 시험을 준비했어요.", "기숙사는 월 380유로였어요.", "담당 교수님께 메일을 보냈어요.",
    "지도 교수님 승인이 필요했어요.", "현지 선배님들이 많이 도와줬어요.", "이번 학기에는 수업이 많았어요.",
    "학점 인정은 6학점 받았어요.", "공항에서 기차로 한 시간 걸려요.", "세미나는 발표가 성적의 절반이에요.",
    "한국인 친구도 몇 명 있었어요.", "장학금 신청 기간을 놓치지 마세요.", "2학기에 3과목을 들었어요.",
    "같은 과 선배님께 물어봤어요.", "교환학생으로 선발됐어요.", "옆자리 선배가 방향을 잡아 주셨어요.",
]


def main():
    bad = [f"놓침: {s}" for s in IDENTIFYING if not check(s)["identifying"]]
    bad += [f"오탐: {s} {check(s)['reasons']}" for s in ORDINARY if check(s)["identifying"]]
    evidence = json.loads((Path(__file__).resolve().parent.parent / "data" / "evidence.json").read_text(encoding="utf-8"))
    bad += [f"근거 오탐: {e['id']} {check(e['text'])['reasons']}" for e in evidence if check(e["text"])["identifying"]]
    draft = mark({"sections": [{"name": "생활", "lines": [{"text": IDENTIFYING[0]}, {"text": ORDINARY[0]}]}]})
    if [ln["identifying"] for ln in draft["sections"][0]["lines"]] != [True, False]:
        bad.append("mark()가 identifying을 채우지 못함")
    print("\n".join(bad) or f"통과: 식별 {len(IDENTIFYING)}·일반 {len(ORDINARY)}·근거 문단 {len(evidence)}개")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
