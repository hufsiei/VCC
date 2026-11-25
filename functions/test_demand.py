# test_demand.py — 선배 추천 열림 규칙과 「궁금한 것 정리하기」(demand.py, 11/22)
# 실행: cd functions && python test_demand.py
# 기준: docs/spec-v1.md 4장 demandNext·saveDemand·getMe.recommend. AI를 부르지 않는다. 기록은 임시 폴더. 하나라도 틀리면 종료코드 1.
import sys
import tempfile
from pathlib import Path

import store

store.RUNTIME = Path(tempfile.mkdtemp()) / "runtime"

import account
import demand
import runtime_fns as rf
rf._call_ai = lambda *a, **k: {"ok": True, "json": {"ok": True}}   # 시험은 실제 AI를 부르지 않는다(쪽지검사 연결, 작업 27)
from demand import answer_problem, count_interview_answers, demandNext, recommend_status, saveDemand

JUNIOR, OTHER, SENIOR1 = "H0143", "H0010", "H0469"
MARBURG = "마르부르크필립스대학교"
fails = []


def expect(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


def walk(me, picks):
    """화면처럼 state를 들고 다니며 단계마다 picks[step]을 넣는다. 끝까지 가면 마지막 응답."""
    state, seen = dict(picks.get("_start", {})), []
    for _ in range(20):
        r = demandNext(me, {"state": state})
        if r.get("done") or r.get("error"):
            return r, seen
        step = r["step"]
        seen.append(step)
        state = dict(r["state"])
        if step not in picks:
            return r, seen
        v = picks[step]
        if step == "more":
            state["moreDone"] = True if v is None else state.get("moreDone")
            if v:
                state["more"] = state.get("more", []) + [v]
        else:
            state[step] = v
    return r, seen


# ── 1. 유효 답변 ─────────────────────────────────────────────────────
expect("짧은 답은 무효", answer_problem("학점요")["reason"] == "short")
expect("「몰라요」류는 무효", answer_problem("잘 모르겠어요.")["reason"] == "junk")
expect("같은 글자 반복은 무효", answer_problem("ㅋㅋㅋㅋㅋㅋㅋㅋㅋㅋㅋ")["reason"] == "junk")
expect("전화번호는 쪽지 검사로 막힘", answer_problem("010-1234-5678로 연락 주세요 궁금해요")["reason"] == "연락처")
expect("10자 이상 구체적인 답은 유효", answer_problem("학점 인정은 몇 학점까지 되나요?") is None)

tr = [{"section": "지원", "question": "언제부터 준비했어요?", "answer": "출국 3학기 전부터 TestDaF를 준비했어요"},
      {"section": "지원", "question": "언제부터 준비했어요?", "answer": "어학원도 다녔어요 주말마다요"},   # 같은 질문 → 1개
      {"section": "학점", "question": "학점 인정은요?", "answer": "몰라요"},                               # 무효
      {"section": "비용", "question": "비용은요?", "answer": "", "skipped": True},
      {"section": "생활", "question": "생활은 어땠어요?", "answer": "기숙사 경쟁이 치열해서 일찍 신청했어요"},
      {"section": "배운점", "question": "무엇이 남았어요?", "answer": "혼자 문제를 푸는 힘이 생겼어요 정말로"}]
expect("들려주기 유효 답변 = 서로 다른 질문 3개", count_interview_answers(tr) == 3)

# ── 2. 처음엔 잠김 ──────────────────────────────────────────────────
st = recommend_status(JUNIOR)
expect("처음엔 잠김(ready False, need 3)", st["ready"] is False and st["need"] == 3 and st["by"] is None)
me = account.getMe(JUNIOR, {})
expect("getMe에 recommend", me.get("recommend", {}).get("ready") is False)

# ── 3. 수요 인터뷰: 잘 모르겠어요 → 고민 → 비교과 ─────────────────────
r, seen = walk(JUNIOR, {"field": "잘 모르겠어요", "explore": "진로 찾기"})
expect("「잘 모르겠어요」면 고민을 먼저 묻는다", seen[:2] == ["field", "explore"])
expect("고민 「진로 찾기」 → 비교과·진로·취업 교육과정, 다음은 프로그램", r["step"] == "program"
       and r["state"]["field"] == "비교과" and r["state"]["detail"] == "진로·취업 교육과정")
expect("프로그램 목록 끝에 「아직 정하지 않았어요」", r["options"][-1] == demand.NOT_YET and len(r["options"]) > 1)

base = {"field": "비교과", "detail": "진로·취업 교육과정", "program": demand.NOT_YET}
r, _ = walk(JUNIOR, base)
expect("프로그램 미정이면 분야 노트 틀(비교과)에서 칸, 후배 질문 제외", r["step"] == "section" and r["options"] == ["활동내용", "배운점"])
expect("프로그램 미정이면 칸 질문이 관심을 가리킨다", r["question"] == "프로그램은 나중에 정해도 돼요. 비교과·진로·취업 교육과정에 대해 무엇이 가장 궁금해요?")
r, _ = walk(JUNIOR, {"field": "국제교류", "detail": demand.NOT_YET, "program": demand.NOT_YET})
expect("나라·프로그램 모두 미정이면 「교환학생에 대해」", r["step"] == "section" and "교환학생에 대해" in r["question"])

# 국제교류: 나라 → 마르부르크
r, _ = walk(JUNIOR, {"field": "국제교류"})
labels = [o["label"] for o in r["options"]]
expect("국제교류 → 나라 칩(독일 포함) + 아직 정하지 않았어요", r["step"] == "detail" and "독일" in labels and labels[-1] == demand.NOT_YET)
r, _ = walk(JUNIOR, {"field": "국제교류", "detail": "독일"})
expect("독일 → 마르부르크가 프로그램 목록에", r["step"] == "program" and MARBURG in r["options"])
r, _ = walk(JUNIOR, {"field": "국제교류", "detail": "독일", "program": MARBURG})
expect("마르부르크 → 교환 노트 틀 칸(지원~배운점)", r["step"] == "section" and r["options"][:2] == ["지원", "학점"] and "후배 질문" not in r["options"]
       and r["question"] == "이 프로그램에서 무엇이 가장 궁금해요?")

# 답변 단계: 짧으면 다시
full = {"field": "국제교류", "detail": "독일", "program": MARBURG, "section": "학점", "when": "다음 학기"}
r, _ = walk(JUNIOR, {**full, "situation": "몰라요"})
expect("상황 답이 무효면 같은 단계 + retry", r["step"] == "situation" and r.get("retry"))
expect("progress는 유효 답변만 센다", r["progress"] == {"answered": 0, "need": 3})
answers = {"situation": "2학년이고 독일어 B1, 어학 점수를 준비하고 있어요",
           "question": "학점 인정은 전공 몇 학점까지 되나요?",
           "hope": "외국어로 일상을 꾸려 본 자신감을 얻고 싶어요"}
r, seen = walk(JUNIOR, {**full, **answers})
expect("답 3개 뒤에는 「더 궁금한 것」(건너뛰기 가능)", r["step"] == "more" and r.get("canSkip") is True)
expect("질문 문장에 고른 칸 이름", "학점" in demandNext(JUNIOR, {"state": {**full, "situation": answers["situation"]}})["question"])
r, _ = walk(JUNIOR, {**full, **answers, "more": None})
expect("건너뛰면 done + 요약(관심 「교환학생·독일」)", r.get("done") and r["summary"]["interest"] == "교환학생·독일"
       and r["summary"]["questions"] == [answers["question"]] and r["progress"]["answered"] == 3)

# ── 4. saveDemand ───────────────────────────────────────────────────
done_state = r["state"]
expect("동의 없으면 저장 안 함", "error" in saveDemand(JUNIOR, {"state": done_state}))
half = saveDemand(JUNIOR, {"state": {**full, "situation": answers["situation"]}, "consent": True})
expect("덜 끝난 state는 ok False + 다음 단계", half.get("ok") is False and half["next"]["step"] == "question")
expect("아직 잠김", recommend_status(JUNIOR)["ready"] is False)
s1 = saveDemand(JUNIOR, {"state": done_state, "consent": True})
expect("저장 → 열림(by ask, unlocked)", s1.get("ok") and s1["recommend"]["ready"] and s1["recommend"]["by"] == "ask" and s1["unlocked"] is True)
q = next(q for q in store.load("questions", []) if q["id"] == s1["questionIds"][0])
expect("질문함에 hold로 저장(프로그램·칸·시기·수요)", q["status"] == "hold" and q["프로그램명"] == MARBURG
       and q["칸"] == "학점" and q["시기"] == "다음 학기" and q["수요"] is True)
d = store.load("demands", [])[-1]
expect("demands에 상황·바라는 것 원문 보관", d["owner"] == JUNIOR and d["situation"] == answers["situation"])
s2 = saveDemand(JUNIOR, {"state": done_state, "consent": True})
expect("두 번째부터 unlocked False", s2.get("ok") and s2["unlocked"] is False)

# 열린 뒤: 추천·쪽지
rec = rf.recommendSeniors(JUNIOR, {"noteId": "N-marburg"})
expect("열리면 추천 3명", rec.get("shown") == 3)
send = rf.sendMessage(JUNIOR, {"to": SENIOR1, "text": "마르부르크 학점 인정이 궁금해서 쪽지 드려요."})
info = next(t for t in rf.getMessages(SENIOR1, {})["threads"] if t["threadId"] == send["threadId"])["askerInfo"]
expect("선배가 보는 관심 = 「교환학생·독일」, 시기, 학과·상황 원문 없음",
       info["관심"][0] == "교환학생·독일" and info["시기"] == "다음 학기" and "crs_nm" not in info
       and answers["situation"] not in str(info))

# ── 5. 물어보기 보류 질문에서 이어 하기 ────────────────────────────────
hold = rf.add_question(OTHER, "마르부르크에서 학기 중 현지 인턴을 병행할 수 있어요?", MARBURG, "생활", status="hold")
expect("남의 보류 질문으로는 시작 못 함", "error" in demandNext(JUNIOR, {"state": {"fromQuestionId": hold}}))
r = demandNext(OTHER, {"state": {"fromQuestionId": hold}})
expect("보류 질문 → 분야·나라·프로그램·칸·질문 미리 채움, 다음은 시기",
       r["step"] == "when" and r["state"]["program"] == MARBURG and r["state"]["section"] == "생활"
       and r["state"]["detail"] == "독일" and r["progress"]["answered"] == 1)
n_before = len(store.load("questions", []))
r, _ = walk(OTHER, {"_start": {"fromQuestionId": hold}, "when": "1년 뒤",
                    "situation": "아직 어학 점수가 없어서 준비를 시작하려고 해요", "hope": "현지에서 일해 본 경험",
                    "more": None})
expect("이어 하기는 답 2개만 더 쓰면 done", r.get("done") and r["progress"]["answered"] == 3)
s3 = saveDemand(OTHER, {"state": r["state"], "consent": True})
q = next(q for q in store.load("questions", []) if q["id"] == hold)
expect("같은 질문 행에 맥락만 붙고 질문함은 늘지 않음", s3.get("ok") and s3["questionIds"] == [hold]
       and len(store.load("questions", [])) == n_before and q["시기"] == "1년 뒤" and q["수요"] is True)

# ── 6. 경험 나눔: 답변 3 + 공유 1문장 ─────────────────────────────────
mid = rf.save_my_note(SENIOR1, MARBURG, "D-9001", {"sections": []}, {"sections": []}, answered=2)
store.load("noteLines", []).append({"myNoteId": mid, "sourceId": "S-1"})
expect("답변 2개 + 공유면 아직 잠김", recommend_status(SENIOR1)["ready"] is False)
rf.save_my_note(SENIOR1, MARBURG, "D-9002", {"sections": []}, {"sections": []}, answered=3)
st = recommend_status(SENIOR1)
expect("답변 3개 + 공유 1문장이면 열림(by talk)", st["ready"] and st["by"] == "talk" and st["talk"] == {"answered": 3, "shared": 1})
rf.save_my_note(SENIOR1, MARBURG, "D-9003", {"sections": []}, {"sections": []}, answered=1)
expect("이어 쓰며 답변 수가 줄어도 큰 값을 남김", recommend_status(SENIOR1)["talk"]["answered"] == 3)
mid2 = rf.save_my_note("H0241", MARBURG, "D-9004", {"sections": []}, {"sections": []}, answered=5)
expect("답변 5개라도 공유 0문장이면 잠김", recommend_status("H0241")["ready"] is False)
store.load("reported", {})["L-S-2"] = {"status": "숨김 중"}
store.load("noteLines", []).append({"myNoteId": mid2, "sourceId": "S-2"})
expect("신고로 숨긴 문장은 공유로 치지 않음", recommend_status("H0241")["ready"] is False)

print()
if fails:
    print(f"실패 {len(fails)}건")
    sys.exit(1)
print("모두 통과")
