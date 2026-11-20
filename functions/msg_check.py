# msg_check.py — 쪽지 검사·공개 요약 재검사의 코드 규칙 (원우, 작업 27). AI 없음.
# 규칙: docs/spec-v1.md 4장 checkMessage·saveConsent, PRD 2-2 표(연락처·학번·메일·URL은 정규식 P0, 비방 AI 판정은 P1),
#       HCX 원칙 v2 4절 '쪽지 검사 = 금지어 목록 + 연락처·학번 정규식'.
#
#   check_message(text)      쪽지 한 통 → {"ok": True} 또는 {"ok": False, "reason": "연락처"|"학번"|"비방", "message": ...}
#                            메일은 허용(spec). 연락처·학번은 mask.py의 find()와 같은 규칙으로 잡는다(규칙을 한 곳에).
#                            이 함수가 ok면 서버(runtime_fns.checkMessage)가 비방 AI 판정(P1, docs/prompts/쪽지검사.txt)을 이어서 한다.
#   check_public_text(text)  선배가 공개 요약 문장을 고친 뒤 다시 보는 검사(saveConsent edits.changed) →
#                            {"ok", "reasons", "identifying", "identifyReasons", "official"}
#                            해봤노트에 실리는 글이라 메일·링크·주소까지 막는다. 본인 식별(identify.py)은 막지 않고 알려만 준다
#                            (동의 시트에서 기본 꺼짐 + 주의 라벨). official = 규정성 진술('개인 경험이에요' + 공식 안내 링크).
# 시험: cd functions && python test_msg_check.py
import re

from identify import check as identify_check
from mask import find

MESSAGES = {
    "연락처": "전화번호나 SNS 아이디는 보낼 수 없어요. 이메일은 괜찮아요.",
    "학번": "학번은 보낼 수 없어요.",
    "비방": "상대를 깎아내리는 말은 보낼 수 없어요.",
}
PUBLIC_MESSAGES = {
    "연락처": "해봤노트에는 연락처·메일·링크·주소를 넣을 수 없어요.",
    "학번": "해봤노트에는 학번을 넣을 수 없어요.",
    "비방": "해봤노트에는 다른 사람을 깎아내리는 말을 넣을 수 없어요.",
}

# 직원 계정 아이디도 학번처럼 막는다(기존 checkMessage 규칙 유지)
STAFF_ID = re.compile(r"(?<![A-Za-z0-9])staff\d+(?![A-Za-z0-9])", re.I)
# 한글로 쓴 전화번호(공일공 일이삼사 오육칠팔) — 숫자로 바꿔 쓰는 우회
_KNUM = "공영일이삼사오육칠팔구"
KOREAN_PHONE = re.compile(rf"공\s*일\s*공(?:[\s\-.]*[{_KNUM}]){{7,8}}")

# 금지어(명백한 욕설·인신공격). 글자 사이 공백·기호·숫자를 지운 뒤 찾는다(시.발, ㅅ ㅂ). '시발점'처럼 뜻이 다른 말은 예외로 둔다.
# 강한 감정 표현('진짜 궁금해 미치겠어요')·제도 불만은 비방이 아니다(쪽지검사 프롬프트와 같은 기준) → 여기 넣지 않고 AI(P1)에 맡긴다.
BANNED = [
    r"시발", r"씨발", r"씨빨", r"씨바", r"시바(?!견)", r"ㅅㅂ", r"ㅆㅂ", r"ㅆ발", r"쌍년", r"썅",
    r"병신", r"ㅂㅅ", r"븅신", r"등신", r"개새끼", r"개새기", r"개색기", r"개색히", r"개쉐", r"ㄱㅅㄲ", r"새끼야", r"색기야",
    r"좆", r"ㅈ같", r"존나\s*(?:못|싫|짜증)", r"닥쳐", r"꺼져", r"미친(?:놈|년|새끼|것)", r"또라이", r"찐따", r"한심하",
    r"엿\s*먹", r"뒤져라", r"죽어라", r"죽여버", r"패버",
]
_BANNED_RE = re.compile("|".join(BANNED))
_EXCEPT = re.compile(r"시발점|시발역|시바견|병신년|등신불")      # 다른 뜻(출발점·시바견·역사 용어)
_SQUEEZE = re.compile(r"[\s\W\d_]+")

# 규정성 진술(build_notes.py의 OFFICIAL_RE와 같은 기준 — 바꾸면 둘 다)
OFFICIAL_RE = re.compile(r"학점\s*인정|인정\s*(신청|서류|받)|전공\s*인정|교양\s*인정|변환\s*성적|몇\s*학점|장학|선발|자격|평점|등록금")


def banned_words(text):
    """금지어 목록에 걸린 말(정규화 전 원문 기준이 아니라 공백·기호를 지운 글에서 찾음)."""
    s = _EXCEPT.sub("", _SQUEEZE.sub("", text or ""))
    return sorted({m.group() for m in _BANNED_RE.finditer(s)})


def _kinds(text):
    kinds = {k for k, *_ in find(text or "")}
    if STAFF_ID.search(text or ""):
        kinds.add("학번")
    if KOREAN_PHONE.search(text or ""):
        kinds.add("연락처")
    return kinds


def check_message(text):
    """쪽지 한 통. 학번 → 연락처(전화·메신저·링크·주소) → 비방(금지어) 순으로 첫 사유만 돌려준다. 메일은 허용."""
    kinds = _kinds(text)
    if "학번" in kinds:
        return {"ok": False, "reason": "학번", "message": MESSAGES["학번"]}
    if kinds & {"연락처", "링크", "주소"}:
        return {"ok": False, "reason": "연락처", "message": MESSAGES["연락처"]}
    if banned_words(text):
        return {"ok": False, "reason": "비방", "message": MESSAGES["비방"]}
    return {"ok": True}


def check_public_text(text):
    """선배가 고친 공개 요약 문장 하나. ok가 False면 그 문장은 저장하지 않고 이유를 보여 준다.
    identifying은 막지 않고 알림만(동의 시트 주의 라벨), official은 '개인 경험이에요' 표시용."""
    kinds = _kinds(text)
    reasons = []
    if "학번" in kinds:
        reasons.append("학번")
    if kinds & {"연락처", "링크", "주소", "메일"}:
        reasons.append("연락처")
    if banned_words(text):
        reasons.append("비방")
    ident = identify_check(text or "")
    return {
        "ok": not reasons,
        "reasons": reasons,
        "message": PUBLIC_MESSAGES[reasons[0]] if reasons else "",
        "identifying": ident["identifying"],
        "identifyReasons": ident["reasons"],
        "official": bool(OFFICIAL_RE.search(text or "")),
    }
