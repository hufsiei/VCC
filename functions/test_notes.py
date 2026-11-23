# test_notes.py — 질문함 → 인터뷰 → 공개 동의 → 질문자 알림 → 노트 Q·A → askBoo 근거 (작업 74·26)
# 실행: cd functions && python test_notes.py
# 완료 기준(작업 74): 후배1의 가상질문 23번 → 선배1 인터뷰 첫 질문 → 공개 동의 → 후배1 알림 → 노트 「후배 질문」 칸 Q·A
# [v2 작업 89] 「후배 질문」 칸은 없다 → 답 문장은 질문의 칸(여기서는 문단분류 가짜가 고른 「팁」)에 answersQuestionId·asked와 함께
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
        text = {"충분판정": '{"충분":true}', "일치검사": '{"일치":true}', "고르기": '{"관련":[1]}', "1인칭": "{}",
                "문단분류": '{"칸":"팁"}'}[작업명]
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
expect("선배1 첫 질문 = 23번(junior, 칸 = 팁)", s.get("junior") and s.get("section") == "팁"
       and s.get("questionId") == qid and s.get("asked") == Q23)

# 3) 요약. 옛 화면(「후배 질문」 칸)으로 온 질문함에 없는 질문(질문 id 없음), 다른 프로그램 질문 id를 붙인 답도 섞는다
transcript = [
    {"section": s["section"], "question": s["question"], "questionId": qid, "answer": A23},
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

# 7) 노트: 「후배 질문」 칸은 없고 답은 질문의 칸(팁) 뒤에 원문 인용
note = notes.getNote(JUNIOR, {"id": "N-marburg"})
expect("「후배 질문」 칸 없음", section(note, "후배 질문") is None)
tip = section(note, "팁")
qa = [ln for ln in tip if ln.get("sourceId", "").startswith("I-")]
expect("팁 칸 뒤에 인터뷰 문장 3개(23번 답 + 질문 id 없는 답 + 남의 질문 id 답)",
       len(qa) == 3 and qa[0]["asked"] == Q23 and qa[0]["answersQuestionId"] == qid)
expect("A는 선배 문장 그대로(합치지 않음)", qa[0]["text"] == A23)
expect("질문 id 없는 답은 Q·질문 id 없이", "asked" not in qa[1] and "answersQuestionId" not in qa[1])
expect("다른 프로그램 질문 id는 노트에 남지 않음(asked도)", all(ln.get("answersQuestionId") != other_qid for ln in qa)
       and "asked" not in qa[2])
sid = qa[0]["sourceId"]
expect("출처 = 인터뷰 + 학기", note["sources"][sid]["docType"] == "인터뷰" and (note["sources"][sid]["semester"] or "").startswith("20"))
expect("지원 칸 뒤에 인터뷰 문장", section(note, "지원")[-1]["text"] == "출국 3학기 전부터 어학 시험을 준비했어요.")
expect("evidenceCount + 4", note["evidenceCount"] == base_count + 4)
expect("응답에 선배 학번 없음", SENIOR not in json.dumps(note, ensure_ascii=False))
expect("officialUrl", "officialUrl" in note)
expect("사전 생성 노트는 그대로(메모리)", not any(ln.get("sourceId", "").startswith("I-") for ln in section(base, "팁")))

card = next(n for n in notes.listNotes(JUNIOR, {"filter": {"q": PROGRAM}})["notes"] if n["id"] == "N-marburg")
expect("listNotes 근거 수 = getNote", card["evidenceCount"] == note["evidenceCount"])

# 8) 같은 초안으로 다시 동의해도 알림은 한 번, 문장은 바뀐 범위로(sourceId 유지)
c2 = saveConsent(SENIOR, {"draftId": d["draftId"], "edits": {"removed": [pub[3]["lineId"]]}, "consent": True})
note2 = notes.getNote(JUNIOR, {"id": "N-marburg"})
expect("다시 동의: answered 빈 목록", c2["answered"] == [] and len(answered_alerts) == 1 ==
       len([a for a in store.load("alerts", {})[JUNIOR] if a["text"].startswith("내 질문에")]))
expect("다시 동의: 뺀 문장만 빠짐 + sourceId 유지",
       note2["evidenceCount"] == base_count + 3
       and [ln for ln in section(note2, "팁") if ln.get("answersQuestionId")][0]["sourceId"] == sid)

# 9) 다음 후배의 askBoo 근거가 된다
r2 = askboo.askBoo(OTHER, {"question": Q23})
expect("다른 후배 23번 → 답변(근거 = 선배 인터뷰)", r2["status"] == "ok" and r2["noteId"] == "N-marburg"
       and r2["lines"][0]["sourceId"] == sid and r2["sources"][sid]["docType"] == "인터뷰")

# 10) 신고한 문장은 노트·근거 풀에서 숨김
reportStatement(OTHER, {"lineId": "L-" + sid, "reason": "기타"})
expect("신고 → 노트에서 숨김", all(ln["sourceId"] != sid for ln in section(notes.getNote(JUNIOR, {"id": "N-marburg"}), "팁")))
expect("신고 → 근거 풀에서 빠짐", all(x["id"] != sid for x in notes.interview_lines(PROGRAM)))

# 11) 없는 노트
expect("없는 노트는 오류", "error" in notes.getNote(JUNIOR, {"id": "N-없음"}))

# 12) 국가(카드 띠 「교환학생 · 독일」) — 국제교류만, 인턴·비교과는 null
cards = {n["id"]: n for n in notes.listNotes(JUNIOR, {})["notes"]}
expect("국가: 마르부르크 = 독일", cards["N-marburg"]["country"] == "독일" and notes.getNote(JUNIOR, {"id": "N-marburg"})["country"] == "독일")
expect("국가: 비교과는 null", cards["N-3ca17d"]["country"] is None and cards["N-3ca17d"]["completedCount"] == 150)
expect("국가: 인턴은 null", all(c["country"] is None for c in cards.values() if c["type"] == "인턴"))

# 12-1) [11/23 주제별] 인턴 kind(기관유형)·나라/기관유형 묶음 칩·필터·비교과 이수 인원순
all_res = notes.listNotes(JUNIOR, {})
expect("kind: 인턴만 기관유형, 나머지 null",
       all((c["kind"] is not None) == (c["type"] == "인턴") for c in all_res["notes"])
       and notes.getNote(JUNIOR, {"id": "N-marburg"})["kind"] is None)
intern = notes.listNotes(JUNIOR, {"filter": {"type": "인턴"}})
kinds = intern["groups"]["kind"]
expect("인턴 묶음 칩: 기관유형별 수 합 = 카드 수, 많은 순",
       sum(g["count"] for g in kinds) == len(intern["notes"]) and kinds == sorted(kinds, key=lambda g: (-g["count"], g["name"]))
       and intern["groups"]["country"] == [])
k0 = kinds[0]
by_kind = notes.listNotes(JUNIOR, {"filter": {"type": "인턴", "kind": k0["name"]}})
expect("kind 필터 → 그 기관유형만, 칩은 그대로", len(by_kind["notes"]) == k0["count"]
       and all(c["kind"] == k0["name"] for c in by_kind["notes"]) and by_kind["groups"] == intern["groups"])
ex = notes.listNotes(JUNIOR, {"filter": {"type": "교환"}})
de = notes.listNotes(JUNIOR, {"filter": {"type": "교환", "country": "독일"}})
expect("country 필터 → 독일 교환만(마르부르크 포함)", de["notes"] and all(c["country"] == "독일" for c in de["notes"])
       and "N-marburg" in [c["id"] for c in de["notes"]]
       and next(g for g in ex["groups"]["country"] if g["name"] == "독일")["count"] == len(de["notes"]))
done = [c["completedCount"] for c in notes.listNotes(JUNIOR, {"filter": {"type": "비교과"}})["notes"]]
expect("비교과는 이수 인원 많은 순", done == sorted(done, key=lambda n: -(n or -1)) and done[0] == max(n or 0 for n in done))
expect("전체 목록에서 비교과 아닌 카드 순서는 그대로",
       [c["id"] for c in all_res["notes"] if c["type"] != "비교과" and c["id"] in notes.NOTES]
       == [i for i, n in notes.NOTES.items() if n["type"] != "비교과"])

# 13) 스크랩 켜기·끄기 → 카드·노트 scrapped, 내 보관함 scraps(최근이 위), 사람마다 따로
expect("스크랩 처음엔 꺼짐", cards["N-marburg"]["scrapped"] is False and getInbox(JUNIOR, {})["scraps"] == [])
s1 = notes.scrapNote(JUNIOR, {"noteId": "N-marburg"})
notes.scrapNote(JUNIOR, {"noteId": "N-3ca17d", "scrap": True})
notes.scrapNote(JUNIOR, {"noteId": "N-marburg", "scrap": True})   # 두 번 눌러도 하나
expect("스크랩 응답", s1 == {"ok": True, "noteId": "N-marburg", "scrapped": True})
expect("보관함 scraps 최근이 위·중복 없음", [s["noteId"] for s in getInbox(JUNIOR, {})["scraps"]] == ["N-3ca17d", "N-marburg"]
       and getInbox(JUNIOR, {})["scraps"][1]["program"] == PROGRAM)
expect("카드·노트 scrapped", notes.getNote(JUNIOR, {"id": "N-marburg"})["scrapped"] is True
       and {n["id"]: n for n in notes.listNotes(JUNIOR, {})["notes"]}["N-3ca17d"]["scrapped"] is True)
expect("다른 사람에게는 꺼짐", notes.getNote(OTHER, {"id": "N-marburg"})["scrapped"] is False and getInbox(OTHER, {})["scraps"] == [])
off = notes.scrapNote(JUNIOR, {"noteId": "N-marburg", "scrap": False})
expect("스크랩 끄기", off["scrapped"] is False and [s["noteId"] for s in getInbox(JUNIOR, {})["scraps"]] == ["N-3ca17d"])
expect("없는 노트 스크랩은 오류", "error" in notes.scrapNote(JUNIOR, {"noteId": "N-없음"}) and "error" in notes.scrapNote(JUNIOR, {}))

# 14) [11/22] 배운점 선배 글자 — 노트 안에서만 「선배 A」, 학과·학번 없음, 같은 사람은 같은 글자
lesson_ids = [nid for nid, n in notes.NOTES.items()
              if len({notes._source_owner(ln["sourceId"]) for s in n["sections"] if s["name"] == "배운점" for ln in s["lines"]}) >= 2]
expect("배운점 선배 둘 이상인 사전 노트가 있다", bool(lesson_ids))
ok_label = True
for nid in lesson_ids[:10]:
    lines = section(notes.getNote(JUNIOR, {"id": nid}), "배운점")
    who = {}
    for ln in lines:
        lab, sid = ln.get("senior"), ln["sourceId"]
        ok_label &= bool(lab) and re.fullmatch(r"선배 [A-Z]", lab or "") is not None
        owner = notes._source_owner(sid)
        ok_label &= who.setdefault(owner, lab) == lab   # 같은 사람 = 같은 글자
    ok_label &= len(set(who.values())) == len(who)        # 다른 사람 = 다른 글자
    ok_label &= lines[0]["senior"] == "선배 A"
    ok_label &= not any(re.search(r"H\d{4}", json.dumps(ln, ensure_ascii=False)) for ln in lines)
expect("배운점 senior: 선배 A부터, 사람마다 하나, 학번 없음", ok_label)
other_secs = [ln for s in notes.getNote(JUNIOR, {"id": lesson_ids[0]})["sections"] if s["name"] != "배운점" for ln in s["lines"]]
expect("배운점 밖 문장에는 senior 없음", all("senior" not in ln for ln in other_secs))

# 15) [11/22] saveQuestion — 「질문함에 담기」: hold로 저장, 멱등, 다음 인터뷰가 먼저 묻는다
q1 = notes.saveQuestion(JUNIOR, {"noteId": "N-marburg", "section": "비용"})
q2 = notes.saveQuestion(JUNIOR, {"noteId": "N-marburg", "section": "비용"})
expect("질문함 담기 응답", q1.get("ok") and q1["already"] is False and q1["questionId"].startswith("Q"))
expect("같은 칸 두 번 → 같은 질문", q2["already"] is True and q2["questionId"] == q1["questionId"])
row = next(q for q in store.load("questions", []) if q["id"] == q1["questionId"])
expect("질문함 행: hold·칸·노트·프로그램",
       row["status"] == "hold" and row["칸"] == "비용" and row["noteId"] == "N-marburg" and row["프로그램명"] == PROGRAM)
expect("다음 선배 인터뷰가 먼저 묻는다", any(q["id"] == q1["questionId"] for q in interview.junior_questions(OTHER, PROGRAM)))
expect("보관함 질문함에 보인다", any(q.get("id") == q1["questionId"] or q.get("questionId") == q1["questionId"]
                                for q in getInbox(JUNIOR, {})["questions"]))
expect("없는 칸·후배 질문 칸·없는 노트는 오류",
       "error" in notes.saveQuestion(JUNIOR, {"noteId": "N-marburg", "section": "없는칸"})
       and "error" in notes.saveQuestion(JUNIOR, {"noteId": "N-marburg", "section": "후배 질문"})
       and "error" in notes.saveQuestion(JUNIOR, {"noteId": "N-없음", "section": "비용"}))

# 16) [11/22] 내 경험노트 카드(getInbox.myNotes)·상세(getMyNote) — 공유 상태 셋, 칸 수, 공유 문장, 본인만
import runtime_fns
WRITER = "H0002"
my = {"sections": [{"name": "생활", "lines": [{"text": "나는 기숙사를 바로 신청했다."}, {"text": "나는 버스를 학생증으로 탔다."}]},
                   {"name": "지원", "lines": [{"text": "나는 TestDaF를 3학기 전부터 준비했다."}]}]}
pubd = {"sections": [{"name": "생활", "lines": [{"lineId": "L-DT-1", "text": "기숙사를 바로 신청했어요.", "match": True},
                                                {"lineId": "L-DT-2", "text": "버스를 학생증으로 탔어요.", "match": True}]},
                     {"name": "지원", "lines": [{"lineId": "L-DT-3", "text": "TestDaF를 3학기 전부터 준비했어요.", "match": True}]}]}
mid = runtime_fns.save_my_note(WRITER, PROGRAM, "D-TEST", my, pubd)
card = next(n for n in getInbox(WRITER, {})["myNotes"] if n["id"] == mid)
expect("카드: 공유 전 = private·칸 2/6(후배 질문 칸 없음)·공유 0",
       card["share"] == "private" and card["filled"] == 2 and card["total"] == 6 and card["sharedLines"] == 0
       and card["type"] == "교환" and card["noteId"] == "N-marburg" and mid.startswith("M"))
c = saveConsent(WRITER, {"draftId": "D-TEST", "edits": {"removed": ["L-DT-2"]}, "consent": True})
card = next(n for n in getInbox(WRITER, {})["myNotes"] if n["id"] == mid)
expect("카드: 일부 공유 = partial·2문장", c.get("ok") and card["share"] == "partial" and card["sharedLines"] == 2)
expect("공유 알림 = 반영됐어요(반영 중 없음)",
       any(a["text"] == "해봤노트에 내 이야기가 반영됐어요" and a.get("noteId") == "N-marburg" for a in getInbox(WRITER, {})["alerts"]))
d = runtime_fns.getMyNote(WRITER, {"id": mid})
expect("상세: 칸은 노트 틀 순서·빈 칸 포함", [s["name"] for s in d["sections"]] == notes.frame_sections("교환") and "후배 질문" not in [s["name"] for s in d["sections"]])
life = next(s for s in d["sections"] if s["name"] == "생활")["lines"]
expect("상세: 문장마다 공유 여부·해봤노트 문장", [ln["shared"] for ln in life] == [True, False]
       and life[0]["publicText"] == "기숙사를 바로 신청했어요." and life[0]["lineId"] == "L-DT-1")
expect("상세: 동의 시트 다시 열 값", d["draftId"] == "D-TEST" and d["publicDraft"] == pubd and d["share"] == "partial")
expect("상세: 남의 것·없는 것은 오류", "error" in runtime_fns.getMyNote(JUNIOR, {"id": mid})
       and "error" in runtime_fns.getMyNote(WRITER, {"id": "M-없음"}))
saveConsent(WRITER, {"draftId": "D-TEST", "edits": {}, "consent": True})
card = next(n for n in getInbox(WRITER, {})["myNotes"] if n["id"] == mid)
expect("카드: 전부 공유 = shared·3문장", card["share"] == "shared" and card["sharedLines"] == 3)
expect("카드에는 학번·문장 원문 없음", not any(k in card for k in ("owner", "sections", "publicDraft")))

print(f"\n{len(fails)}건 실패" if fails else "\n모두 통과")
sys.exit(1 if fails else 0)
