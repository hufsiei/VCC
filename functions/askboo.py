# askboo.py — askBoo(question, history) v2 6단계 (작업 18·87, 작성: 미리)
#
# 기준: docs/spec-v1.md 4장 askBoo [v2] · docs/HCX-원칙-v3.md 3~5절 · docs/askBoo-v2 반영 검토안 2장
#
# [v2, 11/24 작업 87] 지금 4+1단계 위에 두 단계를 더했다. 가드레일(프로그램 범위 안 근거·사후 검증·보류→질문함)은 그대로.
#   ①  AI(질문정리, Sonnet): 최근 대화(history 4턴) + 이번 질문 → {의도, 분야, 나라, 프로그램후보, 제외, 칸, 정리된질문}.
#        코드가 프로그램 이름을 programs.json과 대조해 없는 이름은 버린다. 실패하면 아래 v1 경로(정규식 대조) 그대로.
#   ②  코드: 의도별 분기 — 대화 → status "chat"(고정 문구 + 칩, AI 없음, 질문함 저장 없음) / 탐색·사람찾기 → "notes" /
#        규정 → "official" / 경험질문 → 아래 ③. 「제외」 프로그램은 후보에서 뺀다.
#   ⑤  AI(답쓰기, Sonnet): 정리된 질문 + 고른 문장(번호·출처·연도·선배 표시) → {"답":[{"text","근거":[번호]}]} 2~4문장.
#   ⑥  코드 + AI(답검사, Opus): 문장마다 인용한 근거 원문과 대조(숫자·영문·고유명사·수량 + 답검사 — 전하는 말투 허용). 근거 번호 없는 문장·
#        걸린 문장은 버린다. 다 버려지면 v1 방식(고른 문장 원문 인용, fallback)으로 돌려준다 → v1의 답이 최악의 경우.
#   응답: lines[].cites(인용 sourceId), singleSenior(근거가 한 사람뿐), 새 status "chat"(message·chips), notes에 oneLine·kinds.
#
# v1(작업 18) 4+1단계 — 질문정리가 실패했을 때의 경로이자 ⑥의 폴백:
#   ①′ 코드: 규정 질문 판별 → status "official" (AI 없음, spec 4장 판별 표현)
#   ①  코드: 프로그램명·별칭 대조 (tools/check_alias_match.py와 같은 규칙, 긴 이름 우선)
#        실패하면 data/intern-keywords.json(작업 81, 있을 때만)으로 업체 1~3개. 그래도 없으면 hold
#   ②  코드: 근거 추출 — 질문 주제어 → 보고서 문항으로 좁히고, 문단을 문장으로 쪼개 같은 문장은 하나만
#        근거 풀 = evidence.json + 공개 동의를 통과한 인터뷰 문장(notes.interview_lines, 작업 26·74).
#        인터뷰 문장은 주제어의 칸과 같은 칸 문장. [v2 작업 89] 후배 질문에 답한 문장도 질문의 칸에 든 일반 문장이다
#        후보가 없거나 인터뷰로만 채우는 칸(근무조건 등)에 인터뷰 문장도 없으면 AI 없이 hold
#   ③  AI(고르기): 관련 문장 번호 {"관련":[..]} — 빈 목록이면 hold
#   ④  AI(변환): 고른 문장 하나씩 해요체 한 문장 {"1":"..."}
#   ⑤  코드: 사후 검증 — 원문에 없는 숫자·영문·고유명사·새 내용어가 있으면 그 문장을 버리고 원문 인용(fallback)
#
# AI는 ai.py의 callAI로만 부른다. 프롬프트 원문은 docs/prompts/askBoo-고르기.txt, askBoo-변환.txt.
# hold·official 질문은 runtime_fns.add_question으로 질문함에 저장한다.
import json
import re
from pathlib import Path

import notes
from ai import callAI, load_prompt

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

MAX_LINES = 3        # 폴백(원문 인용) 문장 수 상한 (spec 8장: 출처 달린 문장 3개)
MAX_PICK = 8         # [v2] 고르기가 고르는 문장 수 상한 — 답쓰기에 넣는 근거
MAX_ANSWER_LINES = 4 # [v2] 답쓰기 문장 수 상한
MAX_HISTORY = 4      # [v2] 질문정리에 넣는 이전 대화 수
INTENTS = ("경험질문", "탐색", "대화", "규정", "사람찾기")
FIELDS = ("국제교류", "현장실습", "비교과")
MAX_CANDIDATES = 30  # 고르기에 넣는 문장 수 상한 (최근 학기 순)

HOLD_MESSAGE = "이 부분은 아직 경험한 선배가 없어요. 질문함에 담아 두었어요. 닮은 선배에게 물어볼까요?"
# [11/23] 보류 이유별 문구 — 노트가 있는데 「경험한 선배가 없어요」라고 하지 않는다(미리 실사용)
HOLD_NO_PROGRAM = "질문에 맞는 해봤노트를 찾지 못했어요. 질문함에 담아 두었어요. 닮은 선배에게 물어볼까요?"
HOLD_NO_TOPIC = "{program} 해봤노트에는 아직 이 내용이 없어요. 질문함에 담아 두었어요. 닮은 선배에게 물어볼까요?"
# [11/23] chat 칩 「질문함에 담기」(force: "hold") — 학생이 직접 담은 것이라 「못 찾았어요」라고 하지 않는다
HOLD_SAVED = "질문함에 담아 두었어요. 선배가 답하면 알려 드릴게요."
MAX_NOTES = 5        # status "notes"로 보여 주는 노트 카드 수 상한

# [11/23] 사람을 찾는 질문(「네덜란드 교환 다녀온 선배?」) — 주제어가 없으면 답 대신 해봤노트 카드로 안내한다
# [11/23] 「다녀온 선배」 뒤에 있는지·누구인지를 묻는 말이 올 때만 사람 찾기로 본다.
#        「다녀온 선배들이 제일 후회한 게 뭐예요?」는 선배의 경험을 묻는 질문이라 답으로 보낸다.
#        「선배가 알려준 …」·「선배가 찾은 집」처럼 선배가 주어인 말은 사람 찾기가 아니다 — 찾·소개·연결·알려는
#        「선배(를) 찾아요」처럼 주어 조사 없이 올 때만 본다. 있·계·없은 「선배가 있어요?」처럼 주어 조사와 함께도 본다.
_PERSON_ASK = (r"\s*(님)?(들)?(\s*(이|가|은|는|도)?\s*(있|계|없)"
               r"|\s*(을|를)?\s*(좀\s*)?(찾|소개|연결|알려)|\s*\?|\s*$)")
PERSON_RE = re.compile(r"(다녀온|갔다\s*온|가\s*본|해\s*본|경험한|다녀오신|해보신)\s*(선배|사람|분)" + _PERSON_ASK
                       + r"|선배" + _PERSON_ASK)

# ── ①′ 규정 질문 (spec 4장 [11/19] 판별 표현 그대로) ────────────────────
OFFICIAL_RE = re.compile(r"평점|장학금|몇\s*학점|선발\s*(인원|기준)|휴학|등록금|초과학기|인정\s*신청|인정받을 수")
# [11/23 원우 #151 ①] 넓힌 표현(tools/rule_probe.py PROPOSED에서 「자격증」만 뺌) — 자격·기한·점수 기준·연장·불이익·지원금 등.
# 같은 낱말이 경험 질문에도 나오므로 지난 경험을 묻는 말투(…했어요?·어땠어요?·힘들었어요?)면 공식 안내로 보내지 않는다.
# OFFICIAL_RE(위)에 걸리면 말투와 상관없이 예전처럼 공식 안내(지금보다 나빠지지 않게).
OFFICIAL_WIDE_RE = re.compile(
    r"자격(?!증)|참여\s*조건|지원\s*조건|신청\s*(기간|마감|방법)|접수\s*(기간|마감)"
    r"|(?<!과제)(?<!과제\s)(?<!리포트)(?<!리포트\s)(?<!레포트)(?<!레포트\s)(?<!시험)(?<!시험\s)마감(이|일)|언제까지"   # 과제·시험 마감은 수업 경험
    r"|몇\s*점\s*(이상|넘|필요|되어야|이어야)|(어학|성적|점수)\s*기준|기준표|환산"
    r"|(파견|교환|기간)\s*(을\s*)?(한\s*학기\s*)?연장|중복\s*지원|불이익|페널티|(포기|취소)하면"
    r"|지원\s*가능|지원할\s*수\s*있|학비\s*(는|를|가)?\s*(어디|얼마|감면|면제|내)|체재비|지원금\s*(은|이)?\s*(얼마|나와|나오|받을\s*수)"
    r"|마일리지|이수증|발급\s*기준|수료\s*(기준|못)|몇\s*번\s*빠지면|유효\s*기간|일정이\s*언제"
    r"|(제출|신청|접수|모집|지원)\s*(기한|기간|마감)|기한(이|은)?\s*(언제|지났|까지)|모집\s*(인원|일정|요강|기간|있)"
    r"|발표(가|는|일)?\s*(언제|날)|(학점|평점|성적|점수|어학)\s*기준|연장\s*(신청|가능|할\s*수)")
EXPERIENCE_TONE = re.compile(r"(했|었|였|웠|겼|졌|냈|썼|봤|갔|왔|됐|났|셨)(어요|나요|어|니|습니까)\s*\??$|어땠|힘들|재미|느꼈|좋았|떨렸|고민|걱정")


def is_official(question):
    if OFFICIAL_RE.search(question):
        return True
    return bool(OFFICIAL_WIDE_RE.search(question)) and not EXPERIENCE_TONE.search(question)

# ── ② 질문 주제어 → 보고서 문항 (국제교류). 문항은 앞 번호로 적는다 ──────────
# 여기에 없는 주제(아르바이트·취업 등)는 보고서에 칸이 없으므로 hold → 질문함 → 선배 인터뷰로 채운다.
TOPICS_EXCHANGE = [
    (r"입학\s*허가|지원\s*서류|서류|지원하려면|지원\s*방법|원서", ["1-1", "1-3"]),
    (r"비자|보험|항공|비행기", ["1-2"]),
    (r"출국\s*전|준비물|챙겨\s*가|챙길|짐", ["1-3"]),
    (r"준비", ["1-1", "1-3"]),   # [11/23] 「가려면 뭘 준비해요?」 — 지원 서류·출국 전 준비
    (r"공항|교통편|어떻게\s*가", ["2-1"]),
    (r"수강\s*신청|시간표", ["2-2"]),
    (r"수업|강의|어학|과제|세미나", ["2-3"]),
    (r"기숙사|숙소|방\s*구|방값|집\s*구|월세|자취|주거", ["2-4"]),
    (r"교내\s*활동|동아리|버디|모임|학생회|행사", ["2-5"]),
    (r"생활비|비용|예산|얼마|물가", ["2-6"]),
    (r"학점\s*인정|학점인정|성적\s*인정|학점", ["3", "2-2"]),
    (r"날씨|치안|소매치기|생활(?!비)", ["2-7", "1-3"]),
    (r"조언|한마디|어때|어땠|후기|경험담|팁|해\s*주고\s*싶은|알아\s*두면|후회|아쉬", ["4"]),  # 11/20 원우 제안: '팁' 질문이 보류로 빠지던 것 · 11/23 후회·아쉬움
]
# 현장실습 후기는 칸이 없는 자유 서술이라 전체 문단이 후보. 아래 주제는 인터뷰로만 채우는 칸이라 근거 없음.
INTERVIEW_ONLY_INTERN = re.compile(r"월급|급여|시급|페이|보수|연봉|근무\s*시간|근무\s*조건|복지|휴가|정규직|채용\s*전환")
SECTION_BY_ITEM = {"1-1": "지원", "1-2": "지원", "1-3": "지원", "2-1": "생활", "2-2": "학점", "2-3": "학점",
                   "2-4": "생활", "2-5": "생활", "2-6": "비용", "2-7": "생활", "3": "학점", "4": "팁"}

# 문장 앞의 군말 — 같은 문장 찾기(중복 제거)에만 쓴다. 원문은 바꾸지 않는다.
FILLER_RE = re.compile(r"^(?:(?:참고로|경험상|사실|개인적으로|하나 꼽자면|미리 말해 두면|제 경우엔|지나고 보니|확실히|그리고|진짜|"
                       r"솔직히 말하면|돌이켜 보면|지금 생각해도|그 시기엔|한국과 비교하면|날씨 얘기를 하자면|저는)\s*)+")


# ── 데이터 (한 번만 읽는다) ───────────────────────────────────────────
def _json(name, default):
    try:
        return json.loads((DATA / name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


PROGRAMS = {p["프로그램명"]: p for p in _json("programs.json", [])}
DEPTS = {d["부서코드"]: d for d in _json("departments.json", [])}
EVIDENCE = {}
for _e in _json("evidence.json", []):
    EVIDENCE.setdefault(_e["프로그램명"], []).append(_e)
for _rows in EVIDENCE.values():
    _rows.sort(key=lambda e: (e.get("학년도", 0), e.get("학기", 0)), reverse=True)   # 최근 학기 먼저
INTERN_KEYWORDS = _json("intern-keywords.json", {})   # 작업 81(원우). 없으면 빈 사전
# [11/23] 나라 이름 → 그 나라 국제교류 프로그램(programs.json 세부). 프로그램명 대조가 실패했을 때만 쓴다
COUNTRIES = {}
for _name, _p in PROGRAMS.items():
    if _p.get("분야") == "국제교류" and _p.get("세부"):
        COUNTRIES.setdefault(_p["세부"], []).append(_name)


def _norm(s):
    return re.sub(r"\s+", "", s or "").lower()


# (정규화한 말, 프로그램명, 별칭 여부) — 별칭에만 아래 '학교 종류 꼬리' 규칙을 적용한다
_TERMS = [(_norm(a), name, i > 0) for name, p in PROGRAMS.items()
          for i, a in enumerate([name, *p.get("별칭", [])]) if _norm(a)]

# (11/20, tools/check_alias_match.py 4)와 같은 규칙) 별칭 바로 뒤에 학교 종류 말 + 대학/대가 붙으면 다른 학교로 보고 걸지 않는다.
# 예) '파리시테예술대학교'는 별칭 '파리시테'가 들어 있어도 파리시테대학교가 아님 → 보류. '밀라노대학교'처럼 바로 대학이 오면 건다.
SCHOOL_KIND = ("공과", "공업", "과학기술", "기술", "응용과학", "예술", "음악", "미술", "의과", "약학",
               "경영", "경제", "국립", "주립", "시립", "가톨릭", "카톨릭", "사범", "교육", "외국어", "신학",
               "왕립", "교황청립")   # 11/23 「스톡홀름 왕립공과대학」·「살라망카 교황청립대학교」는 다른 학교(#147)
SCHOOL_TAIL = re.compile(r"(?:" + "|".join(SCHOOL_KIND) + r")+(?:대학교|대학|대)")   # 11/23 종류 말이 이어져도(왕립공과대학)


def _alias_ok(t, q):
    """별칭이 나오는 자리 중 하나라도 뒤에 다른 학교 꼬리가 없으면 인정."""
    start = q.find(t)
    while start != -1:
        if not SCHOOL_TAIL.match(q, start + len(t)):
            return True
        start = q.find(t, start + 1)
    return False

# 사후 검증용 고유명사 사전: 프로그램명·별칭·국가·부서명 + 자주 지어내는 시험·기관 이름
PROPER_NOUNS = sorted({w for name, p in PROGRAMS.items() for w in [name, *p.get("별칭", []), p.get("세부", "")]
                       if len(_norm(w)) >= 2} |
                      {d["부서명"] for d in DEPTS.values()} |
                      {"괴테", "테스트다프", "토플", "토익", "아이엘츠", "델프", "달프", "에라스무스", "슈뱅", "블로킹"},
                      key=len, reverse=True)


# ── 공개 함수 ─────────────────────────────────────────────────────────
def askBoo(me, payload, save=True):
    """local_fn.py가 부른다. save=False면 질문함에 저장하지 않는다(평가 스크립트용).
    payload: {question, history?: [{question, status, program?}], force?: "hold"}"""
    question = (payload.get("question") or "").strip()
    if not question:
        return {"error": "질문을 입력해 주세요"}
    if len(question) > 300:
        return {"error": "질문은 300자 안으로 적어 주세요"}
    history = clean_history(payload.get("history"))

    # [v2] chat 칩 「질문함에 담기」: 답을 찾지 않고 바로 질문함에 hold로
    if payload.get("force") == "hold":
        return _hold(me, question, None, None, save, why="담기")

    programs = match_programs(question)
    country = None
    if not programs:                       # [11/23] 프로그램명이 없으면 나라 이름으로(근거 많은 순)
        country, programs = match_country(question)

    # ①′ 규정 질문 → 공식 안내 (정규식이 먼저 — 보수 규칙, HCX 원칙 v3 5절)
    if is_official(question):
        return _official(me, question, programs, save)

    # ① [v2] 질문 정리(AI). 실패하면 plan=None → 아래는 v1 경로 그대로
    plan = clarify(question, history)
    effective = question
    if plan:
        if plan["의도"] == "규정":
            return _official(me, question, programs, save)
        effective = plan["정리된질문"] or question
        # 프로그램: 정리 결과(대조 통과분)가 있으면 그것, 없으면 정규식 결과. 「제외」는 뺀다
        if plan["프로그램후보"]:
            programs, country = plan["프로그램후보"], None
        else:
            if plan["분야"]:   # 정리 결과의 분야와 다른 프로그램(「독일 인턴」에 나라 대조로 잡힌 독일 교환 등)은 뺀다
                programs = [p for p in programs if PROGRAMS.get(p, {}).get("분야") == plan["분야"]]
            if not programs and plan["나라"]:
                country, programs = match_country(plan["나라"])
                programs = [p for p in programs if not plan["분야"] or PROGRAMS.get(p, {}).get("분야") == plan["분야"]]
        if plan["제외"]:
            programs = [p for p in programs if p not in plan["제외"]]
        if plan["의도"] == "대화":
            return _chat(plan, history)
        if plan["의도"] in ("탐색", "사람찾기"):
            found = _explore(plan, programs, country or plan["나라"])
            if found:
                return found
            return _hold(me, question, programs[0] if programs else None, plan["칸"], save, why="탐색 결과 없음")
        if not programs and plan["분야"] and plan["제외"]:
            # 「코트라 말고 무역 인턴」처럼 제외하고 남는 프로그램이 없으면 그 분야 노트 목록으로
            found = _explore(plan, [], country or plan["나라"])
            if found:
                return found

    # ① 프로그램이 없으면 보류
    if not programs:
        return _hold(me, question, None, None, save, why="프로그램 없음")

    # ①″ [11/23] 사람을 찾는 질문이나 나라만 말한 질문인데 주제어가 없으면 → 해봤노트 카드로 안내(AI 없음)
    if not plan and not has_topic(question) and (PERSON_RE.search(question) or country):
        found = _notes(programs, country)
        if found:
            return found

    # ②/③ 근거 추출 (정리된 질문 + 원래 질문의 주제어·겹침을 모두 본다)
    cands, section, why = extract(effective if effective == question else f"{question} {effective}", programs,
                                  section_hint=plan["칸"] if plan else None)
    if not cands:
        return _hold(me, question, programs[0], section, save, why=why)

    # ④ 고르기 (HCX)
    picked, why = pick(effective, cands)
    if not picked:
        return _hold(me, question, programs[0], section, save, why=why)

    # ⑤ 답쓰기 + ⑥ 검증 (v2) → 다 버려지면 v1 원문 인용
    out = compose(effective, picked)
    if out is None:
        out = fallback_lines(picked)
    out["noteId"] = notes.note_id(picked[0]["program"])
    out["suggestSenior"] = False
    return out


def fallback_lines(picked):
    """v1 ④ 변환 + ⑤ 사후 검증: 고른 문장을 하나씩 해요체로(검증에 걸리면 원문 인용). v2의 폴백."""
    lines, sources, seen, texts = [], {}, {}, set()
    for c in picked[:MAX_LINES]:
        text, fallback = convert(c["text"])
        if _norm(text) in texts:   # 다른 보고서의 같은 문장은 한 번만
            continue
        texts.add(_norm(text))
        sid = c["sourceId"]
        seen[sid] = seen.get(sid, 0) + 1
        line = {"text": text, "sourceId": sid, "cites": [sid],
                "lineId": f"L-{sid}" if seen[sid] == 1 else f"L-{sid}.{seen[sid]}"}
        if fallback:
            line["fallback"] = True   # AI 문장을 버리고 근거 원문을 그대로 보여 준 줄(화면: 「근거 원문 보기」)
        lines.append(line)
        sources[sid] = {"docType": c["docType"], "program": c["program"], "semester": c["semester"]}
    return {"status": "ok", "lines": lines, "sources": sources, "singleSenior": _single_senior([c["sourceId"] for c in picked[:MAX_LINES]])}


# ── ① [v2] 질문 정리 ──────────────────────────────────────────────────
STATUS_WORD = {"ok": "답함", "hold": "보류", "official": "공식 안내", "notes": "노트 안내", "chat": "대화"}


def clean_history(items):
    """화면이 보낸 최근 대화. 글자만 남기고 최근 MAX_HISTORY개."""
    out = []
    for h in items if isinstance(items, list) else []:
        if not isinstance(h, dict) or not isinstance(h.get("question"), str) or not h["question"].strip():
            continue
        out.append({"question": h["question"].strip()[:300],
                    "status": h.get("status") if isinstance(h.get("status"), str) else "",
                    "program": h.get("program") if isinstance(h.get("program"), str) else ""})
    return out[-MAX_HISTORY:]


def clarify(question, history):
    """AI(질문정리). 돌려주는 값: 대조를 거친 plan 또는 None(실패·형식 오류 → v1 경로)."""
    if history:
        lines = [f"{i}. 후배: {h['question']} → BOO: {STATUS_WORD.get(h['status'], h['status'] or '?')}"
                 + (f" ({h['program']})" if h["program"] else "") for i, h in enumerate(history, 1)]
        prev = "\n".join(lines)
    else:
        prev = "(없음)"
    try:
        r = _call("질문정리", f"이전 대화:\n{prev}\n이번 말: {question}\n출력:")
    except Exception:   # 시험용 가짜 callAI가 모르는 작업이어도 v1 경로로
        return None
    j = r.get("json") if r.get("ok") else None
    if not isinstance(j, dict) or j.get("의도") not in INTENTS:
        return None

    def names(key):
        found = []
        for s in j.get(key) if isinstance(j.get(key), list) else []:
            if isinstance(s, str):
                for n in match_programs(s) or ([s] if s in PROGRAMS else []):
                    if n not in found:
                        found.append(n)
        return found[:3]

    country = j.get("나라") if isinstance(j.get("나라"), str) and j.get("나라") in COUNTRIES else None
    section = j.get("칸") if isinstance(j.get("칸"), str) and j.get("칸") in ALL_SECTIONS else None
    asked = j.get("정리된질문") if isinstance(j.get("정리된질문"), str) else ""
    asked = asked.strip()[:300] or question
    return {"의도": j["의도"], "분야": j.get("분야") if j.get("분야") in FIELDS else None, "나라": country,
            "프로그램후보": names("프로그램후보"), "제외": names("제외"), "칸": section, "정리된질문": asked}


ALL_SECTIONS = {s for f in notes.FRAMES.values() for s in f.get("칸", [])} | set(SECTION_BY_ITEM.values())


# ── ② [v2] 대화·탐색 ──────────────────────────────────────────────────
FIELD_NOUN = {"국제교류": "교환·파견 해봤노트", "현장실습": "현장실습 해봤노트", "비교과": "비교과 해봤노트"}


def _chat(plan, history):
    """status "chat": AI가 쓰지 않는 고정 문구 + 칩. 질문함에 저장하지 않는다(답할 질문이 아님)."""
    last = history[-1] if history else None
    program = (plan["제외"] or [None])[0] or (last["program"] if last and last["program"] else None)
    field = plan["분야"] or (PROGRAMS.get(program, {}).get("분야") if program else None)
    chips = []
    if program:
        message = f"아까는 {program} 이야기였어요. 다른 {FIELD_NOUN.get(field, '해봤노트')}를 찾아볼까요?"
        chips.append({"label": "다른 노트 보기", "action": "notes", "payload": {"field": field, "exclude": [program]}})
    elif last and last["status"] == "hold":
        message = "아직 그 내용을 들려준 선배가 없어서 질문함에 담아 두었어요. 선배가 답하면 알림으로 알려 드릴게요."
        chips.append({"label": "닮은선배 보기", "action": "ask", "payload": {}})
    elif last and last["status"] == "notes":
        message = "방금 보여 드린 노트 목록이 맞지 않았나요? 궁금한 프로그램 이름이나 주제(기숙사·비용·업무 등)를 적어 주시면 그 노트로 답해 드릴게요."
        chips.append({"label": "해봤노트 둘러보기", "action": "notes", "payload": {"field": field}})
    else:
        message = "무엇이 궁금한지 조금 더 구체적으로 물어봐 주세요. 예: 「마르부르크 기숙사 어땠어요?」"
        chips.append({"label": "해봤노트 둘러보기", "action": "notes", "payload": {"field": field}})
    chips.append({"label": "질문함에 담기", "action": "save", "payload": {"question": plan["정리된질문"]}})
    return {"status": "chat", "lines": [], "sources": {}, "suggestSenior": False, "message": message, "chips": chips}


def _kinds():
    return sorted({p["세부"] for p in PROGRAMS.values() if p.get("분야") == "현장실습" and p.get("세부")})


def _explore(plan, programs, country):
    """탐색·사람찾기: 답을 만들지 않고 노트 카드(최대 5, 근거 많은 순)로 안내한다. 현장실습을 나라로 물으면 기관 유형 칩."""
    field = plan["분야"]
    if field == "현장실습" and country and not programs:
        return {"status": "notes", "lines": [], "sources": {}, "suggestSenior": True, "notes": [], "kinds": _kinds(),
                "message": "현장실습 노트는 나라가 아니라 기관 유형으로 나뉘어요. 궁금한 유형을 골라 보세요."}
    if not programs and field:
        pool = [n for n, p in PROGRAMS.items() if p.get("분야") == field and n not in plan["제외"]
                and (not country or p.get("세부") == country) and evidence_count(n)]
        programs = sorted(pool, key=evidence_count, reverse=True)[:MAX_NOTES]
    if not programs:
        return None
    found = _notes(programs, country)
    if found and plan["제외"] and len(found["notes"]) > 1:
        found["message"] = f"{', '.join(plan['제외'])}을(를) 뺀 {FIELD_NOUN.get(field, '해봤노트')}가 {len(found['notes'])}개 있어요. 궁금한 노트를 골라 보세요."
    return found


# ── ① 프로그램 대조 ───────────────────────────────────────────────────
def match_programs(question):
    q = _norm(question)
    hits = [(t, name) for t, name, is_alias in _TERMS if t in q and (not is_alias or _alias_ok(t, q))]
    keep = [(t, name) for t, name in hits if not any(t != t2 and t in t2 for t2, _ in hits)]
    found = sorted({name for _, name in keep})
    if found:
        return found
    # 작업 81: 인턴 사전 data/intern-keywords.json
    #   {"문맥": [...], "약칭제외": [...], "약칭": {키워드: [업체명...]}, "직군": {...}, "기관유형": {...}}
    # 원본 규칙은 tools/build_intern_keywords.py의 match()(원우) — 바꾸면 두 곳을 같이 바꾼다.
    #   ① [11/23] "약칭"(KOTRA·코트라 → 권역 3곳)은 문맥 말 없이도 본다.
    #      단 질문에 "약칭제외" 말(목록에 없는 권역·탐방)이 있으면 약칭은 보지 않는다(함정 33 「아시아 권역」은 보류).
    #      "직군"·"기관유형"은 질문에 인턴 문맥 말(인턴·현장실습 등)이 있을 때만 본다
    #   ② 겹치는 키워드는 긴 것만 남기고, 긴 키워드의 업체부터 담는다
    kw = INTERN_KEYWORDS if isinstance(INTERN_KEYWORDS, dict) else {}
    groups = []
    if not any(_norm(b) and _norm(b) in q for b in kw.get("약칭제외", [])):
        groups.append("약칭")
    if any(_norm(c) and _norm(c) in q for c in kw.get("문맥", [])):
        groups += ["직군", "기관유형"]
    hits = [(_norm(w), names) for g in groups
            for w, names in (kw.get(g) or {}).items() if _norm(w) and _norm(w) in q]
    hits = [(t, names) for t, names in hits if not any(t != t2 and t in t2 for t2, _ in hits)]
    for t, names in sorted(hits, key=lambda h: -len(h[0])):
        names = [names] if isinstance(names, str) else list(names)
        found += [n for n in names if n in PROGRAMS and n not in found]
    return found[:3]


SCHOOL_NAME = re.compile(r"\S(?:대학교|대학|대)(?:\s|에서|에|은|는|이|가|을|를|의|로|$)|university", re.I)


def match_country(question):
    """[11/23] 돌려주는 값: (나라, 그 나라 프로그램 중 근거가 있는 것 — 근거 많은 순). 못 찾으면 (None, []).
    「독일어」「일본어」처럼 언어 이름은 나라로 보지 않는다(독일어과 학생의 비교과 질문이 독일 교환으로 가지 않게).
    질문에 학교 이름(…대학교·…대학)이 있는데 ①에서 못 찾았으면 목록에 없는 학교이므로 나라로 넘기지 않는다
    (함정 53 「남스웨덴공과대학교」 → 스웨덴의 다른 학교로 답하면 안 됨, 보류)."""
    if SCHOOL_NAME.search(question):
        return None, []
    for c in sorted(COUNTRIES, key=len, reverse=True):
        if re.search(re.escape(c) + r"(?!어)", question):
            names = [n for n in COUNTRIES[c] if evidence_count(n)]
            return c, sorted(names, key=evidence_count, reverse=True)
    return None, []


def evidence_count(name):
    """노트 커버의 evidenceCount와 같은 셈: 보고서 문단 + 동의 통과 인터뷰 문장(spec 5장)."""
    return len(EVIDENCE.get(name, [])) + len(notes.interview_lines(name))


def has_topic(question):
    return any(re.search(pattern, question) for pattern, _ in TOPICS_EXCHANGE)


def _notes(programs, country):
    """status "notes": 답을 만들지 않고 해봤노트 카드로 안내한다(질문함에 저장하지 않음 — 답할 질문이 아니라 길 안내)."""
    cards = [{"noteId": notes.note_id(n), "program": n, "country": PROGRAMS.get(n, {}).get("세부") if
              PROGRAMS.get(n, {}).get("분야") == "국제교류" else None, "evidenceCount": evidence_count(n),
              "oneLine": (notes.NOTES.get(notes.note_id(n)) or {}).get("oneLine", ""),   # [v2] 카드 한 줄(사전 생성 노트 커버)
              # [11/23 노트] 카드 띠용 노트 종류(교환·파견·인턴·비교과) — listNotes 카드의 type과 같은 값
              "type": (notes.NOTES.get(notes.note_id(n)) or {}).get("type") or notes._kind(n)}
             for n in programs if evidence_count(n)][:MAX_NOTES]
    if not cards:
        return None
    if len(cards) == 1:
        message = f"{cards[0]['program']} 해봤노트에서 선배들의 경험을 볼 수 있어요. 궁금한 내용을 물어보셔도 돼요."
    else:
        message = f"{country or '관련'} 해봤노트가 {len(cards)}개 있어요. 궁금한 노트를 골라 보세요."
    return {"status": "notes", "lines": [], "sources": {}, "notes": cards, "suggestSenior": True, "message": message}


# ── ② 근거 추출 ───────────────────────────────────────────────────────
def extract(question, programs, section_hint=None):
    """돌려주는 값: (후보 문장 목록, 대표 칸, 보류 이유). section_hint: [v2] 질문정리가 고른 칸(주제어가 없을 때 문항으로 쓴다)"""
    rows, section = [], None
    loose, loose_names = [], set()   # 주제어 없는 국제교류 질문의 후보 문단(겹치는 말로 고른다)
    for name in programs:
        ev = EVIDENCE.get(name, [])
        iv = notes.interview_lines(name)            # 최근 동의 먼저. 후보 상한(30)에 밀리지 않게 앞에 둔다
        if not ev and not iv:
            continue
        if PROGRAMS.get(name, {}).get("분야") == "현장실습":
            if INTERVIEW_ONLY_INTERN.search(question):
                only = [r for r in iv if r["칸"] in ("근무조건", "지원·선발")]
                if not only:
                    return [], "근무조건", "인터뷰로만 채우는 칸(근무조건)"
                section = section or "근무조건"
                rows += only
                continue
            rows += iv + ev
        else:
            items = []
            for pattern, nums in TOPICS_EXCHANGE:
                if re.search(pattern, question):
                    items += [n for n in nums if n not in items]
            if not items and section_hint:   # [v2] 주제어는 없지만 질문정리가 칸을 알면 그 칸의 문항으로
                items = [i for i, s in SECTION_BY_ITEM.items() if s == section_hint]
            if not items:
                # [11/23 원우 #151 ③] 주제어가 없어도 바로 보류하지 않는다. 그 프로그램 근거 중 질문과 겹치는 말이 있는
                # 문장을 고르기 AI에 넘기고, 관련 없으면 AI가 비운다(→ 보류). 겹치는 말이 하나도 없으면 지금처럼 보류.
                loose += iv + ev   # [v2 작업 89] 후배 질문 답도 그 칸의 일반 문장
                loose_names.add(name)
                continue
            section = section or SECTION_BY_ITEM.get(items[0])
            sections = {SECTION_BY_ITEM.get(i) for i in items}
            rows += [r for r in iv if r["칸"] in sections]
            rows += [e for e in ev if e["문항"].split(".")[0] in items]
    cands, keys = [], set()

    def add(e, s):
        key = _norm(FILLER_RE.sub("", s)).rstrip(".!?~")
        if len(key) < 6 or key in keys:
            return
        keys.add(key)
        cands.append({"text": s, "sourceId": e["id"], "docType": e["docType"],
                      "program": e["프로그램명"], "semester": e.get("semester")})

    for e in rows:
        for s in split_sentences(e["text"]):
            add(e, s)
            if len(cands) >= MAX_CANDIDATES:
                return cands, section, ""
    if loose:   # 주제어 없는 질문: 겹치는 말이 많은 문장부터(같으면 원래 순서 = 최근 학기 순)
        qb = _bigrams(question, loose_names)
        scored = []
        for e in loose:
            for s in split_sentences(e["text"]):
                n = len(qb & _bigrams(s))
                if n:
                    scored.append((-n, len(scored), e, s))
        for _, _, e, s in sorted(scored, key=lambda x: x[:2]):
            add(e, s)
            if len(cands) >= MAX_CANDIDATES:
                break
    if not cands:
        has_any = any(EVIDENCE.get(n) or notes.interview_lines(n) for n in programs)
        return [], section, "보고서 칸에 없는 주제" if has_any else "근거 없음"
    return cands, section, ""


# 겹침을 셀 때 빼는 두 글자(말투·조사·흔한 말 — 내용이 아님)
_COMMON_BIGRAMS = {"어요", "해요", "에요", "예요", "이에", "있어", "없어", "했어", "었어", "았어", "나요", "까요", "세요", "습니", "니다",
                   "는데", "에서", "으로", "하는", "하고", "하면", "해서", "이랑", "이나", "정도", "많이", "어떻", "떻게", "어때", "어땠",
                   "선배", "후배", "다녀", "녀온", "가면", "가서", "있는", "없는", "그냥", "진짜", "혹시", "궁금", "금해", "뭐예", "무엇",
                   "얼마", "언제", "어디", "누가", "할수", "수있", "같아", "같은", "이런", "그런", "저는", "제가", "우리", "학교", "대학"}


def _bigrams(text, names=()):
    """한글·영문 낱말 안의 두 글자 묶음. names(프로그램 이름·별칭)는 먼저 지운다 — 학교 이름이 겹친다고 관련 문장은 아니다."""
    for n in names:
        for w in [n] + list(PROGRAMS.get(n, {}).get("별칭") or []):
            text = text.replace(w, " ")
    out = set()
    for w in re.findall(r"[가-힣A-Za-z]{2,}", text):
        out |= {w[i:i + 2].lower() for i in range(len(w) - 1)}
    return out - _COMMON_BIGRAMS - _FREQUENT_BIGRAMS


# 전체 근거에서 너무 흔한 두 글자(「학기」·「현지」 등 — 근거 문장의 1.5% 넘게 나옴)는 겹침으로 세지 않는다.
# 시연 0:40 「학기 중 현지 인턴 병행할 수 있어요?」가 흔한 말만으로 엉뚱한 근거를 받지 않게(그 질문은 보류돼야 한다).
_FREQUENT_BIGRAMS = set()


def _frequent_bigrams(ratio=0.015):
    from collections import Counter
    sents = [s for v in EVIDENCE.values() for e in v for s in split_sentences(e["text"])]
    df = Counter(b for s in sents for b in _bigrams(s))
    return {b for b, n in df.items() if n > len(sents) * ratio}


def split_sentences(text):
    parts = re.split(r"(?<=[.!?])\s+|(?<=ㅎㅎ)\s+", text.strip())
    return [p.strip() for p in parts if p.strip() and p.strip() not in ("ㅎㅎ",)]


# ── ③ 고르기 ──────────────────────────────────────────────────────────
def _call(작업명, content):
    system, shots = load_prompt(f"askBoo-{작업명}")   # docs/prompts/askBoo-고르기.txt 등
    return callAI(작업명, shots + [{"role": "user", "content": content}], system=system)


# Max tokens 30에서 목록이 잘린 경우: '{"관련":[1,2,3' 처럼 정해진 모양의 앞부분만 있을 때
_TRUNCATED_PICK = re.compile(r'^\s*\{\s*"관련"\s*:\s*\[\s*(\d+(?:\s*,\s*\d+)*)\s*,?\s*$')
# [11/23] HCX가 빈 목록에서 닫는 괄호만 빠뜨린 경우: '{"관련":[]' — 형식 오류가 아니라 「고른 근거 없음」
_EMPTY_PICK = re.compile(r'^\s*\{\s*"관련"\s*:\s*\[\s*\]\s*\}?\s*$')


def pick(question, cands):
    numbered = "\n".join(f"{i}. {c['text']}" for i, c in enumerate(cands, 1))
    r = _call("고르기", f"질문: {question}\n근거:\n{numbered}\n출력:")
    if not r["ok"]:
        return [], "AI 호출 실패"
    j = r.get("json")
    if isinstance(j, dict) and isinstance(j.get("관련"), list):
        chosen = j["관련"]
    elif _EMPTY_PICK.match(r["text"] or ""):
        chosen = []
    else:
        m = _TRUNCATED_PICK.match(r["text"])
        if not m:
            return [], "고르기 형식 오류"
        chosen = re.findall(r"\d+", m.group(1))[:-1]   # 마지막 숫자는 잘렸을 수 있어 버린다
    nums = []
    for n in chosen:
        try:
            n = int(n)
        except (TypeError, ValueError):
            continue
        if 1 <= n <= len(cands) and n not in nums:   # 없는 번호는 버린다
            nums.append(n)
    if not nums:
        return [], "AI가 고른 근거 없음"
    return [cands[n - 1] for n in nums[:MAX_PICK]], ""


# ── ⑤ [v2] 답쓰기 + ⑥ 검증 ───────────────────────────────────────────
DOC_WORD = {"귀국보고서": "결과보고서", "현장실습후기": "현장실습후기", "인터뷰": "선배 인터뷰"}


def _person_of(source_id):
    """근거 문장을 쓴 사람의 열쇠(화면에 안 나감). 보고서·후기는 문서 번호(R149-1-1 → R149), 인터뷰 문장은 문장마다."""
    m = re.match(r"([RI]\d+)-", source_id or "")
    return m.group(1) if m else source_id


def _single_senior(source_ids):
    return len({_person_of(s) for s in source_ids}) <= 1


def verify_facts(sentence, source):
    """답쓰기 문장용 검증: 숫자·영문·고유명사·수량만 본다(「새 낱말」·길이는 바꿔 쓰기를 허용하므로 답검사가 대신 본다)."""
    return [p for p in verify(sentence, source) if not p.startswith(("새 낱말", "원문보다"))]


def match_check(source, sentence):
    """AI(답검사, Opus): 답 문장이 인용 근거 원문과 맞는지. 인터뷰 일치검사와 달리 BOO가 전하는 말투(「~라는 선배도 있었어요」)는 일치.
    호출 실패·형식 오류는 불일치로 본다(문장을 버림 → 다 버려지면 원문 인용 폴백)."""
    try:
        r = _call("답검사", f"원문: {source}\n답: {sentence}\n출력:")
    except Exception:
        return False
    j = r.get("json")
    return bool(r.get("ok") and isinstance(j, dict) and j.get("일치") is True)


def compose(question, picked):
    """AI(답쓰기) → 문장마다 인용 근거와 대조. 돌려주는 값: {"status","lines","sources","singleSenior"} 또는 None(다 버려짐·실패)."""
    letters, numbered = {}, []
    for i, c in enumerate(picked, 1):
        who = _person_of(c["sourceId"])
        if who not in letters:
            letters[who] = chr(ord("A") + len(letters)) if len(letters) < 26 else str(len(letters) + 1)
        year = str(c.get("semester") or "")[:4] or "–"
        numbered.append(f"[{i}] {DOC_WORD.get(c['docType'], c['docType'])} · {year} · 선배{letters[who]}: {c['text']}")
    try:
        r = _call("답쓰기", f"질문: {question}\n근거:\n" + "\n".join(numbered) + "\n출력:")
    except Exception:
        return None
    j = r.get("json") if r.get("ok") else None
    answers = j.get("답") if isinstance(j, dict) else None
    if not isinstance(answers, list):
        return None
    todo = []   # (문장, 인용 근거) — 코드 검증을 통과한 것만 일치검사로
    for a in answers:
        if not isinstance(a, dict) or not isinstance(a.get("text"), str):
            continue
        text = a["text"].strip()
        nums = []
        for n in a.get("근거") if isinstance(a.get("근거"), list) else []:
            try:
                n = int(n)
            except (TypeError, ValueError):
                continue
            if 1 <= n <= len(picked) and n not in nums:
                nums.append(n)
        if not text or not nums or not POLITE_END.search(text):   # 근거 번호 없는 문장·반말은 버린다
            continue
        cited = [picked[n - 1] for n in nums]
        if verify_facts(text, " ".join(c["text"] for c in cited)):
            continue
        todo.append((text, cited))
        if len(todo) >= MAX_ANSWER_LINES:
            break
    if not todo:
        return None
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(MAX_ANSWER_LINES) as pool:   # 일치검사는 문장별로 동시에(인터뷰 요약과 같은 방식)
        matched = list(pool.map(lambda tc: match_check(" ".join(c["text"] for c in tc[1]), tc[0]), todo))
    lines, sources, used = [], {}, set()
    for (text, cited), ok in zip(todo, matched):
        if not ok:
            continue
        cites = []
        for c in cited:
            if c["sourceId"] not in cites:
                cites.append(c["sourceId"])
            sources[c["sourceId"]] = {"docType": c["docType"], "program": c["program"], "semester": c["semester"]}
        lines.append({"text": text, "sourceId": cites[0], "cites": cites, "lineId": f"L-A1-{len(lines) + 1}"})
        used.update(cites)
    if not lines:
        return None
    return {"status": "ok", "lines": lines, "sources": sources, "singleSenior": _single_senior(used)}


# ── ④ 변환 + ⑤ 사후 검증 ─────────────────────────────────────────────
def convert(source):
    """돌려주는 값: (문장, 폴백 여부). 형식·말투가 틀리거나 검증에 걸리면 원문을 쓴다."""
    cleaned = clean_source(source)
    if POLITE_END.search(cleaned):
        # [11/23 작업 30] 군말만 지우면 이미 해요체·합쇼체인 문장은 AI에 보내지 않는다(낱말 0개 변경, 폴백 아님).
        # 11/22 HCX 측정에서 폴백 45줄 중 41줄이 이런 문장이었다 — 바꿀 게 없는데 AI가 말을 바꿔 검증에 걸렸다.
        return cleaned, False
    r = _call("변환", f"근거: {source}\n출력:")
    j = r.get("json")
    text = None
    if r["ok"] and isinstance(j, dict) and len(j) >= 1:
        v = j.get("1", next(iter(j.values())))
        if isinstance(v, str):
            text = v.strip()
    if not text or not POLITE_END.search(text) or verify(text, source):
        return cleaned, True
    return text, False


POLITE_END = re.compile(r"(요|니다)[.!?~]*$")   # 해요체·합쇼체로 끝나야 한다(반말이면 폴백)


def clean_source(s):
    """폴백 문장: 원문에서 앞머리 군말과 'ㅎㅎ'·'!!'만 지운다. 낱말은 바꾸지 않는다."""
    s = re.sub(r"\s*ㅎㅎ\s*", " ", s)
    s = re.sub(r"!{2,}", ".", s)
    s = FILLER_RE.sub("", s.strip())
    return s.strip() or s


NUM_WORD_RE = re.compile(r"(?<![가-힣])(한|두|세|네|다섯|여섯|일곱|여덟|아홉|열)\s*(달|주|개월|번|명|시간|학기|해|살|군데|가지|장)")


def verify(sentence, source):
    """원문에 없는 내용이 있으면 이유 목록(글자)을 돌려준다. 빈 목록이면 통과. AI를 쓰지 않는다."""
    problems = []
    src, src_n = source.lower(), _norm(source)
    for num in re.findall(r"\d+(?:[.,]\d+)?", sentence):
        if num not in source:
            problems.append(f"숫자 {num}")
    for w in re.findall(r"[A-Za-z][A-Za-z\-]+", sentence):
        if w.lower() not in src:
            problems.append(f"영문 {w}")
    for m in NUM_WORD_RE.finditer(sentence):
        if _norm(m.group(0)) not in src_n:
            problems.append(f"수량 {m.group(0)}")
    s_n = _norm(sentence)
    for noun in PROPER_NOUNS:
        if _norm(noun) in s_n and _norm(noun) not in src_n:
            problems.append(f"고유명사 {noun}")
    # 새 내용어: 두 글자 이상 낱말의 앞 두 글자가 원문에 없으면 새로 생긴 말로 본다(어미 변화는 허용)
    new = [w for w in re.findall(r"[가-힣]{2,}", sentence) if w[:2] not in src_n and w[:2] not in _STYLE_OK]
    if len(new) >= 2:
        problems.append("새 낱말 " + ",".join(new))
    if len(sentence) > len(source) + 15:
        problems.append("원문보다 많이 김")
    return problems


# 해요체로 바꿀 때 새로 생기는 말투 조각(내용이 아님)
_STYLE_OK = {"해요", "돼요", "있어", "없어", "좋아", "거예", "이에", "예요", "에요", "세요", "했어", "됐어", "봤어", "가요",
             "와요", "줘요", "져요", "워요", "이어", "어요", "아요", "편이", "수월", "그래"}


# ── 응답 만들기 ───────────────────────────────────────────────────────
def _official(me, question, programs, save):
    code = PROGRAMS.get(programs[0], {}).get("운영부서코드") if programs else None
    if not code:
        code = "D02" if re.search(r"현장실습|인턴", question) else "D03" if re.search(r"특교원|탄뎀", question) else "D01"
    dept = DEPTS.get(code, {})
    qid = _save(me, question, programs[0] if programs else None, None, "official", save)
    return {"status": "official", "lines": [], "sources": {}, "questionId": qid, "suggestSenior": False,
            "officialUrl": dept.get("공식안내URL", ""),
            "message": f"학교 규정에 관한 질문이라 {dept.get('부서명', '담당 부서')} 공식 안내에서 정확한 내용을 확인해 주세요."}


def _hold(me, question, program, section, save, why=""):
    qid = _save(me, question, program, section, "hold", save)
    if why == "담기":
        message = HOLD_SAVED
    elif not program:
        message = HOLD_NO_PROGRAM
    elif evidence_count(program):     # 노트는 있는데 이 내용만 없다 → 그 노트로 갈 수 있게 noteId도 준다
        message = HOLD_NO_TOPIC.format(program=program)
    else:
        message = HOLD_MESSAGE
    out = {"status": "hold", "lines": [], "sources": {}, "questionId": qid, "suggestSenior": True, "message": message}
    if program and evidence_count(program):
        out["noteId"] = notes.note_id(program)
    if not save:
        out["_why"] = why   # 평가 스크립트에서만 보이는 보류 이유
    return out


def _save(me, question, program, section, status, save):
    if not save:
        return None
    from runtime_fns import add_question
    return add_question(me, question, program=program, section=section, status=status)


_FREQUENT_BIGRAMS.update(_frequent_bigrams())   # 근거를 다 읽은 뒤 한 번만 센다
