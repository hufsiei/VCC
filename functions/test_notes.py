# test_notes.py — 질문함 → 인터뷰 → 공개 동의 → 질문자 알림 → 노트 Q·A → askBoo 근거 (작업 74·26)
# 실행: cd functions && python test_notes.py
# 완료 기준(작업 74): 후배1의 가상질문 23번 → 선배1 인터뷰 첫 질문 → 공개 동의 → 후배1 알림 → 노트 「후배 질문」 칸 Q·A
# AI는 가짜로 바꿔 돈을 쓰지 않는다. 기록은 임시 폴더에 쓴다(data/runtime을 건드리지 않음). 하나라도 틀리면 종료코드 1.
import json
import re
import sys
import tempfile
from pathlib import Path

import store

store.RUNTIME = Path(tempfile.mkdtemp()) / "runtime"

import askboo
import interview
import notes
from runtime_fns import add_question, getInbox, reportStatement, saveConsent

PROGRAM = "마르부르크필립스대학교"
JUNIOR, SENIOR, OTHER = "H0143", "H0469", "H0745"
Q23 = "마르부르크에서 학기 중 현지 인턴 병행할 수 있어요?"
A23 = "학기 중에는 수업이 많아 인턴은 어렵고, 방학에 단기 인턴을 했어요."


def fake_call(작업명, messages, system=None):
    """요약·변환은 받은 원문을 그대로 돌려준다(원문 인용 확인용). 고르기는 1번."""
    from ai import first_json
    c = messages[-1]["content"]
    if 작업명 == "요약":
        text = json.dumps({"문장": [re.search(r"답: (.*)\n출력", c, re.S).group(1)]}, ensure_ascii=False)
    elif 작업명 == "변환":
        text = json.dumps({"1": re.search(r"근거: (.*)\n출력", c, re.S).group(1)}, ensure_ascii=False)
    else:
        text = {"충분판정": '{"충분":true}', "일치검사": '{"일치":true}', "고르기": '{"관련":[1]}', "1인칭": "{}"}[작업명]
    return {"ok": True, "text": text, "json": first_json(text), "model": "fake"}


askboo.callAI = interview.callAI = fake_call
fails = []


def expect(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


def section(note, name):
    return next((s["lines"] for s in note["sections"] if s["name"] == name), None)


base = notes.NOTES[notes.note_id(PROGRAM)]
base_count = base["evidenceCount"]

# 1) 후배1이 23번을 묻는다 → 보고서에 없는 주제라 보류 → 질문함
r = askboo.askBoo(JUNIOR, {"question": Q23})
qid = r.get("questionId")
expect("23번은 보류 + 질문함", r["status"] == "hold" and qid)
other_qid = add_question(OTHER, "다른 학교 질문이에요", program="국립동양언어문화대학교 (이날코)", status="hold")

# 2) 선배1 인터뷰 첫 질문 = 그 후배 질문
s = interview.interviewNext(SENIOR, {"program": PROGRAM, "answers": []})
expect("선배1 첫 질문 = 23번", s.get("section") == "후배 질문" and s.get("questionId") == qid and s.get("asked") == Q23)

# 3) 요약. 후배 질문 칸이지만 질문함에 없는 질문(질문 id 없음), 다른 프로그램 질문 id를 붙인 답도 섞는다
transcript = [
    {"section": "후배 질문", "question": Q23, "questionId": qid, "answer": A23},
    {"section": "후배 질문", "question": "질문함에 없는 질문이에요?", "answer": "그건 잘 모르겠어요."},
    {"section": "후배 질문", "question": "다른 학교 질문이에요", "questionId": other_qid, "answer": "거기는 안 가 봤어요."},
    {"section": "지원", "question": "언제부터 준비하셨어요?", "answer": "출국 3학기 전부터 어학 시험을 준비했어요."},
]
d = interview.summarizeInterview(SENIOR, {"program": PROGRAM, "transcript": transcript})
pub = [ln for sec in d["publicDraft"]["sections"] for ln in sec["lines"]]
expect("요약 4문장", len(pub) == 4)

# 4) 남의 초안으로는 동의할 수 없다
expect("남의 초안 거절", saveConsent(JUNIOR, {"draftId": d["draftId"], "edits": {}, "consent": True}).get("error"))

# 5) 공개 동의 → 23번만 answered + 알림
c = saveConsent(SENIOR, {"draftId": d["draftId"], "edits": {"removed": []}, "consent": True})
expect("동의 응답 noteId·added·answered", c.get("ok") and c["noteId"] == "N-marburg" and c["added"] == 4 and c["answered"] == [qid])
qs = {q["id"]: q for q in store.load("questions", [])}
expect("23번 status answered + noteId", qs[qid]["status"] == "answered" and qs[qid]["noteId"] == "N-marburg")
expect("다른 프로그램 질문 id는 그대로 hold", qs[other_qid]["status"] == "hold")
alerts = store.load("alerts", {})
answered_alerts = [(who, a) for who, items in alerts.items() for a in items if a["text"].startswith("내 질문에 선배가 답했어요")]
expect("답변 알림은 후배1에게 1건만(칸 일치·남의 질문 id로는 안 보냄)",
       len(answered_alerts) == 1 and answered_alerts[0][0] == JUNIOR)
expect("알림 문구·questionId·noteId",
       answered_alerts[0][1] == {**answered_alerts[0][1], "text": f"내 질문에 선배가 답했어요 · {PROGRAM} 해봤노트",
                                 "questionId": qid, "noteId": "N-marburg"})

# 6) 후배1 내 보관함
inbox = getInbox(JUNIOR, {})
q = next(x for x in inbox["questions"] if x["questionId"] == qid)
expect("내 보관함: answered + 노트 링크 + 맨 위", q["status"] == "answered" and q["noteId"] == "N-marburg"
       and inbox["questions"][0]["questionId"] == qid and q.get("answeredAt"))
expect("내 보관함 알림 맨 위", inbox["alerts"][0]["questionId"] == qid)

# 7) 노트 「후배 질문」 칸 Q·A 원문 인용
note = notes.getNote(JUNIOR, {"id": "N-marburg"})
qa = section(note, "후배 질문")
expect("후배 질문 칸 Q·A 1쌍 + 질문 id 없는 답 1개", len(qa) == 3 and qa[0]["asked"] == Q23 and qa[0]["answersQuestionId"] == qid)
expect("A는 선배 문장 그대로(합치지 않음)", qa[0]["text"] == A23)
expect("질문 id 없는 답은 Q·질문 id 없이", "asked" not in qa[1] and "answersQuestionId" not in qa[1])
expect("다른 프로그램 질문 id는 노트에 남지 않음", all(ln.get("answersQuestionId") != other_qid for ln in qa))
sid = qa[0]["sourceId"]
expect("출처 = 인터뷰 + 학기", note["sources"][sid]["docType"] == "인터뷰" and (note["sources"][sid]["semester"] or "").startswith("20"))
expect("지원 칸 뒤에 인터뷰 문장", section(note, "지원")[-1]["text"] == "출국 3학기 전부터 어학 시험을 준비했어요.")
expect("evidenceCount + 4", note["evidenceCount"] == base_count + 4)
expect("응답에 선배 학번 없음", SENIOR not in json.dumps(note, ensure_ascii=False))
expect("officialUrl", "officialUrl" in note)
expect("사전 생성 노트는 그대로(메모리)", len(section(base, "후배 질문")) == 0)

card = next(n for n in notes.listNotes(JUNIOR, {"filter": {"q": PROGRAM}})["notes"] if n["id"] == "N-marburg")
expect("listNotes 근거 수 = getNote", card["evidenceCount"] == note["evidenceCount"])

# 8) 같은 초안으로 다시 동의해도 알림은 한 번, 문장은 바뀐 범위로(sourceId 유지)
c2 = saveConsent(SENIOR, {"draftId": d["draftId"], "edits": {"removed": [pub[3]["lineId"]]}, "consent": True})
note2 = notes.getNote(JUNIOR, {"id": "N-marburg"})
expect("다시 동의: answered 빈 목록", c2["answered"] == [] and len(answered_alerts) == 1 ==
       len([a for a in store.load("alerts", {})[JUNIOR] if a["text"].startswith("내 질문에")]))
expect("다시 동의: 뺀 문장만 빠짐 + sourceId 유지",
       note2["evidenceCount"] == base_count + 3 and section(note2, "후배 질문")[0]["sourceId"] == sid)

# 9) 다음 후배의 askBoo 근거가 된다
r2 = askboo.askBoo(OTHER, {"question": Q23})
expect("다른 후배 23번 → 답변(근거 = 선배 인터뷰)", r2["status"] == "ok" and r2["noteId"] == "N-marburg"
       and r2["lines"][0]["sourceId"] == sid and r2["sources"][sid]["docType"] == "인터뷰")

# 10) 신고한 문장은 노트·근거 풀에서 숨김
reportStatement(OTHER, {"lineId": "L-" + sid, "reason": "기타"})
expect("신고 → 노트에서 숨김", all(ln["sourceId"] != sid for ln in section(notes.getNote(JUNIOR, {"id": "N-marburg"}), "후배 질문")))
expect("신고 → 근거 풀에서 빠짐", all(x["id"] != sid for x in notes.interview_lines(PROGRAM)))

# 11) 없는 노트
expect("없는 노트는 오류", "error" in notes.getNote(JUNIOR, {"id": "N-없음"}))

print(f"\n{len(fails)}건 실패" if fails else "\n모두 통과")
sys.exit(1 if fails else 0)
