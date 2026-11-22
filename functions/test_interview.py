# test_interview.py — interview.py 시험 (작업 21). 실행: cd functions && python test_interview.py
# AI는 가짜(callAI 대신)로 바꿔 돈을 쓰지 않는다. 기록은 임시 폴더에 쓴다(data/runtime을 건드리지 않음).
# 하나라도 틀리면 종료코드 1.
import sys
import tempfile
from pathlib import Path

import store

store.RUNTIME = Path(tempfile.mkdtemp()) / "runtime"

import interview
from runtime_fns import add_question

PROGRAM = "마르부르크필립스대학교"
SENIOR, JUNIOR = "H0469", "H0143"

# 가짜 AI: 작업명마다 정해 둔 답. 요약은 일부러 원문에 없는 숫자를 섞어 사후 검증을 시험한다.
FAKE = {
    "충분판정": lambda c: '{"충분":false}' if "그냥" in c else '{"충분":true}',
    "꼬리질문": lambda c: '{"질문":"어떤 점이 가장 기억에 남았어요?"}',
    "요약": lambda c: ('{"문장":["월세는 450유로였어요.","보증금은 900유로였어요."]}' if "450" in c
                     else '{"문장":["방학에 단기 인턴을 했어요."]}'),
    "일치검사": lambda c: '{"일치":true}',
    "1인칭": lambda c: fake_first_person(c),
}


def fake_first_person(content):
    """'했어요.'→'했다.' 식으로 바꾸고, 450이 든 문장에는 일부러 원문에 없는 숫자(900)를 넣는다."""
    import json
    import re
    out = {}
    for m in re.finditer(r"^(\d+)\. (.+)$", content, re.M):
        t = re.sub(r"였어요\.$", "였다.", re.sub(r"했어요\.$", "했다.", m.group(2)))
        out[m.group(1)] = ("나는 " + t) + (" 보증금은 900유로였다." if "450" in t else "")
    return json.dumps(out, ensure_ascii=False)


def fake_call(작업명, messages, system=None):
    from ai import first_json
    text = FAKE[작업명](messages[-1]["content"])
    return {"ok": True, "text": text, "json": first_json(text), "model": "fake"}


interview.callAI = fake_call
fails = []


def expect(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


qid = add_question(JUNIOR, "마르부르크에서 학기 중 현지 인턴 병행할 수 있어요?", program=PROGRAM, status="hold")
add_question(SENIOR, "내가 한 질문은 나에게 안 나와야 해요", program=PROGRAM, status="hold")

# 1) 첫 질문은 후배 질문
s = interview.interviewNext(SENIOR, {"program": PROGRAM, "answers": []})
expect("첫 질문 = 후배 질문", s.get("section") == "후배 질문" and s.get("questionId") == qid)
expect("본인 질문 제외", s.get("pendingQuestions") == 1)
expect("total 7", s["progress"]["total"] == 7)

answers = [{"section": "후배 질문", "question": s["asked"], "questionId": qid, "answer": "학기 중엔 어렵고 방학에 단기 인턴 했어요."}]
s = interview.interviewNext(SENIOR, {"program": PROGRAM, "answers": answers})
first = interview.section_order(PROGRAM, ["지원", "학점", "비용", "생활", "팁", "배운점"])[0]
expect("다음은 근거 적은 칸", s.get("section") == first and not s.get("done"))
expect("배운점은 마지막", interview.section_order(PROGRAM, ["배운점", "지원", "팁"])[-1] == "배운점")

# 2) 부족한 답 → 꼬리 질문 1회, 다시 부족해도 다음 칸
answers.append({"section": s["section"], "question": s["question"], "answer": "그냥 그랬어요."})
s2 = interview.interviewNext(SENIOR, {"program": PROGRAM, "answers": answers})
expect("부족하면 꼬리 질문", s2.get("followUp") and s2.get("section") == first)
answers.append({"section": first, "question": s2["question"], "answer": "음 월세가 450유로였고요, 교통은 학생증으로 공짜였어요."})
s3 = interview.interviewNext(SENIOR, {"program": PROGRAM, "answers": answers})
expect("꼬리 질문은 칸당 1회", s3.get("section") != first and not s3.get("followUp"))

# 3) 끝까지 답하면 done
while not s3.get("done"):
    answers.append({"section": s3["section"], "question": s3["question"], "answer": "합격 메일 받고 바로 기숙사 신청했어요."})
    s3 = interview.interviewNext(SENIOR, {"program": PROGRAM, "answers": answers})
expect("done + filled 7/7", s3["done"] and s3["progress"] == {"filled": 7, "total": 7})

# 4) 요약: 화면처럼 questionId를 빼고 보내도 질문 원문으로 찾는다
transcript = [{k: a[k] for k in ("section", "question", "answer")} for a in answers]
r = interview.summarizeInterview(SENIOR, {"program": PROGRAM, "transcript": transcript})
expect("저장됨", r.get("saved") and r.get("myNoteId", "").startswith("M-") and r.get("draftId", "").startswith("D-"))
pub = {sec["name"]: sec["lines"] for sec in r["publicDraft"]["sections"]}
texts = [ln["text"] for lines in pub.values() for ln in lines]
expect("원문에 없는 숫자(900) 0건", not any("900" in t for t in texts))
expect("원문 숫자(450)는 남음", any("450" in t for t in texts))
junior = pub.get("후배 질문", [{}])[0]
expect("후배 질문 answersQuestionId·asked", junior.get("answersQuestionId") == qid and junior.get("asked"))
expect("문장마다 lineId·match·identifying",
       all("lineId" in ln and "match" in ln and "identifying" in ln for lines in pub.values() for ln in lines))
expect("myNote 칸 = 공개 초안 칸", [s["name"] for s in r["myNote"]["sections"]] == list(pub))
mine = [ln["text"] for sec in r["myNote"]["sections"] for ln in sec["lines"]]
expect("myNote는 1인칭 해라체", any(t.startswith("나는 ") and t.endswith("다.") for t in mine))
expect("1인칭 변환이 숫자를 지어내면 해요체 그대로", not any("900" in t for t in mine) and "월세는 450유로였어요." in mine)
expect("myNote 후배 질문도 answersQuestionId",
       all(ln.get("answersQuestionId") == qid for sec in r["myNote"]["sections"] if sec["name"] == "후배 질문" for ln in sec["lines"]))
r2 = interview.summarizeInterview(SENIOR, {"program": PROGRAM, "transcript": transcript})
expect("다시 요약하면 같은 myNoteId", r2["myNoteId"] == r["myNoteId"])

# 5) AI 실패 → 원문 문장 fallback, 인터뷰는 막히지 않음
interview.callAI = lambda *a, **k: {"ok": False, "text": "", "json": None, "model": "fake", "error": "x"}
r3 = interview.summarizeInterview(SENIOR, {"program": PROGRAM, "transcript": transcript[:2]})
expect("AI 실패 시 fallback", all(ln.get("fallback") for sec in r3["publicDraft"]["sections"] for ln in sec["lines"]))
expect("fallback: 정보 없는 짧은 답은 뺀다", interview.too_thin("생각보다 많이 들었어요."))
expect("fallback: 숫자 있으면 짧아도 남긴다", not interview.too_thin("비자는 2주 걸렸어요."))
expect("fallback: 긴 답은 남긴다", not interview.too_thin("기숙사는 합격 메일 받자마자 신청해야 자리가 있어요."))
g_short = {"section": "팁", "source": "생각보다 많이 들었어요. 월세는 450유로였어요."}
expect("fallback 묶음에서 짧은 답만 빠짐",
       [ln["text"] for ln in interview.summarize_group(g_short)] == ["월세는 450유로였어요."])
s4 = interview.interviewNext(SENIOR, {"program": PROGRAM, "answers": answers[:2]})
expect("판정 실패면 다음 칸으로", not s4.get("followUp") and s4.get("section"))
expect("빈 transcript는 오류", "error" in interview.summarizeInterview(SENIOR, {"program": PROGRAM, "transcript": []}))

print(f"\n{len(fails)}건 실패" if fails else "\n모두 통과")
sys.exit(1 if fails else 0)
