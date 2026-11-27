# test_question_candidates.py — [Q-109] 업체 유형으로만 잡힌 보류 질문을 후보 업체 선배 모두에게(작업 35 A1 후속). AI 없음.
# 보는 것: ① 질문함 행의 후보유형·후보프로그램명 ② 들려주기 후배 질문(junior_questions)·답 연결(_question_row·publish_lines)
#         ③ getInbox candidates ④ 수요 정리에서 프로그램을 고르면 그 업체만 ⑤ 이름 부른 질문은 그대로
# 실행: cd functions && python test_question_candidates.py   (임시 runtime 폴더 — 실제 data/runtime을 건드리지 않는다)
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import store  # noqa: E402

store.RUNTIME = Path(tempfile.mkdtemp()) / "runtime"

import askboo  # noqa: E402
import interview  # noqa: E402
import runtime_fns  # noqa: E402
from runtime_fns import add_question, getInbox, publish_lines, question_for  # noqa: E402

fails = []


def expect(name, cond, info=""):
    print(("ok   " if cond else "FAIL ") + name + (f"  — {info}" if info and not cond else ""))
    if not cond:
        fails.append(name)


JUNIOR, SENIOR_A, SENIOR_B, SENIOR_X = "H0001", "H0901", "H0902", "H0903"
Q = "승무원이 꿈인데 스타트업 여행사 인턴십에 합격했어요. 진로에 도움이 될까요?"
CANDS = askboo._type_candidates(Q)
A, B = CANDS["programs"][0], CANDS["programs"][-1]           # 스타트업 첫 업체 · 여행사 마지막 업체
OTHER = next(n for n, p in askboo.PROGRAMS.items() if p.get("분야") == "현장실습" and n not in CANDS["programs"])
expect("전제: 후보 = 스타트업 + 여행사 업체 전부", CANDS["label"] == "스타트업·여행사 현장실습" and len(CANDS["programs"]) == 7, CANDS)

# ① 질문함 행
qid = add_question(JUNIOR, Q, program=None, status="hold", candidates=CANDS)
named = add_question(JUNIOR, f"{OTHER} 인턴 근무 시간 어때요?", program=OTHER, status="hold", candidates=CANDS)
plain = add_question(JUNIOR, "이중전공 vs 부전공", program=None, status="hold")
rows = {q["id"]: q for q in store.load("questions", [])}
expect("① 후보 행: 후보유형·후보프로그램명", rows[qid].get("후보유형") == CANDS["label"]
       and rows[qid].get("후보프로그램명") == CANDS["programs"] and rows[qid]["프로그램명"] is None, rows[qid])
expect("① 프로그램이 있으면 후보를 남기지 않음", "후보프로그램명" not in rows[named], rows[named])
expect("① 후보 없는 행은 그전 모양", "후보프로그램명" not in rows[plain] and "후보유형" not in rows[plain], rows[plain])

# ② 들려주기 후배 질문
ids = lambda me, program: [q["id"] for q in interview.junior_questions(me, program)]  # noqa: E731
expect("② 후보 업체 A 선배가 받음", qid in ids(SENIOR_A, A), ids(SENIOR_A, A))
expect("② 후보 업체 B(여행사) 선배도 받음", qid in ids(SENIOR_B, B), ids(SENIOR_B, B))
expect("② 후보 밖 업체 선배는 안 받음", qid not in ids(SENIOR_X, OTHER) and named in ids(SENIOR_X, OTHER), ids(SENIOR_X, OTHER))
expect("② 교환 학교 선배는 안 받음", qid not in ids(SENIOR_X, "마르부르크필립스대학교"))
expect("② 질문한 사람 본인에게는 안 나옴", qid not in ids(JUNIOR, A))
expect("② 프로그램도 후보도 없는 질문은 아무에게도", all(plain not in ids(SENIOR_A, p) for p in [A, B, OTHER]))
expect("② _question_row: 후보 업체로 받은 질문을 찾음(id·원문)",
       (interview._question_row(A, qid) or {}).get("id") == qid
       and (interview._question_row(B, None, Q) or {}).get("id") == qid and interview._question_row(OTHER, qid) is None)

# ③ getInbox
card = next(q for q in getInbox(JUNIOR, {})["questions"] if q["questionId"] == qid)
expect("③ getInbox: program null + candidates {label, programs}", card["program"] is None
       and card["candidates"] == {"label": CANDS["label"], "programs": CANDS["programs"]}, card)
others = [q for q in getInbox(JUNIOR, {})["questions"] if q["questionId"] != qid]
expect("③ getInbox: 후보 없는 질문은 candidates null(늘 있음)", all("candidates" in q and q["candidates"] is None for q in others), others)

# ④ 답 연결: 후보 업체 선배 둘이 답해도 둘 다 연결 · 알림
line = lambda me, did: {"text": "스타트업이라 업무 범위가 넓었어요.", "draftLineId": did, "section": "업무내용",  # noqa: E731
                        "official": False, "answersQuestionId": qid, "asked": Q}
_, done_a = publish_lines(SENIOR_A, A, "M-9001", [line(SENIOR_A, "D-1")])
row = next(q for q in store.load("questions", []) if q["id"] == qid)
expect("④ A 선배 답 → answered · 알림", done_a == [qid] and row["status"] == "answered", (done_a, row.get("status")))
expect("④ 답해도 프로그램명은 비워 둠(다른 후보 선배 답도 연결)", row["프로그램명"] is None and question_for(row, B))
_, done_b = publish_lines(SENIOR_B, B, "M-9002", [line(SENIOR_B, "D-2")])
expect("④ B 선배 답도 연결 · 알림", done_b == [qid], done_b)
_, done_x = publish_lines(SENIOR_X, OTHER, "M-9003", [line(SENIOR_X, "D-3")])
expect("④ 후보 밖 업체 선배가 questionId를 붙여도 연결 안 됨", done_x == [], done_x)
expect("④ answered는 후배 질문 목록에서 빠짐", qid not in ids(SENIOR_A, A))

# ⑤ 수요 정리에서 프로그램을 고르면(행의 프로그램명이 채워짐) 그 업체만
qid2 = add_question(JUNIOR, "스타트업 인턴 면접 어땠어요?", program=None, status="hold", candidates=CANDS)
for q in store.load("questions", []):
    if q["id"] == qid2:
        q["프로그램명"] = B   # demand.saveDemand(작업 117)가 하는 일
expect("⑤ 프로그램을 고르면 그 업체 선배만", qid2 in ids(SENIOR_B, B) and qid2 not in ids(SENIOR_A, A))
card2 = next(q for q in getInbox(JUNIOR, {})["questions"] if q["questionId"] == qid2)
expect("⑤ 그때 getInbox candidates는 null", card2["program"] == B and card2["candidates"] is None, card2)

expect("question_for: 빈 값", not question_for(None, A) and not question_for(rows[qid], None))

print()
print("실패 %d개" % len(fails) if fails else "전부 통과")
sys.exit(1 if fails else 0)
