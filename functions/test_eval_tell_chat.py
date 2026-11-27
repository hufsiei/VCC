# test_eval_tell_chat.py — eval_tell_chat.py(작업 112 측정 준비) 시험. 실행: cd functions && python test_eval_tell_chat.py
# 실제 AI는 0회: ai.call_hcx·call_claude를 부르면 바로 실패로 센다. 가짜 callAI로 30상황 흐름과 기준 6개 판정을 본다.
# 기록은 임시 폴더(data/runtime을 건드리지 않음). 하나라도 틀리면 종료코드 1.
import contextlib
import io
import json
import re
import sys
import tempfile
from pathlib import Path

import store

store.RUNTIME = Path(tempfile.mkdtemp()) / "runtime"

import ai  # noqa: E402

REAL_CALLS = []


def _no_real(*a, **k):
    REAL_CALLS.append(a[:1])
    raise AssertionError("실제 AI 호출")


ai.call_hcx = _no_real
ai.call_claude = _no_real

import eval_tell_chat as ev  # noqa: E402
import interview  # noqa: E402
import tell_chat  # noqa: E402

fails = []


def expect(name, ok):
    print(("  ok  " if ok else "  XX  ") + name)
    if not ok:
        fails.append(name)


def quiet(fn, *a, **k):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        r = fn(*a, **k)
    return r, buf.getvalue()


# ── 상황 파일 ────────────────────────────────────────────────────────
doc = ev.load_cases()
expect("상황 파일 검사 통과", ev.validate(doc) == [])
expect("상황 30개", len(doc["상황"]) == 30)
groups = {}
for c in doc["상황"]:
    groups[c["묶음"]] = groups.get(c["묶음"], 0) + 1
expect("11/26 시험 14개 + 16개(다중턴·더들려주기·후배질문·궁금평서문·물음표만·11/27)",
       groups.get("1126") == 14 and all(groups.get(g) for g in ("다중턴", "더들려주기", "후배질문", "궁금평서문", "물음표만", "1127")))
s30 = next(c for c in doc["상황"] if c["id"] == "S30")
e30 = s30["턴"][0]["기대"]
expect("11/27 상황: 인턴 깊이 질문 + 「나도 그게 궁금했는데」 + 질문함글에 BOO 질문 + 담음문구만 + 다시묻기",
       ev.resolve_question(ev.program_of(doc, s30), "업무내용", s30["방금질문"]["질문"]) == "시작 전에 상상했던 일과 실제 업무가 어떻게 달랐나요?"
       and s30["턴"][0]["말"] == "나도 그게 궁금했는데" and e30["질문함"] and e30["다시묻기"] and e30["반응"] == "담음문구만"
       and any("상상했던" in s for s in e30["질문함글"]))
bad = json.loads(json.dumps(doc))
bad["상황"][0]["턴"][0]["기대"]["종류"] = ["대답"]
bad["상황"][1]["프로그램"] = "없는 학교"
bad["상황"][2]["턴"][0]["기대"]["모르는키"] = 1
bad["상황"][3]["방금질문"] = {"칸": "배운점", "질문": "@기본"}   # S04(다시묻기) — 코드의 다음 질문(활동내용)과 다름
probs = ev.validate(bad)
expect("상황 검사: 틀린 종류·없는 프로그램·모르는 기대를 잡음",
       any("종류" in p for p in probs) and any("없는 프로그램" in p for p in probs) and any("모르는 기대" in p for p in probs)
       and any(p.startswith("S04: 방금질문이 코드의 다음 질문과 다름") for p in probs))

# ── --dry: 호출 수·비용, AI 0회 ──────────────────────────────────────
est = ev.estimate(doc["상황"], 3, ["sonnet", "haiku"])
turns = sum(len(c["턴"]) for c in doc["상황"]) * 3
expect("예상: 턴 = 상황 턴 합 × 3", est["turns"] == turns and est["writers"]["sonnet"]["judge_calls"] == turns)
expect("예상: 그만 턴은 대화쓰기 안 셈", est["writers"]["sonnet"]["write_calls"] == turns - 2 * 3)
expect("예상: haiku가 sonnet보다 싸고 $ > 0",
       0 < est["writers"]["haiku"]["usd"] < est["writers"]["sonnet"]["usd"])
rc, out = quiet(ev.main, ["--dry"])
expect("--dry 종료코드 0 · 호출 수·예상 비용 출력", rc == 0 and "턴 " in out and "예상 $" in out and "AI 호출 0회" in out)
rc, out = quiet(ev.main, ["--dry", "--writer", "sonnet,haiku", "--only", "S09,S30", "--runs", "1"])
expect("--dry --only: 고른 상황만", rc == 0 and "상황 2개 × 1회" in out and "[haiku]" in out)
rc, out = quiet(ev.main, [])
expect("--yes 없으면 예상만 보여 주고 종료코드 2", rc == 2 and "--yes" in out)
expect("여기까지 실제 AI 0회", REAL_CALLS == [])

# ── 가짜 AI로 30상황 × 1회 ───────────────────────────────────────────
EXPECT_BY_SAID = {t["말"]: t["기대"] for c in doc["상황"] for t in c["턴"]}
QUESTIONS = ["그때 가장 먼저 떠오르는 장면은 뭐였어요?", "그 일을 하면서 어떤 점이 기억에 남았어요?",
             "처음 해 보니 어떤 느낌이었어요?", "가장 손이 많이 간 일은 뭐였어요?", "그 과정에서 무엇이 달랐어요?"]
FAKE = {"n": 0, "eval_reaction": False, "fail_judge": False}
SEEN = []


def said_of(content):
    m = re.search(r"^선배가 방금 한 말: (.*)$", content, re.M)
    return m.group(1).strip() if m else ""


def fake(작업명, messages, system=None):
    c = messages[-1]["content"]
    SEEN.append(작업명)
    if 작업명 == "말판정":
        if FAKE["fail_judge"]:
            return {"ok": False, "text": "", "json": None, "model": "fake", "error": "x"}
        e = EXPECT_BY_SAID.get(said_of(c), {"종류": ["답"]})
        j = {"종류": e["종류"][0], "궁금": said_of(c) if e.get("질문함") else None}
    elif 작업명 == "대화쓰기":
        kind = re.search(r"^방금 말의 종류: (.*)$", c, re.M).group(1)
        FAKE["n"] += 1
        if kind in tell_chat.REASK_KINDS:
            react = "질문이 조금 어려웠을 수 있어요." if FAKE["eval_reaction"] else "네, 다시 여쭤볼게요."
            j = {"반응": react, "칸": None, "더묻기": False, "질문": QUESTIONS[FAKE["n"] % len(QUESTIONS)]}
        elif kind == "답":   # 다른 칸 이야기는 대화쓰기의 칸이 옮긴다(S05)
            j = {"반응": "말씀 고마워요.", "칸": EXPECT_BY_SAID.get(said_of(c), {}).get("칸"), "더묻기": False, "질문": None}
        else:
            j = {"반응": "괜찮아요. 다음 질문으로 넘어갈게요.", "칸": None, "더묻기": False, "질문": None}
    elif 작업명 == "쪽지검사":
        j = {"ok": True}
    else:
        j = None
    if j is None:
        return {"ok": False, "text": "", "json": None, "model": "fake", "error": "x"}
    return {"ok": True, "text": json.dumps(j, ensure_ascii=False), "json": j, "model": "fake"}


ev.CTX["fake"] = fake
saved_model = ai.CLAUDE_MODEL
res, out = quiet(ev.run, doc, doc["상황"], 1, ["sonnet", "haiku"])
expect("가짜 AI 실행: 실제 AI 0회", REAL_CALLS == [])
expect("haiku 쓰기는 측정모델 claude(ai.py PROVIDER 그대로), 끝나면 CLAUDE_MODEL 원래대로",
       all(c["model"] == "fake:claude" for r in res["haiku"][1] for c in r["calls"] if c["작업"] == "대화쓰기")
       and all(c["model"] == "fake:sonnet" for r in res["sonnet"][1] for c in r["calls"] if c["작업"] == "대화쓰기")
       and ai.CLAUDE_MODEL == saved_model and ai.PROVIDER["대화쓰기"] == "sonnet")
s, recs = res["sonnet"]
expect("턴 기록 = 상황 턴 합", len(recs) == turns // 3)
expect("말판정 HCX·대화쓰기 모두 불림", "말판정" in SEEN and "대화쓰기" in SEEN)
expect("가짜(기대대로 판정): 판정 정확 100%", s["judge_acc"] == 1.0)
crit = {c["name"]: c for c in s["criteria"]}
expect("기준 6개 이름", list(crit) == ["판정 정확", "대화 밖 숫자·이름", "같은 질문 되풀이", "폴백", "궁금하지 않은 말 담김", "반응 평가 말"])
by = {}
for r in recs:
    by.setdefault(r["case"], []).append(r)
q114 = hasattr(tell_chat, "bare_deictic")
# S05(다른 칸 이야기): 답이 배운점으로 옮겨져 활동내용이 빈칸 → 지금 코드는 같은 질문을 원문 그대로 다시 묻는다.
# 기준 ③이 이것을 잡는다(가짜 AI에서도). tell_chat이 고쳐지면 0건이 된다
s05_repeat = by["S05"][0]["repeat"]
print(f"  (참고) S05 같은 질문 되풀이: {'있음 — 지금 tell_chat 동작' if s05_repeat else '없음'}")
expect("가짜: 밖 숫자 0 · 되풀이는 S05뿐 · 폴백 0 · 잘못 담김 0 · 평가 말 0",
       s["outside"] == 0 and s["repeat"] == int(s05_repeat) and s["fallback_rate"] == 0 and s["wrong_hold"] == 0
       and s["eval_word"] == 0)
expect("가짜: 되풀이 말고 기준 모두 통과, 되풀이가 있으면 미달로 보임",
       all(c["ok"] for c in s["criteria"] if c["name"] != "같은 질문 되풀이") and s["all_ok"] == (not s05_repeat))
not_pass = sorted(cid for cid, rs in by.items() if not all(r["pass"] for r in rs))
want_np = sorted(({"S05"} if s05_repeat else set()) | (set() if q114 else {"S09", "S30"}))
expect(f"가짜: 상황 기대 통과(S09·S30은 Q-114 {'있음 → 통과' if q114 else '없음 → 반응·질문함글에서 걸림'}) — 걸린 상황 {not_pass}",
       not_pass == want_np)
if not q114:
    r30 = by["S30"][0]
    expect("Q-114 전 S30: 질문함글·반응만 걸리고 담기·다시 묻기는 통과",
           r30["checks"]["질문함글"] is False and r30["checks"]["반응"] is False and r30["checks"]["질문함"]
           and r30["checks"]["다시묻기"])
expect("S16: 같은 질문에 부족 3번째는 모름으로 넘겨 다른 칸", by["S16"][2]["pass"] and by["S16"][2]["heard"]["kind"] == "모름"
       and by["S16"][2]["checks"]["넘김"])
expect("S19: 지난 노트 칸(비용·생활)은 안 물음", by["S19"][0]["checks"].get("안물을칸") is True)
expect("S21·S22·S23: 후배 질문 차례", all(by[c][0]["checks"].get("후배질문차례") for c in ("S21", "S22", "S23")))
expect("S12·S17: 그만이면 끝", by["S12"][0]["checks"]["끝"] and by["S17"][2]["checks"]["끝"])
expect("응답 시간·턴당 비용 열", "ms_avg" in s and "ms_p90" in s and "usd_per_turn" in s and "hcx_tokens_per_turn" in s
       and "말판정" in s["ms_by_job"])
_, out = quiet(ev.print_summary, "sonnet", s, recs)
expect("요약 출력: 기준 6줄", sum(1 for ln in out.splitlines() if ln.strip().startswith(("통과", "미달"))) == 6)

# ── 기준이 잘못을 잡는지 ─────────────────────────────────────────────
FAKE["eval_reaction"] = True
res2, _ = quiet(ev.run, doc, [c for c in doc["상황"] if c["id"] in ("S02", "S03")], 1, ["sonnet"])
s2 = res2["sonnet"][0]
expect("평가 말 반응 → 기준 ⑥에 걸리거나(Q-114 전) 코드가 버려 폴백(Q-114 뒤)",
       (s2["eval_word"] == 2 and not s2["all_ok"]) if not q114 else (s2["fallbacks"].get("반응 버림") == 2 and s2["eval_word"] == 0))
FAKE["eval_reaction"] = False
FAKE["fail_judge"] = True
res3, _ = quiet(ev.run, doc, [c for c in doc["상황"] if c["id"] in ("S01", "S02")], 1, ["sonnet"])
s3 = res3["sonnet"][0]
expect("말판정 실패 → 폴백 100%·판정 정확 0 → 미달",
       s3["fallback_rate"] == 1.0 and s3["fallbacks"] == {"말판정 실패": 2} and s3["judge_acc"] == 0 and not s3["all_ok"])
FAKE["fail_judge"] = False

turn = {"말": "x", "기대": {"종류": ["되물음"], "질문함": False}}
asked = {"section": "비용", "question": "한 달 생활비는 얼마나 들었어요?"}
judge_ok = {"작업": "말판정", "ok": True, "json": {"종류": "되물음", "궁금": None}, "usage": {}, "ms": 1, "model": "HCX-005"}
write = {"작업": "대화쓰기", "ok": True, "input": "선배가 방금 한 말: x 다음 질문: [비용] 한 달 생활비는 얼마나 들었어요?",
         "json": {"반응": "80만 원이었군요.", "질문": "한 달 생활비는 얼마나 들었어요?"}, "usage": {}, "ms": 1,
         "model": "claude-sonnet-5-5"}
new = {"section": "비용", "question": "한 달 생활비는 얼마나 들었어요?", "reaction": "80만 원이었군요.",
       "heard": {"kind": "되물음", "section": None}, "heldQuestionId": "Q-X"}
g = ev.grade_turn(turn, asked, new, [{"section": "비용", "question": asked["question"], "answer": "x"}], [judge_ok, write])
expect("채점: 대화 밖 숫자 잡음", any("80" in p for p in g["outside"]))
expect("채점: 같은 질문 되풀이 잡음", g["repeat"])
expect("채점: 궁금하지 않은 말이 담김 잡음", g["wrong_hold"])
expect("채점: 턴 실패", not g["pass"])
g2 = ev.grade_turn(turn, asked, {**new, "question": "생활비 중에 제일 큰 건 뭐였어요?", "reaction": "네, 다시 여쭤볼게요.",
                                 "heldQuestionId": None},
                   [{"section": "비용", "question": asked["question"], "answer": "x"}],
                   [judge_ok, {**write, "json": {"반응": "네, 다시 여쭤볼게요.", "질문": "생활비 중에 제일 큰 건 뭐였어요?"}}])
expect("채점: 깨끗한 되물음 턴은 통과", g2["pass"] and not g2["fallback"])
g3 = ev.grade_turn(turn, asked, {**new, "question": asked["question"], "reaction": "다시 여쭤볼게요.", "heldQuestionId": None},
                   [{"section": "비용", "question": asked["question"], "answer": "x"}],
                   [judge_ok, {**write, "json": {"반응": "질문이 어려웠죠.", "질문": "생활비 중에 제일 큰 건 뭐였어요?"}}])
expect("채점: 반응·질문이 검증에서 버려지면 폴백", g3["fallback"] == "반응 버림")
expect("비용: haiku 단가(1M당 0.10/0.50)",
       abs(ev._usd({"model": "claude-haiku-5-5", "usage": {"input": 1_000_000, "output": 1_000_000}}) - 0.60) < 1e-9)
fake_s = ev.summarize([{**g2, "ms": 10}] * 3 + [{**g3, "ms": 10}])
expect("요약: 폴백 25% → 기준 ④ 미달", fake_s["fallback_rate"] == 0.25
       and not next(c for c in fake_s["criteria"] if c["name"] == "폴백")["ok"])
expect("끝까지 실제 AI 0회", REAL_CALLS == [])

print(f"\n{len(fails)}건 실패" if fails else "\n모두 통과")
sys.exit(1 if fails else 0)
