# demand.py — 선배 추천 열림 규칙과 「궁금한 것 정리하기」(수요 인터뷰) [11/22, 미리 결정]
#
# 규칙: 누구나 선배도 후배도 될 수 있지만, 닮은선배 추천을 받으려면 나도 하나를 내놓는다. 둘 중 하나면 열리고, 한 번 열리면 모든 프로그램이 열린다.
#   ① 경험 나눔(들려주기): 인터뷰에서 서로 다른 질문에 유효 답변 3개 이상 + 해봤노트에 1문장 이상 공유
#   ② 수요 제공(궁금한 것 정리하기): 유효 답변 3개(내 상황 · 가장 궁금한 것 · 얻고 싶은 것) + 선배·부서에 전하는 데 동의
#   유효 답변 = 직접 쓴 문장 10자 이상, 「몰라요」류가 아님, 쪽지 검사(학번·연락처·비방) 통과. 칩으로 고른 것은 답변으로 치지 않는다.
#
# 함수(AI 없음 — 칩과 규칙만):
#   demandNext(me, {state})   — 수요 인터뷰 다음 단계 하나. state는 화면이 그대로 들고 다니다 돌려준다(interviewNext처럼 서버는 기억하지 않음)
#   saveDemand(me, {state, consent}) — 다시 검사 → 질문함에 질문 저장(+ 보류 질문이면 그 행에 맥락만 붙임) → demands 기록 → 열림
#   recommend_status(me)      — getMe.recommend, recommendSeniors·sendMessage 잠금이 같이 쓴다
#   interest_labels(me)       — 쪽지 요청 카드(askerInfo)의 「관심」: 「교환학생·독일」 형식
import re

import notes
import store
from msg_check import check_message

NEED = 3                      # 양쪽 모두 유효 답변 3개
MIN_LEN = 10
MAX_LEN = 300
MAX_MORE = 2                  # 「더 궁금한 것」 최대 2개(가장 궁금한 것 포함 최대 3개)
LOCK_MESSAGE = "경험을 들려주거나 궁금한 것을 정리하면 선배 추천이 열려요"
QUESTION_SECTION = "후배 질문"

FIELDS = ["국제교류", "현장실습", "비교과"]
UNSURE = "잘 모르겠어요"
NOT_YET = "아직 정하지 않았어요"
FIELD_LABEL = {"국제교류": "교환학생", "현장실습": "현장실습", "비교과": "비교과"}   # 관심 라벨 앞부분(PRD 시연 「교환학생·독일」)
DETAIL_LABEL = {"1회성": "1회성 특강"}
KIND_BY_FIELD = {"국제교류": "교환", "현장실습": "인턴", "비교과": "비교과"}
EXPLORE = [   # 「잘 모르겠어요」 → BOO가 먼저 고민을 묻고 분야(·분류)를 정해 준다
    {"label": "외국에서 살아 보기", "field": "국제교류"},
    {"label": "일 경험 해 보기", "field": "현장실습"},
    {"label": "진로 찾기", "field": "비교과", "detail": "진로·취업 교육과정"},
    {"label": "공부 방법 찾기", "field": "비교과", "detail": "학습공동체·튜터링·멘토링"},
]
WHEN = ["이번 학기", "다음 학기", "1년 뒤", "아직 몰라요"]
JUNK = {"몰라요", "모르겠어요", "잘 모르겠어요", "없어요", "없음", "아무거나", "글쎄요", "그냥요", "딱히요", "ㅇㅇ", "네", "아니요"}

QUESTIONS = {
    "explore": "괜찮아요. 요즘 가장 고민인 게 뭐예요?",
    "field": "어떤 경험이 궁금해요?",
    "detail": {"국제교류": "어느 나라가 궁금해요?", "현장실습": "어떤 곳에서 일해 보고 싶어요?",
               "비교과": "어떤 종류의 프로그램이 궁금해요?"},
    "program": "궁금한 프로그램을 골라 주세요. 아직 정하지 않았어도 괜찮아요.",
    "section": "이 프로그램에서 무엇이 가장 궁금해요?",
    "sectionNotYet": "프로그램은 나중에 정해도 돼요. {i}에 대해 무엇이 가장 궁금해요?",   # 프로그램 「아직 정하지 않았어요」
    "when": "언제쯤 해 보려고 해요?",
    "situation": "지금 어느 정도 준비됐어요? 선배가 답할 때 참고할 수 있게 지금 상황을 적어 주세요.",
    "question": "{s}에 대해 무엇이 궁금해요? 선배에게 묻고 싶은 것을 한 문장으로 적어 주세요.",
    "hope": "이 경험이 나에게 무엇을 남겨 줬으면 좋겠어요?",
    "more": "더 궁금한 게 있으면 적어 주세요. 없으면 넘어가도 돼요.",
}
EXAMPLES = {
    "situation": ["2학년이고 어학 점수를 준비하고 있어요", "아직 아무것도 준비하지 못했어요"],
    "hope": ["외국어로 일상을 꾸려 본 자신감", "진로를 정할 실마리"],
}
RETRY = {"short": f"조금만 더 자세히 적어 주세요({MIN_LEN}자 이상).", "junk": "선배가 답할 수 있게 구체적으로 적어 주세요."}


# ---------- 유효 답변 ----------
def answer_problem(text):
    """유효 답변이면 None, 아니면 {"reason", "message"}. 쪽지 검사(학번·연락처·비방)를 그대로 쓴다."""
    t = (text or "").strip()
    if t.rstrip(".!?~ ") in JUNK:
        return {"reason": "junk", "message": RETRY["junk"]}
    if len(t) < MIN_LEN:
        return {"reason": "short", "message": RETRY["short"]}
    if len(set(re.sub(r"\s", "", t))) <= 2:            # ㅋㅋㅋㅋㅋㅋㅋㅋㅋㅋ 같은 반복
        return {"reason": "junk", "message": RETRY["junk"]}
    c = check_message(t)
    if not c.get("ok"):
        return {"reason": c.get("reason"), "message": c.get("message")}
    return None


def count_interview_answers(transcript):
    """들려주기 transcript에서 서로 다른 질문에 대한 유효 답변 수(건너뛴 것·짧은 답 제외)."""
    seen = set()
    for a in transcript or []:
        if not isinstance(a, dict) or a.get("skipped") or answer_problem(a.get("answer")):
            continue
        key = (a.get("section"), re.sub(r"\s+", "", a.get("question") or ""))
        seen.add(key)
    return len(seen)


# ---------- 열림 판단 ----------
def _shared_lines(mid):
    hidden = set(store.load("reported", {}))
    return sum(1 for r in store.load("noteLines", [])
               if r.get("myNoteId") == mid and "L-" + r.get("sourceId", "") not in hidden)


def recommend_status(me):
    talk_answered, talk_shared, talk_ok = 0, 0, False
    for mid, v in store.load("myNotes", {}).items():
        if v.get("owner") != me:
            continue
        answered, shared = v.get("answered", 0), _shared_lines(mid)
        if answered >= NEED and shared >= 1:
            talk_ok = True
        if (answered, shared) > (talk_answered, talk_shared):
            talk_answered, talk_shared = answered, shared
    ask_ok = any(d.get("owner") == me for d in store.load("demands", []))
    by = "talk" if talk_ok else "ask" if ask_ok else None
    return {"ready": bool(by), "by": by, "need": NEED,
            "talk": {"answered": talk_answered, "shared": talk_shared}, "ask": ask_ok}


def locked(me):
    """잠겼으면 응답에 붙일 dict, 열렸으면 None. 호출하는 쪽이 store.lock() 안에 있어도 된다(읽기만)."""
    st = recommend_status(me)
    return None if st["ready"] else {"locked": True, "message": LOCK_MESSAGE, "recommend": st}


# ---------- 관심 라벨 ----------
def label_of(field, detail=None):
    if field not in FIELD_LABEL:
        return None
    return FIELD_LABEL[field] + (f"·{DETAIL_LABEL.get(detail, detail)}" if detail else "")


def _program_field(program):
    info = notes.PROGRAMS.get(program) or {}
    return info.get("분야"), info.get("세부")


def interest_labels(me, limit=2):
    """최근 것부터: 수요 인터뷰 → 질문함(프로그램이 붙은 질문). 같은 라벨은 한 번."""
    out = []
    for d in reversed(store.load("demands", [])):
        if d.get("owner") == me:
            out.append(label_of(d.get("field"), d.get("detail")))
    for q in reversed(store.load("questions", [])):
        if q.get("colreg_no") == me and q.get("프로그램명"):
            out.append(label_of(*_program_field(q["프로그램명"])))
    seen = []
    for x in out:
        if x and x not in seen:
            seen.append(x)
    return seen[:limit]


def latest_when(me):
    for d in reversed(store.load("demands", [])):
        if d.get("owner") == me and d.get("when") and d["when"] != "아직 몰라요":
            return d["when"]
    return None


# ---------- 수요 인터뷰 ----------
# [11/26] 칩 순서: 우리 학과(crs_nm) 선배가 많이 다녀온 순 → 전교 선배 순 → (분류는 프로그램 수 순) → 이름.
#   학적(data/students.json)의 경험 열이 programs.json의 세부·프로그램명과 같은 값이다(원우 데이터, 11/26 대조 100%).
#   인원은 칩에 보여 주지 않는다(학과 + 나라 + 1명이면 사람이 짐작된다). 순서에만 쓴다.
HISTORY = {   # (분야, 단계) → 학적 열
    ("국제교류", "detail"): "파견국가", ("국제교류", "program"): "파견대학",
    ("현장실습", "detail"): "기관 유형(가상)", ("현장실습", "program"): "기관명(가상)",
    ("비교과", "detail"): "비교과 유형", ("비교과", "program"): "이수 비교과 프로그램",
}
_history = None


def _values(col, cell):
    """한 학생의 한 열 → 값 집합. 비교과는 「1회성(4), 진로·취업 교육과정(1)」·「A / B」처럼 여럿이 한 칸에 있다."""
    if not cell:
        return set()
    if col == "비교과 유형":
        return {re.sub(r"\(\d+\)$", "", x.strip()) for x in str(cell).split(", ") if x.strip()}
    if col == "이수 비교과 프로그램":
        return {x.strip() for x in str(cell).split(" / ") if x.strip()}
    return {str(cell).strip()}


def _seniors():
    """{(분야, 단계): {"all": {값: 인원}, "dept": {학과: {값: 인원}}}} — 처음 쓸 때 한 번 센다."""
    global _history
    if _history is None:
        _history = {k: {"all": {}, "dept": {}} for k in HISTORY}
        for s in notes._json("students.json", []):
            if not str(s.get("colreg_no", "")).startswith("H"):
                continue
            for k, col in HISTORY.items():
                dept = _history[k]["dept"].setdefault(s.get("crs_nm"), {})
                for v in _values(col, s.get(col)):
                    _history[k]["all"][v] = _history[k]["all"].get(v, 0) + 1
                    dept[v] = dept.get(v, 0) + 1
    return _history


def _ranked(me, field, step, names, tie=None):
    """우리 학과 인원 ↓ → 전교 인원 ↓ → tie(이름별 보조 수) ↓ → 이름. 학과가 없으면(직원 등) 전교 순."""
    from runtime_fns import student   # runtime_fns가 이 파일을 불러오므로 여기서
    h = _seniors().get((field, step), {"all": {}, "dept": {}})
    mine = h["dept"].get(student(me).get("crs_nm"), {}) if me else {}
    tie = tie or {}
    return sorted(names, key=lambda n: (-mine.get(n, 0), -h["all"].get(n, 0), -tie.get(n, 0), n))


def _details(me, field):
    counts = {}
    for p in notes.PROGRAMS.values():
        if p.get("분야") == field and p.get("세부"):
            counts[p["세부"]] = counts.get(p["세부"], 0) + 1
    return _ranked(me, field, "detail", counts, tie=counts)


def _programs(me, field, detail):
    return _ranked(me, field, "program", [p["프로그램명"] for p in notes.PROGRAMS.values()
                                          if p.get("분야") == field and (detail is None or p.get("세부") == detail)])


def _sections(field, program):
    kind = notes._kind(program) if program else KIND_BY_FIELD.get(field, "교환")
    return [s for s in (notes.FRAMES.get(kind) or {}).get("칸", []) if s != QUESTION_SECTION]


# [11/26 P11] 보류 질문에 칸이 없을 때 질문 문장으로 칸을 정한다(코드만, AI 없음).
#   askboo의 주제어 표(TOPICS_EXCHANGE → SECTION_BY_ITEM)를 읽기만 하고, 그 표가 일부러 빼 둔 보류 주제
#   (askboo 「아르바이트·취업 등은 보고서에 칸이 없으므로 hold」)만 여기서 덧붙인다. 시연 0:40 「학기 중 현지 인턴 병행」 → 생활
#   (들려주기 문단분류가 같은 질문에 고르는 칸과 같다 — test_interview.py).
HOLD_TOPICS_EXCHANGE = [(r"인턴|아르바이트|알바|일자리|병행|현지\s*취업", "생활")]


def guess_section(question, program):
    """질문 문장 → 그 프로그램 노트 틀(data/frames.json)의 칸. 못 정하면 None(지금처럼 칸을 묻는다)."""
    import askboo   # 근거를 읽는 모듈이라 쓸 때만 불러온다(runtime_fns가 demand를 부를 때마다 읽지 않게)
    text = question or ""
    names = _sections(None, program)
    if notes._kind(program) in ("교환", "파견"):
        found = [askboo.SECTION_BY_ITEM.get(n) for pat, nums in askboo.TOPICS_EXCHANGE if re.search(pat, text) for n in nums]
        found += [s for pat, s in HOLD_TOPICS_EXCHANGE if re.search(pat, text)]
    else:
        found = ["근무조건"] if askboo.INTERVIEW_ONLY_INTERN.search(text) else []
    return next((s for s in found if s in names), None)


def _from_question(me, qid):
    """물어보기에서 보류된 내 질문으로 시작: 프로그램·칸·질문 문장을 미리 채운다.
    [11/26 P11] 칸이 없거나 그 노트 틀 밖이면 질문 문장으로 정한다(guess_section). 못 정하면 칸을 묻는다."""
    q = next((q for q in store.load("questions", []) if q.get("id") == qid), None)
    if not q or q.get("colreg_no") != me:
        return None
    st = {"fromQuestionId": qid, "question": q.get("질문")}
    program = q.get("프로그램명") if q.get("프로그램명") in notes.PROGRAMS else None
    if program:
        st["field"], st["detail"] = _program_field(program)
        st["program"] = program
    section = q.get("칸")
    if program and section not in _sections(st["field"], program):
        section = guess_section(q.get("질문"), program) or section
    if section:
        st["section"] = section
    return st


def _clean_state(me, raw):
    s = dict(raw) if isinstance(raw, dict) else {}
    if s.get("fromQuestionId") and not s.get("_prefilled"):
        pre = _from_question(me, s["fromQuestionId"])
        if pre is None:
            return None
        s = {**pre, **s, "_prefilled": True}
    for k in ("situation", "question", "hope"):
        if isinstance(s.get(k), str):
            s[k] = s[k].strip()[:MAX_LEN]
    s["more"] = [m.strip()[:MAX_LEN] for m in (s.get("more") or []) if isinstance(m, str) and m.strip()][:MAX_MORE]
    return s


def valid_count(s):
    return sum(1 for k in ("situation", "question", "hope") if s.get(k) and not answer_problem(s[k])) + \
        sum(1 for m in s.get("more", []) if not answer_problem(m))


def _step(s, step, **kw):
    return {"done": False, "step": step, "state": s, "progress": {"answered": valid_count(s), "need": NEED}, **kw}


def next_step(s, me=None):
    """state → 다음 단계. 칩 단계(explore·field·detail·program·section·when) → 답변 단계(situation·question·hope) → more."""
    field = s.get("field")
    if field == UNSURE and not s.get("explored"):
        return _step(s, "explore", question=QUESTIONS["explore"], options=[e["label"] for e in EXPLORE])
    if field not in FIELDS:
        return _step(s, "field", question=QUESTIONS["field"], options=FIELDS + [UNSURE])
    if "detail" not in s:
        return _step(s, "detail", question=QUESTIONS["detail"][field],
                     options=[{"value": d, "label": DETAIL_LABEL.get(d, d)} for d in _details(me, field)] + [{"value": None, "label": NOT_YET}])
    if "program" not in s:
        return _step(s, "program", question=QUESTIONS["program"],
                     options=_programs(me, field, s.get("detail")) + [NOT_YET])
    sections = _sections(field, s.get("program"))
    if s.get("section") not in sections:
        q = QUESTIONS["section"] if s.get("program") else             QUESTIONS["sectionNotYet"].replace("{i}", label_of(field, s.get("detail")))
        return _step(s, "section", question=q, options=sections)
    if s.get("when") not in WHEN:
        return _step(s, "when", question=QUESTIONS["when"], options=WHEN)
    for key in ("situation", "question", "hope"):
        problem = answer_problem(s.get(key)) if s.get(key) else None
        if not s.get(key) or problem:
            q = QUESTIONS[key].replace("{s}", s["section"])
            return _step(s, key, question=q, examples=EXAMPLES.get(key, []),
                         **({"retry": problem["message"]} if s.get(key) and problem else {}))
    if s.get("moreDone"):      # 건너뛰면 잘못 쓴 「더 궁금한 것」은 버린다
        s["more"] = [m for m in s.get("more", []) if not answer_problem(m)]
    bad_more = next((m for m in s.get("more", []) if answer_problem(m)), None)
    if not s.get("moreDone") and (len(s.get("more", [])) < MAX_MORE or bad_more):
        return _step(s, "more", question=QUESTIONS["more"], canSkip=True,
                     **({"retry": answer_problem(bad_more)["message"]} if bad_more else {}))
    return {"done": True, "state": s, "progress": {"answered": valid_count(s), "need": NEED}, "summary": summary_of(s)}


def summary_of(s):
    return {"interest": label_of(s.get("field"), s.get("detail")), "program": s.get("program"),
            "section": s.get("section"), "when": s.get("when"), "situation": s.get("situation"),
            "questions": [s.get("question")] + s.get("more", []), "hope": s.get("hope")}


def _apply_pick(s):
    """화면이 보낸 칩 값 정리: 「잘 모르겠어요」 고민 칩 → 분야·분류, 「아직 정하지 않았어요」 → None."""
    if s.get("field") == UNSURE and s.get("explore"):
        e = next((e for e in EXPLORE if e["label"] == s["explore"]), None)
        if e:
            s["field"], s["explored"] = e["field"], True
            if e.get("detail"):
                s["detail"] = e["detail"]
    if s.get("detail") == NOT_YET:
        s["detail"] = None
    if s.get("program") == NOT_YET:
        s["program"] = None
    if s.get("program") and s["program"] not in notes.PROGRAMS:
        s.pop("program")
    return s


def _state(me, p):
    with store.lock():
        s = _clean_state(me, p.get("state"))
    return None if s is None else _apply_pick(s)


def demandNext(me, p):
    s = _state(me, p)
    if s is None:
        return {"error": "볼 수 없는 기록이에요"}
    return next_step(s, me)


def saveDemand(me, p):
    if not p.get("consent"):
        return {"error": "선배와 부서에 전하는 데 동의해 주세요"}
    s = _state(me, p)
    if s is None:
        return {"error": "볼 수 없는 기록이에요"}
    nxt = next_step(s, me)
    if not nxt.get("done") or valid_count(s) < NEED:
        return {"ok": False, "message": "아직 정리가 끝나지 않았어요", "next": nxt}

    from runtime_fns import add_question, now   # runtime_fns가 이 파일을 불러오므로 여기서
    before = recommend_status(me)["ready"]
    texts = [s["question"]] + [m for m in s.get("more", []) if not answer_problem(m)]
    qids = []
    with store.lock():
        rows = store.load("questions", [])
        src = next((q for q in rows if q.get("id") == s.get("fromQuestionId") and q.get("colreg_no") == me), None)
        if src:                      # 보류 질문에서 시작: 그 질문 행에 맥락만 붙인다(질문함 중복 없음)
            src["질문"] = s["question"]
            src.update({"칸": s["section"], "시기": s["when"], "수요": True})
            if s.get("program") and src.get("프로그램명") not in notes.PROGRAMS:   # [11/26 작업 117] 프로그램 없던 질문
                src["프로그램명"] = s["program"]                                  #   → 고른 프로그램(그 선배에게 전달됨)
            qids.append(src["id"])
            store.save("questions")
            texts = texts[1:]
    for t in texts:
        qid = add_question(me, t, s.get("program"), s["section"], status="hold")
        qids.append(qid)
    with store.lock():
        rows = store.load("questions", [])
        for q in rows:
            if q.get("id") in qids and not q.get("수요"):
                q.update({"시기": s["when"], "수요": True, "분야": s["field"], "세부": s.get("detail")})
        store.save("questions")
        did = store.next_id("R")
        store.load("demands", []).append({
            "id": did, "owner": me, "at": now(), "field": s["field"], "detail": s.get("detail"),
            "program": s.get("program"), "section": s["section"], "when": s["when"],
            "situation": s["situation"], "hope": s["hope"], "questionIds": qids,   # situation·hope 원문은 선배에게 보내지 않는다
        })
        store.save("demands")
        status = recommend_status(me)
    return {"ok": True, "demandId": did, "questionIds": qids, "recommend": status, "unlocked": status["ready"] and not before}


ROUTES = {"demandNext": demandNext, "saveDemand": saveDemand}
