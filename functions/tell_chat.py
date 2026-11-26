# tell_chat.py — 들려주기 대화형 인터뷰 [작업 110 초안, 작성: 미리]
#
# 플래그 VCC_TELL_CHAT=1일 때만 interview.py가 부른다. 기본(0)은 지금 그대로 — 이 파일의 어떤 함수도 불리지 않는다.
# 왜: 들려주기가 고정 질문만 내고, 선배의 되묻는 말·딴 얘기도 답으로 저장했다(11/26 진단). 팀 결정(11/27) 전 초안.
#
# 한 턴(interviewNext 한 번) — 선배가 새 말을 보냈을 때:
#   ① AI(말판정, HCX): 방금 말 → 종류 6종(답·부족·되물음·딴얘기·모름·그만) + 궁금(경험·프로그램에 대해 알고 싶은 것).
#   ② 코드: 무엇을 물을지는 지금 코드(interview._next_step, 충분판정·꼬리질문은 끔)가 정한다 — 후배 질문 먼저·칸 진행·끝 조건 그대로.
#        「답」만 answers로 센다(다른 칸 이야기면 ③의 칸으로 옮김). 부족·되물음·딴얘기는 없던 말로 치고 같은 질문을 다시 묻는다
#        (같은 질문에 MAX_REASK번 넘게 이어지면 넘긴다). 모름은 그 질문을 넘긴다(후배 질문은 건너뛰기와 같게 hold로 남음).
#        그만이면 done(stopped).
#   ③ AI(대화쓰기, Sonnet): 이번 대화 전체 + 지난 노트 문장 + 남은 칸·후배 질문·깊이 질문 후보 + ②의 다음 질문
#        → {반응, 칸, 더묻기, 질문}. 더묻기는 그 칸(후배 질문은 그 질문)의 첫 답일 때 한 번만 받는다(지금 꼬리 질문과 같은 횟수).
#   ④ 코드 검증: 대화·후보에 없는 숫자·영문·고유명사, 길이, 해요체, 이미 물은 질문. askboo.verify의 「수량」「새 낱말」은
#        보지 않는다(11/26 시험에서 「한 장면」을 수량으로 잘못 잡음 — 반응·질문은 새 말을 써야 하는 글). 걸린 값만 버린다:
#        반응 → 고정 문구(FALLBACK_REACTION), 질문 → ②의 질문 원문, 칸 → 질문의 칸, 더묻기 → ②의 다음 질문.
#   ⑤ 판정은 서버에 남긴다(store tellChat). 화면은 answers를 통째로 다시 보내므로 다음 턴·요약에서 같은 말을 같은 종류로 본다.
#        말·질문 원문은 남기지 않고 해시만 키로 쓴다(마지막 응답 하나만 그대로 — 같은 answers로 다시 부를 때 AI를 다시 안 부르게).
#        다듬은 질문 → 원래 질문(깊이 질문 번호·예시 칩·요약 맥락이 그대로 맞게).
#        7일 지나면 지우고, 요약(summarizeInterview)이 끝나면 지운다. 화면이 heard.kind를 answers의 kind로 돌려보내면 그 값이 먼저다(제안).
#   ⑥ 궁금 → askboo._save(#369 관문: 연락처·학번·메일·비방)를 지나 내 질문함(hold, 지금 들려주는 프로그램)에 담는다.
#        질문의 뜻·왜 묻는지 되묻는 말은 담지 않는다(말판정이 궁금 null). 궁금 글이 선배 말 그대로가 아니면 말 전체(짧을 때만).
# 실패: 말판정이 실패하면 지금처럼 답으로 보고 고정 질문(반응 없음). 대화쓰기가 실패하면 고정 질문 + 고정 반응.
# 응답(제안 — spec·화면 미반영): 지금 필드 그대로 + reaction(반응 글) · heard {kind, section}(방금 말을 어떻게 봤는지)
#        · heldQuestionId(질문함에 담은 질문) · stopped(그만). 화면이 reaction을 질문 말풍선 앞에 그리면 된다.
import hashlib
import os
import re

import askboo
import store

FLAG = "VCC_TELL_CHAT"
STORE = "tellChat"
KINDS = ("답", "부족", "되물음", "딴얘기", "모름", "그만")
REASK_KINDS = {"부족", "되물음", "딴얘기"}   # 없던 말로 치고 같은 질문을 다시
MAX_REASK = 2          # 같은 질문을 다시 묻는 횟수 상한. 넘으면 모름처럼 넘긴다(인터뷰가 한 질문에 갇히지 않게)
MAX_REACTION = 120     # 반응 글자 수
MAX_SENTENCES = 3      # 반응 문장 수(프롬프트는 1~2, 검증은 느슨하게)
MAX_QUESTION = 60      # 질문 글자 수(꼬리질문 검증과 같음)
MAX_CURIOUS = 120      # 궁금 글이 말 그대로가 아닐 때 말 전체를 담는 상한
MAX_MEMORY = 80        # 사람·프로그램마다 남기는 판정 수
KEEP_DAYS = 7          # 인터뷰 초안(runtime_fns.DRAFT_DAYS)과 같은 보관기간
HISTORY_TURNS = 12     # 대화쓰기에 넘기는 지난 턴 수
MAX_TURN_CHARS = 300   # 대화쓰기에 넘기는 말 하나 글자 수
PRIOR_LINES = 8        # 대화쓰기에 넘기는 지난 노트 문장 수
ALLOW = "해봤노트 후배 선배 BOO 인터뷰 노트 경험 질문 이야기"   # 반응·질문에 써도 되는 말(검증 원문에 더함)

STOP_TEXT = "알겠어요. 들려주셔서 고마워요. 아래 AI 요약을 누르면 지금까지 이야기가 정리돼요."
HELD_TEXT = "궁금하신 점은 내 질문함에 담아 두었어요."
FALLBACK_REACTION = {   # 대화쓰기가 실패하거나 반응이 검증에 걸렸을 때. 답은 반응 없이 다음 질문만
    "부족": "괜찮아요. 떠오르는 장면 하나만 들려주셔도 돼요.",
    "되물음": "편하게 떠오르는 대로 들려주시면 돼요.",
    "딴얘기": "인터뷰로 돌아와서 이어서 여쭤볼게요.",
    "모름": "괜찮아요. 다음 질문으로 넘어갈게요.",
}
_END = re.compile(r"(요|죠|까)[.!?~]*$")
_ASK_END = re.compile(r"(요|까)\?$|주세요\.?$")   # 「…들려주세요.」도 질문으로(기본 질문 「배운 점을 … 들려주세요.」와 같은 끝맺음)
_FEATURE = re.compile(r"질문함|요약|저장")   # 화면 기능을 말하는 반응은 버린다(담았는지·정리되는지는 코드가 붙인다)
# ⑥ 질문의 뜻·왜 묻는지·예를 들어 달라는 말은 궁금으로 담지 않는다 — 말판정이 궁금을 붙여도 코드가 한 번 더 거른다
# (실제 호출 11/26: 「각오라는 게 무슨 뜻이에요? 예를 들어 주세요.」를 HCX가 궁금으로 냄)
_META = re.compile(r"뜻|무슨\s*(말|의미)|의미(가|를|예요|에요)|왜\s*(물어|묻|여쭤)|어디에\s*(쓰|써)|예를\s*들|예시")


def enabled():
    """부를 때마다 읽는다(시험·평가 스크립트가 환경변수로 두 길을 바꿔 돌린다)."""
    return os.environ.get(FLAG, "0").strip() == "1"


# ── 기록(store tellChat) ──────────────────────────────────────────────
def _qn(s):
    """질문 대조용: 띄어쓰기·문장부호를 뺀다."""
    return re.sub(r"[\s.,!?~…·\"'「」]+", "", s or "").lower()


def _h(*parts):
    return hashlib.sha256("\x1f".join(_qn(p) for p in parts).encode("utf-8")).hexdigest()[:16]


def _said_key(a):
    return _h(a.get("question"), a.get("answer"))


def _turn_key(items):
    return _h(*[f"{a.get('question')}|{a.get('answer')}|{bool(a.get('skipped'))}" for a in items])


def _key(me, program):
    return f"{me}|{program}"


def load(me, program):
    with store.lock():
        rec = store.load(STORE, {}).get(_key(me, program))
    rec = rec if isinstance(rec, dict) and rec.get("owner") == me else {}
    return {"said": dict(rec.get("said") or {}), "asked": dict(rec.get("asked") or {}), "last": rec.get("last")}


def _cap(d):
    return dict(list(d.items())[-MAX_MEMORY:])


def save(me, program, mem):
    from runtime_fns import _days_since, now
    with store.lock():
        rows = store.load(STORE, {})
        for k in [k for k, v in rows.items() if _days_since(v.get("at")) >= KEEP_DAYS or not v.get("at")]:
            del rows[k]
        rows[_key(me, program)] = {"owner": me, "program": program, "at": now(),
                                   "said": _cap(mem["said"]), "asked": _cap(mem["asked"]), "last": mem.get("last")}
        store.save(STORE)


def drop(me, program):
    with store.lock():
        rows = store.load(STORE, {})
        if rows.pop(_key(me, program), None) is not None:
            store.save(STORE)


def _resolve(items, mem):
    """화면이 보낸 answers → (센 answers, 넘긴 칸, 질문별 다시 물은 수).
    답만 남기고(다른 칸 이야기면 그 칸으로), 모름은 건너뛴 것으로, 부족·되물음·딴얘기·그만은 뺀다. 다듬은 질문은 원래 질문으로."""
    import interview as iv
    out, passed, reask = [], set(), {}
    for a in items:
        a = dict(a)
        said = mem["said"].get(_said_key(a)) if a.get("answer") and not a.get("skipped") else None
        kind = a.pop("kind", None)
        kind = kind if kind in KINDS else (said or {}).get("k")
        orig = mem["asked"].get(_h(a.get("question")))
        if orig:
            a["question"] = orig["q"]
        if kind in REASK_KINDS:
            reask[_h(a.get("question"))] = reask.get(_h(a.get("question")), 0) + 1
            continue
        if kind == "그만":
            continue
        if kind == "모름":
            a.pop("answer", None)
            a["skipped"] = True
            if not iv.is_junior(a) and not iv.depth_id(a.get("question")) and a.get("section"):
                passed.add(a["section"])   # 기본 질문·배운점은 건너뛰기가 없어 칸으로 넘긴다(깊이·후배 질문은 skipped로 넘어감)
        elif said and said.get("s"):
            a["section"] = said["s"]
        out.append(a)
    return out, passed, reask


def for_summary(me, program, items):
    """summarizeInterview 입력에서 답만(다른 칸 이야기는 그 칸, 다듬은 질문은 원래 질문)."""
    out, _, _ = _resolve(items, load(me, program))
    return [a for a in out if not a.get("skipped")]


# ── 한 턴 ─────────────────────────────────────────────────────────────
def next_step(me, program, payload, prior, mine=None):
    import interview as iv
    items = iv._clean_answers(payload.get("answers"))
    mem = load(me, program)
    last = items[-1] if items else None
    fresh = bool(last and last.get("answer") and not last.get("skipped") and not iv.bare_stem(last["answer"]))
    turn = _turn_key(items)
    cached = mem.get("last") or {}
    if fresh and cached.get("key") == turn and isinstance(cached.get("step"), dict):
        return cached["step"]   # 같은 answers로 다시 부름(재시도·이어 하기) — AI를 다시 부르지 않는다

    if not fresh or _said_key(last) in mem["said"] or last.get("kind") in KINDS:
        answers, passed, _ = _resolve(items, mem)
        return iv._next_step(me, program, {**payload, "answers": answers}, prior, follow=False, passed=passed)

    prev, passed, reask = _resolve(items[:-1], mem)
    orig = mem["asked"].get(_h(last.get("question")))
    cur = {**last, "question": orig["q"]} if orig else dict(last)
    placed = iv._place_all(program, iv._clean_answers(prev + [cur]))[-1]
    junior = iv.is_junior(placed)
    section = placed.get("section")
    before = items[-2] if len(items) > 1 else None

    def plan_with(answers, passed_):
        return iv._next_step(me, program, {**payload, "answers": answers}, prior, follow=False, passed=passed_)

    judged = judge(section, last.get("question") or "", last["answer"], before)
    if not judged:   # 판정 실패 — 지금처럼 답으로 보고 고정 질문(기록하지 않음: 다음 턴에도 답으로 센다)
        return plan_with(prev + [cur], passed)
    kind, curious = judged
    held = hold_question(me, program, curious, last["answer"]) if curious else None
    eff = kind
    if kind in REASK_KINDS and reask.get(_h(cur.get("question")), 0) + 1 > MAX_REASK:
        eff = "모름"

    if eff == "그만":
        plan = plan_with(prev, passed)
        step = {"done": True, "stopped": True, "progress": plan.get("progress"), "covered": plan.get("covered", []),
                "reaction": " ".join(x for x in (STOP_TEXT, HELD_TEXT if held else None) if x),
                "heard": {"kind": "그만", "section": None}}
        return _remember(me, program, mem, last, turn, {"k": "그만"}, step, held)

    skipped = {**{k: v for k, v in cur.items() if k != "answer"}, "skipped": True}
    answers = prev + ([cur] if eff == "답" else [skipped] if eff == "모름" else [])
    if eff == "모름" and not junior and not iv.depth_id(cur.get("question")) and section:
        passed = passed | {section}
    plan = plan_with(answers, passed)

    content = _write_input(me, program, items, prev, cur, section, eff, _can_follow(program, answers, eff, cur), plan,
                           prior, mine)
    w = write(content)
    source = content + " " + ALLOW
    asked = {_qn(a.get("question")) for a in items} | {_qn(cur.get("question"))}

    moved = None
    if w and eff == "답" and not junior and w.get("칸") in iv.sections_of(program) and w.get("칸") != section:
        moved = w["칸"]
        answers = prev + [{**cur, "section": moved}]
        plan2 = plan_with(answers, passed)
        if (plan2.get("section"), plan2.get("question")) != (plan.get("section"), plan.get("question")) \
                and w.get("더묻기") is not True:
            w = {**w, "질문": None}   # 다음 질문이 바뀌었으면 다듬은 글은 버리고 새 질문 원문(꼬리 질문은 방금 답에 대한 것이라 그대로)
        plan = plan2
    final_sec = moved or section

    reaction = check_reaction(w.get("반응"), source) if w else None
    if not reaction:
        reaction = FALLBACK_REACTION.get(eff)
    q = check_question(w.get("질문"), source, asked) if w else None

    if w and w.get("더묻기") is True and q and _can_follow(program, answers, eff, {**cur, "section": final_sec}):
        step = _follow_step(plan, placed, final_sec, q, junior)
    else:
        step = dict(plan)
        if q and w.get("더묻기") is not True and not step.get("done") and not step.get("junior") \
                and not step.get("retry") and _qn(q) != _qn(step.get("question")):   # 꼬리 질문 글을 다른 질문 자리에 쓰지 않는다
            mem["asked"][_h(q)] = {"q": step["question"]}
            step["question"] = q
    text = " ".join(x for x in (reaction, HELD_TEXT if held else None) if x)
    if text:
        step["reaction"] = text
    step["heard"] = {"kind": eff, "section": final_sec if eff == "답" else None}
    rec = {"k": eff, **({"s": moved} if moved else {})}
    return _remember(me, program, mem, last, turn, rec, step, held)


def _remember(me, program, mem, last, turn, rec, step, held):
    if held:
        step["heldQuestionId"] = held
    mem["said"][_said_key(last)] = rec
    mem["last"] = {"key": turn, "step": step}
    try:
        save(me, program, mem)
    except (OSError, RuntimeError) as e:   # 기록 실패가 인터뷰를 막지 않게(다음 턴은 그 말을 답으로 센다)
        print(f"[vcc] tellChat 기록 실패: {type(e).__name__}")
    return step


def _can_follow(program, answers, eff, cur):
    """한 번 더 물어도 되나: 답이고, 그 칸(후배 질문은 그 질문)의 첫 답이고, 방금 질문이 꼬리 질문이 아닐 때."""
    import interview as iv
    if eff != "답" or (cur.get("question") or "").startswith(iv.JUNIOR_FOLLOW):
        return False
    placed = iv._place_all(program, iv._clean_answers(answers))
    me_ = placed[-1] if placed else {}
    live = [a for a in placed if a.get("answer") and not a.get("skipped")]
    if iv.is_junior(me_):
        return len([a for a in live if iv.is_junior(a) and iv._junior_key(a) == iv._junior_key(me_)]) == 1
    sec = cur.get("section")
    return len([a for a in live if a.get("section") == sec and not iv.is_junior(a)]) == 1


def _follow_step(plan, placed, section, q, junior):
    import interview as iv
    step = {"done": False, "section": section, "question": q, "followUp": True, "progress": plan.get("progress"),
            "pendingQuestions": plan.get("pendingQuestions", 0), "covered": plan.get("covered", [])}
    if junior:   # 지금 후배 질문 꼬리와 같은 모양(머리말 + questionId·asked) — _place_all이 같은 묶음으로 잇는다
        step["question"] = iv.JUNIOR_FOLLOW + q
        step["asked"] = placed.get("asked", "")
        if placed.get("questionId"):
            step["questionId"] = placed["questionId"]
    return step


# ── AI ①: 말판정(HCX) ────────────────────────────────────────────────
def judge(section, question, said, before=None):
    """(종류, 궁금 글 또는 None) 또는 None(호출 실패·형식 오류)."""
    import interview as iv
    ctx = f"BOO: {before.get('question') or ''} / 선배: {before.get('answer') or '(건너뜀)'}" if before else "(없음)"
    r = iv._call("말판정", f"칸: {section or '–'}\n질문: {question}\n앞 대화: {ctx}\n선배가 방금 한 말: {said}\n출력:")
    j = r.get("json") if r.get("ok") else None
    if not isinstance(j, dict) or j.get("종류") not in KINDS:
        return None
    c = j.get("궁금")
    c = c.strip() if isinstance(c, str) else ""
    return j["종류"], (c if c and c.lower() != "null" else None)


def hold_question(me, program, curious, said):
    """⑥ 궁금 → 내 질문함(hold). #369 관문(askboo._save)에 걸리거나 담을 글이 없으면 None."""
    text = curious.strip()
    if _META.search(text):
        return None
    if askboo._norm(text) not in askboo._norm(said):   # 선배 말 그대로가 아니면(AI가 바꿔 씀) 말 전체 — 짧을 때만
        text = said.strip() if len(said.strip()) <= MAX_CURIOUS else ""
    if not text:
        return None
    from demand import guess_section
    qid, blocked = askboo._save(me, text, program, guess_section(text, program), "hold", True)
    return None if blocked else qid


# ── AI ②: 대화쓰기(Sonnet) ───────────────────────────────────────────
def _turn_text(a):
    q = (a.get("question") or "").strip()
    sec = a.get("section")
    said = "(건너뜀)" if a.get("skipped") else (a.get("answer") or "")[:MAX_TURN_CHARS]
    return f"BOO: {f'[{sec}] ' if sec else ''}{q}\n선배: {said}"


def _write_input(me, program, items, prev, cur, section, eff, can_follow, plan, prior, mine):
    import interview as iv
    sections = iv.sections_of(program)
    placed = iv._place_all(program, iv._clean_answers(prev + ([cur] if eff == "답" else [])))
    answered = {a.get("section") for a in placed if a.get("answer") and not a.get("skipped")} | set(prior["sections"])
    lines = [f"[{s.get('name')}] {ln.get('text')}" for s in ((mine or {}).get("myNote") or {}).get("sections", [])
             for ln in s.get("lines") or [] if ln.get("text")][:PRIOR_LINES]
    asked_now = {iv.depth_id(a.get("question")) for a in prev + [cur]}
    cands = [f"[{s}] {q}" for i, s, q, _ in iv.depth_questions(program, sections, before=prior["depth"]) if i not in asked_now]
    seen = {a.get("questionId") for a in placed if a.get("questionId")} | set(prior["questionIds"])
    cands += [f"후배 질문 — \"{q['질문']}\"" for q in iv.junior_questions(me, program) if q["id"] not in seen]
    if plan.get("done"):
        nxt = "(끝)"
    elif plan.get("junior"):
        nxt = f"후배 질문 — \"{plan.get('asked', '')}\""
    else:
        nxt = f"[{plan.get('section')}] {plan.get('question')}"
    history = [_turn_text(a) for a in items[:-1]][-HISTORY_TURNS:]
    return (f"프로그램: {iv.short_name(program)} ({iv.kind_of(program)})\n"
            f"노트 칸: {', '.join(sections)}\n"
            f"아직 안 채운 칸: {', '.join(s for s in sections if s not in answered) or '(없음)'}\n"
            "지난 노트 문장:" + ("\n" + "\n".join("- " + x for x in lines) if lines else " (없음)") + "\n"
            "남은 질문 후보:" + ("\n" + "\n".join("- " + x for x in cands) if cands else " (없음)") + "\n"
            "지금까지의 대화:" + ("\n" + "\n".join(history) if history else " (없음)") + "\n"
            f"방금 BOO의 질문: {f'[{section}] ' if section else ''}{items[-1].get('question') or ''}\n"
            f"선배가 방금 한 말: {items[-1].get('answer', '')[:MAX_TURN_CHARS * 2]}\n"
            f"방금 말의 종류: {eff}\n"
            f"더 물을 수 있음: {'예' if can_follow else '아니오'}\n"
            f"다음 질문: {nxt}\n출력:")


def write(content):
    import interview as iv
    r = iv._call("대화쓰기", content)
    j = r.get("json") if r.get("ok") else None
    return j if isinstance(j, dict) else None


# ── 코드 검증 ─────────────────────────────────────────────────────────
def facts_outside(text, source):
    """대화·후보에 없는 숫자·영문·고유명사. 수량(「한 장면」)·새 낱말은 보지 않는다."""
    return [p for p in askboo.verify(text, source) if p.split(" ")[0] in ("숫자", "영문", "고유명사")]


def check_reaction(text, source):
    """해요체 1~3문장, 120자 안, 근거 밖 사실 없음, 화면 기능 말 없음. 통과하면 다듬은 글, 아니면 None."""
    if not isinstance(text, str):
        return None
    t = " ".join(text.split())
    if not t or len(t) > MAX_REACTION or _FEATURE.search(t):
        return None
    parts = [x for x in re.split(r"(?<=[.!?~])\s+", t) if x]
    if len(parts) > MAX_SENTENCES or not all(_END.search(x) for x in parts) or facts_outside(t, source):
        return None
    return t


def check_question(text, source, asked=()):
    """60자 안, 「요?/까?」로 끝남, 근거 밖 사실 없음, 이번 인터뷰에서 물은 질문이 아님. 통과하면 다듬은 글, 아니면 None."""
    if not isinstance(text, str):
        return None
    t = " ".join(text.split())
    if not t or len(t) > MAX_QUESTION or not _ASK_END.search(t) or facts_outside(t, source) or _qn(t) in asked:
        return None
    return t
