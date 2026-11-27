# interview.py — 들려주기(선배 인터뷰) 서버 함수 (작업 21·74, 작성: 미리)
#
# 기준: docs/spec-v1.md 4장 interviewNext·summarizeInterview · docs/HCX-원칙-v2.md · 작업내역 21번 세부
#
# interviewNext(program, answers) — 다음 질문 하나
#   ① 코드: 질문함(questions.json)에서 같은 프로그램의 hold 질문을 최근순 최대 3개 먼저 묻는다(작업 74).
#        본인이 한 질문·이미 answered·이번 인터뷰에서 답했거나 건너뛴 질문은 뺀다.
#        [v2 작업 89] 「후배 질문」 칸은 없다. 응답은 junior: true, section = 그 질문의 칸(질문 행의 「칸」, 틀 밖이거나
#        없으면 AI(문단분류, Sonnet)가 틀 안의 칸 하나를 고르고, 그것도 안 되면 교환 「팁」·인턴·비교과 「배운점」).
#        답은 그 칸에 담기고 progress.filled에 센다. [11/26] 답이 부족하면(③과 같은 판정) 그 질문에 꼬리 질문 1회.
#        꼬리 답도 같은 questionId·칸에 담겨 처음 답과 함께 요약된다(후배에게 가는 답).
#   [v2 작업 90] 이어 쓰기: 같은 사람·같은 프로그램의 내 경험노트(myNotes.json)에 문장이 있는 칸은 답한 것으로 치고,
#        그 노트에서 이미 답한 후배 질문·이미 물은 깊이 질문(myNotes의 askedDepth 번호, 옛 기록은 asked 글)은 다시 묻지 않는다.
#        노트가 있으면 첫 응답(answers가 빈 때)에 resumed: true·myNoteId.
#   ② 코드: [11/22] 그 뒤 근거가 0건이거나 모두 2년 넘은 칸만 기본 질문(근거 적은 칸 순). 근거가 충분한 칸은
#        묻지 않고 covered로 알린다 → 깊이 질문(교환·파견 3, 인턴·비교과 2 — DEPTH_QUESTIONS, 판단·비교·후회·오해) → 「배운점」 마지막.
#        [11/23 작업 84] 기본·깊이·배운점 질문에 예시답 칩(examples). 말머리 칩만 보낸 답은 빼고 같은 질문을 다시 묻는다(retry).
#   ③ AI(충분판정, HCX): 칸의 첫 답이 들어오면 충분한지 본다. 부족하면
#      AI(꼬리질문, HCX): 꼬리 질문 하나 — 칸당 1회. 형식이 틀리거나 답에 없는 숫자·고유명사가 있으면 버리고 다음 칸.
#
# summarizeInterview(program, transcript, append?) — 요약 2종 + 내 경험노트 저장
#   [v2 작업 90] append: true면 기존 내 경험노트·공개 초안 뒤에 새 문장을 덧붙인다(새 문장에 new: true, 응답은 합친 전체).
#   ① AI(요약, Sonnet): 칸별로(후배 질문 답은 그 칸 안에서 질문마다 따로) 답 원문 → 해요체 문장 1~3개 {"문장":[...]}
#   ② 코드: 사후 검증 — 답 원문에 없는 숫자·영문·수량·고유명사가 있는 문장은 버린다.
#      다 버려지거나 AI가 실패하면 답 원문 문장을 그대로 쓴다(fallback: true).
#   ③ AI(일치검사, Opus): 남은 문장마다 원문과 대조 → match. 호출이 실패하면 match: false(「원문과 다를 수 있어요」).
#   ③′ AI(1인칭, Sonnet): 공개 초안 문장을 한 번에 1인칭 해라체로 → 내 경험노트. 검증에 걸린 문장은 해요체 그대로.
#   ④ 코드: identify.mark로 본인 식별 문장 표시 → runtime_fns.save_my_note로 저장(saved, myNoteId).
#
# [작업 110 초안] 플래그 VCC_TELL_CHAT=1이면 interviewNext 한 턴을 tell_chat.py가 맡는다(말판정 HCX → 다음 질문은 아래 코드 →
#   대화쓰기 Sonnet이 반응·질문 다듬기, 코드가 검증). 기본(0)은 이 파일 그대로.
# AI는 ai.py의 callAI로만 부른다. 프롬프트 원문은 docs/prompts/충분판정·꼬리질문·요약·일치검사.txt(작업 53 검증본).
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import askboo
import demand
import identify
import notes
import store
import tell_chat
from ai import callAI, load_prompt
from runtime_fns import drop_interview_draft, find_my_note, save_my_note

QUESTION_SECTION = notes.QUESTION_SECTION   # [v2] 없어진 칸 — 옛 화면·옛 transcript가 보내면 질문의 칸으로 옮긴다
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

# [11/22] 깊이 질문 — 보고서가 이미 답한 사실(서류·학점·금액)은 다시 묻지 않고, 보고서에 잘 안 쓰는
# 판단·비교·후회·오해를 묻는다(PRD 1:10 「보고서가 답하지 못한 질문만 묻는다」). (칸, 질문) — 답은 그 칸에 담긴다.
# 유도 질문·본인 식별 답(성적·사람 이름·날짜)을 부르는 질문은 넣지 않는다. 문장은 미리가 정했다(AI가 만들지 않음).
# [11/23 작업 84] 네 번째 값 = 예시답 칩(원우 PR #133 제안 문구). 질문마다 뜻이 달라 칸 단위 frames.json 예시 대신 여기 둔다.
# [11/26 작업 108] 첫 값 = 바뀌지 않는 번호. 「물었음」은 번호로 남기고 번호로 대조한다(myNotes askedDepth).
# 문구를 고쳐도 번호는 그대로 두고, 바뀌기 전 문구는 DEPTH_OLD에 남긴다(옛 기록 asked의 글을 그 번호로 이어 준다).
# 번호는 지우거나 다른 질문에 다시 쓰지 않는다.
DEPTH_QUESTIONS = {
    "교환": [
        ("교환-1", "생활", "출국 전에 걱정했던 것과 실제로 달랐던 게 있었나요?",
         ["걱정보다 수월했던 건 …", "생각보다 힘들었던 건 …", "예상과 달랐던 건 …"]),
        ("교환-2", "지원", "다시 준비 과정을 거친다면 무엇부터 하실 것 같아요?",
         ["어학 점수부터 준비할 거예요", "서류 일정부터 확인할 거예요", "다시 한다면 먼저 …"]),
        ("교환-3", "팁", "후배들이 {p}에 대해 잘 모르고 있는 것, 또는 잘못 알고 있는 게 있다면요?",
         ["생각보다 많아요. 예를 들면 …", "의외로 잘 모르는 건 …", "잘못 알려진 건 …"]),
    ],
    "인턴": [
        ("인턴-1", "업무내용", "시작 전에 상상했던 일과 실제 업무가 어떻게 달랐나요?",
         ["생각보다 많았던 일은 …", "상상과 달랐던 건 …", "예상과 비슷했던 건 …"]),
        ("인턴-2", "배운점", "이 인턴이 맞는 사람과 안 맞는 사람은 어떤 사람일까요?",
         ["이런 사람에게 맞아요: …", "이런 사람은 힘들 수 있어요: …", "꼭 필요한 건 …"]),
    ],
    "비교과": [
        ("비교과-1", "배운점", "기대와 비교해 실제로 얻은 건 뭐였어요?",
         ["기대한 만큼 얻은 건 …", "기대와 달랐던 건 …", "기대보다 좋았던 건 …"]),
        ("비교과-2", "배운점", "이 프로그램을 몇 학년 때 듣는 게 가장 좋을까요? 왜요?",
         ["1학년 때가 좋아요", "2~3학년 때가 좋아요", "학년보다 중요한 건 …"]),
        ("비교과-3", "활동내용", "끝까지 하려면 어떤 점을 각오해야 하나요?",
         ["시간을 꽤 들여야 해요", "과제가 많은 편이에요", "꼭 각오할 건 …"]),
    ],
}
# 바뀌기 전 문구(번호 → 옛 문구들). 11/26 작업 93(b2867b0)에서 비교과-1 문구를 바꿨다.
DEPTH_OLD = {
    "비교과-1": ["신청할 때 기대한 것과 실제로 얻은 게 같았나요?"],
}
DEPTH_BY_ID = {d[0]: d for qs in DEPTH_QUESTIONS.values() for d in qs}


def _depth_pattern(template):
    """질문 틀 → 정규화한 글과 맞춰 볼 식. {p}(프로그램 짧은 이름)는 아무 이름이나 — 짧은 이름 규칙이 바뀌어도 맞게."""
    parts = askboo._norm(template).split("{p}")
    return re.compile(".+?".join(re.escape(x) for x in parts))


_DEPTH_MATCH = [(d[0], _depth_pattern(t)) for d in DEPTH_BY_ID.values() for t in [d[2], *DEPTH_OLD.get(d[0], [])]]


def depth_id(question):
    """깊이 질문 글(지금 문구 또는 바뀌기 전 문구) → 번호. 깊이 질문이 아니면 None."""
    n = askboo._norm(question)
    return next((i for i, p in _DEPTH_MATCH if p.fullmatch(n)), None) if n else None
# 한 인터뷰에 묻는 깊이 질문 수(종류별, 없으면 기본). 근거가 적은 칸에 담기는 질문부터(시연 순서가 매번 같게).
# 교환·파견은 보고서 근거가 많아 기본 질문이 거의 안 남으므로 3개 모두 묻는다(11/22 미리).
DEPTH_PER_INTERVIEW = {"교환": 3, "*": 2}
OLD_YEARS = 2             # 칸의 근거가 모두 이보다 오래되면 '오래된 칸'(디자인 규칙 6-2 「최근 경험이 없어요」와 같은 기준)
STALE_PREFIX = "{s} 칸은 최근 경험이 없어요. "
# [11/23 작업 84] 말머리 칩(「가장 크게 배운 건 …」)을 고치지 않고 보내면 내용 없는 답이 노트에 남는다.
# 그 답은 없던 것으로 치고 같은 질문을 이 말을 붙여 다시 묻는다. 화면이 「…」를 지우고 보내도 잡는다.
RETRY_PREFIX = "조금만 더 이어서 써 주세요. "


# ── 공통 ──────────────────────────────────────────────────────────────
def kind_of(program):
    field = askboo.PROGRAMS.get(program, {}).get("분야")
    return KIND_BY_FIELD.get(field, "교환")


def frame_of(program):
    return FRAMES.get(kind_of(program)) or FRAMES.get("교환") or {"칸": [], "인터뷰로만": []}


def sections_of(program):
    """노트 틀 칸(「후배 질문」 빼고, frames.json 순서)."""
    return [s for s in frame_of(program)["칸"] if s != QUESTION_SECTION]


# ── 후배 질문의 칸 [v2 작업 89] ───────────────────────────────────────
_section_cache = {}   # 질문 id → 칸(문단분류 결과). questions.json에는 쓰지 않는다(콘솔 집계의 「칸」을 바꾸지 않게)


def question_section(program, q):
    """질문함 질문이 담길 칸. 질문 행의 칸 → (없거나 틀 밖) AI 문단분류 → 교환 「팁」·그 밖 「배운점」."""
    s = notes.section_for_question(program, q)
    if s:
        return s
    names = sections_of(program)
    key = (q or {}).get("id") or askboo._norm((q or {}).get("질문"))
    if key in _section_cache:
        return _section_cache[key]
    text = ((q or {}).get("질문") or "").strip()
    s = None
    if text and names:
        r = _call("문단분류", f"칸 목록: {', '.join(names)}\n문장: {text}\n출력:")
        j = r.get("json")
        s = j.get("칸") if r["ok"] and isinstance(j, dict) else None
    s = s if s in names else notes.fallback_section(program)
    if key:
        _section_cache[key] = s
    return s


def _question_row(program, qid=None, asked=None):
    """질문함 행. id로 찾고, 화면이 id를 빠뜨렸으면 질문 원문으로 찾는다. 없으면 None."""
    asked = askboo._norm(asked)
    with store.lock():
        rows = list(store.load("questions", []))
    if qid:
        q = next((q for q in rows if q.get("id") == qid), None)
        if q and q.get("프로그램명") == program:
            return q
    if asked:
        for q in reversed(rows):
            if q.get("프로그램명") == program and askboo._norm(q.get("질문")) == asked:
                return q
    return None


JUNIOR_ASK = "후배가 이렇게 물었어요 — \"{q}\" 경험이 있으면 들려주세요."
_JUNIOR_ASK_RE = re.compile(r'^후배가 이렇게 물었어요 — "(.*)" 경험이 있으면 들려주세요\.?$', re.S)


# [11/26] 후배 질문의 꼬리 질문 머리말. 화면이 요약 때 questionId를 빼고 보내므로, 이 머리말이 붙은 답은
# 바로 앞 후배 질문 답의 꼬리 답으로 본다.
JUNIOR_FOLLOW = "조금 더 여쭤볼게요. "


def _unwrap(question):
    """interviewNext가 감싼 후배 질문 글 → 후배 질문 원문. 감싼 글이 아니면 그대로."""
    m = _JUNIOR_ASK_RE.match((question or "").strip())
    return m.group(1) if m else question


def is_junior(a):
    """후배 질문에 대한 답인가(questionId가 있거나 옛 화면이 「후배 질문」 칸으로 보냄)."""
    return bool(a.get("questionId") or a.get("junior") or a.get("section") == QUESTION_SECTION)


SHORT_MAX = 14            # [Q-12] 질문에 넣는 이름 상한. 별칭이 없고 다듬어도 길면 「이 프로그램」
SHORT_FALLBACK = {"교환": "이 학교", "파견": "이 학교", "인턴": "이 기관"}   # 그 밖(비교과) 「이 프로그램」


def short_name(program):
    """질문에 넣는 짧은 이름. 별칭 → 다듬은 프로그램명(앞의 학교 이름·괄호 뺌) → 「이 학교·이 기관·이 프로그램」.
    [Q-12] 미리 시험(11/25): 「한국외국어대학교 직무탐색 집중교육에서는 어떤 활동을 했어요?」처럼 긴 이름이 그대로 들어가
    질문이 어색하고, 요약(Sonnet)이 그 이름을 문장 앞에 붙여 일치검사에서 떨어졌다."""
    aliases = askboo.PROGRAMS.get(program, {}).get("별칭") or []
    if aliases:
        return aliases[0]
    name = re.sub(r"\[[^\]]*\]|\([^)]*\)", " ", program or "")
    name = re.sub(r"^\s*(한국외국어대학교|외대|HUFS)\s+", "", name)
    name = " ".join(re.sub(r"[_&]", " ", name).split())
    return name if 0 < len(name) <= SHORT_MAX else SHORT_FALLBACK.get(kind_of(program), "이 프로그램")


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
        if isinstance(a.get("question"), str) and a["question"].startswith(RETRY_PREFIX):
            a["question"] = a["question"][len(RETRY_PREFIX):]   # 다시 물은 질문도 원래 질문으로 센다
        out.append(a)
    return out


# ── 예시답 칩(작업 84) ────────────────────────────────────────────────
def _stem(s):
    return re.sub(r"[\s.…:·,!?~]+", "", s or "")


def _all_stems():
    """말머리 칩(…로 끝남)의 앞부분 모음. 틀 예시 + 깊이 질문 예시."""
    chips = [c for f in FRAMES.values() for cs in (f.get("예시") or {}).values() for c in cs]
    chips += [c for qs in DEPTH_QUESTIONS.values() for *_, cs in qs for c in cs]
    return {_stem(c) for c in chips if isinstance(c, str) and c.rstrip().endswith("…")} - {""}


STEMS = _all_stems()


def bare_stem(answer):
    """답이 말머리 칩 앞부분뿐이면(이어 쓴 내용 없음) True."""
    return bool(answer) and _stem(answer) in STEMS


def _chips(lst):
    return [str(x) for x in lst[:3]] if isinstance(lst, list) and lst else None


def chips_for(program, section, question):
    """그 질문에 붙일 예시답 칩. 깊이 질문이면 질문별 예시, 아니면 frames.json 칸 예시. 후배 질문은 없음."""
    if section == QUESTION_SECTION:
        return None
    d = DEPTH_BY_ID.get(depth_id(question))
    if d and d[1] == section and d in DEPTH_QUESTIONS.get(kind_of(program), []):
        return _chips(d[3])
    if askboo._norm(question).endswith(askboo._norm(base_question(program, section))):   # 기본 질문·배운점(꼬리 질문은 없음)
        return _chips((frame_of(program).get("예시") or {}).get(section))
    return None


# ── interviewNext ─────────────────────────────────────────────────────
def interviewNext(me, payload):
    program = (payload.get("program") or "").strip()
    if not program:
        return {"error": "들려줄 경험을 먼저 골라 주세요"}
    # [v2 작업 90] 이어 쓰기: 내 경험노트가 있으면 그 칸·질문을 이미 한 것으로 친다
    mid, mine = find_my_note(me, program)
    prior = prior_of(program, mine)
    if tell_chat.enabled():   # [작업 110 초안] 대화형 — 끄면(기본) 아래 한 줄 그대로
        step = tell_chat.next_step(me, program, payload, prior, mine)
    else:
        step = _next_step(me, program, payload, prior)
    if mid and not payload.get("answers") and "error" not in step:
        step = {**step, "resumed": True, "myNoteId": mid}
    return step


def prior_of(program, mine):
    """내 경험노트에서 이미 한 것: 문장이 있는 칸, 답한 후배 질문 id, 물은 깊이 질문 번호(depth).
    [작업 108] 번호(askedDepth)에 더해, 번호가 없던 옛 기록의 질문 글(asked)도 번호로 바꿔 넣는다(바뀌기 전 문구 포함)."""
    names = set(sections_of(program))
    out = {"sections": set(), "questionIds": set(), "depth": set()}
    for sec in ((mine or {}).get("myNote") or {}).get("sections", []):
        lines = sec.get("lines") or []
        if lines and sec.get("name") in names:
            out["sections"].add(sec["name"])
        out["questionIds"] |= {ln["answersQuestionId"] for ln in lines if ln.get("answersQuestionId")}
    out["depth"] = {i for i in (mine or {}).get("askedDepth") or [] if i in DEPTH_BY_ID}
    out["depth"] |= {depth_id(q) for q in (mine or {}).get("asked") or []} - {None}
    return out


def _next_step(me, program, payload, prior, follow=True, passed=frozenset()):
    """follow·passed는 [작업 110] 대화형(tell_chat)만 넘긴다. 기본값이면 지금 그대로.
    follow=False: 충분판정·꼬리질문(AI)을 부르지 않는다(대화형은 말판정·대화쓰기가 대신 본다).
    passed: 선배가 「모름」이라 답 없이 넘긴 칸 — 다시 묻지 않는다(채운 칸으로 세지는 않음)."""
    # [v2] 후배 질문 답은 질문의 칸으로(옛 「후배 질문」 칸·questionId를 빠뜨린 답도)
    answers = _place_all(program, _clean_answers(payload.get("answers")))
    # [11/23 작업 84] 말머리 칩만 보낸 답은 빼고 센다. 방금 그랬으면 같은 질문을 다시 묻는다(아래).
    last_raw = answers[-1] if answers else None
    retry = last_raw if last_raw and not last_raw.get("skipped") and not is_junior(last_raw) \
        and bare_stem(last_raw.get("answer")) else None   # 후배 질문은 아래 ①이 다시 묻는다
    answers = [a for a in answers if a.get("skipped") or not bare_stem(a.get("answer"))]
    frame = frame_of(program)
    sections = sections_of(program)
    answered = {a.get("section") for a in answers if not a.get("skipped") and a.get("answer")}
    answered |= prior["sections"]   # [v2 작업 90] 내 경험노트에 문장이 있는 칸
    filled = len([s for s in sections if s in answered])   # [v2] 후배 질문 답도 그 칸으로 센다
    progress = {"filled": filled, "mine": filled, "total": len(sections)}

    # [11/22] 근거가 충분해 묻지 않을 칸(covered) — [v2] 후배 질문 단계에도 매 응답에 알린다
    stats = evidence_stats(program)
    gaps = [s for s in section_order(program, sections, stats) if s != LAST_SECTION and is_gap(stats.get(s))]
    covered = [s for s in sections if s != LAST_SECTION and s not in gaps]

    # ① 질문함의 후배 질문 먼저
    juniors = junior_questions(me, program)
    seen_q = {a.get("questionId") for a in answers if a.get("questionId")} | prior["questionIds"]
    seen_text = {askboo._norm(a.get(k)) for a in answers if is_junior(a) for k in ("asked", "question")}
    waiting = [q for q in juniors if q["id"] not in seen_q and askboo._norm(q["질문"]) not in seen_text]
    # [11/26] 방금 답이 후배 질문의 첫 답이면 다음 질문보다 먼저 충분한지 본다 — 질문마다 꼬리 질문 1회
    last = answers[-1] if answers else None
    if follow and last and last is last_raw and not last.get("skipped") and last.get("answer") and is_junior(last) \
            and last.get("section") in sections:
        same = [a for a in answers if is_junior(a) and not a.get("skipped") and _junior_key(a) == _junior_key(last)]
        if len(same) == 1:
            follow = follow_up(last["section"], last.get("asked", ""), last["answer"])
            if follow:   # junior: true를 붙이지 않는다 — 화면이 일반 질문 말풍선으로 question을 보여 주게
                step = {"done": False, "section": last["section"], "question": JUNIOR_FOLLOW + follow,
                        "followUp": True, "asked": last.get("asked", ""), "progress": progress,
                        "pendingQuestions": len(waiting), "covered": covered}
                if last.get("questionId"):
                    step["questionId"] = last["questionId"]
                return step

    if waiting:
        q = waiting[0]
        return {"done": False, "junior": True, "section": question_section(program, q),
                "questionId": q["id"], "asked": q["질문"],
                "question": JUNIOR_ASK.format(q=q["질문"]),
                "progress": progress, "pendingQuestions": len(waiting), "covered": covered}

    if retry and retry.get("section") in sections and retry.get("question"):
        step = {"done": False, "section": retry["section"], "question": RETRY_PREFIX + retry["question"],
                "progress": progress, "pendingQuestions": 0, "retry": True, "covered": covered}
        ex = chips_for(program, retry["section"], retry["question"])
        if ex:
            step["examples"] = ex
        return step

    # ③ 방금 들어온 답이 그 칸의 첫 답이면 충분한지 보고, 부족하면 꼬리 질문(칸당 1회)
    # [v2] 후배 질문 답(위에서 따로 본다)은 그 칸의 「첫 답」으로 세지 않는다(그 칸 질문의 꼬리는 그대로)
    if follow and last and not last.get("skipped") and last.get("answer") and last.get("section") in sections \
            and not is_junior(last):
        same = [a for a in answers if a.get("section") == last["section"] and not a.get("skipped")
                and not is_junior(a)]
        if len(same) == 1:
            follow = follow_up(last["section"], last.get("question", ""), last["answer"])
            if follow:
                return {"done": False, "section": last["section"], "question": follow,
                        "followUp": True, "progress": progress, "pendingQuestions": 0, "covered": covered}

    # ② [11/22] 비었거나(0건) 오래된 칸만 기본 질문 — 근거가 충분한 칸은 묻지 않는다(covered)
    base = {"done": False, "progress": progress, "pendingQuestions": 0, "covered": covered}
    for s in gaps:
        if s not in answered and s not in passed:
            q = base_question(program, s)
            if stats.get(s):   # 근거가 있는데 오래된 칸
                q = STALE_PREFIX.format(s=s) + q
            step = {**base, "section": s, "question": q}
            ex = _chips((frame.get("예시") or {}).get(s))   # P1-여건(작업 84): frames.json에 있으면
            if ex:
                step["examples"] = ex
            return step

    # ③′ 깊이 질문(보고서에 잘 안 쓰는 판단·비교) — 이번 인터뷰에서 아직 안 한 것
    # [작업 108] 번호로 대조. 지난번에 물은 것은 고르기 전에 빼므로(depth_questions) 남은 질문이 다음 차례가 된다.
    now = {depth_id(a.get("question")) for a in answers}
    for i, s, q, ex in depth_questions(program, sections, stats, before=prior["depth"]):
        if i not in now:
            step = {**base, "section": s, "question": q, "depth": True}
            if _chips(ex):
                step["examples"] = _chips(ex)   # [11/23 작업 84] 깊이 질문 예시답
            return step

    # ④ 배운점은 마지막(교환·파견은 인터뷰로만 받는 칸)
    if LAST_SECTION in sections and LAST_SECTION not in answered and LAST_SECTION not in passed:
        step = {**base, "section": LAST_SECTION, "question": base_question(program, LAST_SECTION)}
        ex = _chips((frame.get("예시") or {}).get(LAST_SECTION))   # [11/23 작업 84] 배운점에도 칩
        if ex:
            step["examples"] = ex
        return step
    return {"done": True, "progress": progress, "covered": covered}


def junior_questions(me, program):
    """같은 프로그램의 미답변(hold) 질문, 최근순 최대 3개. 본인이 한 질문은 뺀다."""
    with store.lock():
        rows = list(store.load("questions", []))
    rows = [q for q in rows if q.get("프로그램명") == program and q.get("status") == "hold"
            and q.get("colreg_no") != me and (q.get("질문") or "").strip()]
    rows.sort(key=lambda q: q.get("at") or "", reverse=True)
    return rows[:MAX_JUNIOR]


def _year(semester):
    m = re.match(r"(\d{4})", str(semester or ""))
    return int(m.group(1)) if m else None


def evidence_stats(program):
    """칸별 근거 연도 목록. 보고서 근거(evidence.json) + 동의를 통과한 인터뷰 문장(noteLines)."""
    import notes   # notes가 runtime_fns를 거쳐 돌아오지 않게 여기서 부른다
    stats = {}
    for e in list(askboo.EVIDENCE.get(program, [])) + notes.interview_lines(program):
        stats.setdefault(e.get("칸"), []).append(_year(e.get("semester")))
    return stats


def is_gap(years, this_year=None):
    """근거 0건이거나, 연도가 있는 근거가 모두 OLD_YEARS보다 오래됐으면 물어야 할 칸."""
    if not years:
        return True
    this_year = this_year or date.today().year
    known = [y for y in years if y]
    return bool(known) and len(known) == len(years) and all(this_year - y > OLD_YEARS for y in known)


def section_order(program, sections, stats=None):
    stats = evidence_stats(program) if stats is None else stats
    body = [s for s in sections if s != LAST_SECTION]
    body.sort(key=lambda s: len(stats.get(s) or []))   # 안정 정렬: 같은 수면 frames.json 순서
    return body + ([LAST_SECTION] if LAST_SECTION in sections else [])


def depth_questions(program, sections, stats=None, before=()):
    """이번 인터뷰의 깊이 질문 (번호, 칸, 질문, 칩) — 종류별 DEPTH_PER_INTERVIEW개. 근거가 적은 칸에 담기는 것부터(같으면 목록 순서).
    [작업 108] before = 지난 인터뷰들에서 이미 물은 번호. 먼저 빼고 나서 고른다(앞 N개만 돌지 않게)."""
    stats = evidence_stats(program) if stats is None else stats
    kind = kind_of(program)
    pool = [d for d in DEPTH_QUESTIONS.get(kind, []) if d[1] in sections and d[0] not in before]
    pool.sort(key=lambda d: len(stats.get(d[1]) or []))
    n = DEPTH_PER_INTERVIEW.get(kind, DEPTH_PER_INTERVIEW["*"])
    return [(i, s, q.format(p=short_name(program)), ex) for i, s, q, ex in pool[:n]]


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
    items = _clean_answers(payload.get("transcript"))
    if tell_chat.enabled():   # [작업 110 초안] 되물음·딴얘기·모름은 빼고, 다른 칸 이야기는 그 칸으로, 다듬은 질문은 원래 질문으로
        items = tell_chat.for_summary(me, program, items)
    transcript = [a for a in items
                  if a.get("answer") and not a.get("skipped") and not bare_stem(a.get("answer"))][:MAX_TRANSCRIPT]
    if not transcript:
        return {"error": "요약할 답이 아직 없어요. 질문에 하나 이상 답해 주세요"}

    append = payload.get("append") is True
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

    public_draft = identify.mark({"sections": pub_sections})   # 새 문장만 검사(기존 문장은 선배가 고친 값 유지)
    my_note = {"sections": my_sections}
    answered = demand.count_interview_answers(transcript)
    asked = [_unwrap(a.get("question")) for a in transcript if a.get("question")]
    asked_depth = list(dict.fromkeys(i for i in map(depth_id, asked) if i))   # [작업 108] 물은 깊이 질문 번호
    try:
        my_note_id = save_my_note(me, program, draft_id, my_note, public_draft,
                                  answered=answered, asked=asked, asked_depth=asked_depth, append=append)
        saved = True
        drop_interview_draft(me, program)   # [v2 작업 79] 요약하면 미완성 초안은 지운다(0장 보관기간)
        if tell_chat.enabled():
            tell_chat.drop(me, program)       # [작업 110 초안] 대화 판정 기록도 함께
    except OSError:
        my_note_id, saved = None, False
    if append and saved:   # [v2 작업 90] 응답은 합친 전체, 이번에 만든 문장에 new: true
        _, rec = find_my_note(me, program)
        my_note, public_draft = _flag_new(rec["myNote"], my_note), _flag_new(rec["publicDraft"], public_draft)
        answered = max(answered, int(rec.get("answered", 0)))
    # [11/22] answered = 유효 답변 수(서로 다른 질문, 10자 이상). need(3) 이상 + 1문장 공유면 선배 추천이 열린다
    return {"draftId": draft_id, "program": program, "saved": saved, "myNoteId": my_note_id,
            "myNote": my_note, "publicDraft": public_draft, "answered": answered, "need": demand.NEED}


def _flag_new(merged, new):
    """합친 칸에서 이번 문장(각 칸의 마지막 n개 — save_my_note가 뒤에 붙임)에 new: true."""
    count = {s["name"]: len(s.get("lines", [])) for s in (new or {}).get("sections", [])}
    for sec in merged.get("sections", []):
        n = count.get(sec["name"], 0)
        if n:
            sec["lines"][-n:] = [{**ln, "new": True} for ln in sec["lines"][-n:]]
    return merged


def _append(sections, name, lines):
    for s in sections:
        if s["name"] == name:
            s["lines"] += lines
            return
    sections.append({"name": name, "lines": lines})


def _place_junior(program, a):
    """[v2 작업 89] 후배 질문 답을 질문의 칸에 놓는다. 돌려주는 값은 새 dict(questionId·asked 채움).
    화면이 보낸 칸이 틀 안이면 그대로(interviewNext가 준 칸), 옛 「후배 질문」 칸·틀 밖이면 질문으로 다시 정한다."""
    if is_junior(a):
        q = _question_row(program, a.get("questionId"), a.get("asked") or _unwrap(a.get("question")))
    else:   # 화면이 questionId·junior를 빠뜨렸어도 질문 글이 질문함 질문이면 후배 질문 답으로 본다
        q = _question_row(program, None, _unwrap(a.get("question"))) if a.get("question") else None
        if not q:
            return a
    a = dict(a)
    if q:
        a["questionId"] = q.get("id")
        a.setdefault("asked", q.get("질문", ""))
    a.setdefault("asked", _unwrap(a.get("question", "")))
    if a.get("section") not in sections_of(program):
        a["section"] = question_section(program, q or {"질문": a["asked"]})
    return a


def _junior_key(a):
    return a.get("questionId") or askboo._norm(a.get("asked"))


def _place_all(program, items):
    """답마다 _place_junior. 꼬리 답(JUNIOR_FOLLOW 머리말)은 바로 앞 후배 질문의 questionId·asked·칸을 물려받고
    follow에 꼬리 질문 글을 남긴다."""
    out = []
    for a in items:
        question = a.get("question") or ""
        prev = out[-1] if out else None
        if question.startswith(JUNIOR_FOLLOW) and prev and is_junior(prev):
            a = {**a, "follow": question[len(JUNIOR_FOLLOW):], "asked": prev.get("asked", ""),
                 "section": prev.get("section"), "junior": True}
            if prev.get("questionId"):
                a["questionId"] = prev["questionId"]
        else:
            a = _place_junior(program, {k: v for k, v in a.items() if k != "follow"})
        out.append(a)
    return out


def group_answers(me, program, transcript):
    """칸별로 답을 모은다(첫 답 + 꼬리 답). 순서는 frames.json 칸 순서.
    [v2 작업 89] 「후배 질문」 칸은 없다 — 후배 질문 답은 질문의 칸에 담되, 칸 안에서 질문마다 따로 모은다
    (문장에 answersQuestionId·asked를 붙여야 하므로 그 칸의 다른 답과 섞어 요약하지 않는다)."""
    order = sections_of(program)
    by_key, keys = {}, []
    for a in _place_all(program, transcript):
        section = a.get("section") or "기타"
        qid = a.get("questionId") if is_junior(a) else None
        key = (section, qid or (askboo._norm(a.get("asked")) if is_junior(a) else None))
        if key not in by_key:
            keys.append(key)
            by_key[key] = {"section": section, "questionId": qid,
                           "asked": a.get("asked", "") if is_junior(a) else a.get("question", ""),
                           "answers": [], "questions": []}
        by_key[key]["answers"].append(a["answer"])
        q = a.get("follow") or (a.get("asked") if is_junior(a) else _unwrap(a.get("question")))
        by_key[key]["questions"].append((q or "").strip())
    keys.sort(key=lambda k: order.index(k[0]) if k[0] in order else len(order))   # 안정 정렬: 칸 안에서는 들어온 순서
    groups = [by_key[k] for k in keys]
    for g in groups:
        g["source"] = " ".join(g["answers"])
    return groups


def _qa_text(g):
    """[작업 21] 요약 입력: 질문·답 쌍을 차례로. 「네, 그랬어요」 같은 답도 질문이 있어야 뜻이 통한다."""
    qs = g.get("questions") or [""] * len(g.get("answers", []))
    return "\n".join((f"질문: {q}\n" if q else "") + f"답: {a}" for q, a in zip(qs, g.get("answers", [])))


def summarize_group(g):
    """돌려주는 값: [{"text", "fallback"?}] — 검증을 통과한 해요체 문장, 없으면 답 원문 문장.
    [작업 21] AI에 질문도 함께 넘기고, 원문 대조(outside_source)도 질문+답 기준. 정보 없는 짧은 문장은 AI 문장도 뺀다."""
    if "answers" not in g:   # 옛 호출(source만): 답 하나로 본다
        g = {**g, "answers": [g["source"]], "questions": []}
    context = " ".join(q for q in g.get("questions", []) if q) + " " + g["source"]
    r = _call("요약", f"칸: {g['section']}\n{_qa_text(g)}\n출력:")
    j = r.get("json")
    lines = []
    if r["ok"] and isinstance(j, dict) and isinstance(j.get("문장"), list):
        for s in j["문장"][:3]:
            s = s.strip() if isinstance(s, str) else ""
            if s and not too_thin(s) and not outside_source(s, context):
                lines.append({"text": s})
    if lines:
        return lines
    # [11/26] 후배 질문은 처음 답과 꼬리 답을 따로 잘라 둘 다 싣는다(마침표 없는 첫 답이 꼬리 답과 붙지 않게)
    parts = g["answers"] if g.get("questionId") else [g["source"]]
    out = []
    for part in parts:
        src = [askboo.clean_source(s) for s in askboo.split_sentences(part)]
        out += [{"text": s, "fallback": True} for s in src if s and not too_thin(s)][:3]
    return out


# 정보가 없는 짧은 문장(「생각보다 많이 들었어요.」)은 해봤노트에 올리지 않는다
# (원우 11/22 제보 → 미리 결정: 빼기). 숫자가 있으면 짧아도 정보로 본다(「비자는 2주 걸렸어요.」).
# [작업 21] 원문 fallback뿐 아니라 AI 요약 문장에도 쓴다(질문 맥락 없이 답만 옮긴 문장 거르기).
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
