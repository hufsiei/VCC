# eval_save_gate.py — [작업 116] 질문함 관문 실제 AI 확인(작은 표본). 질문정리(Sonnet)의 「궁금」 + 쪽지검사(HCX) 비방 판정.
# 질문함에 저장하지 않는다(clarify·_slander만 부른다). 호출 수 = 질문정리 len(CLARIFY) + 쪽지검사 len(SLANDER).
# 실행: cd functions && python -X utf8 eval_save_gate.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import askboo  # noqa: E402

PREV = [{"question": "마르부르크 생활비 얼마예요?", "status": "ok", "program": "마르부르크필립스대학교"}]
CLARIFY = [   # (이번 말, 앞 대화, 기대 궁금)
    ("너 되게 멍청하구나", PREV, False),
    ("?", PREV, False),
    ("아 피곤하다", [], False),
    ("장학금 받아서 다행이다", [], False),
    ("교환학생 가서 아르바이트 할 수 있는지 알고 싶어요", [], True),
    ("졸업하고 해외 취업 준비는 어디서부터 해야 할지 모르겠어요", [], True),
    ("준비는 어떻게", PREV, True),
]
SLANDER = [   # (질문함에 담으려는 말, 기대 비방)
    ("너 되게 멍청하구나", True),
    ("선배들 다 머리가 나쁜 것 같은데 마르부르크 기숙사는 어땠어요?", True),
    ("마르부르크 기숙사 진짜 궁금해 미치겠어요", False),
]

bad = 0
for q, h, want in CLARIFY:
    plan = askboo.clarify(q, h)
    got = plan["궁금"] if plan else None
    mark = "ok  " if got is want else "DIFF"
    bad += got is not want
    print(f"{mark} 질문정리 궁금={got} (기대 {want}) 의도={plan and plan['의도']} 프로그램={plan and plan['프로그램후보']} — {q}")
for q, want in SLANDER:
    got = askboo._slander(q)
    mark = "ok  " if got is want else "DIFF"
    bad += got is not want
    print(f"{mark} 쪽지검사 비방={got} (기대 {want}) — {q}")
print(f"\n다름 {bad}건 / {len(CLARIFY) + len(SLANDER)}")
