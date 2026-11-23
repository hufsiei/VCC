# test_question_edit.py — 내 질문 지우기·고치기(작업 91, spec 4장 deleteQuestion·updateQuestion [v2]).
# 실행: cd functions && python test_question_edit.py. AI 없음, 기록은 임시 폴더. 하나라도 틀리면 종료코드 1.
import sys
import tempfile
from pathlib import Path

import store

store.RUNTIME = Path(tempfile.mkdtemp()) / "runtime"

import interview
from runtime_fns import ROUTES, add_question, deleteQuestion, getInbox, publish_lines, updateQuestion

PROGRAM = "마르부르크필립스대학교"
JUNIOR, OTHER, SENIOR = "H0143", "H0745", "H0469"
fails = []


def expect(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


def row(qid):
    return next(q for q in store.load("questions", []) if q["id"] == qid)


hold = add_question(JUNIOR, "마르부르크 기숙사 인터넷은 어떻게 신청해요?", program=PROGRAM, section="생활")
keep = add_question(JUNIOR, "마르부르크 겨울 난방비는 얼마나 나와요?", program=PROGRAM, section="비용")
ans = add_question(JUNIOR, "마르부르크 학생증으로 버스 타요?", program=PROGRAM, section="생활", status="answered")
off = add_question(JUNIOR, "장학금 받을 수 있어요?", program=PROGRAM, status="official")

expect("ROUTES에 두 함수", ROUTES.get("deleteQuestion") is deleteQuestion and ROUTES.get("updateQuestion") is updateQuestion)

# 1) 고치기
r = updateQuestion(JUNIOR, {"questionId": hold, "text": "  마르부르크 기숙사 인터넷은\n 언제 신청해요?  "})
expect("고치기: 공백 정리 + editedAt", r.get("ok") and r["text"] == "마르부르크 기숙사 인터넷은 언제 신청해요?" and r.get("editedAt"))
expect("고치기: 질문 행 덧씀, 프로그램·칸 그대로", row(hold)["질문"] == r["text"] and row(hold)["칸"] == "생활"
       and row(hold)["프로그램명"] == PROGRAM and row(hold)["status"] == "hold")
expect("고치기: 빈 문장 오류", "error" in updateQuestion(JUNIOR, {"questionId": hold, "text": "   "}))
expect("고치기: 300자 초과 오류", "error" in updateQuestion(JUNIOR, {"questionId": hold, "text": "가" * 301}))
expect("고치기: 300자는 됨", updateQuestion(JUNIOR, {"questionId": keep, "text": "나" * 299 + "?"}).get("ok"))
bad = updateQuestion(JUNIOR, {"questionId": hold, "text": "010-1234-5678로 연락 주세요"})
expect("고치기: 연락처 → error + reason", bad.get("error") == "질문에 연락처·메일·링크를 넣을 수 없어요" and bad.get("reason") == "연락처")
expect("고치기: 걸린 문장은 저장 안 함", row(hold)["질문"] == r["text"])
expect("고치기: 남의 질문", updateQuestion(OTHER, {"questionId": hold, "text": "남이 고친 질문이에요?"}) == {"error": "볼 수 없는 기록이에요"})
expect("고치기: 없는 질문", updateQuestion(JUNIOR, {"questionId": "Q-9999", "text": "없는 질문이에요?"}) == {"error": "볼 수 없는 기록이에요"})
expect("고치기: answered", updateQuestion(JUNIOR, {"questionId": ans, "text": "고쳐 볼게요?"}) == {"error": "선배가 답한 질문은 고칠 수 없어요"})
expect("고치기: official", updateQuestion(JUNIOR, {"questionId": off, "text": "고쳐 볼게요?"}) == {"error": "공식 안내 질문은 고칠 수 없어요"})

# 2) 고친 질문이 다음 선배 인터뷰에 나간다
expect("인터뷰엔 고친 질문 글", any(q["id"] == hold and q["질문"] == r["text"]
                                for q in interview.junior_questions(SENIOR, PROGRAM)))

# 3) 지우기
expect("지우기: answered", deleteQuestion(JUNIOR, {"questionId": ans}) == {"error": "선배가 답한 질문은 지울 수 없어요"})
expect("지우기: official", deleteQuestion(JUNIOR, {"questionId": off}) == {"error": "공식 안내 질문은 지울 수 없어요"})
expect("지우기: 남의 질문", deleteQuestion(OTHER, {"questionId": hold}) == {"error": "볼 수 없는 기록이에요"})
d = deleteQuestion(JUNIOR, {"questionId": hold})
expect("지우기: ok + deleted", d == {"ok": True, "questionId": hold, "status": "deleted"})
expect("지우기: 행은 남음(소프트) + deletedAt", row(hold)["status"] == "deleted" and row(hold).get("deletedAt"))
expect("지우기: 두 번 지우면 오류", deleteQuestion(JUNIOR, {"questionId": hold}) == {"error": "볼 수 없는 기록이에요"})
expect("지운 뒤 고치기 오류", "error" in updateQuestion(JUNIOR, {"questionId": hold, "text": "다시 고칠게요?"}))
inbox = [q["questionId"] for q in getInbox(JUNIOR, {})["questions"]]
expect("getInbox에서 빠짐(다른 질문은 그대로)", hold not in inbox and {keep, ans, off} <= set(inbox))
expect("인터뷰 후배 질문에서 빠짐", hold not in {q["id"] for q in interview.junior_questions(SENIOR, PROGRAM)})

# 4) 선배가 답하는 도중 지워진 질문: 문장은 칸 문장으로 싣고 answered·알림·asked 없음
nid, answered = publish_lines(SENIOR, PROGRAM, "M-TEST", [
    {"section": "생활", "draftLineId": "L-D9-1", "text": "기숙사 인터넷은 입주 첫 주에 신청했어요.", "official": False,
     "answersQuestionId": hold, "asked": r["text"]}])
line = next(x for x in store.load("noteLines", []) if x["draftLineId"] == "L-D9-1")
expect("지운 질문 답: answered 전환·알림 없음", answered == [] and row(hold)["status"] == "deleted")
expect("지운 질문 답: 칸 문장으로만", line["section"] == "생활" and "answersQuestionId" not in line and "asked" not in line)

print(f"\n{len(fails)}건 실패" if fails else "\n모두 통과")
sys.exit(1 if fails else 0)
