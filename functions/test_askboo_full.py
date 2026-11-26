# test_askboo_full.py — [11/26 A안] 플래그 VCC_ASK_FULL 전문 길 시험. AI는 가짜(callAI 대신)라 돈을 쓰지 않는다.
# 보는 것: (a) 두 단계 번호 해석 (b) 코드 검사 범위 = 지목 문장 + 앞뒤 한 문장 (c) 글자 수 상한 자르기
#         (d) 옛 번호 "3"(문단 전체)도 통과 (e) 플래그 꺼지면 옛 길 그대로 + 전문 길 흐름(호출 순서·캐시·폴백·보류)
# 실행: cd functions && python test_askboo_full.py   (질문함에 저장하지 않는다: save=False)
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.pop("VCC_ASK_FULL", None)
import ai  # noqa: E402
import askboo  # noqa: E402

PROGRAM = "마르부르크필립스대학교"
fails = []


def expect(name, cond, info=""):
    print(("ok   " if cond else "FAIL ") + name + (f"  — {info}" if info and not cond else ""))
    if not cond:
        fails.append(name)


def ok(obj):
    text = json.dumps(obj, ensure_ascii=False)
    return {"ok": True, "text": text, "json": ai.first_json(text), "model": "fake"}


FAIL = {"ok": False, "text": "", "json": None, "model": "fake", "error": "x"}
PLAN = {"의도": "경험질문", "분야": "국제교류", "나라": None, "프로그램후보": [PROGRAM], "제외": [], "칸": "생활",
        "정리된질문": "마르부르크 기숙사는 어땠어요?"}


def make_fake(answer=None, match=True, plan=PLAN):
    """작업명별 가짜. answer=None이면 답쓰기(두 길 모두) 실패. match: 답검사 결과(함수면 원문·답으로 정한다)."""
    calls = []

    def fake(작업명, messages, system=None, cache=None, **kw):
        last = messages[-1]["content"]
        calls.append((작업명, last, cache))
        if 작업명 == "질문정리":
            return ok(plan) if plan else FAIL
        if 작업명 == "고르기":
            return ok({"관련": [1, 2]})
        if 작업명 in ("답쓰기", "답쓰기-전문"):
            a = answer(작업명) if callable(answer) else answer
            return ok(a) if a is not None else FAIL
        if 작업명 == "답검사":
            m = re.search(r"원문: (.*)\n답: (.*)\n출력", last, re.S)
            return ok({"일치": match(m.group(1), m.group(2)) if callable(match) else match})
        if 작업명 == "변환":
            return ok({"1": re.search(r"근거: (.*)\n출력", last, re.S).group(1)})
        raise KeyError(작업명)
    fake.calls = calls
    return fake


def run(question, flag, **kw):
    if flag is None:
        os.environ.pop("VCC_ASK_FULL", None)
    else:
        os.environ["VCC_ASK_FULL"] = flag
    askboo.callAI = make_fake(**kw)
    trace = {}
    res = askboo._answer("H0143", {"question": question, "history": []}, False, trace)
    return res, askboo.callAI.calls, trace


# 시험용 문단(실제 근거와 무관한 모양만)
P5 = {"n": 1, "sourceId": "R900-2-4", "docType": "귀국보고서", "program": PROGRAM, "semester": "2026-1", "label": "기숙사 정보",
      "sents": ["기숙사는 재단에 신청해요.", "보증금 500유로를 냈어요.", "월세는 320유로였어요.", "부엌은 같이 써요.", "세탁은 한 번에 7유로였어요."]}
P2 = {"n": 2, "sourceId": "R901-2-4", "docType": "귀국보고서", "program": PROGRAM, "semester": "2025-2", "label": "기숙사 정보",
      "sents": ["저는 2인실에서 월 280유로를 냈어요."]}
PARAS = [P5, P2]
BY_N = {p["n"]: p for p in PARAS}

# ── (a) 두 단계 번호 해석 ─────────────────────────────────────────────
expect("(a) \"3-2\" → (3, 2)", askboo.parse_ref("3-2") == (3, 2))
expect("(a) 대괄호·공백·긴 줄표도 읽음", askboo.parse_ref(" [3 - 2] ") == (3, 2) and askboo.parse_ref("3–2") == (3, 2))
expect("(a) 옛 번호 \"3\"·3 → (3, None)", askboo.parse_ref("3") == (3, None) and askboo.parse_ref(3) == (3, None))
expect("(a) 틀린 모양은 None", all(askboo.parse_ref(x) is None for x in ("a", "3-2-1", True, 3.5, None, [], "")))

ans = {"답": [{"text": "월세는 320유로였다고 해요.", "근거": ["1-3"]}]}
askboo.callAI = make_fake(answer=ans)
out, quotes = askboo.compose_full("기숙사 월세?", PARAS)
calls = askboo.callAI.calls
expect("(a) \"1-3\" → 문단 1의 sourceId로 cites", out and out["lines"][0]["cites"] == ["R900-2-4"], out)
expect("(a) 답검사 원문은 문단 전체 + 지목 문장에 ▶", calls[-1][0] == "답검사" and "▶ 월세는 320유로였어요." in calls[-1][1]
       and "세탁은 한 번에 7유로였어요." in calls[-1][1] and calls[-1][1].count("▶") == 1, calls[-1][1])
expect("(a) 원문 인용 후보 = 가리킨 문장", quotes and quotes[0]["text"] == "월세는 320유로였어요." and quotes[0]["sourceId"] == "R900-2-4")
expect("(a) compose_full 기본 문장 수 상한 = 6",
       askboo.compose_full.__defaults__[0] == askboo.MAX_ANSWER_LINES_FULL == 6)
askboo.callAI = make_fake(answer={"답": [{"text": "월세는 320유로였다고 해요.", "근거": ["1-9", "5-1"]}]})
out, quotes = askboo.compose_full("q", PARAS)
expect("(a) 번호가 다 틀리면 그 문장은 버림(후보도 없음)", out is None and quotes == [], (out, quotes))

# ── (b) 코드 검사 범위 = 지목 문장 + 앞뒤 한 문장 ────────────────────────
v, c, cited = askboo.full_sources([(1, 2)], BY_N)
expect("(b) 1-2의 범위 = 1-1·1-2·1-3", v == "기숙사는 재단에 신청해요. 보증금 500유로를 냈어요. 월세는 320유로였어요.", v)
v, _, _ = askboo.full_sources([(1, 1)], BY_N)
expect("(b) 첫 문장은 뒤 한 문장만", v == "기숙사는 재단에 신청해요. 보증금 500유로를 냈어요.", v)
v, _, _ = askboo.full_sources([(1, 5)], BY_N)
expect("(b) 끝 문장은 앞 한 문장만", v == "부엌은 같이 써요. 세탁은 한 번에 7유로였어요.", v)
v, c, cited = askboo.full_sources([(1, 2), (1, 5), (2, 1)], BY_N)
expect("(b) 같은 문단 두 번 → 한 번만, ▶ 두 개", c.count("▶") == 3 and c.count("기숙사는 재단에") == 1 and len(cited) == 2, c)

askboo.callAI = make_fake(answer={"답": [
    {"text": "세탁은 한 번에 7유로였다고 해요.", "근거": ["1-2"]},      # 7은 1-5에만 → 범위 밖 → 버림
    {"text": "월세는 320유로였다고 해요.", "근거": ["1-2"]},          # 320은 1-3(뒤 한 문장) → 통과
]})
out, _ = askboo.compose_full("q", PARAS)
expect("(b) 범위 밖 숫자(1-5의 7) 버림, 뒤 한 문장(1-3의 320) 통과",
       out and [l["text"] for l in out["lines"]] == ["월세는 320유로였다고 해요."], out and out["lines"])

# ── (c) 글자 수 상한 ───────────────────────────────────────────────────
paras, why = askboo.full_evidence("기숙사 어땠어요?", [PROGRAM])
n_all = len(askboo.EVIDENCE[PROGRAM]) + len(askboo.notes.interview_lines(PROGRAM))
expect("(c) 상한 안이면 문단 전부(쪼개지 않음)", len(paras) == n_all and why == "", (len(paras), n_all))
expect("(c) 번호는 1부터 차례로", [p["n"] for p in paras] == list(range(1, len(paras) + 1)))
keys = [askboo._semester_key(p["semester"]) for p in paras]
expect("(c) 최근 학기 먼저", keys == sorted(keys, reverse=True), keys[:5])
cap = 1500
small, _ = askboo.full_evidence("기숙사 어땠어요?", [PROGRAM], cap=cap)
total = sum(len(" ".join(p["sents"])) for p in small)
dropped = [e for e in askboo.EVIDENCE[PROGRAM] if e["id"] not in {p["sourceId"] for p in small}]
expect("(c) 상한 1,500자 → 그 안으로 자름", 0 < total <= cap and len(small) < n_all, (total, len(small)))
expect("(c) 오래된 학기부터 뺌", min(askboo._semester_key(p["semester"]) for p in small)
       >= max(askboo._semester_key(e["semester"]) for e in dropped), (small[-1]["semester"], dropped[0]["semester"]))
big = max(askboo.EVIDENCE, key=lambda n: sum(len(e["text"]) for e in askboo.EVIDENCE[n]))
paras, _ = askboo.full_evidence("x", [big])
expect(f"(c) 가장 큰 프로그램({big})도 2만 자 상한에 안 걸림", len(paras) == len(askboo.EVIDENCE[big]), len(paras))
two, _ = askboo.full_evidence("x", [PROGRAM, "레이던 대학교"])
text = askboo.render_evidence(two)
expect("(c) 여러 프로그램 → 프로그램별 머리글", text.count("\n## ") == 2 and f"## {PROGRAM}" in text and "## 레이던 대학교" in text)
expect("(c) 근거 글 모양: [n] 보고서 · 연도 · 선배X · 칸 / [n-1] 문장",
       re.search(r"^\[1\] 보고서 · \d{4} · 선배A · \S", text, re.M) and re.search(r"^  \[1-1\] \S", text, re.M), text[:300])
expect("(c) 근거 글은 부를 때마다 같은 글자(캐시)", askboo.render_evidence(two) == text)

# ── (d) 옛 번호 "3"도 통과 ──────────────────────────────────────────────
askboo.callAI = make_fake(answer={"답": [{"text": "세탁은 한 번에 7유로였다고 해요.", "근거": [1]},
                                         {"text": "2인실 월세는 280유로였다고 해요.", "근거": ["2"]}]})
out, quotes = askboo.compose_full("q", PARAS)
expect("(d) 옛 번호 1·\"2\" → 문단 전체로 대조해 통과", out and len(out["lines"]) == 2
       and out["lines"][1]["cites"] == ["R901-2-4"], out and out["lines"])
expect("(d) 문단만 가리키면 원문 인용 후보는 그 문단 첫 문장", [q["text"] for q in quotes] == ["기숙사는 재단에 신청해요.", "저는 2인실에서 월 280유로를 냈어요."])

# ── (e) 플래그 꺼짐 = 옛 길, 켜짐 = 전문 길 ──────────────────────────────
OLD_ANS = {"답": [{"text": "선배들은 기숙사에 대해 이렇게 말했어요.", "근거": [1, 2]}]}
base, calls0, tr0 = run("마르부르크 기숙사 어땠어요?", None, answer=OLD_ANS)
for flag in ("0", ""):
    res, calls, tr = run("마르부르크 기숙사 어땠어요?", flag, answer=OLD_ANS)
    expect(f"(e) VCC_ASK_FULL={flag!r} → 플래그 없을 때와 같은 응답", res == base, (res, base))
    expect(f"(e) VCC_ASK_FULL={flag!r} → 옛 길 호출 순서", [c[0] for c in calls] == ["질문정리", "고르기", "답쓰기", "답검사"]
           and all(c[2] is None for c in calls) and tr["route"] == "질문정리", ([c[0] for c in calls], tr))
expect("(e) 옛 길 답쓰기는 MAX_ANSWER_LINES 4 그대로", askboo.compose.__defaults__[0] == askboo.MAX_ANSWER_LINES == 4)

paras, _ = askboo.full_evidence("마르부르크 기숙사 어땠어요?", [PROGRAM])
s_room = next(f"{p['n']}-{j}" for p in paras for j, s in enumerate(p["sents"], 1) if re.search(r"\d+\s*유로", s) and "기숙사" in " ".join(p["sents"]))
FULL_ANS = {"답": [{"text": "선배들은 기숙사에 만족했다고 해요.", "근거": [s_room]}] * 1}
res, calls, tr = run("마르부르크 기숙사 어땠어요?", "1", answer=FULL_ANS)
names = [c[0] for c in calls]
expect("(e) 플래그 1 → 질문정리 → 답쓰기-전문 → 답검사(고르기 없음)", names == ["질문정리", "답쓰기-전문", "답검사"], names)
expect("(e) 기록 route에 「전문」", tr["route"] == "질문정리·전문", tr)
expect("(e) 근거 전문은 cache 블록, 질문은 가변", calls[1][2] and "[1-1]" in calls[1][2] and calls[1][1].startswith("질문: ")
       and "[1-1]" not in calls[1][1], (calls[1][1][:80], (calls[1][2] or "")[:80]))
expect("(e) 응답 모양 그대로(status·lines·cites·sources·noteId·singleSenior)",
       res["status"] == "ok" and set(res) >= {"lines", "sources", "noteId", "singleSenior", "suggestSenior"}
       and res["lines"][0]["cites"][0] in res["sources"] and res["lines"][0]["lineId"] == "L-A1-1", res)

six = {"답": [{"text": f"선배들은 기숙사가 좋았다고 해요{'.' * (i + 1)}", "근거": [s_room]} for i in range(8)]}
res, calls, _ = run("마르부르크 기숙사 어땠어요?", "1", answer=six)
expect("(e) 전문 길은 답 문장 6개까지", len(res["lines"]) == 6 and [c[0] for c in calls].count("답검사") == 6, len(res.get("lines", [])))

res, calls, tr = run("마르부르크 기숙사 어땠어요?", "1", answer=FULL_ANS, match=False)
expect("(e) 답검사가 다 거짓 → 가리킨 원문 문장 인용(fallback)", res["status"] == "ok" and res["lines"]
       and all(l.get("fallback") for l in res["lines"]) and "고르기" not in [c[0] for c in calls], (res.get("lines"), [c[0] for c in calls]))

res, calls, tr = run("마르부르크 기숙사 어땠어요?", "1", answer=lambda n: None if n == "답쓰기-전문" else OLD_ANS)
expect("(e) 답쓰기-전문 실패 → 옛 길(고르기 → 답쓰기)", [c[0] for c in calls] == ["질문정리", "답쓰기-전문", "고르기", "답쓰기", "답검사"]
       and tr["route"] == "질문정리·전문→옛 길" and res["status"] == "ok", ([c[0] for c in calls], tr))

res, calls, _ = run("마르부르크 기숙사 어땠어요?", "1", answer={"답": []})
expect("(e) 답쓰기-전문 빈 답 → hold", res["status"] == "hold" and res.get("_why") == "답쓰기 근거 없음"
       and [c[0] for c in calls] == ["질문정리", "답쓰기-전문"], (res.get("status"), res.get("_why")))

INTERN = next(n for n, p in askboo.PROGRAMS.items() if p.get("분야") == "현장실습" and askboo.EVIDENCE.get(n)
              and not askboo.notes.interview_lines(n))
paras, why = askboo.full_evidence("월급 얼마예요?", [INTERN])
expect("(e) 현장실습 근무조건 질문 + 인터뷰 없음 → 근거 없음(옛 길과 같은 규칙)", paras == [] and why.startswith("인터뷰로만"), why)

# ── ai.py cache 블록 ───────────────────────────────────────────────────
msgs = [{"role": "user", "content": "예시"}, {"role": "assistant", "content": "{}"}, {"role": "user", "content": "질문: q"}]
b = ai.with_cache_block(msgs, "근거 전문")
expect("cache: Claude는 마지막 user 글을 [고정(cache_control), 가변] 두 블록으로",
       b[-1]["content"] == [{"type": "text", "text": "근거 전문", "cache_control": {"type": "ephemeral"}}, {"type": "text", "text": "질문: q"}]
       and b[0]["content"] == "예시" and msgs[-1]["content"] == "질문: q")
expect("cache: HCX는 두 글을 이어 붙임", ai.with_cache_block(msgs, "근거 전문", blocks=False)[-1]["content"] == "근거 전문\n질문: q")
masked = ai.mask_messages(ai.with_cache_block(msgs, "연락처 010-1234-5678"))
expect("cache: 고정 블록도 mask로 가림", "010-1234-5678" not in json.dumps(masked, ensure_ascii=False)
       and masked[-1]["content"][0]["cache_control"] == {"type": "ephemeral"})

print()
os.environ.pop("VCC_ASK_FULL", None)
print("실패 %d개" % len(fails) if fails else "전부 통과")
sys.exit(1 if fails else 0)
