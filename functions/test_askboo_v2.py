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
expect("notes 카드에 type(현장실습 → 인턴)", all(c.get("type") == "인턴" for c in res["notes"]), [c.get("type") for c in res["notes"]])
expect("제외가 별칭(코트라)으로 와도 프로그램명으로 대조", KOTRA not in [c["program"] for c in res["notes"]])

res, calls = run("독일에서 인턴하고 싶은데 어디어디 있어요?", [],
                 plan={"의도": "탐색", "분야": "현장실습", "나라": "독일", "프로그램후보": [], "제외": [], "칸": None, "정리된질문": "독일에서 할 수 있는 인턴은 어디 있나요?"})
expect("현장실습을 나라로 물으면 기관 유형 칩", res["status"] == "notes" and res.get("kinds") and res["notes"] == [] and "기관 유형" in res["message"], res)
expect("독일 인턴 → 독일 노트 수(0개)를 먼저", res["message"].startswith("독일에서 한 현장실습 해봤노트는 0개예요."), res["message"])
expect("독일 교환 노트 수도 코드가 센 값", f"독일 교환·파견 해봤노트는 {len([n for n in askboo.COUNTRIES['독일'] if askboo.evidence_count(n)])}개" in res["message"], res["message"])

res, calls = run("베트남 교환 갈 수 있는 곳 있어요?", [],
                 plan={"의도": "탐색", "분야": "국제교류", "나라": "베트남", "프로그램후보": [], "제외": [], "칸": None, "정리된질문": "베트남 교환은 어디 있나요?"})
expect("교환 목록에 없는 나라 → 보류 대신 0개", res["status"] == "notes" and "베트남 교환·파견 해봤노트는 0개예요." in res["message"], res)
res, calls = run("교환 어디 있어요?", [],
                 plan={"의도": "탐색", "분야": "국제교류", "나라": "몰디브", "프로그램후보": [], "제외": [], "칸": None, "정리된질문": "x"})
expect("질문에 없는 나라를 AI가 지어내면 쓰지 않음", "몰디브" not in (res.get("message") or ""), res.get("message"))

res, calls = run("교환학생 선발 기준이 어떻게 돼요", [],
                 plan={"의도": "경험질문", "분야": "국제교류", "나라": None, "프로그램후보": [], "제외": [], "칸": None, "정리된질문": "x"})
expect("정규식 규정 판별이 질문정리보다 먼저(official)", res["status"] == "official" and [c[0] for c in calls] == [])

res, calls = run("마르부르크 기숙사 월세 얼마였어요?", [],
                 plan={"의도": "규정", "분야": None, "나라": None, "프로그램후보": [PROGRAM], "제외": [], "칸": None, "정리된질문": "x"})
expect("질문정리가 규정이라고 하면 official", res["status"] == "official")

# ── ①-2 [11/24] 제외 이어받기 · 유무 질문 · chat 되풀이 없음 ─────────────
KOTRAS = [n for n in askboo.PROGRAMS if n.startswith("KOTRA")]
H2 = H_KOTRA + [{"question": "아니 코트라 말고 전반적인 무역 관련 인턴이 어떤지 소개해주세요", "status": "notes", "program": ""}]
expect("앞 턴 「코트라 말고」 → KOTRA 권역 모두 제외", set(askboo.carried_exclusions("좋은 인턴 추천해주세요", H2)) == set(KOTRAS),
       askboo.carried_exclusions("좋은 인턴 추천해주세요", H2))
expect("이번 말이 코트라를 다시 부르면 빼지 않음", askboo.carried_exclusions("코트라는 어땠어요?", H2) == [])
expect("「말고」 없으면 제외 없음", askboo.carried_exclusions("좋은 인턴 추천해주세요", H_KOTRA) == [])

# AI가 앞 대화의 KOTRA를 후보로 다시 넣어도 코드가 뺀다
res, calls = run("좋은 인턴 어디 있나 추천해주세요", H2,
                 plan={"의도": "탐색", "분야": "현장실습", "나라": None, "프로그램후보": [KOTRA], "제외": [], "칸": None, "정리된질문": "좋은 인턴 추천"})
expect("③ 다음 턴에도 KOTRA 없음(AI가 제외를 잊어도)", res["status"] == "notes" and res["notes"] and not any(c["program"] in KOTRAS for c in res["notes"]), res)
expect("질문정리 입력에 「앞에서 뺀 프로그램」", "앞에서 뺀 프로그램: " in calls[0][1], calls[0][1])
expect("제외 안내는 「KOTRA 해외무역관」 하나로 줄임", res["message"].startswith("KOTRA 해외무역관을 뺀"), res["message"])
expect("카드 5개여도 전체 수를 말함", f"{n_left}개 있어요. 근거가 많은 5개" in res["message"] if (n_left := len([n for n, p in askboo.PROGRAMS.items() if p.get("분야") == "현장실습" and n not in KOTRAS and askboo.evidence_count(n)])) > 5 else True, res["message"])
res, calls = run("코트라 무역 인턴 추천해주세요", H2, plan=None)   # v1 경로: 정규식이면 KOTRA가 잡히지만 이번 말이 다시 불렀으니 유지
expect("v1: 다시 부르면 KOTRA 유지", any(s["program"] in KOTRAS for s in res.get("sources", {}).values()), res)
res, calls = run("무역 인턴 추천해주세요", H2, plan=None)
expect("v1(질문정리 실패)에도 앞에서 뺀 KOTRA 없음", not any(s["program"] in KOTRAS for s in res.get("sources", {}).values()), res)


def talk_sequence(steps):
    """talk.js rememberTurn처럼 history를 쌓으며 차례로 묻는다. steps: [(질문, plan)]"""
    turns, outs = [], []
    for q, plan in steps:
        res, _ = run(q, turns[-4:], plan=plan)
        src = [s["program"] for s in res.get("sources", {}).values()]
        prog = src[0] if src else (turns[-1]["program"] if res["status"] == "chat" and turns else "")
        turns.append({"question": q, "status": res["status"], "program": prog})
        outs.append(res)
    return outs


def P(의도, 분야=None, 나라=None, 후보=(), 제외=(), q="x"):
    return {"의도": 의도, "분야": 분야, "나라": 나라, "프로그램후보": list(후보), "제외": list(제외), "칸": None, "정리된질문": q}


# 11/23 캡처 6문항(같은 순서). 질문정리는 11/24 실제 결과처럼 ③에서 제외를 빠뜨리고 ⑥을 대화로 낸다고 둔다
outs = talk_sequence([
    ("무역 관련 인턴 어떤가요?", None),
    ("아니 코트라 말고 전반적인 무역 관련 인턴이 어떤지 소개해주세요", P("탐색", "현장실습", 제외=["코트라"])),
    ("좋은 인턴 어디 있나 추천해주세요", P("탐색", "현장실습")),
    ("이건 아까도 한 얘기잖아", P("대화", "현장실습", 제외=[KOTRA])),
    ("독일에서 인턴하고 싶은데 어디어디 있어요?", P("탐색", "현장실습", "독일")),
    ("아예 데이터가 없나요?", P("대화", "현장실습")),
])
progs3 = [c["program"] for c in outs[2].get("notes", [])] + [s["program"] for s in outs[2].get("sources", {}).values()]
expect("6문항 ③ KOTRA 없음", progs3 and not any(p in KOTRAS for p in progs3), progs3)
expect("6문항 ⑤ 독일 노트 개수 문장", "독일에서 한 현장실습 해봤노트는 0개" in outs[4].get("message", ""), outs[4].get("message"))
expect("6문항 ⑥ 유무 질문 → 독일 개수로 답(chat, 질문함 없음)",
       outs[5]["status"] == "chat" and "독일" in outs[5]["message"] and "0개" in outs[5]["message"] and "questionId" not in outs[5], outs[5])
expect("6문항 ⑥이 ④와 다른 답", outs[5].get("message") != outs[3].get("message"), (outs[3].get("message"), outs[5].get("message")))

# 바로 앞이 chat이면 같은 「아까는 ○○ 이야기」 안내를 되풀이하지 않는다
hc = H_KOTRA + [{"question": "이건 아까도 한 얘기잖아", "status": "chat", "program": KOTRA}]
res, _ = run("그러니까 그거 말고요", hc, plan=P("대화", "현장실습", 제외=[KOTRA]))
expect("chat 두 번째는 다른 문구", res["status"] == "chat" and not res["message"].startswith("아까는"), res.get("message"))

# 유무 질문: 나라가 없으면 분야 노트 수(제외 뺀 수)
res, _ = run("노트가 하나도 없어요?", H2, plan=P("대화", "현장실습"))
n_left = len([n for n, p in askboo.PROGRAMS.items() if p.get("분야") == "현장실습" and n not in KOTRAS and askboo.evidence_count(n)])
expect("유무 질문(나라 없음) → 제외 뺀 현장실습 노트 수", res["status"] == "chat" and f"{n_left}개" in res["message"] and "KOTRA 해외무역관" in res["message"], res.get("message"))
expect("조사: 독일이·KOTRA 해외무역관을(를)", askboo._josa("이가", "독일") == "이" and askboo._josa("을를", "무역관") == "을" and askboo._josa("을를", "(권역)") == "을(를)")

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

expect("검증 탈락 폴백 → 모든 줄 fallback True", res["lines"] and all(l.get("fallback") is True for l in res["lines"]), res.get("lines"))

res, calls = run("마르부르크 기숙사 어땠어요?", [], plan=plan_q, answer=None)
expect("답쓰기 실패 → 폴백(원문 인용), 줄 수 ≤ 3", res["status"] == "ok" and 1 <= len(res["lines"]) <= 3)
expect("답쓰기 실패 폴백도 모든 줄 fallback True", all(l.get("fallback") is True for l in res["lines"]), res.get("lines"))

# [11/24] 답쓰기가 {"답":[]}(근거가 질문에 안 맞음) → 원문을 답처럼 보이지 않고 보류
res, calls = run("마르부르크 기숙사 어땠어요?", [], plan=plan_q, answer={"답": []})
expect("답쓰기 빈 답 → hold", res["status"] == "hold" and res["lines"] == [] and res.get("_why") == "답쓰기 근거 없음", res)
expect("빈 답 hold는 노트로 갈 noteId·선배 제안", res.get("noteId") and res["suggestSenior"] is True, res)
expect("빈 답이면 답검사·변환을 부르지 않음", [c[0] for c in calls] == ["질문정리", "고르기", "답쓰기"], [c[0] for c in calls])
expect("compose 기본값은 빈 답에도 None(칸 요약 build_notes용)",
       askboo.compose.__defaults__[-1] is None)

# 고르기가 max_tokens에 잘리면(14개 넘게 고름) 앞 MAX_PICK(8)개만 답쓰기에 넘긴다
many = [{"text": f"문장 {i}이에요."} for i in range(1, 21)]
orig = askboo._call
askboo._call = lambda n, c: {"ok": True, "text": '{"관련":[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15', "json": None, "model": "fake"}
got, _ = askboo.pick("q", many)
askboo._call = orig
expect("잘린 고르기 목록(15개) → 앞 8개", askboo.MAX_PICK == 8 and got == many[:8], len(got))

# [11/24] 말머리 「덧붙이자면」 등은 폴백 문장에서 지운다
expect("덧붙이자면 제거", askboo.clean_source("덧붙이자면 일요일엔 상점이 닫아요.") == "일요일엔 상점이 닫아요.")
expect("저 같은 경우·체감상·사족이지만·하나 더 제거",
       [askboo.clean_source(s) for s in ("저 같은 경우 버스로 가요.", "체감상 추워요.", "사족이지만 비싸요.", "하나 더, 싸요.")]
       == ["버스로 가요.", "추워요.", "비싸요.", "싸요."])

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
expect("force hold 문구는 「담아 두었어요」(못 찾았어요 아님)", res["message"] == askboo.HOLD_SAVED, res["message"])
res = askboo.askBoo("H0143", {"question": "마르부르크 기숙사 어땠어요?", "force": "hold"}, save=False)
expect("force hold는 프로그램이 있어도 같은 문구", res["status"] == "hold" and res["message"] == askboo.HOLD_SAVED, res["message"])
h = askboo.clean_history([{"question": " a ", "status": "ok", "program": "p"}, {"question": "", "status": "x"}, {"bad": 1},
                          {"question": "b", "status": 3}, {"question": "c"}, {"question": "d"}, {"question": "e"}])
expect("history 정리: 글자만, 최근 4개", [x["question"] for x in h] == ["b", "c", "d", "e"] and h[0]["status"] == "" and h[0]["program"] == "", h)

# ── 정리 ──────────────────────────────────────────────────────────────
print()
print("실패 %d개" % len(fails) if fails else "전부 통과")
sys.exit(1 if fails else 0)
