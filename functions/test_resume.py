# test_resume.py — 이어 쓰기(작업 90, spec 4장 interviewNext·summarizeInterview [v2]). 실행: cd functions && python test_resume.py
# 첫 인터뷰 → 요약(내 경험노트) → 고치기·공유 → 다시 들려주기(resumed, 이미 한 칸·질문 건너뜀) → append 요약 → 다시 공유.
# AI는 가짜(돈 안 씀), 기록은 임시 폴더. 하나라도 틀리면 종료코드 1.
import json
import re
import sys
import tempfile
from pathlib import Path

import store

store.RUNTIME = Path(tempfile.mkdtemp()) / "runtime"

import interview
from runtime_fns import add_question, find_my_note, getMyNote, saveConsent, updateMyNote

PROGRAM = "마르부르크필립스대학교"
SENIOR, JUNIOR = "H0469", "H0143"


def fake_call(작업명, messages, system=None):
    """요약은 답 원문을 그대로, 1인칭은 비워서 해요체 그대로 둔다."""
    from ai import first_json
    c = messages[-1]["content"]
    if 작업명 == "요약":
        text = json.dumps({"문장": [re.search(r"답: (.*)\n출력", c, re.S).group(1)]}, ensure_ascii=False)
    else:
        text = {"충분판정": '{"충분":true}', "일치검사": '{"일치":true}', "1인칭": "{}", "문단분류": '{"칸":"생활"}'}[작업명]
    return {"ok": True, "text": text, "json": first_json(text), "model": "fake"}


interview.callAI = fake_call
fails = []


def expect(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


def run(answers):
    """끝날 때까지 interviewNext를 부르며 정해 둔 답을 넣는다. 돌려주는 값: (answers, 물은 단계들)."""
    steps = []
    while True:
        s = interview.interviewNext(SENIOR, {"program": PROGRAM, "answers": answers})
        steps.append(s)
        if s.get("done"):
            return answers, steps
        a = {"section": s["section"], "question": s["question"], "answer": f"{s['section']} 칸 이야기를 자세히 들려줄게요."}
        if s.get("questionId"):
            a["questionId"] = s["questionId"]
        answers = answers + [a]


q1 = add_question(JUNIOR, "마르부르크 기숙사 인터넷은 어떻게 신청해요?", program=PROGRAM, section="생활", status="hold")

# 1) 첫 인터뷰: 내 경험노트가 없으면 resumed 없음
first = interview.interviewNext(SENIOR, {"program": PROGRAM, "answers": []})
expect("첫 인터뷰엔 resumed 없음", "resumed" not in first and first.get("questionId") == q1)
answers1, steps1 = run([])
asked1 = [s["question"] for s in steps1 if not s.get("done")]
depth = [q for _, q, _ in interview.depth_questions(PROGRAM, interview.sections_of(PROGRAM))]
expect("첫 인터뷰에서 깊이 질문 3개를 다 물음", all(q in asked1 for q in depth))

# 깊이 질문 하나는 아직 안 한 것으로 만들기 위해 첫 요약은 앞의 세 답만(후배 질문 + 깊이 2)
d1 = interview.summarizeInterview(SENIOR, {"program": PROGRAM, "transcript": answers1[:3]})
mid = d1["myNoteId"]
_, rec = find_my_note(SENIOR, PROGRAM)
expect("요약하면 물은 질문을 저장(asked)", len(rec["asked"]) == 3 and depth[0] in rec["asked"])

# 선배가 문장 하나를 고치고, 하나만 빼고 공유
pub1 = [ln for sec in d1["publicDraft"]["sections"] for ln in sec["lines"]]
updateMyNote(SENIOR, {"id": mid, "changed": [{"section": d1["myNote"]["sections"][0]["name"], "index": 0,
                                                "text": "내가 고친 첫 문장이다."}]})
c1 = saveConsent(SENIOR, {"draftId": d1["draftId"], "edits": {"removed": [pub1[-1]["lineId"]]}, "consent": True})
expect("첫 공유: 후배 질문 answered", c1.get("ok") and c1["answered"] == [q1])
sid_before = {r["draftLineId"]: r["sourceId"] for r in store.load("noteLines", []) if r.get("myNoteId") == mid}

# 2) 다시 들려주기: resumed·myNoteId, 내 경험노트 칸은 답한 것으로, 이미 한 질문은 다시 묻지 않음
q2 = add_question(JUNIOR, "마르부르크 겨울 난방비는 얼마나 나와요?", program=PROGRAM, section="비용", status="hold")
again = interview.interviewNext(SENIOR, {"program": PROGRAM, "answers": []})
mine_sections = {s["name"] for s in d1["myNote"]["sections"]}
expect("다시 오면 resumed + myNoteId", again.get("resumed") is True and again.get("myNoteId") == mid)
expect("내 경험노트 칸 수가 진행에 들어감", again["progress"]["filled"] == len(mine_sections) == again["progress"]["mine"])
expect("새 후배 질문만 먼저(이미 답한 질문은 안 나옴)", again.get("questionId") == q2 and again.get("pendingQuestions") == 1)
answers2, steps2 = run([])
asked2 = [s["question"] for s in steps2 if not s.get("done")]
expect("지난번에 물은 깊이 질문은 다시 묻지 않음", depth[0] not in asked2 and depth[1] not in asked2)
expect("아직 안 한 깊이 질문은 물음", depth[2] in asked2)
expect("둘째 응답부터는 resumed 없음", all("resumed" not in s for s in steps2[1:]))

# 3) append 요약: 기존 문장(고친 것 포함)은 그대로, 새 문장 new: true, 응답은 합친 전체
d2 = interview.summarizeInterview(SENIOR, {"program": PROGRAM, "transcript": answers2, "append": True})
mine2 = [ln for sec in d2["myNote"]["sections"] for ln in sec["lines"]]
pub2 = [ln for sec in d2["publicDraft"]["sections"] for ln in sec["lines"]]
old_ids = [ln["lineId"] for ln in pub1]
expect("같은 myNoteId · 새 draftId", d2["myNoteId"] == mid and d2["draftId"] != d1["draftId"])
expect("고친 문장 그대로", any(ln["text"] == "내가 고친 첫 문장이다." and ln.get("edited") for ln in mine2))
expect("기존 공개 문장 lineId 그대로", [ln["lineId"] for ln in pub2 if not ln.get("new")] == old_ids)
n2 = d2["draftId"].split("-")[-1].lstrip("0")
new_pub = [ln for ln in pub2 if ln.get("new")]
expect("새 문장은 새 lineId(L-D{n}-k) + new", new_pub and all(ln["lineId"].startswith(f"L-D{n2}-") for ln in new_pub))
expect("myNote 새 문장 수 = 공개 새 문장 수", sum(1 for ln in mine2 if ln.get("new")) == len(new_pub))
expect("칸 순서는 노트 틀 순서", [s["name"] for s in d2["publicDraft"]["sections"]]
       == [n for n in interview.sections_of(PROGRAM) if n in {s["name"] for s in d2["publicDraft"]["sections"]}])
expect("answered는 큰 쪽", d2["answered"] >= d1["answered"])
_, rec2 = find_my_note(SENIOR, PROGRAM)
expect("저장본엔 new 표시 없음", not any(ln.get("new") for s in rec2["publicDraft"]["sections"] for ln in s["lines"]))
expect("asked 합침", set(rec["asked"]) <= set(rec2["asked"]) and len(rec2["asked"]) > len(rec["asked"]))
expect("공유 상태 그대로(partial)", getMyNote(SENIOR, {"id": mid}).get("share") == "partial")

# 4) 합친 초안으로 다시 공유: 기존 문장 sourceId 유지, 새 후배 질문 answered
c2 = saveConsent(SENIOR, {"draftId": d2["draftId"], "edits": {"removed": [pub1[-1]["lineId"]]}, "consent": True})
rows = {r["draftLineId"]: r["sourceId"] for r in store.load("noteLines", []) if r.get("myNoteId") == mid}
expect("다시 공유: 기존 문장 sourceId 유지", all(rows.get(k) == v for k, v in sid_before.items()))
expect("다시 공유: 새 문장도 실림 + q2 answered", len(rows) == len(sid_before) + len(new_pub) and c2["answered"] == [q2])

# 5) append 없이 요약하면 지금처럼 통째로 바꾼다
d3 = interview.summarizeInterview(SENIOR, {"program": PROGRAM, "transcript": answers2[:1]})
expect("append 없으면 교체(new 없음)", not any(ln.get("new") for s in d3["publicDraft"]["sections"] for ln in s["lines"])
       and sum(len(s["lines"]) for s in d3["publicDraft"]["sections"]) == 1)

# 6) append인데 내 경험노트가 없으면 처음처럼
other = "H0745"
d4 = interview.summarizeInterview(other, {"program": PROGRAM, "transcript": answers1[:1], "append": True})
expect("노트 없는 append = 새 노트, 문장 전부 new", d4["saved"] and all(
    ln.get("new") for s in d4["publicDraft"]["sections"] for ln in s["lines"]))

print(f"\n{len(fails)}건 실패" if fails else "\n모두 통과")
sys.exit(1 if fails else 0)
