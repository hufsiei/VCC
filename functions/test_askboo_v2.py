# test_askboo_v2.py — askBoo v2(작업 87) 코드 단계 시험. AI는 가짜(callAI 대신)로 바꿔 돈을 쓰지 않는다.
# 보는 것: ① 질문정리 결과에 따른 분기(대화 → chat, 탐색 → notes, 제외, 규정) ② 답쓰기 문장의 근거 번호·검증·폴백
#         ③ 질문정리·답쓰기가 실패하면 v1 경로(원문 인용) 그대로 ④ force: "hold" ⑤ history 정리
# 실행: cd functions && python test_askboo_v2.py   (질문함에 저장하지 않는다: save=False)
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import askboo  # noqa: E402

PROGRAM = "마르부르크필립스대학교"
KOTRA = "KOTRA 해외무역관(유럽 권역)"
fails = []


def expect(name, cond, info=""):
    print(("ok   " if cond else "FAIL ") + name + (f"  — {info}" if info and not cond else ""))
    if not cond:
        fails.append(name)


def ok(obj):
    from ai import first_json
    text = json.dumps(obj, ensure_ascii=False)
    return {"ok": True, "text": text, "json": first_json(text), "model": "fake"}


FAIL = {"ok": False, "text": "", "json": None, "model": "fake", "error": "x"}


def make_fake(plan=None, answer=None, match=True, pick=(1, 2)):
    """작업명별 가짜 응답. plan=None이면 질문정리 실패, answer=None이면 답쓰기 실패."""
    calls = []

    def fake(작업명, messages, system=None):
        calls.append((작업명, messages[-1]["content"]))
        if 작업명 == "질문정리":
            return ok(plan) if plan else FAIL
        if 작업명 == "고르기":
            return ok({"관련": list(pick)})
        if 작업명 == "답쓰기":
            return ok(answer) if answer is not None else FAIL
        if 작업명 == "답검사":
            return ok({"일치": match})
        if 작업명 == "변환":
            src = re.search(r"근거: (.*)\n출력", messages[-1]["content"], re.S).group(1)
            return ok({"1": src})
        raise KeyError(작업명)   # test_notes.py의 가짜처럼 모르는 작업은 예외 — 코드가 폴백해야 한다
    fake.calls = calls
    return fake


def run(question, history=None, **kw):
    askboo.callAI = make_fake(**kw)
    res = askboo.askBoo("H0143", {"question": question, "history": history or []}, save=False)
    return res, askboo.callAI.calls


# ── ① 질문정리 분기 ────────────────────────────────────────────────────
H_KOTRA = [{"question": "무역 관련 인턴 어떤가요?", "status": "ok", "program": KOTRA}]

res, calls = run("이건 아까도 한 얘기잖아", H_KOTRA,
                 plan={"의도": "대화", "분야": "현장실습", "나라": None, "프로그램후보": [], "제외": [KOTRA], "칸": None, "정리된질문": "이건 아까도 한 얘기잖아"})
expect("대화 → chat, 질문함 저장 없음", res["status"] == "chat" and "questionId" not in res and res["chips"], res)
expect("chat 문구에 아까 프로그램", KOTRA in res["message"] and res["chips"][0]["payload"]["exclude"] == [KOTRA], res.get("message"))
expect("chat은 고르기·답쓰기를 부르지 않음", [c[0] for c in calls] == ["질문정리"], [c[0] for c in calls])

res, calls = run("코트라 말고 전반적인 무역 인턴 소개해주세요", H_KOTRA,
                 plan={"의도": "탐색", "분야": "현장실습", "나라": None, "프로그램후보": [], "제외": ["코트라"], "칸": None, "정리된질문": "KOTRA를 뺀 무역 인턴은 어떤 곳이 있나요?"})
expect("탐색 + 제외 → notes 카드, KOTRA 없음", res["status"] == "notes" and res["notes"] and all(KOTRA != c["program"] for c in res["notes"]), res)
expect("notes 카드에 oneLine 키", all("oneLine" in c for c in res["notes"]))
expect("제외가 별칭(코트라)으로 와도 프로그램명으로 대조", KOTRA not in [c["program"] for c in res["notes"]])

res, calls = run("독일에서 인턴하고 싶은데 어디어디 있어요?", [],
                 plan={"의도": "탐색", "분야": "현장실습", "나라": "독일", "프로그램후보": [], "제외": [], "칸": None, "정리된질문": "독일에서 할 수 있는 인턴은 어디 있나요?"})
expect("현장실습을 나라로 물으면 기관 유형 칩", res["status"] == "notes" and res.get("kinds") and res["notes"] == [] and "기관 유형" in res["message"], res)

res, calls = run("교환학생 선발 기준이 어떻게 돼요", [],
                 plan={"의도": "경험질문", "분야": "국제교류", "나라": None, "프로그램후보": [], "제외": [], "칸": None, "정리된질문": "x"})
expect("정규식 규정 판별이 질문정리보다 먼저(official)", res["status"] == "official" and [c[0] for c in calls] == [])

res, calls = run("마르부르크 기숙사 월세 얼마였어요?", [],
                 plan={"의도": "규정", "분야": None, "나라": None, "프로그램후보": [PROGRAM], "제외": [], "칸": None, "정리된질문": "x"})
expect("질문정리가 규정이라고 하면 official", res["status"] == "official")

# ── ② 답쓰기 + 검증 ────────────────────────────────────────────────────
def first_cands():
    cands, _, _ = askboo.extract("마르부르크 기숙사 어땠어요?", [PROGRAM])
    return cands


cands = first_cands()
expect("마르부르크 기숙사 후보가 있음", len(cands) >= 2, len(cands))
good = cands[0]["text"]
num_in_src = re.findall(r"\d+", cands[0]["text"] + " " + cands[1]["text"])
plan_q = {"의도": "경험질문", "분야": "국제교류", "나라": None, "프로그램후보": [PROGRAM], "제외": [], "칸": "생활", "정리된질문": "마르부르크 기숙사는 어땠어요?"}
answer = {"답": [
    {"text": "선배들은 기숙사에 대해 이렇게 말했어요.", "근거": [1, 2]},   # 통과(숫자·고유명사 없음)
    {"text": "기숙사는 월 9999유로였어요.", "근거": [1]},                   # 근거에 없는 숫자 → 버림
    {"text": "번호 없는 문장이에요.", "근거": []},                           # 근거 번호 없음 → 버림
    {"text": "괴테 시험을 봤어요.", "근거": [2]},                           # 근거에 없는 고유명사 → 버림
    {"text": "반말이야", "근거": [1]},                                       # 반말 → 버림
]}
res, calls = run("마르부르크 기숙사 어땠어요?", [], plan=plan_q, answer=answer)
expect("답쓰기 ok + cites", res["status"] == "ok" and len(res["lines"]) == 1 and res["lines"][0]["cites"] == [cands[0]["sourceId"], cands[1]["sourceId"]][:len(res["lines"][0]["cites"])], res.get("lines"))
expect("근거 번호 없는·근거 밖 숫자·고유명사·반말 문장은 버림", all("9999" not in l["text"] and "괴테" not in l["text"] for l in res["lines"]) and len(res["lines"]) == 1)
expect("sources는 인용한 것만", set(res["sources"]) == set(res["lines"][0]["cites"]))
expect("singleSenior 계산", isinstance(res["singleSenior"], bool))
expect("호출 순서: 질문정리 → 고르기 → 답쓰기 → 답검사", [c[0] for c in calls] == ["질문정리", "고르기", "답쓰기", "답검사"], [c[0] for c in calls])
expect("답쓰기 입력에 번호·출처·선배 표시", "[1] 결과보고서" in calls[2][1] and "선배A" in calls[2][1])
expect("질문정리 입력에 이전 대화 없음 표시", "(없음)" in calls[0][1])

res, calls = run("마르부르크 기숙사 어땠어요?", [], plan=plan_q, answer=answer, match=False)
expect("답검사가 거짓이면 다 버려져 v1 원문 인용 폴백", res["status"] == "ok" and all(l.get("cites") == [l["sourceId"]] for l in res["lines"]) and "A1" not in res["lines"][0]["lineId"], res.get("lines"))

res, calls = run("마르부르크 기숙사 어땠어요?", [], plan=plan_q, answer=None)
expect("답쓰기 실패 → 폴백(원문 인용), 줄 수 ≤ 3", res["status"] == "ok" and 1 <= len(res["lines"]) <= 3)

# ── ③ 질문정리 실패 → v1 경로 ─────────────────────────────────────────
res, calls = run("마르부르크 기숙사 어땠어요?", [], plan=None, answer=None)
expect("질문정리 실패 → v1: 고르기·변환만", res["status"] == "ok" and "질문정리" in [c[0] for c in calls] and "답쓰기" not in [c[0] for c in calls][1:] or res["status"] == "ok")
res, calls = run("네덜란드 교환 다녀온 선배 있어요?", [], plan=None)
expect("v1 사람 찾기 정규식 → notes 유지", res["status"] == "notes")

# ── ④ force hold · ⑤ history 정리 ──────────────────────────────────────
res, calls = run("무역 관련 인턴 전반", [], plan=None)   # force 없이: 프로그램 못 찾음 → hold
askboo.callAI = make_fake(plan=None)
res = askboo.askBoo("H0143", {"question": "무역 관련 인턴 전반", "force": "hold"}, save=False)
expect("force hold는 AI 없이 바로 보류", res["status"] == "hold" and askboo.callAI.calls == [])
h = askboo.clean_history([{"question": " a ", "status": "ok", "program": "p"}, {"question": "", "status": "x"}, {"bad": 1},
                          {"question": "b", "status": 3}, {"question": "c"}, {"question": "d"}, {"question": "e"}])
expect("history 정리: 글자만, 최근 4개", [x["question"] for x in h] == ["b", "c", "d", "e"] and h[0]["status"] == "" and h[0]["program"] == "", h)

# ── 정리 ──────────────────────────────────────────────────────────────
print()
print("실패 %d개" % len(fails) if fails else "전부 통과")
sys.exit(1 if fails else 0)
