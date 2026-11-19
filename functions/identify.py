# identify.py — 본인 식별 문장 검사 (작업 70, 원본: docs/spec-v1.md 4장 summarizeInterview `identifying`, PRD 4절·9절)
#
# 공개 초안 문장 하나가 그 선배를 특정할 수 있는지 코드(정규식·사전)로만 본다. AI를 쓰지 않는다.
#   성적 숫자 — 평점·학점·GPA 수치, 어학 점수, 등수·수석
#   수상     — 수상·입상·우승·성적 장학 등
#   실명     — 「성+이름 + 교수님/선배/씨…」, Prof./Mr. + 영문 이름
#   특정 인물 — '유일한 한국인', '최초', 과대표·학생회장처럼 한 사람으로 좁혀지는 말
#   학번·연락처 — H0000 꼴 학번, 9자리 학번, 전화번호, 메일
# true면 동의 시트에서 그 문장을 기본 꺼짐 + 주의 라벨(디자인 규칙 7-②). 문장을 고치거나 지우지는 않는다(선배가 정함).
#
#   from identify import check
#   check("평점 4.3으로 선발됐어요")  →  {"identifying": True, "reasons": ["성적 숫자"]}
import re

SURNAMES = "김이박최정강조윤장임한오서신권황안송류전홍고문양손배백허유남심노하곽성차주우구민진나지엄채원천방공현함변염여추도소석선설마길연위표명기반왕금옥육인맹제모탁국어은편용예봉경"
TITLES = r"(?:교수님|교수|선생님|선배님|선배|후배|씨|님|매니저님|대리님|과장님|팀장님)"
# 성씨 글자로 시작하지만 사람 이름이 아닌 말(오탐 막기)
NOT_NAMES = {"이번", "이전", "이후", "이런", "이분", "정말", "전공", "전체", "전에", "장학", "한국", "한분", "한명", "한두", "현지",
             "지도", "담당", "주임", "고생", "같은", "다른", "우리", "남자", "여자", "남은", "동기", "조교", "선배", "유학",
             "학과", "기숙", "공동", "공부", "방학", "강의", "수업", "원어", "외국", "도움", "주변", "모든", "여러", "어느",
             "안내", "연구", "인턴", "인사", "채용", "주재", "주재원", "차장", "부장", "과장", "대리", "사수", "멘토", "직원"}

RULES = [
    ("성적 숫자", re.compile(
        r"(?:평점|평균\s*학점|학점\s*평균|GPA|성적)\s*(?:은|이|은\s*약|이\s*약)?\s*\d\.\d{1,2}"
        r"|\d\.\d{1,2}\s*/\s*4\.[35]"
        r"|(?:토익|TOEIC|토플|TOEFL|IELTS|아이엘츠|TestDaF|테스트다프|DELF|DALF|델프|달프|HSK|JLPT|JPT|OPIc|오픽|DELE|TORFL|괴테|Goethe)\s*\w*\s*\d"
        r"|\d{3,4}\s*점|\d\s*등(?!급)|수석|석차|전\s*과목\s*A|올\s*A", re.I)),
    ("수상", re.compile(r"수상|입상|우승|준우승|최우수상|우수상|장려상|대상을|금상|은상|동상을|표창|성적\s*장학|전액\s*장학|장학생으로")),
    ("실명", re.compile(rf"(?<![가-힣])([{SURNAMES}][가-힣]{{1,2}})\s*{TITLES}"
                       r"|(?:Prof\.?|Professor|Mr\.?|Ms\.?|Mrs\.?|Dr\.?)\s+[A-Z][a-z]+")),
    ("특정 인물", re.compile(r"유일한|유일하게|혼자만\s*한국인|한국인은\s*(?:저|나)\s*혼자|최초|첫\s*파견생|과대표|과\s*대표|학생회장|총학생회|회장을\s*맡")),
    ("학번·연락처", re.compile(r"(?<![A-Za-z0-9])H\d{4}(?!\d)|(?<!\d)20\d{7}(?!\d)|01[016-9][\s-]?\d{3,4}[\s-]?\d{4}|[\w.+-]+@[\w-]+\.[\w.]+", re.I)),
]


def check(text):
    """돌려주는 값: {"identifying": 참/거짓, "reasons": [찾은 갈래, ...]}"""
    reasons = []
    for name, rx in RULES:
        for m in rx.finditer(text or ""):
            if name == "실명" and m.group(1) and m.group(1) in NOT_NAMES:
                continue
            reasons.append(name)
            break
    return {"identifying": bool(reasons), "reasons": reasons}


def mark(public_draft):
    """summarizeInterview(작업 21)가 공개 초안에 붙인다: 문장마다 identifying 값을 채워 그대로 돌려준다."""
    for sec in (public_draft or {}).get("sections", []):
        for ln in sec.get("lines", []):
            ln["identifying"] = check(ln.get("text", ""))["identifying"]
    return public_draft
