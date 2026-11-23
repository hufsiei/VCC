# askboo.py — askBoo(question) 4+1단계 (작업 18, 작성: 미리)
#
# 기준: docs/spec-v1.md 4장 askBoo · docs/HCX-원칙-v2.md 3~5절 · 작업내역 18번 세부
#   ①′ 코드: 규정 질문 판별 → status "official" (AI 없음, spec 4장 판별 표현)
#   ①  코드: 프로그램명·별칭 대조 (tools/check_alias_match.py와 같은 규칙, 긴 이름 우선)
#        실패하면 data/intern-keywords.json(작업 81, 있을 때만)으로 업체 1~3개. 그래도 없으면 hold
#   ②  코드: 근거 추출 — 질문 주제어 → 보고서 문항으로 좁히고, 문단을 문장으로 쪼개 같은 문장은 하나만
#        근거 풀 = evidence.json + 공개 동의를 통과한 인터뷰 문장(notes.interview_lines, 작업 26·74).
#        인터뷰 문장은 주제어의 칸과 같은 칸 문장, 그리고 「후배 질문」 칸의 A 문장(주제어가 없어도 후보)
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

MAX_LINES = 3        # 답변 문장 수 상한 (spec 8장: 출처 달린 문장 3개)
MAX_CANDIDATES = 30  # 고르기에 넣는 문장 수 상한 (최근 학기 순)

HOLD_MESSAGE = "이 부분은 아직 경험한 선배가 없어요. 질문함에 담아 두었어요. 닮은 선배에게 물어볼까요?"
# [11/23] 보류 이유별 문구 — 노트가 있는데 「경험한 선배가 없어요」라고 하지 않는다(미리 실사용)
HOLD_NO_PROGRAM = "질문에 맞는 해봤노트를 찾지 못했어요. 질문함에 담아 두었어요. 닮은 선배에게 물어볼까요?"
HOLD_NO_TOPIC = "{program} 해봤노트에는 아직 이 내용이 없어요. 질문함에 담아 두었어요. 닮은 선배에게 물어볼까요?"
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
               "경영", "경제", "국립", "주립", "시립", "가톨릭", "카톨릭", "사범", "교육", "외국어", "신학")
SCHOOL_TAIL = re.compile(r"(?:" + "|".join(SCHOOL_KIND) + r")(?:대학교|대학|대)")


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
    """local_fn.py가 부른다. save=False면 질문함에 저장하지 않는다(평가 스크립트용)."""
    question = (payload.get("question") or "").strip()
    if not question:
        return {"error": "질문을 입력해 주세요"}
    if len(question) > 300:
        return {"error": "질문은 300자 안으로 적어 주세요"}

    programs = match_programs(question)
    country = None
    if not programs:                       # [11/23] 프로그램명이 없으면 나라 이름으로(근거 많은 순)
        country, programs = match_country(question)

    # ①′ 규정 질문 → 공식 안내
    if OFFICIAL_RE.search(question):
        return _official(me, question, programs, save)

    # ① 프로그램이 없으면 보류
    if not programs:
        return _hold(me, question, None, None, save, why="프로그램 없음")

    # ①″ [11/23] 사람을 찾는 질문이나 나라만 말한 질문인데 주제어가 없으면 → 해봤노트 카드로 안내(AI 없음)
    if not has_topic(question) and (PERSON_RE.search(question) or country):
        found = _notes(programs, country)
        if found:
            return found

    # ② 근거 추출
    cands, section, why = extract(question, programs)
    if not cands:
        return _hold(me, question, programs[0], section, save, why=why)

    # ③ 고르기
    picked, why = pick(question, cands)
    if not picked:
        return _hold(me, question, programs[0], section, save, why=why)

    # ④ 변환 + ⑤ 사후 검증
    lines, sources, seen, texts = [], {}, {}, set()
    for c in picked:
        text, fallback = convert(c["text"])
        if _norm(text) in texts:   # 다른 보고서의 같은 문장은 한 번만
            continue
        texts.add(_norm(text))
        sid = c["sourceId"]
        seen[sid] = seen.get(sid, 0) + 1
        line = {"text": text, "sourceId": sid, "lineId": f"L-{sid}" if seen[sid] == 1 else f"L-{sid}.{seen[sid]}"}
        if fallback:
            line["fallback"] = True   # AI 문장을 버리고 근거 원문을 그대로 보여 준 줄(화면: 「근거 원문 보기」)
        lines.append(line)
        sources[sid] = {"docType": c["docType"], "program": c["program"], "semester": c["semester"]}

    main_program = picked[0]["program"]
    return {"status": "ok", "lines": lines, "sources": sources,
            "noteId": notes.note_id(main_program), "suggestSenior": False}


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
              PROGRAMS.get(n, {}).get("분야") == "국제교류" else None, "evidenceCount": evidence_count(n)}
             for n in programs if evidence_count(n)][:MAX_NOTES]
    if not cards:
        return None
    if len(cards) == 1:
        message = f"{cards[0]['program']} 해봤노트에서 선배들의 경험을 볼 수 있어요. 궁금한 내용을 물어보셔도 돼요."
    else:
        message = f"{country or '관련'} 해봤노트가 {len(cards)}개 있어요. 궁금한 노트를 골라 보세요."
    return {"status": "notes", "lines": [], "sources": {}, "notes": cards, "suggestSenior": True, "message": message}


# ── ② 근거 추출 ───────────────────────────────────────────────────────
def extract(question, programs):
    """돌려주는 값: (후보 문장 목록, 대표 칸, 보류 이유)"""
    rows, section = [], None
    for name in programs:
        ev = EVIDENCE.get(name, [])
        iv = notes.interview_lines(name)            # 최근 동의 먼저. 후보 상한(30)에 밀리지 않게 앞에 둔다
        answers = [r for r in iv if r["칸"] == notes.QUESTION_SECTION]   # 후배 질문의 A 문장
        if not ev and not iv:
            continue
        if PROGRAMS.get(name, {}).get("분야") == "현장실습":
            if INTERVIEW_ONLY_INTERN.search(question):
                only = [r for r in iv if r["칸"] in ("근무조건", "지원·선발", notes.QUESTION_SECTION)]
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
            if not items:
                rows += answers   # 보고서 칸에 없는 주제는 후배 질문 답만 후보(고르기 AI가 관련 없으면 비운다)
                continue
            section = section or SECTION_BY_ITEM.get(items[0])
            sections = {SECTION_BY_ITEM.get(i) for i in items}
            rows += [r for r in iv if r["칸"] in sections or r["칸"] == notes.QUESTION_SECTION]
            rows += [e for e in ev if e["문항"].split(".")[0] in items]
    if not rows:
        has_any = any(EVIDENCE.get(n) or notes.interview_lines(n) for n in programs)
        return [], section, "보고서 칸에 없는 주제" if has_any else "근거 없음"

    cands, keys = [], set()
    for e in rows:
        for s in split_sentences(e["text"]):
            key = _norm(FILLER_RE.sub("", s)).rstrip(".!?~")
            if len(key) < 6 or key in keys:
                continue
            keys.add(key)
            cands.append({"text": s, "sourceId": e["id"], "docType": e["docType"],
                          "program": e["프로그램명"], "semester": e.get("semester")})
            if len(cands) >= MAX_CANDIDATES:
                return cands, section, ""
    return cands, section, ""


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
    return [cands[n - 1] for n in nums[:MAX_LINES]], ""


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
    if not program:
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
