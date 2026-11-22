# interview.py — 들려주기(선배 인터뷰) 서버 함수 (작업 21·74, 작성: 미리)
#
# 기준: docs/spec-v1.md 4장 interviewNext·summarizeInterview · docs/HCX-원칙-v2.md · 작업내역 21번 세부
#
# interviewNext(program, answers) — 다음 질문 하나
#   ① 코드: 질문함(questions.json)에서 같은 프로그램의 hold 질문을 최근순 최대 3개 먼저 묻는다(작업 74).
#        본인이 한 질문·이미 answered·이번 인터뷰에서 답했거나 건너뛴 질문은 뺀다.
#   ② 코드: 그 뒤 근거(evidence.json)가 적은 칸 순, 「배운점」은 마지막.
#   ③ AI(충분판정, HCX): 칸의 첫 답이 들어오면 충분한지 본다. 부족하면
#      AI(꼬리질문, HCX): 꼬리 질문 하나 — 칸당 1회. 형식이 틀리거나 답에 없는 숫자·고유명사가 있으면 버리고 다음 칸.
#
# summarizeInterview(program, transcript) — 요약 2종 + 내 경험노트 저장
#   ① AI(요약, Sonnet): 칸(후배 질문은 질문마다)별로 답 원문 → 해요체 문장 1~3개 {"문장":[...]}
#   ② 코드: 사후 검증 — 답 원문에 없는 숫자·영문·수량·고유명사가 있는 문장은 버린다.
#      다 버려지거나 AI가 실패하면 답 원문 문장을 그대로 쓴다(fallback: true).
#   ③ AI(일치검사, Opus): 남은 문장마다 원문과 대조 → match. 호출이 실패하면 match: false(「원문과 다를 수 있어요」).
#   ③′ AI(1인칭, Sonnet): 공개 초안 문장을 한 번에 1인칭 해라체로 → 내 경험노트. 검증에 걸린 문장은 해요체 그대로.
#   ④ 코드: identify.mark로 본인 식별 문장 표시 → runtime_fns.save_my_note로 저장(saved, myNoteId).
#
# AI는 ai.py의 callAI로만 부른다. 프롬프트 원문은 docs/prompts/충분판정·꼬리질문·요약·일치검사.txt(작업 53 검증본).
import json
import re
from concurrent.futures import ThreadPoolExecutor

import askboo
import identify
import store
from ai import callAI, load_prompt
from runtime_fns import save_my_note

QUESTION_SECTION = "후배 질문"
LAST_SECTION = "배운점"
MAX_JUNIOR = 3          # 먼저 묻는 질문함 질문 수 (spec 4장)
MAX_ANSWER = 1000       # 답 하나 글자 수 상한
MAX_TRANSCRIPT = 30     # 요약에 받는 답 수 상한
WORKERS = 6             # 요약·일치검사를 동시에 부르는 수

FRAMES = askboo._json("frames.json", {})
KIND_BY_FIELD = {"국제교류": "교환", "현장실습": "인턴", "비교과": "비교과"}

# 칸별 첫 질문. {p}는 프로그램 짧은 이름. frames.json에 칸이 늘면 여기에 더한다(없으면 GENERIC).
BASE_QUESTIONS = {
    "지원": "{p} 파견은 언제부터 어떻게 준비하셨어요?",
    "학점": "{p}에서 들은 수업과 학점 인정은 어땠어요?",
    "비용": "{p}에서 한 달 생활비는 얼마나 들었어요?",
    "생활": "기숙사나 현지 생활은 어땠어요?",
    "팁": "후배가 출국 전에 꼭 알았으면 하는 팁이 있나요?",
    "지원동기": "{p}에 지원한 이유는 무엇이었어요?",
    "업무내용": "{p}에서 주로 어떤 일을 하셨어요?",
    "지원·선발": "지원부터 선발까지 어떤 순서로 진행됐어요?",
    "근무조건": "근무 시간이나 근무 조건은 어땠어요?",
    "활동내용": "{p}에서는 어떤 활동을 했어요?",
    "배운점": "이 경험에서 배운 점을 한 문장으로 들려주세요.",
}
GENERIC = "{s}에 대해 기억나는 경험을 들려주세요."


# ── 공통 ──────────────────────────────────────────────────────────────
def kind_of(program):
    field = askboo.PROGRAMS.get(program, {}).get("분야")
    return KIND_BY_FIELD.get(field, "교환")


def frame_of(program):
    return FRAMES.get(kind_of(program)) or FRAMES.get("교환") or {"칸": [], "인터뷰로만": []}


def short_name(program):
    aliases = askboo.PROGRAMS.get(program, {}).get("별칭") or []
    return aliases[0] if aliases else program


def _call(작업명, content):
    system, shots = load_prompt(작업명)
    return callAI(작업명, shots + [{"role": "user", "content": content}], system=system)


def outside_source(text, source):
    """답 원문에 없는 숫자·영문·수량·고유명사(새 낱말은 허용). 빈 목록이면 통과. AI를 쓰지 않는다."""
    problems = askboo.verify(text, source)
    return [p for p in problems if p.split(" ")[0] in ("숫자", "영문", "수량", "고유명사")]


def _clean_answers(items):
    out = []
    for a in items or []:
        if not isinstance(a, dict):
            continue
        a = dict(a)
        if isinstance(a.get("answer"), str):
            a["answer"] = a["answer"].strip()[:MAX_ANSWER]
        out.append(a)
    return out


# ── interviewNext ─────────────────────────────────────────────────────
def interviewNext(me, payload):
    program = (payload.get("program") or "").strip()
    if not program:
        return {"error": "들려줄 경험을 먼저 골라 주세요"}
    answers = _clean_answers(payload.get("answers"))
    frame = frame_of(program)
    sections = [s for s in frame["칸"] if s != QUESTION_SECTION]
    total = len(frame["칸"])
    answered = {a.get("section") for a in answers if not a.get("skipped") and a.get("answer")}
    filled = len([s for s in sections if s in answered]) + (1 if QUESTION_SECTION in answered else 0)
    progress = {"filled": filled, "total": total}

    # ① 질문함의 후배 질문 먼저
    juniors = junior_questions(me, program)
    seen_q = {a.get("questionId") for a in answers if a.get("questionId")}
    seen_text = {askboo._norm(a.get("question")) for a in answers if a.get("section") == QUESTION_SECTION}
    waiting = [q for q in juniors if q["id"] not in seen_q and askboo._norm(q["질문"]) not in seen_text]
    if waiting:
        q = waiting[0]
        return {"done": False, "section": QUESTION_SECTION, "questionId": q["id"], "asked": q["질문"],
                "question": f"후배가 이렇게 물었어요 — \"{q['질문']}\" 경험이 있으면 들려주세요.",
                "progress": progress, "pendingQuestions": len(waiting)}

    # ③ 방금 들어온 답이 그 칸의 첫 답이면 충분한지 보고, 부족하면 꼬리 질문(칸당 1회)
    last = answers[-1] if answers else None
    if last and not last.get("skipped") and last.get("answer") and last.get("section") in sections:
        same = [a for a in answers if a.get("section") == last["section"] and not a.get("skipped")]
        if len(same) == 1:
            follow = follow_up(last["section"], last.get("question", ""), last["answer"])
            if follow:
                return {"done": False, "section": last["section"], "question": follow,
                        "followUp": True, "progress": progress, "pendingQuestions": 0}

    # ② 근거가 적은 칸 순, 배운점은 마지막
    for s in section_order(program, sections):
        if s not in answered:
            step = {"done": False, "section": s, "question": base_question(program, s),
                    "progress": progress, "pendingQuestions": 0}
            examples = (frame.get("예시") or {}).get(s)   # P1-여건(작업 84): frames.json에 있으면
            if isinstance(examples, list) and examples:
                step["examples"] = [str(x) for x in examples[:3]]
            return step
    return {"done": True, "progress": progress}


def junior_questions(me, program):
    """같은 프로그램의 미답변(hold) 질문, 최근순 최대 3개. 본인이 한 질문은 뺀다."""
    with store.lock():
        rows = list(store.load("questions", []))
    rows = [q for q in rows if q.get("프로그램명") == program and q.get("status") == "hold"
            and q.get("colreg_no") != me and (q.get("질문") or "").strip()]
    rows.sort(key=lambda q: q.get("at") or "", reverse=True)
    return rows[:MAX_JUNIOR]


def section_order(program, sections):
    count = {}
    for e in askboo.EVIDENCE.get(program, []):
        count[e.get("칸")] = count.get(e.get("칸"), 0) + 1
    body = [s for s in sections if s != LAST_SECTION]
    body.sort(key=lambda s: count.get(s, 0))   # 안정 정렬: 같은 수면 frames.json 순서
    return body + ([LAST_SECTION] if LAST_SECTION in sections else [])


def base_question(program, section):
    return BASE_QUESTIONS.get(section, GENERIC).format(p=short_name(program), s=section)


def follow_up(section, question, answer):
    """답이 부족하면 꼬리 질문 글, 충분하거나 AI가 실패하면 None(다음 칸으로)."""
    r = _call("충분판정", f"칸: {section}\n질문: {question}\n답: {answer}\n출력:")
    j = r.get("json")
    if not r["ok"] or not isinstance(j, dict) or j.get("충분") is not False:
        return None   # 판정 실패는 '충분'으로 보고 넘어간다(인터뷰가 막히지 않게)
    r = _call("꼬리질문", f"칸: {section}\n처음 질문: {question}\n답: {answer}\n출력:")
    j = r.get("json")
    q = j.get("질문") if r["ok"] and isinstance(j, dict) else None
    if not isinstance(q, str):
        return None
    q = q.strip()
    if not q or len(q) > 60 or not re.search(r"(요|까)\??$", q) or outside_source(q, question + " " + answer):
        return None
    return q


# ── summarizeInterview ────────────────────────────────────────────────
def summarizeInterview(me, payload):
    program = (payload.get("program") or "").strip()
    if not program:
        return {"error": "들려줄 경험을 먼저 골라 주세요"}
    transcript = [a for a in _clean_answers(payload.get("transcript"))
                  if a.get("answer") and not a.get("skipped")][:MAX_TRANSCRIPT]
    if not transcript:
        return {"error": "요약할 답이 아직 없어요. 질문에 하나 이상 답해 주세요"}

    groups = group_answers(me, program, transcript)
    with ThreadPoolExecutor(WORKERS) as pool:
        summaries = list(pool.map(lambda g: summarize_group(g), groups))
    pairs = [(g, ln) for g, lines in zip(groups, summaries) for ln in lines]
    with ThreadPoolExecutor(WORKERS) as pool:
        mine_future = pool.submit(first_person, [ln["text"] for _, ln in pairs])   # 일치검사와 동시에
        matches = list(pool.map(lambda p: p[1].get("fallback") or match_check(p[0]["source"], p[1]["text"]), pairs))
        mine_of = iter(mine_future.result())

    draft_id = store.next_id("D")
    n = draft_id.split("-")[-1].lstrip("0") or "0"
    my_sections, pub_sections, k = [], [], 0
    match_of = iter(matches)   # pairs와 같은 순서(칸 순 → 문장 순)
    for g, lines in zip(groups, summaries):
        if not lines:
            continue
        extra = {"answersQuestionId": g["questionId"], "asked": g["asked"]} if g.get("questionId") else {}
        my_lines, pub_lines = [], []
        for ln in lines:
            k += 1
            ok = next(match_of)
            pub = {"lineId": f"L-D{n}-{k}", **extra, "text": ln["text"], "match": bool(ok)}
            if ln.get("fallback"):
                pub["fallback"] = True
            pub_lines.append(pub)
            my_lines.append({**extra, "text": next(mine_of)})
        _append(my_sections, g["section"], my_lines)
        _append(pub_sections, g["section"], pub_lines)

    public_draft = identify.mark({"sections": pub_sections})
    my_note = {"sections": my_sections}
    try:
        my_note_id = save_my_note(me, program, draft_id, my_note, public_draft)
        saved = True
    except OSError:
        my_note_id, saved = None, False
    return {"draftId": draft_id, "program": program, "saved": saved, "myNoteId": my_note_id,
            "myNote": my_note, "publicDraft": public_draft}


def _append(sections, name, lines):
    for s in sections:
        if s["name"] == name:
            s["lines"] += lines
            return
    sections.append({"name": name, "lines": lines})


def group_answers(me, program, transcript):
    """칸별로 답을 모은다(첫 답 + 꼬리 답). 후배 질문은 질문마다 따로. 순서는 frames.json 칸 순서."""
    order = frame_of(program)["칸"]
    by_key, keys = {}, []
    for a in transcript:
        section = a.get("section") or "기타"
        qid = None
        if section == QUESTION_SECTION:
            qid = a.get("questionId") or _find_question_id(program, a.get("question"))
        key = (section, qid or (a.get("question") if section == QUESTION_SECTION else None))
        if key not in by_key:
            keys.append(key)
            by_key[key] = {"section": section, "questionId": qid, "asked": a.get("question", ""), "answers": []}
        by_key[key]["answers"].append(a["answer"])
    keys.sort(key=lambda k: order.index(k[0]) if k[0] in order else len(order))
    groups = [by_key[k] for k in keys]
    for g in groups:
        g["source"] = " ".join(g["answers"])
    return groups


def _find_question_id(program, asked):
    """화면이 questionId를 빠뜨려도 질문 원문으로 질문함에서 찾는다."""
    asked = askboo._norm(asked)
    if not asked:
        return None
    with store.lock():
        for q in reversed(store.load("questions", [])):
            if q.get("프로그램명") == program and askboo._norm(q.get("질문")) == asked:
                return q.get("id")
    return None


def summarize_group(g):
    """돌려주는 값: [{"text", "fallback"?}] — 검증을 통과한 해요체 문장, 없으면 답 원문 문장."""
    r = _call("요약", f"칸: {g['section']}\n답: {g['source']}\n출력:")
    j = r.get("json")
    lines = []
    if r["ok"] and isinstance(j, dict) and isinstance(j.get("문장"), list):
        for s in j["문장"][:3]:
            if isinstance(s, str) and s.strip() and not outside_source(s.strip(), g["source"]):
                lines.append({"text": s.strip()})
    if lines:
        return lines
    src = [askboo.clean_source(s) for s in askboo.split_sentences(g["source"])]
    return [{"text": s, "fallback": True} for s in src if s and not too_thin(s)][:3]


# 요약이 실패해 원문을 그대로 쓸 때, 정보가 없는 짧은 답(「생각보다 많이 들었어요.」)은 해봤노트에 올리지 않는다
# (원우 11/22 제보 → 미리 결정: 빼기). 숫자가 있으면 짧아도 정보로 본다(「비자는 2주 걸렸어요.」).
MIN_FALLBACK_CHARS = 12


def too_thin(s):
    body = re.sub(r"[\s\W_]+", "", s or "")
    return len(body) < MIN_FALLBACK_CHARS and not re.search(r"\d", body)


PLAIN_END = re.compile(r"다[.!?~]*$")   # 해라체로 끝나야 한다


def first_person(texts):
    """공개 초안 문장(해요체) → 내 경험노트 문장(1인칭 해라체). 한 번에 부른다.
    형식이 틀리거나 원래 문장에 없는 숫자·영문·수량·고유명사가 생기면 그 문장만 해요체 그대로 둔다."""
    if not texts:
        return []
    numbered = "\n".join(f"{i}. {t}" for i, t in enumerate(texts, 1))
    r = _call("1인칭", f"{numbered}\n출력:")
    j = r.get("json") if r["ok"] else None
    out = []
    for i, t in enumerate(texts, 1):
        v = j.get(str(i)) if isinstance(j, dict) else None
        v = v.strip() if isinstance(v, str) else ""
        ok = v and PLAIN_END.search(v) and not outside_source(v, t) and len(v) <= len(t) + 15
        out.append(v if ok else t)
    return out


def match_check(source, sentence):
    r = _call("일치검사", f"원문: {source}\n요약: {sentence}\n출력:")
    j = r.get("json")
    return bool(r["ok"] and isinstance(j, dict) and j.get("일치") is True)
