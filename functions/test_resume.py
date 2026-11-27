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
from runtime_fns import add_question, find_my_note, getMyNote, save_my_note, saveConsent, updateMyNote

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
depth = [q for _, _, q, _ in interview.depth_questions(PROGRAM, interview.sections_of(PROGRAM))]
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

# 7) [작업 108] 깊이 질문은 번호로 「물었음」을 남기고 번호로 대조한다 — 비교과(한 인터뷰 2개, 모두 3개)
# 11/26 미리 폰 시험(H0019, 대동제 이벤트 Guardians): 문구가 바뀌자 같은 질문을 또 묻고, 세 번째 질문은 안 나왔다.
EXTRA = "교육혁신원 대동제 이벤트 Guardians(퀴즈 고득점을 위한 자료 업로드!)"
OLD_Q1 = "신청할 때 기대한 것과 실제로 얻은 게 같았나요?"   # 비교과-1의 바뀌기 전 문구(작업 93, b2867b0)
ALL3 = [d[0] for d in interview.DEPTH_QUESTIONS["비교과"]]
NOTE = {"sections": [{"name": "활동내용", "lines": [{"text": "활동을 했다."}]},
                     {"name": "배운점", "lines": [{"text": "많이 배웠다."}]}]}


def run_as(me, program):
    answers, steps = [], []
    while True:
        s = interview.interviewNext(me, {"program": program, "answers": answers})
        steps.append(s)
        if s.get("done") or len(steps) > 20:
            return answers, steps
        answers = answers + [{"section": s["section"], "question": s["question"],
                              "answer": f"{s['section']} 칸 이야기를 자세히 들려줄게요."}]


def depth_ids(steps):
    return [interview.depth_id(s["question"]) for s in steps if s.get("depth")]


expect("깊이 질문 번호는 겹치지 않음", len(interview.DEPTH_BY_ID) == sum(len(v) for v in interview.DEPTH_QUESTIONS.values()))
expect("바뀌기 전 문구도 그 질문의 번호로", interview.depth_id(OLD_Q1) == "비교과-1"
       and interview.depth_id("기대와 비교해 실제로 얻은 건 뭐였어요?") == "비교과-1")
expect("깊이 질문이 아닌 글은 번호 없음", interview.depth_id(interview.base_question(EXTRA, "배운점")) is None
       and interview.depth_id("") is None and interview.depth_id(None) is None)
expect("{p}가 든 질문은 이름이 달라도 같은 번호", interview.depth_id(
    "후배들이 마르부르크에 대해 잘 모르고 있는 것, 또는 잘못 알고 있는 게 있다면요?") == "교환-3"
       == interview.depth_id("후배들이 마르부르크필립스대학교에 대해 잘 모르고 있는 것, 또는 잘못 알고 있는 게 있다면요?"))

ME = "H0019"
ans_a, steps_a = run_as(ME, EXTRA)
first2 = depth_ids(steps_a)
expect("비교과 첫 방문: 깊이 질문 2개(한 인터뷰에 묻는 수 그대로)", len(first2) == 2 and None not in first2)
# 첫 방문 순서는 그대로(main과 같음): 빈 칸 기본 질문(활동내용) → 깊이 질문 2개(배운점 칸에 담겨 배운점 질문은 따로 없음) → done
expect("첫 방문 순서: 빈 칸 기본 질문 → 깊이 질문 2개 → done",
       [("깊이" if s.get("depth") else s.get("section")) for s in steps_a[:-1]] == ["활동내용", "깊이", "깊이"]
       and steps_a[0]["question"] == interview.base_question(EXTRA, "활동내용") and steps_a[-1].get("done") is True)
interview.summarizeInterview(ME, {"program": EXTRA, "transcript": ans_a})
_, rec_a = find_my_note(ME, EXTRA)
expect("요약하면 물은 깊이 질문 번호를 저장(askedDepth)", rec_a.get("askedDepth") == first2)
ans_b, steps_b = run_as(ME, EXTRA)
expect("앞 2개를 물은 뒤 방문하면 세 번째 질문이 나옴", depth_ids(steps_b) == [i for i in ALL3 if i not in first2]
       and steps_b[-1].get("done") is True)
interview.summarizeInterview(ME, {"program": EXTRA, "transcript": ans_b, "append": True})
_, rec_b = find_my_note(ME, EXTRA)
expect("append 요약: askedDepth 합침", sorted(rec_b["askedDepth"]) == sorted(ALL3))
_, steps_c = run_as(ME, EXTRA)
expect("다 물었으면 done", len(steps_c) == 1 and steps_c[0].get("done") is True)

# 옛 기록(번호 없이 글만): M-0003처럼 옛 문구·새 문구가 둘 다 asked에 있어도 같은 질문으로 보고 세 번째만 묻는다
q2 = interview.DEPTH_BY_ID["비교과-2"][2]
save_my_note("H0020", EXTRA, "D-old", NOTE, NOTE, asked=[OLD_Q1, q2, interview.DEPTH_BY_ID["비교과-1"][2]])
_, steps_old = run_as("H0020", EXTRA)
expect("문구가 바뀐 뒤에도 다시 묻지 않음(옛 기록 asked 글)", depth_ids(steps_old) == ["비교과-3"])
save_my_note("H0021", EXTRA, "D-old2", NOTE, NOTE, asked=[OLD_Q1])
_, steps_old2 = run_as("H0021", EXTRA)
expect("옛 문구 하나만 물었으면 나머지 둘을 물음", sorted(depth_ids(steps_old2)) == ["비교과-2", "비교과-3"])

# 번호로 남긴 기록은 글이 어떻게 바뀌었든 번호로 본다(지금 문구와 다른 글만 있어도)
save_my_note("H0022", EXTRA, "D-id", NOTE, NOTE, asked=["앞으로 바뀔지 모르는 문구"], asked_depth=["비교과-1", "비교과-3"])
_, steps_id = run_as("H0022", EXTRA)
expect("문구가 바뀐 뒤에도 다시 묻지 않음(askedDepth 번호)", depth_ids(steps_id) == ["비교과-2"])

# 8) [작업 111 후속] 초안은 대화형 화면이 붙인 reaction·kind·heardSection을 남긴다(길이 상한), 없으면 모양 그대로
import tell_chat
from runtime_fns import MAX_DRAFT_LABEL, MAX_DRAFT_REACTION, getInterviewDraft, saveInterviewDraft

plain = {"section": "생활", "question": "어땠어요?", "answer": "좋았어요."}
saveInterviewDraft(SENIOR, {"program": PROGRAM, "answers": [plain]})
expect("플래그 끔 초안 모양 그대로", getInterviewDraft(SENIOR, {"program": PROGRAM})["answers"] == [plain])
longest = "가" * tell_chat.MAX_REACTION + " " + tell_chat.HELD_TEXT
chat = {**plain, "reaction": longest, "kind": "답", "heardSection": "비용"}
saveInterviewDraft(SENIOR, {"program": PROGRAM, "answers": [chat, {**plain, "extra": 1}]})
got = getInterviewDraft(SENIOR, {"program": PROGRAM})["answers"]
expect("reaction·kind·heardSection 저장·불러오기 그대로(질문함 안내까지 붙은 긴 반응)", got == [chat, plain])
saveInterviewDraft(SENIOR, {"program": PROGRAM, "answers": [
    {**plain, "reaction": "가" * 500, "kind": "나" * 500, "heardSection": "다" * 500}]})
cut = getInterviewDraft(SENIOR, {"program": PROGRAM})["answers"][0]
expect("세 필드는 길이 상한으로 자름", [len(cut[k]) for k in ("reaction", "kind", "heardSection")]
       == [MAX_DRAFT_REACTION, MAX_DRAFT_LABEL, MAX_DRAFT_LABEL])
expect("초안은 본인만", getInterviewDraft(JUNIOR, {"program": PROGRAM}) == {"answers": []})

print(f"\n{len(fails)}건 실패" if fails else "\n모두 통과")
sys.exit(1 if fails else 0)
