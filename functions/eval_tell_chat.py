# eval_tell_chat.py — [작업 112] 대화형 들려주기(VCC_TELL_CHAT=1) 측정: 30상황 × N회, 기준 6개 자동 판정.
# 왜: 12/1(작업 113) 플래그를 켤지 숫자로 정한다. 상황은 docs/조사/112_대화형인터뷰_측정상황.json(11/26 시험 14개 + 16개).
#
# 실행 (cd functions):
#   python -X utf8 eval_tell_chat.py --dry                      # AI 0회. 상황 검사 + 호출 수·예상 비용만
#   python -X utf8 eval_tell_chat.py --yes                      # 실제 호출: HCX 말판정 + Sonnet 대화쓰기, 30상황 × 3회
#   python -X utf8 eval_tell_chat.py --yes --writer sonnet,haiku --json ../docs/조사/112_측정_1130.json
#   --runs N(기본 3) · --only S09,S30 · --writer sonnet|haiku|opus(쉼표로 여럿 = 같은 상황을 쓰기 모델마다 따로)
# --yes 없이 부르면 예상만 보여 주고 멈춘다(실수로 돈 쓰지 않게).
#
# 쓰기 모델 비교: ai.py의 PROVIDER·CLAUDE_MODELS는 건드리지 않는다(12/1까지 동결). 이 스크립트 안에서만 대화쓰기를
#   callAI(측정모델=…)로 부른다. haiku는 측정모델 "claude" + ai.CLAUDE_MODEL을 잠깐 claude-haiku-5-5로 바꿔서.
#   말판정·쪽지검사는 PROVIDER 그대로(HCX).
# 기록은 상황마다 새 임시 폴더(data/runtime을 건드리지 않음). AI 호출 로그는 본 저장소 functions/logs에 남는다(paths.py).
#
# 기준 6개(넘으면 「미달」):
#   ① 판정 정확 ≥ 95%   — heard.kind가 기대 종류, 답이면 칸도 맞음(코드가 MAX_REASK로 바꾼 뒤의 값으로 본다)
#   ② 대화 밖 숫자·이름 0건 — 화면에 나간 반응·질문을 tell_chat.facts_outside로 다시 봄(대화쓰기 입력 + ALLOW가 원문)
#   ③ 같은 질문 되풀이 0건 — 다음 질문이 이번 대화에서 이미 물은 질문과 같음(띄어쓰기·문장부호 무시). 후배 질문 차례는 뺌
#   ④ 폴백 ≤ 20%        — 말판정 실패·대화쓰기 실패·반응이나 질문이 코드 검증에서 버려진 턴 / 전체 턴
#   ⑤ 궁금하지 않은 말이 질문함에 담김 0건 — 기대 「질문함 false」인데 heldQuestionId
#   ⑥ 반응 평가 말 0건   — 부족·되물음·딴얘기 반응에 「어려웠·헷갈·이해…」(Q-114 tell_chat._EVAL, 없으면 같은 식)
# 함께 보는 열: 응답 시간(턴 평균·p90, 작업별 평균), 턴당 비용(Claude $ · HCX 토큰), 상황 기대(질문함 글·다시 묻기 등) 통과.
import argparse
import json
import math
import os
import re
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CASES_FILE = ROOT.parent / "docs" / "조사" / "112_대화형인터뷰_측정상황.json"
N_CASES = 30
WRITERS = {"sonnet": "sonnet", "opus": "opus", "haiku": "claude"}   # → callAI 측정모델
WRITER_IDS = {"sonnet": "claude-sonnet-5-5", "opus": "claude-opus-5-5", "haiku": "claude-haiku-5-5"}
PRICES = {"claude-sonnet-5-5": (2.0, 10.0), "claude-opus-5-5": (4.0, 20.0), "claude-haiku-5-5": (0.10, 0.50)}   # $ per 1M (입력, 출력)
# --dry 추정값: 로그(ai-calls.jsonl)에 그 모델 대화쓰기가 3건 넘게 있으면 그 평균, 없으면 아래 값(11/27 Sonnet 로그 평균 근처)
WRITE_TOKENS = (3900, 90)
GATE_TOKENS = (460, 15)          # 쪽지검사(질문함 관문 비방 판정) — 11/20 로그 평균 근처
HCX_CHARS_PER_TOKEN = 1.5        # 말판정 입력 토큰 추정(프롬프트 글자 수 ÷ 이 값). HCX 단가는 미확인이라 $에 넣지 않는다
JUDGE_OUT = 20
CRITERIA = [   # (이름, 비교, 기준, 값 키)
    ("판정 정확", ">=", 0.95, "judge_acc"),
    ("대화 밖 숫자·이름", "==", 0, "outside"),
    ("같은 질문 되풀이", "==", 0, "repeat"),
    ("폴백", "<=", 0.20, "fallback_rate"),
    ("궁금하지 않은 말 담김", "==", 0, "wrong_hold"),
    ("반응 평가 말", "==", 0, "eval_word"),
]
# Q-114(tell-tone)가 tell_chat._EVAL을 넣기 전에도 같은 기준으로 재도록 같은 식을 둔다
EVAL_WORDS = re.compile(r"어려[웠우워]|어렵|헷갈|이해|쉽게\s*말(하면|씀)|다시\s*말(해|하면|씀드리)|무슨\s*말인지|부족|모호|애매"
                        r"|질문이\s*(조금|좀|너무)?\s*(길|막연|추상)")
EXPECT_KEYS = {"종류", "칸", "질문함", "질문함글", "다시묻기", "반응", "안물을칸", "후배질문차례", "끝", "넘김"}
OTHER = "H0800"   # 후배 질문을 보낸 사람(가상)


# ── 상황 읽기·검사 ────────────────────────────────────────────────────
def load_cases(path=CASES_FILE):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def program_of(doc, case):
    return doc["프로그램"].get(case["프로그램"], case["프로그램"])


def resolve_question(program, section, text):
    """「@기본」 → 그 칸 첫 질문, 「@깊이:번호」 → 깊이 질문 글. 그 밖은 그대로."""
    import interview as iv
    if text == "@기본":
        return iv.base_question(program, section)
    if text.startswith("@깊이:"):
        d = iv.DEPTH_BY_ID[text[4:]]
        return d[2].format(p=iv.short_name(program))
    return text


def validate(doc, deep=True):
    """상황 파일 문제 목록(빈 목록이면 통과). AI를 부르지 않는다.
    deep: 「다시묻기」를 기대하는 첫 턴의 방금질문이 코드의 다음 질문과 같은지도 본다(임시 기록 폴더에서)."""
    import interview as iv
    import tell_chat
    probs, ids = [], set()
    cases = doc.get("상황") or []
    if len(cases) != N_CASES:
        probs.append(f"상황 {len(cases)}개(기대 {N_CASES})")
    for c in cases:
        cid = c.get("id")
        n_before = len(probs)
        if cid in ids:
            probs.append(f"{cid}: id 중복")
        ids.add(cid)
        prog = program_of(doc, c)
        if prog not in iv.askboo.PROGRAMS:
            probs.append(f"{cid}: 목록에 없는 프로그램 {prog}")
            continue
        secs = iv.sections_of(prog)
        for h in (c.get("지난대화") or []) + ([c["방금질문"]] if c.get("방금질문") else []):
            if h.get("칸") not in secs:
                probs.append(f"{cid}: 틀 밖 칸 {h.get('칸')}")
            q = h.get("질문") or ""
            if q.startswith("@깊이:") and q[4:] not in iv.DEPTH_BY_ID:
                probs.append(f"{cid}: 없는 깊이 질문 {q}")
        for s in list((c.get("지난노트") or {}).keys()) + [j.get("칸") for j in c.get("후배질문") or []]:
            if s not in secs:
                probs.append(f"{cid}: 틀 밖 칸 {s}")
        if not c.get("턴"):
            probs.append(f"{cid}: 턴 없음")
        for i, t in enumerate(c.get("턴") or [], 1):
            e = t.get("기대") or {}
            if not (t.get("말") or "").strip():
                probs.append(f"{cid} 턴{i}: 말 없음")
            if not e.get("종류") or any(k not in tell_chat.KINDS for k in e["종류"]):
                probs.append(f"{cid} 턴{i}: 종류 {e.get('종류')}")
            if "질문함" not in e:
                probs.append(f"{cid} 턴{i}: 질문함 기대 없음")
            if set(e) - EXPECT_KEYS:
                probs.append(f"{cid} 턴{i}: 모르는 기대 {sorted(set(e) - EXPECT_KEYS)}")
            if e.get("칸") and e["칸"] not in secs:
                probs.append(f"{cid} 턴{i}: 틀 밖 칸 {e['칸']}")
        if deep and len(probs) == n_before and c.get("방금질문") and c.get("턴") and c["턴"][0].get("기대", {}).get("다시묻기"):
            me = "H0999"
            fresh_store()
            seed(me, prog, c)
            nxt = plan_next(me, prog, history(prog, c))
            want = resolve_question(prog, c["방금질문"]["칸"], c["방금질문"]["질문"])
            if (nxt.get("section"), nxt.get("question")) != (c["방금질문"]["칸"], want):
                probs.append(f"{cid}: 방금질문이 코드의 다음 질문과 다름(다시묻기 측정이 틀어짐) — 코드: "
                             f"[{nxt.get('section')}] {nxt.get('question')}")
    return probs


def select(doc, only=None):
    cases = doc["상황"]
    if only:
        want = {x.strip() for x in only.split(",") if x.strip()}
        cases = [c for c in cases if c["id"] in want]
    return cases


# ── 예상(--dry) ───────────────────────────────────────────────────────
def _log_avg(model_id, job="대화쓰기"):
    try:
        import paths
        rows = [json.loads(ln) for ln in (paths.LOGS / "ai-calls.jsonl").open(encoding="utf-8")]
    except (OSError, ValueError):
        return None
    rows = [r for r in rows if r.get("작업") == job and r.get("모델") == model_id and r.get("입력토큰")]
    if len(rows) < 3:
        return None
    return (statistics.mean(r["입력토큰"] + (r.get("캐시읽기토큰") or 0) + (r.get("캐시쓰기토큰") or 0) for r in rows),
            statistics.mean(r.get("출력토큰") or 0 for r in rows))


def _judge_tokens():
    from ai import load_prompt
    system, shots = load_prompt("말판정")
    chars = len(system or "") + sum(len(str(m.get("content", ""))) for m in shots) + 250   # + 한 턴 입력(칸·질문·앞 대화·말)
    return chars / HCX_CHARS_PER_TOKEN


def estimate(cases, runs, writers):
    turns = sum(len(c["턴"]) for c in cases) * runs
    stops = sum(1 for c in cases for t in c["턴"] if t["기대"]["종류"] == ["그만"]) * runs
    holds = sum(1 for c in cases for t in c["턴"] if t["기대"].get("질문함")) * runs
    jt = _judge_tokens()
    out = {"cases": len(cases), "runs": runs, "turns": turns, "writers": {}}
    for w in writers:
        mid = WRITER_IDS[w]
        tin, tout = _log_avg(mid) or WRITE_TOKENS
        n_write = turns - stops
        usd = n_write * (tin * PRICES[mid][0] + tout * PRICES[mid][1]) / 1e6
        out["writers"][w] = {
            "model": mid, "judge_calls": turns, "write_calls": n_write, "gate_calls": holds,
            "write_tokens_each": (round(tin), round(tout)), "usd": usd, "usd_per_turn": usd / turns if turns else 0,
            "hcx_calls": turns + holds,
            "hcx_tokens": round(turns * (jt + JUDGE_OUT) + holds * sum(GATE_TOKENS)),
        }
    return out


def print_estimate(est):
    print(f"상황 {est['cases']}개 × {est['runs']}회 = 턴 {est['turns']}개")
    total = 0
    for w, e in est["writers"].items():
        total += e["usd"]
        print(f"  [{w}] 말판정(HCX) {e['judge_calls']}회 + 대화쓰기({e['model']}) {e['write_calls']}회"
              f" + 쪽지검사(HCX, 질문함에 담을 때) 약 {e['gate_calls']}회")
        print(f"      대화쓰기 한 번 입력 {e['write_tokens_each'][0]:,} · 출력 {e['write_tokens_each'][1]:,}토큰 →"
              f" 예상 ${e['usd']:.2f} (턴당 ${e['usd_per_turn']:.4f}) · HCX {e['hcx_calls']}회 약 {e['hcx_tokens']:,}토큰(크레딧)")
    print(f"  합계 예상 Claude ${total:.2f} (HCX는 단가 미확인 — 회수·토큰만)")
    return total


# ── 호출 엿보기 ───────────────────────────────────────────────────────
CTX = {"writer": None, "calls": [], "stack": [], "fake": None}
_PATCHED = {}


def install(fake=None):
    """interview·askboo의 callAI와 ai.call_hcx·call_claude를 감싼다(시간·토큰·출력 기록, 대화쓰기 모델 바꾸기).
    fake: 시험용 가짜 callAI(작업명, messages, system) — 주면 실제 호출 대신 그것을 부른다."""
    import ai
    import askboo
    import interview
    CTX["fake"] = fake
    if _PATCHED:
        return
    _PATCHED.update(callAI=ai.callAI, hcx=ai.call_hcx, claude=ai.call_claude)

    def spy_callAI(작업명, messages, system=None, 측정모델=None, 측정설정=None, cache=None):
        if 작업명 == "대화쓰기" and CTX["writer"]:
            측정모델 = WRITERS[CTX["writer"]]
        rec = {"작업": 작업명, "model": None, "usage": {}, "input": messages[-1].get("content") if messages else ""}
        CTX["stack"].append(rec)
        t0 = time.perf_counter()
        try:
            if CTX["fake"]:
                out = CTX["fake"](작업명, messages, system)
                rec["model"] = f"fake:{측정모델 or ai.PROVIDER.get(작업명)}"
            else:
                out = _PATCHED["callAI"](작업명, messages, system, 측정모델=측정모델, 측정설정=측정설정, cache=cache)
        finally:
            CTX["stack"].pop()
        rec.update(ms=int((time.perf_counter() - t0) * 1000), ok=bool(out.get("ok")), json=out.get("json"))
        CTX["calls"].append(rec)
        return out

    def spy_hcx(messages, system, 설정):
        text, usage = _PATCHED["hcx"](messages, system, 설정)
        if CTX["stack"]:
            CTX["stack"][-1].update(model="HCX-005", usage=usage)
        return text, usage

    def spy_claude(messages, system, 설정, model_id):
        text, usage = _PATCHED["claude"](messages, system, 설정, model_id)
        if CTX["stack"]:
            CTX["stack"][-1].update(model=model_id, usage=usage)
        return text, usage

    interview.callAI = spy_callAI
    askboo.callAI = spy_callAI
    ai.call_hcx = spy_hcx
    ai.call_claude = spy_claude


def _usd(rec):
    p = PRICES.get(rec.get("model"))
    u = rec.get("usage") or {}
    if not p:
        return 0.0
    tin = (u.get("input") or 0) + (u.get("cache_write") or 0) * 1.25 + (u.get("cache_read") or 0) * 0.1
    return (tin * p[0] + (u.get("output") or 0) * p[1]) / 1e6


# ── 한 상황 돌리기 ────────────────────────────────────────────────────
def fresh_store():
    import store
    with store.lock():   # 상황마다 빈 기록 — 앞 상황에서 질문함에 담긴 말이 다음 상황의 후배 질문으로 끼지 않게
        store.RUNTIME = Path(tempfile.mkdtemp(prefix="vcc112-")) / "runtime"
        store._cache.clear()


def seed(me, program, case):
    import store
    with store.lock():
        if case.get("후배질문"):
            rows = store.load("questions", [])
            for i, j in enumerate(case["후배질문"], 1):
                rows.append({"id": f"Q-E112{i}", "colreg_no": OTHER, "질문": j["질문"], "프로그램명": program,
                             "칸": j.get("칸"), "status": "hold", "at": f"2026-11-27T10:0{i}:00"})
            store.save("questions")
        if case.get("지난노트"):
            notes = store.load("myNotes", {})
            notes["M-E112"] = {"owner": me, "program": program, "askedDepth": [],
                               "myNote": {"sections": [{"name": s, "lines": [{"text": t} for t in lines]}
                                                       for s, lines in case["지난노트"].items()]}}
            store.save("myNotes")


def ans(step, text):
    """화면처럼: section·question(후배 질문은 asked)·answer·questionId."""
    a = {"section": step.get("section"), "question": step["asked"] if step.get("junior") else step.get("question"),
         "answer": text}
    if step.get("questionId"):
        a["questionId"] = step["questionId"]
    return a


def held_text(qid):
    import store
    with store.lock():
        row = next((q for q in store.load("questions", []) if q.get("id") == qid), None)
    return (row or {}).get("질문") or ""


def history(program, case):
    return [{"section": h["칸"], "question": resolve_question(program, h["칸"], h["질문"]), "answer": h["답"]}
            for h in case.get("지난대화") or []]


def plan_next(me, program, answers):
    """코드가 정하는 다음 질문(대화형 AI 없이 — 지난대화는 모두 답으로 친다). 칸 없는 후배 질문이면 문단분류가 불릴 수 있음."""
    import interview as iv
    _, mine = iv.find_my_note(me, program)
    return iv._next_step(me, program, {"program": program, "answers": answers}, iv.prior_of(program, mine), follow=False)


def run_case(doc, case, me):
    """상황 하나 → 턴 기록 목록. 실제(또는 가짜) AI를 부른다."""
    import interview as iv
    program = program_of(doc, case)
    fresh_store()
    seed(me, program, case)
    answers = history(program, case)
    CTX["calls"] = []
    if case.get("방금질문"):
        q = case["방금질문"]
        step = {"section": q["칸"], "question": resolve_question(program, q["칸"], q["질문"])}
    else:   # 화면이 받는 다음 질문. interviewNext로 부르면 지난대화 마지막 답을 말판정하므로 _next_step을 바로
        step = plan_next(me, program, answers)
    out = []
    for n, turn in enumerate(case["턴"], 1):
        if step.get("done") or step.get("error"):
            out.append({"case": case["id"], "turn": n, "said": turn["말"], "skipped": "앞 턴에서 끝남",
                        "checks": {"끝나서 못 물음": False}, "pass": False, "kind_ok": False, "fallback": "턴 못 함",
                        "ms": 0, "usd": 0.0, "hcx_tokens": 0, "calls": []})
            continue
        a = ans(step, turn["말"])
        answers.append(a)
        CTX["calls"] = []
        t0 = time.perf_counter()
        new = iv.interviewNext(me, {"program": program, "answers": [dict(x) for x in answers]})
        ms = int((time.perf_counter() - t0) * 1000)
        rec = grade_turn(turn, step, new, answers, list(CTX["calls"]))
        rec.update(case=case["id"], turn=n, said=turn["말"], ms=ms)
        out.append(rec)
        step = new
    return out


# ── 채점 ──────────────────────────────────────────────────────────────
def _norm(s):
    return " ".join((s or "").split())


def grade_turn(turn, asked_step, new, answers, calls):
    import interview as iv
    import tell_chat
    e = turn["기대"]
    qn = tell_chat._qn
    evalre = getattr(tell_chat, "_EVAL", EVAL_WORDS)
    no_react_held = getattr(tell_chat, "NO_REACTION_HELD", set())
    judge = [c for c in calls if c["작업"] == "말판정"]
    write = [c for c in calls if c["작업"] == "대화쓰기"]
    heard = new.get("heard") or {}
    kind, section = heard.get("kind"), heard.get("section")
    done = bool(new.get("done"))
    held = new.get("heldQuestionId")
    reaction = new.get("reaction") or ""
    body = _norm(reaction.replace(tell_chat.HELD_TEXT, ""))
    q = "" if done else (new.get("question") or "")
    q_core = q[len(iv.JUNIOR_FOLLOW):] if q.startswith(iv.JUNIOR_FOLLOW) else q

    kind_ok = kind in e["종류"] and not (kind == "답" and e.get("칸") and section != e["칸"])

    source = (write[-1]["input"] + " " + tell_chat.ALLOW) if write else ""
    outside = []
    if source:
        outside = [f"반응 {p}" for p in tell_chat.facts_outside(body, source)] if body else []
        outside += [f"질문 {p}" for p in tell_chat.facts_outside(q_core, source)] if q_core else []

    asked_before = {qn(x.get("question")) for x in answers} | {qn(iv._unwrap(x.get("question") or "")) for x in answers}
    repeat = bool(q_core) and not new.get("junior") and qn(q_core) in asked_before

    eval_word = kind in tell_chat.REASK_KINDS and bool(body) and bool(evalre.search(body))

    jj = judge[-1].get("json") if judge else None
    fallback = None
    if not (judge and judge[-1].get("ok") and isinstance(jj, dict) and jj.get("종류") in tell_chat.KINDS):
        fallback = "말판정 실패"
    elif kind != "그만":
        w = write[-1].get("json") if write else None
        if not write:
            fallback = "대화쓰기 안 부름"
        elif not (write[-1].get("ok") and isinstance(w, dict)):
            fallback = "대화쓰기 실패"
        else:
            raw_r, raw_q = w.get("반응"), w.get("질문")
            intended_blank = held and kind in no_react_held   # Q-114: 담은 턴은 반응 없이(의도)
            if isinstance(raw_r, str) and raw_r.strip() and not intended_blank and body != _norm(raw_r):
                fallback = "반응 버림"
            elif isinstance(raw_q, str) and raw_q.strip() and q_core and not new.get("junior") \
                    and qn(q_core) != qn(raw_q):
                fallback = "질문 버림"   # (드묾) 답이 다른 칸으로 옮겨져 다음 질문이 바뀐 경우도 여기로 센다

    checks = {"종류": kind_ok, "질문함": bool(held) == bool(e.get("질문함"))}
    if e.get("질문함글"):
        txt = _norm(held_text(held)) if held else ""
        checks["질문함글"] = all(_norm(s) in txt for s in e["질문함글"])
    if e.get("다시묻기") and not asked_step.get("junior"):
        checks["다시묻기"] = (not done and new.get("section") == asked_step.get("section")
                          and bool(q_core) and qn(q_core) != qn(asked_step.get("question")))
    if e.get("반응") == "담음문구만":
        checks["반응"] = reaction == tell_chat.HELD_TEXT
    if e.get("안물을칸"):
        checks["안물을칸"] = asked_step.get("section") not in e["안물을칸"] and (done or new.get("section") not in e["안물을칸"])
    if "후배질문차례" in e:
        checks["후배질문차례"] = bool(asked_step.get("junior")) == bool(e["후배질문차례"])
    if "끝" in e:
        checks["끝"] = done == bool(e["끝"])
    if e.get("넘김"):
        checks["넘김"] = done or new.get("section") != asked_step.get("section")
    ok = all(checks.values()) and not outside and not repeat and not eval_word
    return {
        "asked": {"section": asked_step.get("section"), "question": asked_step.get("question"),
                  "junior": bool(asked_step.get("junior"))},
        "heard": heard, "held": bool(held), "heldText": held_text(held) if held else None,
        "reaction": reaction, "next": {"section": new.get("section"), "question": q, "followUp": bool(new.get("followUp")),
                                       "done": done, "junior": bool(new.get("junior"))},
        "judge": jj, "write": write[-1].get("json") if write else None,
        "kind_ok": kind_ok, "wrong_hold": bool(held) and not e.get("질문함"),
        "missed_hold": bool(e.get("질문함")) and not held, "outside": outside, "repeat": repeat,
        "eval_word": eval_word, "fallback": fallback, "checks": checks, "pass": ok,
        "usd": sum(_usd(c) for c in calls),
        "hcx_tokens": sum((c["usage"].get("input") or 0) + (c["usage"].get("output") or 0)
                          for c in calls if c.get("model") == "HCX-005"),
        "calls": [{k: c.get(k) for k in ("작업", "model", "ms", "ok")} | {"usage": c.get("usage")} for c in calls],
    }


def _p90(xs):
    xs = sorted(xs)
    return xs[max(0, math.ceil(len(xs) * 0.9) - 1)] if xs else 0


def summarize(recs):
    n = len(recs)
    by_job = {}
    for r in recs:
        for c in r["calls"]:
            by_job.setdefault(c["작업"], []).append(c["ms"] or 0)
    s = {
        "turns": n,
        "judge_acc": sum(r["kind_ok"] for r in recs) / n if n else 0,
        "outside": sum(len(r.get("outside") or []) for r in recs),
        "repeat": sum(bool(r.get("repeat")) for r in recs),
        "fallback_rate": sum(bool(r.get("fallback")) for r in recs) / n if n else 0,
        "wrong_hold": sum(bool(r.get("wrong_hold")) for r in recs),
        "eval_word": sum(bool(r.get("eval_word")) for r in recs),
        "missed_hold": sum(bool(r.get("missed_hold")) for r in recs),
        "turn_pass": sum(bool(r["pass"]) for r in recs),
        "fallbacks": {},
        "ms_avg": statistics.mean(r["ms"] for r in recs) if n else 0,
        "ms_p90": _p90([r["ms"] for r in recs]),
        "ms_by_job": {k: round(statistics.mean(v)) for k, v in by_job.items()},
        "usd": sum(r["usd"] for r in recs),
        "usd_per_turn": sum(r["usd"] for r in recs) / n if n else 0,
        "hcx_tokens_per_turn": sum(r["hcx_tokens"] for r in recs) / n if n else 0,
    }
    for r in recs:
        if r.get("fallback"):
            s["fallbacks"][r["fallback"]] = s["fallbacks"].get(r["fallback"], 0) + 1
    s["criteria"] = [{"name": name, "op": op, "bar": bar, "value": s[key], "ok": _meets(s[key], op, bar)}
                     for name, op, bar, key in CRITERIA]
    s["all_ok"] = all(c["ok"] for c in s["criteria"])
    return s


def _meets(v, op, bar):
    return v >= bar if op == ">=" else v <= bar if op == "<=" else v == bar


def _fmt(v, bar):
    return f"{v * 100:.1f}%" if isinstance(bar, float) else f"{v}건"


def print_summary(writer, s, recs):
    print(f"\n=== [{writer}] 턴 {s['turns']}개 · 턴 통과 {s['turn_pass']}/{s['turns']} · 기준 "
          + ("모두 통과" if s["all_ok"] else "미달 있음"))
    for c in s["criteria"]:
        print(f"  {'통과' if c['ok'] else '미달'}  {c['name']} {_fmt(c['value'], c['bar'])} (기준 {c['op']} {_fmt(c['bar'], c['bar'])})")
    if s["fallbacks"]:
        print("  폴백 내역: " + ", ".join(f"{k} {v}" for k, v in sorted(s["fallbacks"].items())))
    print(f"  참고: 질문함 놓침 {s['missed_hold']}건 · 응답 시간 턴 평균 {s['ms_avg']:.0f}ms · p90 {s['ms_p90']}ms · 작업별 "
          + ", ".join(f"{k} {v}ms" for k, v in s["ms_by_job"].items()))
    print(f"  비용: Claude ${s['usd']:.3f} (턴당 ${s['usd_per_turn']:.4f}) · HCX 턴당 {s['hcx_tokens_per_turn']:.0f}토큰")
    by_case = {}
    for r in recs:
        by_case.setdefault(r["case"], []).append(r)
    bad = [(cid, rs) for cid, rs in by_case.items() if not all(r["pass"] for r in rs)]
    for cid, rs in bad:
        for r in rs:
            if r["pass"]:
                continue
            why = [k for k, v in r["checks"].items() if not v]
            why += ["밖 " + "/".join(r["outside"])] if r.get("outside") else []
            why += ["되풀이"] if r.get("repeat") else []
            why += ["평가 말"] if r.get("eval_word") else []
            print(f"  · {cid} 턴{r['turn']} 「{r['said'][:30]}」 → {(r.get('heard') or {}).get('kind')}"
                  f" · 걸림 {', '.join(why) or '-'}" + (f" · 폴백 {r['fallback']}" if r.get("fallback") else "")
                  + (f" · 반응 {r.get('reaction')!r}" if r.get("reaction") else ""))


# ── 실행 ──────────────────────────────────────────────────────────────
def run(doc, cases, runs, writers):
    """{writer: (summary, recs)}"""
    import ai
    os.environ["VCC_TELL_CHAT"] = "1"   # 이 프로세스에서만
    install(CTX.get("fake"))
    results = {}
    saved_model = ai.CLAUDE_MODEL
    try:
        for w in writers:
            CTX["writer"] = w
            ai.CLAUDE_MODEL = WRITER_IDS["haiku"] if w == "haiku" else saved_model
            recs = []
            for r in range(1, runs + 1):
                for i, c in enumerate(cases, 1):
                    for t in run_case(doc, c, f"H09{i:02d}"):
                        t.update(run=r, writer=w)
                        recs.append(t)
                print(f"  [{w}] {r}/{runs}회 끝", flush=True)
            results[w] = (summarize(recs), recs)
    finally:
        ai.CLAUDE_MODEL = saved_model
        CTX["writer"] = None
    return results


def main(argv=None):
    ap = argparse.ArgumentParser(description="작업 112 대화형 들려주기 측정(30상황 × N회)")
    ap.add_argument("--dry", action="store_true", help="AI 0회: 상황 검사 + 호출 수·예상 비용")
    ap.add_argument("--yes", action="store_true", help="실제 AI 호출(이 값이 없으면 예상만 보여 주고 멈춤)")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--writer", default="sonnet", help="sonnet | haiku | opus (쉼표로 여럿)")
    ap.add_argument("--only", help="상황 id 쉼표 목록(예: S09,S30)")
    ap.add_argument("--cases", default=str(CASES_FILE))
    ap.add_argument("--json", help="턴 기록·요약을 이 파일로")
    a = ap.parse_args(argv)
    writers = [w.strip() for w in a.writer.split(",") if w.strip()]
    if any(w not in WRITERS for w in writers):
        ap.error(f"--writer는 {' | '.join(WRITERS)}")
    doc = load_cases(a.cases)
    probs = validate(doc)
    if probs:
        print("상황 파일 문제:\n  " + "\n  ".join(probs))
        return 1
    cases = select(doc, a.only)
    if not cases:
        print("고른 상황 없음")
        return 1
    print(f"상황 파일 검사 통과 ({len(doc['상황'])}개, 기준 {len(CRITERIA)}개)")
    est = estimate(cases, a.runs, writers)
    print_estimate(est)
    if a.dry:
        print("(--dry: AI 호출 0회)")
        return 0
    if not a.yes and not CTX.get("fake"):
        print("실제로 부르려면 --yes를 붙이세요(하루 $20 기준 — 오늘 누적은 /token).")
        return 2
    if not CTX.get("fake"):
        import ai  # noqa: F401  (.env 읽기)
        missing = [k for k in ("CLOVA_KEY", "ANTHROPIC_API_KEY") if not os.environ.get(k)]
        if missing:
            print(f"키 없음: {', '.join(missing)} — 미리 PC(.env)에서만 돌린다")
            return 1
    results = run(doc, cases, a.runs, writers)
    for w, (s, recs) in results.items():
        print_summary(w, s, recs)
    if len(results) > 1:
        print("\n=== 쓰기 모델 비교")
        print("  " + " | ".join(["모델"] + [c[0] for c in CRITERIA] + ["턴 평균 ms", "턴당 $"]))
        for w, (s, _) in results.items():
            print("  " + " | ".join([w] + [_fmt(c["value"], c["bar"]) + ("" if c["ok"] else "✗") for c in s["criteria"]]
                                    + [f"{s['ms_avg']:.0f}", f"{s['usd_per_turn']:.4f}"]))
    if a.json:
        out = Path(a.json)
        out.write_text(json.dumps({"estimate": est, "results": {w: {"summary": s, "turns": recs}
                                                                for w, (s, recs) in results.items()}},
                                  ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"기록: {out}")
    return 0 if all(s["all_ok"] for s, _ in results.values()) else 3


if __name__ == "__main__":
    sys.exit(main())
