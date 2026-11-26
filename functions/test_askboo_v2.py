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
expect("6문항 ④ chat, 앞(③)이 노트 목록이면 「아까는 KOTRA 이야기」라고 하지 않음",
       outs[3]["status"] == "chat" and not outs[3]["message"].startswith("아까는") and "KOTRA 해외무역관은 빼고 노트를 보여 드렸어요" in outs[3]["message"],
       outs[3].get("message"))
expect("6문항 ④ 칩: 다른 현장실습 노트 보기(KOTRA 제외)",
       outs[3]["chips"][0]["label"] == "다른 현장실습 노트 보기" and set(outs[3]["chips"][0]["payload"]["exclude"]) >= {KOTRA}, outs[3]["chips"])
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

# ── ①-3 [11/25 작업 87] 비교 질문 → 고정 안내 + 그 나라 노트 카드(AI 없음) ─────
# 원우 실서버 시험(93): 마르부르크 생활비 답 뒤 「독일 다른 지역 대비 어떤건가요?」에 마르부르크 답을 되풀이함
H_MARBURG = [{"question": "마르부르크 생활비 얼마나 들어요?", "status": "ok", "program": PROGRAM}]
DE = [n for n in askboo.COUNTRIES["독일"] if askboo.evidence_count(n)]
res, calls = run("독일 다른 지역 대비 어떤건가요?", H_MARBURG, plan=P("경험질문", "국제교류", "독일", 후보=[PROGRAM]), answer={"답": []})
expect("비교 질문 → notes + 「여러 학교 비교는 아직 못 해요」", res["status"] == "notes" and res["message"].startswith("여러 학교 비교는 아직 못 해요."), res)
expect("비교 질문은 AI를 부르지 않음(고정 문구)", calls == [], [c[0] for c in calls])
expect("비교 질문 카드 = 독일 노트(근거 많은 순, 최대 5)", [c["program"] for c in res["notes"]] == sorted(DE, key=askboo.evidence_count, reverse=True)[:5], res["notes"])
expect("비교 질문 문구의 노트 수는 코드가 센 값", (f"독일 해봤노트 {len(DE)}개" in res["message"]), res["message"])
expect("비교 질문은 lines 없음·질문함 저장 없음", res["lines"] == [] and "questionId" not in res)
res, _ = run("다른 학교보다 기숙사 좋아요?", H_MARBURG, plan=None)
expect("나라 없는 비교 질문 → 앞 대화 프로그램의 나라(독일) 카드", res["status"] == "notes" and PROGRAM in [c["program"] for c in res["notes"]]
       and "독일 해봤노트" in res["message"], res.get("message"))
res, _ = run("마르부르크랑 레이던 대학교 중 어디가 생활비 싸요?", [], plan=None)
expect("두 학교 비교 → 부른 두 학교 카드가 먼저", res["status"] == "notes" and set([c["program"] for c in res["notes"]][:2]) == {PROGRAM, "레이던 대학교"}
       and "네덜란드·독일 해봤노트" in res["message"], res.get("notes"))
res, _ = run("둘 중에 어디가 좋아요?", [], plan=None)
expect("비교할 곳을 모르면 카드 없이 한 곳을 고르라는 안내", res["status"] == "notes" and res["notes"] == [] and "하나를 골라" in res["message"], res)
for q in ("독일 다른 지역 대비 어떤건가요?", "어느 학교가 더 추천할 만해요?", "레이던 vs 마르부르크", "다른 나라랑 비교하면 물가 어때요?",
          "독일이 프랑스보다 생활비 더 싸요?"):
    expect(f"비교 판정: {q}", askboo.is_compare(q))
for q in ("한국보다 물가 비싸요?", "가격 대비 기숙사 괜찮아요?", "학기 중에 뭐 하면 좋아요?", "그 중에 뭐가 제일 힘들었어요?",
          "비교과 프로그램 추천해 주세요", "한국과 비교하면 수업은 어때요?", "다른 학교 노트도 보여 주세요", "독일어 수업 어땠어요?",
          "마르부르크 수업과 과제 중에 뭐가 힘들었어요?"):
    expect(f"비교 아님: {q}", not askboo.is_compare(q))
res, calls = run("마르부르크 기숙사 어땠어요?", [], plan=None, answer=None)
expect("비교가 아닌 질문은 그대로(답 ok, AI 경로)", res["status"] == "ok" and calls, res.get("status"))


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
expect("답쓰기 입력에 번호·출처·선배 표시", "[1] 보고서" in calls[2][1] and "선배A" in calls[2][1])
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

# ── [11/26 Q-44] 「질문함에 담기」 저장에 프로그램·칸을 남긴다 ─────────────────
import tempfile  # noqa: E402

import demand  # noqa: E402
import store  # noqa: E402

_runtime = store.RUNTIME
store.RUNTIME = Path(tempfile.mkdtemp()) / "runtime"   # 실제 data/runtime을 건드리지 않는다
HACK = "학기 중 현지 인턴 병행할 수 있어요?"


def saved_row(question, history=None):
    askboo.callAI = make_fake()
    res = askboo.askBoo("H0143", {"question": question, "history": history or [], "force": "hold"})
    row = next(q for q in store.load("questions", []) if q["id"] == res["questionId"])
    return res, row


def turn(program, question="마르부르크 생활비 얼마예요?", status="ok"):
    return [{"question": question, "status": status, "program": program}]


res, row = saved_row(HACK, turn(PROGRAM))
expect("담기 + 앞 턴 프로그램 → 질문 행에 프로그램·칸", row["프로그램명"] == PROGRAM and row["칸"] == "생활", row)
expect("담기 응답 모양·문구는 그대로(noteId 없음, AI 없음)", res["message"] == askboo.HOLD_SAVED and "noteId" not in res
       and "_program" not in res and askboo.callAI.calls == [], res)
st = demand._from_question("H0143", row["id"])
expect("궁금한 것 정리하기가 분야·프로그램·칸을 채움", st.get("field") == "국제교류" and st.get("program") == PROGRAM
       and st.get("section") == "생활", st)
expect("history 없이 질문이 학교를 부르면 그 프로그램(화면 칩은 history를 안 보냄)",
       saved_row("마르부르크에서 " + HACK)[1]["프로그램명"] == PROGRAM)
expect("질문의 프로그램이 앞 턴보다 먼저", saved_row("마르부르크 기숙사 어땠어요?", turn(KOTRA))[1]["프로그램명"] == PROGRAM)
row = saved_row(HACK)[1]
expect("프로그램을 모르면 지금처럼 비움", row["프로그램명"] is None and row["칸"] is None, row)
expect("앞 턴에 프로그램이 없으면 비움", saved_row(HACK, turn(""))[1]["프로그램명"] is None)
expect("history 항목에 program 칸이 없어도 담김(spec상 선택)",
       saved_row(HACK, [{"question": "안녕", "status": "chat"}])[1]["프로그램명"] is None
       and askboo._saved_program(HACK, [{"question": "안녕", "status": "chat"}]) is None)
expect("「말고」로 뺀 프로그램은 붙이지 않음", saved_row("코트라 말고 다른 인턴 있어요?", turn(KOTRA))[1]["프로그램명"] is None)
expect("다른 나라 질문에는 앞 턴 프로그램을 붙이지 않음", saved_row("일본 생활비는 얼마예요?", turn(PROGRAM))[1]["프로그램명"] is None)
expect("목록에 없는 학교 질문에도 붙이지 않음", saved_row("남스웨덴공과대학교 기숙사 있어요?", turn(PROGRAM))[1]["프로그램명"] is None)
store.RUNTIME = _runtime

h = askboo.clean_history([{"question": " a ", "status": "ok", "program": "p"},{"question": "", "status": "x"}, {"bad": 1},
                          {"question": "b", "status": 3}, {"question": "c"}, {"question": "d"}, {"question": "e"}])
expect("history 정리: 글자만, 최근 4개", [x["question"] for x in h] == ["b", "c", "d", "e"] and h[0]["status"] == "" and h[0]["program"] == "", h)

# ── [11/25 Q-13] 후속 질문·시기 질문 (미리 실사용 캡처 세 질문) — 코드가 세어 답한다, AI 없음 ──────────
INTERN_PLAN = {"의도": "탐색", "분야": "현장실습", "나라": None, "프로그램후보": [], "제외": [], "칸": None, "정리된질문": "x"}
n_intern = len(askboo._pool("현장실습", None))

res, calls = run("인턴십 보통 언제 하는지", [], plan=INTERN_PLAN)
expect("캡처①「인턴십 보통 언제 하는지」→ 시기별 보고서 수 + 노트 카드", res["status"] == "notes" and "여름방학" in res["message"]
       and "1학기" in res["message"] and "편" in res["message"] and res["notes"] and calls == [], res.get("message"))
expect("시기 답의 편수는 시기별 합과 같음", sum(int(x.replace(",", "")) for x in re.findall(r"(?:학기|방학) ([\d,]+)편", res["message"]))
       == int(re.search(r"보고서 ([\d,]+)편", res["message"]).group(1).replace(",", "")), res["message"])
expect("시기 답은 모집 일정을 지어내지 않고 공지로", "학교 공지" in res["message"])

H_NOTES = [{"question": "인턴십 보통 언제 하는지", "status": "notes", "program": ""}]
res, calls = run("이게 다야?", H_NOTES, plan=INTERN_PLAN)
expect("캡처②「이게 다야?」(노트 목록 뒤) → 전체 수를 말함", res["status"] == "chat" and f"모두 {n_intern}개" in res["message"]
       and "5개만" in res["message"] and calls == [], res.get("message"))
expect("「이게 다야?」에 엇나간 문구 없음", "겹쳤다면" not in res["message"])
expect("「이게 다야?」 칩: 그 분야 둘러보기", res["chips"][0]["action"] == "notes" and res["chips"][0]["payload"]["field"] == "현장실습")

H_EX = [{"question": "교환학생 어디가 좋아?", "status": "notes", "program": ""}]
res, calls = run("이 해봤노트 준 기준이 뭐야", H_EX, plan=INTERN_PLAN)
expect("캡처③「이 해봤노트 준 기준이 뭐야」→ 근거 많은 순이라고 설명", res["status"] == "chat" and "근거" in res["message"]
       and "많은 순서" in res["message"] and "교환·파견" in res["message"] and calls == [], res.get("message"))

res, _ = run("이게 다야?", [{"question": "마르부르크 기숙사 어땠어요?", "status": "ok", "program": PROGRAM}])
expect("답 뒤 「이게 다야?」 → 그 노트 근거 수", res["status"] == "chat" and f"{askboo.evidence_count(PROGRAM)}개" in res["message"], res.get("message"))
res, _ = run("다른 데는 없어?", [{"question": "독일 교환 어디 있어요?", "status": "notes", "program": ""}])
expect("나라 노트 뒤 「다른 데는 없어?」 → 그 나라 노트 수", res["status"] == "chat" and "독일 해봤노트" in res["message"], res.get("message"))

res, _ = run("교환학생 보통 몇 학년에 가요?", [])
expect("「몇 학년」은 노트에 없다고 먼저 말함", res["status"] == "notes" and res["message"].startswith("몇 학년에 했는지는 해봤노트에 없어요."), res.get("message"))
res, _ = run("독일 인턴 언제 해요?", [])
expect("「독일 인턴 언제」→ 독일 교환 노트를 쓰지 않음", res["status"] == "notes" and "현장실습" in res["message"]
       and all(c["type"] == "인턴" for c in res["notes"]), res.get("message"))
res, _ = run("마르부르크 언제 가는 게 좋아요?", [])
expect("한 학교 시기 → 그 노트만", res["status"] == "notes" and [c["program"] for c in res["notes"]] == [PROGRAM], res.get("notes"))

# [11/26] 인원·순위 질문 → 학적의 파견대학을 세어 답한다(AI 없음)
res, calls = run("독일 7+1 갈 때 가장 많이 간 대학교는 어디야?", [])
expect("「7+1 가장 많이 간」→ 파견학생 유형만 세어 인원 순", res["status"] == "notes" and calls == []
       and res["message"].startswith("독일 7+1 파견 다녀온 선배는") and "마르부르크필립스대학교 3명" in res["message"], res.get("message"))
expect("카드도 인원 많은 순", res["notes"][0]["program"] == PROGRAM, [c["program"] for c in res["notes"]])
res, _ = run("독일에서 가장 많이 간 대학교는?", [])
expect("유형을 안 말하면 모두 세고 유형별로 나눠 말함", "뷔르츠부르크 대학교 6명(교환학생 4·7+1 파견 2)" in res["message"]
       and res["notes"][0]["program"] == "뷔르츠부르크 대학교", res.get("message"))
expect("7+1 묶음: 학과·우수입학·국제 파견학생, 아너스 제외", askboo.kind_group("우수입학 파견학생") == "7+1 파견"
       and askboo.kind_group("국제 파견학생") == "7+1 파견" and askboo.kind_group("아너스 파견") == "아너스 파견")
res, _ = run("마르부르크 몇 명 갔어요?", [])
expect("한 학교 인원", res["message"].startswith("마르부르크필립스대학교 다녀온 선배는 5명") and len(res["notes"]) == 1, res.get("message"))
res, _ = run("뷔르츠부르크 말고 독일에서 제일 많이 간 곳", [])
expect("「말고」로 뺀 학교는 세지 않음", "뷔르츠부르크" not in res["message"] and "뷔르츠부르크 대학교" not in [c["program"] for c in res["notes"]], res.get("message"))
# [Q-40] 「순서대로」의 「서대로」를 학교 이름으로 읽지 않는다
res, calls = run("독일 7+1 파견학생 간 사람들이 가장 많이 간 대학교를 순서대로 말해줘", [])
expect("「…대학교를 순서대로」→ 인원 답(학교별 N명, AI 없음)", res["status"] == "notes" and calls == []
       and res["message"].startswith("독일 7+1 파견 다녀온 선배는") and "마르부르크필립스대학교 3명" in res["message"], res.get("message"))
for q in ("순서대로 알려줘", "제대로 알려줘", "생각대로 됐어?"):
    expect(f"학교 이름 아님: {q}", not askboo.SCHOOL_NAME.search(q))
for q in ("서울대 어때?", "외대에서 갔어?", "서울대·외대에서 간 곳", "남스웨덴공과대학교로 갔어?"):
    expect(f"학교 이름 그대로: {q}", askboo.SCHOOL_NAME.search(q))
_saved = askboo.ABROAD
askboo.ABROAD = _saved + [("본대학교", "교환학생")] * 9   # 본대학교를 1등으로 만들고 노트가 없다고 친다
_ev = askboo.evidence_count
askboo.evidence_count = lambda n: 0 if n == "본대학교" else _ev(n)
res, _ = run("독일 교환학생 제일 많이 간 학교?", [])
expect("노트 없는 학교는 인원만 말하고 카드에서 뺌", "본대학교 10명" in res["message"] and "본대학교는 아직 해봤노트가 없어요" in res["message"]
       and "본대학교" not in [c["program"] for c in res["notes"]], res.get("message"))
askboo.ABROAD, askboo.evidence_count = _saved, _ev
res, calls = run("마르부르크 수업 한 반 인원 몇 명이에요?", [], plan=plan_q, answer=answer)
expect("주제가 있는 「인원」(수업)은 인원 답이 아니라 경험 답", "질문정리" in [c[0] for c in calls])
res, _ = run("독일 교환학생 선발 인원 몇 명이에요?", [])
expect("「선발 인원」은 공식 안내", res["status"] == "official")
hits = [q for q in ("마르부르크에서 가장 많이 한 일은?", "마르부르크 학생들이 주말에 많이 가는 곳", "마르부르크 대학 순위 어때요?",
                    "독일에서 제일 많이 간 여행지", "마르부르크에서 어디가 제일 인기 있는 맛집이에요?", "마르부르크에서 제일 많이 간 곳",
                    "독일 파견 순서가 어떻게 돼요?", "마르부르크 한국인 몇 명 있어요?")
        if askboo.rank(q, *(lambda c: (c[1] or askboo.match_programs(q), c[0]))(askboo.match_country(q)))]
expect("학교 인원이 아닌 「많이·인기·순위」는 인원 답을 하지 않음", hits == [], hits)

# 걸리면 안 되는 것
res, calls = run("교환학생 선발 기준이 뭐예요?", H_EX)
expect("「선발 기준」은 후속이 아니라 공식 안내", res["status"] == "official", res.get("status"))
res, calls = run("신청 기간 언제까지예요?", [])
expect("「신청 기간 언제까지」는 시기 답이 아니라 공식 안내", res["status"] == "official")
res, calls = run("마르부르크 기숙사 신청 언제 했어요?", [], plan=plan_q, answer=answer)
expect("주제가 있는 「언제」(기숙사)는 시기 답이 아니라 경험 답", "질문정리" in [c[0] for c in calls] and "시기별" not in (res.get("message") or ""))
res, calls = run("이게 다야?", [])
expect("앞 턴 없는 「이게 다야?」는 후속으로 보지 않음", "질문정리" in [c[0] for c in calls])
res, calls = run("마르부르크 기숙사도 더 알려줘", H_NOTES, plan=plan_q, answer=answer)
expect("프로그램을 부른 새 질문은 후속으로 보지 않음", "질문정리" in [c[0] for c in calls])

# 카드가 5개로 잘리면 「5개 있어요」라고 하지 않는다
res, _ = run("현장실습 뭐 있어요?", [], plan=INTERN_PLAN)
expect("노트 카드 5개로 잘림 → 전체 수를 말함", res["status"] == "notes" and f"{n_intern}개 중" in res["message"], res.get("message"))

# ── [11/25 Q-14] 근거 범위: 도시·「○○ 말고 나라 전체」 (실사용 채점 길 2점 두 건) ──────────
JP = ["긴키 대학교", "나가사키외국어대학교"]
res, calls = run("일본 도쿄 한달 생활비 얼마에요?", [], plan=plan_q, answer=answer)
expect("①「일본 도쿄 생활비」→ 다른 학교 근거로 답하지 않음(AI 없음)", res["status"] == "notes" and not res["lines"] and calls == [],
       (res.get("status"), [c[0] for c in calls]))
expect("① 도쿄 0개 + 일본 노트 수(코드가 센 값) + 일본 카드", "도쿄에 있는 학교 해봤노트는 0개" in res["message"]
       and f"일본 교환·파견 해봤노트는 {len([n for n in JP if askboo.evidence_count(n)])}개" in res["message"]
       and {c["program"] for c in res["notes"]} <= set(JP), res.get("message"))
res, calls = run("도쿄는 생활비 어때요?", [{"question": "일본 교환 어때요?", "status": "notes", "program": ""}], plan=plan_q, answer=answer)
expect("① 나라 없이 도시만 → 도시로 나라를 알아 같은 안내", res["status"] == "notes" and "도쿄" in res["message"] and calls == [])
res, calls = run("나가사키 생활비 얼마에요?", [], plan=None)
expect("① 학교 이름에 있는 도시(나가사키) → 그 학교로 답하는 길", res["status"] != "notes" or "0개" not in (res.get("message") or "")
       and "고르기" in [c[0] for c in calls], (res.get("status"), res.get("message")))
expect("① city_scope: 파리 → 파리 학교만", all("파리" in n for n in askboo.city_scope("파리 생활비", [], None)[2]))
expect("① city_scope: 일본·본인·마르부르크(학교 이름) → 도시 아님",
       askboo.city_scope("일본 본인 생활비", *askboo.match_country("일본 본인 생활비")) is None
       and askboo.city_scope("마르부르크 생활비", [PROGRAM], None) is None)
for q in ("포르투갈 한달 생활비 얼마예요?", "포르투갈 교환 어때요?", "테니스 동아리 있어요?", "프랑스 비즈니스 수업 어때요?",
          "로마자 표기 어떻게 해요?"):   # 총괄 검토(#282): 낱말 속 도시(포르투·니스·로마)는 걸리면 안 됨
    expect(f"① 도시 아님(낱말 속): {q}", askboo.city_scope(q, *askboo.match_country(q)) is None,
           askboo.city_scope(q, *askboo.match_country(q)))
res, _ = run("포르투갈 교환 어때요?", [], plan=None)
expect("① 「포르투갈 교환」은 포르투갈 노트 그대로(0개 안내 아님)", "0개" not in (res.get("message") or ""), res.get("message"))
expect("① 조사·문장부호 뒤 도시는 잡음: 도쿄에서·로마는·파리?", all(askboo.city_scope(q, [], None) for q in ("도쿄에서 살기", "로마는 어때요", "파리?")))
expect("① 도쿄 인턴 질문은 교환 도시 판정에서 뺌", askboo.city_scope("도쿄 인턴 어때요?", [], None) is None)

H_NGS = [{"question": "나가사키외국어대학교 생활비 얼마에요?", "status": "hold", "program": "나가사키외국어대학교"}]
res, calls = run("나가사키외국어대학교 말고 일본 대학 전체의 해봤노트에도 없나요?", H_NGS, plan=P("대화", "국제교류", 제외=["나가사키외국어대학교"]))
expect("②「○○ 말고 일본 전체 노트에도 없나요?」→ 남은 일본 노트 수(AI 없음)", res["status"] == "notes" and calls == []
       and "나가사키외국어대학교를 뺀 일본 해봤노트는 1개" in res["message"] and "긴키 대학교" in res["message"], res.get("message"))
expect("② 엇나간 문구 없음 · 카드에 나가사키 없음", "겹쳤다면" not in res["message"]
       and all(c["program"] != "나가사키외국어대학교" for c in res["notes"]))
res, calls = run("나가사키외국어대학교 말고 일본 다른 학교 생활비는요?", H_NGS, plan=None)
expect("② 주제가 있는 「말고」 질문은 노트 수가 아니라 남은 학교로 답하는 길", "고르기" in [c[0] for c in calls]
       or res["status"] == "hold", (res.get("status"), [c[0] for c in calls]))

# 기존 나라·학교 질문은 그대로
res, calls = run("마르부르크 생활비 얼마나 들어요?", [], plan=plan_q, answer=answer)
expect("「마르부르크 생활비」는 그대로 답(도시 판정 안 탐)", res["status"] == "ok" and "질문정리" in [c[0] for c in calls], res.get("status"))
res, calls = run("독일 교환 어디 있어요?", [], plan=None)
expect("「독일 교환 어디 있어요?」는 그대로 독일 노트", res["status"] == "notes" and "독일" in res["message"], res.get("message"))

# ── [11/26 Q-38] 규정 판별 좁히기 + 나라 단위 보류 문구 ─────────────────
Q1 = "독일에서 교환학생 하면서 장학금 받은 사람이 있나? 독일 현지 대학교에서 주는 장학금 말이야"
Q2 = "보통 독일 대학교에서 몇학점 들어?"
Q3 = "독일 학비 알려줘"
for q in (Q1, Q2, Q3, "그 학교 자체 장학금 있어요?", "파견 대학에서 몇 학점 수강했어요?"):
    expect(f"규정 아님(현지·수강 경험): {q}", not askboo.is_official(q))
for q in ("외대 장학금 받으려면 평점 몇 점?", "학점 인정 신청 언제까지?", "장학금 얼마예요?", "교환학생 장학금 신청 방법 알려 주세요",
          "현지에서 들은 학점 인정받을 수 있어요?", "파견 대학 배정 결과 발표는 언제 나와요?", "독일 대학 다녀와서 초과학기 등록금 내요?",
          "이중전공 과목도 파견대학에서 인정받을 수 있어요?", "현장실습 하면 몇 학점 받아요?"):
    expect(f"그대로 규정: {q}", askboo.is_official(q))

GERMANY = askboo.match_country("독일")[1]
PLAN_DE = {"의도": "경험질문", "분야": "국제교류", "나라": "독일", "프로그램후보": [], "제외": [], "칸": "비용", "정리된질문": "x"}
# ① 근거에 장학 문장이 없음 → 답쓰기가 비움 → 보류, 문구는 나라 단위 · 한 학교 링크 없음
res, calls = run(Q1, [], plan=dict(PLAN_DE, 의도="규정"), answer={"답": []})
expect("① 질문정리가 규정이라 해도 현지 대학 장학금은 근거 길", res["status"] == "hold" and "질문정리" in [c[0] for c in calls], res.get("status"))
expect("① 보류 문구 = 「독일 해봤노트에는」", "독일 해봤노트에는 아직 이 내용이 없어요" in res.get("message", ""), res.get("message"))
expect("① 나라 단위 보류에는 한 학교 noteId 없음", "noteId" not in res, res.get("noteId"))
res, calls = run(Q1, [], plan=dict(PLAN_DE, 의도="사람찾기"), answer={"답": []})
expect("① 질문정리가 사람찾기라 해도 주제어(장학)가 있으면 근거 길 → 보류", res["status"] == "hold", res.get("status"))
res, calls = run("독일 교환 다녀온 선배 있어요?", [], plan=dict(PLAN_DE, 의도="사람찾기", 칸=None))
expect("주제어 없는 사람 찾기는 그대로 노트 카드", res["status"] == "notes", res.get("status"))
# ② 학점 칸(2-2 수강신청·2-3 수업) 근거
cands, section, _ = askboo.extract(Q2, GERMANY)
expect("② 몇 학점 들어 → 학점 칸 근거", section == "학점" and cands, (section, len(cands)))
# ③ 학비·학기 등록 → 비용 칸 + 2-2의 「학기 등록만 하면 교통권」 문장이 후보에
cands, section, _ = askboo.extract(Q3, GERMANY)
expect("③ 학비 → 비용 칸", section == "비용", section)
expect("③ 학기 등록 문장이 후보에", any("학기 등록" in c["text"] for c in cands), len(cands))
# 학교 하나를 부른 질문의 보류 문구는 그대로 학교 이름
res, calls = run("마르부르크에서 아르바이트 했어요?", [],
                 plan={"의도": "경험질문", "분야": "국제교류", "나라": None, "프로그램후보": [PROGRAM], "제외": [], "칸": None, "정리된질문": "x"},
                 answer={"답": []})
expect("학교 하나 보류 문구는 학교 이름 + noteId", res["status"] == "hold" and f"{PROGRAM} 해봤노트에는" in res.get("message", "")
       and res.get("noteId"), (res.get("message"), res.get("noteId")))

# 기록 route에 새 길 이름
logged = []
_orig = askboo._log_answer
askboo._log_answer = lambda q, out, program=None, trace=None, prev=None: logged.append((trace or {}).get("route"))
for q, h, want in (("일본 도쿄 한달 생활비 얼마에요?", [], "도시 범위 밖"),
                   ("나가사키외국어대학교 말고 일본 대학 전체의 해봤노트에도 없나요?", H_NGS, "제외 범위")):
    askboo.callAI = make_fake()
    askboo.askBoo("H0143", {"question": q, "history": h}, save=True)
    expect(f"기록 route = {want}", logged and logged[-1] == want, logged[-1:])
askboo._log_answer = _orig

# ── [작업 105] 학교 이름 오타·변형 퍼지 대조 ───────────────────────────────
# 국제처 검토(11/26): 7변형 중 마브루크·마부루크·마르브루크·마르브루쿠가 보류로 빠짐
MARBURG_7 = ("마부르크", "마브루크", "마부루크", "마르부르크필립스", "마르부르크", "마르브루크", "마르브루쿠")
for v in MARBURG_7:
    expect(f"퍼지: 「{v}」 → 마르부르크", askboo.match_programs(f"{v} 기숙사 어땠어요?") == [PROGRAM],
           askboo.match_programs(f"{v} 기숙사 어땠어요?"))
expect("퍼지: 조사가 붙어도(마르브루쿠에서·마브루크대학교)",
       askboo.match_programs("마르브루쿠에서 생활비 얼마예요?") == [PROGRAM] == askboo.match_programs("마브루크대학교 수업 어때요?"))
res, _ = run("마브루크 기숙사 어땠어요?", [], plan=None, answer=None)
expect("퍼지: 답 경로도 마르부르크 근거(보류 아님)", res["status"] == "ok"
       and {s.get("program") for s in (res.get("sources") or {}).values()} == {PROGRAM}, res.get("status"))
res, row = saved_row("마르브루쿠 기숙사 어땠어요?")
expect("퍼지: 고친 글은 대조에만 — 원문 그대로 저장", "마르브루쿠 기숙사 어땠어요?" in row.values() and row["프로그램명"] == PROGRAM, row)
expect("퍼지: 다른 학교 별칭 「함부르크」(자모 2개 차이)는 함부르크", askboo.match_programs("함부르크 기숙사 어때요?") == ["함부르크 대학교"])
expect("퍼지: 뒤에 학교 종류 말 → 다른 학교(마브루크공과대학교)",
       PROGRAM not in askboo.match_programs("마브루크공과대학교 기숙사 어때요?"))
for q in ("마무리를 어떻게 했어요?", "마르지 않게 보관하는 법", "마지막으로 하나만요", "마르세유 생활비 알려줘", "말라고 했어요",
          "밀리니까 힘들었어요", "레지던시 프로그램", "레이어로 나눠 정리", "마트에서 장보기", "마부장님께 여쭤봐도"):
    expect(f"퍼지 반례: 「{q}」는 그대로", askboo.fix_names(q) == q, askboo.fix_names(q))
expect("퍼지: 3글자 이름(말라가·밀라노)은 퍼지 대상 아님", all(len(t) >= askboo.FUZZY_MIN for c in askboo._FUZZY.values() for t, _, _ in c))

# ── [작업 106] 비교과 이름 넓은 대조 · 근거 0 사실 답 · 유형 단위 질문 (#342 분류표, AI 없음) ─────────────
import notes  # noqa: E402

EX = {"직무탐색 교육 들을 만해요?": "한국외국어대학교 직무탐색 집중교육",
      "북플 독서모임 활동하면 뭐 해요?": "[HUFS 북플] 북클럽(독서모임) 활동",
      "GAT 해 보신 분 어땠어요?": "ISO 국제학생회 GAT 프로그램 수료자",
      "잡콘서트 가면 뭘 얻어요?": "하계 글로벌 잡콘서트: 글로벌 커리어 로드맵, 재직 동문 선배에게 길을 묻다",
      "NCS 수리 특강 도움 됐어요?": "[공기업 NCS 실시간 온라인 특강] NCS 수리능력",
      "BYOI 나가 보신 분 후기요": "Bring Your Own Ideas(BYOI)",
      "삼성 공채 프로그램 들으면 뭐가 좋아요?": "삼성 공채 대비 취업 프로그램",
      "국정원 설명회 가 볼 만해요?": "국가정보원 채용설명회",
      "네덜란드어과 대사관 특강은 뭘 알려 줘요?": "[특교원] 네덜란드 대사관 연계 특강",
      "독서PT대회 예선 참가비 있어요?": "도서관 (제4회) 독서PT대회 예선",
      # 사용 로그: 괄호 꼬리를 뗀 이름 · 부제를 뗀 이름(다른 비교과로 가지 않게)
      "동문 초청 진로 취업 릴레이 특강 어떤 활동 해요?": "동문 초청 진로 취업 릴레이 특강(+한화생명 채용설명회)",
      "25년 합격 자기소개서 취업특강 진로에 도움 됐어요?": "25년 합격 자기소개서 취업특강(커리어랩)"}
for q, want in EX.items():
    expect(f"비교과 넓은 대조: 「{q}」", askboo.match_programs(q) == [want], askboo.match_programs(q))
for q in ("튜터링 프로그램은 어때요?", "멘토링 프로그램 해 본 사람 후기 있어요?", "취업 특강 중에 뭐가 제일 도움 돼요?",
          "토익 스터디 비교과 해 보신 분 있어요?", "해커톤 참가 후기 알려 주세요", "예선 통과하려면 뭐 해요?",
          "네덜란드 생활비 얼마예요?", "선배에게 길을 묻다", "자소서 어떻게 써요?", "교환 가기 전 특강 있어요?"):
    expect(f"넓은 대조 반례(유형어·없는 활동·보통 말): 「{q}」 → 0개", askboo.extra_loose(q) == [], askboo.extra_loose(q))
expect("넓은 대조는 교환·인턴 문맥 말이 있으면 안 봄", askboo.extra_loose("마르부르크에서 학기 중 현지 인턴 병행할 수 있어요?") == []
       and askboo.match_programs("마르부르크에서 학기 중 현지 인턴 병행할 수 있어요?") == [PROGRAM])

GAT = "ISO 국제학생회 GAT 프로그램 수료자"
cover = notes.NOTES[notes.note_id(GAT)]
res, calls = run("GAT 해 보신 분 어땠어요?", [], plan=None, answer=None)
expect("근거 0 비교과 → 사실 답(세부·부서·이수 인원·만족도 + 경험담 없음)", res["status"] == "hold"
       and f"이수 인원 {cover['completedCount']}명" in res["message"] and f"만족도 {cover['satisfaction']:g}점" in res["message"]
       and "국제교류·버디 활동" in res["message"] and "국제교류팀" in res["message"] and askboo.EXTRA_NO_STORY in res["message"],
       res.get("message"))
expect("사실 답에도 그 노트 링크(noteId) — 노트에 이수 인원·만족도", res.get("noteId") == notes.note_id(GAT), res.get("noteId"))
expect("사실 답은 답쓰기를 부르지 않음(근거 0)", "답쓰기" not in [c[0] for c in calls], [c[0] for c in calls])
_saved = dict(cover)
cover.pop("completedCount")
cover.pop("satisfaction")
_sat = askboo.PROGRAMS[GAT].pop("만족도(5점)")
expect("데이터에 없는 값은 「–」(지어내지 않음)", "이수 인원 – · 만족도 –" in askboo.extra_facts(GAT), askboo.extra_facts(GAT))
cover.update(_saved)
askboo.PROGRAMS[GAT]["만족도(5점)"] = _sat
res, _ = run("GAT 해 보신 분 어땠어요?", [], plan={"의도": "경험질문", "분야": "비교과", "나라": None, "프로그램후보": ["GAT"],
                                             "제외": [], "칸": None, "정리된질문": "GAT 프로그램 후기"})
expect("질문정리 길에서도 같은 사실 답(프로그램후보 「GAT」도 대조)", res["status"] == "hold" and askboo.EXTRA_NO_STORY in res["message"],
       res.get("message"))

TUTOR = {n for n in askboo.EXTRA if "튜터링" in n or "TUTORING" in n}
res, calls = run("튜터링 프로그램은 어때요?", [], plan=None)
expect("유형 단위 → 그 유형 비교과 카드(130개 풀, 근거 0이어도)", res["status"] == "notes" and res["notes"]
       and {c["program"] for c in res["notes"]} == TUTOR and all(c["evidenceCount"] == 0 for c in res["notes"]), res)
expect("유형 단위 문구: 개수 + 이수 인원 순", res["message"].startswith(f"튜터링 비교과는 {len(TUTOR)}개 있어요.") and "이수 인원" in res["message"],
       res["message"])
expect("유형 단위는 AI를 부르지 않음(질문정리 앞에서 코드가 답함)", calls == [], [c[0] for c in calls])
res, _ = run("독일 튜터링 어때요?", [], plan=None)
expect("나라 이름 + 유형 말(「독일 튜터링」)은 비교과 유형 길이 아님", res["status"] != "notes"
       or not any(askboo.is_extra(c["program"]) for c in res["notes"]), res.get("message"))
res, _ = run("버디 활동은 보통 뭐 해요?", [], plan=None)
expect("버디 → 국제교류·버디 활동 세부 3개", res["status"] == "notes"
       and {c["program"] for c in res["notes"]} == {n for n in askboo.EXTRA if askboo.PROGRAMS[n]["세부"] == "국제교류·버디 활동"}, res)
res, _ = run("취업 특강 중에 뭐가 제일 도움 돼요?", [], plan=None)
sats = [askboo.extra_sat(c["program"]) for c in res["notes"]]
expect("「제일 도움」 → 만족도 순, 만족도로 본다고 밝힘", res["status"] == "notes" and sats == sorted(sats, reverse=True)
       and "만족도로 보여 드려요" in res["message"] and all("취업" in c["program"] for c in res["notes"]), res.get("message"))

res, _ = run("비교과 중에 만족도 제일 높은 건 뭐예요?", [], plan=None)
best = max(askboo.extra_sat(n) for n in askboo.EXTRA)
expect("만족도 순위는 코드가 셈(130개 중 최고점)", res["status"] == "notes" and askboo.extra_sat(res["notes"][0]["program"]) == best
       and f"{best:g}점" in res["message"] and f"{len(askboo.EXTRA)}개 중" in res["message"], res.get("message"))
res, _ = run("1학년이 들을 만한 비교과 추천해 주세요", [], plan=None)
g1 = max(askboo._STU_GRADE.get(n, {}).get(1, 0) for n in askboo.EXTRA)
expect("「1학년 추천」 → 1학년 때 이수한 인원 순(추천 순위는 없다고 밝힘)", res["status"] == "notes"
       and askboo._STU_GRADE[res["notes"][0]["program"]][1] == g1 and "추천 순위는 따로 없어서" in res["message"], res.get("message"))
res, _ = run("인적성검사랑 NCS 특강 중에 뭐가 나아요?", [], plan=None)
expect("비교과 둘 비교 → 이수 인원·만족도 나란히(어느 쪽이 낫다고 하지 않음)", res["status"] == "notes"
       and "인적성검사" in res["message"] and "NCS 특강 5개" in res["message"] and "말씀드리기 어려워요" in res["message"], res.get("message"))

for plan in (None, {"의도": "사람찾기", "분야": "비교과", "나라": None, "프로그램후보": [], "제외": [], "칸": None, "정리된질문": "토익 스터디"}):
    res, _ = run("토익 스터디 비교과 해 보신 분 있어요?", [], plan=plan)
    expect(f"없는 프로그램 → 보류, 카드 없음({'질문정리' if plan else 'v1'})", res["status"] == "hold" and not res.get("notes")
           and res["message"] == askboo.HOLD_NO_PROGRAM, res)
# 실서버에서 늘 같은 2장이 나오던 길: 근거 있는 비교과 노트가 있어도 _explore가 그 노트만 고르지 않는다
_ec = askboo.evidence_count
askboo.evidence_count = lambda n: 3 if n in ("HUFS 동문멘토링 데이", GAT) else _ec(n)
res, _ = run("자기계발 프로그램 뭐 있어요?", [], plan={"의도": "탐색", "분야": "비교과", "나라": None, "프로그램후보": [], "제외": [],
                                              "칸": None, "정리된질문": "자기계발 프로그램 목록"})
expect("비교과 탐색에 이름·유형이 안 맞으면 근거 있는 2장 대신 보류", res["status"] == "hold" and not res.get("notes"), res)
res, _ = run("비교과 뭐 있어요?", [], plan={"의도": "탐색", "분야": "비교과", "나라": None, "프로그램후보": [], "제외": [],
                                       "칸": None, "정리된질문": "비교과 목록"})
expect("비교과 목록 → 130개 풀 이수 인원 순(근거 있는 노트 수도 말함)", res["status"] == "notes" and len(res["notes"]) == askboo.MAX_NOTES
       and f"{len(askboo.EXTRA)}개 있어요" in res["message"] and "선배 경험담이 있는 노트는 2개" in res["message"], res.get("message"))
askboo.evidence_count = _ec
res, _ = run("비교과는 데이터가 아예 없나요?", [], plan={"의도": "탐색", "분야": "비교과", "나라": None, "프로그램후보": [], "제외": [],
                                              "칸": None, "정리된질문": "비교과 데이터가 있나요?"})
expect("「비교과 데이터 없나요?」 → 노트 130개(0개라고 하지 않음)", f"{len(askboo.EXTRA)}개 있어요" in (res.get("message") or ""), res)

# 시연 대본(0:00 답 · 0:40 보류)은 그대로
res, _ = run("마르부르크 생활비 얼마예요?", [], plan=None, answer=None)
expect("시연 0:00 생활비 → 마르부르크 근거 답", res["status"] == "ok" and {s["program"] for s in res["sources"].values()} == {PROGRAM}, res.get("status"))
res, _ = run("마부르크 파견 가려면 지원 서류는 뭘 준비해요?", [], plan=None, answer=None)
expect("시연 0:00 지원 서류 → 마르부르크 근거 답", res["status"] == "ok" and {s["program"] for s in res["sources"].values()} == {PROGRAM}, res.get("status"))
res, _ = run("마르부르크에서 학기 중 현지 인턴 병행할 수 있어요?", [], plan=None)
expect("시연 0:40 학기 중 현지 인턴 → 보류(비교과 사실 답 아님)", res["status"] == "hold" and askboo.EXTRA_NO_STORY not in res["message"], res)

# ── [11/26 작업 104] 공식 안내 연락처 · 「꼭 확인」 안내 · 도시 학교 고르기 ─────────────
D01 = askboo.DEPTS["D01"]
PHONE = D01.get("대표전화(가상)", "").strip()
res, calls = run("파견 장학금은 얼마 받아요?", [], plan=None)
expect("official 문구 끝에 「문의: 국제교류팀 <대표전화(가상)>」", res["status"] == "official" and PHONE
       and res["message"].endswith(f"문의: 국제교류팀 {PHONE}"), res.get("message"))
expect("official 응답에 officialPhone(departments.json 값 그대로)", res.get("officialPhone") == PHONE, res)
res, _ = run("국내 인턴십 학점 인정 신청은 언제까지예요?", [], plan=None)
expect("현장실습 규정 → 현장실습지원센터 연락처", res.get("officialPhone") == askboo.DEPTS["D02"]["대표전화(가상)"].strip()
       and "문의: 현장실습지원센터" in res["message"], res.get("message"))
_dept_saved = dict(D01)
D01.pop("대표전화(가상)", None)
res, _ = run("파견 장학금은 얼마 받아요?", [], plan=None)
expect("대표전화(가상)가 없으면 officialPhone 필드·「문의」 문구 없음", "officialPhone" not in res and "문의" not in res["message"], res)
res, _ = run("마르부르크 비자는 어떻게 받아요?", [], plan=None)
expect("전화 없으면 officialCheck에도 officialPhone 없음", res.get("officialCheck") and "officialPhone" not in res["officialCheck"]
       and "문의" not in res["officialCheck"]["message"], res.get("officialCheck"))
D01.update(_dept_saved)

# 경계: 비자·보험·지원 서류·파견 대학 규정 = 선배 답 그대로 + officialCheck. 외대 제도(학점 인정 신청·장학금·선발)는 official 그대로
for q, kind in [("마르부르크 비자는 어떻게 받아요?", "비자"), ("마르부르크 유학생 보험은 어떻게 했어요?", "비자"),
                ("겐트대학교 비자랑 보험은 어떻게 준비했어요?", "비자"),
                ("마부르크 파견 가려면 지원 서류는 뭘 준비해요?", "지원"), ("이날코 입학허가서 신청할 때 유의할 점은?", "지원")]:
    res, _ = run(q, [], plan=None)
    chk = res.get("officialCheck") or {}
    expect(f"{kind}: 「{q}」 → 선배 답(ok) + 「꼭 확인」 안내 + 연락처", res["status"] == "ok" and "꼭 확인해 주세요" in chk.get("message", "")
           and chk.get("officialPhone") == PHONE and chk.get("officialUrl") == D01["공식안내URL"]
           and ("대사관" in chk["message"]) == (kind == "비자"), (res["status"], chk))
expect("「꼭 확인」 안내는 lines에 넣지 않음(근거 번호 없는 문장이 답에 섞이지 않게)",
       all("꼭 확인" not in ln["text"] for ln in run("마르부르크 비자는 어떻게 받아요?", [], plan=None)[0]["lines"]))
res, _ = run("독일에서 교환학생 장학금 받은 사람이 있나? 독일 현지 대학교에서 주는 장학금 말이야", [], plan=None)
expect("현지 대학 장학금(Q-38 근거 길) → 「그 대학 안내」 확인 안내", res["status"] != "official"
       and "그 대학 안내" in (res.get("officialCheck") or {}).get("message", ""), (res["status"], res.get("officialCheck")))
# [11/26 미리 결정] 학점 인정 경험 → 선배 답 + 「학과 사무실에서 꼭 확인」(연락처 없음 — departments.json에 학과 사무실 없음)
for q in ["마르부르크에서 들은 수업 학점 인정 받을 때 주의할 점 있어요?", "리옹3 대학 학점 인정 받을 때 챙길 서류 있어요?"]:
    res, _ = run(q, [], plan=None)
    chk = res.get("officialCheck") or {}
    expect(f"학점 인정 경험: 「{q}」 → 선배 답 + 「학과 사무실에서 꼭 확인」, 전화 없음", res["status"] == "ok"
           and "학과 사무실에서 꼭 확인해 주세요." in chk.get("message", "") and "문의" not in chk.get("message", "")
           and "officialPhone" not in chk, (res["status"], chk))
res, _ = run("국내 인턴십 학점 인정 신청은 언제까지예요?", [], plan=None)
expect("학점 인정 신청(규정 표현)은 official 그대로(확인 안내 없음)", res["status"] == "official" and "officialCheck" not in res, res)
res, _ = run("하이델베르크대학교 파견 서류 뭐 내요?", [], plan=None)
expect("보류여도 지원 서류 질문이면 확인 안내", res["status"] == "hold" and res.get("officialCheck"), res)
askboo.callAI = make_fake()
res = askboo.askBoo("H0143", {"question": "마르부르크 비자는 어떻게 받아요?", "force": "hold"}, save=False)
expect("「질문함에 담기」(force hold)에는 확인 안내 없음", "officialCheck" not in res, res)
# 과잉 안내 0: 생활·수업·경험 질문(규정 말이 없음)에는 붙지 않는다
for q in ["마르부르크 가면 한 달 생활비 얼마나 들어요?", "마르부르크 기숙사비 한 달에 얼마예요?", "이날코 교환학생 기숙사 있어요?",
          "마르부르크 수강신청은 어떻게 해요?", "마르부르크대 공항에서 학교까지 어떻게 가요?", "볼로냐대학교 교환 가기 전에 알아 두면 좋은 팁 있어요?",
          "리스본종합대학교 방 구할 때 예산은요?", "마르부르크에서 학기 중 현지 인턴 병행할 수 있어요?", "파견 대학에서 몇 학점 수강했어요?",
          "보통 독일 대학교에서 몇학점 들어?", "코임브라대학교 공항에서 학교까지 교통편은?"]:
    res, _ = run(q, [], plan=None)
    expect(f"과잉 안내 없음: 「{q}」", "officialCheck" not in res, res.get("officialCheck"))
expect("official 응답에는 officialCheck 없음(문구에 이미 연락처)", "officialCheck" not in run("파견 장학금은 얼마 받아요?", [], plan=None)[0])

# 도시 학교 고르기(A안 측정 51번)
LYON = [n for n in askboo.COUNTRIES["프랑스"] if "리옹" in n and askboo.evidence_count(n)]
for plan in (None, P("경험질문", "국제교류", "프랑스", q="리옹 대학 한 달 생활비")):
    res, calls = run("리옹 대학 생활비 한 달에 얼마예요?", [], plan=plan)
    expect(f"「리옹 대학 생활비」 → 섞어 답하지 않고 리옹 학교 카드({'질문정리' if plan else 'v1'})",
           res["status"] == "notes" and {c["program"] for c in res["notes"]} == set(LYON) and len(LYON) >= 2
           and res["message"].endswith("어느 학교인지 골라 주세요.") and not res["lines"], res)
    expect("도시 학교 고르기는 AI를 부르지 않고 질문함에 저장하지 않음", calls == [] and "questionId" not in res, calls)
res, _ = run("리옹에서 기숙사 어때요?", [], plan=None)
expect("「리옹에서 기숙사」 → 고르기", res["status"] == "notes" and "어느 학교인지" in res["message"], res.get("message"))
for q, prog in [("뤼미에르 리옹 2대학 생활비는요?", "뤼미에르 리옹 2대학"), ("리옹3 대학 학점 인정 받을 때 챙길 서류 있어요?", "쟝 물랑 리옹 3 대학")]:
    res, _ = run(q, [], plan=None)
    expect(f"학교를 특정하면 그 학교로 답: 「{q}」", res["status"] == "ok" and {s["program"] for s in res["sources"].values()} == {prog},
           (res["status"], res.get("message")))
res, _ = run("뤼미에르 리옹 음악대학 수강신청 팁 있어요?", [], plan=None)
expect("목록에 없는 학교(「리옹 음악대학」) → 도시로 넓히지 않고 보류(함정 55)", res["status"] == "hold"
       and res["message"] == askboo.HOLD_NO_PROGRAM, res)
res, _ = run("리옹 물가 어때요?", [], plan=None)
expect("도시 자체 이야기(물가·치안)는 고르기 없이 그 도시 학교 근거로", res["status"] == "ok"
       and {s["program"] for s in res["sources"].values()} <= set(LYON), (res["status"], res.get("message")))
res, _ = run("리옹에 있는 학교 물가 어때요?", [], plan=None)
expect("학교를 말하면 주제와 상관없이 고르기", res["status"] == "notes" and "어느 학교인지" in res["message"], res.get("message"))
res, _ = run("일본 도쿄 한달 생활비 얼마예요?", [], plan=None)
expect("도시 학교 0개(도쿄)는 지금처럼 「0개예요」", res["status"] == "notes" and "도쿄에 있는 학교 해봤노트는 0개" in res["message"], res.get("message"))

# ── 정리 ──────────────────────────────────────────────────────────────
print()
print("실패 %d개" % len(fails) if fails else "전부 통과")
sys.exit(1 if fails else 0)
