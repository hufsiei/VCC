# test_msg_check.py — msg_check.py 시험 (작업 27). 실행: cd functions && python test_msg_check.py
# 완료 기준(작업내역 27): 차단 사례 전부 막히고 이유 문구가 나옴, 이메일은 허용. 시험 사례 통과 5건·차단 10건 이상.
# 더해서: 일반 쪽지·근거 문단·개발 질문·사용 로그 질문은 코드 단계에서 막히면 안 된다(오탐 0). 하나라도 틀리면 종료코드 1.
import csv
import json
import sys
from pathlib import Path

from msg_check import MESSAGES, banned_words, check_message, check_public_text

ROOT = Path(__file__).resolve().parent.parent

PASS = [   # 쪽지 — 통과해야 함
    "선배님 안녕하세요! 마르부르크 기숙사 신청 시기 여쭤봐도 될까요?",
    "메일 boo.hufs@example.com으로 자료 주실 수 있을까요?",          # 이메일은 허용(spec)
    "진짜 궁금해서 미치겠어요ㅠㅠ 기숙사 경쟁률 어땠어요?",            # 강한 감정 표현
    "솔직히 학점 인정 절차는 너무 엉망인 것 같아요. 선배님은 어떻게 하셨어요?",   # 제도 불만
    "2024 2025학년도 기준으로 알려 주셔도 돼요",                       # 숫자 나열(옛 8자리 규칙 오탐)
    "시발점이 어디인지부터 알려 주세요",                                # 금지어 예외(출발점)
    "3학년 1학기에 파견 갔는데 월 380유로 들었어요",
    "동대문구 이문동 근처에 사는데 같이 스터디해요",                    # 넓은 주소는 허용(상세주소 없음)
    "바쁘신데 시간 내 주셔서 감사합니다!",
    # 금지어 오탐 회귀 시험(11/20 검토: 공백·숫자를 지우고 찾던 방식의 오탐)
    "오후 3시 발표 끝나고 연락드릴게요", "3시발표 끝나고요", "오후 3시 바로 갈게요", "김OO씨 바로 연락드릴게요",
    "불이 꺼져서 놀랐어요", "시험이 닥쳐서 바빠요", "죽어라 공부했어요", "시바우라공업대학 교환 어때요?",
    "개 새끼를 낳았대요", "엿 먹는 문화가 있어요", "가방을 뒤져라 했어요", "한 심하게 아팠어요",
    "병신년 역사 수업 들었어요", "시바견 키우는 선배 있어요?",
]
BLOCK = [   # (쪽지, 기대 사유)
    ("제 번호 010-1234-5678로 연락 주세요", "연락처"),
    ("번호01098765432예요", "연락처"),
    ("공일공 일이삼사 오육칠팔로 문자 주세요", "연락처"),
    ("카톡 아이디 boo2026 추가해 주세요", "연락처"),
    ("인스타 @boo.hufs 로 DM 주세요", "연락처"),
    ("오픈채팅 open.kakao.com/o/abcDEF 들어오세요", "연락처"),
    ("저희 집 101동 1203호로 오세요", "연락처"),
    ("저 H0143이에요 학번으로 찾아 주세요", "학번"),
    ("학번 202301234입니다", "학번"),
    ("staff01 계정으로 물어봐도 돼요?", "학번"),
    ("시.발 답장 좀 빨리 해요", "비방"),
    ("ㅅ ㅂ 진짜 느리네", "비방"),
    ("그런 것도 모르면서 선배라고 글을 썼어요? 한심하네요.", "비방"),
    ("너 같은 선배는 또라이야", "비방"),   # '꺼져'는 '불이 꺼져서' 오탐 때문에 목록에서 빼고 AI 판정(P1)에 맡김
    ("병-신 같은 노트네요", "비방"),
    ("개*새끼 같은 소리", "비방"),
    ("ㅂ ㅅ 같아요", "비방"),
]
PUBLIC = [  # (공개 요약 문장, ok, reasons, identifying, official)
    ("기숙사는 월 380유로였어요.", True, [], False, False),
    ("학점 인정 신청은 귀국하고 바로 했어요.", True, [], False, True),
    ("평점 4.3으로 선발됐어요.", True, [], True, True),          # 본인 식별은 막지 않고 알림
    ("궁금하면 boo@example.com으로 메일 주세요.", False, ["연락처"], True, False),   # 공개 글에는 메일도 안 됨
    ("자세한 건 blog.naver.com/hufs_boo 참고하세요.", False, ["연락처"], False, False),
    ("제 학번은 H0469예요.", False, ["학번"], True, False),
    ("담당자가 병신 같았어요.", False, ["비방"], False, False),
]


def main():
    bad = []
    for t in PASS:
        r = check_message(t)
        if not r["ok"]:
            bad.append(f"쪽지 오탐: {t!r} → {r}")
    for t, why in BLOCK:
        r = check_message(t)
        if r["ok"] or r["reason"] != why or r["message"] != MESSAGES[why]:
            bad.append(f"쪽지 놓침·사유 틀림: {t!r} 기대 {why} → {r}")
    for t, ok, reasons, ident, official in PUBLIC:
        r = check_public_text(t)
        if (r["ok"], r["reasons"], r["identifying"], r["official"]) != (ok, reasons, ident, official):
            bad.append(f"공개 문장 틀림: {t!r} → {r}")
        if not r["ok"] and not r["message"]:
            bad.append(f"공개 문장 이유 문구 없음: {t!r}")

    # 작업 53 쪽지 판정 사례: 비방이 아닌 쪽지(기대 True)는 코드 단계에서 막히면 안 됨. 비방(기대 False)은 AI(P1) 몫이라 참고만
    cases = json.loads((Path(__file__).parent / "eval53_cases.json").read_text(encoding="utf-8"))["쪽지검사"]
    caught = 0
    for c in cases:
        r = check_message(c["쪽지"])
        if c["기대"] and not r["ok"]:
            bad.append(f"53번 정상 쪽지 오탐: {c['쪽지']!r} → {r}")
        if not c["기대"] and not r["ok"]:
            caught += 1

    # 실제처럼 쓰인 문장들 — 쪽지로 보내도 막히면 안 됨(근거 문단은 공개 문장 검사도 통과해야 함)
    evidence = json.loads((ROOT / "data" / "evidence.json").read_text(encoding="utf-8"))
    for e in evidence:
        if not check_message(e["text"])["ok"]:
            bad.append(f"근거 문단 쪽지 오탐: {e['id']} {check_message(e['text'])}")
        if not check_public_text(e["text"])["ok"]:
            bad.append(f"근거 문단 공개 검사 오탐: {e['id']} {check_public_text(e['text'])['reasons']}")
    qs = [r["질문"] for r in csv.DictReader(open(ROOT / "data" / "eval-questions.csv", encoding="utf-8-sig"))]
    log = ROOT / "data" / "usage-log.json"
    if log.exists():
        qs += [r["질문"] for r in json.loads(log.read_text(encoding="utf-8"))["questions"]]
    for q in qs:
        if not check_message(q)["ok"]:
            bad.append(f"질문 오탐: {q!r} → {check_message(q)}")

    if banned_words("시발점 시바견 병신년 3시 발표 3시발표 시바우라 등신불") != []:
        bad.append(f"금지어 예외가 걸림: {banned_words('시발점 시바견 병신년 3시 발표 3시발표 시바우라 등신불')}")

    n = len(PASS) + len(BLOCK) + len(PUBLIC) + len(cases) + len(evidence) * 2 + len(qs)
    print(f"쪽지·공개 문장 검사 시험 {n}건(통과 {len(PASS)} · 차단 {len(BLOCK)} · 공개 {len(PUBLIC)} · 53번 사례 {len(cases)}"
          f" · 근거 {len(evidence)}×2 · 질문 {len(qs)}) 중 틀림 {len(bad)}건")
    print(f"  참고: 53번 비방 사례 {sum(not c['기대'] for c in cases)}건 중 코드(금지어)로 잡힌 것 {caught}건 — 나머지는 AI 판정(P1) 몫")
    for b in bad[:20]:
        print("  -", b)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
