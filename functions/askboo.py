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
#   [11/25] ①‴ 코드: 여러 곳 비교 질문(「다른 지역 대비」「어디가 더」) → status "notes" 고정 안내 + 그 나라 노트 카드(AI 없음).
#   [11/25 Q-13] ①⁗ 코드: 앞 답에 대한 후속(「이게 다야?」「기준이 뭐야」) → "chat" 노트 수·고른 기준 /
#        시기 질문(「인턴 보통 언제 해요?」) → "notes" 근거 보고서의 학기별 편수 + 카드(AI 없음). 기록(askLog)에 판단값·앞 턴.
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
# [11/26 A안, 플래그 VCC_ASK_FULL=1 — 기본 0은 위 길 그대로. 11/29 측정으로 확정, 그때까지 옛 길 코드는 지우지 않는다]
#   ②′ 코드: 추출·고르기(HCX)를 건너뛰고 프로그램 근거 전문(보고서·후기 문단 + 공개 동의 인터뷰 문장, full_evidence)을
#        두 단계 번호(문단 [3], 문장 [3-1])로 답쓰기-전문(Sonnet)에 넘긴다. 근거 전문은 프롬프트 캐시(ai.py cache, 5분).
#   ⑥′ 코드 검사(verify_facts) 대조 원문 = 지목 문장 + 같은 문단 앞뒤 한 문장. Opus 답검사 = 문단 전체, 지목 문장에 ▶.
#        다 버려지면 답쓰기가 가리킨 원문 문장을 인용(fallback_lines → 변환 HCX). 답쓰기가 실패하면 위 옛 길로.
#
# AI는 ai.py의 callAI로만 부른다. 프롬프트 원문은 docs/prompts/askBoo-고르기.txt, askBoo-변환.txt.
# hold·official 질문은 runtime_fns.add_question으로 질문함에 저장한다.
import json
import os
import re
from pathlib import Path

import notes
from ai import callAI, load_prompt

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

MAX_LINES = 3        # 폴백(원문 인용) 문장 수 상한 (spec 8장: 출처 달린 문장 3개)
MAX_PICK = 8         # [v2] 고르기가 고르는 문장 수 상한 — 답쓰기에 넣는 근거
MAX_ANSWER_LINES = 4 # [v2] 답쓰기 문장 수 상한
MAX_ANSWER_LINES_FULL = 6   # [11/26 A안] 전문 길의 답 문장 수 상한(질문에 맞게 2~6)
FULL_CHAR_CAP = 20000       # [11/26 A안] 전문 길 근거 글자 수 안전 상한(가장 큰 프로그램 약 1.5만 자). 넘으면 오래된 학기부터 뺀다
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
HOLD_EXTRA_TAIL = "질문함에 담아 두었어요. 닮은 선배에게 물어볼까요?"   # [작업 106] 비교과 사실 답 뒤
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
    if local_scope(question):   # [11/26 Q-38] 현지·파견 대학 이야기·수강 경험 말투는 규정이 아니다(아래 「데이터」 뒤 정의)
        return False
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
    # [11/26 Q-38] 학비·학기 등록비(독일 노트 「학기 등록만 하면 교통권 포함」은 2-2에 있다)·현지 장학금은 비용 칸
    (r"학비|등록비|수업료|학기\s*등록|장학", ["2-6", "2-2"]),
    (r"몇\s*학점\s*(을|씩|정도|쯤)?\s*(들|수강)", ["2-2", "2-3"]),   # [Q-38] 「독일 대학교에서 몇 학점 들어?」 — 수강 경험
    (r"학점\s*인정|학점인정|성적\s*인정|학점", ["3", "2-2"]),
    (r"날씨|치안|소매치기|생활(?!비)", ["2-7", "1-3"]),
    (r"조언|한마디|어때|어땠|후기|경험담|팁|해\s*주고\s*싶은|알아\s*두면|후회|아쉬", ["4"]),  # 11/20 원우 제안: '팁' 질문이 보류로 빠지던 것 · 11/23 후회·아쉬움
]
# 현장실습 후기는 칸이 없는 자유 서술이라 전체 문단이 후보. 아래 주제는 인터뷰로만 채우는 칸이라 근거 없음.
INTERVIEW_ONLY_INTERN = re.compile(r"월급|급여|시급|페이|보수|연봉|근무\s*시간|근무\s*조건|복지|휴가|정규직|채용\s*전환")
SECTION_BY_ITEM = {"1-1": "지원", "1-2": "지원", "1-3": "지원", "2-1": "생활", "2-2": "학점", "2-3": "학점",
                   "2-4": "생활", "2-5": "생활", "2-6": "비용", "2-7": "생활", "3": "학점", "4": "팁"}

# 문장 앞의 군말 — 같은 문장 찾기(중복 제거)와 clean_source(폴백·변환 건너뛴 문장의 앞머리 군말 지우기)에 쓴다.
# 군말만 지우고 낱말은 바꾸지 않는다.
FILLER_RE = re.compile(r"^(?:(?:참고로|경험상|사실|개인적으로|하나 꼽자면|미리 말해 두면|제 경우엔|지나고 보니|확실히|그리고|진짜|"
                       r"솔직히 말하면|돌이켜 보면|지금 생각해도|그 시기엔|한국과 비교하면|날씨 얘기를 하자면|저는|"
                       # [11/24 작업 87] 가상데이터 말머리 전수 확인으로 추가(덧붙이자면 137·저 같은 경우 31·체감상 22문장 등)
                       r"덧붙이자면|저 같은 경우|체감상|사족이지만|하나 더,)\s*)+")


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

# [11/26 Q-38] 규정 = 외대 제도(학점 인정·외대 장학금·선발·등록금 납부·휴학 등). 같은 낱말이라도 주체가 현지·파견 대학이거나
# (「독일 현지 대학교에서 주는 장학금」) 수강 경험을 묻는 말투(「독일 대학교에서 몇 학점 들어?」)면 선배 경험 질문이다.
# 외대 제도 말(외대·인정·선발·휴학·등록금·국제교류팀 등)이 함께 있으면 주체가 현지여도 그대로 규정
# (「현지에서 들은 학점 인정받을 수 있어요?」). 주체를 말하지 않은 「장학금 얼마예요?」「학점 인정 신청 언제까지?」는 지금처럼 규정.
LOCAL_SUBJECT_RE = re.compile(
    r"현지|자체|DAAD|거기서|거기에서|그\s*(학교|대학)|파견\s*(대학|학교|교)"
    r"|(?:" + "|".join(re.escape(c) for c in sorted(COUNTRIES, key=len, reverse=True) or ["독일"]) + r")\s*(?:의\s*)?(?:대학|학교)",
    re.IGNORECASE)
COURSE_TONE_RE = re.compile(r"몇\s*학점\s*(을|씩|정도|쯤)?\s*(들|수강|신청했|신청해|넣)")
# 기한·자격·배정·발표 등 절차 말도 외대 제도로 본다(보수 — 외대 제도 질문이 근거 길로 가는 쪽이 더 위험)
HUFS_RULE_RE = re.compile(r"외대|본교|우리\s*학교|국제교류팀|인정|선발|배정|휴학|등록금|초과학기|졸업"
                          r"|발표|모집|자격(?!증)|마감|기한|언제까지|중복\s*지원|불이익|페널티|연장")


def local_scope(question):
    """[Q-38] 현지·파견 대학 이야기이거나 수강 경험 말투이고 외대 제도 말이 없으면 True — is_official이 규정으로 보지 않는다."""
    return bool((LOCAL_SUBJECT_RE.search(question) or COURSE_TONE_RE.search(question))
                and not HUFS_RULE_RE.search(question))


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


# ── [11/26 작업 105] 학교 이름 오타·변형 퍼지 대조(코드, AI 없음) ─────────────────
# 국제처 검토: 「마브루크·마부루크·마르브루크·마르브루쿠」가 마르부르크로 안 잡혀 보류로 빠졌다. 별칭으로는 다 못 막는다.
# 규칙(가짜 매칭을 막는 쪽으로 좁게):
#   ① 한글 4글자 이상인 프로그램명·별칭만(3글자 「말라가·밀라노·레이던」은 「말라고·밀리니·레이어로」 같은 보통 말에 걸려서 뺐다). 질문의 한글 덩어리 **첫머리**에서만 본다(낱말 가운데는 안 봄).
#   ② 첫 글자가 같아야 한다(「함부르크」는 「마부르크」와 자모 두 개만 달라도 다른 도시).
#   ③ 자모(초성·중성·종성)로 풀어 편집 거리가 그 이름 자모 수의 30% 이하이고 3 이하. 글자 수 차이는 1까지.
#   ④ 덩어리가 이미 어떤 이름·별칭·나라·도시로 시작하면 보지 않는다(정확한 대조가 먼저).
#   ⑤ 가장 가까운 후보가 서로 다른 프로그램 둘이면(동점) 고치지 않는다.
# 맞으면 그 자리를 이름으로 바꾼 글을 대조에만 쓴다(질문 원문·저장·AI 입력은 그대로).
def _jamo(s):
    out = []
    for ch in s:
        c = ord(ch) - 0xAC00
        if 0 <= c < 11172:
            out += [("초", c // 588), ("중", c % 588 // 28)] + ([("종", c % 28)] if c % 28 else [])
        else:
            out.append(("", ch))
    return out


def _edit(a, b):
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


FUZZY_MIN = 4   # 이름의 한글 글자 수(질문 쪽은 한 글자 모자란 것까지 본다)
_FUZZY = {}     # 첫 글자 → [(이름·별칭, 프로그램명, 자모)]
for _t, _name, _ in _TERMS:
    if re.fullmatch(r"[가-힣]{%d,}" % FUZZY_MIN, _t):
        _FUZZY.setdefault(_t[0], []).append((_t, _name, _jamo(_t)))
_FUZZY_SKIP = None   # ④ 나라·도시 이름(CITIES가 아래에 있어 처음 쓸 때 만든다)


def _fuzzy_skip():
    global _FUZZY_SKIP
    if _FUZZY_SKIP is None:
        words = {t for t, _, _ in _TERMS} | {_norm(w) for w in [*COUNTRIES, *CITY_COUNTRY]}
        _FUZZY_SKIP = sorted((w for w in words if len(w) >= 2), key=len, reverse=True)
    return _FUZZY_SKIP


def fix_names(text):
    """질문 속 학교 이름 오타를 프로그램명·별칭으로 바꾼 글(대조용). 고칠 것이 없으면 그대로."""
    if not text:
        return text
    out, last = [], 0
    for m in re.finditer(r"[가-힣]{%d,}" % (FUZZY_MIN - 1), text):
        run = m.group(0)
        if run[0] not in _FUZZY or any(run.startswith(w) for w in _fuzzy_skip()):
            continue
        best = []   # (거리, 글자 수 차, 이름, 프로그램명, 고칠 글자 수)
        for t, name, tj in _FUZZY[run[0]]:
            for n in range(len(t) - 1, min(len(run), len(t) + 1) + 1):
                d = _edit(_jamo(run[:n]), tj)
                if d <= min(3, int(len(tj) * 0.3)):
                    best.append((d, abs(n - len(t)), t, name, n))
        if not best:
            continue
        best.sort()
        if len({b[3] for b in best if b[:2] == best[0][:2]}) > 1:   # ⑤
            continue
        _, _, t, _, n = best[0]
        out += [text[last:m.start()], t]
        last = m.start() + n
    return "".join(out) + text[last:] if out else text


# 사후 검증용 고유명사 사전: 프로그램명·별칭·국가·부서명 + 자주 지어내는 시험·기관 이름
PROPER_NOUNS = sorted({w for name, p in PROGRAMS.items() for w in [name, *p.get("별칭", []), p.get("세부", "")]
                       if len(_norm(w)) >= 2} |
                      {d["부서명"] for d in DEPTS.values()} |
                      {"괴테", "테스트다프", "토플", "토익", "아이엘츠", "델프", "달프", "에라스무스", "슈뱅", "블로킹"},
                      key=len, reverse=True)


# ── 공개 함수 ─────────────────────────────────────────────────────────
def askBoo(me, payload, save=True):
    """local_fn.py가 부른다. save=False면 질문함에도 답 기록에도 남기지 않는다(평가 스크립트용).
    payload: {question, history?: [{question, status, program?}], force?: "hold"}
    [11/25 작업 33] 답을 만든 뒤 질문과 답을 runtime/askLog.json에 남긴다(_log_answer).
    [11/25 Q-13] 기록에 판단값(질문정리의 의도·분야·칸, 코드가 고른 길)과 바로 앞 턴을 더한다 — judge_asklog.py 채점용."""
    trace = {}
    out = _answer(me, payload, save, trace)
    program = out.pop("_program", None)   # _hold·_official이 넘긴 프로그램(기록용, 응답에는 없음)
    # [11/26 작업 104] 비자·보험·지원 서류·파견 대학 규정 → 답(또는 보류) 끝에 「꼭 확인」 안내 + 담당 연락처. 담기는 빼고
    if out.get("status") in ("ok", "hold") and trace.get("route") != "담기":
        progs = [s.get("program") for s in (out.get("sources") or {}).values()] or ([program] if program else [])
        check = official_check((payload.get("question") or "").strip(), [p for p in progs if p in PROGRAMS])
        if check:
            out["officialCheck"] = check
    if save and "error" not in out:
        history = clean_history(payload.get("history"))
        _log_answer((payload.get("question") or "").strip(), out, program, trace=trace,
                    prev=history[-1] if history else None)
    return out


ASK_LOG_MAX = 2000    # askLog.json에 남기는 최근 답 기록 수(askBoo마다 파일 전체를 읽고 쓰므로 상한을 둔다)
ASK_LOG_SLACK = 200   # 이만큼 더 쌓이면 한 번에 ASK_LOG_MAX건으로 자른다


def _log_answer(question, out, program=None, trace=None, prev=None):
    """답 기록 한 줄: 시각·status·질문·답 문장(cites)·프로그램·안내 문구. **사람 칸은 남기지 않는다**
    (spec 0장 「질문 로그는 학번 제거 후 통계만」 — 학번·학과·학년·questionId 없음). 질문 글은 mask.py로 가린다.
    AI를 부르지 않고 이미 만든 답을 남기기만 한다. 기록이 실패해도 답은 그대로 돌려준다.
    [11/25 Q-13] 채점용 칸: id(채점이 새 기록만 고르는 열쇠, 사람과 무관한 무작위 값) · route(코드가 고른 길) ·
      intent·field·section·asked(질문정리 결과, 실패하면 None) · prev(바로 앞 턴: 질문·결과·프로그램)."""
    try:
        import uuid

        import mask
        import store
        from runtime_fns import now
        trace = trace or {}
        plan = trace.get("plan") or {}
        sources = out.get("sources") or {}
        programs = [program] if program else \
            [s.get("program") for s in sources.values()] or [c.get("program") for c in out.get("notes") or []]
        asked = plan.get("정리된질문")
        row = {"id": uuid.uuid4().hex[:12], "at": now(), "status": out.get("status"), "question": mask.mask(question),
               "lines": [{"text": ln.get("text", ""), "cites": list(ln.get("cites") or [ln.get("sourceId")]),
                          **({"fallback": True} if ln.get("fallback") else {})} for ln in out.get("lines") or []],
               "programs": list(dict.fromkeys(p for p in programs if p)), "noteId": out.get("noteId"),
               "message": out.get("message"),
               "route": trace.get("route"), "intent": plan.get("의도"), "field": plan.get("분야"), "section": plan.get("칸"),
               "asked": mask.mask(asked) if asked and asked != question else None,
               "prev": {"question": mask.mask(prev["question"]), "status": prev.get("status") or "",
                        "program": prev.get("program") or ""} if prev else None}
        with store.lock():
            log = store.load("askLog", [])
            log.append(row)
            # 끝없이 커지지 않게: ASK_LOG_MAX + ASK_LOG_SLACK건을 넘으면 최근 ASK_LOG_MAX건만 남긴다(그 전은 드라이브 로그 시트).
            # 매번 자르지 않고 여유를 두는 이유 — store(ncp)는 줄어든 목록을 통째로 쓰므로, 자르는 요청을 드물게 한다
            if len(log) > ASK_LOG_MAX + ASK_LOG_SLACK:
                del log[:len(log) - ASK_LOG_MAX]
            store.save("askLog")
    except Exception as e:   # 기록 때문에 답을 잃지 않는다. 원인 종류만 서버 로그에(글·키는 찍지 않는다)
        print(f"[vcc] askLog 기록 실패: {type(e).__name__}")


def _answer(me, payload, save, trace=None):
    """trace: [Q-13] 기록용 판단값을 담는 사전(route·plan). 응답에는 나가지 않는다."""
    trace = {} if trace is None else trace
    question = (payload.get("question") or "").strip()
    if not question:
        return {"error": "질문을 입력해 주세요"}
    if len(question) > 300:
        return {"error": "질문은 300자 안으로 적어 주세요"}
    history = clean_history(payload.get("history"))

    # [v2] chat 칩 「질문함에 담기」: 답을 찾지 않고 바로 질문함에 hold로
    if payload.get("force") == "hold":
        trace["route"] = "담기"
        program = _saved_program(question, history)
        section = None
        if program:   # [Q-44] 칸까지 남긴다 — 「궁금한 것 정리하기」가 분야부터 다시 묻지 않게(못 정하면 None)
            from demand import guess_section   # demand → runtime_fns → askboo로 이어지므로 쓸 때 불러온다
            section = guess_section(question, program)
        return _hold(me, question, program, section, save, why="담기")

    # [11/24 작업 87] 앞 턴(과 이번 말)에서 「○○ 말고」로 뺀 프로그램 — 이번 말이 그 이름을 다시 부르지 않으면 계속 뺀다
    excluded = carried_exclusions(question, history)

    # [11/25 Q-14] 「○○ 말고」로 뺀 프로그램은 대조에서 바로 뺀다 — 빼고 남는 것이 없으면 「말고」 뒤 말로 나라를 찾는다
    #   (「나가사키외국어대학교 말고 일본 대학 전체…」가 나가사키로 잡혀 나라를 못 보던 일)
    rest = EXCLUDE_RE.sub(" ", question)
    programs = [p for p in match_programs(question) if p not in excluded]
    country = None
    if not programs:                       # [11/23] 프로그램명이 없으면 나라 이름으로(근거 많은 순)
        country, programs = match_country(rest)
        programs = [p for p in programs if p not in excluded]
    # [11/25 Q-14] 질문의 도시가 그 나라 학교 이름에 있으면 그 학교만, 없으면 아래에서 「그 도시 노트 0개」로 답한다
    city = city_scope(rest, programs, country)
    if city and city[2]:
        country, programs = city[1], city[2]

    # ①′ 규정 질문 → 공식 안내 (정규식이 먼저 — 보수 규칙, HCX 원칙 v3 5절)
    if is_official(question):
        trace["route"] = "규정(정규식)"
        return _official(me, question, programs, save)

    # ①‴′ [11/26] 인원·순위 질문(「독일 7+1 가장 많이 간 대학교」) → 학적의 파견대학을 코드가 세어 답한다(AI 없음).
    #     비교(「어느 학교가 제일 많이」)보다 먼저 본다
    found = rank(question, programs, country, excluded)
    if found:
        trace["route"] = "인원"
        return found

    # ①‴ [11/25 작업 87] 여러 곳 비교 질문 → 고정 안내 + 노트 카드(AI 없음). 비교 근거가 없으니 한 학교 답을 되풀이하지 않는다
    if is_compare(question):
        trace["route"] = "비교"
        return _compare(question, programs, history)

    # ①⁗′ [11/25 Q-14] 근거 범위 밖 도시(「일본 도쿄 생활비」) → 다른 학교 근거로 답하지 않고 노트 수 + 카드(AI 없음)
    if city and not city[2]:
        trace["route"] = "도시 범위 밖"
        return _city_none(city[0], city[1], excluded)
    # ①⁗″′ [11/26 작업 104] 한 도시에 노트 있는 학교가 둘 이상(「리옹 대학 생활비」 → 리옹2·리옹3·리옹카톨릭)이고 학교를
    #     특정하지 않았으면 근거를 섞어 답하지 않고 학교를 고르게 한다(A안 측정 51번). 「뤼미에르 리옹 2대학」처럼 부르면 city가 None
    #     도시 자체 이야기(「파리 치안은 어때요?」 — 날씨·치안·물가·생활 환경)는 학교와 상관없어 그 도시 학교 근거로 그대로 답한다.
    #     단 「리옹 대학」「파리에 있는 학교」처럼 학교를 말했으면 주제와 상관없이 고르게 한다
    if city and len(city[2]) >= 2 and (SCHOOL_WORD_RE.search(rest) or not CITY_TOPIC_RE.search(rest)):
        trace["route"] = "도시 학교 고르기"
        return _city_pick(city[0], city[1], city[2])
    # 「○○ 말고 일본 대학 전체의 노트에도 없나요?」 → 빼고 남은 그 나라(분야) 노트 수(AI 없음)
    found = exclude_scope(question, rest, excluded)
    if found:
        trace["route"] = "제외 범위"
        return found

    # ①⁗ [11/25 Q-13] 앞 답에 대한 후속 질문(「이게 다야?」「기준이 뭐야」)과 시기 질문(「인턴 보통 언제 해요?」)
    #     — 코드가 노트 수·근거 학기를 세어 답한다(AI 없음, 지어낼 것이 없게). 걸리지 않으면 아래 그대로
    found = follow_up(question, history, programs, excluded)
    if found:
        trace["route"] = found.pop("_route")
        return found
    found = timing(question, history, programs, country, excluded)
    if found:
        trace["route"] = "시기"
        return found
    # ①⁗″ [11/26 작업 106] 비교과 유형 단위·순위·비교 질문(「튜터링 어때요?」「만족도 제일 높은 비교과」) — 코드가 센다(AI 없음)
    #     나라 이름이 있으면(「독일 튜터링 어때요?」 — 파견 대학 이야기일 수 있음) 「비교과」라고 말했을 때만
    found = extra_scope(question, [] if country else programs, excluded) \
        if not country or EXTRA_WORD_RE.search(question) else None
    if found:
        trace["route"] = found.pop("_route")
        return found

    # ①⁰ [작업 35] 학교 이름이 글자로 잡힌 첫 질문이면 답쓰기-전문을 질문정리와 같이 시작(쓰일지는 _answer_full이 정한다)
    spec = _overlap_start(question, history, excluded, programs, country)
    if spec:
        trace["overlap"] = spec
    # ① [v2] 질문 정리(AI). 실패하면 plan=None → 아래는 v1 경로 그대로
    plan = clarify(question, history, excluded)
    trace["plan"] = plan
    trace["route"] = "질문정리" if plan else "v1(질문정리 실패)"
    effective = question
    if plan:
        if plan["의도"] == "규정":
            if not local_scope(question):
                return _official(me, question, programs, save)
            plan["의도"] = "경험질문"   # [Q-38] 현지·파견 대학 이야기는 질문정리가 규정이라 해도 근거 길로(정규식과 같은 기준)
        # [11/26 Q-38] 「장학금 받은 사람이 있나?」처럼 주제어가 있는 사람 찾기는 경험 질문(①″ 정규식 길과 같은 기준 —
        #   사람 찾기 카드는 주제어가 없을 때만). 근거가 없으면 카드 대신 보류 → 질문함
        if plan["의도"] == "사람찾기" and has_topic(question):
            plan["의도"] = "경험질문"
        plan["제외"] += [p for p in excluded if p not in plan["제외"]]
        # [11/24] 「아예 데이터가 없나요?」 — 있고 없음을 묻는 말은 앞 대화 주제의 노트 수로 답한다(코드가 센다, AI 없음)
        if plan["의도"] in ("대화", "탐색") and EXIST_RE.search(question) and not match_programs(question) \
                and not match_country(question)[0]:
            found = _exists(plan, history)
            if found:
                return found
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
            found = _explore(plan, programs, country or plan["나라"], question)
            if found:
                found.pop("_route", None)
                return found
            return _hold(me, question, programs[0] if programs else None, plan["칸"], save, why="탐색 결과 없음",
                         place=_place(country or plan["나라"], programs))
        if not programs and plan["분야"] and plan["제외"]:
            # 「코트라 말고 무역 인턴」처럼 제외하고 남는 프로그램이 없으면 그 분야 노트 목록으로
            found = _explore(plan, [], country or plan["나라"], question)
            if found:
                found.pop("_route", None)
                return found
    elif excluded:   # 질문정리 실패(v1 경로)에도 앞에서 뺀 프로그램은 뺀다
        programs = [p for p in programs if p not in excluded]

    # ① 프로그램이 없으면 보류
    if not programs:
        return _hold(me, question, None, None, save, why="프로그램 없음")
    # [11/26 Q-38] 나라로 여러 학교를 잡았으면 보류 문구를 나라 단위로(「독일 해봤노트에는 …」).
    #   programs[0]은 근거가 가장 많은 학교일 뿐이라 학교 이름으로 말하면 그 학교만 본 것처럼 읽힌다(실서버 「독일 학비 알려줘」)
    place = _place(country, programs)

    # ①″ [11/23] 사람을 찾는 질문이나 나라만 말한 질문인데 주제어가 없으면 → 해봤노트 카드로 안내(AI 없음)
    if not plan and not has_topic(question) and (PERSON_RE.search(question) or country):
        found = _notes(programs, country)
        if found:
            return found

    # ②′ [11/26 A안] VCC_ASK_FULL=1: 추출·고르기를 건너뛰고 프로그램 근거 전문을 답쓰기-전문에 넘긴다.
    #     답쓰기가 실패(형식·호출)하면 None → 아래 옛 길(추출 → 고르기 → 답쓰기 → 원문 인용) 그대로
    if ask_full():
        trace["route"] = (trace.get("route") or "") + "·전문"
        found = _answer_full(me, question, effective, programs, plan, save, place, spec)
        if found is not None:
            return found
        trace["route"] += "→옛 길"

    # ②/③ 근거 추출 (정리된 질문 + 원래 질문의 주제어·겹침을 모두 본다)
    cands, section, why = extract(effective if effective == question else f"{question} {effective}", programs,
                                  section_hint=plan["칸"] if plan else None)
    if not cands:
        return _hold(me, question, programs[0], section, save, why=why, place=place)

    # ④ 고르기 (HCX)
    picked, why = pick(effective, cands)
    if not picked:
        return _hold(me, question, programs[0], section, save, why=why, place=place)

    # ⑤ 답쓰기 + ⑥ 검증 (v2) → 다 버려지면 v1 원문 인용
    # [11/24 작업 87] 답쓰기가 {"답":[]}(근거가 질문에 안 맞음)를 내면 원문을 답처럼 보여 주지 않고 보류한다
    out = compose(effective, picked, on_empty=EMPTY_ANSWER)
    if out is EMPTY_ANSWER:
        return _hold(me, question, programs[0], section, save, why="답쓰기 근거 없음", place=place)
    if out is None:
        out = fallback_lines(picked)
    out["noteId"] = notes.note_id(picked[0]["program"])
    out["suggestSenior"] = False
    return out


def _answer_full(me, question, effective, programs, plan, save, place=None, spec=None):
    """[11/26 A안] 전문 길. 돌려주는 값: 응답 사전, 또는 None(답쓰기 실패 — 부르는 쪽이 옛 길로).
    spec: [작업 35] _overlap_start가 미리 시작한 답쓰기. 프로그램·근거 글이 같으면 그 결과를 쓴다."""
    paras, why = full_evidence(effective if effective == question else f"{question} {effective}", programs)
    section = "근무조건" if why.startswith("인터뷰로만") else (plan["칸"] if plan else None)
    if not paras:
        return _hold(me, question, programs[0], section, save, why=why, place=place)
    out, quotes = compose_full(effective, paras, written=_overlap_take(spec, programs, paras))
    if out is EMPTY_ANSWER:
        return _hold(me, question, programs[0], section, save, why="답쓰기 근거 없음", place=place)
    if out is None:
        if not quotes:          # 답쓰기 호출·형식 실패 → 옛 길
            return None
        out = fallback_lines(quotes)   # 답쓰기가 가리킨 원문 문장을 인용(다 버려진 경우)
    first = out["lines"][0]["sourceId"] if out["lines"] else None
    out["noteId"] = notes.note_id(out["sources"].get(first, {}).get("program") or programs[0])
    out["suggestSenior"] = False
    return out


def fallback_lines(picked):
    """v1 ④ 변환 + ⑤ 사후 검증: 고른 문장을 하나씩 해요체로(검증에 걸리면 원문 인용). v2의 폴백.
    [11/24 작업 87] 답쓰기가 실패·탈락한 뒤의 줄이므로 모든 줄에 fallback을 붙인다(화면: 「근거 원문」).
    이미 합쇼체라 변환을 건너뛴 원문도 BOO가 질문에 맞춰 쓴 답이 아니다."""
    lines, sources, seen, texts = [], {}, {}, set()
    for c in picked[:MAX_LINES]:
        text, _ = convert(c["text"])
        if _norm(text) in texts:   # 다른 보고서의 같은 문장은 한 번만
            continue
        texts.add(_norm(text))
        sid = c["sourceId"]
        seen[sid] = seen.get(sid, 0) + 1
        lines.append({"text": text, "sourceId": sid, "cites": [sid], "fallback": True,
                      "lineId": f"L-{sid}" if seen[sid] == 1 else f"L-{sid}.{seen[sid]}"})
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


EXCLUDE_RE = re.compile(r"([^,.?!~\n]{1,30}?)\s*(?:말고|말구|말곤|빼고|제외하고)")
# 있고 없음을 묻는 말 — 「아예 데이터가 없나요?」「노트가 하나도 없어요?」
EXIST_RE = re.compile(r"(데이터|자료|노트|근거|정보|후기|사례)\s*(가|이|는|도|조차|에도|에는|엔|에서도|에)?\s*(아예|전혀|하나도|정말|진짜)?\s*(없|있)"
                      r"|아예\s*없|하나도\s*없")


def _named_programs(text):
    """이름·별칭·약칭(KOTRA·코트라)으로 직접 부른 프로그램. 직군·기관유형(「무역 인턴」)은 보지 않는다."""
    q = _norm(fix_names(text))
    found = {name for t, name, is_alias in _TERMS if t in q and (not is_alias or _alias_ok(t, q))}
    kw = INTERN_KEYWORDS if isinstance(INTERN_KEYWORDS, dict) else {}
    for w, names in (kw.get("약칭") or {}).items():
        if _norm(w) and _norm(w) in q:
            found |= set([names] if isinstance(names, str) else names)
    return found


def carried_exclusions(question, history):
    """[11/24 작업 87] 이전 질문들과 이번 말의 「○○ 말고/빼고」에서 뺀 프로그램(코드 대조, AI 없음).
    화면 history에는 제외 칸이 없으므로 이전 질문 글자에서 다시 찾는다(talk.js 변경 없음, 최근 4턴 동안 유지).
    이번 말이 「말고」 밖에서 그 이름을 다시 부르면(「코트라는 어때요?」) 빼지 않는다."""
    out = []
    for text in [h["question"] for h in history] + [question]:
        for m in EXCLUDE_RE.finditer(text):
            out += [n for n in match_programs(m.group(1)) if n in PROGRAMS and n not in out]
    again = _named_programs(EXCLUDE_RE.sub(" ", question))
    return [n for n in out if n not in again]


def _saved_program(question, history):
    """[Q-44] 「질문함에 담기」로 담는 질문의 프로그램(코드 대조, AI 없음). 못 정하면 None.
    질문에서 부른 프로그램 → 없으면 바로 앞 턴의 프로그램. 「말고」로 뺀 것, 목록에 없는 학교 이름이나
    다른 나라를 말하는 질문에는 붙이지 않는다(엉뚱한 프로그램의 선배에게 가지 않게)."""
    excluded = carried_exclusions(question, history)
    prev = (history[-1].get("program") or "") if history else ""
    prev = prev if prev in PROGRAMS and prev not in excluded else None
    rest = EXCLUDE_RE.sub(" ", question)
    named = [n for n in match_programs(rest) if n in PROGRAMS and n not in excluded]
    if named:   # 약칭 「코트라」처럼 여럿이면 앞 턴이 그중 하나일 때만
        return prev if prev in named else named[0] if len(named) == 1 else None
    if SCHOOL_NAME.search(rest):
        return None
    country, programs = match_country(rest)
    return None if country and prev not in programs else prev


def clarify(question, history, excluded=()):
    """AI(질문정리). 돌려주는 값: 대조를 거친 plan 또는 None(실패·형식 오류 → v1 경로)."""
    if history:
        lines = [f"{i}. 후배: {h['question']} → BOO: {STATUS_WORD.get(h['status'], h['status'] or '?')}"
                 + (f" ({h['program']})" if h["program"] else "") for i, h in enumerate(history, 1)]
        prev = "\n".join(lines)
    else:
        prev = "(없음)"
    if excluded:
        prev += "\n앞에서 뺀 프로그램: " + ", ".join(excluded)
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
    # [11/24] 나라원문: 교환 나라 목록(COUNTRIES)에 없는 나라도 「0개」라고 답하려고 남긴다(한글 2~10자, 「…어」는 언어라 뺌)
    raw = j.get("나라").strip() if isinstance(j.get("나라"), str) else ""
    raw = raw if re.fullmatch(r"[가-힣]{2,10}", raw) and not raw.endswith("어") and raw in question else None
    return {"의도": j["의도"], "분야": j.get("분야") if j.get("분야") in FIELDS else None, "나라": country,
            "나라원문": country or raw,
            "프로그램후보": names("프로그램후보"), "제외": names("제외"), "칸": section, "정리된질문": asked}


ALL_SECTIONS = {s for f in notes.FRAMES.values() for s in f.get("칸", [])} | set(SECTION_BY_ITEM.values())


# ── ② [v2] 대화·탐색 ──────────────────────────────────────────────────
FIELD_NOUN = {"국제교류": "교환·파견 해봤노트", "현장실습": "현장실습 해봤노트", "비교과": "비교과 해봤노트"}


def _chat(plan, history):
    """status "chat": AI가 쓰지 않는 고정 문구 + 칩. 질문함에 저장하지 않는다(답할 질문이 아님)."""
    # [11/24] 문구는 바로 앞 턴이 실제로 보여 준 것을 따른다. 예전에는 「제외」를 먼저 봐서, ③이 이미 다른 노트 목록을
    #   보여 준 뒤에도 ④가 「아까는 KOTRA … 이야기였어요」라고 했다(캡처 ④). 뺀 프로그램은 「빼고 보고 있어요」로만 말한다.
    last = history[-1] if history else None
    program = last["program"] if last and last["program"] else None    # 앞 답의 근거 프로그램
    excl = plan["제외"]
    field = plan["분야"] or (PROGRAMS.get(program, {}).get("분야") if program else None) \
        or (PROGRAMS.get(excl[0], {}).get("분야") if excl else None)
    lab = _label(excl) if excl else ""
    noun = FIELD_NOUN.get(field, "해봤노트")
    chips = []
    if last and last["status"] == "chat" and (program or excl):
        # 바로 앞도 chat이면 같은 안내를 되풀이하지 않는다
        lab = lab or program
        message = f"{lab}{_josa('은는', lab)} 빼고 볼게요. 궁금한 주제(업무·지원·배운 점 등)를 적어 주시거나 다른 노트를 둘러보세요."
        chips.append({"label": "다른 노트 보기", "action": "notes", "payload": {"field": field, "exclude": excl or [program]}})
    elif last and last["status"] == "notes":
        # 앞 턴이 노트 목록이었다 — 그 목록이 겹쳤거나 맞지 않았다는 말로 받는다
        head = f"{lab}{_josa('은는', lab)} 빼고 노트를 보여 드렸어요. " if excl else ""
        message = (f"{head}앞에서 본 노트와 겹쳤다면 궁금한 기관 유형이나 주제(업무·지원·배운 점 등)를 적어 주세요. "
                   f"그 노트에서 선배 이야기를 찾아 답해 드릴게요.")
        chips.append({"label": f"다른 {noun.replace(' 해봤노트', ' 노트')} 보기" if field else "해봤노트 둘러보기",
                      "action": "notes", "payload": {"field": field, "exclude": excl}})
    elif program:
        message = f"아까는 {program} 이야기였어요. 다른 {noun}를 찾아볼까요?"
        chips.append({"label": "다른 노트 보기", "action": "notes", "payload": {"field": field, "exclude": [program]}})
    elif excl:
        message = f"{lab}{_josa('은는', lab)} 빼고 볼게요. 다른 {noun}를 찾아볼까요?"
        chips.append({"label": "다른 노트 보기", "action": "notes", "payload": {"field": field, "exclude": excl}})
    elif last and last["status"] == "hold":
        message = "아직 그 내용을 들려준 선배가 없어서 질문함에 담아 두었어요. 선배가 답하면 알림으로 알려 드릴게요."
        chips.append({"label": "닮은선배 보기", "action": "ask", "payload": {}})
    else:
        message = "무엇이 궁금한지 조금 더 구체적으로 물어봐 주세요. 예: 「마르부르크 기숙사 어땠어요?」"
        chips.append({"label": "해봤노트 둘러보기", "action": "notes", "payload": {"field": field}})
    chips.append({"label": "질문함에 담기", "action": "save", "payload": {"question": plan["정리된질문"]}})
    return {"status": "chat", "lines": [], "sources": {}, "suggestSenior": False, "message": message, "chips": chips}


def _kinds():
    return sorted({p["세부"] for p in PROGRAMS.values() if p.get("분야") == "현장실습" and p.get("세부")})


def _explore(plan, programs, country, question=""):
    """탐색·사람찾기: 답을 만들지 않고 노트 카드(최대 5, 근거 많은 순)로 안내한다. 현장실습을 나라로 물으면 기관 유형 칩.
    [11/26 작업 106] 비교과는 근거 있는 노트(2개)만 고르지 않는다 — 유형·순위·목록은 extra_scope(130개 풀)가,
    이름·유형이 하나도 안 맞으면 None(부르는 쪽이 보류). 예전에는 질문과 상관없이 늘 같은 2장이 나왔다(#342)."""
    field = plan["분야"]
    place = country or plan.get("나라원문")
    if field == "비교과" and not programs:
        return extra_scope(question, [], plan["제외"], field="비교과")
    if field == "현장실습" and place and not programs:
        # [11/24] 나라 노트 수를 먼저 말한다(코드가 셈). 근거에 그 나라가 나오는 인턴 노트가 있으면 카드로 함께
        mentions = [n for n in intern_mentions(place) if n not in plan["제외"]]
        found = _notes(mentions, place) or {"notes": []}
        return {"status": "notes", "lines": [], "sources": {}, "suggestSenior": True, "notes": found["notes"], "kinds": _kinds(),
                "message": country_counts(place, field) + " 현장실습 노트는 나라가 아니라 기관 유형으로 나뉘어요. 궁금한 유형을 골라 보세요."}
    if not programs and place and not country and field in (None, "국제교류"):
        # 교환 나라 목록에 없는 나라(「베트남 교환」) — 보류 대신 0개라고 답한다
        return {"status": "notes", "lines": [], "sources": {}, "suggestSenior": True, "notes": [],
                "message": country_counts(place, field) + " 궁금한 다른 나라나 프로그램을 물어봐 주세요."}
    if not programs and field:
        pool = [n for n, p in PROGRAMS.items() if p.get("분야") == field and n not in plan["제외"]
                and (not country or p.get("세부") == country) and evidence_count(n)]
        programs = sorted(pool, key=evidence_count, reverse=True)[:MAX_NOTES]
        total = len(pool)
    else:
        total = 0
    if not programs:
        return None
    found = _notes(programs, country, total=total)
    if found and plan["제외"] and len(found["notes"]) > 1:
        lab = _label(plan["제외"])
        n = len(found["notes"])
        # [11/24] 카드는 5개까지라 「5개 있어요」는 틀린 수 — 전체 수를 말하고 근거 많은 것부터 보여 준다고 한다
        count = f"{total}개 있어요. 근거가 많은 {n}개를 먼저 보여 드려요" if total > n else f"{n}개 있어요"
        found["message"] = f"{lab}{_josa('을를', lab)} 뺀 {FIELD_NOUN.get(field, '해봤노트')}가 {count}. 궁금한 노트를 골라 보세요."
    return found


# ── [11/24 작업 87] 나라·유무 질문: 개수는 코드가 programs.json·근거에서 센다(AI 없음 — 없는 근무지·나라를 지어내지 않게) ──
def _josa(pair, word):
    """pair: "이가"·"은는"·"을를". 받침을 모르면(영문·괄호 끝) 「을(를)」처럼 둘 다."""
    ch = (word or " ")[-1]
    if "가" <= ch <= "힣":
        return pair[0] if (ord(ch) - 0xAC00) % 28 else pair[1]
    return f"{pair[0]}({pair[1]})"


def _label(names):
    """뺀 프로그램 이름 — 같은 세부(「KOTRA 해외무역관」 권역 3곳)는 세부 하나로 줄인다."""
    out = []
    for n in names:
        kind = PROGRAMS.get(n, {}).get("세부")
        same = [m for m in names if kind and PROGRAMS.get(m, {}).get("세부") == kind]
        w = kind if len(same) > 1 and PROGRAMS.get(n, {}).get("분야") == "현장실습" else n
        if w not in out:
            out.append(w)
    return ", ".join(out)


def intern_mentions(place):
    """근거(보고서·동의 통과 인터뷰 문장)에 그 나라 이름이 나오는 현장실습 프로그램(근거 많은 순). 현장실습은 나라 칸이 없다."""
    pat = re.compile(re.escape(place) + r"(?!어)")
    hits = [n for n, p in PROGRAMS.items() if p.get("분야") == "현장실습"
            and (any(pat.search(e.get("text", "")) for e in EVIDENCE.get(n, []))
                 or any(pat.search(r.get("text", "")) for r in notes.interview_lines(n)))]
    return sorted(hits, key=evidence_count, reverse=True)


def country_counts(place, field):
    """나라 노트 수 문장. field가 현장실습이면 인턴 수를 먼저, 그 나라 교환·파견 노트가 있으면 덧붙인다."""
    ex = len([n for n in COUNTRIES.get(place, []) if evidence_count(n)])
    ex_s = f"{place} 교환·파견 해봤노트는 {ex}개예요." if ex == 0 else f"{place} 교환·파견 해봤노트는 {ex}개 있어요."
    if field == "국제교류":
        return ex_s
    k = len(intern_mentions(place))
    in_s = (f"{place}에서 한 현장실습 해봤노트는 0개예요." if not k
            else f"근거에 {place}{_josa('이가', place)} 나오는 현장실습 해봤노트가 {k}개 있어요.")
    return in_s + (" " + ex_s if ex or field is None else "")


FIELD_RE = (("현장실습", re.compile(r"인턴|실습|회사|기업|기관|근무")), ("국제교류", re.compile(r"교환|파견|유학|어학연수|대학")))


def _exists(plan, history):
    """status "chat": 「데이터가 없나요?」에 앞 대화 주제(나라 > 프로그램 > 분야)의 노트 수로 답한다."""
    texts = [h["question"] for h in reversed(history)]
    place = plan.get("나라원문")
    if not place:
        for t in texts:
            c, _ = match_country(t)
            if c:
                place = c
                break
    field = plan["분야"]
    for t in ([] if field else texts):
        field = next((f for f, rx in FIELD_RE if rx.search(t)), None)
        if field:
            break
    program = next((h["program"] for h in reversed(history) if h["program"] and h["program"] not in plan["제외"]), None)
    chips = [{"label": "해봤노트 둘러보기", "action": "notes", "payload": {"field": field, "exclude": plan["제외"]}}]
    if place:
        message = country_counts(place, field)
        if field == "현장실습":
            message += " 현장실습 노트는 기관 유형으로 나뉘어 있어요."   # chat은 유형 칩을 못 보여 줘서 「유형으로 찾아보세요」라고 하지 않는다
    elif program:
        message = f"{program} 해봤노트에는 선배 근거가 {evidence_count(program)}개 있어요. 궁금한 주제를 물어보시면 그 근거로 답해 드릴게요."
    elif field == "비교과":   # [작업 106] 비교과 노트는 130개 — 근거(선배 경험담)가 0이어도 노트는 있다
        pool = [n for n in EXTRA if n not in plan["제외"]]
        k = len([n for n in pool if evidence_count(n)])
        message = (f"{FIELD_NOUN[field]}는 {len(pool)}개 있어요. 선배 경험담이 있는 노트는 {k}개"
                   + ("예요" if not k else " 있어요") + ". 노트에서 이수 인원·만족도를 볼 수 있어요.")
    elif field:
        pool = [n for n, p in PROGRAMS.items() if p.get("분야") == field and n not in plan["제외"] and evidence_count(n)]
        lab = _label(plan["제외"])
        head = f"{lab}{_josa('을를', lab)} 빼도 " if plan["제외"] else ""
        message = f"{head}{FIELD_NOUN[field]}가 {len(pool)}개 있어요. 궁금한 노트를 둘러보세요."
    else:
        return None
    chips.append({"label": "질문함에 담기", "action": "save", "payload": {"question": plan["정리된질문"]}})
    return {"status": "chat", "lines": [], "sources": {}, "suggestSenior": False, "message": message, "chips": chips}


# ── ① 프로그램 대조 ───────────────────────────────────────────────────
def match_programs(question):
    q = _norm(fix_names(question))
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
    if found:
        return found[:3]
    # [11/26 작업 106] 비교과 줄임말·부분 이름(「직무탐색 교육」「GAT」「국정원 설명회」) — 위 대조가 모두 0개일 때만
    return extra_loose(question)


# ── [11/26 작업 106] 비교과 이름 넓은 대조 (코드, AI 없음) ─────────────────────
# #342 계측: 비교과 구어 질문 27문 중 10문이 줄임말·부분 이름이라 match_programs 0개 → 「해봤노트를 찾지 못했어요」.
# 정식 이름을 낱말로 쪼개 군더더기(꾸밈 괄호 안 말·「프로그램」「수료자」·유형어)를 빼고, 남은 낱말이 질문에 있는지 본다.
#   ① 낱말 맞음: 질문(띄어쓰기 지움)에 그 낱말이 들어 있음. 영문은 3자 이상 따로 쓴 낱말만(GAT·BYOI — OT·AI·IT는 안 봄)
#   ② 앞부분 맞음: 질문 낱말이 이름 낱말의 앞 절반 이상(「수리」 → 수리능력). 이것만으로는 안 잡고 다른 낱말이 하나 더 맞아야 한다
#   ③ 줄임말: 질문의 한글 3글자가 이름 낱말(4글자 이상)의 첫·끝 글자와 같고 가운데 글자가 그 사이에 있음(「국정원」 → 국가정보원)
#   잡는 조건: 비교과 2곳 이하에만 있는 낱말(학과·나라 이름은 빼고)이 ①·③으로 맞거나 ②에 다른 낱말이 더해짐.
#   여럿이면 드문 낱말(1/들어 있는 프로그램 수)의 합이 가장 큰 것, 같으면 3곳까지.
#   유형어(튜터링·멘토링·특강 등)는 낱말로 세지 않는다 — 「튜터링 어때요?」는 프로그램 하나가 아니라 아래 extra_scope(유형 단위).
#   교환·인턴 문맥 말(교환·파견·인턴·현장실습·대학교·기숙사 등)이 있으면 보지 않는다(나라·학교·인턴 대조가 먼저).
#   짧은 낱말(2글자 한글)만 맞으면 비교과 말(특강·교육·활동·모임 등)이 질문에 있을 때만 잡는다(「예선 통과」는 안 잡음).
EXTRA_TYPE_WORDS = ("특강", "프로그램", "교육", "과정", "활동", "멘토링", "튜터링", "탄뎀", "버디", "강좌", "설명회", "대회", "공모전",
                    "캠프", "테라피", "코스", "워크숍", "상담", "컨설팅", "강연", "포럼", "세미나", "스터디", "동아리", "검사", "이벤트",
                    "예술제", "영화제", "취업특강", "취업설명회", "채용설명회", "보충강좌", "집중강좌", "집중교육", "직무특강",
                    "창업", "자격증", "경연", "독서", "강의")
EXTRA_FILLER = {"수료자", "신청", "안내", "지원", "온라인", "실시간", "오프라인", "비대면", "집중", "초청", "연계", "현직자", "동문",
                "취업", "진로", "채용", "대비", "한국외국어대학교", "hufs", "특교원", "서울캠퍼스", "하계", "동계", "여름방학",
                "겨울방학", "방중", "방과후", "방과", "후", "초급", "중급", "고급", "초급반", "중급반", "초-중급", "중-고급", "반", "선발",
                "예정", "및", "등", "이수", "참여", "대상", "까지", "선착순", "외국어", "전공", "학과", "학생", "선배", "직무",
                "취업역량", "역량", "강화", "해외", "글로벌", "현지", "기업", "공기업", "대기업", "실무", "기초", "준비", "the", "and",
                "for", "de", "em", "para", "program", "프로그램_튜티"}
EXTRA_TYPE_SET = {_norm(w) for w in EXTRA_TYPE_WORDS}
EXTRA_CUE_RE = re.compile("|".join(EXTRA_TYPE_WORDS) + r"|비교과|모임|클럽|콘서트|들을|들어|참가|참여|수강|수료|나가|나갔|해\s*보")
EXTRA_BLOCK_RE = re.compile(r"교환|파견|유학|어학연수|인턴|현장실습|대학교|기숙사|비자|월세|생활비|학점\s*인정")
_LANG_RE = re.compile(r".+(어과|어)$|^(네덜란드|이탈리아|포르투갈|스칸디나비아|브라질|벨기에|스웨덴|포르투갈어권|중남미|유럽)$")
_PARTICLE_RE = re.compile(r"(이랑|랑|하고|에서|으로|로|은|는|이|가|을|를|에|도|의|와|과|만|요)$")


def _extra_tokens(name):
    """비교과 이름 → 낱말(소문자, 군더더기·유형어 뺌). 「[HUFS 북플] 북클럽(독서모임) 활동」 → 북플·북클럽·독서모임.
    「:」 뒤 부제와 < > 안 강연 제목은 보지 않는다(「길을 묻다」「선배에게」 같은 보통 말이 낱말이 되지 않게)."""
    core = re.sub(r"<[^>]*>", " ", name).split(":")[0]
    words = re.split(r"[\s\[\]()<>「」『』:/&·․,_+~.!?'\"‐–—\-]+", core.lower())
    out = []
    for w in words:
        w = w.strip()
        if re.fullmatch(r"[가-힣]{3,}", w):
            w = _PARTICLE_RE.sub("", w)   # 「선배가」「풀어주는」 → 조사를 뗀 꼴
        if len(w) < 2 or w in EXTRA_FILLER or w in EXTRA_TYPE_SET or re.fullmatch(r"[\d제회월일차년총시간명팀a-z]{1,2}|\d+.*", w):
            continue
        if re.fullmatch(r"[a-z]+", w) and len(w) < 3:
            continue
        for t in EXTRA_TYPE_WORDS:   # 「채용설명회」「취업특강」처럼 유형어가 붙은 낱말은 앞말도 낱말로(채용·취업은 군더더기라 빠짐)
            if w.endswith(t) and len(w) > len(t) + 1 and w[:-len(t)] not in EXTRA_FILLER | EXTRA_TYPE_SET:
                out.append(w[:-len(t)])
        out.append(w)
    return list(dict.fromkeys(out))


EXTRA = [n for n, p in PROGRAMS.items() if p.get("분야") == "비교과"]
EXTRA_TOK = {n: _extra_tokens(n) for n in EXTRA}
def _extra_core(name):
    """꾸밈 [ ]·( )·< >와 「:」 뒤 부제를 뗀 핵심 이름(띄어쓰기 지움). 「동문 초청 진로 취업 릴레이 특강(+한화생명 채용설명회)」
    → 동문초청진로취업릴레이특강. 4글자 미만이면 빈 글자(너무 짧아 보통 말에 걸림)."""
    core = re.sub(r"\[[^\]]*\]|\([^)]*\)|<[^>]*>", " ", name).split(":")[0]
    core = _norm(core)
    return core if len(core) >= 4 else ""


EXTRA_CORE = {n: _extra_core(n) for n in EXTRA}
EXTRA_ALL = {n: {w for w in re.split(r"[\s\[\]()<>「」:/&·․,_+~.!?\-]+", n.lower()) if len(w) >= 2} for n in EXTRA}
_EXTRA_DF = {}
for _toks in EXTRA_TOK.values():
    for _t in _toks:
        _EXTRA_DF[_t] = _EXTRA_DF.get(_t, 0) + 1


def _q_words(question):
    """질문 낱말(소문자) + 조사를 뗀 꼴."""
    out = []
    for w in re.findall(r"[가-힣]+|[A-Za-z]+", question.lower()):
        out.append(w)
        s = _PARTICLE_RE.sub("", w)
        if s and s != w:
            out.append(s)
    return out


def _extra_scores(question):
    """[(점수, 프로그램, 잡을 만한가)] — 점수가 0인 것은 뺀다."""
    q = _norm(fix_names(question))
    words = _q_words(question)
    hangul = [w for w in words if re.fullmatch(r"[가-힣]+", w)]
    latin = set(w for w in words if re.fullmatch(r"[a-z]+", w))
    out = []
    for name in EXTRA:
        hits = []   # (낱말, 종류)
        for t in EXTRA_TOK[name]:
            if re.fullmatch(r"[a-z]+", t):
                if t in latin:
                    hits.append((t, "낱말"))
            elif t in q and (len(t) > 2 or t in hangul):   # 2글자는 따로 쓴 낱말만(「데이터」의 데이는 아님)
                hits.append((t, "낱말"))
            elif any(len(w) >= 2 and len(w) * 2 >= len(t) and t.startswith(w) and w not in EXTRA_TYPE_SET
                     and w not in EXTRA_FILLER and w not in _EXTRA_DF for w in hangul):
                hits.append((t, "앞"))
            elif len(t) >= 4 and re.fullmatch(r"[가-힣]+", t) and any(
                    len(w) == 3 and w[0] == t[0] and w[2] == t[-1] and w[1] in t[1:-1] for w in hangul):
                hits.append((t, "줄임"))
        if not hits:
            continue
        rare = [(t, k) for t, k in hits if _EXTRA_DF.get(t, 9) <= 2 and not _LANG_RE.match(t)]
        strong = any(k in ("낱말", "줄임") for _, k in rare) or (rare and len(hits) >= 2)
        # 짧은 낱말(한글 2글자)만 드물게 맞았으면 비교과 말이 질문에 있어야 한다
        if strong and all(len(t) <= 2 and re.fullmatch(r"[가-힣]+", t) and k == "낱말" for t, k in rare) \
                and not EXTRA_CUE_RE.search(question):
            strong = False
        score = sum((0.5 if _LANG_RE.match(t) else 1.0) / _EXTRA_DF.get(t, 1) for t, _ in hits)
        # 같은 점수를 가르는 작은 덤: 이름의 낱말(유형어·군더더기 포함)이 질문에 든 수(「북플 독서모임 활동」 → 「… 활동」 쪽)
        score += 0.01 * sum(1 for w in EXTRA_ALL[name] if w in q)
        out.append((score, name, bool(strong)))
    return out


def extra_loose(question, relaxed=False):
    """비교과 넓은 대조. relaxed: 비교 질문의 한쪽(「NCS 특강」)처럼 드문 낱말이 없어도 가장 많이 맞은 것들(5곳까지).
    교환·인턴 문맥 말이 있으면 빈 목록."""
    if not question or EXTRA_BLOCK_RE.search(question):
        return []
    q = _norm(fix_names(question))
    cores = [(c, n) for n, c in EXTRA_CORE.items() if c and c in q]
    cores = [(c, n) for c, n in cores if not any(c != c2 and c in c2 for c2, _ in cores)]   # 긴 이름이 먼저
    if cores and len(cores) <= 3:
        return sorted(n for _, n in cores)
    scored = [s for s in _extra_scores(question) if s[2] or relaxed]
    if not scored:
        return []
    top = max(s[0] for s in scored)
    best = sorted(n for sc, n, _ in scored if abs(sc - top) < 1e-9)
    limit = MAX_NOTES if relaxed else 3
    return best if len(best) <= limit else []


# ── [11/26 작업 106] 비교과 사실 답 (코드, AI 없음 — 미리 결정 A) ──────────────────
# 비교과 130개는 선배 근거 문단이 0이다(#342). 「경험한 선배가 없어요」만 말하지 않고 코드가 가진 사실
# (세부 유형·운영 부서·이수 인원·만족도)을 말한 뒤 「선배 경험담은 아직 없어요」를 덧붙인다. 데이터에 없는 값은 「–」.
# 이수 인원·만족도는 노트 커버(notes.json completedCount·satisfaction — 해봤노트 화면과 같은 값).
_STU_GRADE = {}   # 프로그램 → {이수 당시 학년: 인원}
for _r in _json("extracurricular.json", []):
    if _r.get("프로그램명") and isinstance(_r.get("이수 당시 학년"), int):
        _g = _STU_GRADE.setdefault(_r["프로그램명"], {})
        _g[_r["이수 당시 학년"]] = _g.get(_r["이수 당시 학년"], 0) + 1


def _cover(name):
    return notes.NOTES.get(notes.note_id(name)) or {}


def extra_count(name):
    v = _cover(name).get("completedCount")
    return v if isinstance(v, int) else None


def extra_sat(name):
    v = _cover(name).get("satisfaction")
    if not isinstance(v, (int, float)):
        v = PROGRAMS.get(name, {}).get("만족도(5점)")
    return float(v) if isinstance(v, (int, float)) else None


def _num(v, unit=""):
    return "–" if v is None else (f"{v:,}{unit}" if isinstance(v, int) else f"{v:g}{unit}")


def short_name(name, cap=32):
    """문구용 짧은 이름: 꾸밈 [ ]·괄호 ( )를 떼고 「:」「<」 앞까지(「Bring Your Own Ideas(BYOI)」 → Bring Your Own Ideas).
    카드에는 정식 이름 그대로."""
    s = re.sub(r"^\s*(?:\[[^\]]*\]\s*)+", "", name)
    s = re.sub(r"\s*\([^()]*\)", "", s)
    s = re.split(r"\s*[:<]", s)[0].strip() or name
    s = re.sub(r"\s{2,}", " ", s)
    return s if len(s) <= cap else s[:cap].rstrip() + "…"


def is_extra(name):
    return PROGRAMS.get(name, {}).get("분야") == "비교과"


def extra_facts(name):
    """「직무탐색 집중교육은 1회성 비교과예요. 진로취업지원센터에서 운영하고, 이수 인원 109명 · 만족도 4.6점(5점 만점)이에요.」"""
    p = PROGRAMS.get(name, {})
    s = short_name(name)
    kind = p.get("세부")
    dept = DEPTS.get(p.get("운영부서코드"), {}).get("부서명")
    head = f"{s}{_josa('은는', s)} " + (f"{kind} 비교과예요." if kind else "비교과예요.")
    run = f" {dept}에서 운영하고," if dept else ""
    return f"{head}{run} 이수 인원 {_num(extra_count(name), '명')} · 만족도 {_num(extra_sat(name), '점')}(5점 만점)이에요."


EXTRA_NO_STORY = "선배 경험담은 아직 없어요."


def _extra_cards(names):
    """비교과 카드 — 근거가 0이어도 보여 준다(해봤노트 화면에 이수 인원·만족도가 있다). _notes와 같은 모양."""
    return [{"noteId": notes.note_id(n), "program": n, "country": None, "evidenceCount": evidence_count(n),
             "oneLine": _cover(n).get("oneLine", ""), "type": _cover(n).get("type") or notes._kind(n)}
            for n in names][:MAX_NOTES]


# 유형 단위 질문 — 질문의 말 → 그 유형의 비교과(이름에 든 말 또는 세부). 한 프로그램이 아니라 묶음이다
EXTRA_TYPES = [
    ("튜터링", re.compile(r"튜터링|튜터|튜티|tutoring", re.I), r"튜터링|tutoring", None),
    ("멘토링", re.compile(r"멘토링|멘토(?!스)"), r"멘토링", None),
    ("탄뎀", re.compile(r"탄뎀|언어\s*교환"), r"탄뎀", None),
    ("버디", re.compile(r"버디|buddy|국제\s*학생회", re.I), None, "국제교류·버디 활동"),
    ("특강", re.compile(r"특강|강연|설명회"), r"특강|강연|설명회", None),
    ("창업", re.compile(r"창업"), r"창업", "창업 활동"),
    ("공모전·대회", re.compile(r"공모전|대회|경연"), None, "공모전·대회"),
    ("외국어 강좌", re.compile(r"어학\s*강좌|외국어\s*강좌|집중\s*강좌|보충\s*강좌|방과\s*후\s*강좌|테라피"), None, "외국어·전공 집중강좌"),
    ("상담·컨설팅", re.compile(r"상담|컨설팅"), r"상담|컨설팅", "진로·취업 상담·컨설팅"),
    ("자격증", re.compile(r"자격증"), None, "자격증·기타 역량개발"),
    ("캠프", re.compile(r"캠프"), r"캠프", None),
    ("독서 모임", re.compile(r"독서|북클럽|책\s*모임"), r"독서|북클럽", None),
]
EXTRA_WORD_RE = re.compile(r"비교과")
EXTRA_RANK_SAT = re.compile(r"만족도|(제일|가장|젤|최고로)\s*(좋|도움|괜찮|나아|낫|유익|만족|알찬|추천)")
EXTRA_RANK_CNT = re.compile(r"인기|많이\s*(듣|들|이수|참여|신청|하는|한)|이수\s*인원|사람\s*(이\s*)?많")
EXTRA_GRADE = re.compile(r"([1-4])\s*학년")
EXTRA_LIST = re.compile(r"추천|들을\s*만|할\s*만|뭐\s*(가|이)?\s*(있|들)|어떤\s*(게|것|거|프로그램)?\s*(이\s*)?있|무엇이\s*있|종류|목록|어때|어땠|후기|해\s*본|해\s*보신|뭐\s*해")
EXTRA_PROXY = re.compile(r"도움|좋|괜찮|나아|낫|유익|알찬|추천")
EXTRA_SIDES = re.compile(r"^(.+?)\s*(?:이랑|랑|하고|vs\.?|VS\.?|와|과)\s+(.+?)\s*(?:둘\s*)?중(?:에|에서)?\s*(?:뭐|무엇|어느|어떤|어디)")


def _type_pool(question, excluded=()):
    """질문의 유형 말 → (유형 이름들, 그 유형 비교과). 유형 말이 없으면 ([], []).
    여럿이면 질문의 다른 말(「취업」 특강)이 이름에 가장 많이 든 것으로 좁히고, 그 말을 유형 이름 앞에 붙인다."""
    labels, pool = [], []
    for label, rx, name_rx, kind in EXTRA_TYPES:
        if not rx.search(question):
            continue
        labels.append(label)
        for n in EXTRA:
            if n in excluded or n in pool:
                continue
            if (name_rx and re.search(name_rx, n, re.I)) or (kind and PROGRAMS[n].get("세부") == kind):
                pool.append(n)
    if len(pool) > 1:   # 「취업 특강」 — 질문의 다른 말이 이름에 든 것으로 좁힌다(없으면 유형 전체)
        words = [w for w in _q_words(question) if len(w) >= 2 and _norm(w) not in EXTRA_TYPE_SET
                 and not any(rx.search(w) for _, rx, _, _ in EXTRA_TYPES)]
        words = list(dict.fromkeys(words))
        hit = {n: [w for w in words if w in n.lower()] for n in pool}
        most = max((len(v) for v in hit.values()), default=0)
        if most:
            pool = [n for n in pool if len(hit[n]) == most]
            used = [w for w in words if any(w in hit[n] for n in pool)]
            if labels and used:
                labels = [" ".join(used[:2]) + " " + labels[0]] + labels[1:]
    return labels, pool


def _side_text(names, said=""):
    """비교 한쪽 사실: 하나면 「이수 n명 · 만족도 x점」, 여럿이면 「(학생이 한 말) n개 · 이수 합 n명 · 만족도 a~b점」."""
    if len(names) == 1:
        return f"{short_name(names[0])} 이수 {_num(extra_count(names[0]), '명')} · 만족도 {_num(extra_sat(names[0]), '점')}"
    cnt = [extra_count(n) for n in names if extra_count(n) is not None]
    sat = [extra_sat(n) for n in names if extra_sat(n) is not None]
    rng = "–" if not sat else (f"{min(sat):g}점" if min(sat) == max(sat) else f"{min(sat):g}~{max(sat):g}점")
    return f"{said + ' ' if said else ''}{len(names)}개 · 이수 합 {_num(sum(cnt) if cnt else None, '명')} · 만족도 {rng}"


def extra_scope(question, programs, excluded=(), field=None):
    """비교과 유형 단위·순위·비교·없는 프로그램 질문 → 코드가 세어 답한다(AI 없음). 해당 없으면 None(아래 길 그대로).
    field: 질문정리가 「비교과」로 정리했으면 "비교과"(질문에 「비교과」 말이 없어도 본다).
    프로그램 하나를 이름으로 부른 질문(T1)은 여기서 답하지 않는다 — 아래 길에서 근거를 찾고, 없으면 _hold가 사실 답."""
    if EXTRA_BLOCK_RE.search(question):
        return None
    named = [p for p in programs if p in PROGRAMS]
    if named and not all(is_extra(p) for p in named):
        return None
    # ① 비교 「인적성검사랑 NCS 특강 중에 뭐가 나아요?」 — 두 쪽 모두 비교과면 이수 인원·만족도를 나란히
    m = EXTRA_SIDES.search(question)
    if m:
        a, b = (extra_loose(s, relaxed=True) or _type_pool(s, excluded)[1] for s in (m.group(1), m.group(2)))
        a = [n for n in a if n not in excluded]
        b = [n for n in b if n not in excluded and n not in a]
        if a and b:
            stories = sum(evidence_count(n) for n in a + b)
            head = ("두 쪽 모두 선배 경험담은 아직 없어서 어느 쪽이 나은지는 말씀드리기 어려워요." if not stories else
                    "여러 프로그램을 맞대 본 선배 경험담은 없어서 어느 쪽이 나은지는 말씀드리기 어려워요.")
            said = [_PARTICLE_RE.sub("", g.strip()) for g in (m.group(1), m.group(2))]
            message = (f"{head} 이수 인원·만족도로 보면 {_side_text(a, said[0])}, {_side_text(b, said[1])}이에요. "
                       f"노트를 열어 보거나 하나를 골라 물어봐 주세요.")
            return _extra_notes(a[:2] + b[:3], message, "비교과 비교")
    if named:
        return None
    labels, pool = _type_pool(question, excluded)
    asked_extra = bool(EXTRA_WORD_RE.search(question)) or field == "비교과"
    if not pool and not asked_extra:
        return None
    grade = EXTRA_GRADE.search(question)
    by_sat = bool(EXTRA_RANK_SAT.search(question))
    by_cnt = bool(EXTRA_RANK_CNT.search(question))
    if not pool:
        # 유형 말 없이 「비교과」만: 순위·목록을 묻는 말이면 130개 전체. 아니면(「토익 스터디 비교과」 — 이름·세부가 하나도
        # 안 맞음) None → 부르는 쪽이 「없는 프로그램」으로 보류한다(근거 있는 노트 카드를 대신 보여 주지 않는다)
        if not (grade or by_sat or by_cnt or (EXTRA_LIST.search(question) and not _content_words(question))):
            return None
        pool = [n for n in EXTRA if n not in excluded]
    label = "·".join(labels) + " 비교과" if labels else "비교과"
    total = len(pool)
    stories = [n for n in pool if evidence_count(n)]
    if grade:
        g = int(grade.group(1))
        order = sorted(pool, key=lambda n: (-_STU_GRADE.get(n, {}).get(g, 0), -(extra_count(n) or 0), n))
        order = [n for n in order if _STU_GRADE.get(n, {}).get(g)]
        if not order:
            message = f"{label} {total}개 가운데 {g}학년 때 이수한 선배 기록이 있는 프로그램은 없어요."
            return _extra_notes([], message, "비교과 학년")
        top = order[:3]
        message = (f"추천 순위는 따로 없어서, {g}학년 때 이수한 선배가 많은 {label}를 보여 드려요. "
                   + " · ".join(f"{short_name(n)} {_STU_GRADE[n][g]}명" for n in top) + " 순이에요.")
        return _extra_notes(order, message, "비교과 학년")
    if by_sat and not by_cnt:
        order = sorted(pool, key=lambda n: (-(extra_sat(n) or 0), -(extra_count(n) or 0), n))
        best = extra_sat(order[0])
        if best is None:
            return _extra_notes(order, f"{label} {total}개의 만족도 기록이 없어요.", "비교과 만족도")
        ties = [n for n in order if extra_sat(n) == best]
        names = " · ".join(short_name(n) for n in ties[:3]) + (f" 등 {len(ties)}개" if len(ties) > 3 else "")
        proxy = ("도움이 됐는지는 선배 경험담이 아직 없어 말하기 어려워서, 만족도로 보여 드려요. "
                 if EXTRA_PROXY.search(question) and not re.search(r"만족도", question) else "")
        message = (f"{proxy}{label} {total}개 중 만족도가 가장 높은 건 {names}(5점 만점에 {best:g}점)이에요. "
                   f"만족도가 높은 순서로 보여 드려요.")
        return _extra_notes(order, message, "비교과 만족도")
    order = sorted(pool, key=lambda n: (-(extra_count(n) or 0), -(extra_sat(n) or 0), n))
    top = order[:3]
    tail = ("아직 선배 경험담은 없어서" if not stories else f"선배 경험담이 있는 노트는 {len(stories)}개이고,")
    message = (f"{label}{_josa('은는', label)} {total}개 있어요. {tail} 이수 인원이 많은 순서로 보여 드려요: "
               + " · ".join(f"{short_name(n)} {_num(extra_count(n), '명')}" for n in top) + ".")
    if total == 1:
        message = f"{label}{_josa('은는', label)} 1개예요. {extra_facts(order[0])} {EXTRA_NO_STORY if not stories else ''}".strip()
    return _extra_notes(order, message, "비교과 유형" if labels else "비교과 목록")


# 「없는 프로그램」을 가를 때 빼는 말(묻는 말투·흔한 말). 이것 말고 남는 말이 있으면 그 활동 이름을 말한 것으로 본다
_EXTRA_STOP = re.compile(r"^(비교과|프로그램|활동|해|해본|해보신|보신|본|분|사람|선배|후기|있어요|있나요|있어|있을까요|있는|어때요|어땠어요"
                         r"|뭐|뭐가|뭐예요|무엇|어떤|게|건|거|중에|중|제일|가장|좋은|좋아요|추천|추천해|주세요|들을|만한|할|만해요|알려|"
                         r"줘|줘요|요|좀|혹시|학교|우리|외대|들으면|들어|하면|있으면|관련|종류|목록|보통|해요|하는|궁금해요|궁금)$")


def _content_words(question):
    ws = [w for w in re.findall(r"[가-힣]+|[A-Za-z]+", question) if not _EXTRA_STOP.match(_PARTICLE_RE.sub("", w) or w)
          and not _EXTRA_STOP.match(w) and not EXTRA_GRADE.search(w) and not re.fullmatch(r"\d*학년\S*", w)]
    return ws


def _extra_notes(order, message, route):
    return {"status": "notes", "lines": [], "sources": {}, "notes": _extra_cards(order), "suggestSenior": True,
            "message": message, "_route": route}


# 「대」 단독은 「대로」 앞에서 뺀다 — 「순서대로·제대로·생각대로」는 학교 이름이 아니다
SCHOOL_NAME = re.compile(r"\S(?:대학교|대학|대(?!로))(?:\s|에서|에|은|는|이|가|을|를|의|로|$)|university", re.I)


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


def _notes(programs, country, total=0):
    """status "notes": 답을 만들지 않고 해봤노트 카드로 안내한다(질문함에 저장하지 않음 — 답할 질문이 아니라 길 안내).
    total: 카드로 다 못 보여 준 전체 노트 수(부르는 쪽이 이미 5개로 자른 경우). [Q-13] 카드가 5개로 잘렸으면
    「5개 있어요」라고 하지 않고 전체 수를 말한다(11/25 캡처: 「관련 해봤노트가 5개」 뒤 「이게 다야?」)."""
    cards = [{"noteId": notes.note_id(n), "program": n, "country": PROGRAMS.get(n, {}).get("세부") if
              PROGRAMS.get(n, {}).get("분야") == "국제교류" else None, "evidenceCount": evidence_count(n),
              "oneLine": (notes.NOTES.get(notes.note_id(n)) or {}).get("oneLine", ""),   # [v2] 카드 한 줄(사전 생성 노트 커버)
              # [11/23 노트] 카드 띠용 노트 종류(교환·파견·인턴·비교과) — listNotes 카드의 type과 같은 값
              "type": (notes.NOTES.get(notes.note_id(n)) or {}).get("type") or notes._kind(n)}
             for n in programs if evidence_count(n)][:MAX_NOTES]
    if not cards:
        return None
    total = max(total, len([n for n in dict.fromkeys(programs) if evidence_count(n)]))
    if len(cards) == 1 and total <= 1:
        message = f"{cards[0]['program']} 해봤노트에서 선배들의 경험을 볼 수 있어요. 궁금한 내용을 물어보셔도 돼요."
    elif total > len(cards):
        message = f"{country or '관련'} 해봤노트 {total}개 중 근거가 많은 {len(cards)}개를 보여 드려요. 궁금한 노트를 골라 보세요."
    else:
        message = f"{country or '관련'} 해봤노트가 {len(cards)}개 있어요. 궁금한 노트를 골라 보세요."
    return {"status": "notes", "lines": [], "sources": {}, "notes": cards, "suggestSenior": True, "message": message}


# ── ①‴ [11/25 작업 87] 비교 질문 ─────────────────────────────────────
# 원우 실서버 시험(93): 마르부르크 생활비 답 뒤 「독일 다른 지역 대비 어떤건가요?」에 마르부르크 답을 되풀이했다.
# 근거는 학교마다 따로라 여러 곳을 맞대 볼 수 없다 → 코드의 고정 문구로 「비교는 아직 못 해요」 + 그 나라 노트 카드.
# 판정(AI 없음): ① 「어디가 더」「어느 학교가 더」「A랑 B 중 어디」「vs」 ② 「다른 지역·학교·나라…」 + 비교하는 말
#   ③ 프로그램·나라 이름이 둘 이상 + 비교하는 말. 「한국보다」「가격 대비」처럼 한 곳만 두고 하는 말은 비교로 보지 않는다.
COMPARE_DIRECT_RE = re.compile(
    r"어디\s*(가|이|를|가\s*제일)?\s*더|어느\s*(쪽|곳|학교|대학|나라|국가|도시|지역|프로그램|기관|회사|게|것)\s*(이|가|을|를)?\s*(더|제일|나아|낫|좋)"
    # 「학기 중에 뭐」「그 중에 뭐가 힘들었어요」는 비교가 아니다 — 「둘 중」「A랑 B 중」만 본다
    r"|(둘|셋|두\s*(곳|군데|학교|나라))\s*중(에|에서)?\s*(어디|어느|뭐|무엇)|(?<![A-Za-z])vs(?![A-Za-z])", re.I)
# 학교·나라 이름이 둘 이상일 때만 보는 말(「마르부르크랑 레이던 대학교 중 어디가 싸요?」). 「수업과 과제 중에 뭐가」는 비교가 아니다
COMPARE_PICK_RE = re.compile(r"어디|어느|중(에|에서)?\s*(뭐|무엇)")
COMPARE_OTHER_RE = re.compile(r"다른\s*(지역|학교|대학|도시|나라|국가|곳|데|프로그램|기관|회사)")
COMPARE_WORD_RE = re.compile(r"(?<!가격\s)(?<!가격)(?<!비용\s)(?<!비용)대비|비교(?!과)|보다|비해|차이|달라|다른가|다른지|나아|낫"
                             r"|더\s*(좋|싸|비싸|많|적|편|괜찮|추천|힘들|쉬|어렵)")


def _places(text):
    """질문에 나온 교환 나라 이름(긴 이름 먼저, 「독일어」는 뺌)."""
    out = []
    for c in sorted(COUNTRIES, key=len, reverse=True):
        if re.search(re.escape(c) + r"(?!어)", text) and not any(c in o for o in out):
            out.append(c)
    return out


def _direct_programs(question):
    """이름·별칭으로 직접 부른 프로그램(match_programs ① 단계와 같은 규칙). 인턴 사전(직군·약칭)으로 잡힌 업체 여럿은
    학생이 두 곳을 부른 것이 아니므로 세지 않는다(「무역 쪽 인턴 어디가 좋아요?」는 탐색)."""
    q = _norm(fix_names(question))
    hits = [(t, name) for t, name, is_alias in _TERMS if t in q and (not is_alias or _alias_ok(t, q))]
    return {name for t, name in hits if not any(t != t2 and t in t2 for t2, _ in hits)}


def is_compare(question):
    if COMPARE_DIRECT_RE.search(question):
        return True
    word = COMPARE_WORD_RE.search(question)
    if word and COMPARE_OTHER_RE.search(question):
        return True
    many = len(_direct_programs(question)) >= 2 or len(_places(question)) >= 2
    return bool(many and (word or COMPARE_PICK_RE.search(question)))


def _compare(question, programs, history):
    """status "notes": 비교 안내(고정 문구) + 그 나라(질문 > 질문의 프로그램 > 앞 대화) 노트 카드. 질문함에 저장하지 않는다."""
    named = [p for p in programs if p in PROGRAMS]
    places = _places(question)
    if not places:
        places = list(dict.fromkeys(PROGRAMS[p]["세부"] for p in named
                                    if PROGRAMS[p].get("분야") == "국제교류" and PROGRAMS[p].get("세부")))
    if not places and not named:
        for h in reversed(history):
            p = h["program"] if h["program"] in PROGRAMS else None
            if p and PROGRAMS[p].get("분야") == "국제교류" and PROGRAMS[p].get("세부"):
                places = [PROGRAMS[p]["세부"]]
            elif p:
                named = [p]
            else:
                places = _places(h["question"])
            if places or named:
                break
    pool = list(named)
    for c in places:
        pool += [n for n in COUNTRIES.get(c, []) if n not in pool]
    pool = [n for n in pool if evidence_count(n)]
    pool = [n for n in named if n in pool] + sorted([n for n in pool if n not in named], key=evidence_count, reverse=True)
    field = PROGRAMS.get(pool[0], {}).get("분야") if pool else None
    noun = {"국제교류": "학교", "현장실습": "기관"}.get(field, "학교" if places else "프로그램")
    head = f"여러 {noun} 비교는 아직 못 해요."
    found = _notes(pool, None)
    if not found:
        return {"status": "notes", "lines": [], "sources": {}, "notes": [], "suggestSenior": True,
                "message": f"{head} 궁금한 {noun} 하나를 골라 물어봐 주세요."}
    n, total = len(found["notes"]), len(pool)
    label = "·".join(places) if places else "관련"
    count = f"{total}개 중 근거가 많은 {n}개를" if total > n else f"{n}개를"
    found["message"] = f"{head} {label} 해봤노트 {count} 보여 드려요. 노트를 하나씩 열어 보거나, 한 곳을 골라 물어봐 주세요."
    return found


# ── ①⁗ [11/25 Q-13] 후속 질문·시기 질문 (코드, AI 없음) ───────────────────
# 11/25 미리 실사용 캡처: 노트 목록 뒤 「이게 다야?」「이 해봤노트 준 기준이 뭐야」에 질문정리가 「대화」로 보내
# 「앞에서 본 노트와 겹쳤다면…」(엇나간 문구)이 나왔고, 「인턴십 보통 언제 하는지」는 시기를 말하지 않고 노트 5개만 보여 줬다.
# 셋 다 데이터로 셀 수 있는 답이 있다 → 코드가 세어 고정 문구로 답한다.
MORE_RE = re.compile(r"(이게|그게|이거|이것|그거|요게)\s*(다|전부|끝|뿐|밖에)|^\s*(다야|끝이야|전부야)"
                     r"|(더|다른\s*(건|거|것|노트|곳|데))\s*(는|은|도)?\s*(없|있|보여|알려|찾아)")
CRITERIA_RE = re.compile(r"기준|뭘\s*보고|무엇을\s*보고|무슨\s*순서|순서(가|는)?\s*(뭐|어떻게|왜)"
                         r"|어떻게\s*(골|뽑|정했|정한|고른|찾은)|왜\s*(이|이걸|이거|이것|이런|그|저)\s*(노트|걸|거|것|곳|학교|기관|들)")
FOLLOW_MAX = 40   # 이보다 긴 말은 새 질문으로 본다
TIMING_RE = re.compile(r"(언제|몇\s*학년|어느\s*(시기|학기|때)|무슨\s*학기|시기)\s*(쯤|에|에는|가|는|이)?\s*"
                       r"(주로|보통|많이|제일|가장)?\s*(하|해|가|떠나|다녀|시작|나가|많|\?|$)")
SEASON = {"1": "1학기", "여름": "여름방학", "2": "2학기", "겨울": "겨울방학"}


def _field_of(text):
    return next((f for f, rx in FIELD_RE if rx.search(text)), None)


def _pool(field, country, excluded=()):
    """그 분야(·나라)의 근거 있는 노트 — 근거 많은 순. _explore가 카드를 고르는 범위와 같다."""
    names = [n for n, p in PROGRAMS.items() if (not field or p.get("분야") == field)
             and (not country or p.get("세부") == country) and n not in excluded and evidence_count(n)]
    return sorted(names, key=evidence_count, reverse=True)


def _noun(field, country):
    return f"{country} 해봤노트" if country else FIELD_NOUN.get(field, "해봤노트")


# ── ①⁗′ [11/25 Q-14] 근거 범위: 도시·「○○ 말고」 (코드, AI 없음) ───────────────
# 11/25 실사용 채점(길 2점): ① 「일본 도쿄 한달 생활비」에 도쿄 근거가 없는데 나라 대조로 나가사키·긴키 근거로 답했다.
#   ② 「나가사키외국어대학교 말고 일본 대학 전체의 해봤노트에도 없나요?」가 「대화」로 빠져 엇나간 문구가 나왔다.
# 도시는 학교 이름·별칭에 있을 때만 그 학교로 본다. 근거 글자에 도시가 나오는 것(「마드리드로 여행」)은 그 도시 학교가 아니다.
# 도시 표는 교환 나라(COUNTRIES)의 큰 도시만 — data/가 아니라 여기 둔다(나라 대조와 같은 코드 규칙).
CITIES = {
    "일본": ["도쿄", "오사카", "교토", "후쿠오카", "삿포로", "요코하마", "나고야", "고베", "나가사키", "히로시마", "오키나와"],
    "프랑스": ["파리", "리옹", "마르세유", "니스", "툴루즈", "보르도", "스트라스부르", "낭트", "몽펠리에", "그르노블"],
    "독일": ["베를린", "뮌헨", "프랑크푸르트", "쾰른", "함부르크", "슈투트가르트", "드레스덴", "하이델베르크", "본", "라이프치히"],
    "스페인": ["마드리드", "바르셀로나", "발렌시아", "세비야", "그라나다", "말라가", "빌바오"],
    "네덜란드": ["암스테르담", "로테르담", "위트레흐트", "헤이그", "레이던"],
    "러시아": ["모스크바", "상트페테르부르크", "블라디보스토크", "야쿠츠크"],
    "포르투갈": ["리스본", "포르투", "코임브라"],
    "스웨덴": ["스톡홀름", "예테보리", "웁살라", "룬드", "말뫼"],
    "이탈리아": ["로마", "밀라노", "피렌체", "베네치아", "나폴리", "볼로냐", "토리노", "시에나"],
    "미국": ["뉴욕", "로스앤젤레스", "샌프란시스코", "시카고", "보스턴", "시애틀", "워싱턴", "콜럼버스"],
    "브라질": ["상파울루", "상파울로", "리우데자네이루", "브라질리아"],
    "벨기에": ["브뤼셀", "앤트워프", "겐트", "루벤", "브뤼헤"],
    "덴마크": ["코펜하겐", "오르후스", "오덴세"],
    "아일랜드": ["더블린", "코크", "골웨이"],
    "체코": ["프라하", "브르노", "플젠"],
}
CITY_COUNTRY = {c: k for k, cs in CITIES.items() if k in COUNTRIES for c in cs}
CITY_END = r"(?=에서|으로|에|은|는|의|이|가|도|로|랑|\s|[?!.,~]|$)"
# 「○○대학교·○○대학·○○대」의 ○○(띄어 쓴 「리옹 대학」은 ○○ 없음 — 잡지 않음). 뒤는 SCHOOL_NAME과 같은 경계
SCHOOL_WORD_RE = re.compile(r"대학|학교")
CITY_TOPIC_RE = re.compile(r"날씨|기후|치안|소매치기|위험|안전|물가|생활\s*환경|도시\s*(분위기|환경)")   # [작업 104] 도시 자체 이야기
SCHOOL_STEM_RE = re.compile(r"(\S+?)(?:대학교|대학|대(?!로))(?=\s|에서|에|은|는|이|가|을|를|의|로|$)")


def _in_city(name, city):
    terms = [name] + list(PROGRAMS.get(name, {}).get("별칭") or [])
    return any(city in t for t in terms)


def city_scope(text, programs, country):
    """돌려주는 값: (도시, 나라, 그 도시 학교 — 근거 많은 순) 또는 None.
    학교를 이름으로 부른 질문(programs가 나라 대조가 아님)·인턴 질문은 보지 않는다."""
    if (programs and not country) or _field_of(text) == "현장실습":
        return None
    for city in sorted(CITY_COUNTRY, key=len, reverse=True):
        # 낱말로 따로 쓴 도시만 — 앞에 한글이 없고 뒤는 조사·공백·문장부호·끝(총괄 검토 #282:
        #   「포르투갈」의 포르투, 「테니스」「비즈니스」의 니스, 「로마자」의 로마, 「일본」「본인」의 본에 걸리지 않게)
        if re.search(r"(?<![가-힣])" + re.escape(city) + CITY_END, text):
            k = CITY_COUNTRY[city]
            if country and k != country:   # 「독일 파리」처럼 나라와 안 맞으면 나라를 따른다
                return None
            # [11/26 작업 104] 목록에 없는 학교 이름(「뤼미에르 리옹 음악대학」「파리 국립대학」)이면 도시로 넓히지 않는다 —
            #   match_country의 SCHOOL_NAME 규칙(함정 53)과 같은 뜻. 「리옹대학교」「리옹 대학」처럼 도시 + 대학만이면 그대로
            if any(m.group(1) != city for m in SCHOOL_STEM_RE.finditer(text)):
                return None
            named = sorted([n for n in COUNTRIES[k] if _in_city(n, city) and evidence_count(n)], key=evidence_count, reverse=True)
            return city, k, named
    return None


def _city_none(city, country, excluded=()):
    """status "notes": 그 도시 학교 노트 0개 + 그 나라 노트 카드. 다른 학교 근거로 그 도시 이야기를 하지 않는다."""
    pool = [n for n in COUNTRIES.get(country, []) if n not in excluded and evidence_count(n)]
    pool = sorted(pool, key=evidence_count, reverse=True)
    head = (f"{city}에 있는 학교 해봤노트는 0개예요. 다른 도시 학교의 근거로는 {city} 이야기를 답하지 않을게요. ")
    found = _notes(pool, country)
    if not found:
        return {"status": "notes", "lines": [], "sources": {}, "notes": [], "suggestSenior": True,
                "message": head + f"{country} 교환·파견 해봤노트도 아직 없어요."}
    found["message"] = head + f"{country} 교환·파견 해봤노트는 {len(pool)}개 있어요. 노트를 열어 보거나 그 학교로 물어봐 주세요."
    return found


def _city_pick(city, country, named):
    """status "notes": 그 도시 학교 노트 카드 + 「어느 학교인지 골라 주세요」. 질문함에 저장하지 않는다(답할 수 있는 질문 — 학교만 모름)."""
    found = _notes(named, country)
    names = f"({'·'.join(named)})" if len(named) <= 3 else ""
    found["message"] = (f"{city}에는 해봤노트가 있는 학교가 {len(named)}곳 있어요{names}. "
                        "학교마다 선배 이야기가 달라서 섞어 답하지 않을게요. 어느 학교인지 골라 주세요.")
    return found


def exclude_scope(question, rest, excluded):
    """「○○ 말고 (나라·분야) 노트에도 없나요?」 → 뺀 뒤 남은 노트 수(코드가 셈). 이번 말에 「말고」가 없거나,
    있고 없음을 묻는 말이 아니거나, 주제어(생활비 등)가 있는 새 질문이면 None(아래 길 그대로)."""
    if not excluded or not EXCLUDE_RE.search(question) or not EXIST_RE.search(rest) or has_topic(rest):
        return None
    base = PROGRAMS.get(excluded[0], {})
    field = _field_of(rest) or base.get("분야")
    country = match_country(rest)[0] if field != "현장실습" else None
    if not country and field == "국제교류" and re.search(r"다른|말고|전체|나머지", question):
        country = base.get("세부")
    pool = _pool(field, country, excluded)
    lab, noun = _label(excluded), _noun(field, country)
    if not pool:
        return {"status": "chat", "lines": [], "sources": {}, "suggestSenior": False, "chips": [
                    {"label": "해봤노트 둘러보기", "action": "notes", "payload": {"field": field, "exclude": list(excluded)}}],
                "message": f"{lab}{_josa('을를', lab)} 빼면 {noun}는 0개예요. 지금은 {lab} 노트뿐이에요."}
    found = _notes(pool, country, total=len(pool))
    names = "·".join(pool) if len(pool) <= 3 else ""
    found["message"] = (f"{lab}{_josa('을를', lab)} 뺀 {noun}는 {len(pool)}개 있어요"
                        + (f"({names})" if names else "") + f". 노트를 열어 보거나 그 {'기관' if field == '현장실습' else '학교'}로 물어봐 주세요.")
    return found


def follow_up(question, history, programs, excluded=()):
    """앞 답(노트 목록·답)에 대한 「이게 다야?」「기준이 뭐야?」 → status "chat" 고정 문구. 해당 없으면 None.
    새 질문(프로그램·나라·주제어가 있거나 긴 말)이면 보지 않는다."""
    if not history or programs or has_topic(question) or len(question) > FOLLOW_MAX:
        return None
    kind = "더" if MORE_RE.search(question) else "기준" if CRITERIA_RE.search(question) else None
    last = history[-1]
    if not kind or last["status"] not in ("notes", "ok"):
        return None
    q = last["question"]
    program = last["program"] if last["program"] in PROGRAMS else None
    country, _ = match_country(q)
    field = _field_of(q) or (PROGRAMS[program]["분야"] if program else None)
    chips = [{"label": "해봤노트 둘러보기", "action": "notes", "payload": {"field": field, "exclude": list(excluded)}}]
    if last["status"] == "ok":
        if not program:
            return None
        if kind == "더":
            message = (f"{program} 해봤노트에는 선배 근거가 {evidence_count(program)}개 있어요. 그중 질문에 맞는 문장만 골라 답했어요. "
                       f"다른 주제(비용·생활·학점 등)도 물어보시면 그 근거로 답해 드릴게요.")
        else:
            message = f"{program} 해봤노트의 선배 근거 가운데 질문에 맞는 문장을 골라 답했어요. 답 아래 근거에서 원문을 볼 수 있어요."
    else:
        pool = _pool(field, country, excluded)
        shown, noun = min(MAX_NOTES, len(pool)), _noun(field, country)
        if not pool:
            return None
        if kind == "기준":
            message = (f"질문에 맞는 {noun} 가운데 선배 근거(보고서 문단·인터뷰 문장)가 많은 순서로 {shown}개까지 보여 드렸어요. "
                       f"카드의 「근거 n건」이 그 수예요. 좋고 나쁨을 매긴 순위는 아니에요.")
        elif len(pool) > shown:
            hint = {"현장실습": "기관 유형이나 주제", "국제교류": "나라·학교나 주제"}.get(field, "주제")
            message = (f"근거가 많은 {shown}개만 먼저 보여 드렸어요. {noun}는 모두 {len(pool)}개예요. "
                       f"궁금한 {hint}를 적어 주시면 그 노트에서 선배 이야기를 찾아 드릴게요.")
        else:
            message = f"{noun}는 지금 그 {len(pool)}개가 전부예요. 선배 이야기가 더 쌓이면 늘어나요."
    return {"status": "chat", "lines": [], "sources": {}, "suggestSenior": False, "message": message, "chips": chips,
            "_route": f"후속({kind})"}


def season_counts(names):
    """선배 보고서(같은 선배·같은 학기·같은 프로그램 = 한 편)를 시기별로 센다 → [(시기, 편수)] 많은 순."""
    from collections import Counter
    docs = {(e["프로그램명"], e.get("학번"), e.get("semester")) for n in names for e in EVIDENCE.get(n, [])}
    c = Counter(SEASON.get(str(s).rsplit("-", 1)[-1]) for _, _, s in docs if s)
    c.pop(None, None)
    return c.most_common()


def timing(question, history, programs, country, excluded=()):
    """「인턴 보통 언제 해요?」「교환은 몇 학년에 가요?」 → 근거 보고서의 학기를 세어 말하고 노트 카드(status "notes").
    모집 일정(기한·발표)은 규정 질문으로 먼저 빠진다(is_official). 분야·프로그램을 질문에서 알 수 없으면 None."""
    if not TIMING_RE.search(question) or has_topic(question):
        return None
    field = _field_of(question)
    names = [n for n in programs if n in PROGRAMS and n not in excluded and evidence_count(n)
             and (not field or PROGRAMS[n].get("분야") == field)]   # 「독일 인턴 언제」에 독일 교환 노트를 쓰지 않는다
    if not names:
        country = None
    if names:
        label = f"{country} 교환·파견 해봤노트" if country else \
            (f"{names[0]} 해봤노트" if len(names) == 1 else "관련 해봤노트")
    elif field:
        names = _pool(field, None, excluded)
        label = FIELD_NOUN[field]
    else:
        return None
    seasons = season_counts(names)
    if not seasons:
        return None
    total = sum(n for _, n in seasons)
    found = _notes(names, country, total=len(names))
    if not found:
        return None
    # 노트에는 학기만 있고 학년은 없다(가상데이터 열) — 「몇 학년」은 없다고 먼저 말한다
    head = "몇 학년에 했는지는 해봤노트에 없어요. " if re.search(r"몇\s*학년", question) else ""
    tail = "근거가 많은 노트부터 보여 드려요." if len(found["notes"]) > 1 else "노트에서 선배 경험을 볼 수 있어요."
    found["message"] = (head + f"{label} 선배 보고서 {total:,}편을 시기별로 보면 "
                        + " · ".join(f"{s} {n:,}편" for s, n in seasons)
                        + f"이에요. 모집 일정은 학교 공지에서 확인해 주세요. {tail}")
    return found


# ── ①‴′ [11/26] 인원·순위 질문 (코드, AI 없음) ──────────────────────────
# 실서버 「독일 7+1 갈 때 가장 많이 간 대학교?」(11/26 15:26)에 근거가 많은 순으로 노트만 보여 줬다 — 실제 간 학생 수
# (뷔르츠부르크 6 · 마르부르크 5 · 마인츠 4)와 순서가 다르다. 학적(students.json)의 파견대학·해외경험 유형을 세어 고정 문구로 답한다.
# 노트가 없는 학교는 인원만 말하고, 카드는 노트가 있는 학교를 인원 많은 순으로. 사람 칸(학번 등)은 세기만 하고 내보내지 않는다.
# 유형 묶음(미리 11/26): 이름에 「파견학생」이 들어간 유형(학과·우수입학·국제 파견학생) = 7+1 파견. 아너스 파견은 7+1이 아니다.
ABROAD = [(s["파견대학"], s.get("해외경험 유형") or "") for s in _json("students.json", []) if s.get("파견대학")]
KIND_ORDER = ("교환학생", "7+1 파견", "자비유학생", "아너스 파견")
KIND_WORDS = (("7+1 파견", re.compile(r"7\s*\+\s*1|파견\s*학생|학과\s*파견|우수\s*입학|국제\s*파견")),
              ("교환학생", re.compile(r"교환")), ("자비유학생", re.compile(r"자비")), ("아너스 파견", re.compile(r"아너스")))
# 「가는 곳」을 묻는 말만 본다 — 「가장 많이 한 일」「주말에 많이 가는 곳」「대학 순위」「인기 있는 음식」「한 반 인원」은 아니다
RANK_RE = re.compile(r"(가장|제일|젤)\s*많이\s*(가|갔|간|다녀|보내|뽑|파견|선택|지원)"
                     r"|많이\s*(간|가는|갔던|다녀온|파견된|보내는|뽑는)\s*(학교|대학|나라|국가|파견지)"
                     r"|몇\s*명(이나|이|정도|쯤)?\s*(가|갔|간|다녀|뽑|보내|파견)"
                     r"|(간|갔던|다녀온|가는|파견된)\s*(사람|학생|선배)\s*(수|인원|이\s*몇)|(파견|다녀온|간)\s*인원"
                     r"|인기\s*(있는|많은)?\s*(학교|대학|파견지)|(학교|대학|파견지|어디)\S{0,2}\s*(제일|가장)?\s*인기"
                     r"|(인원|인기|파견)\s*순위|인원\s*(많은|순)")
# 학교가 아닌 곳을 묻는 말(「독일에서 제일 많이 간 여행지」 — has_topic에 없는 말)
RANK_NOT_RE = re.compile(r"여행|관광|맛집|식당|음식|카페|마트|도시|동네|수업|과목|강의|동아리|축제|술집|가게|병원")
# 학교 하나를 부른 질문은 인원만 묻는 말이어야 한다(「마르부르크에서 가장 많이 간 곳」은 그 학교 안 이야기)
RANK_ONE_RE = re.compile(r"몇\s*명|인원|(사람|학생|선배)\s*(수|이\s*몇)")
RANK_TOP = 3   # 문구에 말하는 학교 수(나머지는 「모두 n곳」으로)


def kind_group(kind):
    """학적의 해외경험 유형 → 묶음. 「파견학생」이 들어간 유형은 7+1 파견."""
    return "7+1 파견" if "파견학생" in kind else kind


def rank(question, programs, country, excluded=()):
    """「독일 7+1 가장 많이 간 대학교?」「마르부르크 몇 명 갔어요?」 → 학적의 파견 인원을 세어 말하고 노트 카드(status "notes").
    나라나 학교를 질문에서 알 수 없으면 None(전국 순위는 나라 이름을 놓쳤을 때 엉뚱한 답이 되므로 하지 않는다)."""
    if not RANK_RE.search(question) or has_topic(question) or RANK_NOT_RE.search(question) \
            or _field_of(question) == "현장실습":
        return None
    scope = [p for p in (COUNTRIES.get(country, []) if country else programs)
             if PROGRAMS.get(p, {}).get("분야") == "국제교류" and p not in excluded]
    if not scope or (len(scope) == 1 and not RANK_ONE_RE.search(question)):
        return None
    from collections import Counter
    kinds = [k for k, rx in KIND_WORDS if rx.search(question)]
    counts = {}
    for school, kind in ABROAD:
        k = kind_group(kind)
        if school in scope and (not kinds or k in kinds):
            counts.setdefault(school, Counter())[k] += 1
    order = sorted(counts, key=lambda n: (-sum(counts[n].values()), -evidence_count(n), n))
    kind_label = "·".join(kinds) if kinds else "교환·파견"
    if country:
        where = f"{country} {kind_label}"
    elif len(scope) == 1:
        where = f"{scope[0]} {kind_label}" if kinds else scope[0]
    else:
        where = kind_label

    def num(n):   # 「6명(교환학생 4·7+1 파견 2)」 — 유형을 골라 물었거나 한 유형뿐이면 괄호 없음
        c = counts[n]
        part = "·".join(f"{k} {c[k]}" for k in KIND_ORDER if c[k]) if not kinds and len(c) > 1 else ""
        return f"{sum(c.values())}명" + (f"({part})" if part else "")

    def say(n):
        return f"{n} {num(n)}"

    if not order:
        message = f"{where} 다녀온 선배는 아직 없어요."
    elif len(scope) == 1:
        message = f"{where} 다녀온 선배는 {num(order[0])}이에요."
    elif len(order) == 1:
        top = order
        message = f"{where} 다녀온 선배는 {say(order[0])}이에요."
    else:
        total = lambda n: sum(counts[n].values())   # noqa: E731
        top = order[:RANK_TOP]
        while len(top) < min(len(order), MAX_NOTES) and total(order[len(top)]) == total(top[-1]):
            top.append(order[len(top)])   # 3등과 같은 인원이면 함께 말한다(5곳까지)
        message = (f"{where} 다녀온 선배는 {len(order)}곳 {sum(map(total, order))}명이에요. "
                   f"많이 간 곳은 {' · '.join(say(n) for n in top)} 순이에요.")
        missing = [n for n in top if not evidence_count(n)]
        if missing:
            message += f" {', '.join(missing)}{_josa('은는', missing[-1])} 아직 해봤노트가 없어요."
    # 카드: 인원 많은 순, 노트 없는 학교는 빼고. 인원이 0명이면 그 나라 노트를 근거 많은 순으로
    found = _notes(order or sorted(scope, key=evidence_count, reverse=True), country)
    if not found:
        return {"status": "chat", "lines": [], "sources": {}, "suggestSenior": False, "message": message,
                "chips": [{"label": "해봤노트 둘러보기", "action": "notes",
                           "payload": {"field": "국제교류", "exclude": list(excluded)}}]}
    found["message"] = message + (" 많이 간 학교 노트부터 보여 드려요." if order and len(found["notes"]) > 1 else "")
    return found


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
DOC_WORD = {"귀국보고서": "보고서",  # [Q-12] 11/25 미리: 화면 용어 「결과보고서」 → 「보고서」
            "현장실습후기": "현장실습후기", "인터뷰": "선배 인터뷰"}


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


EMPTY_ANSWER = object()   # compose: 답쓰기가 {"답":[]}(근거가 질문에 안 맞음)를 낸 경우의 표지


def compose(question, picked, max_lines=MAX_ANSWER_LINES, on_empty=None):
    """AI(답쓰기) → 문장마다 인용 근거와 대조. 돌려주는 값: {"status","lines","sources","singleSenior"} 또는 None(다 버려짐·실패).
    답쓰기가 빈 목록을 내면 on_empty를 돌려준다(기본 None — tools/build_notes.py 칸 요약은 그대로 None).
    max_lines: 일치검사로 보낼 문장 수 상한(작업 78 칸 요약은 칸 근거 수에 따라 3·5)."""
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
    if not answers:
        return on_empty
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
        todo.append((text, cited, " ".join(c["text"] for c in cited)))
        if len(todo) >= max_lines:
            break
    return _match_lines(todo, max_lines)


def _match_lines(todo, max_lines):
    """todo: [(답 문장, 인용 근거 목록, 답검사에 줄 원문)] → 답검사(Opus)를 통과한 줄로 응답. 없으면 None. compose·compose_full 공통."""
    if not todo:
        return None
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_lines) as pool:   # 일치검사는 문장별로 동시에(인터뷰 요약과 같은 방식)
        matched = list(pool.map(lambda t: match_check(t[2], t[0]), todo))
    lines, sources, used = [], {}, set()
    for (text, cited, _), ok in zip(todo, matched):
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


# ── ②′ [11/26 A안] 전문 길: 근거 전문 + 두 단계 번호 ─────────────────────
def ask_full():
    """플래그 VCC_ASK_FULL=1이면 전문 길. 부를 때마다 읽는다(평가 스크립트가 환경변수로 두 길을 바꿔 돌린다)."""
    return os.environ.get("VCC_ASK_FULL", "0").strip() == "1"


# ── [11/26 작업 35 · #278 3-3] 질문정리와 답쓰기 겹쳐 돌리기 ─────────────────
# 첫 질문(앞 대화 없음)에 학교(프로그램) 이름이 글자로 잡히면 질문정리를 기다리지 않고 답쓰기-전문을 같이 시작한다.
# 질문정리 뒤 길이 전문 길(_answer_full)이고 프로그램·근거 글이 같을 때만 그 답을 쓴다. 대화·탐색·규정 등 다른 길이면 버린다.
# 버리는 것은 답쓰기 한 번뿐 — 답검사(Opus)는 답을 쓰기로 정한 뒤에만 부른다. 규정·인원·비교·도시·비교과 같은
# AI 없는 길은 이보다 먼저 걸러지므로 순서는 그대로다. 답쓰기에는 질문정리가 다듬은 질문 대신 원래 질문이 들어간다
# (첫 질문은 질문정리가 조사만 다듬는다 — docs/조사/278_첫답시간_미리.md 3절). 끄기: VCC_ASK_OVERLAP=0
_overlap_pool = None


def ask_overlap():
    """겹쳐 돌리기 켜짐 여부(기본 켬, 전문 길에서만). 부를 때마다 읽는다(측정 스크립트가 환경변수로 바꿔 돌린다)."""
    return os.environ.get("VCC_ASK_OVERLAP", "1").strip() != "0"


def _overlap_start(question, history, excluded, programs, country):
    """조건이 맞으면 답쓰기-전문을 미리 시작해 {programs, evidence, future}를, 아니면 None을 돌려준다(코드만, 0.01초 안)."""
    global _overlap_pool
    if not (ask_full() and ask_overlap()) or history or excluded or country or not programs:
        return None
    if programs != [p for p in match_programs(question) if p not in excluded]:   # 학교 이름을 글자로 부른 질문만
        return None
    paras, _ = full_evidence(question, programs)
    if not paras:
        return None
    if _overlap_pool is None:
        from concurrent.futures import ThreadPoolExecutor
        _overlap_pool = ThreadPoolExecutor(4)
    return {"programs": list(programs), "evidence": render_evidence(paras),
            "future": _overlap_pool.submit(write_full, question, paras)}


def _overlap_take(spec, programs, paras):
    """미리 시작한 답쓰기를 쓸 수 있으면 그 결과(끝날 때까지 기다림), 아니면 None. 같은지는 답쓰기가 본 근거 글로 가린다."""
    if not spec:
        return None
    if spec["programs"] != list(programs) or spec["evidence"] != render_evidence(paras):
        spec["used"] = False
        return None
    spec["used"] = True
    return spec["future"].result()


_SEASON_RANK = {"1": 1, "여름": 2, "2": 3, "겨울": 4}


def _semester_key(sem):
    """'2026-1' → (2026, 1), '2026-여름' → (2026, 2). 학기를 모르는 줄(인터뷰 등)은 가장 최근으로 친다."""
    m = re.match(r"(\d{4})-(.+)$", str(sem or ""))
    return (int(m.group(1)), _SEASON_RANK.get(m.group(2), 0)) if m else (9999, 9)


def _para_label(r):
    """문단 머리의 칸 이름: 보고서는 문항(번호 뺌), 후기·인터뷰는 칸."""
    if r.get("docType") == "귀국보고서" and r.get("문항"):
        return re.sub(r"^\s*[\d-]+\.\s*", "", r["문항"])
    return r.get("칸") or ""


def full_evidence(question, programs, cap=FULL_CHAR_CAP):
    """프로그램(들)의 보고서·후기 문단 + 공개 동의 인터뷰 문장 전부(문단은 쪼개지 않는다).
    돌려주는 값: (문단 목록, 보류 이유). 문단: {n, sourceId, docType, program, semester, label, sents}.
    정렬은 프로그램 순서 → 최근 학기 먼저. 글자 수가 cap을 넘으면 오래된 학기 문단부터 뺀다.
    현장실습 근무조건 질문(INTERVIEW_ONLY_INTERN)은 옛 길처럼 인터뷰의 근무조건·지원·선발 칸만 쓴다."""
    rows, why = [], ""
    for pi, name in enumerate(programs):
        iv = notes.interview_lines(name)
        if PROGRAMS.get(name, {}).get("분야") == "현장실습" and INTERVIEW_ONLY_INTERN.search(question):
            got = [r for r in iv if r["칸"] in ("근무조건", "지원·선발")]
            if not got:
                why = why or "인터뷰로만 채우는 칸(근무조건)"
        else:
            got = iv + EVIDENCE.get(name, [])
        for r in got:
            sents = split_sentences(r["text"])
            if sents:
                rows.append({"pi": pi, "order": len(rows), "row": r, "sents": sents,
                             "key": _semester_key(r.get("semester"))})
    total = sum(len(x["row"]["text"]) for x in rows)
    if total > cap:   # 오래된 학기부터, 같은 학기면 뒤 문단부터 뺀다
        for x in sorted(rows, key=lambda x: (x["key"], -x["order"])):
            if total <= cap:
                break
            x["drop"] = True
            total -= len(x["row"]["text"])
        rows = [x for x in rows if not x.get("drop")]
    rows.sort(key=lambda x: (x["pi"], -x["key"][0], -x["key"][1], x["order"]))
    paras = [{"n": i, "sourceId": x["row"]["id"], "docType": x["row"]["docType"], "program": x["row"]["프로그램명"],
              "semester": x["row"].get("semester"), "label": _para_label(x["row"]), "sents": x["sents"]}
             for i, x in enumerate(rows, 1)]
    if not paras:
        why = why or "근거 없음"
    return paras, ("" if paras else why)


def render_evidence(paras):
    """답쓰기-전문에 넣는 근거 글. 호출마다 글자가 같아야 캐시가 맞는다(시각·임의 값을 넣지 않는다).
    [3] 보고서 · 2025 · 선배A · 기숙사 정보
      [3-1] …   [3-2] …"""
    letters, out, cur = {}, ["근거:"], None
    for p in paras:
        if p["program"] != cur:
            cur = p["program"]
            out.append(f"## {cur} (문단 {sum(1 for q in paras if q['program'] == cur)}개)")
        who = _person_of(p["sourceId"])
        if who not in letters:
            letters[who] = chr(ord("A") + len(letters)) if len(letters) < 26 else str(len(letters) + 1)
        year = str(p.get("semester") or "")[:4] or "–"
        out.append(f"[{p['n']}] {DOC_WORD.get(p['docType'], p['docType'])} · {year} · 선배{letters[who]}"
                   + (f" · {p['label']}" if p["label"] else ""))
        out += [f"  [{p['n']}-{j}] {s}" for j, s in enumerate(p["sents"], 1)]
    return "\n".join(out)


_REF_RE = re.compile(r"^\s*\[?\s*(\d+)\s*(?:[-‐–]\s*(\d+))?\s*\]?\s*$")


def parse_ref(x):
    """근거 번호 → (문단, 문장|None). "3-2" → (3, 2) · "3"·3 → (3, None)(옛 번호: 문단 전체). 모양이 틀리면 None."""
    if isinstance(x, bool):
        return None
    if isinstance(x, int):
        return (x, None)
    if isinstance(x, float) and x.is_integer():
        return (int(x), None)
    if isinstance(x, str):
        m = _REF_RE.match(x)
        if m:
            return (int(m.group(1)), int(m.group(2)) if m.group(2) else None)
    return None


def full_sources(refs, by_n):
    """인용 번호들 → (코드 검사 원문, 답검사 원문, 인용 문단 목록).
    코드 검사: 지목 문장 + 같은 문단 앞뒤 한 문장(문단 번호만 대면 문단 전체).
    답검사: 문단 전체, 지목 문장 앞에 ▶. 같은 문단을 여러 번 가리키면 한 번만 싣는다."""
    groups = {}
    for pn, sn in refs:
        groups.setdefault(pn, set()).add(sn)
    verify_parts, check_parts, cited = [], [], []
    for pn, g in groups.items():
        p = by_n[pn]
        sents = p["sents"]
        if None in g:
            idx = range(len(sents))
        else:
            idx = sorted({i for s in g for i in range(max(0, s - 2), min(len(sents), s + 1))})
        verify_parts.append(" ".join(sents[i] for i in idx))
        marked = {s - 1 for s in g if s is not None}
        check_parts.append(" ".join(("▶ " if i in marked else "") + s for i, s in enumerate(sents)))
        cited.append({k: p[k] for k in ("sourceId", "docType", "program", "semester")})
    return " ".join(verify_parts), "\n".join(check_parts), cited


def write_full(question, paras):
    """답쓰기-전문 호출 하나(AI). 돌려주는 값: callAI 결과(호출이 예외면 ok=False). 겹쳐 돌리기(_overlap_start)가 따로 부른다."""
    system, shots = load_prompt("askBoo-답쓰기-전문")
    try:   # 지침·예시·근거 전문이 캐시(고정), 질문만 가변
        return callAI("답쓰기-전문", shots + [{"role": "user", "content": f"질문: {question}\n출력:"}],
                      system=system, cache=render_evidence(paras))
    except Exception:
        return {"ok": False}


def compose_full(question, paras, max_lines=MAX_ANSWER_LINES_FULL, written=None):
    """AI(답쓰기-전문) → 문장마다 두 단계 번호로 원문 대조 → 답검사. 돌려주는 값: (응답|None|EMPTY_ANSWER, 원문 인용 후보).
    원문 인용 후보: 답쓰기가 가리킨 문장(문단만 가리키면 그 문단 첫 문장), 처음 가리킨 순서. 다 버려졌을 때 폴백에 쓴다.
    written: [작업 35] 겹쳐 돌리기로 미리 받아 둔 답쓰기 결과(write_full). 있으면 답쓰기를 다시 부르지 않는다."""
    r = write_full(question, paras) if written is None else written
    j = r.get("json") if r.get("ok") else None
    answers = j.get("답") if isinstance(j, dict) else None
    if not isinstance(answers, list):
        return None, []
    if not answers:
        return EMPTY_ANSWER, []
    by_n = {p["n"]: p for p in paras}
    todo, quotes, seen = [], [], set()
    for a in answers:
        if not isinstance(a, dict):
            continue
        refs = []
        for x in a.get("근거") if isinstance(a.get("근거"), list) else []:
            ref = parse_ref(x)
            p = by_n.get(ref[0]) if ref else None
            if not p or (ref[1] is not None and not 1 <= ref[1] <= len(p["sents"])):   # 없는 번호는 버린다
                continue
            if ref not in refs:
                refs.append(ref)
        for pn, sn in refs:
            if (pn, sn or 1) not in seen:
                seen.add((pn, sn or 1))
                p = by_n[pn]
                quotes.append({"text": p["sents"][(sn or 1) - 1],
                               **{k: p[k] for k in ("sourceId", "docType", "program", "semester")}})
        text = a.get("text").strip() if isinstance(a.get("text"), str) else ""
        if not text or not refs or not POLITE_END.search(text):   # 근거 번호 없는 문장·반말은 버린다
            continue
        verify_src, check_src, cited = full_sources(refs, by_n)
        if verify_facts(text, verify_src):
            continue
        todo.append((text, cited, check_src))
        if len(todo) >= max_lines:
            break
    return _match_lines(todo, max_lines), quotes


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
def _dept(question, programs):
    """담당 부서(departments.json 한 줄): 프로그램의 운영부서코드 → 없으면 질문 말로(현장실습·인턴 D02, 특교원·탄뎀 D03, 그 외 D01)."""
    code = PROGRAMS.get(programs[0], {}).get("운영부서코드") if programs else None
    if not code:
        code = "D02" if re.search(r"현장실습|인턴", question) else "D03" if re.search(r"특교원|탄뎀", question) else "D01"
    return DEPTS.get(code, {})


def _contact(dept):
    """[11/26 작업 104] 「문의: 국제교류팀 02-2173-9999」 — 대표전화(가상)가 없으면 빈 글(문구도 officialPhone도 없음)."""
    phone = (dept.get("대표전화(가상)") or "").strip()
    return f"문의: {dept.get('부서명', '담당 부서')} {phone}" if phone else ""


def _official(me, question, programs, save):
    dept = _dept(question, programs)
    qid = _save(me, question, programs[0] if programs else None, None, "official", save)
    contact = _contact(dept)
    out = {"status": "official", "lines": [], "sources": {}, "questionId": qid, "suggestSenior": False,
           "_program": programs[0] if programs else None,
           "officialUrl": dept.get("공식안내URL", ""),
           "message": f"학교 규정에 관한 질문이라 {dept.get('부서명', '담당 부서')} 공식 안내에서 정확한 내용을 확인해 주세요."
                      + (f" {contact}" if contact else "")}
    if contact:   # [작업 104] 국제처 피드백(#331) — 값이 없으면 필드를 넣지 않는다
        out["officialPhone"] = dept["대표전화(가상)"].strip()
    return out


# ── [11/26 작업 104] 선배 답 + 「꼭 확인」 안내 (코드 고정 문구, AI 없음) ─────────────
# 국제처 피드백(#331 요청 1): 비자·보험·지원 서류·파견 대학 규정은 선배 경험이 있어도 나라·해마다 바뀐다.
# 경계: 외대 제도(학점 인정 신청·외대 장학금·선발·기한·자격 — OFFICIAL_RE·OFFICIAL_WIDE_RE)는 지금처럼 official(선배 답 없음).
#       나머지 넷은 선배 경험이 근거로 있으므로(보고서 1-1·1-2 칸) 답은 그대로 주고, 답 끝에 확인 안내 + 담당 연락처만 붙인다.
#   ① 비자·보험·체류 허가·거주 등록 → 「대사관과 ○○팀」
#   ② 파견 대학 지원 서류·입학 허가·지원 절차 → 「모집 요강과 ○○팀」
#   ③ 파견·현지 대학 규정(local_scope가 규정에서 뺀 질문: 현지 장학금·현지 수강 학점 등) → 「그 대학 안내와 ○○팀」
#   ④ [11/26 미리 결정] 학점 인정 경험(「학점 인정 받을 때 주의할 점」「챙길 서류」 — 규정 표현 「인정 신청·인정받을 수」는
#      official이 먼저) → 「학과 사무실」. departments.json에 학과 사무실 줄이 없어 연락처(문의·officialPhone)는 붙이지 않는다
#   생활비·기숙사·수업·교통 같은 생활 질문에는 붙이지 않는다(과잉 안내 0 — test_askboo_v2). 걸리는 말이 있을 때만.
CHECK_VISA_RE = re.compile(r"비자|보험|체류\s*허가|거주\s*(허가|등록)|레지던스\s*퍼밋|외국인\s*등록")
CHECK_APPLY_RE = re.compile(r"입학\s*허가|지원\s*(서류|절차)|(파견|교환|지원|제출)\s*서류|서류\s*(는|를|가|은)?\s*(뭐|뭘|무엇|어떤|준비|내|챙)"
                            r"|원서|지원하려면|지원\s*방법|지원\s*과정")
CHECK_CREDIT_RE = re.compile(r"학점\s*인정|성적\s*인정|인정\s*(받|학점|과목)|(학점|성적)\s*(변환|환산)")
CHECK_TEXT = {
    "비자": "비자·보험은 나라와 시기마다 규정이 바뀌어요. 선배 경험은 참고만 하고, 대사관과 {부서}에서 꼭 확인해 주세요.",
    "지원": "지원 서류와 절차는 해마다 바뀔 수 있어요. 선배 경험은 참고만 하고, 모집 요강과 {부서}에서 꼭 확인해 주세요.",
    "인정": "학점 인정은 학과와 과목마다 기준이 달라요. 선배 경험은 참고만 하고, 학과 사무실에서 꼭 확인해 주세요.",
    "규정": "파견 대학의 규정은 학교와 해마다 달라요. 선배 경험은 참고만 하고, 그 대학 안내와 {부서}에서 꼭 확인해 주세요.",
}
CHECK_NO_CONTACT = {"인정"}   # 담당이 학과 사무실 — 부서 대표전화를 붙이면 다른 곳으로 안내하게 된다


def check_kind(question):
    """확인 안내가 필요한 질문이면 "비자"|"지원"|"인정"|"규정", 아니면 None."""
    if CHECK_VISA_RE.search(question):
        return "비자"
    if CHECK_APPLY_RE.search(question):
        return "지원"
    if CHECK_CREDIT_RE.search(question):
        return "인정"
    # 수강 경험 말투(「파견 대학에서 몇 학점 수강했어요?」)는 규정을 묻는 말이 아니라 빼고, 주체가 현지인 것만(현지 장학금 등)
    if local_scope(question) and not COURSE_TONE_RE.search(question) \
            and (OFFICIAL_RE.search(question) or OFFICIAL_WIDE_RE.search(question)):
        return "규정"
    return None


def official_check(question, programs):
    """ok·hold 응답에 붙일 officialCheck {message, officialUrl, officialPhone?} 또는 None."""
    kind = check_kind(question)
    if not kind:
        return None
    dept = _dept(question, programs)
    contact = "" if kind in CHECK_NO_CONTACT else _contact(dept)
    out = {"message": CHECK_TEXT[kind].format(부서=dept.get("부서명", "담당 부서")) + (f" {contact}" if contact else ""),
           "officialUrl": dept.get("공식안내URL", "")}
    if contact:
        out["officialPhone"] = dept["대표전화(가상)"].strip()
    return out


def _place(country, programs):
    """[Q-38] 보류 문구에 쓸 나라 — 나라로 학교 둘 이상을 잡았을 때만. 아니면 None(학교 이름 문구 그대로)."""
    return country if country and len(programs) > 1 else None


def _hold(me, question, program, section, save, why="", place=None):
    """place: [Q-38] 나라 단위 보류(「독일 해봤노트에는 …」). 이때 한 학교 노트 링크(noteId)는 주지 않는다.
    질문함에는 지금처럼 program(근거가 가장 많은 학교)으로 담는다."""
    qid = _save(me, question, program, section, "hold", save)
    if why == "담기":
        message = HOLD_SAVED
    elif not program:
        message = HOLD_NO_PROGRAM
    elif place:
        message = HOLD_NO_TOPIC.format(program=place)
    elif evidence_count(program):     # 노트는 있는데 이 내용만 없다 → 그 노트로 갈 수 있게 noteId도 준다
        message = HOLD_NO_TOPIC.format(program=program)
    elif is_extra(program):           # [작업 106] 근거 0 비교과 — 「없어요」만 말하지 않고 코드가 가진 사실부터(AI 없음)
        message = f"{extra_facts(program)} {EXTRA_NO_STORY} {HOLD_EXTRA_TAIL}"
    else:
        message = HOLD_MESSAGE
    out = {"status": "hold", "lines": [], "sources": {}, "questionId": qid, "suggestSenior": True, "message": message,
           "_program": program}
    if program and (evidence_count(program) or is_extra(program)) and not place and why != "담기":
        out["noteId"] = notes.note_id(program)   # 담기 응답에는 노트 링크를 붙이지 않는다. 비교과는 근거 0이어도 노트(이수 인원·만족도)로
    if not save:
        out["_why"] = why   # 평가 스크립트에서만 보이는 보류 이유
    return out


def _save(me, question, program, section, status, save):
    if not save:
        return None
    from runtime_fns import add_question
    return add_question(me, question, program=program, section=section, status=status)


_FREQUENT_BIGRAMS.update(_frequent_bigrams())   # 근거를 다 읽은 뒤 한 번만 센다
